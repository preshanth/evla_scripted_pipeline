# EVLA_pipe_startup.py
import os
from pathlib import Path
from datetime import datetime
from evla_pipe.utils import (
from evla_pipe.pipeline_steps
from typing import Dict, Any import register_step
    runtiming,
    logprint,
    get_log_path,
    path_exists,
    format_qa_status,
)

def task_logprint(msg):
    logprint(msg, logfileout="logs/startup.log")

def pipeline_startup(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Performs initial startup tasks for the EVLA pipeline, including
    getting the SDM name and other initial parameters.

    Args:
        pipeline_context (dict): A dictionary to store and share the pipeline's context.

    Returns:
        dict: Updated pipeline context with initial parameters.
    """
    task_logprint = lambda msg: logprint(msg, logfileout=str(get_log_path("startup.log")))
    task_logprint("*** Starting pipeline_startup ***")
    runtiming('startup', 'start')

    task_logprint(f"Running from path: {os.getcwd()}")

    # File names
    SDM_name_already_defined = "SDM_name" in pipeline_context
    if not SDM_name_already_defined:
        SDM_name = input("Enter SDM file name: ")
        if SDM_name == "":
            raise RuntimeError("SDM name must be given.")
        pipeline_context["SDM_name"] = SDM_name
    else:
        SDM_name = pipeline_context["SDM_name"]

    # Trap for '.ms', just in case, also for directory slash if present:
    SDM_name = SDM_name.rstrip('/')
    if SDM_name.endswith('.ms'):
        SDM_name = SDM_name[:-3]
    msname = f"{SDM_name}.ms"

    if SDM_name_already_defined:
        msname = msname.replace('rawdata', 'working')

    if not path_exists(msname):
        while not path_exists(SDM_name) and not path_exists(msname):
            print(f"{SDM_name} is not a valid SDM directory")
            SDM_name = input("Re-enter a valid SDM directory (without '.ms'): ")
            SDM_name = SDM_name.rstrip('/')
            if SDM_name.endswith('.ms'):
                SDM_name = SDM_name[:-3]
            msname = f"{SDM_name}.ms"
        pipeline_context["SDM_name"] = SDM_name # Update SDM name if re-entered

    pipeline_context["msname"] = msname
    mshsmooth = f"{SDM_name}.hsmooth.ms"
    if SDM_name_already_defined:
        mshsmooth = mshsmooth.replace('rawdata', 'working')
    pipeline_context["mshsmooth"] = mshsmooth
    ms_spave = f"{SDM_name}.spave.ms"
    if SDM_name_already_defined:
        ms_spave = ms_spave.replace('rawdata', 'working')
    pipeline_context["ms_spave"] = ms_spave

    task_logprint(f"SDM used is: {SDM_name}")

    # Pipeline options - use flags instead of prompting:
    pipeline_context["scratch"] = pipeline_context.get("scratch", False)  # Always False, scratch columns not used
    pipeline_context["do_hanning"] = pipeline_context.get("do_hanning", False)  # Default: no Hanning smoothing (use --hanning flag)
    pipeline_context["do_pol"] = pipeline_context.get("do_pol", False)  # Default: no polarization calibration (use --polarization flag)

    pipeline_context["ms_active"] = pipeline_context.get("ms_active", msname)

    # Set default metadata values for weblog (these don't affect calibration)
    pipeline_context["projectCode"] = pipeline_context.get("projectCode", "Unknown")
    pipeline_context["piName"] = pipeline_context.get("piName", "Unknown")
    pipeline_context["piGlobalId"] = pipeline_context.get("piGlobalId", "Unknown")
    pipeline_context["observeDateString"] = pipeline_context.get("observeDateString", "Unknown")
    pipeline_context["pipelineDateString"] = pipeline_context.get("pipelineDateString", datetime.now().strftime('%Y-%m-%d'))
    
    # Log the configuration
    task_logprint(f"Pipeline configuration:")
    task_logprint(f"  Create model column: {pipeline_context['scratch']}")
    task_logprint(f"  Hanning smoothing: {pipeline_context['do_hanning']}")
    task_logprint(f"  Polarization calibration: {pipeline_context['do_pol']}")

    task_logprint("Finished pipeline_startup")
    runtiming('startup', 'end')

    return pipeline_context

@register_step("EVLA_pipe_startup")
def EVLA_pipe_startup(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for EVLA_pipe_startup pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_startup.py ***")
    time_list = runtiming("startup", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        # Call the main function if it exists
        if "pipeline_startup" in globals():
            QA2_score = pipeline_startup(pipeline_context)
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_startup: {e}")
        QA2_score = "Fail"
    
    task_logprint(f"Finished EVLA_pipe_startup.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("startup", "end")
    
    # Update context and return
    pipeline_context["QA2_startup"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
