"""
Perform flux density bootstrapping.

This module performs flux density bootstrapping using fluxscale, fits power-law
models to the bootstrapped flux densities, and sets the model column with the
fitted values.
"""

import os
from typing import Any, Dict, List, Tuple, Optional
import numpy as np
import scipy as sp
from casatasks import fluxscale, casalog, setjy, rmtables
from evla_pipe.plotting import plotms
from evla_pipe.utils import MAINLOG, logprint, runtiming, find_EVLA_band, format_qa_status
from evla_pipe.pipeline_steps import register_step


def task_logprint(msg: str) -> None:
    """
    Log a message to the fluxboot log file.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/fluxboot.log")


def _fitfunc(p: List[float], x: np.ndarray) -> np.ndarray:
    """
    Linear function for power-law fitting.

    Parameters
    ----------
    p : list of float
        Parameters [intercept, slope]
    x : np.ndarray
        Independent variable (log frequency)

    Returns
    -------
    np.ndarray
        Fitted values
    """
    return p[0] + p[1] * x


def _errfunc(p: List[float], x: np.ndarray, y: np.ndarray, err: np.ndarray) -> np.ndarray:
    """
    Error function for least-squares fitting.

    Parameters
    ----------
    p : list of float
        Parameters [intercept, slope]
    x : np.ndarray
        Independent variable (log frequency)
    y : np.ndarray
        Dependent variable (log flux density)
    err : np.ndarray
        Errors on y

    Returns
    -------
    np.ndarray
        Residuals normalized by errors
    """
    return (y - _fitfunc(p, x)) / err


def _bootstrap_flux(
    pipeline_context: Dict[str, Any],
    flux_field_select_string: str
) -> Dict[str, Any]:
    """
    Perform flux density bootstrapping using fluxscale.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and calibrators_ms
    flux_field_select_string : str
        Field selection string for flux calibrator

    Returns
    -------
    dict
        Fluxscale results dictionary

    Notes
    -----
    Creates fluxgaincalFcal.g calibration table and writes flux densities
    to a text file.
    """
    task_logprint("Doing flux density bootstrapping")

    msname = pipeline_context.get("msname")
    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")

    fluxscale_output = msname.rstrip("ms") + "fluxdensities"
    task_logprint(f"Flux densities will be written to '{fluxscale_output}'")

    # Clean up old output files
    os.system(f"rm -rf {fluxscale_output}")

    # Temporarily redirect CASA log
    casalog.setlogfile(fluxscale_output)

    # Remove old calibration table
    rmtables("fluxgaincalFcal.g")

    # Run fluxscale
    fluxscale_result = fluxscale(
        vis=calibrators_ms,
        caltable="fluxgaincal.g",
        fluxtable="fluxgaincalFcal.g",
        reference=[flux_field_select_string],
        transfer=[""],
        listfile="",
        append=False,
        refspwmap=[-1],
        incremental=False,
        fitorder=1,
    )

    # Restore CASA log
    casalog.setlogfile(MAINLOG)

    return fluxscale_result


def _fit_power_law(
    fluxscale_result: Dict[str, Any],
    center_frequencies: Dict[int, float]
) -> List[List[Any]]:
    """
    Fit a power law to the bootstrapped flux densities.

    Parameters
    ----------
    fluxscale_result : dict
        Results from fluxscale task
    center_frequencies : dict
        Mapping of spw to center frequency in Hz

    Returns
    -------
    list of list
        Fitting results for each source/band combination.
        Each entry is [source, spws, fluxdensity, spix, SNR, reffreq]

    Notes
    -----
    Fits log(flux) vs log(frequency) with a linear model per source and band.
    """
    task_logprint("Fitting data with power law")

    results = []
    sources = []
    flux_densities = []
    spws = []

    # Parse fluxscale results
    for field_id, field_data in fluxscale_result.items():
        # Skip non-numeric keys
        try:
            int(field_id)
        except ValueError:
            continue

        sourcename = field_data.get("fieldName")
        if not sourcename:
            continue

        for spw_id, spw_data in field_data.items():
            # Skip non-numeric keys
            try:
                int(spw_id)
            except ValueError:
                continue

            flux_items = spw_data.get("fluxd")
            flux_errs = spw_data.get("fluxdErr")

            if flux_items and flux_errs:
                for f_d, f_e in zip(flux_items, flux_errs):
                    if f_d != -1 and f_d != 0:
                        sources.append(sourcename)
                        flux_densities.append([float(f_d), float(f_e)])
                        spws.append(int(spw_id))

    # Fit power law for each source and band
    for source in np.unique(sources):
        indices = np.argwhere(np.array(sources) == source).squeeze(axis=1)
        bands = [
            find_EVLA_band(center_frequencies.get(spws[i], 0.0))
            for i in indices
        ]

        for band in np.unique(bands):
            lfreqs = []
            lfds = []
            lerrs = []
            uspws = []

            # Collect data for this source/band
            for ii in indices:
                center_freq = center_frequencies.get(spws[ii])
                if center_freq is not None and find_EVLA_band(center_freq) == band:
                    lfreqs.append(np.log10(center_freq))
                    lfds.append(np.log10(flux_densities[ii][0]))

                    # Compute error in log space
                    ratio = (
                        flux_densities[ii][1] / flux_densities[ii][0]
                        if flux_densities[ii][0] != 0
                        else 0.0
                    )
                    lerrs.append(np.log10(np.e) * ratio if ratio != 0 else 0.0)
                    uspws.append(spws[ii])

            # Fit or use simple estimates
            if len(lfds) <= 2:
                # Not enough points for a fit
                aa = lfds[0] if lfds else 0.0
                bb = 0.0
                SNR = 0.0
            else:
                # Least-squares fit
                alfds = np.array(lfds)
                alerrs = np.array(lerrs)
                alfreqs = np.array(lfreqs)
                pinit = [0.0, 0.0]

                try:
                    fit_out = sp.optimize.leastsq(
                        _errfunc,
                        pinit,
                        args=(alfreqs, alfds, alerrs),
                        full_output=True,
                    )
                    aa, bb = fit_out[0]
                    covar = fit_out[1]

                    # Compute SNR of spectral index
                    summed_error = np.sum((_fitfunc([aa, bb], alfreqs) - alfds) ** 2)
                    residual_variance = (
                        summed_error / (len(alfds) - 2)
                        if len(alfds) > 2
                        else 0.0
                    )
                    SNR = (
                        np.abs(bb) / np.sqrt(covar[1][1] * residual_variance)
                        if covar is not None and residual_variance > 0
                        else 0.0
                    )
                except Exception as e:
                    task_logprint(
                        f"Error during power law fitting for {source} {band}: {e}"
                    )
                    aa = 0.0
                    bb = 0.0
                    SNR = 0.0

            # Convert back to linear space
            reffreq = 10 ** lfreqs[0] / 1e9 if lfreqs else 1.0
            fluxdensity = 10 ** (aa + bb * lfreqs[0]) if lfreqs else 0.0
            spix = bb

            results.append([source, uspws, fluxdensity, spix, SNR, reffreq])

            task_logprint(
                f"{source} {band} fitted spectral index = {spix:.4f} and SNR = {SNR:.2f}"
            )
            task_logprint("Frequency (GHz), data (Jy), error (Jy), fitted data (Jy):")

            for ii in range(len(lfreqs)):
                flux_exp = 10 ** lfreqs[ii] / 1e9
                err_exp = 10 ** lfds[ii]
                SS = fluxdensity * (flux_exp / reffreq) ** spix
                fderr = (
                    lerrs[ii] * err_exp / np.log10(np.e)
                    if np.log10(np.e) != 0
                    else 0.0
                )
                task_logprint(
                    f"    {flux_exp:.3f} {10**lfds[ii]:.3f} {fderr:.3f} {SS:.3f}"
                )

    return results


def _set_fitted_flux(
    pipeline_context: Dict[str, Any],
    fitting_results: List[List[Any]],
    scratch: bool
) -> str:
    """
    Set the power-law fit in the model column using setjy.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and calibrators_ms
    fitting_results : list of list
        Fitting results from _fit_power_law
    scratch : bool
        Whether to use scratch columns

    Returns
    -------
    str
        QA2 status ("Pass" or "Fail")

    Notes
    -----
    Sets QA2_fluxboot to "Fail" if any spectral index has |spix| > 5.0
    """
    task_logprint("Setting power-law fit in the model column")

    QA2_fluxboot = "Pass"
    ms_active = pipeline_context.get("msname")
    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")

    for result in fitting_results:
        source, spws, fluxdensity, spix, _, reffreq_ghz = result

        for spw_i in spws:
            task_logprint(f"Running setjy on spw {spw_i} for source {source}")

            for vis in (calibrators_ms, ms_active):
                try:
                    setjy(
                        vis=vis,
                        field=str(source),
                        spw=str(spw_i),
                        selectdata=False,
                        scalebychan=True,
                        standard="manual",
                        fluxdensity=[fluxdensity, 0, 0, 0],
                        spix=spix,
                        reffreq=f"{reffreq_ghz}GHz",
                        usescratch=scratch,
                    )

                    # Check spectral index sanity
                    if abs(spix) > 5.0:
                        QA2_fluxboot = "Fail"
                        task_logprint(
                            f"WARNING: Spectral index {spix:.2f} exceeds threshold"
                        )

                except Exception as e:
                    task_logprint(
                        f"Unable to complete flux scaling operation for "
                        f"field {source}, spw {spw_i}: {e}"
                    )
                    QA2_fluxboot = "Fail"

    return QA2_fluxboot


def _plot_flux_model(pipeline_context: Dict[str, Any]) -> None:
    """
    Plot model calibrator flux densities.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and plot settings

    Notes
    -----
    Creates bootstrappedFluxDensities.png plot file.
    """
    task_logprint("Plotting model calibrator flux densities")

    ms_active = pipeline_context.get("msname")
    calibrator_scan_select_string = pipeline_context.get(
        "calibrator_scan_select_string", ""
    )
    corrstring = pipeline_context.get("corrstring", "RR,LL")

    try:
        plotms(
            vis=ms_active,
            xaxis="freq",
            yaxis="amp",
            ydatacolumn="model",
            selectdata=True,
            scan=calibrator_scan_select_string,
            correlation=corrstring,
            averagedata=True,
            avgtime="1e8",
            avgscan=True,
            transform=False,
            extendflag=False,
            iteraxis="",
            coloraxis="field",
            plotrange=[],
            title="",
            xlabel="",
            ylabel="",
            showmajorgrid=False,
            showminorgrid=False,
            showgui=False,
            plotfile="bootstrappedFluxDensities.png",
            highres=True,
            overwrite=True,
        )
    except Exception as e:
        task_logprint(f"Warning: Failed to create flux density plot: {e}")


def fluxboot(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform flux density bootstrapping.

    This function bootstraps flux densities from a flux calibrator to secondary
    calibrators using fluxscale, fits power-law models to the bootstrapped values,
    and sets the model column with the fitted flux densities and spectral indices.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing:
        - msname : str
            Name of the measurement set
        - calibrators_ms : str, optional
            Name of calibrators-only MS (default: "calibrators.ms")
        - flux_field_select_string : str
            Field selection string for flux calibrator
        - center_frequencies : dict
            Mapping of spw (int) to center frequency (float) in Hz
        - usescratch : bool, optional
            Whether to use scratch columns (default: False)
        - calibrator_scan_select_string : str, optional
            Scan selection for plotting
        - corrstring : str, optional
            Correlation string for plotting (default: "RR,LL")

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_fluxboot : str
            QA2 status ("Pass" or "Fail")
        - time_list : list
            Updated timing information

    Notes
    -----
    This replaces EVLA_pipe_fluxboot.py with a cleaner, modular approach.
    Sets QA2_fluxboot to "Fail" if:
    - Any spectral index has |spix| > 5.0
    - Flux scaling operations fail
    """
    task_logprint("*** Starting flux density bootstrapping ***")
    time_list = runtiming("fluxboot", "start")
    QA2_fluxboot = "Pass"

    try:
        # Extract required parameters from context
        flux_field_select_string = pipeline_context.get("flux_field_select_string", "")
        center_frequencies = pipeline_context.get("center_frequencies", {})
        scratch = pipeline_context.get("usescratch", False)

        # Validate required inputs
        if not flux_field_select_string:
            task_logprint("ERROR: No flux calibrator field specified")
            QA2_fluxboot = "Fail"
            pipeline_context["QA2_fluxboot"] = QA2_fluxboot
            pipeline_context["error_message"] = "No flux calibrator field specified"
            return pipeline_context

        if not center_frequencies:
            task_logprint("WARNING: No center frequencies provided")

        # Step 1: Bootstrap flux densities
        task_logprint("Step 1: Running fluxscale")
        fluxscale_result = _bootstrap_flux(pipeline_context, flux_field_select_string)

        # Step 2: Fit power laws
        task_logprint("Step 2: Fitting power-law models")
        fitting_results = _fit_power_law(fluxscale_result, center_frequencies)

        # Step 3: Set fitted flux in model column
        task_logprint("Step 3: Setting model column with fitted flux densities")
        QA2_fluxboot = _set_fitted_flux(pipeline_context, fitting_results, scratch)

        # Step 4: Plot results
        task_logprint("Step 4: Creating flux density plots")
        _plot_flux_model(pipeline_context)

        task_logprint(f"QA2 score: {format_qa_status(QA2_fluxboot)}")

    except Exception as e:
        task_logprint(f"ERROR: Flux bootstrapping failed: {e}")
        QA2_fluxboot = "Fail"
        pipeline_context["error_message"] = str(e)

    finally:
        task_logprint("*** Finished flux density bootstrapping ***")
        time_list = runtiming("fluxboot", "end")

        # Update context and return
        pipeline_context["QA2_fluxboot"] = QA2_fluxboot
        pipeline_context["time_list"] = time_list

    return pipeline_context


# Maintain backward compatibility
EVLA_pipe_fluxboot = fluxboot



@register_step("EVLA_pipe_fluxboot")
def EVLA_pipe_fluxboot(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for fluxboot() to match expected step name.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary

    Returns
    -------
    dict
        Updated pipeline context
    """
    return fluxboot(pipeline_context)
