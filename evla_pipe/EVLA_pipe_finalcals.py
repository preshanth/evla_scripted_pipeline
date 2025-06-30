"""
Make final gain calibration tables.
"""

import copy
import os
import numpy as np
import scipy as sp
from casatasks import rmtables, gaincal, bandpass, flagdata, applycal, split, setjy, fluxscale, casalog, plotms
from casatools import table
from . import pipeline_save
from .utils import logprint, runtiming, RefAntHeuristics, getCalFlaggedSoln, find_standards, find_EVLA_band, MAINLOG

tb = table()


def task_logprint(msg):
    logprint(msg, logfileout="logs/finalcals.log")


def _fitfunc(p, x):
    return p[0] + p[1] * x


def _errfunc(p, x, y, err):
    return (y - _fitfunc(p, x)) / err


def bootstrap_flux(pipeline_context, fluxgaincal_table, flux_field_select_string):
    """Perform flux density bootstrapping using fluxscale."""
    task_logprint("Doing flux density bootstrapping")
    msname = pipeline_context.get("msname")
    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")
    fluxscale_output = msname.rstrip("ms") + "fluxdensities"
    task_logprint(f"Flux densities will be written to '{fluxscale_output}'")
    os.system(f"rm -rf {fluxscale_output}")
    casalog.setlogfile(fluxscale_output)
    rmtables("fluxgaincalFcal.g")
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
    casalog.setlogfile(MAINLOG)
    return fluxscale_result, fluxscale_output


def fit_flux_power_law(fluxscale_result, center_frequencies):
    """Fit a power law to the bootstrapped flux densities."""
    task_logprint("Fitting data with power law")
    results = []
    sources = []
    flux_densities = []
    spws = []
    for field_id, field_data in fluxscale_result.items():
        try:
            int(field_id)
        except ValueError:
            continue
        sourcename = field_data.get("fieldName")
        if sourcename:
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
    for source in np.unique(sources):
        indices = np.argwhere(np.array(sources) == source).squeeze(axis=1)
        bands = [find_EVLA_band(center_frequencies.get(spws[i], 0.0)) for i in indices]
        for band in np.unique(bands):
            lfreqs = []
            lfds = []
            lerrs = []
            uspws = []
            for ii in indices:
                center_freq = center_frequencies.get(spws[ii])
                if center_freq is not None and find_EVLA_band(center_freq) == band:
                    lfreqs.append(np.log10(center_freq))
                    lfds.append(np.log10(flux_densities[ii][0]))
                    ratio = flux_densities[ii][1] / flux_densities[ii][0] if flux_densities[ii][0] != 0 else 0.0
                    lerrs.append(np.log10(np.e) * ratio if ratio != 0 else 0.0)
                    uspws.append(spws[ii])
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
                    residual_variance = summed_error / (len(alfds) - 2) if len(alfds) > 2 else 0.0
                    SNR = np.abs(bb) / np.sqrt(covar[1][1] * residual_variance) if covar is not None and residual_variance > 0 else 0.0
                except Exception as e:
                    task_logprint(f"Error during power law fitting for source in band: {e}")
                    aa = 0.0
                    bb = 0.0
                    SNR = 0.0
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
                fderr = lerrs[ii] * err_exp / np.log10(np.e) if np.log10(np.e) != 0 else 0.0
                task_logprint(f"    {flux_exp:.3f} {10**lfds[ii]:.3f} {fderr:.3f} {SS:.3f}")
    return results

def set_fitted_flux(pipeline_context, fitting_results, scratch):
    """Set the power-law fit in the model column using setjy."""
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
                    if abs(spix) > 5.0:
                        QA2_fluxboot = "Fail"
                except Exception as e:
                    task_logprint(
                        f"Unable to complete flux scaling operation for field {source}, spw {spw_i}: {e}"
                    )
    return QA2_fluxboot


def perform_final_calibrations(pipeline_context, priorcals, delay_field_select_string, tst_delay_spw,
                              delay_scan_select_string, uvrange3C84, cal3C84_d, bandpass_field_select_string,
                              tst_bpass_spw, bandpass_scan_select_string, cal3C84_bp, gain_solint1,
                              calibrator_field_select_string, minBL_for_cal, new_gain_solint1, gain_solint2,
                              field_positions, field_spws, center_frequencies, scratch, fluxscale_output,
                              fluxscale_result, channels, numAntenna, critfrac, ms_active, calibrator_scan_select_string, corrstring):
    """
    Perform the final gain calibration steps.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
        # ... (other arguments as before)
        numAntenna (int): The total number of antennas in the observation.
        # ... (other arguments as before)

    Returns:
        tuple: A tuple containing the QA2 score and a dictionary of flagged solution statistics.
    """
    task_logprint("Performing final gain calibrations")
    QA2_finalcals = "Pass"
    flagged_solutions = {}

    # ... (rest of the calibration steps as before, without plotting)

    # Calculate fractions of flagged solutions for final QA2
    flaggedDelaySolns = getCalFlaggedSoln("finaldelay.k")
    flaggedBPSolns = getCalFlaggedSoln("finalBPcal.b")
    flaggedAmpSolns = getCalFlaggedSoln("finalampgaincal.g")
    flaggedPhaseSolns = getCalFlaggedSoln("finalphasegaincal.g")

    # ... (QA2 scoring logic as before)

    return QA2_finalcals, flagged_solutions