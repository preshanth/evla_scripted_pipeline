"""
Perform flux density bootstrapping.
"""

import os

import numpy as np
import scipy as sp

from casatasks import fluxscale, casalog
from casaplotms import plotms

from . import pipeline_save
from .utils import MAINLOG, logprint, runtiming, find_EVLA_band


def task_logprint(msg):
    logprint(msg, logfileout="logs/fluxboot.log")


def fitfunc(p, x):
    return p[0] + p[1] * x


def errfunc(p, x, y, err):
    return (y - fitfunc(p, x)) / err


task_logprint("Starting EVLA_pipe_fluxboot.py")
time_list = runtiming("fluxboot", "start")
QA2_fluxboot = "Pass"

fluxscale_output = msname.rstrip("ms") + "fluxdensities"
fluxcalfields = flux_field_select_string

task_logprint("Doing flux density bootstrapping")
task_logprint(f"Flux densities will be written to '{fluxscale_output}'")

os.system(f"rm -rf {fluxscale_output}")
casalog.setlogfile(fluxscale_output)


rmtables("fluxgaincalFcal.g")
fluxscale_result = fluxscale(
    vis="calibrators.ms",
    caltable="fluxgaincal.g",
    fluxtable="fluxgaincalFcal.g",
    reference=[fluxcalfields],
    transfer=[""],
    listfile="",
    append=False,
    refspwmap=[-1],
    incremental=False,
    fitorder=1,
)

casalog.setlogfile(MAINLOG)
task_logprint("Fitting data with power law")

if not os.path.exists(fluxscale_output):
    task_logprint(f"Error: fluxscale output '{fluxscale_output}' does not exist.")

# Find the field_ids in the dictionary returned from the CASA task fluxscale
sources = []
flux_densities = []
spws = []
for field_id in fluxscale_result.keys():
    try:
        int(field_id)
    except ValueError:
        continue  # not a field ID, "freq", "spwName", etc.
    sourcename = fluxscale_result[field_id]["fieldName"]
    secondary_keys = list(fluxscale_result[field_id].keys())
    for spw_id in secondary_keys:
        try:
            int(spw_id)
        except ValueError:
            continue  # not a SpW ID, "fitRefFreq", "spidx", etc.
        flux_items = fluxscale_result[field_id][spw_id]
        flux_d = list(flux_items["fluxd"])
        flux_d_err = list(flux_items["fluxdErr"])
        for f_d, f_e in zip(flux_d, flux_d_err):
            if f_d != -1 and f_d != 0:
                sources.append(sourcename)
                flux_densities.append([float(f_d), float(f_e)])
                spws.append(int(spw_id))

