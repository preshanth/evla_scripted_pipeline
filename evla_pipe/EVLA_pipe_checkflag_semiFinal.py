# check_rfi_flagging_semifinal.py

from casatasks import flagdata
from evla_pipe.utils import logprint, runtiming, format_qa_status

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

    task_logprint(f"QA2 score: {format_qa_status(QA2_checkflag_semiFinal)}")
    task_logprint("Finished EVLA_pipe_checkflag_semiFinal.py")
    time_list = runtiming("checkflag_semiFinal", "end")

    return None # This task doesn't explicitly return a QA score in the original

def EVLA_pipe_checkflag_semiFinal(pipeline_context):
    """
    Main entry point for EVLA_pipe_checkflag_semiFinal pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    
    task_logprint("*** Starting EVLA_pipe_checkflag_semiFinal.py ***")
    time_list = runtiming("checkflag_semiFinal", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        # Call the main function if it exists
        if "check_rfi_flagging_semifinal" in globals():
            QA2_score = check_rfi_flagging_semifinal(pipeline_context)
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_checkflag_semiFinal: {e}")
        QA2_score = "Fail"
    
    task_logprint(f"Finished EVLA_pipe_checkflag_semiFinal.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("checkflag_semiFinal", "end")
    
    
    # Update context and return
    pipeline_context["QA2_checkflag_semiFinal"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
