# EVLA_pipe_checkflag.py (Refactored)

from casatasks import flagdata
from evla_pipe.utils import logprint, runtiming, format_qa_status

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

        # Import colored output function
    task_logprint(f"QA2 score: {format_qa_status(QA2_checkflag)}")
    task_logprint("Finished EVLA_pipe_checkflag.py")
    time_list = runtiming("checkflag", "end")

    return None # This task doesn't explicitly return a QA score in the original

def EVLA_pipe_checkflag(pipeline_context):
    """
    Main entry point for EVLA_pipe_checkflag pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    
    task_logprint("*** Starting EVLA_pipe_checkflag.py ***")
    time_list = runtiming("checkflag", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        # Call the main function if it exists
        if "check_rfi_flagging" in globals():
            QA2_score = check_rfi_flagging(pipeline_context)
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_checkflag: {e}")
        QA2_score = "Fail"
    
    task_logprint(f"Finished EVLA_pipe_checkflag.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("checkflag", "end")
    
    # Update context and return
    pipeline_context["QA2_checkflag"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
