"""
Check the flagging of all calibrated data, including target using the `rflag`
mode of `flagdata`.
"""

from casatasks import flagdata, flagmanager
from evla_pipe.utils import logprint, runtiming, format_qa_status

def task_logprint(msg):
    logprint(msg, logfileout="logs/targetflag.log")

def EVLA_pipe_targetflag(pipeline_context):
    """
    Main entry point for EVLA_pipe_targetflag pipeline step.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """

    task_logprint("*** Starting EVLA_pipe_targetflag.py ***")
    time_list = runtiming("targetflag", "start")

    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    start_total = pipeline_context.get("start_total", 0)
    init_on_source_vis = pipeline_context.get("init_on_source_vis", 1)

    try:
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
        task_logprint("Flag column saved to 'finalflags'")

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
            QA2_score = "Fail"
        else:
            QA2_score = "Pass"

        # Update context with results
        pipeline_context["frac_flagged_on_source2"] = frac_flagged_on_source2
        pipeline_context["final_flags"] = final_flags

    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_targetflag: {e}")
        QA2_score = "Fail"

    task_logprint(f"Finished EVLA_pipe_targetflag.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("targetflag", "end")

    # Update context and return
    pipeline_context["QA2_targetflag"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context
