from casatasks import rmtables, split
from casatools import ms as mstool
import os
from evla_pipe.utils import logprint, runtiming, format_qa_status

ms = mstool()

def task_logprint(msg):
    logprint(msg, logfileout="logs/solint.log")

def determine_long_solint(pipeline_context, channels, phase_scan_list):
    """
    Determine the solution interval for scan-average equivalent.
    First split out gain calibrators and drop flagged rows.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
        channels (list): List of channels (used to determine width for split).
        phase_scan_list (list): List of scan IDs for phase calibrators.

    Returns:
        str: The long solution interval string (e.g., "123.45s").
    """
    task_logprint("*** Starting determine_long_solint.py ***")
    runtiming("solint", "start")
    QA2_solint = "Pass"

    ms_active = pipeline_context.get("msname")
    calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")

    # Split out calibrators, dropping flagged data
    task_logprint("Splitting out calibrators into calibrators.ms")
    output_ms = "calibrators.ms"
    rmtables(output_ms)
    try:
        split(
            vis=ms_active,
            outputvis=output_ms,
            datacolumn="data",  # Use data column, corrected likely doesn't exist yet
            field="",
            spw="",
            width=int(max(channels)) if channels else 1, # Default width if channels is empty
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

    durations = []
    old_spws = []
    old_field = ""
    day_in_s = 86400  # s

    if os.path.exists(output_ms):
        ms.open(output_ms)
        scan_summary = ms.getscansummary()
        for kk, ii in enumerate(phase_scan_list):
            summary = scan_summary.get(str(ii))
            if summary:
                try:
                    endtimes = [v["EndTime"] for v in summary.values()]
                    begintimes = [v["BeginTime"] for v in summary.values()]
                    end_time = max(endtimes)
                    begin_time = min(begintimes)
                    new_spws = list(summary.values())[0]["SpwIds"] if summary else []
                    new_field = list(summary.values())[0]["FieldId"] if summary else ""
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
                        f"WARNING: scan {ii} has incomplete information in 'calibrators.ms'"
                    )
            else:
                task_logprint(
                    f"WARNING: scan {ii} is completely flagged and missing from 'calibrators.ms'"
                )
        ms.close()
    else:
        task_logprint(f"ERROR: {output_ms} not found.")
        QA2_solint = "Fail"

    longsolint = max(durations) * 1.01 if durations else 30.0 # Default if no durations
    gain_solint2 = f"{longsolint}s"

    # Keep calibrators.ms for subsequent pipeline steps - DO NOT DELETE
    task_logprint(f"Keeping {output_ms} for subsequent calibration steps")

    task_logprint(f"Long solution interval (gain_solint2) determined as: {gain_solint2}")
    task_logprint(f"QA2 score: {format_qa_status(QA2_solint)}")
    runtiming("solint", "end")

    return gain_solint2, output_ms

def EVLA_pipe_solint(pipeline_context):
    """
    Main entry point for EVLA_pipe_solint pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_solint.py ***")
    time_list = runtiming("solint", "start")
    
    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    
    try:
        # Call the main function if it exists
        if "determine_long_solint" in globals():
            # Get required parameters from context
            channels = pipeline_context.get("channels", [])
            phase_scan_list = pipeline_context.get("phase_scan_list", [])
            gain_solint2, calibrators_ms = determine_long_solint(pipeline_context, channels, phase_scan_list)
            
            # Add calibrators.ms to pipeline context for subsequent steps
            pipeline_context["calibrators_ms"] = calibrators_ms
            pipeline_context["gain_solint2"] = gain_solint2
            QA2_score = "Pass"
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_solint: {e}")
        QA2_score = "Fail"
    
    task_logprint(f"Finished EVLA_pipe_solint.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("solint", "end")
    
    # Update context and return
    pipeline_context["QA2_solint"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
