# semi_final_cal_apply.py

import copy
import os
import numpy as np
from casatasks import gaincal, bandpass, applycal
from casatools import table
from .utils import (
    logprint,
    runtiming,
    RefAntHeuristics,
    semiFinaldelays,
    getCalFlaggedSoln,
)

tb = table()

def task_logprint(msg):
    logprint(msg, logfileout="logs/semiFinalBPdcals1_cal.log")

def perform_semi_final_calibration(pipeline_context, priorcals):
    """
    Perform semi-final delay and bandpass calibrations and apply them to calibrators.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
        priorcals (list): List of prior calibration tables.

    Returns:
        str: The overall QA2 score for this calibration stage.
    """
    task_logprint("*** Starting semi-final delay and BP calibrations ***")
    time_list = runtiming("semiFinalBPdcals1_cal", "start")
    QA2_semiFinalBPdcals1 = "Pass"
    QA2_delay = "Pass"
    QA2_BP = "Pass"

    ms_active = pipeline_context.get("msname")
    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")
    delay_field_select_string = pipeline_context.get("delay_field_select_string", "")
    tst_delay_spw = pipeline_context.get("tst_delay_spw", "")
    uvrange3C84 = pipeline_context.get("uvrange3C84", "")
    cal3C84_d = pipeline_context.get("cal3C84_d", False)
    minBL_for_cal = pipeline_context.get("minBL_for_cal", 3)
    critfrac = pipeline_context.get("critfrac", 0.5)
    numAntenna = pipeline_context.get("numAntenna", 0)
    bandpass_field_select_string = pipeline_context.get("bandpass_field_select_string", "")
    tst_bpass_spw = pipeline_context.get("tst_bpass_spw", "")
    cal3C84_bp = pipeline_context.get("cal3C84_bp", False)
    gain_solint1 = pipeline_context.get("gain_solint1", "")
    calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")

    # --- Find reference antenna ---
    task_logprint("Finding a reference antenna for semi-final delay and BP calibrations")
    findrefant = RefAntHeuristics(
        vis=ms_active, field=calibrator_field_select_string, geometry=True, flagging=True
    )
    RefAntOutput = findrefant.calculate()
    refAnt = str(RefAntOutput[0])
    task_logprint(f"The pipeline will use antenna {refAnt} as the reference")

    # --- Initial phase solutions on delay calibrator ---
    os.system("rm -rf semiFinaldelayinitialgain.g")
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

    # --- Semi-final delay calibration ---
    os.system("rm -rf delay.k")
    flaggedDelaySolns = semiFinaldelays(
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
        "Fraction of flagged delay solutions = " + str(flaggedDelaySolns["all"]["fraction"])
    )
    task_logprint(
        "Median fraction of flagged delay solutions per antenna = "
        + str(flaggedDelaySolns["antmedian"]["fraction"])
    )
    task_logprint("Delay calibration complete")

    if flaggedDelaySolns["all"]["total"] > 0:
        if flaggedDelaySolns["antmedian"]["fraction"] > critfrac:
            QA2_delay = "Partial"
        else:
            QA2_delay = "Pass"
    else:
        QA2_delay = "Fail"
    task_logprint(f"QA2_delay: {QA2_delay}")

    # --- Initial gaincal on BP calibrator ---
    os.system("rm -rf BPdinitialgain.g")
    GainTables = copy.copy(priorcals)
    GainTables.append("delay.k")
    uvrange_bp = uvrange3C84 if cal3C84_bp else ""
    gaincal(
        vis=ms_active,
        caltable="BPdinitialgain.g",
        field="",
        spw=tst_bpass_spw,
        selectdata=True,
        uvrange=uvrange_bp,
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

    # --- Semi-final BP calibration ---
    os.system("rm -rf BPcal.b")
    BPGainTables = copy.copy(priorcals)
    BPGainTables.append("delay.k")
    BPGainTables.append("BPdinitialgain.g")
    bandpass(
        vis=ms_active,
        caltable="BPcal.b",
        field=bandpass_field_select_string,
        spw="",
        selectdata=True,
        uvrange=uvrange_bp,
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

    flaggedBPSolns = getCalFlaggedSoln("BPcal.b")
    task_logprint(
        "Fraction of flagged BP solutions = " + str(flaggedBPSolns["all"]["fraction"])
    )
    task_logprint(
        "Median fraction of flagged BP solutions per antenna = "
        + str(flaggedBPSolns["antmedian"]["fraction"])
    )

    if flaggedBPSolns["all"]["total"] > 0:
        if flaggedBPSolns["antmedian"]["fraction"] > 0.2:
            QA2_BP = "Partial"
        else:
            QA2_BP = "Pass"
    else:
        QA2_BP = "Fail"
    task_logprint(f"QA2_BP: {QA2_BP}")

    # --- Apply semi-final delay and BP calibrations to all calibrators ---
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
    task_logprint("Applied semi-final delay and BP calibrations to calibrators")

    if QA2_delay == "Fail" or QA2_BP == "Fail":
        QA2_semiFinalBPdcals1 = "Fail"
    elif QA2_delay == "Partial" or QA2_BP == "Partial":
        QA2_semiFinalBPdcals1 = "Partial"

    task_logprint(f"QA2 score: {QA2_semiFinalBPdcals1}")
    time_list = runtiming("semiFinalBPdcals1_cal", "end")

    return QA2_semiFinalBPdcals1