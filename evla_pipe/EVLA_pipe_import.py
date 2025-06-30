# EVLA_pipe_import.py
import os
import shutil
from casatasks import importasdm
from .utils import runtiming, logprint
from . import pipeline_save  # We might reconsider this later

def import_data(pipeline_context):
    """
    Imports the SDM data into a CASA measurement set.

    Args:
        pipeline_context (dict): A dictionary containing the pipeline's context,
                                 including variables like SDM_name and msname.

    Returns:
        dict: Updated pipeline context. Returns "Fail" if critical parameters are missing.
    """
    SDM_name = pipeline_context.get("SDM_name")
    msname = pipeline_context.get("msname")

    if not SDM_name or not msname:
        logprint("Error: Missing SDM_name or msname in pipeline context for import_data.", logfileout="logs/import.log")
        return "Fail"

    task_logprint = lambda msg: logprint(msg, logfileout="logs/import.log")
    task_logprint("*** Starting import_data ***")
    time_list = runtiming("import", "start")
    QA2_import = "Pass"

    if not os.path.exists(msname):
        task_logprint("Creating measurement set")
        try:
            importasdm(
                asdm=SDM_name,
                vis=msname,
                ocorr_mode="co",
                compression=False,
                asis="",
                process_flags=True,
                applyflags=False,
                savecmds=True,
                outfile="onlineFlags.txt",
                flagbackup=False,
                overwrite=False,
                verbose=True,
                # FIXME keyword arguments in latest versions of CASA
                #with_pointing_correction=True,
                #process_pointing=True,
                #process_caldevice=True,
            )
            task_logprint(f"Measurement set '{msname}' created")
            task_logprint("Copying xml files to the output ms")
            for xml_file in ("Flag", "Antenna", "SpectralWindow"):
                shutil.copy2(f"{SDM_name}/{xml_file}.xml", f"{msname}/")
        except Exception as e:
            task_logprint(f"Error during importasdm: {e}")
            QA2_import = "Fail"
    else:
        task_logprint(f"Measurement set already exists, will use '{msname}'")

    task_logprint("Finished import_data")
    task_logprint(f"QA2 score: {QA2_import}")
    time_list = runtiming("import", "end")

    # pipeline_save() # We'll handle saving in the main orchestration

    return pipeline_context