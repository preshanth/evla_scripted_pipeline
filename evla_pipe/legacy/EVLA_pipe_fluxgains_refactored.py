"""EVLA Pipeline: Flux Calibration and Gain Solutions.

This module sets flux density models for standard calibrators and applies
setjy to set the model column for flux calibration.

Replaces: EVLA_pipe_fluxgains.py
"""

from typing import Any, Dict, List, Union

from casatasks import setjy

from evla_pipe.pol_setjy_utils import integrate_polarization_setjy
from evla_pipe.utils import (
    find_EVLA_band,
    find_standards,
    format_qa_status,
    logprint,
    runtiming,
)


def task_logprint(msg: str) -> None:
    """Centralized logging for flux gains operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/fluxgains.log")


def set_standard_source_models(
    pipeline_context: Dict[str, Any],
    field_positions: Any,
    field_spws: Union[List, Dict],
    center_frequencies: Union[List, Dict],
    scratch: bool,
) -> Dict[str, Any]:
    """
    Set flux density models for standard primary calibrators using setjy.

    This function identifies standard calibrators (3C48, 3C138, 3C147, 3C286)
    in the observation and sets appropriate flux density models for each
    spectral window. It attempts to use full polarization models when available,
    falling back to intensity-only models if polarization models fail.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing msname and configuration
    field_positions : numpy.ndarray
        Array of field positions for identifying standard sources
    field_spws : list or dict
        Field-to-spectral window mapping (list indexed by field ID)
    center_frequencies : list or dict
        Center frequencies for each spectral window (GHz)
    scratch : bool
        Whether to use scratch columns in the measurement set

    Returns
    -------
    dict
        Updated pipeline context with setjy results

    Notes
    -----
    - Uses Perley-Butler 2017 flux density scale
    - Attempts full polarization models first via integrate_polarization_setjy
    - Falls back to intensity-only setjy if polarization models unavailable
    - Updates context with success/failure information for each field/spw
    """
    task_logprint("*** Setting standard source models ***")
    runtiming("fluxgains_setjy", "start")

    calibrators_ms = pipeline_context.get("msname", "calibrators.ms")
    standard_source_names = ["3C48", "3C138", "3C147", "3C286"]

    # Find which fields correspond to standard calibrators
    standard_source_fields = find_standards(field_positions)

    # Track results for QA
    setjy_results = []
    failed_fields = []

    for ii, fields in enumerate(standard_source_fields):
        field_name = standard_source_names[ii]

        for myfield in fields:
            # field_spws is a list indexed by field number
            if myfield >= len(field_spws) or field_spws[myfield] is None:
                task_logprint(f"Warning: No spectral windows found for field {myfield}")
                continue

            myfield_spws = field_spws[myfield]

            for myspw in myfield_spws:
                # Get reference frequency for this spw
                # center_frequencies might be list or dict - handle both
                if isinstance(center_frequencies, dict):
                    reference_frequency = center_frequencies.get(myspw)
                elif isinstance(center_frequencies, list) and myspw < len(
                    center_frequencies
                ):
                    reference_frequency = center_frequencies[myspw]
                else:
                    reference_frequency = None

                if reference_frequency is None:
                    task_logprint(
                        f"Warning: Center frequency not found for spw {myspw} (field {myfield})"
                    )
                    failed_fields.append(
                        {"field": myfield, "spw": myspw, "reason": "missing_frequency"}
                    )
                    continue

                # Determine observing band and model image
                EVLA_band = find_EVLA_band(reference_frequency)
                model_image = f"{field_name}_{EVLA_band}.im"

                task_logprint(
                    f"Center freq for spw {myspw} (field {myfield}) = {reference_frequency} GHz, "
                    f"observing band = {EVLA_band}"
                )
                task_logprint(
                    f"Setting model for field {myfield} ({field_name}) spw {myspw} using {model_image}"
                )

                # Attempt full polarization model first
                try:
                    task_logprint(
                        f"Attempting full polarization models for {field_name}"
                    )

                    integrate_polarization_setjy(
                        vis=calibrators_ms,
                        field_id=myfield,
                        field_name=field_name,
                        spws=[myspw],
                        band=EVLA_band,
                        ref_freq_hz=reference_frequency * 1e9,  # Convert GHz to Hz
                        obs_date=None,  # Will use 2019 data by default
                        use_model_image=model_image,
                        standard="Perley-Butler 2017",
                        usescratch=scratch,
                    )

                    task_logprint(
                        f"Successfully set full polarization models for {field_name}"
                    )
                    setjy_results.append(
                        {
                            "field": myfield,
                            "field_name": field_name,
                            "spw": myspw,
                            "model": model_image,
                            "polarization": True,
                            "status": "success",
                        }
                    )

                except Exception as e:
                    task_logprint(
                        f"Error setting polarization models for field {myfield} spw {myspw}: {e}"
                    )
                    task_logprint("Falling back to intensity-only setjy")

                    # Fallback to standard intensity-only setjy
                    try:
                        setjy(
                            vis=calibrators_ms,
                            field=str(myfield),
                            spw=str(myspw),
                            selectdata=False,
                            scalebychan=True,
                            standard="Perley-Butler 2017",
                            model=model_image,
                            listmodels=False,
                            usescratch=scratch,
                        )

                        task_logprint(
                            f"Fallback intensity-only setjy succeeded for field {myfield}"
                        )
                        setjy_results.append(
                            {
                                "field": myfield,
                                "field_name": field_name,
                                "spw": myspw,
                                "model": model_image,
                                "polarization": False,
                                "status": "fallback_success",
                            }
                        )

                    except Exception as fallback_e:
                        task_logprint(
                            f"Fallback setjy also failed for field {myfield}: {fallback_e}"
                        )
                        failed_fields.append(
                            {
                                "field": myfield,
                                "field_name": field_name,
                                "spw": myspw,
                                "error": str(fallback_e),
                            }
                        )

    runtiming("fluxgains_setjy", "end")

    # Store results in context (JSON-serializable)
    pipeline_context["setjy_results"] = setjy_results
    pipeline_context["setjy_failed_fields"] = failed_fields
    pipeline_context["setjy_success_count"] = len(setjy_results)
    pipeline_context["setjy_failure_count"] = len(failed_fields)

    return pipeline_context


def fluxgains(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply flux density calibration models to standard calibrators.

    This is the main entry point for the flux gains calibration step.
    It sets flux density models for known standard calibrators using
    the appropriate flux density scale and observing band models.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Measurement set name
        - field_positions : numpy.ndarray
            Array of field positions
        - field_spws : list
            Field-to-spectral window mapping
        - center_frequencies : list or dict
            Center frequencies for spectral windows
        - usescratch : bool, optional
            Use scratch columns (default: False)

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_fluxgains : str
            Quality assessment result ("Pass" or "Fail")
        - setjy_results : list
            Detailed results for each setjy operation
        - setjy_failed_fields : list
            List of fields where setjy failed
        - time_list : list
            Timing information
        - error_message : str, optional
            Error message if step failed

    Notes
    -----
    This function replaces the procedural EVLA_pipe_fluxgains.py script
    with a clean function-based implementation that:
    - Takes context as input
    - Returns updated context
    - Handles errors gracefully
    - Logs all operations
    - Sets QA flags appropriately

    The flux density models are set using the Perley-Butler 2017 scale,
    with full polarization models when available.
    """
    task_logprint("*** Starting EVLA_pipe_fluxgains ***")
    time_list = runtiming("fluxgains", "start")

    QA2_score = "Fail"  # Default to fail, set to pass on success

    try:
        # Extract required parameters from context
        msname = pipeline_context.get("msname")
        field_positions = pipeline_context.get("field_positions")
        field_spws = pipeline_context.get("field_spws")
        center_frequencies = pipeline_context.get("center_frequencies")
        scratch = pipeline_context.get("usescratch", False)

        # Validate required parameters
        if msname is None:
            error_msg = "Missing required parameter: msname"
            task_logprint(f"ERROR: {error_msg}")
            pipeline_context["error_message"] = error_msg
            pipeline_context["QA2_fluxgains"] = QA2_score
            return pipeline_context

        if field_positions is None:
            error_msg = "Missing required parameter: field_positions"
            task_logprint(f"ERROR: {error_msg}")
            pipeline_context["error_message"] = error_msg
            pipeline_context["QA2_fluxgains"] = QA2_score
            return pipeline_context

        if field_spws is None:
            error_msg = "Missing required parameter: field_spws"
            task_logprint(f"ERROR: {error_msg}")
            pipeline_context["error_message"] = error_msg
            pipeline_context["QA2_fluxgains"] = QA2_score
            return pipeline_context

        if center_frequencies is None:
            error_msg = "Missing required parameter: center_frequencies"
            task_logprint(f"ERROR: {error_msg}")
            pipeline_context["error_message"] = error_msg
            pipeline_context["QA2_fluxgains"] = QA2_score
            return pipeline_context

        task_logprint(f"Processing measurement set: {msname}")
        task_logprint(f"Using scratch columns: {scratch}")

        # Set standard source models
        pipeline_context = set_standard_source_models(
            pipeline_context, field_positions, field_spws, center_frequencies, scratch
        )

        # Check results and set QA score
        success_count = pipeline_context.get("setjy_success_count", 0)
        failure_count = pipeline_context.get("setjy_failure_count", 0)

        if success_count > 0:
            QA2_score = "Pass"
            task_logprint(
                f"Successfully set models for {success_count} field/spw combinations"
            )
            if failure_count > 0:
                task_logprint(f"Warning: {failure_count} field/spw combinations failed")
        else:
            QA2_score = "Fail"
            error_msg = "No standard source models were successfully set"
            task_logprint(f"ERROR: {error_msg}")
            pipeline_context["error_message"] = error_msg

    except Exception as e:
        error_msg = f"Error in fluxgains step: {str(e)}"
        task_logprint(f"ERROR: {error_msg}")
        pipeline_context["error_message"] = error_msg
        QA2_score = "Fail"

    # Final logging and context updates
    task_logprint("Finished EVLA_pipe_fluxgains")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("fluxgains", "end")

    # Update context with results (all JSON-serializable)
    pipeline_context["QA2_fluxgains"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context


# Alias for backward compatibility
EVLA_pipe_fluxgains = fluxgains
