"""
Pre-Calibration Setup Module for EVLA Pipeline

This module handles pre-calibration tasks that need to occur after flagging
and calibrator splitting but before the main calibration steps:

1. Flux density calibration (setjy)
2. Reference antenna selection
3. Solution interval determination
4. Calibration strategy setup
"""

from pathlib import Path
from typing import Any, Dict

import numpy as np
from casatasks import setjy
from casatools import quanta, table

from evla_pipe.utils import (
    ensure_dir_exists,
    get_caltable_path,
    get_log_path,
    logprint,
    runtiming,
)

# from evla_pipe.polarization import integrate_polarization_calibration  # Temporarily disabled

tb = table()
qa = quanta()


def task_logprint(msg: str):
    """Centralized logging for pre-calibration operations."""
    logprint(msg, logfileout=str(get_log_path("precalibration.log")))


def perform_precalibration_setup(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main pre-calibration setup function.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with MS metadata and calibrator information

    Returns
    -------
    dict
        Updated pipeline context with pre-calibration setup complete
    """
    task_logprint("*** Starting Pre-Calibration Setup ***")
    runtiming("precalibration", "start")

    try:
        # Step 1: Flux density calibration (setjy)
        pipeline_context = setup_flux_calibration(pipeline_context)

        # Step 2: Polarization calibrator model fitting
        pipeline_context = setup_polarization_calibration(pipeline_context)

        # Step 3: Reference antenna selection
        pipeline_context = select_reference_antenna(pipeline_context)

        # Step 4: Solution interval determination
        pipeline_context = determine_solution_intervals(pipeline_context)

        # Step 5: Calibration strategy setup
        pipeline_context = setup_calibration_strategy(pipeline_context)

        pipeline_context["QA2_precalibration"] = "Pass"
        task_logprint("Pre-calibration setup completed successfully")

    except Exception as e:
        task_logprint(f"Pre-calibration setup failed: {e}")
        pipeline_context["QA2_precalibration"] = "Fail"
        raise

    finally:
        runtiming("precalibration", "end")

    return pipeline_context


def setup_flux_calibration(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set up flux density calibration using setjy.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context

    Returns
    -------
    dict
        Updated context with flux calibration setup
    """
    task_logprint("=== Setting up flux density calibration ===")

    # Get calibrators.ms and flux calibrator information
    calibrators_ms = pipeline_context.get("calibrators_ms", "calibrators.ms")
    flux_field_list = pipeline_context.get("flux_field_list", [])

    if not flux_field_list:
        task_logprint("Warning: No flux calibrators identified")
        return pipeline_context

    # Get observing frequency for flux calibration
    spw_info = pipeline_context.get("spw_info", {})
    evla_band = pipeline_context.get("EVLA_band", "Unknown")

    # Determine flux standard based on frequency
    flux_standard = determine_flux_standard(evla_band, spw_info)
    task_logprint(f"Using flux standard: {flux_standard}")

    setjy_results = {}

    for field_id in flux_field_list:
        field_name = get_field_name(pipeline_context, field_id)
        task_logprint(f"Setting flux density for field {field_id} ({field_name})")

        try:
            # Run setjy for this flux calibrator
            result = setjy(
                vis=calibrators_ms,
                field=str(field_id),
                standard=flux_standard,
                model="",
                modimage="",
                listmodels=False,
                scalebychan=True,
                spw="",
                timerange="",
                scan="",
                intent="",
                observation="",
                usescratch=False,
            )

            setjy_results[field_id] = result
            task_logprint(f"Setjy completed for field {field_id}")

            # Log flux density information
            if isinstance(result, dict) and field_id in result:
                flux_info = result[field_id]
                if "fluxd" in flux_info:
                    flux_density = flux_info["fluxd"]
                    task_logprint(f"Flux density set: I={flux_density[0]:.3f} Jy")

        except Exception as e:
            task_logprint(f"Setjy failed for field {field_id}: {e}")
            setjy_results[field_id] = {"error": str(e)}

    # Store setjy results in context
    pipeline_context["setjy_results"] = setjy_results
    pipeline_context["flux_standard"] = flux_standard

    return pipeline_context


def setup_polarization_calibration(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set up polarization calibrator model fitting for position angle and polarization.

    This function uses the integrated polarization setjy to fit models for
    polarization calibrators, determining the position angle (p) and
    polarization angle (chi) parameters.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with polarization calibrator information

    Returns
    -------
    dict
        Updated context with polarization calibration setup
    """
    task_logprint("=== Setting up polarization calibration ===")

    # Get polarization calibrator information
    pol_angle_fields = pipeline_context.get("polarization_angle_field_list", [])
    pol_lkg_fields = pipeline_context.get("polarization_lkg_field_list", [])
    pipeline_context.get("calibrators_ms", "calibrators.ms")

    # Check if we have polarization calibrators
    has_pol_calibrators = len(pol_angle_fields) > 0 or len(pol_lkg_fields) > 0

    if not has_pol_calibrators:
        task_logprint("No polarization calibrators found, skipping polarization setup")
        pipeline_context["polarization_calibration_setup"] = False
        return pipeline_context

    task_logprint(f"Found polarization angle calibrators: {pol_angle_fields}")
    task_logprint(f"Found polarization leakage calibrators: {pol_lkg_fields}")

    try:
        # TODO: Implement polarization setjy integration
        # For now, skip polarization setup
        task_logprint("Polarization setjy integration not yet implemented")
        pol_results = {"success": False, "models": {}}

        # Extract results for context
        if pol_results.get("success", False):
            pipeline_context["polarization_models"] = pol_results.get("models", {})
            pipeline_context["polarization_calibration_setup"] = True

            # Log fitted parameters
            for field_id, model in pol_results.get("models", {}).items():
                field_name = get_field_name(pipeline_context, field_id)
                if "position_angle" in model:
                    pa = model["position_angle"]
                    task_logprint(
                        f"Field {field_id} ({field_name}): position angle = {pa:.1f} deg"
                    )
                if "polarization_fraction" in model:
                    pf = model["polarization_fraction"]
                    task_logprint(
                        f"Field {field_id} ({field_name}): polarization fraction = {pf:.3f}"
                    )

        else:
            task_logprint("Polarization model fitting failed, will use defaults")
            pipeline_context["polarization_calibration_setup"] = False

    except Exception as e:
        task_logprint(f"Polarization calibration setup failed: {e}")
        task_logprint("Continuing without polarization calibration")
        pipeline_context["polarization_calibration_setup"] = False

    return pipeline_context


def determine_flux_standard(evla_band: str, spw_info: Dict[str, Any]) -> str:
    """
    Determine appropriate flux standard based on observing frequency.

    Parameters
    ----------
    evla_band : str
        VLA band designation (L, S, C, X, etc.)
    spw_info : dict
        Spectral window information

    Returns
    -------
    str
        Flux standard name for setjy
    """
    # Get representative frequency from first spw
    if spw_info:
        first_spw = list(spw_info.values())[0]
        freq_ghz = first_spw.get("centerfreq_hz", 0) / 1e9
    else:
        freq_ghz = 1.4  # Default L-band

    # Choose flux standard based on frequency
    # Modern standards (post-2017)
    if freq_ghz < 1.0:
        # Low frequencies: use Perley-Butler 2017
        return "Perley-Butler 2017"
    elif freq_ghz < 8.0:
        # L, S, C bands: use Perley-Butler 2017
        return "Perley-Butler 2017"
    elif freq_ghz < 20.0:
        # X, Ku bands: use Perley-Butler 2017
        return "Perley-Butler 2017"
    else:
        # K, Ka, Q bands: use Perley-Butler 2017
        return "Perley-Butler 2017"


def select_reference_antenna(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Select optimal reference antenna for calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with antenna information

    Returns
    -------
    dict
        Updated context with reference antenna selection
    """
    task_logprint("=== Selecting reference antenna ===")

    antenna_info = pipeline_context.get("antenna_info", {})
    antenna_names_data = antenna_info.get("names", {})

    if isinstance(antenna_names_data, dict) and "data" in antenna_names_data:
        antenna_names = antenna_names_data["data"]
    else:
        antenna_names = (
            antenna_names_data if isinstance(antenna_names_data, list) else []
        )

    if not antenna_names:
        task_logprint("Warning: No antenna names available")
        pipeline_context["refantignore"] = ""
        pipeline_context["refant"] = ""
        return pipeline_context

    # Preferred reference antennas (central, stable antennas)
    preferred_antennas = [
        "ea13",
        "ea14",
        "ea15",
        "ea16",
        "ea17",
        "ea18",
        "ea19",
        "ea20",
        "ea21",  # Inner A-array
        "ea02",
        "ea03",
        "ea04",
        "ea05",
        "ea06",
        "ea08",
        "ea09",
        "ea10",
        "ea12",  # Good antennas
    ]

    # Find available preferred antennas
    available_preferred = []
    for ant in preferred_antennas:
        if ant in antenna_names:
            available_preferred.append(ant)

    if available_preferred:
        refant = available_preferred[0]
        refantignore = ",".join(available_preferred[1:6])  # Next 5 as backups
    else:
        # Fallback: use first available antenna
        refant = antenna_names[0] if antenna_names else ""
        refantignore = ",".join(antenna_names[1:6]) if len(antenna_names) > 1 else ""

    task_logprint(f"Selected reference antenna: {refant}")
    task_logprint(f"Reference antenna hierarchy: {refantignore}")

    pipeline_context["refant"] = refant
    pipeline_context["refantignore"] = refantignore

    return pipeline_context


def determine_solution_intervals(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine optimal solution intervals for calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with scan and time information

    Returns
    -------
    dict
        Updated context with solution intervals
    """
    task_logprint("=== Determining solution intervals ===")

    int_time = pipeline_context.get("int_time", 1.0)
    scan_info = pipeline_context.get("scan_info", {})

    # Calculate typical scan lengths
    scan_lengths = []
    for _scan_id, scan_data in scan_info.items():
        if isinstance(scan_data, dict):
            times_data = scan_data.get("times", {})
            if isinstance(times_data, dict) and "data" in times_data:
                times = np.array(times_data["data"])
                if len(times) > 1:
                    scan_length = (
                        times.max() - times.min()
                    ) * 86400  # Convert to seconds
                    scan_lengths.append(scan_length)

    if scan_lengths:
        median_scan_length = np.median(scan_lengths)
        task_logprint(f"Median scan length: {median_scan_length:.1f} seconds")
    else:
        median_scan_length = 300.0  # Default 5 minutes

    # Set solution intervals based on scan characteristics
    # Short solint for phase: ~30s to 1 minute
    short_solint = min(60.0, median_scan_length / 3.0)
    short_solint = max(short_solint, 5 * int_time)  # At least 5 integrations

    # Long solint for amplitude: scan length or 5-10 minutes
    long_solint = min(median_scan_length, 600.0)  # Max 10 minutes
    long_solint = max(long_solint, 60.0)  # At least 1 minute

    # Bandpass solution interval: entire scan
    bp_solint = "inf"  # Use entire scan

    task_logprint(f"Short solution interval (phase): {short_solint:.1f}s")
    task_logprint(f"Long solution interval (amplitude): {long_solint:.1f}s")
    task_logprint(f"Bandpass solution interval: {bp_solint}")

    pipeline_context["short_solint"] = f"{short_solint:.1f}s"
    pipeline_context["long_solint"] = f"{long_solint:.1f}s"
    pipeline_context["bp_solint"] = bp_solint

    return pipeline_context


def setup_calibration_strategy(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set up calibration strategy based on available calibrators and data.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context

    Returns
    -------
    dict
        Updated context with calibration strategy
    """
    task_logprint("=== Setting up calibration strategy ===")

    # Get calibrator field information
    flux_fields = pipeline_context.get("flux_field_list", [])
    bandpass_fields = pipeline_context.get("bandpass_field_list", [])
    delay_fields = pipeline_context.get("delay_field_list", [])
    phase_fields = pipeline_context.get("phase_field_list", [])

    # Determine calibration strategy
    has_separate_bp = len(bandpass_fields) > 0 and bandpass_fields != delay_fields
    has_separate_delay = len(delay_fields) > 0
    has_flux_cal = len(flux_fields) > 0
    has_phase_cal = len(phase_fields) > 0

    # Set up calibration table paths
    caltables = setup_calibration_tables(pipeline_context)

    strategy = {
        "has_separate_bandpass": has_separate_bp,
        "has_separate_delay": has_separate_delay,
        "has_flux_calibrator": has_flux_cal,
        "has_phase_calibrator": has_phase_cal,
        "calibration_tables": caltables,
    }

    task_logprint(f"Calibration strategy: {strategy}")

    pipeline_context["calibration_strategy"] = strategy
    pipeline_context.update(caltables)

    return pipeline_context


def setup_calibration_tables(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set up paths for calibration tables.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context

    Returns
    -------
    dict
        Dictionary of calibration table paths
    """
    msname = pipeline_context.get("msname", "")
    basename = Path(msname).stem

    # Ensure calibration directories exist
    ensure_dir_exists(Path("intermediate_caltables"))
    ensure_dir_exists(Path("final_caltables"))

    tables = {
        # Prior calibrations
        "priorcals_table": get_caltable_path(f"{basename}.priorcals", "intermediate"),
        # Test calibrations
        "test_delay_table": get_caltable_path(f"{basename}.test_delay", "intermediate"),
        "test_bp_table": get_caltable_path(f"{basename}.test_bp", "intermediate"),
        "test_gain_table": get_caltable_path(f"{basename}.test_gain", "intermediate"),
        # Final calibrations
        "final_delay_table": get_caltable_path(f"{basename}.final_delay", "final"),
        "final_bp_table": get_caltable_path(f"{basename}.final_bp", "final"),
        "final_gain_table": get_caltable_path(f"{basename}.final_gain", "final"),
        "final_flux_table": get_caltable_path(f"{basename}.final_flux", "final"),
    }

    return tables


def get_field_name(pipeline_context: Dict[str, Any], field_id: int) -> str:
    """
    Get field name from field ID.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context
    field_id : int
        Field ID

    Returns
    -------
    str
        Field name
    """
    field_info = pipeline_context.get("field_info", {})
    if field_id in field_info:
        return field_info[field_id].get("name", f"field_{field_id}")
    return f"field_{field_id}"
