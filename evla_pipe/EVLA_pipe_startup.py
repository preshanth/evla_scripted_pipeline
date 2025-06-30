# EVLA_pipe_startup.py
import os
from .utils import runtiming, logprint
from . import pipeline_save  # We might reconsider this later

def pipeline_startup(pipeline_context):
    """
    Performs initial startup tasks for the EVLA pipeline, including
    getting the SDM name and other initial parameters.

    Args:
        pipeline_context (dict): A dictionary to store and share the pipeline's context.

    Returns:
        dict: Updated pipeline context with initial parameters.
    """
    task_logprint = lambda msg: logprint(msg, logfileout="logs/startup.log")
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

    if not os.path.isdir(msname):
        while not os.path.isdir(SDM_name) and not os.path.isdir(msname):
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

    # Other inputs:
    pipeline_context["scratch"] = pipeline_context.get("scratch", input("Create the real model column (y/[n]): ").lower() == "y")
    pipeline_context["do_hanning"] = pipeline_context.get("do_hanning", input("Hanning smooth the data (y/[n]): ").lower() not in ("", "n"))
    pipeline_context["do_pol"] = pipeline_context.get("do_pol", input("Perform polarization calibration? (y/[n]): ").lower() not in ("", "n"))

    pipeline_context["ms_active"] = pipeline_context.get("ms_active", msname)

    pipeline_context["projectCode"] = pipeline_context.get("projectCode", input("Enter project code (or 'Unknown'): ") or 'Unknown')
    pipeline_context["piName"] = pipeline_context.get("piName", input("Enter PI name (or 'Unknown'): ") or 'Unknown')
    pipeline_context["piGlobalId"] = pipeline_context.get("piGlobalId", input("Enter PI global ID (or 'Unknown'): ") or 'Unknown')
    pipeline_context["observeDateString"] = pipeline_context.get("observeDateString", input("Enter observe date string (or 'Unknown'): ") or 'Unknown')
    pipeline_context["pipelineDateString"] = pipeline_context.get("pipelineDateString", input("Enter pipeline date string (or 'Unknown'): ") or 'Unknown')

    task_logprint("Finished pipeline_startup")
    runtiming('startup', 'end')

    # pipeline_save() # We'll handle saving in the main orchestration

    return pipeline_context