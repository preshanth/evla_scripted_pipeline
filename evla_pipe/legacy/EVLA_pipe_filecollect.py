"""
Move relevant plots and tables after calibration is complete.
"""

import copy
import glob
import os
import shutil
from time import gmtime, strftime

from evla_pipe import __version_str__
from evla_pipe.utils import (
    CALTABLES_DIR,
    PLOTS_DIR,
    WEBLOG_DIR,
    format_qa_status,
    get_log_path,
    logprint,
    runtiming,
)


def task_logprint(msg):
    logprint(msg, logfileout=str(get_log_path("filecollect.log")))


# ... rest of your code ...


def EVLA_pipe_filecollect(pipeline_context):
    """
    Main entry point for EVLA_pipe_filecollect pipeline step.
    """

    def task_logprint(msg):
        logprint(msg, logfileout="logs/filecollect.log")

    task_logprint("*** Starting EVLA_pipe_filecollect.py ***")
    time_list = runtiming("filecollect", "start")

    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    SDM_name = pipeline_context.get("SDM_name", "")
    priorcals = pipeline_context.get("priorcals", [])

    try:
        # Directories already ensured in utils.py imports
        caltables_dir = str(CALTABLES_DIR)
        weblog_dir = str(WEBLOG_DIR)
        plots_dir = str(PLOTS_DIR)

        # Move all png files/plots to plots directory first
        png_files = glob.glob("./*.png")
        for filen in png_files:
            try:
                shutil.move(filen, plots_dir + "/.")
            except:
                task_logprint(f"Unable to move {filen}")

        task_logprint(f"Plots moved to {plots_dir}")

        # Copy key plots to weblog for web display
        key_plot_patterns = ["*cal*.png", "*flag*.png", "*summary*.png"]
        for pattern in key_plot_patterns:
            plot_files = glob.glob(f"{plots_dir}/{pattern}")
            for plot_file in plot_files:
                try:
                    shutil.copy2(plot_file, weblog_dir + "/.")
                except:
                    task_logprint(f"Unable to copy {plot_file} to weblog")

        task_logprint(f"Key plots copied to {weblog_dir} for web display")

        # Listobs output
        listobs_output = glob.glob("./*.listobs")
        for filen in listobs_output:
            try:
                shutil.move(filen, weblog_dir + "/.")
            except:
                task_logprint(f"Unable to move {filen}")

        # Move calibration tables into caltables_dir
        cal_files = copy.copy(priorcals)
        for caltable in (
            "switched_power.g",
            "fluxgaincal.g",
            "finaldelay.k",
            "finalBPcal.b",
            "averagephasegain.g",
            "finalampgaincal.g",
            "finalphasegaincal.g",
        ):
            cal_files.append(caltable)

        for filen in cal_files:
            try:
                shutil.move(filen, caltables_dir + "/.")
            except:
                task_logprint(f"Unable to move {filen}")

        task_logprint(f"Final calibration tables moved to {caltables_dir}")

        # Create timing profile
        gmt_time = strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())
        strftime("%d%b%Y_%H%M%Sgmt", gmtime())

        # compute size of ms directory
        ms_size = 0
        bytes_in_gb = 1024.0**3
        try:
            for path, _dirs, files in os.walk(ms_active):
                for filen in files:
                    filename = os.path.join(path, filen)
                    ms_size += os.path.getsize(filename)
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

        pipeline_context["pipeprofile"] = pipeprofile
        QA2_score = "Pass"

    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_filecollect: {e}")
        QA2_score = "Fail"

    task_logprint("Finished EVLA_pipe_filecollect.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("filecollect", "end")

    pipeline_context["QA2_filecollect"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context
