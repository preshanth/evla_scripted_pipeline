# set_standard_models.py

from casatasks import setjy

from evla_pipe.pol_setjy_utils import integrate_polarization_setjy
from evla_pipe.utils import (
    _extract_position_tuples,
    find_EVLA_band,
    find_standards,
    format_qa_status,
    logprint,
    runtiming,
)


def task_logprint(msg):
    logprint(msg, logfileout="logs/fluxgains_setjy.log")


def set_standard_source_models(
    pipeline_context, field_positions, field_spws, center_frequencies, scratch
):
    """
    Set models for standard primary calibrators using setjy.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
        field_positions (numpy.ndarray): Array of field positions.
        field_spws (dict): Dictionary mapping field IDs to spectral window IDs.
        center_frequencies (dict): Dictionary mapping spectral window IDs to center frequencies.
        scratch (bool): Use scratch columns in the MS.
    """
    task_logprint("*** Starting set_standard_source_models.py ***")
    runtiming("fluxgains_setjy", "start")

    calibrators_ms = pipeline_context.get(
        "msname", "calibrators.ms"
    )  # Default to calibrators.ms
    standard_source_names = ["3C48", "3C138", "3C147", "3C286"]
    task_logprint("TEST:running find_standards")
    # Convert CASA measure dictionaries to position tuples
    positions = _extract_position_tuples(field_positions)
    standard_source_fields = find_standards(positions)
    task_logprint("TEST:find_standards complete")

    for ii, fields in enumerate(standard_source_fields):
        for myfield in fields:
            # field_spws is a list, not a dict - index by field number
            if myfield < len(field_spws) and field_spws[myfield] is not None:
                myfield_spws = field_spws[myfield]
                for myspw in myfield_spws:
                    # center_frequencies might be a list, not a dict - handle both cases
                    if isinstance(center_frequencies, dict):
                        reference_frequency = center_frequencies.get(myspw)
                    elif isinstance(center_frequencies, list) and myspw < len(
                        center_frequencies
                    ):
                        reference_frequency = center_frequencies[myspw]
                    else:
                        reference_frequency = None
                    if reference_frequency is not None:
                        EVLA_band = find_EVLA_band(reference_frequency)
                        task_logprint(
                            f"Center freq for spw {myspw} (field {myfield}) = {reference_frequency}, "
                            f"observing band = {EVLA_band}"
                        )
                        model_image = f"{standard_source_names[ii]}_{EVLA_band}.im"
                        task_logprint(
                            f"Setting model for field {myfield} spw {myspw} using {model_image}"
                        )
                        try:
                            # Set full polarization models directly
                            field_name = standard_source_names[ii]
                            task_logprint(
                                f"Setting full polarization models for {field_name}"
                            )

                            integrate_polarization_setjy(
                                vis=calibrators_ms,
                                field_id=myfield,
                                field_name=field_name,
                                spws=[myspw],
                                band=EVLA_band,
                                ref_freq_hz=reference_frequency
                                * 1e9,  # Convert GHz to Hz
                                obs_date=None,  # Will use 2019 data by default
                                use_model_image=model_image,  # Include the model image
                                standard="Perley-Butler 2017",  # Pass through the standard
                                usescratch=scratch,
                            )
                            task_logprint(
                                f"Successfully set full polarization models for {field_name}"
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
                            except Exception as fallback_e:
                                task_logprint(
                                    f"Fallback setjy also failed for field {myfield}: {fallback_e}"
                                )
                else:
                    task_logprint(
                        f"Warning: Center frequency not found for spw {myspw} (field {myfield})"
                    )

    runtiming("fluxgains_setjy", "end")


def EVLA_pipe_fluxgains(pipeline_context):
    """
    Main entry point for EVLA_pipe_fluxgains pipeline step.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_fluxgains.py ***")
    time_list = runtiming("fluxgains", "start")

    # Extract variables from context
    pipeline_context.get("msname", "")

    try:
        # Extract required parameters from context
        field_positions = pipeline_context.get("field_positions")
        field_spws = pipeline_context.get("field_spws")
        center_frequencies = pipeline_context.get("center_frequencies")
        scratch = pipeline_context.get("usescratch", False)

        if (
            field_positions is not None
            and field_spws is not None
            and center_frequencies is not None
        ):
            set_standard_source_models(
                pipeline_context,
                field_positions,
                field_spws,
                center_frequencies,
                scratch,
            )
            QA2_score = "Pass"
        else:
            task_logprint("Missing required parameters for set_standard_source_models")
            QA2_score = "Fail"
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_fluxgains: {e}")
        QA2_score = "Fail"

    task_logprint("Finished EVLA_pipe_fluxgains.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("fluxgains", "end")

    # Update context and return
    pipeline_context["QA2_fluxgains"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context
