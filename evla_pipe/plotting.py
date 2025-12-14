"""
Centralized plotting functionality for EVLA Pipeline.

This module provides a unified interface for all plotting operations,
handling casaplotms imports and providing consistent plotting utilities.
"""

import warnings
from typing import Dict, List, Optional

# Handle casaplotms import with fallback
try:
    from casaplotms import plotms

    PLOTMS_AVAILABLE = True
except ImportError as e:
    warnings.warn(f"casaplotms not available: {e}", stacklevel=2)
    PLOTMS_AVAILABLE = False

    def plotms(*args, **kwargs):
        """Fallback plotms function when casaplotms is not available."""
        warnings.warn(
            "plotms called but casaplotms not available - skipping plot", stacklevel=2
        )
        return None


# Import other plotting utilities
try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    warnings.warn(
        "matplotlib not available - some plotting features disabled", stacklevel=2
    )

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    warnings.warn("numpy not available - some plotting features disabled", stacklevel=2)


def is_plotting_available() -> bool:
    """Check if plotting capabilities are available."""
    return PLOTMS_AVAILABLE


def create_plotms_plot(vis: str, xaxis: str, yaxis: str, **kwargs) -> bool:
    """
    Create a plotms plot with error handling.

    Parameters
    ----------
    vis : str
        Visibility file path
    xaxis : str
        X-axis parameter
    yaxis : str
        Y-axis parameter
    **kwargs
        Additional plotms parameters

    Returns
    -------
    bool
        True if plot was created successfully, False otherwise
    """
    if not PLOTMS_AVAILABLE:
        warnings.warn("plotms not available - skipping plot", stacklevel=2)
        return False

    try:
        plotms(vis=vis, xaxis=xaxis, yaxis=yaxis, **kwargs)
        return True
    except Exception as e:
        warnings.warn(f"plotms failed: {e}", stacklevel=2)
        return False


def plot_calibration_table(
    caltable: str, xaxis: str, yaxis: str, plotfile: Optional[str] = None, **kwargs
) -> bool:
    """
    Plot a calibration table using plotms.

    Parameters
    ----------
    caltable : str
        Calibration table path
    xaxis : str
        X-axis parameter
    yaxis : str
        Y-axis parameter
    plotfile : str, optional
        Output plot file path
    **kwargs
        Additional plotms parameters

    Returns
    -------
    bool
        True if plot was created successfully, False otherwise
    """
    if not PLOTMS_AVAILABLE:
        warnings.warn(
            "plotms not available - skipping calibration table plot", stacklevel=2
        )
        return False

    plot_params = {
        "vis": caltable,
        "xaxis": xaxis,
        "yaxis": yaxis,
        "showgui": False,
        "clearplots": True,
    }

    if plotfile:
        plot_params.update(
            {
                "plotfile": plotfile,
                "expformat": "png",
                "exprange": "all",
                "highres": True,
                "overwrite": True,
            }
        )

    plot_params.update(kwargs)

    try:
        plotms(**plot_params)
        return True
    except Exception as e:
        warnings.warn(f"Calibration table plot failed: {e}", stacklevel=2)
        return False


def plot_visibility_data(
    vis: str,
    field: str,
    spw: str,
    xaxis: str = "time",
    yaxis: str = "amp",
    plotfile: Optional[str] = None,
    **kwargs,
) -> bool:
    """
    Plot visibility data using plotms.

    Parameters
    ----------
    vis : str
        Visibility file path
    field : str
        Field selection
    spw : str
        Spectral window selection
    xaxis : str, optional
        X-axis parameter (default: 'time')
    yaxis : str, optional
        Y-axis parameter (default: 'amp')
    plotfile : str, optional
        Output plot file path
    **kwargs
        Additional plotms parameters

    Returns
    -------
    bool
        True if plot was created successfully, False otherwise
    """
    if not PLOTMS_AVAILABLE:
        warnings.warn("plotms not available - skipping visibility plot", stacklevel=2)
        return False

    plot_params = {
        "vis": vis,
        "field": field,
        "spw": spw,
        "xaxis": xaxis,
        "yaxis": yaxis,
        "showgui": False,
        "clearplots": True,
    }

    if plotfile:
        plot_params.update(
            {
                "plotfile": plotfile,
                "expformat": "png",
                "exprange": "all",
                "highres": True,
                "overwrite": True,
            }
        )

    plot_params.update(kwargs)

    try:
        plotms(**plot_params)
        return True
    except Exception as e:
        warnings.warn(f"Visibility plot failed: {e}", stacklevel=2)
        return False


def plot_bandpass_solutions(
    caltable: str, plotfile: Optional[str] = None, **kwargs
) -> bool:
    """
    Plot bandpass solutions.

    Parameters
    ----------
    caltable : str
        Bandpass calibration table
    plotfile : str, optional
        Output plot file path
    **kwargs
        Additional plotms parameters

    Returns
    -------
    bool
        True if plot was created successfully, False otherwise
    """
    return plot_calibration_table(
        caltable=caltable, xaxis="chan", yaxis="amp", plotfile=plotfile, **kwargs
    )


