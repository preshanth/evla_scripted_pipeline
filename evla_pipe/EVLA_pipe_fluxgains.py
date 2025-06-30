# set_standard_models.py

from casatasks import setjy
from .utils import (
        logprint,
        find_standards,
        find_EVLA_band,
)

def task_logprint(msg):
    logprint(msg, logfileout="logs/fluxgains_setjy.log")

def set_standard_source_models(pipeline_context, field_positions, field_spws, center_frequencies, scratch):
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

    calibrators_ms = pipeline_context.get("msname", "calibrators.ms") # Default to calibrators.ms
    standard_source_names = ["3C48", "3C138", "3C147", "3C286"]
    standard_source_fields = find_standards(field_positions)

    for ii, fields in enumerate(standard_source_fields):
        for myfield in fields:
            for myspw in field_spws.get(myfield, []):
                reference_frequency = center_frequencies.get(myspw)
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
                    except Exception as e:
                        task_logprint(f"Error settingjy for field {myfield} spw {myspw}: {e}")
                else:
                    task_logprint(f"Warning: Center frequency not found for spw {myspw} (field {myfield})")

    runtiming("fluxgains_setjy", "end")