"""
Check flagging of all calibrators using `rflag` mode of `flagdata`.
"""

from casatasks import flagdata

from . import pipeline_save
from .utils import logprint, runtiming


def task_logprint(msg):
    logprint(msg, logfileout="logs/checkflag.log")


task_logprint("Starting EVLA_pipe_checkflag_semiFinal.py")
time_list = runtiming("checkflag_semiFinal", "start")
QA2_checkflag_semiFinal = "Pass"

task_logprint("Checking RFI flagging of all calibrators")

flagdata(
    vis=ms_active,
    mode="rflag",
    field=calibrator_field_select_string,
    correlation="ABS_" + corrstring,
    scan=calibrator_scan_select_string,
    ntime="scan",
    combinescans=False,
    datacolumn="corrected",
    winsize=3,
    timedevscale=4.0,
    freqdevscale=4.0,
    extendflags=False,
    action="apply",
    display="",
    flagbackup=False,
    savepars=True,
)

# Until we know what the QA criteria are for this script, leave QA2
# set score to "Pass".

task_logprint(f"QA2 score: {QA2_checkflag_semiFinal}")
task_logprint("Finished EVLA_pipe_checkflag_semiFinal.py")
time_list = runtiming("checkflag_semiFinal", "end")

pipeline_save()
