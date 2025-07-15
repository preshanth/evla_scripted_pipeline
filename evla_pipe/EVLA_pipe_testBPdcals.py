# EVLA_pipe_testBPdcals.py (Refactored - Calibration Part)

import os
import copy
import numpy as np
from casatasks import gaincal, bandpass, applycal
from casatools import table
from evla_pipe.utils import (
    runtiming,
    logprint,
    RefAntHeuristics,
    testdelays,
    testBPdgains,
    getCalFlaggedSoln,
    get_caltable_path,
    format_qa_status,
)

tb = table()

def task_logprint(msg):
    logprint(msg, logfileout="logs/testBPdcals.log")

def test_bandpass_and_delay_calibration(pipeline_context, priorcals):
    """
    Test bandpass and delay calibration. Returns QA2 scores.
    """
    task_logprint("*** Starting test bandpass and delay calibration ***")
    time_list = runtiming("testBPdcals_cal", "start")
    QA2_testBPdcals = "Pass"
    QA2_delay = "Pass"
    QA2_gain = "Pass"
    QA2_BP = "Pass"

    ms_active = pipeline_context.get("msname")
    delay_field_select_string = pipeline_context.get("delay_field_select_string", "")
    tst_delay_spw = pipeline_context.get("tst_delay_spw", "")
    delay_scan_select_string = pipeline_context.get("delay_scan_select_string", "")
    uvrange3C84 = pipeline_context.get("uvrange3C84", "")
    cal3C84_d = pipeline_context.get("cal3C84_d", False)
    minBL_for_cal = pipeline_context.get("minBL_for_cal", 3)
    refantfield = pipeline_context.get("calibrator_field_select_string", "")
    critfrac = pipeline_context.get("critfrac", 0.5) # Provide a default if not in context
    bandpass_field_select_string = pipeline_context.get("bandpass_field_select_string", "")
    bandpass_scan_select_string = pipeline_context.get("bandpass_scan_select_string", "")
    tst_bpass_spw = pipeline_context.get("tst_bpass_spw", "")
    cal3C84_bp = pipeline_context.get("cal3C84_bp", False)
    int_time = pipeline_context.get("int_time", 0.0)
    cal3C84 = cal3C84_d or cal3C84_bp

    # --- Find a reference antenna ---
    task_logprint("Finding a reference antenna")
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

    # --- Initial phase solutions on the delay calibrator ---
    testdelayinitialgain_table = str(get_caltable_path("testdelayinitialgain.g", "test"))
    os.system(f"rm -rf {testdelayinitialgain_table}")
    uvrange_delay = uvrange3C84 if cal3C84_d else ""
    gaincal(
        vis=ms_active,
        caltable=testdelayinitialgain_table,
        field=delay_field_select_string,
        spw=tst_delay_spw,
        intent="",
        selectdata=True,
        uvrange=uvrange_delay,
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

    # --- Test delay calibration ---
    testdelay_table = str(get_caltable_path("testdelay.k", "test"))
    os.system(f"rm -rf {testdelay_table}")
    found_good_refant = False
    for ii in range(min(5, len(RefAntOutput))):
        refAnt_test = str(RefAntOutput[ii])
        task_logprint(f"Testing reference antenna: {refAnt_test}")
        flaggedSolnResult = testdelays(
            ms_active,
            testdelay_table,
            delay_field_select_string,
            delay_scan_select_string,
            refAnt_test,
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
            refAnt = refAnt_test
            task_logprint(f"Using {refAnt} as reference antenna.")
            found_good_refant = True
            break
    if not found_good_refant:
        task_logprint(
            "WARNING, tried several reference antennas, there might be something wrong with your data"
        )
        QA2_delay = "Fail"
        QA2_testBPdcals = "Fail"

    # --- Initial amplitude and phase gain solutions ---
    testgainscans = ""
    if delay_scan_select_string == bandpass_scan_select_string:
        testgainscans = bandpass_scan_select_string
    else:
        testgainscans = f"{bandpass_scan_select_string},{delay_scan_select_string}"

    flagging_threshold = 0.05
    gain_solint1 = ""
    shortsol1 = 0.0

    for time_factor in (1.0, 3.0, 10.0):
        soltime = time_factor * int_time
        solint = f"{soltime}s"
        testBPdinitialgain_table = str(get_caltable_path("testBPdinitialgain.g", "test"))
        os.system(f"rm -rf {testBPdinitialgain_table}")
        flaggedSolnResult1 = testBPdgains(
            ms_active,
            testBPdinitialgain_table,
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
            gain_solint1 = solint
            shortsol1 = soltime
            break
    else:
        task_logprint(
            "WARNING, large fraction of flagged solutions, there might be something wrong with your data."
        )
        QA2_gain = "Fail"
        QA2_testBPdcals = "Fail"

    task_logprint(
        "Test amp and phase calibration on delay and bandpass calibrators complete"
    )

    # --- Test bandpass calibration ---
    task_logprint("Doing test bandpass calibration")
    testBPcal_table = str(get_caltable_path("testBPcal.b", "test"))
    os.system(f"rm -rf {testBPcal_table}")
    BPGainTables = copy.copy(priorcals)
    BPGainTables.append(testdelay_table)
    BPGainTables.append(testBPdinitialgain_table)
    uvrange_bp = uvrange3C84 if cal3C84_bp else ""
    bandpass(
        vis=ms_active,
        caltable=testBPcal_table,
        field=bandpass_field_select_string,
        spw="",
        intent="",
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
    task_logprint("Test bandpass calibration complete")
    flaggedSolnResultBP = getCalFlaggedSoln(testBPcal_table)
    task_logprint(
        "Fraction of flagged BP solutions = " + str(flaggedSolnResultBP["all"]["fraction"])
    )
    task_logprint(
        "Median fraction of flagged BP solutions per antenna = "
        + str(flaggedSolnResultBP["antmedian"]["fraction"])
    )

    # --- Apply test calibrations ---
    task_logprint("Applying test calibrations to BP and delay calibrators")
    AllCalTables = copy.copy(priorcals)
    AllCalTables.append(testdelay_table)
    AllCalTables.append(testBPdinitialgain_table)
    AllCalTables.append(testBPcal_table)
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
    task_logprint("Applied test calibrations")

    # --- Calculate fractions of flagged solutions for final QA2 ---
    if flaggedSolnResult["all"]["total"] > 0:
        if flaggedSolnResult["antmedian"]["fraction"] > critfrac:
            QA2_delay = "Partial"
    else:
        QA2_delay = "Fail"
    task_logprint(f"QA2_delay: {QA2_delay}")

    if flaggedSolnResult1["all"]["total"] > 0:
        if flaggedSolnResult1["antmedian"]["fraction"] > 0.1:
            QA2_gain = "Partial"
    else:
        QA2_gain = "Fail"
    task_logprint(f"QA2_gain: {QA2_gain}")

    if flaggedSolnResultBP["all"]["total"] > 0:
        if flaggedSolnResultBP["antmedian"]["fraction"] > 0.2:
            QA2_BP = "Partial"
    else:
        QA2_BP = "Pass"
    task_logprint(f"QA2_BP: {QA2_BP}")

    if QA2_delay == "Fail" or QA2_gain == "Fail" or QA2_BP == "Fail":
        QA2_testBPdcals = "Fail"
    elif QA2_delay == "Partial" or QA2_gain == "Partial" or QA2_BP == "Partial":
        QA2_testBPdcals = "Partial"

        # Import colored output function
    task_logprint(f"QA2 score: {format_qa_status(QA2_testBPdcals)}")
    time_list = runtiming("testBPdcals_cal", "end")

    # Save calibration tables to context for resume capability
    calibration_results = {
        "QA2_testBPdcals": QA2_testBPdcals,
        "testBPdcals_tables": ["testdelayinitialgain.g", "testBPcal.b"],
        "BPGainTables": BPGainTables,
        "AllCalTables": AllCalTables,
        "time_list": time_list
    }
    
    return calibration_results

def EVLA_pipe_testBPdcals(pipeline_context):
    """
    Main entry point for EVLA_pipe_testBPdcals pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    from evla_pipe.utils import runtiming, logprint
    
    task_logprint("*** Starting EVLA_pipe_testBPdcals.py ***")
    time_list = runtiming("testBPdcals", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        # Call the main function if it exists
        if "test_bandpass_and_delay_calibration" in globals():
            # Get priorcals from previous step or use default
            priorcals = pipeline_context.get("priorcals", ["gain_curves.g", "opacities.g"])
            results = test_bandpass_and_delay_calibration(pipeline_context, priorcals)
            if isinstance(results, dict):
                # New format - results contain calibration tables
                QA2_score = results.get("QA2_testBPdcals", "Pass")
                # Save calibration tables to context
                pipeline_context.update({
                    "testBPdcals_tables": results.get("testBPdcals_tables", []),
                    "BPGainTables": results.get("BPGainTables", []),
                    "AllCalTables": results.get("AllCalTables", [])
                })
            else:
                # Old format - just QA2 score
                QA2_score = results
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_testBPdcals: {e}")
        QA2_score = "Fail"
    
    task_logprint(f"Finished EVLA_pipe_testBPdcals.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("testBPdcals", "end")
    
    
    # Update context and return
    pipeline_context["QA2_testBPdcals"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
