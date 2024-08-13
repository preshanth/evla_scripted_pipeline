"""
Check the flags before final calibration, apply all calibrations and check
calibrated data, and check the flags after final calibration.
"""

import copy

from casatasks import flagdata, applycal

from . import pipeline_save
from .utils import logprint, runtiming


def task_logprint(msg):
    logprint(msg, logfileout="logs/applycals.log")


task_logprint("*** Starting EVLA_pipe_applycals.py ***")
time_list = runtiming("applycals", "start")
QA2_applycals = "Pass"

myinitialflags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)
task_logprint("Finished flags summary before final applycal.")


FinalGainTables = copy.copy(priorcals)
FinalGainTables.append("finaldelay.k")
FinalGainTables.append("finalBPcal.b")
FinalGainTables.append("averagephasegain.g")
FinalGainTables.append("finalampgaincal.g")
FinalGainTables.append("finalphasegaincal.g")
ntables = len(FinalGainTables)

applycal(
    vis=ms_active,
    field="",
    spw="",
    intent="",
    selectdata=False,
    gaintable=FinalGainTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
    calwt=[False] * ntables,
    applymode="calflagstrict",
    flagbackup=True,
)


myinitialflags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)
task_logprint("Finished flags summary after final applycal.")


# TODO
# Check calibrated data for more flagging
# Plot "corrected" datacolumn for calibrators in plotms
# Plot "corrected" datacolumn for targets
# Amp vs. freq, amp vs. time

# Until we understand better the failure modes of this task, leave
# QA2 score set to "Pass".

logprint(f"QA2 score: {QA2_applycals}")
logprint("Finished EVLA_pipe_applycals.py")
time_list = runtiming("applycals", "end")

pipeline_save()
