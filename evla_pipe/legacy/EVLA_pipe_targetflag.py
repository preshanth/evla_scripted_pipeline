"""
Target flagging module for EVLA pipeline.

This module checks the flagging of all calibrated data, including targets,
using the `rflag` mode of `flagdata`. It performs RFI flagging on both
calibrator and target scans, then calculates final flag statistics.
"""

from typing import Any, Dict

from casatasks import flagdata, flagmanager

from evla_pipe.utils import format_qa_status, logprint, runtiming


def task_logprint(msg: str) -> None:
    """
    Centralized logging for target flagging operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/targetflag.log")


def targetflag(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply RFI flagging to all calibrated target and calibrator data.

    This function replaces EVLA_pipe_targetflag.py with a cleaner, modular approach.
    It runs `flagdata` in rflag mode on both calibrator and target scans, saves
    the final flags, and calculates the fraction of flagged on-source data.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Name of the measurement set
        - corrstring : str
            Correlation string (e.g., "RR,LL")
        - start_total : int
            Total number of visibilities before final flagging
        - init_on_source_vis : int
            Initial on-source visibilities

    Returns
    -------
    dict
        Updated pipeline context with:
        - frac_flagged_on_source2 : float
            Final fraction of on-source data flagged
        - final_flags : dict
            Final flag statistics from flagdata summary
        - QA2_targetflag : str
            QA score ("Pass" or "Fail")
        - time_list : list
            Timing information for this step

    Notes
    -----
    QA2 scoring:
    - Fail: >= 60% of on-source data flagged
    - Pass: < 60% of on-source data flagged

    Flag backups are created automatically and final flags are saved
    as 'finalflags' version.
    """
    task_logprint("*** Starting Target Flagging ***")
    time_list = runtiming("targetflag", "start")

    # Extract required variables from context
    ms_active = pipeline_context.get("msname", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    start_total = pipeline_context.get("start_total", 0)
    init_on_source_vis = pipeline_context.get("init_on_source_vis", 1)

    # Initialize QA score
    QA2_score = "Fail"

    try:
        task_logprint(f"Processing measurement set: {ms_active}")
        task_logprint(f"Using correlation: {corrstring}")
        task_logprint("Checking RFI flagging of all targets")

        # Run rflag on all calibrator scans
        task_logprint("Running rflag on calibrator scans...")
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
        task_logprint("Calibrator flagging complete")

        # Run rflag on all target scans
        task_logprint("Running rflag on target scans...")
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
        task_logprint("Target flagging complete")

        # Save final version of flags
        task_logprint("Saving final flag version...")
        flagmanager(
            vis=ms_active,
            mode="save",
            versionname="finalflags",
            comment="Final flags saved after calibrations and rflag",
            merge="replace",
        )
        task_logprint("Flag column saved to 'finalflags'")

        # Calculate final flag statistics
        task_logprint("Calculating final flag statistics...")
        final_flags = flagdata(
            vis=ms_active,
            mode="summary",
            spwchan=True,
            spwcorr=True,
            basecnt=True,
            action="calculate",
            savepars=False,
        )

        # Calculate fraction of on-source data flagged
        if init_on_source_vis > 0:
            frac_flagged_on_source2 = 1.0 - (
                (start_total - final_flags["flagged"]) / init_on_source_vis
            )
        else:
            task_logprint("Warning: init_on_source_vis is 0, setting fraction to 1.0")
            frac_flagged_on_source2 = 1.0

        task_logprint(
            f"Final fraction of on-source data flagged = {frac_flagged_on_source2:.4f}"
        )

        # Determine QA score based on flagging fraction
        if frac_flagged_on_source2 >= 0.6:
            QA2_score = "Fail"
            task_logprint(
                f"WARNING: {frac_flagged_on_source2*100:.1f}% of on-source data flagged (threshold: 60%)"
            )
        else:
            QA2_score = "Pass"
            task_logprint(
                f"Good: {frac_flagged_on_source2*100:.1f}% of on-source data flagged (threshold: 60%)"
            )

        # Update context with results (JSON-serializable)
        pipeline_context["frac_flagged_on_source2"] = float(frac_flagged_on_source2)
        pipeline_context["final_flags"] = {
            "flagged": int(final_flags.get("flagged", 0)),
            "total": int(final_flags.get("total", 0)),
            "name": str(final_flags.get("name", "")),
        }

    except Exception as e:
        task_logprint(f"Error in target flagging: {e}")
        QA2_score = "Fail"
        pipeline_context["error_message"] = str(e)
        pipeline_context["frac_flagged_on_source2"] = 1.0
        pipeline_context["final_flags"] = {}

    # Finalize timing
    time_list = runtiming("targetflag", "end")

    task_logprint("*** Finished Target Flagging ***")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")

    # Update context and return
    pipeline_context["QA2_targetflag"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context


# Legacy entry point for backwards compatibility
def EVLA_pipe_targetflag(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Legacy entry point for EVLA_pipe_targetflag pipeline step.

    This function provides backwards compatibility with the original
    EVLA_pipe_targetflag.py script.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context

    Notes
    -----
    This is a wrapper around the new `targetflag` function.
    Use `targetflag` directly for new code.
    """
    return targetflag(pipeline_context)
