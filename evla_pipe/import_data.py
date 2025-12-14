"""
Data Import Module for EVLA Pipeline

This module handles data import from SDM to MS format with optional
Hanning smoothing applied in the same step.

Functions:
- import_asdm_data: Import SDM to MS
- apply_hanning_smooth: Apply Hanning smoothing
- import_with_optional_hanning: Combined import + optional Hanning
"""

import os
import shutil
from glob import glob
from pathlib import Path
from typing import Any, Dict, Tuple

from casatasks import flagdata, hanningsmooth, importasdm
from casatools import table

from evla_pipe.utils import (
    MEASUREMENT_SETS_DIR,
    cleanup_import_files,
    get_log_path,
    get_measurement_set_path,
    logprint,
    runtiming,
)

tb = table()


def task_logprint(msg: str, step: str = "import"):
    """Centralized logging for import operations."""
    logprint(msg, logfileout=str(get_log_path(f"{step}.log")))


def detect_data_type(data_path: str) -> Tuple[str, str]:
    """
    Detect whether input is SDM or MS.

    Parameters
    ----------
    data_path : str
        Path to data (SDM directory or MS)

    Returns
    -------
    tuple
        (data_type, ms_name) where data_type is 'SDM' or 'MS'
        and ms_name is the MS name to use
    """
    data_path = Path(data_path)

    # Check if it's an existing MS
    if data_path.is_dir():
        table_dat = data_path / "table.dat"
        antenna_table = data_path / "ANTENNA" / "table.dat"

        if table_dat.exists() and antenna_table.exists():
            # It's an MS
            ms_name = str(data_path)
            task_logprint(f"Detected MS: {ms_name}")
            return "MS", ms_name

    # Check if it's an SDM
    if data_path.is_dir():
        asdm_xml = data_path / "ASDM.xml"
        if asdm_xml.exists():
            # It's an SDM
            ms_name = str(data_path).rstrip("/").replace(".asdm", ".ms")
            if not ms_name.endswith(".ms"):
                ms_name += ".ms"
            task_logprint(f"Detected SDM: {data_path} -> will create MS: {ms_name}")
            return "SDM", ms_name

    # Assume it's an SDM if file extension suggests it
    if str(data_path).endswith(".asdm"):
        ms_name = str(data_path).replace(".asdm", ".ms")
        task_logprint(f"Treating as SDM: {data_path} -> will create MS: {ms_name}")
        return "SDM", ms_name

    # Default: treat as SDM, create .ms name
    ms_name = str(data_path) + ".ms"
    task_logprint(f"Defaulting to SDM: {data_path} -> will create MS: {ms_name}")
    return "SDM", ms_name


def get_flagging_summary(ms_name: str, operation: str = "initial") -> Dict[str, Any]:
    """
    Get comprehensive flagging summary for an MS.

    Parameters
    ----------
    ms_name : str
        Name of the MS
    operation : str
        Description of the operation (for logging)

    Returns
    -------
    dict
        Flagging summary with totals, fractions, and per-antenna/spw breakdown
    """
    try:
        task_logprint(f"Getting flagging summary ({operation}) for {ms_name}")

        flag_summary = flagdata(
            vis=ms_name,
            mode="summary",
            spwchan=True,
            spwcorr=True,
            basecnt=True,
            action="calculate",
            savepars=False,
        )

        # Extract key statistics
        total_data = flag_summary.get("total", 0)
        flagged_data = flag_summary.get("flagged", 0)
        flagged_fraction = flagged_data / total_data if total_data > 0 else 0.0

        summary = {
            "operation": operation,
            "ms_name": ms_name,
            "total_data": total_data,
            "flagged_data": flagged_data,
            "flagged_fraction": flagged_fraction,
            "unflagged_data": total_data - flagged_data,
            "unflagged_fraction": 1.0 - flagged_fraction,
            "raw_summary": flag_summary,
        }

        task_logprint(
            f"Flagging summary ({operation}): {flagged_fraction:.4f} "
            f"({flagged_data}/{total_data} flagged)"
        )

        return summary

    except Exception as e:
        task_logprint(f"Error getting flagging summary: {e}")
        return {
            "operation": operation,
            "ms_name": ms_name,
            "error": str(e),
            "total_data": 0,
            "flagged_data": 0,
            "flagged_fraction": 0.0,
        }


