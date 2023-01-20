"""
Check flagging of bandpass and delay calibrators using `rflag` mode
of `flagdata`.
"""

from casatasks import flagdata

from . import pipeline_save
from .utils import logprint, runtiming


def task_logprint(msg):
    logprint(msg, logfileout="logs/checkflag.log")


task_logprint("Starting EVLA_pipe_checkflag.py")
time_list = runtiming("checkflag", "start")
QA2_checkflag = "Pass"

task_logprint("Checking RFI flagging of BP and Delay Calibrators")

checkflagfields = bandpass_field_select_string
if bandpass_field_select_string != delay_field_select_string:
    checkflagfields += "," + delay_field_select_string

# Run only on the bandpass and delay calibrators - testgainscans
flagdata(
    vis=ms_active,
    mode="rflag",
    field=checkflagfields,
    correlation="ABS_" + corrstring,
    scan=testgainscans,
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

task_logprint(f"QA2 score: {QA2_checkflag}")
task_logprint("Finished EVLA_pipe_checkflag.py")
time_list = runtiming("checkflag", "end")

pipeline_save()
