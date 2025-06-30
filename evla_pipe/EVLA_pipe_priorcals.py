# priorcals.py (Calibration part)

import os
from casatasks import gencal
from .utils import runtiming, logprint, correct_ant_posns

def task_logprint(msg):
    logprint(msg, logfileout="logs/priorcals.log")

def generate_prior_calibrations(pipeline_context):
    """
    Calculates deterministic prior calibration steps.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.

    Returns:
        list: A list of generated calibration table names.
    """
    task_logprint("*** Starting prior calibration steps ***")
    time_list = runtiming("priorcals_cal", "start")
    priorcals = []
    ms_active = pipeline_context.get("msname")
    all_spw = pipeline_context.get("all_spw", "")
    tau = pipeline_context.get("tau", 0.0)
    startdate = pipeline_context.get("startdate", 0.0)

    # Table for elevation gain curves
    gencal(
        vis=ms_active,
        caltable="gain_curves.g",
        caltype="gc",
        spw="",
        antenna="",
        pol="",
        parameter=[],
    )
    priorcals.append("gain_curves.g")
    task_logprint("Generated gain_curves.g")

    # Table for atmospheric opacities
    gencal(
        vis=ms_active,
        caltable="opacities.g",
        caltype="opac",
        spw=all_spw,
        antenna="",
        pol="",
        parameter=[tau],
    )
    priorcals.append("opacities.g")
    task_logprint("Generated opacities.g")

    # Apply switched power calibration (when commissioned); for now, just
    # requantizer gains (needs casa4.1!), and only for data with sensible switched
    # power tables (Feb 24, 2011)
    feb_24_2011 = 55616.6  # mjd
    if startdate >= feb_24_2011:
        gencal(
            vis=ms_active,
            caltable="requantizergains.g",
            caltype="rq",
            spw="",
            antenna="",
            pol="",
            parameter=[],
        )
        priorcals.append("requantizergains.g")
        task_logprint("Generated requantizergains.g")
    else:
        task_logprint("Skipping requantizer gains (startdate before Feb 24, 2011)")

    # Correct for antenna position errors, if known.
    try:
        gencal(
            vis=ms_active,
            caltable="antposcal.p",
            caltype="antpos",
            spw="",
            antenna="",
            pol="",
            parameter=[],
        )
        if os.path.exists("antposcal.p"):
            priorcals.append("antposcal.p")
            antenna_offsets = correct_ant_posns(ms_active)
            task_logprint("Correcting for known antenna position errors")
            task_logprint(str(antenna_offsets))
        else:
            task_logprint("No antenna position corrections found/needed")
    except Exception as e:
        task_logprint(f"No antenna position corrections found/needed: {e}")

    task_logprint("Finished prior calibration steps")
    time_list = runtiming("priorcals_cal", "end")
    return priorcals