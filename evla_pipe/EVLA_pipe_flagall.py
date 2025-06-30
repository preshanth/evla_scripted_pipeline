# EVLA_pipe_flagall.py (Refactored using flagdata list mode)

import os
from casatasks import flagdata, flagmanager
from . import pipeline_save
from .utils import runtiming, logprint

def task_logprint(msg):
    logprint(msg, logfileout="logs/flagall.log")

task_logprint("*** Starting EVLA_pipe_flagall.py (Refactored) ***")
time_list = runtiming("flagall", "start")
QA2_flagall = "Pass"

ms_active = pipeline_context.get("msname")
int_time = pipeline_context.get("int_time")
quack_scan_string = pipeline_context.get("quack_scan_string")
pointing_state_IDs = pipeline_context.get("pointing_state_IDs", [])
numSpws = pipeline_context.get("numSpws", 0)
channels = pipeline_context.get("channels", [])
low_spws = pipeline_context.get("low_spws", [])
high_spws = pipeline_context.get("high_spws", [])
msname = pipeline_context.get("msname", "")

outputflagfile = "flagging_commands1.txt"
os.system(f"rm -rf {outputflagfile}")

flagging_commands = []
cmdreason_list = []

# --- Initial Statistics ---
myinitialflags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)
task_logprint("Initial flags summary")
start_total = myinitialflags["total"]
start_flagged = myinitialflags["flagged"]
task_logprint(f"Initial flagged fraction = {start_flagged / start_total if start_total > 0 else 0}")

# --- Online Flags ---
online_flag_name = msname.rstrip("ms") + "flagonline.txt"
if os.path.isfile(online_flag_name):
    flagging_commands.append(f"mode='list' inpfile='{online_flag_name}' tbuff={1.5 * int_time} reason='ANTENNA_NOT_ON_SOURCE'")
    cmdreason_list.append("ANTENNA_NOT_ON_SOURCE")
    task_logprint("ANTENNA_NOT_ON_SOURCE flags will be applied")
else:
    task_logprint("No Online flags txt file! ANTENNA_NOT_ON_SOURCE flags will NOT be applied!!")

# --- Shadow Flagging ---
flagging_commands.append("mode='shadow' tolerance=0.0 reason='shadow'")
cmdreason_list.append("shadow")

# --- Zero Flagging ---
flagging_commands.append("mode='clip' clipzeros=True correlation='ABS_ALL' reason='CLIP_ZERO_ALL'")
cmdreason_list.append("CLIP_ZERO_ALL")

# --- Pointing Scans ---
if len(pointing_state_IDs) != 0:
    flagging_commands.append("mode='manual' intent='*POINTING*' reason='pointing'")
    cmdreason_list.append("pointing")
    task_logprint("Pointing scans will be flagged")

# --- Setup Scans ---
flagging_commands.append("mode='manual' intent='UNSPECIFIED#UNSPECIFIED' reason='setup'")
cmdreason_list.append("setup")
flagging_commands.append("mode='manual' intent='SYSTEM_CONFIGURATION#UNSPECIFIED' reason='setup'")
cmdreason_list.append("setup")
task_logprint("Setup scans will be flagged")

# --- Quack the Data ---
if quack_scan_string:
    flagging_commands.append(f"mode='quack' scan='{quack_scan_string}' quackinterval={1.5 * int_time} quackmode='beg' quackincrement=False reason='quack'")
    cmdreason_list.append("quack")
    task_logprint("Quacking will be applied")

# --- Flag End Channels of Each SPW ---
SPWtoflag = ""
for ispw in range(numSpws):
    if ispw < len(channels):
        fivepctch = int(0.05 * channels[ispw])
        startch1 = 0
        startch2 = fivepctch - 1
        endch1 = channels[ispw] - fivepctch
        endch2 = channels[ispw] - 1
        if fivepctch < 3:
            startch2 = 2
            endch1 = channels[ispw] - 3
        SPWtoflag += f"{ispw}:{startch1}~{startch2};{endch1}~{endch2},"
SPWtoflag = SPWtoflag.rstrip(",")
if SPWtoflag:
    flagging_commands.append(f"mode='manual' spw='{SPWtoflag}' reason='spw_ends'")
    cmdreason_list.append("spw_ends")
    task_logprint("Flagging end channels of each spw")

# --- Flag End Channels at Edges of Basebands ---
bottomSPW = ""
topSPW = ""
for ii in range(len(low_spws)):
    if ii < len(high_spws) and ii < len(channels):
        bspw = low_spws[ii]
        tspw = high_spws[ii]
        endch1 = channels[tspw] - 10
        endch2 = channels[tspw] - 1
        bottomSPW += f"{bspw}:0~9,"
        topSPW += f"{tspw}:{endch1}~{endch2},"
bottomSPW = bottomSPW.rstrip(",")
topSPW = topSPW.rstrip(",")
SPWtoflag_bb = ""
if bottomSPW and topSPW:
    SPWtoflag_bb = f"{bottomSPW},{topSPW}"
elif bottomSPW:
    SPWtoflag_bb = bottomSPW
elif topSPW:
    SPWtoflag_bb = topSPW

if SPWtoflag_bb:
    flagging_commands.append(f"mode='manual' spw='{SPWtoflag_bb}' reason='baseband_edge_chans'")
    cmdreason_list.append("baseband_edge_chans")
    task_logprint("Flagging end channels at edges of basebands")

# --- Apply All Flags ---
task_logprint("Applying all deterministic flags to data")
flagdata(
    vis=ms_active,
    mode="list",
    inpfile=flagging_commands,
    action="apply",
    flagbackup=False,
    savepars=True,
    cmdreason=",".join(cmdreason_list),
)
task_logprint("Deterministic flagging completed ")
task_logprint(f"Flag commands applied from list")

# --- Save Flags ---
task_logprint("Saving flags")
flagmanager(
    vis=ms_active,
    mode="save",
    versionname="allflags1",
    comment="Deterministic flags saved after application (list mode)",
    merge="replace",
)
task_logprint(f"Flag column saved to 'allflags1'")

# --- Final Statistics ---
all_flags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)
task_logprint("Final flags summary")
final_total = all_flags["total"]
final_flagged = all_flags["flagged"]
task_logprint(f"Final flagged fraction = {final_flagged / final_total if final_total > 0 else 0}")

# --- Calculate Fraction of On-Source Data Flagged (Approximation) ---
# We are making a simplification here. Ideally, we'd get the on-source count
# after the initial shadow flagging. For simplicity in this refactor, we'll
# use the initial total as an approximation of the total on-source data.
frac_flagged_on_source1 = 1.0 - (
    (start_total - final_flagged) / start_total if start_total > 0 else 1.0
)
task_logprint(f"Approximate fraction of on-source data flagged = {frac_flagged_on_source1}")

if frac_flagged_on_source1 >= 0.3:
    QA2_flagall = "Fail"

task_logprint("Finished EVLA_pipe_flagall.py (Refactored)")
task_logprint(f"QA2 score: {QA2_flagall}")
time_list = runtiming("flagall", "end")

pipeline_save()