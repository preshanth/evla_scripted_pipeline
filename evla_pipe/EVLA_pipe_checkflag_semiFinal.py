# check_rfi_flagging_semifinal.py

from casatasks import flagdata
from .utils import logprint, runtiming

def task_logprint(msg):
    logprint(msg, logfileout="logs/checkflag_semifinal.log")

def check_rfi_flagging_semifinal(pipeline_context):
    """
    Check flagging of all calibrators using `rflag` mode of `flagdata`.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
    """
    task_logprint("*** Starting EVLA_pipe_checkflag_semiFinal.py (Refactored) ***")
    time_list = runtiming("checkflag_semiFinal", "start")
    QA2_checkflag_semiFinal = "Pass"

    ms_active = pipeline_context.get("msname")
    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")

    task_logprint("Checking RFI flagging of all calibrators")

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

    task_logprint(f"QA2 score: {QA2_checkflag_semiFinal}")
    task_logprint("Finished EVLA_pipe_checkflag_semiFinal.py")
    time_list = runtiming("checkflag_semiFinal", "end")

    return None # This task doesn't explicitly return a QA score in the original