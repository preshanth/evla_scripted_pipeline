# EVLA_pipe_calprep.py (Refactored)

from casatasks import setjy
from casatools import measures as mstool
from . import pipeline_save
from .utils import runtiming, logprint, find_EVLA_band, find_standards  # Assuming find_standards is in utils

me = mstool()

def task_logprint(msg):
    logprint(msg, logfileout="logs/calprep.log")

def EVLA_pipe_calprep(pipeline_context):
    """
    Prepare for calibrations: Set models for primary calibrators.
    """
    task_logprint("*** Starting EVLA_pipe_calprep.py (Refactored) ***")
    time_list = runtiming("calprep", "start")
    QA2_calprep = "Pass"

    ms_active = pipeline_context.get("msname")
    field_positions = pipeline_context.get("field_positions")
    field_spws = pipeline_context.get("field_spws")
    center_frequencies = pipeline_context.get("center_frequencies")
    scratch = True  # Setting scratch to True directly

    task_logprint("Setting models for standard primary calibrators")

    if field_positions is None:
        task_logprint("ERROR: field_positions not found in pipeline context.")
        QA2_calprep = "Fail"
    else:
        positions = field_positions.T.squeeze()
        standard_source_names = ["3C48", "3C138", "3C147", "3C286"]
        standard_source_fields = find_standards(positions)

        standard_source_found = any(standard_source_fields)
        if not standard_source_found:
            task_logprint(
                "ERROR: No standard flux density calibrator observed, flux density scale will be arbitrary."
            )
            QA2_calprep = "Fail"

        for ii, fields in enumerate(standard_source_fields):
            for field in fields:
                if field < len(field_spws):
                    spws = field_spws[field]
                    for spw in spws:
                        if spw < len(center_frequencies):
                            reference_frequency = center_frequencies[spw]
                            EVLA_band = find_EVLA_band(reference_frequency)
                            task_logprint(
                                f"Center freq for spw {spw} = {reference_frequency}, observing band = {EVLA_band}"
                            )
                            model_image = f"{standard_source_names[ii]}_{EVLA_band}.im"
                            task_logprint(
                                f"Setting model for field {field} spw {spw} using {model_image}"
                            )
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
                            except Exception as e:
                                task_logprint(f"Error settingjy for field {field} spw {spw}: {e}")
                        else:
                            task_logprint(f"WARNING: center_frequencies index {spw} out of range.")
                else:
                    task_logprint(f"WARNING: field_spws index {field} out of range.")

    task_logprint("Finished setting models for known calibrators")

    task_logprint("Finished EVLA_pipe_calprep.py (Refactored)")
    task_logprint(f"QA2 score: {QA2_calprep}")
    time_list = runtiming("calprep", "end")

    pipeline_save(pipeline_context)  # Ensure pipeline context is passed for saving
    return pipeline_context