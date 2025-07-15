# EVLA_pipe_hanning.py
import os
import shutil
from glob import glob
from casatasks import hanningsmooth
from evla_pipe.utils import runtiming, logprint

def task_logprint(msg):
    logprint(msg, logfileout="logs/hanning.log"), format_qa_status

def apply_hanning_smooth(pipeline_context):
    """
    Applies Hanning smoothing to the visibility data if the do_hanning flag is set.

    Args:
        pipeline_context (dict): A dictionary containing the pipeline's context,
                                 including variables like msname and do_hanning.

    Returns:
        dict: Updated pipeline context. Returns "Fail" if critical parameters are missing.
    """
    msname = pipeline_context.get("msname")
    do_hanning = pipeline_context.get("do_hanning")

    if not msname:
        logprint("Error: Missing msname in pipeline context for apply_hanning_smooth.", logfileout="logs/hanning.log")
        return "Fail"

    task_logprint = lambda msg: logprint(msg, logfileout="logs/hanning.log")
    task_logprint("*** Starting apply_hanning_smooth ***")
    time_list = runtiming('hanning', 'start')
    QA2_hanning = "Pass"

    if do_hanning:
        task_logprint("Hanning smoothing the data")
        try:
            hanningsmooth(
                vis=msname,
                datacolumn="data",
                outputvis="temphanning.ms",
            )

            task_logprint("Copying xml files to the output ms")
            for filen in glob(f"{msname}/*.xml"):
                shutil.copy2(filen , "temphanning.ms/")
            task_logprint(f"Removing original VIS {msname}")
            shutil.rmtree(msname)

            task_logprint(f"Renaming temphanning.ms to {msname}")
            os.rename("temphanning.ms", msname)
            pipeline_context["msname"] = msname # Update msname in context
        except Exception as e:
            task_logprint(f"Error during Hanning smoothing: {e}")
            QA2_hanning = "Fail"
    else:
        task_logprint("NOT Hanning smoothing the data")

    task_logprint("Finished apply_hanning_smooth")
    task_logprint(f"QA2 score: {format_qa_status(QA2_hanning)}")
    time_list = runtiming("hanning", "end")

    return pipeline_context

def EVLA_pipe_hanning(pipeline_context):
    """
    Main entry point for EVLA_pipe_hanning pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_hanning.py ***")
    time_list = runtiming("hanning", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        # Call the main function - it returns updated context
        updated_context = apply_hanning_smooth(pipeline_context)
        if updated_context == "Fail":
            QA2_score = "Fail"
        else:
            pipeline_context.update(updated_context)
            QA2_score = "Pass"
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_hanning: {e}")
        QA2_score = "Fail"
    
    task_logprint(f"Finished EVLA_pipe_hanning.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("hanning", "end")

    # Update context and return
    pipeline_context["QA2_hanning"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
