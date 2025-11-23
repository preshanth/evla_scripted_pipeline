"""
Apply all calibrations to the measurement set.

This module applies all calibration tables including intensity and
polarization calibrations if available.
"""

import copy
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from casatasks import flagdata, applycal
from evla_pipe.utils import logprint, runtiming, get_log_path, get_caltable_path
from evla_pipe.pipeline_steps import register_step


def task_logprint(msg: str) -> None:
    """
    Log message to applycals-specific log file.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout=str(get_log_path("applycals.log")))


def _find_calibration_table(expected_table: str, possible_paths: List[str]) -> Optional[str]:
    """
    Find a calibration table in possible locations.

    Parameters
    ----------
    expected_table : str
        Name of the expected calibration table
    possible_paths : list of str
        List of possible paths to check

    Returns
    -------
    str or None
        Path to the found table, or None if not found
    """
    for path in possible_paths:
        if os.path.exists(path):
            task_logprint(f"Found {expected_table} at {path}")
            return path

    task_logprint(f"WARNING: Could not find calibration table {expected_table} in any expected location")
    return None


def _build_calibration_table_list(pipeline_context: Dict[str, Any]) -> List[str]:
    """
    Build the complete list of calibration tables to apply.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibration information

    Returns
    -------
    list of str
        List of calibration table paths
    """
    priorcals = pipeline_context.get("priorcals", [])
    do_pol = pipeline_context.get("do_pol", False)

    # Start with prior calibrations
    gain_tables = copy.copy(priorcals)

    # Map expected table names to their actual locations
    table_mapping = {
        "finaldelay.k": [
            "delay.k",
            str(get_caltable_path("delay.k", "intermediate")),
            str(get_caltable_path("delay.k", "final"))
        ],
        "finalBPcal.b": [
            "BPcal.b",
            str(get_caltable_path("BPcal.b", "intermediate")),
            str(get_caltable_path("BPcal.b", "final"))
        ],
        "averagephasegain.g": [
            "averagephasegain.g",
            str(get_caltable_path("averagephasegain.g", "final"))
        ],
        "finalampgaincal.g": [
            "finalampgaincal.g",
            str(get_caltable_path("finalampgaincal.g", "final"))
        ],
        "finalphasegaincal.g": [
            "finalphasegaincal.g",
            str(get_caltable_path("finalphasegaincal.g", "final"))
        ]
    }

    # Find and add standard calibration tables
    for expected_table, possible_paths in table_mapping.items():
        table_path = _find_calibration_table(expected_table, possible_paths)
        if table_path:
            gain_tables.append(table_path)

    # Add polarization calibration tables if available
    if do_pol and pipeline_context.get("polarization_calibrated", False):
        pol_tables = pipeline_context.get("pol_cal_tables", [])
        if pol_tables:
            task_logprint(f"Adding polarization calibration tables: {pol_tables}")
            gain_tables.extend(pol_tables)
        else:
            # Check for individual polarization tables
            if "kcross_cal_table" in pipeline_context:
                gain_tables.append(pipeline_context["kcross_cal_table"])
                task_logprint(f"Added Xf table: {pipeline_context['kcross_cal_table']}")

            if "dterms_cal_table" in pipeline_context:
                gain_tables.append(pipeline_context["dterms_cal_table"])
                task_logprint(f"Added Df table: {pipeline_context['dterms_cal_table']}")

    return gain_tables


def _check_flags(ms_active: str, stage: str) -> Dict[str, Any]:
    """
    Check flag statistics for the measurement set.

    Parameters
    ----------
    ms_active : str
        Path to measurement set
    stage : str
        Stage descriptor (e.g., 'before', 'after')

    Returns
    -------
    dict
        Flag statistics dictionary
    """
    task_logprint(f"Checking flags {stage} applying calibrations")

    flag_stats = flagdata(
        vis=ms_active,
        mode="summary",
        spwchan=True,
        spwcorr=True,
        basecnt=True,
        action="calculate",
        savepars=False,
    )

    task_logprint(f"Finished flags summary {stage} final applycal.")
    return flag_stats


def applycals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply all calibrations to the measurement set.

    This function applies all available calibration tables including:
    - Prior calibrations (delay, bandpass)
    - Gain calibrations (amplitude, phase)
    - Polarization calibrations (Xf, Df) if available

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Path to measurement set
        - priorcals : list of str, optional
            List of prior calibration tables
        - do_pol : bool, optional
            Whether polarization calibration was performed
        - polarization_calibrated : bool, optional
            Whether polarization calibration completed successfully
        - pol_cal_tables : list of str, optional
            Polarization calibration tables
        - kcross_cal_table : str, optional
            Cross-hand delay calibration table
        - dterms_cal_table : str, optional
            D-terms (leakage) calibration table

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_applycals : str
            Quality assessment result ('Pass' or 'Fail')
        - final_gain_tables : list of str
            List of applied calibration tables
        - applycals_completed : bool
            Whether calibration application completed
        - initial_flag_stats : dict
            Flag statistics before calibration
        - final_flag_stats : dict
            Flag statistics after calibration
        - applycals_error : str, optional
            Error message if application failed

    Notes
    -----
    - Sets QA2_applycals flag based on success/failure
    - Applies parallactic angle correction for polarization data
    - Uses calflagstrict mode to flag data with failed calibrations
    - Creates backup of flags before applying calibrations
    """
    task_logprint("*** Starting EVLA_pipe_applycals.py ***")
    time_list = runtiming("applycals", "start")

    # Initialize QA score
    QA2_applycals = "Pass"

    # Get context variables
    ms_active = pipeline_context.get("msname")
    do_pol = pipeline_context.get("do_pol", False)

    # Validate required inputs
    if not ms_active:
        task_logprint("ERROR: No measurement set specified")
        pipeline_context["QA2_applycals"] = "Fail"
        pipeline_context["applycals_error"] = "No measurement set specified"
        return pipeline_context

    try:
        # Check initial flags
        initial_flag_stats = _check_flags(ms_active, "before")
        pipeline_context["initial_flag_stats"] = initial_flag_stats

        # Build complete calibration table list
        final_gain_tables = _build_calibration_table_list(pipeline_context)
        ntables = len(final_gain_tables)

        task_logprint(f"Applying {ntables} calibration tables: {final_gain_tables}")

        if ntables == 0:
            task_logprint("WARNING: No calibration tables found to apply")
            QA2_applycals = "Fail"
            pipeline_context["applycals_error"] = "No calibration tables found"
        else:
            # Apply all calibrations
            applycal(
                vis=ms_active,
                field="",
                spw="",
                intent="",
                selectdata=False,
                gaintable=final_gain_tables,
                gainfield=[""] * ntables,
                interp=[""] * ntables,
                spwmap=[[]] * ntables,
                parang=True if do_pol else False,  # Enable parallactic angle correction for polarization
                calwt=[False] * ntables,
                applymode="calflagstrict",
                flagbackup=True,
            )

            task_logprint("Successfully applied all calibrations")

        # Check flags after calibration
        final_flag_stats = _check_flags(ms_active, "after")
        pipeline_context["final_flag_stats"] = final_flag_stats

        # Store calibration information in context
        pipeline_context["final_gain_tables"] = final_gain_tables
        pipeline_context["applycals_completed"] = True

    except Exception as e:
        task_logprint(f"ERROR applying calibrations: {e}")
        QA2_applycals = "Fail"
        pipeline_context["applycals_error"] = str(e)
        pipeline_context["applycals_completed"] = False

    # Set QA score
    pipeline_context["QA2_applycals"] = QA2_applycals

    # Import colored output function
    from evla_pipe.utils import format_qa_status
    task_logprint(f"QA2 score: {format_qa_status(QA2_applycals)}")
    task_logprint("Finished EVLA_pipe_applycals.py")
    time_list = runtiming("applycals", "end")

    return pipeline_context


# Legacy compatibility
EVLA_pipe_applycals = applycals



@register_step("EVLA_pipe_applycals")
def EVLA_pipe_applycals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for applycals() to match expected step name.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary

    Returns
    -------
    dict
        Updated pipeline context
    """
    return applycals(pipeline_context)
