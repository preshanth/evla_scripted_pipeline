"""
Perform Semi-final delay and bandpass calibrations (semi-final because we have
not yet determined the spectral index of the bandpass calibrator).
"""

import copy

import numpy as np

from casatasks import gaincal, bandpass, applycal
from casatools import table
from casaplotms import plotms

from . import pipeline_save
from .utils import (
    logprint,
    runtiming,
    RefAntHeuristics,
    semiFinaldelays,
    getCalFlaggedSoln,
)

tb = table()


def task_logprint(msg):
    logprint(msg, logfileout="logs/semiFinalBPdcals1.log")


# Find reference antenna again after all that flagging
task_logprint("Starting EVLA_pipe_semiFinalBPdcals1.py")
time_list = runtiming("semiFinalBPdcals1", "start")
QA2_semiFinalBPdcals1 = "Pass"

task_logprint("Finding a reference antenna for semi-final delay and BP calibrations")


refantspw = ""
refantfield = calibrator_field_select_string

findrefant = RefAntHeuristics(
    vis=ms_active, field=refantfield, geometry=True, flagging=True
)
RefAntOutput = findrefant.calculate()
refAnt = str(RefAntOutput[0])

task_logprint(f"The pipeline will use antenna {refAnt} as the reference")

# Initial phase solutions on delay calibrator
os.system("rm -rf semiFinaldelayinitialgain.g")
uvrange = uvrange3C84 if cal3C84_d else ""
gaincal(
    vis=ms_active,
    caltable="semiFinaldelayinitialgain.g",
    field=delay_field_select_string,
    spw=tst_delay_spw,
    intent="",
    selectdata=True,
    uvrange=uvrange3C84,
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

os.system("rm -rf delay.k")
flaggedSolnResult = semiFinaldelays(
    ms_active,
    "delay.k",
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

os.system("rm -rf testdelay.k")
for ii in range(5):
    refAnt = str(RefAntOutput[ii])
    task_logprint(f"Testing referance antenna: {refAnt}")
    flaggedSolnResult = testdelays(
        ms_active,
        "delay.k",
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
    QA2_semiFinalBPdcals1 = "Fail"
task_logprint("Delay calibration complete")

task_logprint("Plotting delays")
nplots = int(numAntenna / 3)
if (numAntenna % 3) > 0:
    nplots = nplots + 1
for ii in range(nplots):
    plotfile = f"delay{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="delay.k",
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

# Do initial gaincal on BP calibrator then semi-final BP calibration
os.system("rm -rf BPinitialgain.g")
GainTables = copy.copy(priorcals)
GainTables.append("delay.k")
uvrange = uvrange3C84 if cal3C84_bp else ""
gaincal(
    vis=ms_active,
    caltable="BPinitialgain.g",
    field="",
    spw=tst_bpass_spw,
    selectdata=True,
    uvrange=uvrange3C84,
    scan=bandpass_scan_select_string,
    solint=gain_solint1,
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
    gaintable=GainTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)
task_logprint("Initial gain calibration on BP calibrator complete")


task_logprint("Plotting initial phase gain calibration on BP calibrator")
for ii in range(nplots):
    plotfile = f"BPinitialgainphase{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="BPdinitialgain.g",
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


os.system("rm -rf BPcal.b")
BPGainTables = copy.copy(priorcals)
BPGainTables.append("delay.k")
BPGainTables.append("BPinitialgain.g")
uvrange = uvrange3C84 if cal3C84_bp else ""
bandpass(
    vis=ms_active,
    caltable="BPcal.b",
    field=bandpass_field_select_string,
    spw="",
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
task_logprint("Bandpass calibration complete")

flaggedSolnResult = getCalFlaggedSoln("BPcal.b")
logprint("Fraction of flagged solutions = " + str(flaggedSolnResult["all"]["fraction"]))
logprint(
    "Median fraction of flagged solutions per antenna = "
    + str(flaggedSolnResult["antmedian"]["fraction"])
)


logprint("Plotting bandpass solutions")
try:
    tb.open("BPcal.b")
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
    plotfile = f"BPcal_amp{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="BPcal.b",
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
    plotfile = f"BPcal_phase{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    # create plot
    plotms(
        vis="BPcal.b",
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
task_logprint("Plotting complete")


task_logprint("Applying semi-final delay and BP calibrations to all calibrators")
AllCalTables = copy.copy(priorcals)
AllCalTables.append("delay.k")
AllCalTables.append("BPcal.b")
ntables = len(AllCalTables)
applycal(
    vis=ms_active,
    field="",
    spw="",
    selectdata=True,
    scan=calibrator_scan_select_string,
    gaintable=AllCalTables,
    interp=[""],
    spwmap=[],
    parang=False,
    calwt=[False] * ntables,
    applymode="calflagstrict",
    flagbackup=False,
)


# NB: have to find a way to get plotms to reload data to show
# flagged result on second run
task_logprint("Plot calibrated calibrators to check for further flagging/RFI")
plotms(
    vis=ms_active,
    xaxis="freq",
    yaxis="amp",
    ydatacolumn="corrected",
    selectdata=True,
    scan=calibrator_scan_select_string,
    correlation=corrstring,
    averagedata=True,
    avgtime="1e8",
    avgscan=False,
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
    plotfile="semifinalcalibratedcals1.png",
    showgui=False,
    highres=True,
    overwrite=True,
)

# Calculate fractions of flagged solutions for final QA2
flaggedDelaySolns = getCalFlaggedSoln("delay.k")
flaggedBPSolns = getCalFlaggedSoln("BPcal.b")

if flaggedDelaySolns["all"]["total"] > 0:
    if flaggedDelaySolns["antmedian"]["fraction"] > critfrac:
        QA2_delay = "Partial"
    else:
        QA2_delay = "Pass"
else:
    QA2_delay = "Fail"
task_logprint(f"QA2_delay: {QA2_delay}")

if flaggedBPSolns["all"]["total"] > 0:
    if flaggedBPSolns["antmedian"]["fraction"] > 0.2:
        QA2_BP = "Partial"
    else:
        QA2_BP = "Pass"
else:
    QA2_BP = "Fail"
task_logprint(f"QA2_BP: {QA2_BP}")

if QA2_delay == "Fail" or QA2_BP == "Fail":
    QA2_semiFinalBPdcals1 = "Fail"
elif QA2_delay == "Partial" or QA2_BP == "Partial":
    QA2_semiFinalBPdcals1 = "Partial"

task_logprint(f"QA2 score: {QA2_semiFinalBPdcals1}")
task_logprint("Finished EVLA_pipe_semiFinalBPdcals1.py")
time_list = runtiming("semiFinalBPdcals1", "end")

pipeline_save()
