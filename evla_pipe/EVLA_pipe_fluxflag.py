"""
Flag flux calibrator gain table interactively to remove bad times/antennas.

This module generates diagnostic plots for the flux gain calibration table
to identify problematic data that should be flagged.
"""

from typing import Dict, Any
from pathlib import Path

from evla_pipe.plotting import plotms
from evla_pipe.utils import logprint


def task_logprint(msg: str) -> None:
    """
    Centralized logging for flux flagging operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout='logs/fluxflag.log')


def fluxflag(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate diagnostic plots for flux gain calibration table.

    This function creates amplitude vs time plots for the flux gain calibration
    table to help identify bad data that should be flagged. This is typically
    used for interactive flagging and is not part of the regular automated
    pipeline.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing:
        - msname : str (optional, used to determine working directory)
        - flux_gaincal_table : str (optional, default: "fluxgaincal.g")
        - plot_dir : str (optional, default: current directory)

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_fluxflag : str
            Quality assessment flag ("Pass" or "Fail")
        - fluxflag_plot : str
            Path to generated diagnostic plot
        - error_message : str (only if an error occurred)

    Notes
    -----
    This module generates plots but does not automatically apply flags.
    The user should review the plots and manually flag problematic data
    if needed.

    Examples
    --------
    >>> context = {"msname": "test.ms"}
    >>> context = fluxflag(context)
    >>> print(context["QA2_fluxflag"])
    Pass
    """
    task_logprint("*** Starting Flux Gain Calibration Flagging Diagnostics ***")

    # Get configuration from context with defaults
    flux_gaincal_table = pipeline_context.get("flux_gaincal_table", "fluxgaincal.g")
    plot_dir = pipeline_context.get("plot_dir", ".")

    # Construct output plot path
    plot_filename = "fluxgaincal_time_amp.png"
    plot_path = Path(plot_dir) / plot_filename

    task_logprint(f"Generating diagnostic plot for {flux_gaincal_table}")
    task_logprint(f"Output plot: {plot_path}")

    try:
        # Check if gain table exists
        if not Path(flux_gaincal_table).exists():
            raise FileNotFoundError(
                f"Flux gain calibration table not found: {flux_gaincal_table}"
            )

        # Generate diagnostic plot
        plotms(
            vis=flux_gaincal_table,
            xaxis="time",
            yaxis="amp",
            showgui=False,
            plotfile=str(plot_path),
            highres=True,
            overwrite=True,
        )

        # Verify plot was created
        if not plot_path.exists():
            raise RuntimeError(
                f"Plot generation completed but file not found: {plot_path}"
            )

        # Update context with success
        pipeline_context["QA2_fluxflag"] = "Pass"
        pipeline_context["fluxflag_plot"] = str(plot_path)

        task_logprint(f"Successfully generated diagnostic plot: {plot_path}")
        task_logprint("Review plot to identify data requiring manual flagging")

    except FileNotFoundError as e:
        task_logprint(f"Error: {e}")
        pipeline_context["QA2_fluxflag"] = "Fail"
        pipeline_context["error_message"] = str(e)

    except Exception as e:
        task_logprint(f"Error generating flux flagging diagnostic plot: {e}")
        pipeline_context["QA2_fluxflag"] = "Fail"
        pipeline_context["error_message"] = str(e)

    task_logprint("*** Finished Flux Gain Calibration Flagging Diagnostics ***")

    return pipeline_context


if __name__ == "__main__":
    # Example usage for testing
    test_context: Dict[str, Any] = {
        "flux_gaincal_table": "fluxgaincal.g",
        "plot_dir": "."
    }

    result_context = fluxflag(test_context)
    print(f"QA2 Status: {result_context.get('QA2_fluxflag')}")
    if result_context.get("fluxflag_plot"):
        print(f"Plot created: {result_context['fluxflag_plot']}")
