"""
Apply all calibrations to the measurement set.

This module applies all calibration tables including intensity and 
polarization calibrations if available.
"""

import copy
import os
from casatasks import flagdata, applycal
from evla_pipe.utils import logprint, runtiming, get_log_path, get_caltable_path


def task_logprint(msg):
    logprint(msg, logfileout=str(get_log_path("applycals.log")))


def EVLA_pipe_applycals(pipeline_context):
    """
    Apply all calibrations to the measurement set.
    
    This function applies all available calibration tables including:
    - Prior calibrations (delay, bandpass)
    - Gain calibrations (amplitude, phase)
    - Polarization calibrations (Xf, Df) if available
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibration tables and MS information
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_applycals.py ***")
    time_list = runtiming("applycals", "start")
    QA2_applycals = "Pass"
    
    # Get context variables
    ms_active = pipeline_context.get("msname")
    priorcals = pipeline_context.get("priorcals", [])
    do_pol = pipeline_context.get("do_pol", False)
    
    if not ms_active:
        task_logprint("ERROR: No measurement set specified")
        QA2_applycals = "Fail"
        return pipeline_context
    
    # Check initial flags
    task_logprint("Checking flags before applying calibrations")
    myinitialflags = flagdata(
        vis=ms_active,
        mode="summary",
        spwchan=True,
        spwcorr=True,
        basecnt=True,
        action="calculate",
        savepars=False,
    )
    task_logprint("Finished flags summary before final applycal.")
    
    # Build complete calibration table list
    FinalGainTables = copy.copy(priorcals)
    
    # Add standard calibration tables with proper directory structure
    # These tables might be in different directories or have different names
    # depending on the pipeline step that created them
    
    # Map expected table names to their actual locations
    table_mapping = {
        "finaldelay.k": ["delay.k", str(get_caltable_path("delay.k", "intermediate")), str(get_caltable_path("delay.k", "final"))],
        "finalBPcal.b": ["BPcal.b", str(get_caltable_path("BPcal.b", "intermediate")), str(get_caltable_path("BPcal.b", "final"))],
        "averagephasegain.g": ["averagephasegain.g", str(get_caltable_path("averagephasegain.g", "final"))],
        "finalampgaincal.g": ["finalampgaincal.g", str(get_caltable_path("finalampgaincal.g", "final"))],
        "finalphasegaincal.g": ["finalphasegaincal.g", str(get_caltable_path("finalphasegaincal.g", "final"))]
    }
    
    for expected_table, possible_paths in table_mapping.items():
        table_path = None
        # Try to find the table in possible locations
        for path in possible_paths:
            if os.path.exists(path):
                table_path = path
                task_logprint(f"Found {expected_table} at {path}")
                break
        
        if table_path:
            FinalGainTables.append(table_path)
        else:
            task_logprint(f"WARNING: Could not find calibration table {expected_table} in any expected location")
        
    # Add polarization calibration tables if available
    if do_pol and pipeline_context.get("polarization_calibrated", False):
        pol_tables = pipeline_context.get("pol_cal_tables", [])
        if pol_tables:
            task_logprint(f"Adding polarization calibration tables: {pol_tables}")
            FinalGainTables.extend(pol_tables)
        else:
            # Check for individual polarization tables
            if "kcross_cal_table" in pipeline_context:
                FinalGainTables.append(pipeline_context["kcross_cal_table"])
                task_logprint(f"Added Xf table: {pipeline_context['kcross_cal_table']}")
                
            if "dterms_cal_table" in pipeline_context:
                FinalGainTables.append(pipeline_context["dterms_cal_table"])
                task_logprint(f"Added Df table: {pipeline_context['dterms_cal_table']}")
    
    ntables = len(FinalGainTables)
    task_logprint(f"Applying {ntables} calibration tables: {FinalGainTables}")
    
    try:
        # Apply all calibrations
        applycal(
            vis=ms_active,
            field="",
            spw="",
            intent="",
            selectdata=False,
            gaintable=FinalGainTables,
            gainfield=[""] * ntables,
            interp=[""] * ntables,
            spwmap=[[]] * ntables,
            parang=True if do_pol else False,  # Enable parallactic angle correction for polarization
            calwt=[False] * ntables,
            applymode="calflagstrict",
            flagbackup=True,
        )
        
        task_logprint("Successfully applied all calibrations")
        
    except Exception as e:
        task_logprint(f"ERROR applying calibrations: {e}")
        QA2_applycals = "Fail"
        pipeline_context["applycals_error"] = str(e)
    
    # Check flags after calibration
    task_logprint("Checking flags after applying calibrations")
    myfinalflags = flagdata(
        vis=ms_active,
        mode="summary",
        spwchan=True,
        spwcorr=True,
        basecnt=True,
        action="calculate",
        savepars=False,
    )
    task_logprint("Finished flags summary after final applycal.")
    
    # Store calibration information in context
    pipeline_context["final_gain_tables"] = FinalGainTables
    pipeline_context["applycals_completed"] = True
    
    # TODO: Add calibrated data quality checks
    # - Plot "corrected" datacolumn for calibrators in plotms
    # - Plot "corrected" datacolumn for targets
    # - Amp vs. freq, amp vs. time plots
    
        # Import colored output function
    from evla_pipe.utils import format_qa_status
    task_logprint(f"QA2 score: {format_qa_status(QA2_applycals)}")
    task_logprint("Finished EVLA_pipe_applycals.py")
    time_list = runtiming("applycals", "end")
    
    return pipeline_context