def plot_gain_solutions(
    caltable: str, plotfile: Optional[str] = None, **kwargs
) -> bool:
    """
    Plot gain solutions.

    Parameters
    ----------
    caltable : str
        Gain calibration table
    plotfile : str, optional
        Output plot file path
    **kwargs
        Additional plotms parameters

    Returns
    -------
    bool
        True if plot was created successfully, False otherwise
    """
    return plot_calibration_table(
        caltable=caltable, xaxis="time", yaxis="amp", plotfile=plotfile, **kwargs
    )


def plot_phase_solutions(
    caltable: str, plotfile: Optional[str] = None, **kwargs
) -> bool:
    """
    Plot phase solutions.

    Parameters
    ----------
    caltable : str
        Calibration table
    plotfile : str, optional
        Output plot file path
    **kwargs
        Additional plotms parameters

    Returns
    -------
    bool
        True if plot was created successfully, False otherwise
    """
    return plot_calibration_table(
        caltable=caltable, xaxis="time", yaxis="phase", plotfile=plotfile, **kwargs
    )


def plot_flux_density_fit(
    frequencies: List[float],
    flux_densities: List[float],
    fit_coeffs: List[float],
    plotfile: Optional[str] = None,
) -> bool:
    """
    Plot flux density vs frequency with fitted model.

    Parameters
    ----------
    frequencies : List[float]
        Frequency values in Hz
    flux_densities : List[float]
        Flux density values in Jy
    fit_coeffs : List[float]
        Polynomial fit coefficients
    plotfile : str, optional
        Output plot file path

    Returns
    -------
    bool
        True if plot was created successfully, False otherwise
    """
    if not MATPLOTLIB_AVAILABLE or not NUMPY_AVAILABLE:
        warnings.warn(
            "matplotlib or numpy not available - skipping flux density plot",
            stacklevel=2,
        )
        return False

    try:
        import matplotlib.pyplot as plt
        import numpy as np

        # Convert to GHz for plotting
        freq_ghz = np.array(frequencies) / 1e9
        flux_jy = np.array(flux_densities)

        # Create fitted curve
        freq_fit = np.linspace(freq_ghz.min(), freq_ghz.max(), 100)
        log_freq_fit = np.log10(freq_fit)
        log_flux_fit = np.polyval(fit_coeffs, log_freq_fit)
        flux_fit = 10**log_flux_fit

        # Create plot
        plt.figure(figsize=(10, 6))
        plt.loglog(freq_ghz, flux_jy, "ro", label="Data")
        plt.loglog(freq_fit, flux_fit, "b-", label="Fitted Model")
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Flux Density (Jy)")
        plt.title("Flux Density vs Frequency")
        plt.legend()
        plt.grid(True, alpha=0.3)

        if plotfile:
            plt.savefig(plotfile, dpi=150, bbox_inches="tight")

        plt.close()
        return True

    except Exception as e:
        warnings.warn(f"Flux density plot failed: {e}", stacklevel=2)
        return False


def create_summary_plots(
    vis: str, output_dir: str = "plots", enable_plots: bool = True
) -> Dict[str, bool]:
    """
    Create summary plots for pipeline validation.

    Parameters
    ----------
    vis : str
        Visibility file path
    output_dir : str, optional
        Output directory for plots
    enable_plots : bool, optional
        Whether plotting is enabled

    Returns
    -------
    Dict[str, bool]
        Dictionary of plot names and success status
    """
    if not enable_plots:
        return {}

    import os

    os.makedirs(output_dir, exist_ok=True)

    results = {}

    # Amplitude vs time plot
    results["amp_vs_time"] = plot_visibility_data(
        vis=vis,
        field="",
        spw="",
        xaxis="time",
        yaxis="amp",
        plotfile=os.path.join(output_dir, "amp_vs_time.png"),
    )

    # Phase vs time plot
    results["phase_vs_time"] = plot_visibility_data(
        vis=vis,
        field="",
        spw="",
        xaxis="time",
        yaxis="phase",
        plotfile=os.path.join(output_dir, "phase_vs_time.png"),
    )

    # Amplitude vs frequency plot
    results["amp_vs_freq"] = plot_visibility_data(
        vis=vis,
        field="",
        spw="",
        xaxis="freq",
        yaxis="amp",
        plotfile=os.path.join(output_dir, "amp_vs_freq.png"),
    )

    return results


# Legacy compatibility - re-export plotms for existing code
__all__ = [
    "plotms",
    "is_plotting_available",
    "create_plotms_plot",
    "plot_calibration_table",
    "plot_visibility_data",
    "plot_bandpass_solutions",
    "plot_gain_solutions",
    "plot_phase_solutions",
    "plot_flux_density_fit",
    "create_summary_plots",
    "PLOTMS_AVAILABLE",
    "MATPLOTLIB_AVAILABLE",
    "NUMPY_AVAILABLE",
]
