# determine_short_solint_gains.py

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

def task_logprint(msg, logfile="logs/testgains_solint.log"):
    logprint(msg, logfileout=logfile)

def determine_short_gain_solint(
    pipeline_context, int_time, longsolint, flagging_threshold, minBL_for_cal, shortsol1
):
    """
    Determine the short solution interval for gain calibrators.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
        int_time (float): Integration time.
        longsolint (float): Long solution interval in seconds.
        flagging_threshold (float): Threshold for flagging fraction of solutions.
        minBL_for_cal (int): Minimum baselines per antenna for calibration.
        shortsol1 (float): Short solution interval determined earlier.

    Returns:
        tuple: A tuple containing the new short gain solution interval string
               and the reference antenna string.
    """
    task_logprint("*** Starting determine_short_gain_solint.py ***", logfile="logs/testgains_solint.log")
    runtiming("testgains_solint", "start")

    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")
    calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")

    task_logprint("\nFinding a reference antenna for gain calibrations\n", logfile="logs/testgains_solint.log")

    findrefant = RefAntHeuristics(
        vis="calibrators.ms", field=calibrator_field_select_string, geometry=True, flagging=True
    )
    RefAntOutput = findrefant.calculate()
    refAnt = ",".join(str(RefAntOutput[i]) for i in range(min(4, len(RefAntOutput))))
    task_logprint(f"The pipeline will use antenna(s) {refAnt} as the reference", logfile="logs/testgains_solint.log")

    task_logprint("Doing test gain calibration to determine short solint", logfile="logs/testgains_solint.log")

    shortsol2 = None
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
            "",  # tst_gcal_spw was empty in original
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
            f"For solint = {solint}, fraction of flagged solutions = {frac_flagged}",
            logfile="logs/testgains_solint.log"
        )
        task_logprint(
            f"Median fraction of flagged solutions per antenna = {frac_flagged_med}",
            logfile="logs/testgains_solint.log"
        )
        if frac_flagged_tot > 0:
            fracFlaggedSolns1 = frac_flagged_med
        else:
            fracFlaggedSolns1 = 1.0
        if fracFlaggedSolns1 < flagging_threshold:
            task_logprint(f"Using short solution interval: {solint}", logfile="logs/testgains_solint.log")
            shortsol2 = soltime
            break

    new_gain_solint1 = f"{max(shortsol1, shortsol2) if shortsol2 is not None else shortsol1}s"
    task_logprint(f"Using short solint = {new_gain_solint1}", logfile="logs/testgains_solint.log")

    runtiming("testgains_solint", "end")
    return new_gain_solint1, refAnt

def EVLA_pipe_testgains(pipeline_context):
    """
    Main entry point for EVLA_pipe_testgains pipeline step.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_testgains.py ***", logfile="logs/testgains.log")
    time_list = runtiming("testgains", "start")

    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")

    try:
        # Call the main function if it exists
        if "determine_short_gain_solint" in globals():
            # Get required parameters from context
            int_time = float(pipeline_context.get("int_time", 1.0))
            longsolint = pipeline_context.get("longsolint", "inf")  # Keep as string for "inf" 
            flagging_threshold = float(pipeline_context.get("flagging_threshold", 0.5))
            minBL_for_cal = int(pipeline_context.get("minBL_for_cal", 3))
            shortsol1 = pipeline_context.get("shortsol1", "int")  # Keep as string for "int"
            QA2_score = determine_short_gain_solint(
                pipeline_context, int_time, longsolint, flagging_threshold, minBL_for_cal, shortsol1
            )
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization", logfile="logs/testgains.log")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_testgains: {e}", logfile="logs/testgains.log")
        QA2_score = "Fail"

    task_logprint(f"Finished EVLA_pipe_testgains.py", logfile="logs/testgains.log")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}", logfile="logs/testgains.log")
    time_list = runtiming("testgains", "end")

    # Update context and return
    pipeline_context["QA2_testgains"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context
