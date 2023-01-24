"""
Determine the solution interval for scan-average equivalent. First split out
gain calibrators and drop flagged rows.

Notes
-----
* In CASA 3.3 gaincal doesn't entirely ignore flagged rows, so for now
  include them in the split below; WILL NEED TO CHANGE TO "keepflags=False"
  FOR CASA 3.4, or use Bryan's method for identifying unflagged data
  in the main ms.
* Modified using Brian's code for the flagged data as described in CAS-10130
"""

from casatasks import rmtables, split
from casatools import ms as mstool

from . import pipeline_save
from .utils import logprint, runtiming

ms = mstool()


def task_logprint(msg):
    logprint(msg, logfileout="logs/solint.log")


task_logprint("Starting EVLA_pipe_solint.py")
time_list = runtiming("solint", "start")
QA2_solint = "Pass"

# Split out calibrators, dropping flagged data; note that it may be
# important *not* to select on field ID, so that fields don't get
# renumbered by split

task_logprint("Splitting out calibrators into calibrators.ms")

rmtables("calibrators.ms")
split(
    vis=ms_active,
    outputvis="calibrators.ms",
    datacolumn="corrected",
    field="",
    spw="",
    width=int(max(channels)),
    antenna="",
    timebin="0s",
    timerange="",
    scan=calibrator_scan_select_string,
    intent="",
    array="",
    uvrange="",
    correlation="",
    observation="",
    keepflags=False,
)

ms.open("calibrators.ms")
scan_summary = ms.getscansummary()
durations = []
old_spws = []
old_field = ""
day_in_s = 86400  # s
for kk, ii in enumerate(phase_scan_list):
    summary = scan_summary[str(ii)]
    try:
        endtimes = [v["EndTime"] for v in summary.values()]
        begintimes = [v["BeginTime"] for v in summary.values()]
        end_time = max(endtimes)
        begin_time = min(begintimes)
        new_spws = summary["0"]["SpwIds"]
        new_field = summary["0"]["FieldId"]
        # if contiguous scans then just increase the time on the previous one
        if (
            kk > 0
            and phase_scan_list[kk - 1] == ii - 1
            and set(new_spws) == set(old_spws)
            and new_field == old_field
        ):
            durations[-1] = day_in_s * (end_time - old_begin_time)
        else:
            durations.append(day_in_s * (end_time - begin_time))
            old_begin_time = begin_time
        task_logprint(f"Scan {ii} has {durations[-1]}s on source")
        ms.reset()
        old_spws = new_spws
        old_field = new_field
    except KeyError:
        task_logprint(
            f"WARNING: scan {ii} is completely flagged and missing from 'calibrators.ms'"
        )
ms.close()

longsolint = max(durations) * 1.01
gain_solint2 = f"{longsolint}s"

# Until we know what the QA criteria are for this script, leave QA2
# set score to "Pass".

task_logprint(f"QA2 score: {QA2_solint}")
task_logprint("Finished EVLA_pipe_solint.py")
time_list = runtiming("solint", "end")

pipeline_save()
