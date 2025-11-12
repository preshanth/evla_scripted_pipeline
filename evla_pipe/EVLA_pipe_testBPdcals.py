"""
EVLA Pipeline: Test Bandpass and Delay Calibration

This module performs test calibration runs for bandpass and delay calibrators
to determine optimal reference antenna and solution intervals.

Refactored from original EVLA_pipe_testBPdcals.py to follow function-based pattern.
"""

import os
import copy
from typing import Dict, Any, List, Optional
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


def task_logprint(msg: str) -> None:
    """
    Log message to testBPdcals-specific log file.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/testBPdcals.log")


def find_reference_antenna(
    ms_active: str,
    refantfield: str,
    minBL_for_cal: int
) -> List[str]:
    """
    Find suitable reference antenna candidates using heuristics.

    Parameters
    ----------
    ms_active : str
        Path to measurement set
    refantfield : str
        Field selection string for reference antenna search
    minBL_for_cal : int
        Minimum number of baselines for calibration

    Returns
    -------
    list of str
        Ordered list of reference antenna candidates
    """
    task_logprint("Finding reference antenna candidates")

    findrefant = RefAntHeuristics(
        vis=ms_active,
        field=refantfield,
        geometry=True,
        flagging=True,
    )
    RefAntOutput = findrefant.calculate()

    task_logprint(f"Top reference antenna candidate: {RefAntOutput[0]}")

    return [str(ant) for ant in RefAntOutput]


def calibrate_initial_delay_phase(
    ms_active: str,
    delay_field_select_string: str,
    tst_delay_spw: str,
    delay_scan_select_string: str,
    refAnt: str,
    minBL_for_cal: int,
    priorcals: List[str],
    cal3C84_d: bool,
    uvrange3C84: str
) -> str:
    """
    Compute initial phase solutions on delay calibrator.

    Parameters
    ----------
    ms_active : str
        Measurement set path
    delay_field_select_string : str
        Field selection for delay calibrator
    tst_delay_spw : str
        Spectral window selection
    delay_scan_select_string : str
        Scan selection string
    refAnt : str
        Reference antenna
    minBL_for_cal : int
        Minimum baselines per antenna
    priorcals : list of str
        Prior calibration tables
    cal3C84_d : bool
        Whether calibrating 3C84
    uvrange3C84 : str
        UV range for 3C84

    Returns
    -------
    str
        Path to calibration table
    """
    task_logprint("Computing initial phase solutions on delay calibrator")

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

    task_logprint("Initial phase calibration complete")

    return testdelayinitialgain_table


def test_delay_calibration(
    ms_active: str,
    delay_field_select_string: str,
    delay_scan_select_string: str,
    refant_candidates: List[str],
    minBL_for_cal: int,
    priorcals: List[str],
    cal3C84_d: bool,
    uvrange3C84: str,
    critfrac: float
) -> Dict[str, Any]:
    """
    Test delay calibration with multiple reference antennas.

    Parameters
    ----------
    ms_active : str
        Measurement set path
    delay_field_select_string : str
        Field selection for delay calibrator
    delay_scan_select_string : str
        Scan selection string
    refant_candidates : list of str
        Ordered list of reference antenna candidates
    minBL_for_cal : int
        Minimum baselines per antenna
    priorcals : list of str
        Prior calibration tables
    cal3C84_d : bool
        Whether calibrating 3C84
    uvrange3C84 : str
        UV range for 3C84
    critfrac : float
        Critical fraction threshold for flagged solutions

    Returns
    -------
    dict
        Results containing:
        - refant: Selected reference antenna
        - delay_table: Path to delay calibration table
        - qa_status: QA status ("Pass", "Partial", "Fail")
        - flagged_fraction: Fraction of flagged solutions
    """
    task_logprint("Testing delay calibration")

    testdelay_table = str(get_caltable_path("testdelay.k", "test"))
    found_good_refant = False
    selected_refant = None
    flagged_fraction = 1.0

    for ii in range(min(5, len(refant_candidates))):
        refAnt_test = refant_candidates[ii]
        task_logprint(f"Testing reference antenna: {refAnt_test}")

        os.system(f"rm -rf {testdelay_table}")

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
            f"Fraction of flagged solutions = {flaggedSolnResult['all']['fraction']}"
        )
        task_logprint(
            f"Median fraction per antenna = {flaggedSolnResult['antmedian']['fraction']}"
        )

        if flaggedSolnResult["all"]["total"] > 0:
            fracFlaggedSolns = flaggedSolnResult["antmedian"]["fraction"]
        else:
            fracFlaggedSolns = 1.0

        if fracFlaggedSolns < critfrac:
            selected_refant = refAnt_test
            flagged_fraction = fracFlaggedSolns
            task_logprint(f"Using {selected_refant} as reference antenna")
            found_good_refant = True
            break

    # Determine QA status
    if not found_good_refant:
        task_logprint(
            "WARNING: Tried several reference antennas, possible data quality issue"
        )
        qa_status = "Fail"
        selected_refant = refant_candidates[0]  # Use first candidate anyway
    elif flagged_fraction > critfrac:
        qa_status = "Partial"
    else:
        qa_status = "Pass"

    return {
        "refant": selected_refant,
        "delay_table": testdelay_table,
        "qa_status": qa_status,
        "flagged_fraction": float(flagged_fraction),
    }


def test_initial_gains(
    ms_active: str,
    tst_bpass_spw: str,
    testgainscans: str,
    refAnt: str,
    minBL_for_cal: int,
    priorcals: List[str],
    cal3C84: bool,
    uvrange3C84: str,
    int_time: float
) -> Dict[str, Any]:
    """
    Test initial amplitude and phase gain solutions with varying solution intervals.

    Parameters
    ----------
    ms_active : str
        Measurement set path
    tst_bpass_spw : str
        Spectral window selection
    testgainscans : str
        Scan selection string
    refAnt : str
        Reference antenna
    minBL_for_cal : int
        Minimum baselines per antenna
    priorcals : list of str
        Prior calibration tables
    cal3C84 : bool
        Whether calibrating 3C84
    uvrange3C84 : str
        UV range for 3C84
    int_time : float
        Integration time in seconds

    Returns
    -------
    dict
        Results containing:
        - gain_table: Path to gain calibration table
        - gain_solint: Selected solution interval
        - qa_status: QA status
        - flagged_fraction: Fraction of flagged solutions
    """
    task_logprint("Testing initial amplitude and phase gain solutions")

    flagging_threshold = 0.05
    gain_solint = ""
    best_flagged_fraction = 1.0
    gain_table = ""

    for time_factor in (1.0, 3.0, 10.0):
        soltime = time_factor * int_time
        solint = f"{soltime}s"

        testBPdinitialgain_table = str(get_caltable_path("testBPdinitialgain.g", "test"))
        os.system(f"rm -rf {testBPdinitialgain_table}")

        flaggedSolnResult = testBPdgains(
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

        frac_flagged = flaggedSolnResult["all"]["fraction"]
        frac_flagged_med = flaggedSolnResult["antmedian"]["fraction"]
        frac_flagged_tot = flaggedSolnResult["all"]["total"]

        task_logprint(f"For solint={solint}: flagged fraction = {frac_flagged}")
        task_logprint(f"Median flagged fraction per antenna = {frac_flagged_med}")

        if frac_flagged_tot > 0:
            fracFlaggedSolns = frac_flagged_med
        else:
            fracFlaggedSolns = 1.0

        if fracFlaggedSolns < flagging_threshold:
            task_logprint(f"Using short solution interval: {solint}")
            gain_solint = solint
            gain_table = testBPdinitialgain_table
            best_flagged_fraction = fracFlaggedSolns
            break
    else:
        task_logprint(
            "WARNING: Large fraction of flagged solutions, possible data quality issue"
        )
        gain_table = testBPdinitialgain_table
        gain_solint = f"{10.0 * int_time}s"  # Use longest interval tried

    # Determine QA status
    if best_flagged_fraction >= 0.5:
        qa_status = "Fail"
    elif best_flagged_fraction > 0.1:
        qa_status = "Partial"
    else:
        qa_status = "Pass"

    return {
        "gain_table": gain_table,
        "gain_solint": gain_solint,
        "qa_status": qa_status,
        "flagged_fraction": float(best_flagged_fraction),
    }


def test_bandpass_calibration(
    ms_active: str,
    bandpass_field_select_string: str,
    bandpass_scan_select_string: str,
    refAnt: str,
    minBL_for_cal: int,
    priorcals: List[str],
    delay_table: str,
    gain_table: str,
    cal3C84_bp: bool,
    uvrange3C84: str
) -> Dict[str, Any]:
    """
    Compute test bandpass calibration.

    Parameters
    ----------
    ms_active : str
        Measurement set path
    bandpass_field_select_string : str
        Field selection for bandpass calibrator
    bandpass_scan_select_string : str
        Scan selection string
    refAnt : str
        Reference antenna
    minBL_for_cal : int
        Minimum baselines per antenna
    priorcals : list of str
        Prior calibration tables
    delay_table : str
        Delay calibration table
    gain_table : str
        Gain calibration table
    cal3C84_bp : bool
        Whether calibrating 3C84
    uvrange3C84 : str
        UV range for 3C84

    Returns
    -------
    dict
        Results containing:
        - bp_table: Path to bandpass calibration table
        - qa_status: QA status
        - flagged_fraction: Fraction of flagged solutions
    """
    task_logprint("Computing test bandpass calibration")

    testBPcal_table = str(get_caltable_path("testBPcal.b", "test"))
    os.system(f"rm -rf {testBPcal_table}")

    BPGainTables = copy.copy(priorcals)
    BPGainTables.append(delay_table)
    BPGainTables.append(gain_table)

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
    frac_flagged = flaggedSolnResultBP["all"]["fraction"]
    frac_flagged_med = flaggedSolnResultBP["antmedian"]["fraction"]

    task_logprint(f"Fraction of flagged BP solutions = {frac_flagged}")
    task_logprint(f"Median fraction per antenna = {frac_flagged_med}")

    # Determine QA status
    if flaggedSolnResultBP["all"]["total"] == 0:
        qa_status = "Pass"  # No solutions to flag means success
        flagged_fraction = 0.0
    elif frac_flagged_med > 0.5:
        qa_status = "Fail"
        flagged_fraction = frac_flagged_med
    elif frac_flagged_med > 0.2:
        qa_status = "Partial"
        flagged_fraction = frac_flagged_med
    else:
        qa_status = "Pass"
        flagged_fraction = frac_flagged_med

    return {
        "bp_table": testBPcal_table,
        "bp_gaintables": BPGainTables,
        "qa_status": qa_status,
        "flagged_fraction": float(flagged_fraction),
    }


def apply_test_calibrations(
    ms_active: str,
    testgainscans: str,
    priorcals: List[str],
    delay_table: str,
    gain_table: str,
    bp_table: str
) -> None:
    """
    Apply all test calibrations to the data.

    Parameters
    ----------
    ms_active : str
        Measurement set path
    testgainscans : str
        Scan selection string
    priorcals : list of str
        Prior calibration tables
    delay_table : str
        Delay calibration table
    gain_table : str
        Gain calibration table
    bp_table : str
        Bandpass calibration table
    """
    task_logprint("Applying test calibrations to BP and delay calibrators")

    AllCalTables = copy.copy(priorcals)
    AllCalTables.append(delay_table)
    AllCalTables.append(gain_table)
    AllCalTables.append(bp_table)

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


def testbpdcals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test bandpass and delay calibration with reference antenna optimization.

    This function performs test calibrations to determine:
    - Optimal reference antenna
    - Delay calibration quality
    - Gain solution interval
    - Bandpass calibration quality

    The test calibrations are applied to the data and QA scores are computed
    based on the fraction of flagged solutions.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname: Measurement set path
        - delay_field_select_string: Delay calibrator field selection
        - bandpass_field_select_string: Bandpass calibrator field selection
        - tst_delay_spw: Spectral window for delay calibration
        - tst_bpass_spw: Spectral window for bandpass calibration
        - delay_scan_select_string: Delay calibrator scans
        - bandpass_scan_select_string: Bandpass calibrator scans
        - calibrator_field_select_string: Field for reference antenna search
        - uvrange3C84: UV range for 3C84 calibration
        - cal3C84_d: Whether delay calibrator is 3C84
        - cal3C84_bp: Whether bandpass calibrator is 3C84
        - minBL_for_cal: Minimum baselines for calibration
        - critfrac: Critical fraction for flagged solutions
        - int_time: Integration time
        - priorcals: Prior calibration tables

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_testBPdcals: Overall QA score
        - QA2_delay: Delay calibration QA score
        - QA2_gain: Gain calibration QA score
        - QA2_BP: Bandpass calibration QA score
        - refant: Selected reference antenna
        - gain_solint1: Selected gain solution interval
        - testBPdcals_tables: List of calibration table names
        - BPGainTables: Gain tables used for bandpass
        - AllCalTables: All calibration tables applied
        - testBPdcals_flagged_fractions: Flagging statistics

    Notes
    -----
    - Tests multiple reference antennas to find one with acceptable flagging
    - Tests multiple gain solution intervals (1x, 3x, 10x integration time)
    - Sets QA flags based on fraction of flagged solutions
    - All calibration tables are saved with "test" prefix
    """
    task_logprint("*** Starting test bandpass and delay calibration ***")
    time_list = runtiming("testBPdcals", "start")

    # Extract parameters from context
    ms_active = pipeline_context.get("msname", "")
    delay_field_select_string = pipeline_context.get("delay_field_select_string", "")
    bandpass_field_select_string = pipeline_context.get("bandpass_field_select_string", "")
    tst_delay_spw = pipeline_context.get("tst_delay_spw", "")
    tst_bpass_spw = pipeline_context.get("tst_bpass_spw", "")
    delay_scan_select_string = pipeline_context.get("delay_scan_select_string", "")
    bandpass_scan_select_string = pipeline_context.get("bandpass_scan_select_string", "")
    refantfield = pipeline_context.get("calibrator_field_select_string", "")
    uvrange3C84 = pipeline_context.get("uvrange3C84", "")
    cal3C84_d = pipeline_context.get("cal3C84_d", False)
    cal3C84_bp = pipeline_context.get("cal3C84_bp", False)
    minBL_for_cal = pipeline_context.get("minBL_for_cal", 3)
    critfrac = pipeline_context.get("critfrac", 0.5)
    int_time = pipeline_context.get("int_time", 0.0)
    priorcals = pipeline_context.get("priorcals", [])

    cal3C84 = cal3C84_d or cal3C84_bp

    try:
        # Find reference antenna candidates
        refant_candidates = find_reference_antenna(
            ms_active, refantfield, minBL_for_cal
        )

        # Compute initial delay phase solutions
        initial_delay_gain_table = calibrate_initial_delay_phase(
            ms_active,
            delay_field_select_string,
            tst_delay_spw,
            delay_scan_select_string,
            refant_candidates[0],  # Use top candidate for initial solution
            minBL_for_cal,
            priorcals,
            cal3C84_d,
            uvrange3C84,
        )

        # Test delay calibration with reference antenna selection
        delay_results = test_delay_calibration(
            ms_active,
            delay_field_select_string,
            delay_scan_select_string,
            refant_candidates,
            minBL_for_cal,
            priorcals,
            cal3C84_d,
            uvrange3C84,
            critfrac,
        )

        selected_refant = delay_results["refant"]
        QA2_delay = delay_results["qa_status"]

        # Determine scan selection for gain calibration
        if delay_scan_select_string == bandpass_scan_select_string:
            testgainscans = bandpass_scan_select_string
        else:
            testgainscans = f"{bandpass_scan_select_string},{delay_scan_select_string}"

        # Test initial gain solutions
        gain_results = test_initial_gains(
            ms_active,
            tst_bpass_spw,
            testgainscans,
            selected_refant,
            minBL_for_cal,
            priorcals,
            cal3C84,
            uvrange3C84,
            int_time,
        )

        QA2_gain = gain_results["qa_status"]

        # Test bandpass calibration
        bp_results = test_bandpass_calibration(
            ms_active,
            bandpass_field_select_string,
            bandpass_scan_select_string,
            selected_refant,
            minBL_for_cal,
            priorcals,
            delay_results["delay_table"],
            gain_results["gain_table"],
            cal3C84_bp,
            uvrange3C84,
        )

        QA2_BP = bp_results["qa_status"]

        # Apply all test calibrations
        apply_test_calibrations(
            ms_active,
            testgainscans,
            priorcals,
            delay_results["delay_table"],
            gain_results["gain_table"],
            bp_results["bp_table"],
        )

        # Determine overall QA status
        if QA2_delay == "Fail" or QA2_gain == "Fail" or QA2_BP == "Fail":
            QA2_testBPdcals = "Fail"
        elif QA2_delay == "Partial" or QA2_gain == "Partial" or QA2_BP == "Partial":
            QA2_testBPdcals = "Partial"
        else:
            QA2_testBPdcals = "Pass"

        # Prepare calibration table lists for context
        AllCalTables = copy.copy(priorcals)
        AllCalTables.append(delay_results["delay_table"])
        AllCalTables.append(gain_results["gain_table"])
        AllCalTables.append(bp_results["bp_table"])

        # Update context with results
        pipeline_context.update({
            "QA2_testBPdcals": QA2_testBPdcals,
            "QA2_delay": QA2_delay,
            "QA2_gain": QA2_gain,
            "QA2_BP": QA2_BP,
            "refant": selected_refant,
            "gain_solint1": gain_results["gain_solint"],
            "testBPdcals_tables": [
                "testdelayinitialgain.g",
                "testdelay.k",
                "testBPdinitialgain.g",
                "testBPcal.b",
            ],
            "BPGainTables": bp_results["bp_gaintables"],
            "AllCalTables": AllCalTables,
            "testBPdcals_flagged_fractions": {
                "delay": delay_results["flagged_fraction"],
                "gain": gain_results["flagged_fraction"],
                "bandpass": bp_results["flagged_fraction"],
            },
        })

        task_logprint(f"QA2_delay: {QA2_delay}")
        task_logprint(f"QA2_gain: {QA2_gain}")
        task_logprint(f"QA2_BP: {QA2_BP}")
        task_logprint(f"Overall QA2 score: {format_qa_status(QA2_testBPdcals)}")

    except Exception as e:
        task_logprint(f"Error in test bandpass and delay calibration: {e}")
        pipeline_context.update({
            "QA2_testBPdcals": "Fail",
            "QA2_delay": "Fail",
            "QA2_gain": "Fail",
            "QA2_BP": "Fail",
            "error_message": str(e),
        })

    time_list = runtiming("testBPdcals", "end")
    pipeline_context["time_list"] = time_list

    task_logprint("*** Finished test bandpass and delay calibration ***")

    return pipeline_context


# Backward compatibility alias
EVLA_pipe_testBPdcals = testbpdcals
