"""
Test bandpass and delay calibration.
"""

import os
import copy

import numpy as np

from casatasks import gaincal, bandpass, applycal
from casatools import table
from casaplotms import plotms

from . import pipeline_save
from .utils import (
        runtiming,
        logprint,
        RefAntHeuristics,
        testdelays,
        testBPdgains,
        getCalFlaggedSoln,
)

tb = table()


def task_logprint(msg):
    logprint(msg, logfileout="logs/testBPdcals.log")


task_logprint("*** Starting EVLA_pipe_testBPdcals.py ***")
time_list = runtiming("testBPdcals", "start")
QA2_testBPdcals = "Pass"


# INITIAL TEST CALIBRATIONS USING BANDPASS AND DELAY CALIBRATORS
task_logprint("Finding a reference antenna")

refantfield = calibrator_field_select_string
findrefant = RefAntHeuristics(
    vis=ms_active,
    field=refantfield,
    geometry=True,
    flagging=True,
)
RefAntOutput = findrefant.calculate()
refAnt = str(RefAntOutput[0])

task_logprint(f"The pipeline will use antenna {refAnt} as the reference")
task_logprint("Doing test calibrations")

# Do initial phase solutions on the delay calibrator
os.system("rm -rf testdelayinitialgain.g")
uvrange = uvrange3C84 if cal3C84_d else ""
gaincal(
    vis=ms_active,
    caltable="testdelayinitialgain.g",
    field=delay_field_select_string,
    spw=tst_delay_spw,
    intent="",
    selectdata=True,
    uvrange=uvrange,
    scan=delay_scan_select_string,
    solint="int",
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=3.0,
    solnorm=False,
    gaintype="G",
    smodel=[],
    calmode="p",
    append=False,
    docallib=False,
    gaintable=priorcals,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)
task_logprint("Initial phase calibration on delay calibrator complete")

# Do initial test delay calibration ("test" because more flagging may be
# needed for the final version). In case the reference antenan has a bad
# baseband/IF, check the first five antennas and continue if there is a
# high fraction of flagged solutions.
# NOTE For the future investigate multiband delay.
os.system("rm -rf testdelay.k")
for ii in range(5):
    refAnt = str(RefAntOutput[ii])
    task_logprint(f"Testing referance antenna: {refAnt}")
    flaggedSolnResult = testdelays(
        ms_active,
        "testdelay.k",
        delay_field_select_string,
        delay_scan_select_string,
        refAnt,
        minBL_for_cal,
        priorcals,
        cal3C84_d,
        uvrange3C84,
    )
    task_logprint(
        "Fraction of flagged solutions = " + str(flaggedSolnResult["all"]["fraction"])
    )
    task_logprint(
        "Median fraction of flagged solutions per antenna = "
        + str(flaggedSolnResult["antmedian"]["fraction"])
    )
    if flaggedSolnResult["all"]["total"] > 0:
        fracFlaggedSolns = flaggedSolnResult["antmedian"]["fraction"]
    else:
        fracFlaggedSolns = 1.0
    if fracFlaggedSolns < critfrac:
        task_logprint(f"Using {refAnt} as referance antenna.")
        break
else:
    # loop terminated without hitting `break` on a good antenna
    task_logprint(
        "WARNING, tried several reference antennas, there might be something wrong with your data"
    )
    QA2_testBPdcals = "Fail"

task_logprint("Plotting test delays")
nplots = int(numAntenna / 3)
if (numAntenna % 3) > 0:
    nplots = nplots + 1
for ii in range(nplots):
    plotfile = f"testdelay{ii}.png"
    os.system(f"rm -rf {plotfile}")
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="testdelay.k",
        xaxis="freq",
        yaxis="delay",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )


# Do initial amplitude and phase gain solutions on the BPcalibrator and delay
# calibrator; the amplitudes are used for flagging; only phase
# calibration is applied in final BP calibration, so that solutions are
# not normalized per spw and take out the baseband filter shape

# Try running with solint of int_time, 3*int_time, and 10*int_time.
# If there is still a large fraction of failed solutions with
# solint=10*int_time the source may be too weak, and calibration via the
# pipeline has failed; will need to implement a mode to cope with weak
# calibrators (later)

cal3C84 = cal3C84_d or cal3C84_bp
if delay_scan_select_string == bandpass_scan_select_string:
    testgainscans = bandpass_scan_select_string
else:
    testgainscans = bandpass_scan_select_string + "," + delay_scan_select_string
