"""
Move relevant plots and tables after calibration is complete.
"""

import os
import stat
import glob
import shutil
import copy
from time import gmtime, strftime

from . import __version_str__, pipeline_save
from .utils import logprint, runtiming


def task_logprint(msg):
    logprint(msg, logfileout="logs/filecollect.log")


task_logprint("Starting EVLA_pipe_filecollect.py")
time_list = runtiming("filecollect", "start")

caltables_dir = "./final_caltables"
weblog_dir = "./weblog"

# FIXME move to using `pathlib`
# Check if directories exists - if not create one
if not os.path.exists(caltables_dir):
    os.makedirs(caltables_dir)

if not os.path.exists(weblog_dir):
    os.makedirs(weblog_dir)

# Move all png files/plots
png_files = glob.glob("./*.png")
for filen in png_files:
    try:
        shutil.move(filen, weblog_dir + "/.")
    except:
        task_logprint(f"Unable to move {filen}")

task_logprint(f"Plots moved to {weblog_dir}")

# Listobs output
listobs_output = glob.glob("./*.listobs")
for filen in listobs_output:
    try:
        shutil.move(filen, weblog_dir + "/.")
    except:
        logprint(f"Unable to move {filen}")

# Move calibration tables into caltables_dir
cal_files = copy.copy(priorcals)
for caltable in (
        "switched_power.g", "fluxgaincal.g", "finaldelay.k", "finalBPcal.b",
        "averagephasegain.g", "finalampgaincal.g", "finalphasegaincal.g"
):
    cal_files.append(caltable)

for filen in cal_files:
    try:
        shutil.move(filen, caltables_dir + "/.")
    except:
        task_logprint(f"Unable to move {filen}")

task_logprint(f"Final calibration tables moved to {caltables_dir}")


# Pickle up the timing profile list
try:
    gmt_time = strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())
    file_time = strftime("%d%b%Y_%H%M%Sgmt", gmtime())
    # compute size of ms directory
    ms_size = 0
    bytes_in_gb = 1024.0**3
    try:
        for path, dirs, files in os.walk(ms_active):
            for filen in files:
                filename = os.path.join(path, filen)
                ms_size += os.path.getsize(filename)
        # Size of the ms in Gigabytes
        ms_size /= bytes_in_gb
    except:
        task_logprint("Unable to determine size of ms on disk")

    pipeprofile = {
        "SDM_name": SDM_name,
        "time_list": time_list,
        "gmt_time": gmt_time,
        "version": __version_str__,
        "ms_size": ms_size,
    }

    if os.path.exists("logs"):
        task_logprint("logs directory exists")
    else:
        task_logprint("logs directory does not exist / not in path")

    # if `SDM_name` is a full path (as it is for automatic pipeline executions,
    # it will have '/'s in it.  search for the right-most one, and only use the
    # part after that if it exists; otherwise, just use the full name (since
    # it's one done by hand).
    right_index = SDM_name.rfind("/")
    pickle_filename = (
        "logs/profile_" + SDM_name[right_index + 1 :] + "_" + file_time + ".p"
    )
    task_logprint(f"writing pickle file: {pickle_filename}")
    try:
        with open(pickle_filename, "wb") as f:
            istat = pickle.dump(pipeprofile, f)
        task_logprint("Pickle dump of profile successful")
    except:
        task_logprint("Unable to dump pickle file")
    # Load this dict with pipeprofile = pickle.load( open( "<file.p>", "rb" ) )

    logprint(
        "Timing profile written to logs/timing.log", logfileout="logs/completion.log"
    )
    logprint(
        f"Completed on {gmt_time} with pipeline version {__version_str__}",
        logfileout="logs/timing.log",
    )
except:
    task_logprint("Problem writing timing profile")


# Attempt to copy files to /lustre/aoc/cluster/pipeline/stats
stats_dir = "/lustre/aoc/cluster/pipeline/stats"

if os.path.exists(stats_dir):
    log_filename = (
        stats_dir + "/profile_" + SDM_name[right_index + 1 :] + "_" + file_time + ".log"
    )
    try:
        shutil.copyfile("logs/timing.log", log_filename)
        task_logprint(f"Copied timing log to {stats_dir}")
    except:
        task_logprint(f"Unable to copy timing log to {stats_dir}")
    profile_filename = (
        stats_dir + "/profile_" + SDM_name[right_index + 1 :] + "_" + file_time + ".p"
    )
    try:
        shutil.copyfile(pickle_filename, profile_filename)
        task_logprint(f"Copied profile to {stats_dir}")
    except:
        task_logprint(f"Unable to copy profile to {stats_dir}")
else:
    task_logprint(f"{stats_dir} does not exist or not accessible")


# If this is an automatic execution, try to fix file permissions, so folks in
# the "vlapipe" group can clean up after things are moved into the Trash
# folder...
if SDM_name_already_defined:
    # If it turns out things in the rawdata or results directories are
    # improperly permissioned, uncomment the getcwd() and chdir() below
    #cwd = os.getcwd()
    #os.chdir('..')
    for path, dirs, files in os.walk("."):
        for dirn in dirs:
            full_dir_name = os.path.join(path, dirn)
            st = os.stat(full_dir_name)
            if not (
                bool(st.st_mode & stat.S_IRGRP)
                and bool(st.st_mode & stat.S_IWGRP)
                and bool(st.st_mode & stat.S_IXGRP)
            ):
                os.system(f"chmod -f g+rwx {full_dir_name}")
        for filen in files:
            if filen != "epilogue.sh":
                full_file_name = os.path.join(path, filen)
                st = os.stat(full_file_name)
                if not (
                    bool(st.st_mode & stat.S_IRGRP)
                    and bool(st.st_mode & stat.S_IWGRP)
                    and bool(st.st_mode & stat.S_IXGRP)
                ):
                    os.system(f"chmod -f g+rwx {full_file_name}")
    #os.chdir(cwd)

task_logprint("Finished EVLA_pipe_filecollect.py")
time_list = runtiming("filecollect", "end")

pipeline_save()
