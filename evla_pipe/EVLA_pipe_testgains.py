"""
Do test gain calibrations to see if more flagging is needed and to
establish short and long solution intervals.

Notes
-----
Needs some work to automate; note also that `plotcal` holds onto
testgaincal.g in the table cache unless it has been exited using
the gui, so only plot the final versions.
"""

from casatasks import rmtables
from casatools import table
from casaplotms import plotms

from . import pipeline_save
from .utils import (logprint, runtiming, RefAntHeuristics, testgains, getCalFlaggedSoln)

tb = table()


def task_logprint(msg):
    logprint(msg, logfileout="logs/testgains.log")


task_logprint("*** Starting EVLA_pipe_testgains.py ***")
time_list = runtiming("testgains", "start")
QA2_testgains = "Pass"

print("\nFinding a reference antenna for gain calibrations\n")

refantspw = ""
refantfield = calibrator_field_select_string

# NB: would use ms_active below instead of calibrators.ms when selection
# to exclude flagged data is implemented
findrefant = RefAntHeuristics(
    vis="calibrators.ms", field=refantfield, geometry=True, flagging=True
)
RefAntOutput = findrefant.calculate()
refAnt = ",".join(str(RefAntOutput[i]) for i in range(4))

task_logprint(
    f"The pipeline will use antenna(s) {refAnt} as the reference"
)


# First determine short solint for gain calibrator, and see if it is
# shorter or longer than gain_solint1 (determined on BPd cals)
task_logprint("Doing test gain calibration")

# Start with solint='int' -> 1 * int_time
tst_gcal_spw = ""
for time_factor in (1.0, 3.0, 10.0, "inf"):
    if isinstance(time_factor, float):
        soltime = time_factor * int_time
        solint = f"{soltime}s"
        combtime = "scan"
    else:
        soltime = longsolint
        solint = time_factor
        combtime = ""
    rmtables("testgaincal.g")
    flaggedSolnResult1 = testgains(
        "calibrators.ms",
        "testgaincal.g",
        tst_gcal_spw,
        calibrator_scan_select_string,
        solint,
        refAnt,
        minBL_for_cal,
        combtime,
    )
    frac_flagged = flaggedSolnResult1["all"]["fraction"]
    frac_flagged_med = flaggedSolnResult1["antmedian"]["fraction"]
    frac_flagged_tot = flaggedSolnResult1["all"]["total"]
    task_logprint(
        f"For solint = {solint}, fraction of flagged solutions = {frac_flagged}"
    )
    task_logprint(
        f"Median fraction of flagged solutions per antenna = {frac_flagged_med}"
    )
    if frac_flagged_tot > 0:
        fracFlaggedSolns1 = frac_flagged_med
    else:
        fracFlaggedSolns1 = 1.0
    if fracFlaggedSolns1 < flagging_threshold:
        task_logprint(f"Using short solution interval: {solint}")
        break
else:
    task_logprint(
            "WARNING, large fraction of flagged solutions, "
            "there might be something wrong with your data."
    )
    QA2_testgains = "Fail"

# Determine max (shortsol1, shortsol2)
shortsol2 = soltime
short_solint = max(shortsol1, shortsol2)
new_gain_solint1 = f"{short_solint}s"

task_logprint(f"Using short solint = {new_gain_solint1}")


# Get maximum unflagged amplitude for plot maximum.
try:
    tb.open("testgaincal.g")
    cpar = tb.getcol("CPARAM")
    flgs = tb.getcol("FLAG")
finally:
    tb.close()
amps = np.abs(cpar)
good = np.logical_not(flgs)
maxamp = np.max(amps[good])

# Plot time vs amplitude for gain solutions.
task_logprint("Plotting amplitude gain solutions.")
for ii in range(nplots):
    plotfile = f"testgaincal_amp{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="testgaincal.g",
        xaxis="time",
        yaxis="amp",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, 0, maxamp],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )
task_logprint("Plotting phase gain solutions")
for ii in range(nplots):
    plotfile = f"testgaincal_phase{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="testgaincal.g",
        xaxis="time",
        yaxis="phase",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, -180, 180],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )
task_logprint("Plotting finished.")


# Calculate fractions of flagged solutions for final QA2
flaggedGainSolns = getCalFlaggedSoln("testgaincal.g")

if flaggedGainSolns["all"]["total"] == 0:
    QA2_testgains = "Fail"
elif flaggedGainSolns["antmedian"]["fraction"] > 0.1:
    QA2_testgains = "Partial"

task_logprint(f"QA2 score: {QA2_testgains}")
task_logprint("Finished EVLA_pipe_testgains.py")
time_list = runtiming("testgains", "end")

pipeline_save()