flagging_threshold = 0.05
for time_factor in (1.0, 3.0, 10.0):
    soltime = time_factor * int_time
    solint = f"{soltime}s"
    os.system("rm -rf testBPdinitialgain.g")
    flaggedSolnResult1 = testBPdgains(
        ms_active,
        "testBPdinitialgain.g",
        tst_bpass_spw,
        testgainscans,
        solint,
        refAnt,
        minBL_for_cal,
        priorcals,
        cal3C84,
        uvrange3C84,
    )
    frac_flagged = flaggedSolnResult1["all"]["fraction"]
    frac_flagged_med = flaggedSolnResult1["antmedian"]["fraction"]
    frac_flagged_tot = flaggedSolnResult1["all"]["total"]
    task_logprint(
        f"For solint = {solint} fraction of flagged solutions = {frac_flagged}"
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
        "WARNING, large fraction of flagged solutions, there might be something wrong with your data."
    )
    QA2_testBPdcals = "Fail"
gain_solint1 = solint
shortsol1 = soltime

task_logprint(
    "Test amp and phase calibration on delay and bandpass calibrators complete"
)


# Plot amplitude gain solutions
for ii in range(nplots):
    plotfile = f"testBPdinitialgainamp{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="testBPdinitialgain.g",
        xaxis="time",
        yaxis="amp",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

# Plot phase gain solutions
task_logprint("Plotting phase gain solutions")
for ii in range(nplots):
    plotfile = f"testBPdinitialgainphase{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="testBPdinitialgain.g",
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


# Now do test BPcal
task_logprint("Doing test bandpass calibration")
os.system("rm -rf testBPcal.b")

BPGainTables = copy.copy(priorcals)
BPGainTables.append("testdelay.k")
BPGainTables.append("testBPdinitialgain.g")

uvrange = uvrange3C84 if cal3C84_bp else ""
bandpass(
    vis=ms_active,
    caltable="testBPcal.b",
    field=bandpass_field_select_string,
    spw="",
    intent="",
    selectdata=True,
    uvrange=uvrange,
    scan=bandpass_scan_select_string,
    solint="inf",
    combine="scan",
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=5.0,
    solnorm=False,
    bandtype="B",
    fillgaps=0,
    smodel=[],
    append=False,
    docallib=False,
    gaintable=BPGainTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)

task_logprint("Test bandpass calibration complete")
flaggedSolnResult = getCalFlaggedSoln("testBPcal.b")
task_logprint(
    "Fraction of flagged solutions = " + str(flaggedSolnResult["all"]["fraction"])
)
task_logprint(
    "Median fraction of flagged solutions per antenna = "
    + str(flaggedSolnResult["antmedian"]["fraction"])
)

# Plot BP solutions and check for missing spws, antennas, etc.
try:
    tb.open("testBPcal.b")
    dataVarCol = tb.getvarcol("CPARAM")
    flagVarCol = tb.getvarcol("FLAG")
finally:
    tb.close()
rowlist = dataVarCol.keys()
nrows = len(rowlist)
maxmaxamp = 0.0
maxmaxphase = 0.0
for rrow in rowlist:
    dataArr = dataVarCol[rrow]
    flagArr = flagVarCol[rrow]
    amps = np.abs(dataArr)
    phases = np.arctan2(np.imag(dataArr), np.real(dataArr))
    good = np.logical_not(flagArr)
    tmparr = amps[good]
    if len(tmparr) > 0:
        maxamp = np.max(amps[good])
        if maxamp > maxmaxamp:
            maxmaxamp = maxamp
    tmparr = np.abs(phases[good])
    if len(tmparr) > 0:
        maxphase = np.max(np.abs(phases[good])) * 180.0 / np.pi
        if maxphase > maxmaxphase:
            maxmaxphase = maxphase

ampplotmax = maxmaxamp
phaseplotmax = maxmaxphase

for ii in range(nplots):
    plotfile = f"testBPcal_amp{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="testBPcal.b",
        xaxis="freq",
        yaxis="amp",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, 0, ampplotmax],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

for ii in range(nplots):
    plotfile = f"testBPcal_phase{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="testBPcal.b",
        xaxis="freq",
        yaxis="phase",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, -phaseplotmax, phaseplotmax],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

task_logprint("Plotting of test bandpass solutions complete")

# FIXME The `blcal` section was commented out in the original. Keep?
#
# Do blcal to take out closure errors from source structure for plotting.
#
# NOTE
# * Would be good to be able to specify smodel=[1,0,0,0] here since
#   otherwise this only works for sources that are not primary calibrators.
# * blcal crashes if a spw is missing from gaintable, can't use this
#   for now.
# * level of blcal corrections are an indicator of pointy-ness of
#   BPcal and delay cal and/or system health

