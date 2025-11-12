"""
Post-Calibration Module for EVLA Pipeline

This module handles post-calibration tasks that occur after applying
calibrations to the target data:

1. Target flagging - RFI flagging on calibrated target data
2. Statistical weighting - Calculate weights based on data scatter
"""

from typing import Dict, Any

from casatasks import flagdata, flagmanager, statwt
from evla_pipe.utils import runtiming, logprint, format_qa_status, get_log_path

def task_logprint(msg: str):
    """Centralized logging for post-calibration operations."""
    logprint(msg, logfileout=str(get_log_path("post_calibration.log")))


def flag_target_data(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flag RFI in calibrated target and calibrator data using rflag mode.

    This function applies RFI flagging to all calibrated data (both calibrators
    and targets) using the 'rflag' algorithm. It saves the final flags and
    computes flagging statistics to assess data quality.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname: Path to measurement set
        - corrstring: Correlation string (e.g., "RR,LL")
        - start_total: Total visibility count before flagging
        - init_on_source_vis: Initial on-source visibility count

    Returns
    -------
    dict
        Updated pipeline context with:
        - frac_flagged_on_source2: Final fraction of on-source data flagged
        - final_flags: Dictionary of final flagging statistics
        - QA2_targetflag: QA score ("Pass" if < 60% flagged, else "Fail")

    Notes
    -----
    - Flags calibrators and targets separately with identical parameters
    - Uses corrected data column
    - Saves final flags as 'finalflags' version
    - Sets QA2_targetflag to "Fail" if >= 60% of data is flagged
    """
    task_logprint("*** Starting Target Flagging ***")
    time_list = runtiming("targetflag", "start")

    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    start_total = pipeline_context.get("start_total", 0)
    init_on_source_vis = pipeline_context.get("init_on_source_vis", 1)

    try:
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
        frac_flagged_on_source2 = 1.0 - (
            (start_total - final_flags["flagged"]) / init_on_source_vis
        )

        task_logprint(f"Final fraction of on-source data flagged = {frac_flagged_on_source2:.4f}")

        # Determine QA score based on flagging fraction
        if frac_flagged_on_source2 >= 0.6:
            QA2_score = "Fail"
            task_logprint("WARNING: More than 60% of on-source data is flagged!")
        else:
            QA2_score = "Pass"

        # Update context with results
        pipeline_context["frac_flagged_on_source2"] = float(frac_flagged_on_source2)
        pipeline_context["final_flags"] = {
            "flagged": int(final_flags["flagged"]),
            "total": int(final_flags["total"]),
        }

    except Exception as e:
        task_logprint(f"Error in flag_target_data: {e}")
        QA2_score = "Fail"
        pipeline_context["error_message"] = str(e)

    task_logprint(f"Finished flag_target_data")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("targetflag", "end")

    # Update context and return
    pipeline_context["QA2_targetflag"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context


def apply_statistical_weights(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate data weights based on standard deviation within each spectral window.

    This function uses the statwt task to calculate weights empirically from
    the scatter in the corrected data. This provides more accurate weights
    than the nominal values, improving imaging quality.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname: Path to measurement set

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_statwt: QA score ("Pass" on success, "Fail" on error)

    Notes
    -----
    - Runs on calibrators and targets separately
    - Uses corrected data column
    - Minimum sample size of 2 for statistics
    - For targets, can exclude spectral lines by setting spw parameter
    """
    task_logprint("*** Starting Statistical Weighting ***")
    time_list = runtiming("statwt", "start")

    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")

    try:
        task_logprint("Calculating data weights per SpW using statwt")

        # Run statwt on all calibrators
        task_logprint("Calculating weights for calibrators...")
        statwt(
            vis=ms_active,
            minsamp=2,
            intent="*CALIBRATE*",
            datacolumn="corrected",
        )

        # Run statwt on all targets
        # Note: Can set spw parameter to exclude strong science spectral lines
        task_logprint("Calculating weights for targets...")
        statwt(
            vis=ms_active,
            minsamp=2,
            intent="*TARGET*",
            datacolumn="corrected",
        )

        QA2_score = "Pass"
        task_logprint("Statistical weighting completed successfully")

    except Exception as e:
        task_logprint(f"Error in apply_statistical_weights: {e}")
        QA2_score = "Fail"
        pipeline_context["error_message"] = str(e)

    task_logprint("Finished apply_statistical_weights")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("statwt", "end")

    # Update context and return
    pipeline_context["QA2_statwt"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context
