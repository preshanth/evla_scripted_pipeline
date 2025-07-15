"""
Calculate data weights based on the standard deviation within each spw using
`statwt`.
"""

from casatasks import statwt
from evla_pipe.utils import logprint, runtiming, format_qa_status

def task_logprint(msg):
    logprint(msg, logfileout="logs/statwt.log")

def EVLA_pipe_statwt(pipeline_context):
    """
    Main entry point for EVLA_pipe_statwt pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_statwt.py ***")
    time_list = runtiming("statwt", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        task_logprint("Calculating data weights per SpW using statwt.")
        
        # Run on all calibrators
        statwt(
            vis=ms_active,
            minsamp=2,
            intent="*CALIBRATE*",
            datacolumn="corrected",
        )
        
        # Run on all targets
        # set spw to exclude strong science spectral lines
        statwt(
            vis=ms_active,
            minsamp=2,
            intent="*TARGET*",
            datacolumn="corrected",
        )
        
        QA2_score = "Pass"
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_statwt: {e}")
        QA2_score = "Fail"
    
    task_logprint("Finished EVLA_pipe_statwt.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("statwt", "end")
    
    # Update context and return
    pipeline_context["QA2_statwt"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