def validate_fresh_ms_flagging(ms_name: str) -> bool:
    """
    Validate that a fresh MS has minimal flagging (should be mostly unflagged).

    Parameters
    ----------
    ms_name : str
        Name of the MS

    Returns
    -------
    bool
        True if flagging summary appears reasonable for fresh MS
    """
    summary = get_flagging_summary(ms_name, "fresh_ms_validation")

    flagged_fraction = summary.get("flagged_fraction", 0.0)

    # Fresh MS should have very little flagging (< 5% typically)
    # Some flagging is normal due to autocorrelations, edge channels, etc.
    if flagged_fraction > 0.15:  # 15% threshold
        task_logprint(
            f"WARNING: Fresh MS has high flagging fraction: {flagged_fraction:.4f}"
        )
        task_logprint("This may indicate issues with the data or import process")
        return False
    else:
        task_logprint(
            f"Fresh MS flagging validation passed: {flagged_fraction:.4f} flagged"
        )
        return True


def track_flagging_progression(
    pipeline_context: Dict[str, Any], operation: str
) -> Dict[str, Any]:
    """
    Track flagging progression through pipeline stages.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context
    operation : str
        Name of the current operation

    Returns
    -------
    dict
        Updated pipeline context with flagging tracking
    """
    ms_name = pipeline_context.get("msname")
    if not ms_name:
        return pipeline_context

    # Initialize flagging tracking if not present
    if "flagging_progression" not in pipeline_context:
        pipeline_context["flagging_progression"] = []

    # Get current summary
    current_summary = get_flagging_summary(ms_name, operation)

    # Calculate change from previous step
    progression = pipeline_context["flagging_progression"]
    if progression:
        previous_summary = progression[-1]
        previous_flagged = previous_summary.get("flagged_data", 0)
        current_flagged = current_summary.get("flagged_data", 0)
        added_flags = current_flagged - previous_flagged

        current_summary["flags_added"] = added_flags
        current_summary["previous_operation"] = previous_summary.get(
            "operation", "unknown"
        )

        task_logprint(f"Flagging change: +{added_flags} flags from {operation}")

        # Check for excessive flagging
        total_data = current_summary.get("total_data", 1)
        flags_added_fraction = added_flags / total_data if total_data > 0 else 0

        if flags_added_fraction > 0.1:  # More than 10% flagged in one step
            task_logprint(
                f"WARNING: {operation} flagged {flags_added_fraction:.4f} "
                f"of total data - possible over-flagging!"
            )
            current_summary["over_flagging_warning"] = True
    else:
        current_summary["flags_added"] = current_summary.get("flagged_data", 0)
        current_summary["previous_operation"] = "initial"

    # Add to progression tracking
    progression.append(current_summary)

    return pipeline_context


