"""
Test gains module for EVLA pipeline.

This module determines the optimal short solution interval for gain calibrations
by testing various solution intervals and evaluating the fraction of flagged solutions.
"""

from typing import Dict, Any, Optional
from casatasks import rmtables
from casatools import table

from evla_pipe.utils import (
    logprint,
    runtiming,
    RefAntHeuristics,
    testgains,
    format_qa_status,
)

tb = table()


def task_logprint(msg: str, logfile: str = "logs/testgains.log") -> None:
    """
    Centralized logging for test gains operations.

    Parameters
    ----------
    msg : str
        Message to log
    logfile : str, optional
        Path to log file, by default "logs/testgains.log"
    """
    logprint(msg, logfileout=logfile)


def determine_reference_antenna(
    pipeline_context: Dict[str, Any],
    ms_name: str = "calibrators.ms"
) -> str:
    """
    Determine reference antenna for gain calibrations.

    Uses geometry and flagging heuristics to select the best reference antenna(e).

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibrator field selection
    ms_name : str, optional
        Measurement set to analyze, by default "calibrators.ms"

    Returns
    -------
    str
        Comma-separated list of reference antenna names
    """
    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")

    task_logprint("\nFinding a reference antenna for gain calibrations\n")

    findrefant = RefAntHeuristics(
        vis=ms_name,
        field=calibrator_field_select_string,
        geometry=True,
        flagging=True
    )
    RefAntOutput = findrefant.calculate()
    refAnt = ",".join(str(RefAntOutput[i]) for i in range(min(4, len(RefAntOutput))))

    task_logprint(f"The pipeline will use antenna(s) {refAnt} as the reference")

    return refAnt


def test_solution_interval(
    ms_name: str,
    scan_select: str,
    solint: str,
    refant: str,
    min_bl: int,
    combtime: str = ""
) -> Dict[str, Any]:
    """
    Test a specific solution interval and return flagging statistics.

    Parameters
    ----------
    ms_name : str
        Measurement set name
    scan_select : str
        Scan selection string
    solint : str
        Solution interval (e.g., "30s", "int", "inf")
    refant : str
        Reference antenna string
    min_bl : int
        Minimum baselines per antenna
    combtime : str, optional
        Combine time parameter, by default ""

    Returns
    -------
    dict
        Dictionary containing flagging statistics with keys:
        - fraction: overall fraction flagged
        - antmedian_fraction: median fraction flagged per antenna
        - total: total number of solutions
    """
    rmtables("testgaincal.g")

    flaggedSolnResult = testgains(
        ms_name,
        "testgaincal.g",
        "",  # spw selection (empty for all)
        scan_select,
        solint,
        refant,
        min_bl,
        combtime,
    )

    return {
        "fraction": flaggedSolnResult["all"]["fraction"],
        "antmedian_fraction": flaggedSolnResult["antmedian"]["fraction"],
        "total": flaggedSolnResult["all"]["total"]
    }


