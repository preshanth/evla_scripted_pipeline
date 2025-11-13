"""
EVLA Pipeline: Deterministic Flagging Module

This module applies deterministic flagging to the measurement set including:
- Online flags (ANTENNA_NOT_ON_SOURCE)
- Shadow flagging
- Zero clipping
- Pointing and setup scan flagging
- Quacking (first integrations)
- End channel flagging (SPW edges and baseband edges)

Refactored from original EVLA_pipe_flagall.py to follow function-based patterns.
"""

from typing import Dict, Any
from pathlib import Path

from casatasks import flagdata, flagmanager
from evla_pipe.utils import runtiming, logprint, format_qa_status


def task_logprint(msg: str) -> None:
    """
    Centralized logging for flagall operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/flagall.log")


def flagall(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply deterministic flagging to the measurement set.

    This function applies various deterministic flagging operations including
    online flags, shadow flagging, zero clipping, pointing/setup scans,
    quacking, and edge channel flagging. All flags are applied using
    flagdata list mode for efficiency.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Name of measurement set
        - int_time : float
            Integration time in seconds
        - quack_scan_string : str
            Comma-separated scan numbers to quack
        - pointing_state_IDs : list
            State IDs for pointing scans
        - numSpws : int
            Number of spectral windows
        - channels : list
            Number of channels per SPW
        - low_spws : list
            SPW indices at bottom of basebands
        - high_spws : list
            SPW indices at top of basebands

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_flagall : str
            'Pass' or 'Fail' based on fraction flagged
        - frac_flagged_on_source1 : float
            Approximate fraction of on-source data flagged

    Notes
    -----
    Sets QA2_flagall to 'Fail' if more than 30% of on-source data is flagged.
    Saves flag version 'allflags1' after applying all deterministic flags.
    """

    task_logprint("*** Starting EVLA_pipe_flagall.py (Refactored) ***")
    time_list = runtiming("flagall", "start")
    QA2_flagall = "Pass"

    # Extract required parameters from context
    ms_active = pipeline_context.get("msname", "")
    int_time = pipeline_context.get("int_time", 1.0)
    quack_scan_string = pipeline_context.get("quack_scan_string", "")
    pointing_state_IDs = pipeline_context.get("pointing_state_IDs", [])
    numSpws = pipeline_context.get("numSpws", 0)
    channels = pipeline_context.get("channels", [])
    low_spws = pipeline_context.get("low_spws", [])
    high_spws = pipeline_context.get("high_spws", [])
    msname = pipeline_context.get("msname", "")

    try:
        # Initialize flagging command list
        flagging_commands = []
        cmdreason_list = []

        # --- Initial Statistics ---
        task_logprint("Calculating initial flag statistics")
        myinitialflags = flagdata(
            vis=ms_active,
            mode="summary",
            spwchan=True,
            spwcorr=True,
            basecnt=True,
            action="calculate",
            savepars=False,
        )

        start_total = int(myinitialflags.get("total", 0))
        start_flagged = int(myinitialflags.get("flagged", 0))
        start_fraction = start_flagged / start_total if start_total > 0 else 0.0
        task_logprint(f"Initial flagged fraction = {start_fraction:.4f}")

        # --- Online Flags (ANTENNA_NOT_ON_SOURCE) ---
        online_flag_name = str(Path(msname).with_suffix("")) + ".flagonline.txt"
        if Path(online_flag_name).is_file():
            tbuff = 1.5 * int_time
            flagging_commands.append(
                f"mode='list' inpfile='{online_flag_name}' tbuff={tbuff} reason='ANTENNA_NOT_ON_SOURCE'"
            )
            cmdreason_list.append("ANTENNA_NOT_ON_SOURCE")
            task_logprint("ANTENNA_NOT_ON_SOURCE flags will be applied")
        else:
            task_logprint("No online flags file found - ANTENNA_NOT_ON_SOURCE flags will NOT be applied")

        # --- Shadow Flagging ---
        flagging_commands.append("mode='shadow' tolerance=0.0 reason='shadow'")
        cmdreason_list.append("shadow")
        task_logprint("Shadow flagging will be applied")

        # --- Zero Flagging ---
        flagging_commands.append("mode='clip' clipzeros=True correlation='ABS_ALL' reason='CLIP_ZERO_ALL'")
        cmdreason_list.append("CLIP_ZERO_ALL")
        task_logprint("Zero clipping will be applied")

        # --- Pointing Scans ---
        if len(pointing_state_IDs) > 0:
            flagging_commands.append("mode='manual' intent='*POINTING*' reason='pointing'")
            cmdreason_list.append("pointing")
            task_logprint("Pointing scans will be flagged")

        # --- Setup Scans ---
        flagging_commands.append("mode='manual' intent='UNSPECIFIED#UNSPECIFIED' reason='setup'")
        cmdreason_list.append("setup")
        flagging_commands.append("mode='manual' intent='SYSTEM_CONFIGURATION#UNSPECIFIED' reason='setup'")
        cmdreason_list.append("setup")
        task_logprint("Setup scans will be flagged")

        # --- Quack the Data ---
        if quack_scan_string:
            quack_interval = 1.5 * int_time
            flagging_commands.append(
                f"mode='quack' scan='{quack_scan_string}' quackinterval={quack_interval} "
                f"quackmode='beg' quackincrement=False reason='quack'"
            )
            cmdreason_list.append("quack")
            task_logprint(f"Quacking will be applied (interval={quack_interval:.2f}s)")

        # --- Flag End Channels of Each SPW (5% at each end) ---
        SPWtoflag = _build_spw_end_channels_string(numSpws, channels)
        if SPWtoflag:
            flagging_commands.append(f"mode='manual' spw='{SPWtoflag}' reason='spw_ends'")
            cmdreason_list.append("spw_ends")
            task_logprint("Flagging end channels of each SPW (5% at each end)")

        # --- Flag End Channels at Edges of Basebands (10 channels) ---
        SPWtoflag_bb = _build_baseband_edge_channels_string(low_spws, high_spws, channels)
        if SPWtoflag_bb:
            flagging_commands.append(f"mode='manual' spw='{SPWtoflag_bb}' reason='baseband_edge_chans'")
            cmdreason_list.append("baseband_edge_chans")
            task_logprint("Flagging edge channels at baseband boundaries (10 channels)")

        # --- Apply All Flags ---
        task_logprint(f"Applying {len(flagging_commands)} deterministic flagging commands")
        flagdata(
            vis=ms_active,
            mode="list",
            inpfile=flagging_commands,
            action="apply",
            flagbackup=False,
            savepars=True,
            cmdreason=",".join(cmdreason_list),
        )
        task_logprint("Deterministic flagging completed")

        # --- Save Flags ---
        task_logprint("Saving flag state to 'allflags1'")
        flagmanager(
            vis=ms_active,
            mode="save",
            versionname="allflags1",
            comment="Deterministic flags saved after application (list mode)",
            merge="replace",
        )

        # --- Final Statistics ---
        task_logprint("Calculating final flag statistics")
        all_flags = flagdata(
            vis=ms_active,
            mode="summary",
            spwchan=True,
            spwcorr=True,
            basecnt=True,
            action="calculate",
            savepars=False,
        )

        final_total = int(all_flags.get("total", 0))
        final_flagged = int(all_flags.get("flagged", 0))
        final_fraction = final_flagged / final_total if final_total > 0 else 0.0
        task_logprint(f"Final flagged fraction = {final_fraction:.4f}")

        # --- Calculate Fraction of On-Source Data Flagged ---
        # Approximation: assumes initial total represents on-source data
        frac_flagged_on_source1 = 1.0 - (
            (start_total - final_flagged) / start_total if start_total > 0 else 1.0
        )
        task_logprint(f"Approximate fraction of on-source data flagged = {frac_flagged_on_source1:.4f}")

        # --- QA Assessment ---
        if frac_flagged_on_source1 >= 0.3:
            QA2_flagall = "Fail"
            task_logprint("QA2 FAIL: More than 30% of on-source data flagged")
        else:
            task_logprint("QA2 PASS: Less than 30% of on-source data flagged")

        # Update context with results
        pipeline_context["QA2_flagall"] = QA2_flagall
        pipeline_context["frac_flagged_on_source1"] = float(frac_flagged_on_source1)

    except Exception as e:
        task_logprint(f"ERROR in flagall: {str(e)}")
        pipeline_context["QA2_flagall"] = "Fail"
        pipeline_context["error_message"] = str(e)
        pipeline_context["frac_flagged_on_source1"] = -1.0

    # Final logging
    task_logprint("Finished EVLA_pipe_flagall.py (Refactored)")
    task_logprint(f"QA2 score: {format_qa_status(pipeline_context.get('QA2_flagall', 'Fail'))}")
    time_list = runtiming("flagall", "end")

    return pipeline_context