# blcal(
#    vis=ms_active,
#    caltable='testBPblcal.bl',
#    field='',
#    spw='',
#    selectdata=True,
#    scans=testgainscans,
#    solint='30min',
#    combine='scan',
#    freqdep=False,
#    calmode='ap',
#    solnorm=False,
#    gaintable=[priorcals,'testdelay.k','testBPdinitialgain.g','testBPcal.b'],
#    gainfield=[''],
#    interp=[''],
#    spwmap=[],
#    parang=False,
# )

# Apply gain and bandpass solutions and inspect calibrated BP and delay
# calibrator data for RFI or other problems
task_logprint("Applying test calibrations to BP and delay calibrators")
AllCalTables = copy.copy(priorcals)
AllCalTables.append("testdelay.k")
AllCalTables.append("testBPdinitialgain.g")
AllCalTables.append("testBPcal.b")
ntables = len(AllCalTables)

applycal(
    vis=ms_active,
    field="",
    spw="",
    intent="",
    selectdata=True,
    scan=testgainscans,
    docallib=False,
    gaintable=AllCalTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    calwt=[False] * ntables,
    parang=False,
    applymode="calflagstrict",
    flagbackup=False,
)

task_logprint("Plot calibrated bandpass and delay calibrators")
os.system("rm -rf testcalibratedBPcal.png")
plotms(
    vis=ms_active,
    xaxis="freq",
    yaxis="amp",
    ydatacolumn="corrected",
    selectdata=True,
    field=bandpass_field_select_string,
    scan=bandpass_scan_select_string,
    correlation=corrstring,
    averagedata=True,
    avgtime="1e8",
    avgscan=True,
    transform=False,
    extendflag=False,
    iteraxis="",
    coloraxis="antenna2",
    plotrange=[],
    title="",
    xlabel="",
    ylabel="",
    showmajorgrid=False,
    showminorgrid=False,
    plotfile="testcalibratedBPcal.png",
    showgui=False,
    highres=True,
    overwrite=True,
)

# Plot calibrated delay calibrator, if different from BP cal

if delay_scan_select_string != bandpass_scan_select_string:
    os.system("rm -rf testcalibrated_delaycal.png")
    plotms(
        vis=ms_active,
        xaxis="freq",
        yaxis="amp",
        ydatacolumn="corrected",
        selectdata=True,
        scan=delay_scan_select_string,
        correlation=corrstring,
        averagedata=True,
        avgtime="1e8",
        avgscan=True,
        transform=False,
        extendflag=False,
        iteraxis="",
        coloraxis="antenna2",
        plotrange=[],
        title="",
        xlabel="",
        ylabel="",
        showmajorgrid=False,
        showminorgrid=False,
        plotfile="testcalibrated_delaycal.png",
        overwrite=True,
        showgui=False,
    )

# Calculate fractions of flagged solutions for final QA2

flaggedDelaySolns = getCalFlaggedSoln("testdelay.k")
flaggedGainSolns = getCalFlaggedSoln("testBPdinitialgain.g")
flaggedBPSolns = getCalFlaggedSoln("testBPcal.b")

if flaggedDelaySolns["all"]["total"] > 0:
    if flaggedDelaySolns["antmedian"]["fraction"] > critfrac:
        QA2_delay = "Partial"
    else:
        QA2_delay = "Pass"
else:
    QA2_delay = "Fail"

task_logprint(f"QA2_delay: {QA2_delay}")

if flaggedGainSolns["all"]["total"] > 0:
    if flaggedGainSolns["antmedian"]["fraction"] > 0.1:
        QA2_gain = "Partial"
    else:
        QA2_gain = "Pass"
else:
    QA2_gain = "Fail"

task_logprint(f"QA2_gain: {QA2_gain}")

if flaggedBPSolns["all"]["total"] > 0:
    if flaggedBPSolns["antmedian"]["fraction"] > 0.2:
        QA2_BP = "Partial"
    else:
        QA2_BP = "Pass"
else:
    QA2_BP = "Fail"

task_logprint(f"QA2_BP: {QA2_BP}")

if QA2_delay == "Fail" or QA2_gain == "Fail" or QA2_BP == "Fail":
    QA2_testBPdcals = "Fail"
elif QA2_delay == "Partial" or QA2_gain == "Partial" or QA2_BP == "Partial":
    QA2_testBPdcals = "Partial"


task_logprint(f"QA2 score: {QA2_testBPdcals}")
task_logprint("Finished EVLA_pipe_testBPdcals.py")
time_list = runtiming("testBPdcals", "end")

pipeline_save()