def determine_short_gain_solint(
    pipeline_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determine the optimal short solution interval for gain calibrators.

    Tests multiple solution intervals (1x, 3x, 10x integration time, and scan-level)
    and selects the shortest interval where the fraction of flagged solutions is
    below the threshold.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - int_time: Integration time in seconds
        - longsolint: Long solution interval (seconds or "inf")
        - flagging_threshold: Maximum acceptable fraction of flagged solutions
        - minBL_for_cal: Minimum baselines per antenna for calibration
        - shortsol1: Previously determined short solution interval
        - calibrator_scan_select_string: Scan selection for calibrators

    Returns
    -------
    dict
        Updated pipeline context with:
        - gain_solint1: Determined short solution interval string
        - refAnt: Reference antenna string
        - QA2_testgains: QA status

    Notes
    -----
    Sets QA2_testgains flag based on success/failure.
    """
    task_logprint("*** Starting determine_short_gain_solint ***")
    runtiming("testgains_solint", "start")

    # Extract parameters from context
    int_time = float(pipeline_context.get("int_time", 1.0))
    longsolint = pipeline_context.get("longsolint", "inf")
    flagging_threshold = float(pipeline_context.get("flagging_threshold", 0.5))
    minBL_for_cal = int(pipeline_context.get("minBL_for_cal", 3))
    shortsol1 = pipeline_context.get("shortsol1", "int")
    calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")

    # Convert longsolint to float if it's not "inf"
    longsolint_value = float(longsolint) if longsolint != "inf" else longsolint

    try:
        # Determine reference antenna
        refAnt = determine_reference_antenna(pipeline_context)
        pipeline_context["refAnt"] = refAnt

        task_logprint("Doing test gain calibration to determine short solint")

        # Test solution intervals: 1x, 3x, 10x integration time, then scan-level
        time_factors = [
            (1.0, False),   # 1x int_time
            (3.0, False),   # 3x int_time
            (10.0, False),  # 10x int_time
            ("inf", True)   # scan-level
        ]

        shortsol2 = None

        for time_factor, is_scan_level in time_factors:
            if is_scan_level:
                soltime = longsolint_value
                solint = "inf"
                combtime = ""
            else:
                soltime = time_factor * int_time
                solint = f"{soltime}s"
                combtime = "scan"

            task_logprint(f"\nTesting solint = {solint}")

            stats = test_solution_interval(
                ms_name="calibrators.ms",
                scan_select=calibrator_scan_select_string,
                solint=solint,
                refant=refAnt,
                min_bl=minBL_for_cal,
                combtime=combtime
            )

            frac_flagged = stats["fraction"]
            frac_flagged_med = stats["antmedian_fraction"]
            frac_flagged_tot = stats["total"]

            task_logprint(f"  Fraction of flagged solutions = {frac_flagged:.4f}")
            task_logprint(f"  Median fraction per antenna = {frac_flagged_med:.4f}")

            # Determine effective fraction for threshold comparison
            if frac_flagged_tot > 0:
                fracFlaggedSolns = frac_flagged_med
            else:
                fracFlaggedSolns = 1.0

            # Check if this interval meets the threshold
            if fracFlaggedSolns < flagging_threshold:
                task_logprint(f"  ✓ Solution interval {solint} meets threshold")
                shortsol2 = soltime
                break
            else:
                task_logprint(f"  ✗ Solution interval {solint} exceeds threshold")

        # Determine final short solution interval
        # Convert shortsol1 to numeric if it's "int"
        if isinstance(shortsol1, str) and shortsol1 == "int":
            shortsol1_value = int_time
        else:
            shortsol1_value = float(shortsol1)

        if shortsol2 is not None:
            if isinstance(shortsol2, str) and shortsol2 == "inf":
                # If scan-level was selected, keep it as "inf"
                gain_solint1 = "inf"
            else:
                # Take the maximum of shortsol1 and shortsol2
                final_soltime = max(shortsol1_value, shortsol2)
                gain_solint1 = f"{final_soltime}s"
        else:
            # No interval met threshold, use shortsol1
            gain_solint1 = f"{shortsol1_value}s"

        task_logprint(f"\nFinal short solution interval: {gain_solint1}")

        pipeline_context["gain_solint1"] = gain_solint1
        pipeline_context["refant"] = refAnt
        pipeline_context["QA2_testgains"] = "Pass"

    except Exception as e:
        task_logprint(f"Error determining short gain solint: {e}")
        pipeline_context["QA2_testgains"] = "Fail"
        pipeline_context["error_message"] = str(e)
        # Set default values on failure
        pipeline_context["gain_solint1"] = "int"
        pipeline_context["refant"] = ""

    runtiming("testgains_solint", "end")
    return pipeline_context


def testgains(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for test gains pipeline step.

    Determines the optimal short solution interval for gain calibrations by
    testing various intervals and selecting the shortest one that maintains
    acceptable flagging levels.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state.
        Required keys:
        - int_time: Integration time in seconds
        - longsolint: Long solution interval
        - flagging_threshold: Maximum fraction of flagged solutions
        - minBL_for_cal: Minimum baselines per antenna
        - shortsol1: Initial short solution interval
        - calibrator_scan_select_string: Scan selection

    Returns
    -------
    dict
        Updated pipeline context with:
        - gain_solint1: Determined solution interval
        - refAnt: Reference antenna string
        - QA2_testgains: QA status ("Pass" or "Fail")
        - time_list: Timing information

    Notes
    -----
    This function replaces the procedural EVLA_pipe_testgains.py script.
    It follows the modular, function-based approach with proper error handling
    and context management.
    """
    task_logprint("*** Starting EVLA_pipe_testgains ***")
    time_list = runtiming("testgains", "start")

    try:
        # Call the main processing function
        pipeline_context = determine_short_gain_solint(pipeline_context)

        qa_status = pipeline_context.get("QA2_testgains", "Fail")
        task_logprint(f"\nQA2 score: {format_qa_status(qa_status)}")

    except Exception as e:
        task_logprint(f"Error in testgains: {e}")
        pipeline_context["QA2_testgains"] = "Fail"
        pipeline_context["error_message"] = str(e)

    time_list = runtiming("testgains", "end")
    pipeline_context["time_list"] = time_list

    task_logprint("*** Finished EVLA_pipe_testgains ***")

    return pipeline_context


# Alias for backward compatibility
EVLA_pipe_testgains = testgains
