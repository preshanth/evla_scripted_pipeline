"""Prior calibrations module for EVLA pipeline.

This module generates deterministic prior calibration tables including:
- Elevation gain curves
- Atmospheric opacities
- Requantizer gains (for data after Feb 24, 2011)
- Antenna position corrections

Refactored from original EVLA_pipe_priorcals.py to follow function-based,
context-passing design pattern.
"""

from typing import Dict, Any, List
from pathlib import Path
from casatasks import gencal
from evla_pipe.utils import (
    runtiming,
    logprint,
    correct_ant_posns,
    get_caltable_path,
    format_qa_status,
)


def task_logprint(msg: str) -> None:
    """
    Centralized logging for prior calibrations operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/priorcals.log")


def generate_gain_curves_table(
    msname: str,
    pipeline_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate elevation gain curves calibration table.

    Parameters
    ----------
    msname : str
        Path to measurement set
    pipeline_context : dict
        Pipeline context for storing results

    Returns
    -------
    dict
        Updated context with gain_curves_table path

    Notes
    -----
    Uses gencal with caltype='gc' to generate elevation-dependent gain corrections.
    """
    gain_curves_table = str(get_caltable_path("gain_curves.g", "prior"))

    task_logprint("Generating elevation gain curves table")
    task_logprint(f"  Output: {gain_curves_table}")

    try:
        gencal(
            vis=msname,
            caltable=gain_curves_table,
            caltype="gc",
            spw="",
            antenna="",
            pol="",
        )

        if Path(gain_curves_table).exists():
            pipeline_context["gain_curves_table"] = gain_curves_table
            task_logprint(f"  Success: Generated {gain_curves_table}")
        else:
            raise FileNotFoundError(f"Expected table not created: {gain_curves_table}")

    except Exception as e:
        task_logprint(f"  ERROR: Failed to generate gain curves table: {e}")
        raise

    return pipeline_context


