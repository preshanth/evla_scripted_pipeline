"""
Centralized Pipeline Configuration

Single source of truth for paths, thresholds, and defaults.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PipelineConfig:
    """
    Central configuration for EVLA pipeline.

    All paths, thresholds, and defaults are defined here.
    """

    # Directory structure
    log_dir: Path = Path("logs")
    weblog_dir: Path = Path("weblog")
    plots_dir: Path = Path("plots")
    measurement_sets_dir: Path = Path("measurement_sets")
    caltables_dir: Path = Path("final_caltables")
    intermediate_caltables_dir: Path = Path("intermediate_caltables")
    test_caltables_dir: Path = Path("test_caltables")
    context_dir: Path = Path("pipeline_context")
    backup_dir: Path = Path("pipeline_backups")

    # Flagging thresholds
    flag_critfrac: float = 0.6  # Critical fraction for partial QA
    shadow_diameter: float = 0.0  # Shadow flagging diameter

    # Calibration parameters
    minsnr: float = 3.0  # Minimum SNR for calibration solutions
    minblperant: int = 4  # Minimum baselines per antenna

    # Logging
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_to_console: bool = True
    log_to_file: bool = True

    # State management
    state_file: str = "pipeline_state.json"
    enable_checkpoints: bool = True

    # Plotting
    enable_plots: bool = True
    plot_format: str = "png"

    def __post_init__(self):
        """Ensure all directories exist."""
        for attr_name in dir(self):
            if attr_name.endswith("_dir"):
                path = getattr(self, attr_name)
                if isinstance(path, Path):
                    path.mkdir(exist_ok=True, parents=True)

    def get_log_path(self, name: str) -> Path:
        """Get path to log file."""
        return self.log_dir / f"{name}.log"

    def get_weblog_path(self, filename: str = "") -> Path:
        """Get path to weblog file or directory."""
        if filename:
            return self.weblog_dir / filename
        return self.weblog_dir

    def get_plot_path(self, filename: str) -> Path:
        """Get path to plot file."""
        return self.plots_dir / filename

    def get_caltable_path(self, table_name: str, intermediate: bool = False) -> Path:
        """Get path to calibration table."""
        base_dir = self.intermediate_caltables_dir if intermediate else self.caltables_dir
        return base_dir / table_name


# Global default configuration (can be overridden)
DEFAULT_CONFIG = PipelineConfig()


def get_config() -> PipelineConfig:
    """Get current pipeline configuration."""
    return DEFAULT_CONFIG
