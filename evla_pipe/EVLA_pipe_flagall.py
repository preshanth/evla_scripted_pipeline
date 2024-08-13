"""
Perform deterministic flagging using `flagdata` in list-mode: online flags,
zeros, pointing scans, and quacking.
"""
# NOTE Urvashi Rao points out that it may be possible to consolidate these to
# run faster (minus the flagcmd step) using the toolkit, see:
#     http://www.aoc.nrao.edu/~rurvashi/ActiveFlaggerDocs/node11.html

from casatasks import flagdata, flagmanager

from . import pipeline_save
from .utils import runtiming, logprint


def task_logprint(msg):
    logprint(msg, logfileout="logs/flagall.log")


# Apply deterministic flags
task_logprint("*** Starting EVLA_pipe_flagall.py ***")
time_list = runtiming("flagall", "start")
QA2_flagall = "Pass"

task_logprint("Deterministic flagging")

outputflagfile = "flagging_commands1.txt"
os.system(f"rm -rf {outputflagfile}")

task_logprint(
    "Determine fraction of time on-source (may not be correct for pipeline re-runs on datasets already flagged)"
)

# Report initial statistics
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
task_logprint("Initial flagged fraction = " + str(start_flagged / start_total))
#adding a test comment...
online_flag_name = msname.rstrip("ms") + "flagonline.txt"
if os.path.isfile(online_flag_name):
    flagdata(
        vis=ms_active,
        mode="list",
        inpfile=online_flag_name,
        tbuff=1.5 * int_time,
        reason="ANTENNA_NOT_ON_SOURCE",
        action="apply",
        flagbackup=True,
        savepars=True,
        outfile=outputflagfile,
    )
    task_logprint("ANTENNA_NOT_ON_SOURCE flags carried out")
else:
    task_logprint("No Online flags txt file! ANTENNA_NOT_ON_SOURCE flags NOT carried out!!")

# Now shadow flagging
flagdata(
    vis=ms_active,
    mode="shadow",
    tolerance=0.0,
    action="apply",
    flagbackup=False,
    savepars=False,
)

# Report new statistics
slewshadowflags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)

init_on_source_vis = start_total - slewshadowflags["flagged"]

task_logprint("Initial on-source fraction = " + str(init_on_source_vis / start_total))

try:
    # Restore original flags
    flagmanager(
        vis=ms_active,
        mode="restore",
        versionname="flagdata_1",
        merge="replace",
    )
except:
    task_logprint("Cannot restore original flags!")

os.system(f"rm -rf {outputflagfile}")

# First do zero flagging (reason='CLIP_ZERO_ALL')
myzeroflags = flagdata(
    vis=ms_active,
    mode="clip",
    correlation="ABS_ALL",
    clipzeros=True,
    action="apply",
    flagbackup=False,
    savepars=False,
    outfile=outputflagfile,
)
task_logprint("Zero flags carried out")

# Now report statistics
myafterzeroflags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)
task_logprint("Zero flags summary")

afterzero_total = myafterzeroflags["total"]
afterzero_flagged = myafterzeroflags["flagged"]
task_logprint(
    "After ZERO flagged fraction = " + str(afterzero_flagged / afterzero_total)
)

zero_flagged = myafterzeroflags["flagged"] - myinitialflags["flagged"]
task_logprint("Delta ZERO flagged fraction = " + str(zero_flagged / afterzero_total))

# Now shadow flagging
flagdata(
    vis=ms_active,
    mode="shadow",
    tolerance=0.0,
    action="apply",
    flagbackup=False,
    savepars=False,
)
task_logprint("Shadow flags carried out")

# Now report statistics after shadow
myaftershadowflags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)
task_logprint("Shadow flags summary")

aftershadow_total = myaftershadowflags["total"]
aftershadow_flagged = myaftershadowflags["flagged"]
task_logprint(
    "After SHADOW flagged fraction = " + str(aftershadow_flagged / aftershadow_total)
)

shadow_flagged = myaftershadowflags["flagged"] - myafterzeroflags["flagged"]
task_logprint(
    "Delta SHADOW flagged fraction = " + str(shadow_flagged / aftershadow_total)
)

if os.path.isfile(online_flag_name):
    flagdata(
        vis=ms_active,
        mode="list",
        inpfile=online_flag_name,
        tbuff=1.5 * int_time,
        reason="any",
        action="apply",
        flagbackup=False,
        savepars=True,
        outfile=outputflagfile,
    )

    task_logprint("Online flags applied")
