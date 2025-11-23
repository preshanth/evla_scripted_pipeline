"""
EVLA Pipeline - RFI Flagging Check Module

This module checks RFI flagging of bandpass and delay calibrators using the
`rflag` mode of `flagdata`. It operates on corrected data to identify and
flag additional RFI that may have been missed in initial flagging passes.

Replaces: EVLA_pipe_checkflag.py (legacy global scope version)
"""

from typing import Dict, Any, Optional
from casatasks import flagdata
from evla_pipe.utils import logprint, runtiming, format_qa_status
from evla_pipe.pipeline_steps import register_step


def task_logprint(msg: str, step: str = "checkflag") -> None:
    """
    Centralized logging for checkflag operations.

    Parameters
    ----------
    msg : str
        Message to log
    step : str, optional
        Step name for log file, by default "checkflag"
    """
    logprint(msg, logfileout=f"logs/{step}.log")


def check_rfi_flagging(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check and flag RFI on bandpass and delay calibrators.

    Uses the `rflag` algorithm on corrected data to identify outliers in
    time and frequency. Operates only on the specified calibrator fields
    and scan ranges to avoid over-flagging science targets.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Name of measurement set
        - bandpass_field_select_string : str
            Field selection for bandpass calibrator
        - delay_field_select_string : str
            Field selection for delay calibrator
        - corrstring : str, optional
            Correlation selection (default: "RR,LL")
        - testgainscans : str, optional
            Scan selection string for calibrators

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_checkflag : str
            QA status ("Pass" or "Fail")
        - time_list : list
            Updated timing information
        - error_message : str, optional
            Error description if QA failed

    Notes
    -----
    - Operates only on corrected data column
    - Uses time and frequency deviation scales of 4.0
    - Flags are applied immediately (not extended to adjacent channels/times)
    - Does not create flag backup (assumes prior backup exists)

    See Also
    --------
    casatasks.flagdata : CASA task for flagging operations
    """
    task_logprint("*** Starting RFI Flagging Check ***")
    time_list = runtiming("checkflag", "start")

    # Initialize QA status
    QA2_checkflag = "Pass"

    # Extract required parameters from context
    ms_active = pipeline_context.get("msname", "")
    bandpass_field_select_string = pipeline_context.get("bandpass_field_select_string", "")
    delay_field_select_string = pipeline_context.get("delay_field_select_string", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    testgainscans = pipeline_context.get("testgainscans", "")

    # Validate required inputs
    if not ms_active:
        error_msg = "No measurement set specified in pipeline_context['msname']"
        task_logprint(f"ERROR: {error_msg}")
        pipeline_context["QA2_checkflag"] = "Fail"
        pipeline_context["error_message"] = error_msg
        pipeline_context["time_list"] = runtiming("checkflag", "end")
        return pipeline_context

    # Build combined field selection string
    checkflagfields = bandpass_field_select_string
    if bandpass_field_select_string != delay_field_select_string:
        checkflagfields += "," + delay_field_select_string

    if not checkflagfields:
        task_logprint("WARNING: No calibrator fields specified, skipping RFI check")
        pipeline_context["QA2_checkflag"] = "Pass"
        pipeline_context["time_list"] = runtiming("checkflag", "end")
        return pipeline_context

    task_logprint(f"Checking RFI flagging for MS: {ms_active}")
    task_logprint(f"Calibrator fields: {checkflagfields}")
    task_logprint(f"Correlations: ABS_{corrstring}")
    if testgainscans:
        task_logprint(f"Scan selection: {testgainscans}")

    try:
        # Run rflag on bandpass and delay calibrators
        # Uses corrected data column to identify outliers after calibration
        task_logprint("Running flagdata with rflag mode on corrected data...")

        flagdata(
            vis=ms_active,
            mode="rflag",
            field=checkflagfields,
            correlation="ABS_" + corrstring,
            scan=testgainscans,
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
        QA2_checkflag = "Pass"

    except Exception as e:
        error_msg = f"Error during RFI flagging check: {str(e)}"
        task_logprint(f"ERROR: {error_msg}")
        QA2_checkflag = "Fail"
        pipeline_context["error_message"] = error_msg

    # Update context with results
    pipeline_context["QA2_checkflag"] = QA2_checkflag
    pipeline_context["time_list"] = runtiming("checkflag", "end")

    task_logprint(f"QA2 score: {format_qa_status(QA2_checkflag)}")
    task_logprint("*** Finished RFI Flagging Check ***")

    return pipeline_context


@register_step("EVLA_pipe_checkflag")
def EVLA_pipe_checkflag(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for EVLA checkflag pipeline step.

    This function serves as the primary interface for the RFI flagging check
    step in the EVLA pipeline. It delegates to `check_rfi_flagging` for the
    actual work.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state.
        See `check_rfi_flagging` for required keys.

    Returns
    -------
    dict
        Updated pipeline context with QA2_checkflag status and timing info

    Examples
    --------
    >>> context = {
    ...     "msname": "test.ms",
    ...     "bandpass_field_select_string": "0",
    ...     "delay_field_select_string": "0",
    ...     "corrstring": "RR,LL",
    ...     "testgainscans": "1,2,3"
    ... }
    >>> context = EVLA_pipe_checkflag(context)
    >>> print(context["QA2_checkflag"])
    Pass

    See Also
    --------
    check_rfi_flagging : Core RFI flagging logic
    """
    return check_rfi_flagging(pipeline_context)
