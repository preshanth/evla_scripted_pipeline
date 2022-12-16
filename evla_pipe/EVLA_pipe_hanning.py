import os
import shutil
from glob import glob

from casatasks import hanningsmooth

from . import pipeline_save
from .utils import (runtiming, logprint)


def task_logprint(msg):
    logprint(msg, logfileout="logs/hanning.log")


task_logprint("Starting EVLA_pipe_hanning.py")
time_list = runtiming('hanning', 'start')
QA2_hanning = "Pass"

if do_hanning:
    task_logprint("Hanning smoothing the data")
    hanningsmooth(
        vis=msname,
        datacolumn="data",
        outputvis="temphanning.ms",
    )

    task_logprint("Copying xml files to the output ms")
    for filen in glob(f"{msname}/*.xml"):
        shutil.copy2(filen , "temphanning.ms/")
    task_logprint(f"Removing original VIS {msname}")
    shutil.rmtree(msname)

    task_logprint(f"Renaming temphanning.ms to {msname}")
    os.rename("temphanning.ms", msname)
else:
    task_logprint("NOT Hanning smoothing the data")

# Until we know better the possible failures modes of this script,
# leave set QA2 score set to "Pass".

task_logprint("Finished EVLA_pipe_hanning.py")
task_logprint(f"QA2 score: {QA2_hanning}")
time_list = runtiming("hanning", "end")

pipeline_save()

