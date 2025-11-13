# EVLA_pipe_calprep.py (Refactored)
"""
Calibration preparation module for EVLA pipeline.

This module sets flux density models for standard primary calibrators
using the Perley-Butler 2017 standard, with full polarization support.
"""

from typing import Dict, Any, List, Tuple, Optional
from casatasks import setjy
from casatools import measures as mstool

from evla_pipe.utils import runtiming, logprint, find_EVLA_band, find_standards, format_qa_status
from evla_pipe.pol_setjy_utils import integrate_polarization_setjy


# Module-level CASA tool instances
me = mstool()

# Standard calibrator source names
STANDARD_SOURCE_NAMES = ["3C48", "3C138", "3C147", "3C286"]


def task_logprint(msg: str) -> None:
    """
    Centralized logging for calibration preparation operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/calprep.log")


def _extract_position_tuples(field_positions: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    """
    Convert CASA measure dictionaries to (lon, lat) tuples in radians.

    Parameters
    ----------
    field_positions : list of dict
        CASA measure dictionaries with 'm0' (RA) and 'm1' (Dec)

    Returns
    -------
    list of tuple
        Position tuples as (longitude, latitude) in radians
    """
    positions = []
    for field_pos in field_positions:
        if isinstance(field_pos, dict) and 'm0' in field_pos and 'm1' in field_pos:
            lon = field_pos['m0']['value']  # RA in radians
            lat = field_pos['m1']['value']  # Dec in radians
            positions.append((lon, lat))
        else:
            task_logprint(f"Warning: Unexpected field position format: {field_pos}")
            positions.append((0.0, 0.0))  # Fallback to origin
    return positions


def _set_polarization_models(
    ms_active: str,
    field: int,
    field_name: str,
    spws: List[int],
    center_frequencies: List[float],
    evla_band: str,
    scratch: bool
) -> bool:
    """
    Set full polarization models for a calibrator field.

    Parameters
    ----------
    ms_active : str
        Measurement set name
    field : int
        Field ID
    field_name : str
        Standard calibrator name (e.g., '3C286')
    spws : list of int
        Spectral window IDs for this field
    center_frequencies : list of float
        Center frequencies for all SPWs in GHz
    evla_band : str
        EVLA band designation (e.g., 'L', 'S', 'C', 'X', 'Ku', 'K', 'Ka', 'Q')
    scratch : bool
        Whether to use scratch columns

    Returns
    -------
    bool
        True if successful, False otherwise
    """
    # Filter valid SPWs
    valid_spws = [spw for spw in spws if spw < len(center_frequencies)]

    if not valid_spws:
        task_logprint(f"WARNING: No valid spws found for field {field}")
        return False

    # Calculate average frequency for reference
    avg_freq = sum(center_frequencies[spw] for spw in valid_spws) / len(valid_spws)
    model_image = f"{field_name}_{evla_band}.im"

    task_logprint(f"Setting model for field {field} ({field_name}) in {evla_band} band")
    task_logprint(f"SPWs: {valid_spws}")
    task_logprint(f"Reference frequency: {avg_freq:.3f} GHz")

    try:
        # Attempt full polarization model setting
        task_logprint(f"Setting full polarization models for {field_name}")

        integrate_polarization_setjy(
            vis=ms_active,
            field_id=field,
            field_name=field_name,
            spws=valid_spws,
            band=evla_band,
            ref_freq_hz=avg_freq * 1e9,  # Convert GHz to Hz
            obs_date=None,  # Will use 2019 data by default
            use_model_image=model_image,
            standard="Perley-Butler 2017",
            usescratch=scratch
        )

        task_logprint(f"Successfully set full polarization models for {field_name}")
        return True

    except Exception as e:
        task_logprint(f"Error setting polarization models for field {field}: {e}")
        task_logprint("Falling back to intensity-only setjy per spw")

        # Fallback to standard intensity-only setjy for each spw
        success = True
        for spw in valid_spws:
            try:
                setjy(
                    vis=ms_active,
                    field=str(field),
                    spw=str(spw),
                    selectdata=False,
                    scalebychan=True,
                    standard="Perley-Butler 2017",
                    model=model_image,
                    listmodels=False,
                    usescratch=scratch,
                )
                task_logprint(f"Fallback intensity-only setjy succeeded for field {field} spw {spw}")
            except Exception as fallback_e:
                task_logprint(f"Fallback setjy also failed for field {field} spw {spw}: {fallback_e}")
                success = False

        return success


def calprep(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare for calibrations by setting models for primary calibrators.

    This function sets flux density scale models for standard calibrators
    (3C48, 3C138, 3C147, 3C286) using the Perley-Butler 2017 standard.
    It attempts to set full polarization models when available, falling
    back to intensity-only models if necessary.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Measurement set name
        - field_positions : list of dict
            CASA measure dictionaries for field positions
        - field_spws : list of list
            SPW lists for each field
        - center_frequencies : list of float
            Center frequencies for all SPWs in GHz

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_calprep : str
            Quality assessment flag ('Pass' or 'Fail')
        - calprep_standards_found : bool
            Whether standard calibrators were found
        - calprep_error_message : str, optional
            Error message if calibration preparation failed

    Notes
    -----
    Sets QA2_calprep flag based on success/failure of finding and
    setting models for standard calibrators.
    """
    task_logprint("*** Starting EVLA_pipe_calprep.py (Refactored) ***")
    time_list = runtiming("calprep", "start")

    # Initialize QA status
    QA2_calprep = "Pass"
    standards_found = False

    # Extract required context
    ms_active = pipeline_context.get("msname")
    field_positions = pipeline_context.get("field_positions")
    field_spws = pipeline_context.get("field_spws")
    center_frequencies = pipeline_context.get("center_frequencies")
    scratch = True  # Use scratch columns for model data

    # Debug logging
    task_logprint(f"Debug: field_positions type: {type(field_positions)}, "
                  f"length: {len(field_positions) if field_positions else 'None'}")
    task_logprint(f"Debug: field_spws type: {type(field_spws)}, value: {field_spws}")
    task_logprint(f"Debug: center_frequencies type: {type(center_frequencies)}, "
                  f"length: {len(center_frequencies) if center_frequencies else 'None'}")

    # Validate required context keys
    if ms_active is None:
        error_msg = "ERROR: msname not found in pipeline context."
        task_logprint(error_msg)
        pipeline_context["QA2_calprep"] = "Fail"
        pipeline_context["calprep_error_message"] = error_msg
        return pipeline_context

    if field_positions is None:
        error_msg = "ERROR: field_positions not found in pipeline context."
        task_logprint(error_msg)
        pipeline_context["QA2_calprep"] = "Fail"
        pipeline_context["calprep_error_message"] = error_msg
        return pipeline_context

    if field_spws is None:
        error_msg = "ERROR: field_spws not found in pipeline context."
        task_logprint(error_msg)
        pipeline_context["QA2_calprep"] = "Fail"
        pipeline_context["calprep_error_message"] = error_msg
        return pipeline_context

    if center_frequencies is None:
        error_msg = "ERROR: center_frequencies not found in pipeline context."
        task_logprint(error_msg)
        pipeline_context["QA2_calprep"] = "Fail"
        pipeline_context["calprep_error_message"] = error_msg
        return pipeline_context

    task_logprint("Setting models for standard primary calibrators")

    try:
        # Convert CASA measure dictionaries to position tuples
        positions = _extract_position_tuples(field_positions)

        # Identify standard calibrator fields
        standard_source_fields = find_standards(positions)
        standards_found = any(standard_source_fields)

        if not standards_found:
            error_msg = ("ERROR: No standard flux density calibrator observed, "
                        "flux density scale will be arbitrary.")
            task_logprint(error_msg)
            QA2_calprep = "Fail"
            pipeline_context["calprep_error_message"] = error_msg
        else:
            task_logprint(f"Found standard calibrators: "
                         f"{sum(len(fields) for fields in standard_source_fields)} field(s)")

            # Process each standard calibrator
            for source_idx, fields in enumerate(standard_source_fields):
                field_name = STANDARD_SOURCE_NAMES[source_idx]

                for field in fields:
                    if field >= len(field_spws):
                        task_logprint(f"WARNING: field_spws index {field} out of range.")
                        continue

                    spws = field_spws[field]

                    # Handle numpy arrays and lists - check length explicitly
                    if spws is None or len(spws) == 0 or spws[0] >= len(center_frequencies):
                        task_logprint(f"WARNING: No spws or invalid spw indices for field {field}")
                        continue

                    # Determine EVLA band from first SPW frequency
                    reference_frequency = center_frequencies[spws[0]]
                    evla_band = find_EVLA_band(reference_frequency)

                    # Set polarization models for this field
                    success = _set_polarization_models(
                        ms_active=ms_active,
                        field=field,
                        field_name=field_name,
                        spws=spws,
                        center_frequencies=center_frequencies,
                        evla_band=evla_band,
                        scratch=scratch
                    )

                    if not success:
                        task_logprint(f"WARNING: Failed to set models for field {field} ({field_name})")

        task_logprint("Finished setting models for known calibrators")

    except Exception as e:
        error_msg = f"ERROR during calibration preparation: {str(e)}"
        task_logprint(error_msg)
        QA2_calprep = "Fail"
        pipeline_context["calprep_error_message"] = error_msg

    # Update pipeline context
    pipeline_context["QA2_calprep"] = QA2_calprep
    pipeline_context["calprep_standards_found"] = standards_found

    # Final status logging
    task_logprint("Finished EVLA_pipe_calprep.py (Refactored)")
    task_logprint(f"QA2 score: {format_qa_status(QA2_calprep)}")

    time_list = runtiming("calprep", "end")

    return pipeline_context


# Backward compatibility alias
EVLA_pipe_calprep = calprep
