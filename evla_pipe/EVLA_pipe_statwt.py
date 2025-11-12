"""
Calculate data weights based on the standard deviation within each spw using
`statwt`.

This module provides statistical weighting of visibility data based on the
scatter within each spectral window.
"""

from typing import Dict, Any, Optional
from casatasks import statwt
from evla_pipe.utils import logprint, runtiming, format_qa_status


def task_logprint(msg: str) -> None:
    """
    Log a message to the statwt log file.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/statwt.log")


def statwt_calibration(
    pipeline_context: Dict[str, Any],
    minsamp: int = 2,
    calibrator_spw: str = "",
    target_spw: str = ""
) -> Dict[str, Any]:
    """
    Calculate data weights based on standard deviation within each spectral window.

    This function applies statistical weighting using CASA's statwt task to both
    calibrator and target sources. Weights are calculated from the scatter in the
    corrected data column, which improves the final imaging by properly accounting
    for variations in data quality across spectral windows and time.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Path to the measurement set
        - time_list : list, optional
            Timing information from previous steps
    minsamp : int, optional
        Minimum number of samples required for weight calculation (default: 2)
    calibrator_spw : str, optional
        Spectral window selection for calibrators (default: "" for all)
    target_spw : str, optional
        Spectral window selection for targets (default: "" for all)
        Use this to exclude strong science spectral lines if needed

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_statwt : str
            QA score ("Pass" or "Fail")
        - time_list : list
            Updated timing information
        - error_message : str, optional
            Error description if QA2_statwt is "Fail"

    Notes
    -----
    The statwt task calculates weights from the scatter in the corrected data,
    replacing any weights set during initial data filling. This is run separately
    for calibrators and targets to allow different spectral window selections.

    For targets, you may want to set target_spw to exclude spectral windows
    containing strong science spectral lines to avoid biasing the weight
    calculation.

    Examples
    --------
    >>> context = {"msname": "test.ms"}
    >>> context = statwt_calibration(context)
    >>> context["QA2_statwt"]
    'Pass'

    >>> # Exclude spw 0,1 from target weighting
    >>> context = statwt_calibration(context, target_spw="2~15")
    """
    task_logprint("*** Starting Statistical Weight Calculation ***")
    time_list = pipeline_context.get("time_list", [])
    time_list = runtiming("statwt", "start", time_list)

    # Extract configuration from context
    ms_active = pipeline_context.get("msname", "")

    if not ms_active:
        task_logprint("ERROR: No measurement set specified in pipeline_context")
        pipeline_context["QA2_statwt"] = "Fail"
        pipeline_context["error_message"] = "Missing msname in pipeline_context"
        return pipeline_context

    task_logprint(f"Calculating data weights for: {ms_active}")
    task_logprint(f"Minimum samples required: {minsamp}")

    try:
        # Run statwt on all calibrators
        task_logprint("Calculating weights for calibrator sources...")
        statwt_params_cal = {
            "vis": ms_active,
            "minsamp": minsamp,
            "intent": "*CALIBRATE*",
            "datacolumn": "corrected",
        }

        if calibrator_spw:
            statwt_params_cal["spw"] = calibrator_spw
            task_logprint(f"  Calibrator spw selection: {calibrator_spw}")

        statwt(**statwt_params_cal)
        task_logprint("  Calibrator weights calculated successfully")

        # Run statwt on all targets
        # Use target_spw parameter to exclude strong science spectral lines if needed
        task_logprint("Calculating weights for target sources...")
        statwt_params_tgt = {
            "vis": ms_active,
            "minsamp": minsamp,
            "intent": "*TARGET*",
            "datacolumn": "corrected",
        }

        if target_spw:
            statwt_params_tgt["spw"] = target_spw
            task_logprint(f"  Target spw selection: {target_spw}")

        statwt(**statwt_params_tgt)
        task_logprint("  Target weights calculated successfully")

        QA2_score = "Pass"
        task_logprint("Statistical weight calculation completed successfully")

    except Exception as e:
        task_logprint(f"ERROR in statistical weight calculation: {e}")
        QA2_score = "Fail"
        pipeline_context["error_message"] = str(e)

    # Finalize timing
    time_list = runtiming("statwt", "end", time_list)

    # Update context
    pipeline_context["QA2_statwt"] = QA2_score
    pipeline_context["time_list"] = time_list

    task_logprint("*** Finished Statistical Weight Calculation ***")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")

    return pipeline_context


def EVLA_pipe_statwt(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Legacy entry point for EVLA_pipe_statwt pipeline step.

    This function maintains backward compatibility with the original pipeline
    structure. New code should use statwt_calibration() directly.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context

    See Also
    --------
    statwt_calibration : Main implementation with configurable parameters
    """
    return statwt_calibration(pipeline_context)
