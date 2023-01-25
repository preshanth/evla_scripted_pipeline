"""
Check the flagging of all calibrated data, including target using the `rflag`
mode of `flagdata`.
"""

from casatasks import flagdata, flagmanager

from .utils import logprint, runtiming


def task_logprint(msg):
    logprint(msg, logfileout="logs/targetflag.log")


task_logprint("Starting EVLA_pipe_targetflag.py")
time_list = runtiming("checkflag", "start")
QA2_targetflag = "Pass"

task_logprint("Checking RFI flagging of all targets")

# Run on all calibrator scans
flagdata(
    vis=ms_active,
    mode="rflag",
    field="",
    correlation="ABS_" + corrstring,
    scan="",
    intent="*CALIBRATE*",
    ntime="scan",
    combinescans=False,
    datacolumn="corrected",
    winsize=3,
    timedevscale=4.0,
    freqdevscale=4.0,
    extendflags=False,
    action="apply",
    display="",
    flagbackup=True,
    savepars=True,
)

# Run on all target scans
# Comment out if science target has strong spectral lines
# or set spw to exclude these strong science spectral lines
flagdata(
    vis=ms_active,
    mode="rflag",
    field="",
    correlation="ABS_" + corrstring,
    scan="",
    intent="*TARGET*",
    ntime="scan",
    combinescans=False,
    datacolumn="corrected",
    winsize=3,
    timedevscale=4.0,
    freqdevscale=4.0,
    extendflags=False,
    action="apply",
    display="",
    flagbackup=True,
    savepars=True,
)

# Save final version of flags
flagmanager(
    vis=ms_active,
    mode="save",
    versionname="finalflags",
    comment="Final flags saved after calibrations and rflag",
    merge="replace",
)
task_logprint(f"Flag column saved to 'finalflags'")

# Calculate final flag statistics
final_flags = flagdata(
    vis=ms_active,
    mode="summary",
    spwchan=True,
    spwcorr=True,
    basecnt=True,
    action="calculate",
    savepars=False,
)

frac_flagged_on_source2 = 1.0 - (
    (start_total - final_flags["flagged"]) / init_on_source_vis
)

task_logprint(f"Final fraction of on-source data flagged = {frac_flagged_on_source2}")

if frac_flagged_on_source2 >= 0.6:
    QA2_targetflag = "Fail"

task_logprint(f"QA2 score: {QA2_targetflag}")
task_logprint("Finished EVLA_pipe_targetflag.py")
time_list = runtiming("targetflag", "end")

pipeline_save()