def EVLA_pipe_flagall(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for exec_script compatibility.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary

    Returns
    -------
    dict
        Updated pipeline context
    """
    return flagall(pipeline_context)


def _build_spw_end_channels_string(numSpws: int, channels: list) -> str:
    """
    Build SPW selection string for flagging end channels (5% at each end).

    Parameters
    ----------
    numSpws : int
        Number of spectral windows
    channels : list
        List of channel counts per SPW

    Returns
    -------
    str
        SPW selection string (e.g., "0:0~2;61~63,1:0~2;61~63")
    """
    spw_parts = []

    for ispw in range(numSpws):
        if ispw >= len(channels):
            continue

        # Calculate 5% of channels (minimum 3 channels)
        fivepctch = int(0.05 * channels[ispw])
        if fivepctch < 3:
            fivepctch = 3

        # Define channel ranges
        startch1 = 0
        startch2 = fivepctch - 1
        endch1 = channels[ispw] - fivepctch
        endch2 = channels[ispw] - 1

        spw_parts.append(f"{ispw}:{startch1}~{startch2};{endch1}~{endch2}")

    return ",".join(spw_parts)


def _build_baseband_edge_channels_string(
    low_spws: list,
    high_spws: list,
    channels: list
) -> str:
    """
    Build SPW selection string for flagging baseband edge channels (10 channels).

    Parameters
    ----------
    low_spws : list
        SPW indices at bottom of basebands
    high_spws : list
        SPW indices at top of basebands
    channels : list
        List of channel counts per SPW

    Returns
    -------
    str
        SPW selection string for baseband edges
    """
    bottom_parts = []
    top_parts = []

    for ii in range(len(low_spws)):
        if ii >= len(high_spws) or ii >= len(channels):
            continue

        bspw = low_spws[ii]
        tspw = high_spws[ii]

        # Flag 10 channels at bottom of lower SPW
        bottom_parts.append(f"{bspw}:0~9")

        # Flag 10 channels at top of upper SPW
        if tspw < len(channels):
            endch1 = channels[tspw] - 10
            endch2 = channels[tspw] - 1
            top_parts.append(f"{tspw}:{endch1}~{endch2}")

    all_parts = []
    if bottom_parts:
        all_parts.extend(bottom_parts)
    if top_parts:
        all_parts.extend(top_parts)

    return ",".join(all_parts)