def import_asdm_data(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Import SDM data into a CASA measurement set.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing SDM_name and msname

    Returns
    -------
    dict
        Updated pipeline context
    """
    SDM_name = pipeline_context.get("SDM_name")
    msname = pipeline_context.get("msname")

    if not SDM_name or not msname:
        task_logprint("Error: Missing SDM_name or msname in pipeline context")
        pipeline_context["QA2_import"] = "Fail"
        return pipeline_context

    task_logprint("*** Starting ASDM Import ***")
    runtiming("import", "start")

    # Get organized paths
    ms_path = get_measurement_set_path(msname)
    flags_path = MEASUREMENT_SETS_DIR / "onlineFlags.txt"

    # Clean up any existing files that might interfere
    task_logprint("Cleaning up existing files...")
    cleanup_import_files(SDM_name)

    # Update context with organized paths
    pipeline_context["ms_path"] = str(ms_path)
    pipeline_context["flags_path"] = str(flags_path)

    try:
        task_logprint(f"Importing {SDM_name} to {msname}")

        # Import the ASDM
        importasdm(
            asdm=SDM_name,
            vis=msname,
            ocorr_mode="co",  # Only cross correlations
            process_flags=True,  # Create online flags in FLAG_CMD
            savecmds=True,  # Save import flags
            outfile=f"{msname}_online_flags.txt",
            applyflags=False,
            flagbackup=False,
            process_syspower=True,
            process_pointing=True,
            verbose=False,
            overwrite=True,
        )

        task_logprint("ASDM import completed successfully")
        pipeline_context["QA2_import"] = "Pass"

    except Exception as e:
        task_logprint(f"ASDM import failed: {e}")
        pipeline_context["QA2_import"] = "Fail"
        raise

    runtiming("import", "end")
    return pipeline_context


def apply_hanning_smooth(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply Hanning smoothing to the visibility data.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname

    Returns
    -------
    dict
        Updated pipeline context
    """
    msname = pipeline_context.get("msname")

    if not msname:
        task_logprint("Error: Missing msname in pipeline context", "hanning")
        pipeline_context["QA2_hanning"] = "Fail"
        return pipeline_context

    task_logprint("*** Starting Hanning Smoothing ***", "hanning")
    runtiming("hanning", "start")

    try:
        task_logprint("Applying Hanning smoothing to data", "hanning")

        # Apply Hanning smoothing
        hanningsmooth(
            vis=msname,
            datacolumn="data",
            outputvis="temphanning.ms",
        )

        # Copy XML files to the output MS
        task_logprint("Copying XML files to output MS", "hanning")
        for filen in glob(f"{msname}/*.xml"):
            shutil.copy2(filen, "temphanning.ms/")

        # Replace original with Hanning-smoothed version
        task_logprint(f"Removing original MS {msname}", "hanning")
        shutil.rmtree(msname)

        task_logprint(f"Renaming temphanning.ms to {msname}", "hanning")
        os.rename("temphanning.ms", msname)

        task_logprint("Hanning smoothing completed successfully", "hanning")
        pipeline_context["QA2_hanning"] = "Pass"
        pipeline_context["hanning_applied"] = True

    except Exception as e:
        task_logprint(f"Hanning smoothing failed: {e}", "hanning")
        pipeline_context["QA2_hanning"] = "Fail"
        # Clean up partial results
        if os.path.exists("temphanning.ms"):
            shutil.rmtree("temphanning.ms")
        raise

    runtiming("hanning", "end")
    return pipeline_context


def import_with_optional_hanning(
    pipeline_context: Dict[str, Any], apply_hanning: bool = False
) -> Dict[str, Any]:
    """
    Import SDM data with optional Hanning smoothing.

    This is the main entry point that detects data type (SDM vs MS),
    imports if needed, applies optional Hanning, and tracks flagging.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing SDM_name
    apply_hanning : bool, optional
        Whether to apply Hanning smoothing after import

    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting Import with Optional Hanning ***")

    sdm_name = pipeline_context.get("SDM_name")
    if not sdm_name:
        task_logprint("Error: No SDM_name provided")
        pipeline_context["QA2_import"] = "Fail"
        return pipeline_context

    # Detect data type and determine MS name
    data_type, ms_name = detect_data_type(sdm_name)
    pipeline_context["data_type"] = data_type
    pipeline_context["msname"] = ms_name

    if data_type == "MS":
        task_logprint("Data is already an MS, skipping import")
        pipeline_context["QA2_import"] = "Skipped"
        pipeline_context["import_skipped"] = True

        # Validate fresh MS flagging
        validate_fresh_ms_flagging(ms_name)

        # Track initial flagging state
        pipeline_context = track_flagging_progression(pipeline_context, "initial_ms")

    else:
        task_logprint("Data is SDM, proceeding with import")
        # Step 1: Import ASDM data
        pipeline_context = import_asdm_data(pipeline_context)

        # Check if import was successful
        if pipeline_context.get("QA2_import") == "Fail":
            task_logprint("Import failed, skipping remaining steps")
            return pipeline_context

        # Validate fresh import flagging
        validate_fresh_ms_flagging(ms_name)

        # Track post-import flagging state
        pipeline_context = track_flagging_progression(pipeline_context, "post_import")

    # Step 2: Apply Hanning smoothing if requested
    if apply_hanning:
        task_logprint("Applying Hanning smoothing as requested")
        pipeline_context["do_hanning"] = True
        pipeline_context = apply_hanning_smooth(pipeline_context)

        # Track post-Hanning flagging state (should be same as before)
        if pipeline_context.get("QA2_hanning") == "Pass":
            pipeline_context = track_flagging_progression(
                pipeline_context, "post_hanning"
            )
    else:
        task_logprint("Skipping Hanning smoothing")
        pipeline_context["do_hanning"] = False
        pipeline_context["hanning_applied"] = False
        pipeline_context["QA2_hanning"] = "Skipped"

    # Final summary
    if "flagging_progression" in pipeline_context:
        progression = pipeline_context["flagging_progression"]
        if progression:
            latest = progression[-1]
            task_logprint(
                f"Final flagging state: {latest['flagged_fraction']:.4f} flagged"
            )

    task_logprint("*** Import with Optional Hanning Complete ***")
    return pipeline_context


# Convenience function for pipeline integration
def perform_data_import(
    pipeline_context: Dict[str, Any], apply_hanning: bool = False
) -> Dict[str, Any]:
    """
    Convenience function for pipeline integration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context
    apply_hanning : bool, optional
        Whether to apply Hanning smoothing

    Returns
    -------
    dict
        Updated pipeline context
    """
    return import_with_optional_hanning(pipeline_context, apply_hanning)