# NOTE The variable `center_frequencies` used below should already
# have been filled out with the reference frequencies of the spectral
# window table.
results = []
for source in np.unique(sources):
    indices = np.argwhere(np.array(sources) == source).squeeze(axis=1)
    bands = [find_EVLA_band(center_frequencies[spws[i]]) for i in indices]
    for band in np.unique(bands):
        lfreqs = []
        lfds = []
        lerrs = []
        uspws = []
        for ii in indices:
            center_freq = center_frequencies[spws[ii]]
            if find_EVLA_band(center_freq) == band:
                lfreqs.append(np.log10(center_freq))
                lfds.append(np.log10(flux_densities[ii][0]))
                ratio = flux_densities[ii][1] / flux_densities[ii][0]
                lerrs.append(np.log10(np.e) * ratio)
                uspws.append(spws[ii])

        # FIXME I am ignoring this original comment for now, but this could
        #       likely be implemented now with newer versions of np/sp,
        #       using e.g., `scipy.curve_fit`.
        #
        # If we didn't care about the errors on the data or the fit
        # coefficients, just:
        #
        #       coefficients = np.polyfit(lfreqs, lfds, 1)
        #
        # or, if we ever get to numpy 1.7.x, for weighted fit, and returning
        # covariance matrix, do:
        #
        #       weights = []
        #       weight_sum = 0.0
        #       for ii in range(len(lfreqs)):
        #           weights.append(1.0 / (lerrs[ii]*lerrs[ii]))
        #           weight_sum += weights[ii]
        #       for ii in range(len(weights)):
        #           weights[ii] /= weight_sum
        #       coefficients = np.polyfit(lfreqs, lfds, 1, w=weights, cov=True)
        #
        # but, for now, use the full scipy.optimize.leastsq route...
        #
        # actually, after a lot of testing, np.polyfit does not return a global
        # minimum solution.  sticking with leastsq (modified as below to get the
        # proper errors), or once we get a modern enough version of scipy, moving
        # to curve_fit, is better.

        if len(lfds) <= 2:
            aa = lfds[0]
            bb = 0.0
            SNR = 0.0
        else:
            alfds = np.array(lfds)
            alerrs = np.array(lerrs)
            alfreqs = np.array(lfreqs)
            pinit = [0.0, 0.0]
            fit_out = sp.optimize.leastsq(
                errfunc,
                pinit,
                args=(alfreqs, alfds, alerrs),
                full_output=True,
            )
            aa, bb = fit_out[0]
            covar = fit_out[1]

            # The fit is of the form:
            #
            #     log(S) = a + b * log(f)
            #
            # with a = pfinal[0] and b = pfinal[1]. The errors on the
            # coefficients are:
            #
            #     sqrt(covar[i][i]*residual_variance)
            #
            # with the residual covariance calculated as below (it's like
            # the reduced chi squared without dividing out the errors).
            # See the `scipy.optimize.leastsq` documentation and
            #
            #   http://stackoverflow.com/questions/14854339/in-scipy-how-and-why-does-curve-fit-calculate-the-covariance-of-the-parameter-es

            summed_error = 0.0
            for freq, data in zip(alfreqs, alfds):
                model = aa + bb * freq
                summed_error += (model - data) ** 2
            residual_variance = summed_error / (len(alfds) - 2)
            SNR = np.abs(bb) / np.sqrt(covar[1][1] * residual_variance)

        # Take as the reference frequency the lowest one (although this
        # shouldn't matter, in principle).
        reffreq = 10 ** lfreqs[0] / 1e9
        fluxdensity = 10 ** (aa + bb * lfreqs[0])
        spix = bb
        results.append([source, uspws, fluxdensity, spix, SNR, reffreq])
        task_logprint(
            f"{source} {band} fitted spectral index = {spix} and SNR = {SNR}"
        )
        task_logprint("Frequency, data, error, and fitted data:")
        for ii in range(len(lfreqs)):
            flux_exp = 10 ** lfreqs[ii] / 1e9
            err_exp = 10 ** lfds[ii]
            SS = fluxdensity * (flux_exp / reffreq) ** spix
            fderr = lerrs[ii] * err_exp / np.log10(np.e)
            task_logprint(f"    {flux_exp} {err_exp} {fderr} {SS}")

task_logprint("Setting power-law fit in the model column")
for result in results:
    for spw_i in result[1]:
        task_logprint(f"Running setjy on spw {spw_i}")
        for vis in ("calibrators.ms", ms_active):
            try:
                setjy(
                    vis=vis,
                    field=str(result[0]),
                    spw=str(spw_i),
                    selectdata=False,
                    scalebychan=True,
                    standard="manual",
                    fluxdensity=[result[2], 0, 0, 0],
                    spix=result[3],
                    reffreq=str(result[5]) + "GHz",
                    usescratch=scratch,
                )
                if abs(spix) > 5.0:
                    QA2_fluxboot = "Fail"
            except:
                task_logprint(
                    "Unable to complete flux scaling operation for field "
                    f"{field}, spw {spw}"
                )
task_logprint("Flux density bootstrapping finished.")


task_logprint("Plotting model calibrator flux densities.")
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

task_logprint(f"QA2 score: {QA2_fluxboot}")
task_logprint("Finished EVLA_pipe_fluxboot.py")
time_list = runtiming("fluxboot", "end")

pipeline_save()
