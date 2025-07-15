# priorcals.py (Calibration part)

import os
from casatasks import gencal
from evla_pipe.utils import (
    runtiming,
    logprint,
    correct_ant_posns,
    get_caltable_path,
    format_qa_status,
)

def task_logprint(msg):
    logprint(msg, logfileout="logs/priorcals.log")

def generate_prior_calibrations(pipeline_context):
    """
    Calculates deterministic prior calibration steps.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.

    Returns:
        dict: Dictionary containing generated calibration table names and timing info.
    """
    task_logprint("*** Starting prior calibration steps ***")
    time_list = runtiming("priorcals_cal", "start")
    priorcals = []
    ms_active = pipeline_context.get("msname")
    all_spw = pipeline_context.get("all_spw", "")
    tau = pipeline_context.get("tau", [])  # tau should already be a float vector from msmd
    startdate = pipeline_context.get("startdate", 0.0)

    # Table for elevation gain curves
    gain_curves_table = str(get_caltable_path("gain_curves.g", "prior"))
    task_logprint(f"DEBUG: About to run gencal for gain curves")
    task_logprint(f"DEBUG: gain_curves_table = {gain_curves_table}, type = {type(gain_curves_table)}")
    task_logprint(f"DEBUG: ms_active = {ms_active}, type = {type(ms_active)}")
    try:
        gencal(
            vis=ms_active,
            caltable=gain_curves_table,
            caltype="gc",
            spw="",
            antenna="",
            pol="",
        )
        priorcals.append(gain_curves_table)
        task_logprint(f"Generated {gain_curves_table}")
    except Exception as e:
        task_logprint(f"ERROR in gain curves gencal: {e}")
        raise

    # Table for atmospheric opacities
    opacities_table = str(get_caltable_path("opacities.g", "prior"))
    task_logprint(f"DEBUG: About to run gencal for opacities")
    task_logprint(f"DEBUG: opacities_table = {opacities_table}, type = {type(opacities_table)}")
    task_logprint(f"DEBUG: all_spw = {all_spw}, type = {type(all_spw)}")
    task_logprint(f"DEBUG: tau = {tau}, type = {type(tau)}")
    try:
        gencal(
            vis=ms_active,
            caltable=opacities_table,
            caltype="opac",
            spw=all_spw,
            antenna="",
            pol="",
            parameter=tau,
        )
        priorcals.append(opacities_table)
        task_logprint(f"Generated {opacities_table}")
    except Exception as e:
        task_logprint(f"ERROR in opacities gencal: {e}")
        raise

    # Apply switched power calibration (when commissioned); for now, just
    # requantizer gains (needs casa4.1!), and only for data with sensible switched
    # power tables (Feb 24, 2011)
    feb_24_2011 = 55616.6  # mjd
    if startdate >= feb_24_2011:
        requantizer_table = str(get_caltable_path("requantizergains.g", "prior"))
        gencal(
            vis=ms_active,
            caltable=requantizer_table,
            caltype="rq",
            spw="",
            antenna="",
            pol="",
        )
        priorcals.append(requantizer_table)
        task_logprint(f"Generated {requantizer_table}")
    else:
        task_logprint("Skipping requantizer gains (startdate before Feb 24, 2011)")

    # Correct for antenna position errors, if known.
    task_logprint("DEBUG: Starting antenna position corrections")
    try:
        antpos_table = str(get_caltable_path("antposcal.p", "prior"))
        task_logprint(f"DEBUG: About to run gencal for antenna positions")
        task_logprint(f"DEBUG: antpos_table = {antpos_table}")
        gencal(
            vis=ms_active,
            caltable=antpos_table,
            caltype="antpos",
            spw="",
            antenna="",
            pol="",
            parameter=[],
        )
        task_logprint(f"DEBUG: gencal completed, checking if {antpos_table} exists")
        if os.path.exists(antpos_table):
            priorcals.append(antpos_table)
            task_logprint("DEBUG: About to call correct_ant_posns()")
            antenna_offsets = correct_ant_posns(ms_active)
            task_logprint("DEBUG: correct_ant_posns() completed")
            task_logprint("Correcting for known antenna position errors")
            task_logprint(str(antenna_offsets))
        else:
            task_logprint("No antenna position corrections found/needed")
    except Exception as e:
        task_logprint(f"No antenna position corrections found/needed: {e}")
        task_logprint(f"DEBUG: Exception in antenna position section: {type(e).__name__}: {e}")

    task_logprint("Finished prior calibration steps")
    time_list = runtiming("priorcals_cal", "end")
    
    # Save calibration tables to context for resume capability
    calibration_results = {
        "priorcals": priorcals,
        "priorcals_tables": priorcals.copy(),  # List of actual files created
        "time_list": time_list
    }
    
    return calibration_results

def EVLA_pipe_priorcals(pipeline_context):
    """
    Main entry point for EVLA_pipe_priorcals pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_priorcals.py ***")
    time_list = runtiming("priorcals", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        # Call the main function if it exists
        if "generate_prior_calibrations" in globals():
            results = generate_prior_calibrations(pipeline_context)
            if isinstance(results, dict):
                # New format - results contain calibration tables
                pipeline_context["priorcals"] = results.get("priorcals", [])
                pipeline_context["priorcals_tables"] = results.get("priorcals_tables", [])
                QA2_score = "Pass"
            else:
                # Old format - just priorcals list
                pipeline_context["priorcals"] = results
                QA2_score = "Pass"
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_priorcals: {e}")
        QA2_score = "Fail"
        # Prior calibrations are critical - re-raise the exception to stop pipeline
        raise
    
    task_logprint(f"Finished EVLA_pipe_priorcals.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("priorcals", "end")
    
    # Update context and return
    pipeline_context["QA2_priorcals"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