def generate_opacities_table(
    msname: str,
    all_spw: str,
    tau: List[float],
    pipeline_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate atmospheric opacity calibration table.

    Parameters
    ----------
    msname : str
        Path to measurement set
    all_spw : str
        Comma-separated list of all spectral window IDs
    tau : list of float
        Atmospheric opacity values per spectral window
    pipeline_context : dict
        Pipeline context for storing results

    Returns
    -------
    dict
        Updated context with opacities_table path

    Notes
    -----
    Uses gencal with caltype='opac' to correct for atmospheric opacity.
    The tau parameter should be a list of opacity values matching the spectral windows.
    """
    opacities_table = str(get_caltable_path("opacities.g", "prior"))

    task_logprint("Generating atmospheric opacities table")
    task_logprint(f"  Output: {opacities_table}")
    task_logprint(f"  SPWs: {all_spw}")
    task_logprint(f"  Tau values: {tau}")

    try:
        gencal(
            vis=msname,
            caltable=opacities_table,
            caltype="opac",
            spw=all_spw,
            antenna="",
            pol="",
            parameter=tau,
        )

        if Path(opacities_table).exists():
            pipeline_context["opacities_table"] = opacities_table
            task_logprint(f"  Success: Generated {opacities_table}")
        else:
            raise FileNotFoundError(f"Expected table not created: {opacities_table}")

    except Exception as e:
        task_logprint(f"  ERROR: Failed to generate opacities table: {e}")
        raise

    return pipeline_context


def generate_requantizer_table(
    msname: str,
    startdate: float,
    pipeline_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate requantizer gains calibration table (if applicable).

    Parameters
    ----------
    msname : str
        Path to measurement set
    startdate : float
        Observation start date in MJD
    pipeline_context : dict
        Pipeline context for storing results

    Returns
    -------
    dict
        Updated context with requantizer_table path (if generated)

    Notes
    -----
    Requantizer gains are only applied for data observed after Feb 24, 2011
    (MJD 55616.6), when sensible switched power tables became available.
    """
    # MJD for Feb 24, 2011
    feb_24_2011 = 55616.6

    if startdate < feb_24_2011:
        task_logprint(
            f"Skipping requantizer gains (startdate {startdate:.1f} before "
            f"Feb 24, 2011 MJD {feb_24_2011})"
        )
        pipeline_context["requantizer_table"] = None
        return pipeline_context

    requantizer_table = str(get_caltable_path("requantizergains.g", "prior"))

    task_logprint("Generating requantizer gains table")
    task_logprint(f"  Output: {requantizer_table}")
    task_logprint(f"  Start date: {startdate:.1f} MJD")

    try:
        gencal(
            vis=msname,
            caltable=requantizer_table,
            caltype="rq",
            spw="",
            antenna="",
            pol="",
        )

        if Path(requantizer_table).exists():
            pipeline_context["requantizer_table"] = requantizer_table
            task_logprint(f"  Success: Generated {requantizer_table}")
        else:
            raise FileNotFoundError(f"Expected table not created: {requantizer_table}")

    except Exception as e:
        task_logprint(f"  ERROR: Failed to generate requantizer table: {e}")
        raise

    return pipeline_context


def generate_antenna_position_table(
    msname: str,
    pipeline_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate antenna position corrections calibration table.

    Parameters
    ----------
    msname : str
        Path to measurement set
    pipeline_context : dict
        Pipeline context for storing results

    Returns
    -------
    dict
        Updated context with antpos_table path and antenna_offsets

    Notes
    -----
    Corrects for known antenna position errors. Uses gencal with caltype='antpos'.
    The actual position corrections are determined by correct_ant_posns() utility.
    """
    antpos_table = str(get_caltable_path("antposcal.p", "prior"))

    task_logprint("Generating antenna position corrections table")
    task_logprint(f"  Output: {antpos_table}")

    try:
        # Generate the table
        gencal(
            vis=msname,
            caltable=antpos_table,
            caltype="antpos",
            spw="",
            antenna="",
            pol="",
            parameter=[],
        )

        # Check if corrections were actually needed/applied
        if Path(antpos_table).exists():
            # Get the actual antenna offsets that were applied
            antenna_offsets = correct_ant_posns(msname)

            pipeline_context["antpos_table"] = antpos_table
            pipeline_context["antenna_offsets"] = antenna_offsets

            task_logprint("  Success: Antenna position corrections applied")
            task_logprint(f"  Offsets: {antenna_offsets}")
        else:
            pipeline_context["antpos_table"] = None
            pipeline_context["antenna_offsets"] = {}
            task_logprint("  No antenna position corrections found/needed")

    except Exception as e:
        # Antenna position corrections are optional - log but don't fail
        pipeline_context["antpos_table"] = None
        pipeline_context["antenna_offsets"] = {}
        task_logprint(f"  No antenna position corrections found/needed: {e}")

    return pipeline_context


def priorcals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate all deterministic prior calibration tables.

    This function generates the following calibration tables:
    1. Elevation gain curves (gc)
    2. Atmospheric opacities (opac)
    3. Requantizer gains (rq) - if data after Feb 24, 2011
    4. Antenna position corrections (antpos)

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Path to measurement set
        - all_spw : str
            Comma-separated list of spectral window IDs
        - tau : list of float
            Atmospheric opacity values per SPW
        - startdate : float
            Observation start date in MJD

    Returns
    -------
    dict
        Updated pipeline context with:
        - priorcals : list of str
            List of generated calibration table paths
        - priorcals_tables : list of str
            Copy of priorcals list for backward compatibility
        - gain_curves_table : str
            Path to gain curves table
        - opacities_table : str
            Path to opacities table
        - requantizer_table : str or None
            Path to requantizer table (if applicable)
        - antpos_table : str or None
            Path to antenna position table (if corrections found)
        - antenna_offsets : dict
            Antenna position offsets that were applied
        - QA2_priorcals : str
            QA status ("Pass" or "Fail")

    Notes
    -----
    All calibration tables are saved to the calibration directory structure
    managed by get_caltable_path(). The priorcals list contains only tables
    that were successfully generated and exist on disk.

    This function will raise exceptions for critical failures (gain curves,
    opacities) but will gracefully handle optional corrections (antenna positions).
    """
    task_logprint("*** Starting Prior Calibrations ***")
    time_list = runtiming("priorcals", "start")

    # Extract required parameters from context
    msname = pipeline_context.get("msname", "")
    all_spw = pipeline_context.get("all_spw", "")
    tau = pipeline_context.get("tau", [])
    startdate = pipeline_context.get("startdate", 0.0)

    # Validate inputs
    if not msname:
        raise ValueError("msname not found in pipeline_context")
    if not all_spw:
        raise ValueError("all_spw not found in pipeline_context")
    if not tau:
        raise ValueError("tau not found in pipeline_context")

    task_logprint(f"Measurement set: {msname}")
    task_logprint(f"Spectral windows: {all_spw}")
    task_logprint(f"Start date: {startdate:.1f} MJD")

    try:
        # List to collect all generated calibration tables
        priorcals: List[str] = []

        # 1. Generate gain curves table (required)
        pipeline_context = generate_gain_curves_table(msname, pipeline_context)
        if pipeline_context.get("gain_curves_table"):
            priorcals.append(pipeline_context["gain_curves_table"])

        # 2. Generate opacities table (required)
        pipeline_context = generate_opacities_table(
            msname, all_spw, tau, pipeline_context
        )
        if pipeline_context.get("opacities_table"):
            priorcals.append(pipeline_context["opacities_table"])

        # 3. Generate requantizer table (conditional on date)
        pipeline_context = generate_requantizer_table(
            msname, startdate, pipeline_context
        )
        if pipeline_context.get("requantizer_table"):
            priorcals.append(pipeline_context["requantizer_table"])

        # 4. Generate antenna position corrections (optional)
        pipeline_context = generate_antenna_position_table(msname, pipeline_context)
        if pipeline_context.get("antpos_table"):
            priorcals.append(pipeline_context["antpos_table"])

        # Update context with results
        pipeline_context["priorcals"] = priorcals
        pipeline_context["priorcals_tables"] = priorcals.copy()
        pipeline_context["QA2_priorcals"] = "Pass"

        task_logprint("*** Prior Calibrations Complete ***")
        task_logprint(f"Generated {len(priorcals)} calibration tables:")
        for table in priorcals:
            task_logprint(f"  • {Path(table).name}")

    except Exception as e:
        task_logprint(f"*** Prior Calibrations FAILED ***")
        task_logprint(f"Error: {e}")

        pipeline_context["QA2_priorcals"] = "Fail"
        pipeline_context["error_message"] = str(e)
        pipeline_context["priorcals"] = []
        pipeline_context["priorcals_tables"] = []

        # Prior calibrations are critical - re-raise to stop pipeline
        raise

    finally:
        # Always record timing
        time_list = runtiming("priorcals", "end")
        pipeline_context["time_list"] = time_list

        # Log final QA status
        qa_status = pipeline_context.get("QA2_priorcals", "Unknown")
        task_logprint(f"QA2 score: {format_qa_status(qa_status)}")

    return pipeline_context


def EVLA_pipe_priorcals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for EVLA_pipe_priorcals pipeline step.

    This is a wrapper function that maintains backward compatibility with
    the original pipeline structure while calling the refactored priorcals()
    function.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context

    See Also
    --------
    priorcals : Core implementation of prior calibrations
    """
    return priorcals(pipeline_context)