else:
    task_logprint("No online flags applied!")

# Define list of flagdata parameters to use in 'list' mode
flagdata_list = []
cmdreason_list = []

# Flag pointing scans, if there are any
if len(pointing_state_IDs) != 0:
    task_logprint("Flag pointing scans")
    flagdata_list.append("mode='manual' intent='*POINTING*'")
    cmdreason_list.append("pointing")

# Flag setup scans
task_logprint("Flag setup scans")
flagdata_list.append("mode='manual' intent='UNSPECIFIED#UNSPECIFIED'")
cmdreason_list.append("setup")

task_logprint("Flag setup scans")
flagdata_list.append("mode='manual' intent='SYSTEM_CONFIGURATION#UNSPECIFIED'")
cmdreason_list.append("setup")

# Quack the data
task_logprint("Quack the data")
flagdata_list.append(
    "mode='quack'"
    + f" scan={quack_scan_string}"
    + f" quackinterval={1.5*int_time}"
    + " quackmode='beg'"
    + " quackincrement=False"
)
cmdreason_list.append("quack")


######################################################################
# FLAG SOME MORE STUFF (CHANNEL-BASED)
# Flag end 3 channels of each spw
task_logprint("Flag end 5 percent of each spw or minimum of 3 channels")

SPWtoflag = ""

for ispw in range(numSpws):
    fivepctch = int(0.05 * channels[ispw])
    startch1 = 0
    startch2 = fivepctch - 1
    endch1 = channels[ispw] - fivepctch
    endch2 = channels[ispw] - 1
    # Minimum number of channels flagged must be three on each end
    if fivepctch < 3:
        startch2 = 2
        endch1 = channels[ispw] - 3
    SPWtoflag += f"{ispw}:{startch1}~{startch2};{endch1}~{endch2},"
SPWtoflag = SPWtoflag.rstrip(",")

flagdata_list.append(f"mode='manual' spw='{SPWtoflag}'")
cmdreason_list.append("spw_ends")

# Flag 10 end channels at edges of basebands
#
# NB: assumes continuum set-up that fills baseband; will want to modify
# for narrow spws or spectroscopy!
#
bottomSPW = ""
topSPW = ""

for ii in range(len(low_spws)):
    if ii == 0:
        bspw = low_spws[ii]
        tspw = high_spws[ii]
        endch1 = channels[tspw] - 10
        endch2 = channels[tspw] - 1
        bottomSPW = str(bspw) + ":0~9"
        topSPW = str(tspw) + ":" + str(endch1) + "~" + str(endch2)
    else:
        bspw = low_spws[ii]
        tspw = high_spws[ii]
        endch1 = channels[tspw] - 10
        endch2 = channels[tspw] - 1
        bottomSPW = bottomSPW + "," + str(bspw) + ":0~9"
        topSPW = topSPW + "," + str(tspw) + ":" + str(endch1) + "~" + str(endch2)

if bottomSPW != "":
    task_logprint("Flag end 10 channels at edges of basebands")
    SPWtoflag = bottomSPW + "," + topSPW
    flagdata_list.append("mode='manual' spw='" + SPWtoflag + "'")
    cmdreason_list.append("baseband_edge_chans")

# Write out list for use in flagdata mode 'list'
with open(outputflagfile, "a") as f:
    for line in flagdata_list:
        f.write(line + "\n")

# Apply all flags
task_logprint("Applying all flags to data")

flagdata(
    vis=ms_active,
    mode="list",
    inpfile=outputflagfile,
    action="apply",
    flagbackup=False,
    savepars=True,
    cmdreason=",".join(cmdreason_list),
)

task_logprint("Flagging completed ")
task_logprint(f"Flag commands saved in file {outputflagfile}")

# Save flags
task_logprint("Saving flags")

flagmanager(
    vis=ms_active,
    mode="save",
    versionname="allflags1",
    comment="Deterministic flags saved after application",
    merge="replace",
)
task_logprint(f"Flag column saved to 'allflags1'")

# Report new statistics
all_flags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)

frac_flagged_on_source1 = 1.0 - (
    (start_total - all_flags["flagged"]) / init_on_source_vis
)

task_logprint("Fraction of on-source data flagged = " + str(frac_flagged_on_source1))

if frac_flagged_on_source1 >= 0.3:
    QA2_flagall = "Fail"

task_logprint("Finished EVLA_pipe_flagall.py")
task_logprint("QA2 score: " + QA2_flagall)
time_list = runtiming("flagall", "end")

pipeline_save()

