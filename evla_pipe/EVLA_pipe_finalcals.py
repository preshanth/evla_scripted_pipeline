"""
Make final gain calibration tables.

This module performs the final calibration steps including:
- Delay calibration
- Bandpass calibration
- Gain calibration (phase and amplitude)
- Flux density bootstrapping
- Power-law fitting of flux densities
"""

from typing import Dict, Any, List, Tuple, Optional
import os
import numpy as np
import scipy as sp
from casatasks import rmtables, gaincal, bandpass, setjy, fluxscale, casalog
from casatools import table

from evla_pipe.utils import (
    logprint,
    runtiming,
    getCalFlaggedSoln,
    find_EVLA_band,
    MAINLOG,
)

tb = table()


def task_logprint(msg: str) -> None:
    """
    Centralized logging for final calibration operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/finalcals.log")


def _fitfunc(p: List[float], x: np.ndarray) -> np.ndarray:
    """
    Linear function for power-law fitting.

    Parameters
    ----------
    p : list of float
        Parameters [intercept, slope]
    x : ndarray
        Input values

    Returns
    -------
    ndarray
        Fitted values
    """
    return p[0] + p[1] * x


def _errfunc(p: List[float], x: np.ndarray, y: np.ndarray, err: np.ndarray) -> np.ndarray:
    """
    Error function for least squares fitting.

    Parameters
    ----------
    p : list of float
        Parameters [intercept, slope]
    x : ndarray
        Input values
    y : ndarray
        Observed values
    err : ndarray
        Errors

    Returns
    -------
    ndarray
        Residuals weighted by errors
    """
    return (y - _fitfunc(p, x)) / err


def bootstrap_flux(
    pipeline_context: Dict[str, Any],
    fluxgaincal_table: str,
    flux_field_select_string: str,
) -> Tuple[Dict[str, Any], str]:
    """
    Perform flux density bootstrapping using fluxscale.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and calibrators_ms
    fluxgaincal_table : str
        Name of the gain calibration table
    flux_field_select_string : str
        Field selection string for flux calibrator

    Returns
    -------
    dict
        Fluxscale result dictionary
    str
        Path to flux densities output file
    """
    task_logprint("Doing flux density bootstrapping")

    msname = pipeline_context.get("msname", "")
    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")

    fluxscale_output = msname.rstrip("ms") + "fluxdensities"
    task_logprint(f"Flux densities will be written to '{fluxscale_output}'")

    os.system(f"rm -rf {fluxscale_output}")
    casalog.setlogfile(fluxscale_output)

    rmtables("fluxgaincalFcal.g")

    try:
        fluxscale_result = fluxscale(
            vis=calibrators_ms,
            caltable=fluxgaincal_table,
            fluxtable="fluxgaincalFcal.g",
            reference=[flux_field_select_string],
            transfer=[""],
            listfile="",
            append=False,
            refspwmap=[-1],
            incremental=False,
            fitorder=1,
        )
    finally:
        casalog.setlogfile(MAINLOG)

    return fluxscale_result, fluxscale_output


def fit_flux_power_law(
    fluxscale_result: Dict[str, Any],
    center_frequencies: Dict[int, float],
) -> List[List[Any]]:
    """
    Fit a power law to the bootstrapped flux densities.

    Parameters
    ----------
    fluxscale_result : dict
        Result dictionary from fluxscale
    center_frequencies : dict
        Mapping of SPW ID to center frequency in Hz

    Returns
    -------
    list of list
        Fitting results for each source/band combination.
        Each entry contains: [source, spws, fluxdensity, spix, SNR, reffreq]

    Notes
    -----
    Fits log(flux) vs log(frequency) as a linear model to derive
    spectral index and reference flux density.
    """
    task_logprint("Fitting data with power law")

    results = []
    sources = []
    flux_densities = []
    spws = []

    # Extract flux densities from fluxscale result
    for field_id, field_data in fluxscale_result.items():
        try:
            int(field_id)
        except ValueError:
            continue

        sourcename = field_data.get("fieldName")
        if not sourcename:
            continue

        for spw_id, spw_data in field_data.items():
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

    # Fit power law for each unique source/band combination
    for source in np.unique(sources):
        indices = np.argwhere(np.array(sources) == source).squeeze(axis=1)

        # Group by band
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

                    ratio = (
                        flux_densities[ii][1] / flux_densities[ii][0]
                        if flux_densities[ii][0] != 0
                        else 0.0
                    )
                    lerrs.append(np.log10(np.e) * ratio if ratio != 0 else 0.0)
                    uspws.append(spws[ii])

            # Perform fit
            if len(lfds) <= 2:
                aa = lfds[0] if lfds else 0.0
                bb = 0.0
                SNR = 0.0
            else:
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

                    summed_error = np.sum((_fitfunc([aa, bb], alfreqs) - alfds) ** 2)
                    residual_variance = (
                        summed_error / (len(alfds) - 2) if len(alfds) > 2 else 0.0
                    )
                    SNR = (
                        np.abs(bb) / np.sqrt(covar[1][1] * residual_variance)
                        if covar is not None and residual_variance > 0
                        else 0.0
                    )
                except Exception as e:
                    task_logprint(
                        f"Error during power law fitting for {source} in {band}: {e}"
                    )
                    aa = 0.0
                    bb = 0.0
                    SNR = 0.0

            # Calculate reference frequency and flux density
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
                task_logprint(f"    {flux_exp:.3f} {10**lfds[ii]:.3f} {fderr:.3f} {SS:.3f}")

    return results


def set_fitted_flux(
    pipeline_context: Dict[str, Any],
    fitting_results: List[List[Any]],
    scratch: bool,
) -> str:
    """
    Set the power-law fit in the model column using setjy.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and calibrators_ms
    fitting_results : list of list
        Results from fit_flux_power_law
    scratch : bool
        Whether to use scratch columns

    Returns
    -------
    str
        QA2 score: "Pass" or "Fail"

    Notes
    -----
    Sets QA2_fluxboot to "Fail" if any spectral index has |spix| > 5.0
    """
    task_logprint("Setting power-law fit in the model column")

    QA2_fluxboot = "Pass"
    ms_active = pipeline_context.get("msname", "")
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

                    if abs(spix) > 5.0:
                        QA2_fluxboot = "Fail"
                        task_logprint(
                            f"WARNING: Spectral index {spix} exceeds threshold for {source}"
                        )

                except Exception as e:
                    task_logprint(
                        f"Unable to complete flux scaling for field {source}, spw {spw_i}: {e}"
                    )

    return QA2_fluxboot


def perform_delay_calibration(
    pipeline_context: Dict[str, Any],
    priorcals: List[str],
    delay_field_select_string: str,
    tst_delay_spw: str,
    delay_scan_select_string: str,
) -> None:
    """
    Perform delay calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and refant
    priorcals : list of str
        List of prior calibration tables to apply
    delay_field_select_string : str
        Field selection for delay calibrator
    tst_delay_spw : str
        SPW selection for delay calibration
    delay_scan_select_string : str
        Scan selection for delay calibration
    """
    task_logprint("Performing delay calibration")

    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")
    refant = pipeline_context.get("refant", "")

    rmtables("finaldelay.k")

    gaincal(
        vis=calibrators_ms,
        caltable="finaldelay.k",
        field=delay_field_select_string,
        spw=tst_delay_spw,
        scan=delay_scan_select_string,
        solint="inf",
        combine="scan",
        refant=refant,
        minblperant=4,
        minsnr=3.0,
        gaintype="K",
        gaintable=priorcals,
        parang=False,
    )

    task_logprint("Delay calibration completed")


def perform_bandpass_calibration(
    pipeline_context: Dict[str, Any],
    priorcals: List[str],
    bandpass_field_select_string: str,
    tst_bpass_spw: str,
    bandpass_scan_select_string: str,
) -> None:
    """
    Perform bandpass calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and refant
    priorcals : list of str
        List of prior calibration tables to apply (includes delay)
    bandpass_field_select_string : str
        Field selection for bandpass calibrator
    tst_bpass_spw : str
        SPW selection for bandpass calibration
    bandpass_scan_select_string : str
        Scan selection for bandpass calibration
    """
    task_logprint("Performing bandpass calibration")

    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")
    refant = pipeline_context.get("refant", "")

    rmtables("finalBPcal.b")

    bandpass(
        vis=calibrators_ms,
        caltable="finalBPcal.b",
        field=bandpass_field_select_string,
        spw=tst_bpass_spw,
        scan=bandpass_scan_select_string,
        solint="inf",
        combine="scan",
        refant=refant,
        minblperant=4,
        minsnr=3.0,
        bandtype="B",
        fillgaps=8,
        gaintable=priorcals,
        parang=False,
    )

    task_logprint("Bandpass calibration completed")


def perform_phase_calibration(
    pipeline_context: Dict[str, Any],
    priorcals: List[str],
    calibrator_field_select_string: str,
    gain_solint1: str,
    calibrator_scan_select_string: str,
) -> None:
    """
    Perform phase-only gain calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and refant
    priorcals : list of str
        List of prior calibration tables to apply
    calibrator_field_select_string : str
        Field selection for calibrators
    gain_solint1 : str
        Solution interval for phase calibration
    calibrator_scan_select_string : str
        Scan selection for calibrators
    """
    task_logprint("Performing phase-only gain calibration")

    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")
    refant = pipeline_context.get("refant", "")

    rmtables("finalphasegaincal.g")

    gaincal(
        vis=calibrators_ms,
        caltable="finalphasegaincal.g",
        field=calibrator_field_select_string,
        solint=gain_solint1,
        scan=calibrator_scan_select_string,
        combine="",
        refant=refant,
        minblperant=4,
        minsnr=3.0,
        gaintype="G",
        calmode="p",
        gaintable=priorcals,
        parang=False,
    )

    task_logprint("Phase calibration completed")


def perform_amplitude_calibration(
    pipeline_context: Dict[str, Any],
    priorcals: List[str],
    calibrator_field_select_string: str,
    gain_solint2: str,
    calibrator_scan_select_string: str,
) -> None:
    """
    Perform amplitude and phase gain calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and refant
    priorcals : list of str
        List of prior calibration tables to apply
    calibrator_field_select_string : str
        Field selection for calibrators
    gain_solint2 : str
        Solution interval for amplitude calibration
    calibrator_scan_select_string : str
        Scan selection for calibrators
    """
    task_logprint("Performing amplitude and phase gain calibration")

    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")
    refant = pipeline_context.get("refant", "")

    rmtables("finalampgaincal.g")

    gaincal(
        vis=calibrators_ms,
        caltable="finalampgaincal.g",
        field=calibrator_field_select_string,
        solint=gain_solint2,
        scan=calibrator_scan_select_string,
        combine="",
        refant=refant,
        minblperant=4,
        minsnr=3.0,
        gaintype="G",
        calmode="ap",
        gaintable=priorcals,
        parang=False,
    )

    task_logprint("Amplitude calibration completed")


def calculate_qa2_score(
    num_antennas: int,
    critfrac: float,
) -> str:
    """
    Calculate QA2 score based on flagged solution statistics.

    Parameters
    ----------
    num_antennas : int
        Total number of antennas
    critfrac : float
        Critical fraction threshold for QA2 failure

    Returns
    -------
    str
        QA2 score: "Pass" or "Fail"
    """
    task_logprint("Calculating QA2 score from flagged solutions")

    QA2_finalcals = "Pass"

    try:
        flagged_delay = getCalFlaggedSoln("finaldelay.k")
        flagged_bp = getCalFlaggedSoln("finalBPcal.b")
        flagged_amp = getCalFlaggedSoln("finalampgaincal.g")
        flagged_phase = getCalFlaggedSoln("finalphasegaincal.g")

        # Check each calibration table
        for name, stats in [
            ("delay", flagged_delay),
            ("bandpass", flagged_bp),
            ("amplitude", flagged_amp),
            ("phase", flagged_phase),
        ]:
            if stats:
                frac = float(stats.get("all", {}).get("frac", 0.0))
                task_logprint(f"Fraction of flagged {name} solutions: {frac:.3f}")

                if frac > critfrac:
                    QA2_finalcals = "Fail"
                    task_logprint(
                        f"WARNING: {name} flagged fraction {frac:.3f} exceeds threshold {critfrac:.3f}"
                    )

    except Exception as e:
        task_logprint(f"Error calculating QA2 score: {e}")
        QA2_finalcals = "Fail"

    return QA2_finalcals


def finalcals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform final gain calibrations and flux bootstrapping.

    This function performs the complete final calibration workflow:
    1. Delay calibration
    2. Bandpass calibration
    3. Phase-only gain calibration
    4. Amplitude+phase gain calibration
    5. Flux density bootstrapping
    6. Power-law fitting of flux densities
    7. Setting fitted flux models

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Name of measurement set
        - calibrators_ms : str
            Name of calibrators-only MS
        - refant : str
            Reference antenna
        - priorcals : list of str
            Prior calibration tables
        - delay_field_select_string : str
            Field selection for delay calibration
        - tst_delay_spw : str
            SPW selection for delay
        - delay_scan_select_string : str
            Scan selection for delay
        - bandpass_field_select_string : str
            Field selection for bandpass
        - tst_bpass_spw : str
            SPW selection for bandpass
        - bandpass_scan_select_string : str
            Scan selection for bandpass
        - calibrator_field_select_string : str
            Field selection for gain calibrators
        - calibrator_scan_select_string : str
            Scan selection for calibrators
        - gain_solint1 : str
            Solution interval for phase calibration
        - gain_solint2 : str
            Solution interval for amplitude calibration
        - flux_field_select_string : str
            Field selection for flux calibrator
        - center_frequencies : dict
            SPW to center frequency mapping
        - scratch : bool
            Whether to use scratch columns
        - numAntenna : int
            Total number of antennas
        - critfrac : float
            Critical fraction for QA2

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_finalcals : str
            Overall QA2 score
        - QA2_fluxboot : str
            Flux bootstrapping QA2 score
        - fluxscale_result : dict
            Fluxscale result dictionary
        - fluxscale_output : str
            Path to flux densities file
        - flux_fitting_results : list
            Power-law fitting results
        - time_list : list
            Timing information

    Notes
    -----
    Sets QA2_finalcals based on fraction of flagged solutions.
    All calibration tables are saved with 'final' prefix.
    """
    task_logprint("*** Starting Final Calibrations ***")
    time_list = runtiming("finalcals", "start")

    QA2_finalcals = "Pass"
    QA2_fluxboot = "Pass"

    try:
        # Extract parameters from context
        priorcals = pipeline_context.get("priorcals", [])
        delay_field = pipeline_context.get("delay_field_select_string", "")
        tst_delay_spw = pipeline_context.get("tst_delay_spw", "")
        delay_scan = pipeline_context.get("delay_scan_select_string", "")

        bandpass_field = pipeline_context.get("bandpass_field_select_string", "")
        tst_bpass_spw = pipeline_context.get("tst_bpass_spw", "")
        bandpass_scan = pipeline_context.get("bandpass_scan_select_string", "")

        calibrator_field = pipeline_context.get("calibrator_field_select_string", "")
        calibrator_scan = pipeline_context.get("calibrator_scan_select_string", "")
        gain_solint1 = pipeline_context.get("gain_solint1", "int")
        gain_solint2 = pipeline_context.get("gain_solint2", "inf")

        flux_field = pipeline_context.get("flux_field_select_string", "")
        center_frequencies = pipeline_context.get("center_frequencies", {})
        scratch = pipeline_context.get("scratch", False)
        num_antennas = pipeline_context.get("numAntenna", 27)
        critfrac = pipeline_context.get("critfrac", 0.1)

        # Step 1: Delay calibration
        perform_delay_calibration(
            pipeline_context,
            priorcals,
            delay_field,
            tst_delay_spw,
            delay_scan,
        )

        # Update priorcals for subsequent steps
        priorcals_with_delay = priorcals + ["finaldelay.k"]

        # Step 2: Bandpass calibration
        perform_bandpass_calibration(
            pipeline_context,
            priorcals_with_delay,
            bandpass_field,
            tst_bpass_spw,
            bandpass_scan,
        )

        # Update priorcals for gain calibrations
        priorcals_with_bp = priorcals_with_delay + ["finalBPcal.b"]

        # Step 3: Phase-only gain calibration
        perform_phase_calibration(
            pipeline_context,
            priorcals_with_bp,
            calibrator_field,
            gain_solint1,
            calibrator_scan,
        )

        # Update priorcals for amplitude calibration
        priorcals_with_phase = priorcals_with_bp + ["finalphasegaincal.g"]

        # Step 4: Amplitude and phase gain calibration
        perform_amplitude_calibration(
            pipeline_context,
            priorcals_with_phase,
            calibrator_field,
            gain_solint2,
            calibrator_scan,
        )

        # Step 5: Flux density bootstrapping
        task_logprint("Starting flux density bootstrapping")
        fluxscale_result, fluxscale_output = bootstrap_flux(
            pipeline_context,
            "finalampgaincal.g",
            flux_field,
        )

        # Step 6: Fit power laws to flux densities
        fitting_results = fit_flux_power_law(
            fluxscale_result,
            center_frequencies,
        )

        # Step 7: Set fitted flux models
        QA2_fluxboot = set_fitted_flux(
            pipeline_context,
            fitting_results,
            scratch,
        )

        # Step 8: Calculate QA2 score
        QA2_finalcals = calculate_qa2_score(num_antennas, critfrac)

        # If flux bootstrapping failed, overall QA2 fails
        if QA2_fluxboot == "Fail":
            QA2_finalcals = "Fail"

        task_logprint("Final calibrations completed successfully")

        # Update context with results
        pipeline_context["QA2_finalcals"] = QA2_finalcals
        pipeline_context["QA2_fluxboot"] = QA2_fluxboot
        pipeline_context["fluxscale_result"] = fluxscale_result
        pipeline_context["fluxscale_output"] = fluxscale_output
        pipeline_context["flux_fitting_results"] = [
            {
                "source": r[0],
                "spws": r[1],
                "fluxdensity": float(r[2]),
                "spix": float(r[3]),
                "SNR": float(r[4]),
                "reffreq": float(r[5]),
            }
            for r in fitting_results
        ]

    except Exception as e:
        task_logprint(f"Error in final calibrations: {e}")
        pipeline_context["QA2_finalcals"] = "Fail"
        pipeline_context["error_message"] = str(e)

    # Import colored output function
    from evla_pipe.utils import format_qa_status

    task_logprint("*** Finished Final Calibrations ***")
    task_logprint(f"QA2 score: {format_qa_status(pipeline_context.get('QA2_finalcals', 'Fail'))}")

    time_list = runtiming("finalcals", "end")
    pipeline_context["time_list"] = time_list

    return pipeline_context


def EVLA_pipe_finalcals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for finalcals pipeline step.

    This is a wrapper function that calls the main finalcals function.
    Maintained for backward compatibility with existing pipeline code.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """
    return finalcals(pipeline_context)
