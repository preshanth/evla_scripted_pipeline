"""
Prepare for calibrations
========================

Fill models for all primary calibrators.
NB: in CASA 3.4.0 can only set models based on field ID and spw, not
by intents or scans

"""

from casatasks import setjy

from . import pipeline_save
from .utils import runtiming, logprint, find_standards, find_EVLA_band


def task_logprint(msg):
    logprint(msg, logfileout="logs/calprep.log")


task_logprint("*** Starting EVLA_pipe_calprep.py ***")
time_list = runtiming("calprep", "start")
QA2_calprep = "Pass"

task_logprint("Setting models for standard primary calibrators")

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
        spws = field_spws[field]
        for spw in spws:
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
            except:
                task_logprint(f"no data found for field {field} spw {spw}")

task_logprint("Finished setting models for known calibrators")

task_logprint("Finished EVLA_pipe_calprep.py")
task_logprint(f"QA2 score: {QA2_calprep}")
time_list = runtiming("calprep", "end")

pipeline_save()
