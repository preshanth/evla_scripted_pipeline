# EVLA_pipe_checkflag.py (Refactored)

from casatasks import flagdata
from .utils import logprint, runtiming

def task_logprint(msg):
    logprint(msg, logfileout="logs/checkflag.log")

def check_rfi_flagging(pipeline_context):
    """
    Check flagging of bandpass and delay calibrators using `rflag` mode
    of `flagdata`.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
    """
    task_logprint("*** Starting EVLA_pipe_checkflag.py (Refactored) ***")
    time_list = runtiming("checkflag", "start")
    QA2_checkflag = "Pass"

    ms_active = pipeline_context.get("msname")
    bandpass_field_select_string = pipeline_context.get("bandpass_field_select_string", "")
    delay_field_select_string = pipeline_context.get("delay_field_select_string", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    testgainscans = pipeline_context.get("testgainscans", "")

    task_logprint("Checking RFI flagging of BP and Delay Calibrators")

    checkflagfields = bandpass_field_select_string
    if bandpass_field_select_string != delay_field_select_string:
        checkflagfields += "," + delay_field_select_string

    # Run only on the bandpass and delay calibrators - testgainscans
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

    task_logprint(f"QA2 score: {QA2_checkflag}")
    task_logprint("Finished EVLA_pipe_checkflag.py")
    time_list = runtiming("checkflag", "end")

    return None # This task doesn't explicitly return a QA score in the original