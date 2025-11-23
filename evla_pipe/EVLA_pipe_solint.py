"""
Solution interval determination for EVLA pipeline.

This module determines the optimal solution interval for scan-average equivalent
calibration by analyzing phase calibrator scan durations.
"""

from typing import Dict, Any, List, Tuple
from casatasks import rmtables, split
from casatools import ms as mstool
from pathlib import Path

from evla_pipe.utils import logprint, runtiming, format_qa_status
from evla_pipe.pipeline_steps import register_step


def task_logprint(msg: str) -> None:
    """
    Centralized logging for solution interval operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/solint.log")


def determine_long_solint(
    pipeline_context: Dict[str, Any],
    channels: List[int],
    phase_scan_list: List[int]
) -> Tuple[str, str]:
    """
    Determine the solution interval for scan-average equivalent calibration.

    This function splits out gain calibrators, drops flagged rows, and analyzes
    the scan durations to determine an appropriate long solution interval.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and calibrator scan selection
    channels : list of int
        List of channels used to determine width for split
    phase_scan_list : list of int
        List of scan IDs for phase calibrators

    Returns
    -------
    tuple of (str, str)
        - Long solution interval string (e.g., "123.45s")
        - Path to calibrators.ms file

    Notes
    -----
    Creates calibrators.ms which is kept for subsequent calibration steps.
    Sets gain_solint2 to max(scan_durations) * 1.01 with 30s default fallback.
    """
    ms_active = pipeline_context.get("msname", "")
    calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")

    if not ms_active:
        raise ValueError("msname not found in pipeline_context")

    # Split out calibrators, dropping flagged data
    task_logprint("Splitting out calibrators into calibrators.ms")
    output_ms = "calibrators.ms"
    rmtables(output_ms)

    try:
        # Determine channel width for split
        width = int(max(channels)) if channels else 1

        split(
            vis=ms_active,
            outputvis=output_ms,
            datacolumn="data",  # Use data column, corrected likely doesn't exist yet
            field="",
            spw="",
            width=width,
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
        task_logprint(f"Successfully created {output_ms}")
    except Exception as e:
        task_logprint(f"ERROR creating calibrators.ms: {e}")
        task_logprint(f"ms_active: {ms_active}")
        task_logprint(f"calibrator_scan_select_string: {calibrator_scan_select_string}")
        raise

    # Analyze scan durations
    durations: List[float] = []
    old_spws: List[int] = []
    old_field: str = ""
    old_begin_time: float = 0.0
    day_in_s = 86400.0  # seconds per day

    ms_tool = mstool()

    if not Path(output_ms).exists():
        task_logprint(f"ERROR: {output_ms} not found after split.")
        raise FileNotFoundError(f"{output_ms} was not created")

    try:
        ms_tool.open(output_ms)
        scan_summary = ms_tool.getscansummary()

        for kk, scan_id in enumerate(phase_scan_list):
            summary = scan_summary.get(str(scan_id))

            if not summary:
                task_logprint(
                    f"WARNING: scan {scan_id} is completely flagged and missing from 'calibrators.ms'"
                )
                continue

            try:
                # Extract timing information from all subscan entries
                endtimes = [v["EndTime"] for v in summary.values()]
                begintimes = [v["BeginTime"] for v in summary.values()]
                end_time = max(endtimes)
                begin_time = min(begintimes)

                # Extract SPW and field information
                first_subscan = list(summary.values())[0]
                new_spws = first_subscan.get("SpwIds", [])
                new_field = first_subscan.get("FieldId", "")

                # Check if this is a contiguous scan with same setup
                is_contiguous = (
                    kk > 0
                    and phase_scan_list[kk - 1] == scan_id - 1
                    and set(new_spws) == set(old_spws)
                    and new_field == old_field
                )

                if is_contiguous:
                    # Extend the previous duration
                    durations[-1] = day_in_s * (end_time - old_begin_time)
                else:
                    # New non-contiguous scan
                    durations.append(day_in_s * (end_time - begin_time))
                    old_begin_time = begin_time

                task_logprint(f"Scan {scan_id} has {durations[-1]:.2f}s on source")

                # Update tracking variables
                old_spws = new_spws
                old_field = new_field

                ms_tool.reset()

            except KeyError as e:
                task_logprint(
                    f"WARNING: scan {scan_id} has incomplete information in 'calibrators.ms': {e}"
                )

    finally:
        ms_tool.close()

    # Determine long solution interval
    if durations:
        longsolint = max(durations) * 1.01  # Add 1% margin
        task_logprint(f"Maximum scan duration: {max(durations):.2f}s")
    else:
        longsolint = 30.0  # Default fallback
        task_logprint("WARNING: No valid scan durations found, using default 30s")

    gain_solint2 = f"{longsolint:.2f}s"

    task_logprint(f"Long solution interval (gain_solint2) determined as: {gain_solint2}")
    task_logprint(f"Keeping {output_ms} for subsequent calibration steps")

    return gain_solint2, output_ms


def solint(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine solution interval for EVLA calibration.

    This is the main entry point for the solution interval determination step.
    It analyzes phase calibrator scans to determine an appropriate long solution
    interval (gain_solint2) for subsequent calibration steps.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Path to measurement set
        - calibrator_scan_select_string : str
            Scan selection string for calibrators
        - channels : list of int
            Channel list for determining split width
        - phase_scan_list : list of int
            List of phase calibrator scan IDs

    Returns
    -------
    dict
        Updated pipeline context with:
        - gain_solint2 : str
            Long solution interval (e.g., "123.45s")
        - calibrators_ms : str
            Path to calibrators.ms file
        - QA2_solint : str
            QA score ("Pass" or "Fail")
        - time_list : list
            Timing information from runtiming

    Notes
    -----
    Creates calibrators.ms which is preserved for subsequent pipeline steps.
    This replaces EVLA_pipe_solint.py with a cleaner, modular approach.

    Examples
    --------
    >>> context = {
    ...     "msname": "data.ms",
    ...     "calibrator_scan_select_string": "1,2,3,10,11,12",
    ...     "channels": [0, 1, 2, 3],
    ...     "phase_scan_list": [1, 2, 3]
    ... }
    >>> context = solint(context)
    >>> print(context["gain_solint2"])
    '145.23s'
    """
    task_logprint("*** Starting Solution Interval Determination ***")
    time_list = runtiming("solint", "start")

    # Extract required parameters with validation
    ms_active = pipeline_context.get("msname", "")
    channels = pipeline_context.get("channels", [])
    phase_scan_list = pipeline_context.get("phase_scan_list", [])

    if not ms_active:
        task_logprint("ERROR: msname not found in pipeline_context")
        pipeline_context["QA2_solint"] = "Fail"
        pipeline_context["error_message"] = "msname not found in pipeline_context"
        pipeline_context["time_list"] = runtiming("solint", "end")
        return pipeline_context

    try:
        # Determine long solution interval
        if not phase_scan_list:
            task_logprint("WARNING: phase_scan_list is empty, using default 30s solution interval")
            gain_solint2 = "30.0s"
            # Still need to create calibrators.ms for later steps
            calibrators_ms = "calibrators.ms"

            # Create calibrators.ms even without phase scans
            ms_active = pipeline_context.get("msname", "")
            calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")

            if calibrator_scan_select_string:
                from casatasks import split, rmtables

                rmtables(calibrators_ms)
                width = int(max(channels)) if channels else 1

                split(
                    vis=ms_active,
                    outputvis=calibrators_ms,
                    datacolumn="data",
                    field="",
                    spw="",
                    width=width,
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
                task_logprint(f"Created {calibrators_ms} with all calibrator scans")
            else:
                task_logprint("WARNING: No calibrator scans found, cannot create calibrators.ms")
        else:
            gain_solint2, calibrators_ms = determine_long_solint(
                pipeline_context,
                channels,
                phase_scan_list
            )

        # Update context with results
        pipeline_context["gain_solint2"] = gain_solint2
        pipeline_context["calibrators_ms"] = calibrators_ms
        pipeline_context["QA2_solint"] = "Pass"

        task_logprint(f"Successfully determined solution interval: {gain_solint2}")

    except Exception as e:
        task_logprint(f"ERROR in solution interval determination: {e}")
        pipeline_context["QA2_solint"] = "Fail"
        pipeline_context["error_message"] = str(e)

        # Set safe defaults on failure
        if "gain_solint2" not in pipeline_context:
            pipeline_context["gain_solint2"] = "30.0s"
            task_logprint("Using default 30s solution interval due to error")

    # Log final status
    qa_status = pipeline_context.get("QA2_solint", "Fail")
    task_logprint(f"QA2 score: {format_qa_status(qa_status)}")
    task_logprint("*** Finished Solution Interval Determination ***")

    time_list = runtiming("solint", "end")
    pipeline_context["time_list"] = time_list

    return pipeline_context


# Legacy alias for backward compatibility
EVLA_pipe_solint = solint



@register_step("EVLA_pipe_solint")
def EVLA_pipe_solint(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for solint() to match expected step name.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary

    Returns
    -------
    dict
        Updated pipeline context
    """
    return solint(pipeline_context)
