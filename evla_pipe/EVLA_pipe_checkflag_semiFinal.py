"""
Semi-final RFI flagging check for EVLA pipeline.

This module checks RFI flagging of all calibrators using the 'rflag' mode
of flagdata. This is run after semi-final calibration to identify and flag
remaining RFI.
"""

from typing import Any, Dict

from casatasks import flagdata

from evla_pipe.utils import format_qa_status, logprint, runtiming


def task_logprint(msg: str) -> None:
    """
    Log message to semi-final checkflag log file.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/checkflag_semifinal.log")


def checkflag_semifinal(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check RFI flagging of all calibrators using rflag mode.

    This function runs the rflag algorithm on all calibrator fields after
    semi-final calibration. It uses the corrected data column to identify
    remaining RFI that may not have been caught in earlier flagging rounds.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Measurement set name
        - calibrator_field_select_string : str
            Comma-separated list of calibrator field IDs/names
        - corrstring : str, optional
            Correlation string (default: "RR,LL")
        - calibrator_scan_select_string : str, optional
            Scan selection string for calibrators

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_checkflag_semiFinal : str
            QA score ("Pass" or "Fail")
        - time_list : list
            Updated timing information

    Notes
    -----
    - Uses the 'corrected' data column for flagging assessment
    - Applies flags with rflag algorithm parameters tuned for RFI detection
    - Sets combinescans=False to evaluate each scan independently
    - Uses time/frequency deviation scales of 4.0 for RFI detection

    Examples
    --------
    >>> context = {
    ...     "msname": "test.ms",
    ...     "calibrator_field_select_string": "0,1,2",
    ...     "corrstring": "RR,LL",
    ...     "calibrator_scan_select_string": "1~10"
    ... }
    >>> updated_context = checkflag_semifinal(context)
    >>> updated_context["QA2_checkflag_semiFinal"]
    'Pass'
    """
    task_logprint("*** Starting Semi-Final RFI Flagging Check ***")
    time_list = runtiming("checkflag_semiFinal", "start")

    # Initialize QA score
    QA2_checkflag_semiFinal = "Pass"

    # Extract parameters from context
    ms_active = pipeline_context.get("msname", "")
    calibrator_field_select_string = pipeline_context.get(
        "calibrator_field_select_string", ""
    )
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    calibrator_scan_select_string = pipeline_context.get(
        "calibrator_scan_select_string", ""
    )

    # Validate required parameters
    if not ms_active:
        error_msg = "No measurement set specified in context (msname)"
        task_logprint(f"ERROR: {error_msg}")
        pipeline_context["QA2_checkflag_semiFinal"] = "Fail"
        pipeline_context["error_message"] = error_msg
        pipeline_context["time_list"] = runtiming("checkflag_semiFinal", "end")
        return pipeline_context

    if not calibrator_field_select_string:
        error_msg = "No calibrator fields specified (calibrator_field_select_string)"
        task_logprint(f"ERROR: {error_msg}")
        pipeline_context["QA2_checkflag_semiFinal"] = "Fail"
        pipeline_context["error_message"] = error_msg
        pipeline_context["time_list"] = runtiming("checkflag_semiFinal", "end")
        return pipeline_context

    task_logprint(f"Measurement set: {ms_active}")
    task_logprint(f"Calibrator fields: {calibrator_field_select_string}")
    task_logprint(f"Correlations: {corrstring}")
    if calibrator_scan_select_string:
        task_logprint(f"Calibrator scans: {calibrator_scan_select_string}")

    try:
        task_logprint("Running rflag on all calibrators (corrected data)")
        task_logprint("  Mode: rflag")
        task_logprint("  Data column: corrected")
        task_logprint("  Time dev scale: 4.0")
        task_logprint("  Freq dev scale: 4.0")
        task_logprint("  Window size: 3")
        task_logprint("  Combine scans: False (evaluate each scan independently)")

        # Run rflag on all calibrators
        flagdata(
            vis=ms_active,
            mode="rflag",
            field=calibrator_field_select_string,
            correlation="ABS_" + corrstring,
            scan=calibrator_scan_select_string,
            ntime="scan",
            combinescans=False,
            datacolumn="corrected",
            winsize=3,
            timedevscale=4.0,
            freqdevscale=4.0,
            extendflags=False,
            action="apply",
            display="",
            flagbackup=False,
            savepars=True,
        )

        task_logprint("RFI flagging check completed successfully")
        QA2_checkflag_semiFinal = "Pass"

    except Exception as e:
        error_msg = f"Error during semi-final RFI flagging check: {str(e)}"
        task_logprint(f"ERROR: {error_msg}")
        QA2_checkflag_semiFinal = "Fail"
        pipeline_context["error_message"] = error_msg

    # Update timing
    time_list = runtiming("checkflag_semiFinal", "end")

    # Log final status
    task_logprint(f"QA2 score: {format_qa_status(QA2_checkflag_semiFinal)}")
    task_logprint("*** Finished Semi-Final RFI Flagging Check ***")

    # Update context with results
    pipeline_context["QA2_checkflag_semiFinal"] = QA2_checkflag_semiFinal
    pipeline_context["time_list"] = time_list

    return pipeline_context


# Legacy compatibility - allows import as EVLA_pipe_checkflag_semiFinal
EVLA_pipe_checkflag_semiFinal = checkflag_semifinal
