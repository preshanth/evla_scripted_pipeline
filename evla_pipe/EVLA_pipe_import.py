import os
import shutil

from casatasks import importasdm

from . import pipeline_save
from .utils import (runtiming, logprint)


def task_logprint(msg):
    logprint(msg, logfileout="logs/import.log")


task_logprint("*** Starting EVLA_pipe_import.py ***")
time_list = runtiming("import", "start")
QA2_import = "Pass"

if not os.path.exists(msname):
    task_logprint("Creating measurement set")
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
else:
    task_logprint(f"Measurement set already exists, will use '{msname}'")

# Until we understand better the possible failure modes to look for
# in this script, leave QA2 set to "Pass".

task_logprint("Finished EVLA_pipe_import.py")
task_logprint(f"QA2 score: {QA2_import}")
time_list = runtiming("import", "end")

pipeline_save()

