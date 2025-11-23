"""
Metadata preservation and provenance tracking.

Records pipeline processing history in measurement set HISTORY table
for full scientific reproducibility.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from evla_pipe.logging_config import get_logger

logger = get_logger(__name__)


def record_pipeline_step(
    msname: str,
    step_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    status: str = "started"
) -> None:
    """
    Record pipeline step in MS HISTORY table.

    Parameters
    ----------
    msname : str
        Measurement set name
    step_name : str
        Pipeline step name (e.g., 'EVLA_pipe_finalcals')
    parameters : dict, optional
        Step parameters to record
    status : str
        Step status: 'started', 'completed', 'failed'
    """
    try:
        from casatools import table
        tb = table()

        history_table = f"{msname}/HISTORY"

        # Check if MS exists
        if not Path(msname).exists():
            logger.warning(f"MS not found for history recording: {msname}")
            return

        # Open HISTORY table
        tb.open(history_table, nomodify=False)

        # Get current number of rows
        nrows = tb.nrows()

        # Add new row
        tb.addrows(1)

        # Prepare message
        timestamp = datetime.now().isoformat()
        message = f"EVLA Pipeline Step: {step_name} [{status}]"

        if parameters:
            # Format parameters (avoid huge dumps)
            param_str = ", ".join(f"{k}={v}" for k, v in list(parameters.items())[:10])
            if len(parameters) > 10:
                param_str += f", ... ({len(parameters)} total parameters)"
            message += f"\nParameters: {param_str}"

        # Write to HISTORY table
        tb.putcell("TIME", nrows, datetime.now().timestamp())
        tb.putcell("MESSAGE", nrows, message)
        tb.putcell("PRIORITY", nrows, "INFO")
        tb.putcell("ORIGIN", nrows, f"EVLA Pipeline v2.0 - {step_name}")
        tb.putcell("APPLICATION", nrows, "evla_pipe")

        tb.close()

        logger.debug(f"Recorded history: {step_name} [{status}]")

    except ImportError:
        logger.warning("casatools not available, skipping history recording")
    except Exception as e:
        logger.warning(f"Failed to record history for {step_name}: {e}")


def record_pipeline_metadata(msname: str, pipeline_context: Dict[str, Any]) -> None:
    """
    Record complete pipeline metadata in MS.

    Parameters
    ----------
    msname : str
        Measurement set name
    pipeline_context : dict
        Complete pipeline context with all parameters
    """
    # Extract key metadata
    metadata = {
        "pipeline_version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "do_hanning": pipeline_context.get("do_hanning", False),
        "do_polarization": pipeline_context.get("do_pol", False),
        "refant": pipeline_context.get("refant", "unknown"),
    }

    # Record QA scores
    qa_keys = [k for k in pipeline_context.keys() if k.startswith("QA2_")]
    for key in qa_keys:
        metadata[key] = pipeline_context[key]

    record_pipeline_step(
        msname,
        "EVLA_pipeline_complete",
        parameters=metadata,
        status="completed"
    )


def get_processing_history(msname: str) -> list:
    """
    Retrieve processing history from MS HISTORY table.

    Parameters
    ----------
    msname : str
        Measurement set name

    Returns
    -------
    list
        List of history entries
    """
    try:
        from casatools import table
        tb = table()

        history_table = f"{msname}/HISTORY"

        if not Path(msname).exists():
            logger.warning(f"MS not found: {msname}")
            return []

        tb.open(history_table)

        # Read all columns
        times = tb.getcol("TIME")
        messages = tb.getcol("MESSAGE")
        origins = tb.getcol("ORIGIN")

        tb.close()

        # Combine into list of dicts
        history = []
        for i in range(len(times)):
            history.append({
                "time": datetime.fromtimestamp(times[i]).isoformat(),
                "message": messages[i],
                "origin": origins[i]
            })

        # Filter for EVLA Pipeline entries
        pipeline_history = [h for h in history if "EVLA Pipeline" in h.get("message", "")]

        return pipeline_history

    except ImportError:
        logger.warning("casatools not available")
        return []
    except Exception as e:
        logger.warning(f"Failed to read history: {e}")
        return []
