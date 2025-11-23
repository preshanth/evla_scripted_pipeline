"""
Centralized Pipeline Configuration

Single source of truth for paths, thresholds, and defaults.
"""

import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any


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


def load_config_file(config_path: Path) -> PipelineConfig:
    """
    Load configuration from YAML file.

    Parameters
    ----------
    config_path : Path
        Path to YAML configuration file

    Returns
    -------
    PipelineConfig
        Loaded configuration

    Examples
    --------
    >>> config = load_config_file("evla_config.yaml")
    >>> config.minsnr
    3.5
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)

    # Convert string paths to Path objects
    for key in config_dict.keys():
        if key.endswith('_dir'):
            config_dict[key] = Path(config_dict[key])

    return PipelineConfig(**config_dict)


def save_config_file(config: PipelineConfig, config_path: Path) -> None:
    """
    Save configuration to YAML file.

    Parameters
    ----------
    config : PipelineConfig
        Configuration to save
    config_path : Path
        Path to save YAML configuration file

    Examples
    --------
    >>> config = PipelineConfig(minsnr=3.5, flag_critfrac=0.7)
    >>> save_config_file(config, "my_config.yaml")
    """
    config_path = Path(config_path)

    # Convert to dictionary
    config_dict = asdict(config)

    # Convert Path objects to strings
    for key, value in config_dict.items():
        if isinstance(value, Path):
            config_dict[key] = str(value)

    with open(config_path, 'w') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


def create_default_config_file(config_path: Path) -> None:
    """
    Create a default configuration file with documentation.

    Parameters
    ----------
    config_path : Path
        Path to save default configuration file

    Examples
    --------
    >>> create_default_config_file("evla_config.yaml")
    """
    config_path = Path(config_path)

    default_config_yaml = """# EVLA Pipeline Configuration
#
# This file contains all configurable parameters for the EVLA scripted pipeline.
# Copy and modify this file to customize pipeline behavior.

# Directory structure
log_dir: logs
weblog_dir: weblog
plots_dir: plots
measurement_sets_dir: measurement_sets
caltables_dir: final_caltables
intermediate_caltables_dir: intermediate_caltables
test_caltables_dir: test_caltables
context_dir: pipeline_context
backup_dir: pipeline_backups

# Flagging thresholds
flag_critfrac: 0.6  # Critical fraction for partial QA (0.0-1.0)
shadow_diameter: 0.0  # Shadow flagging diameter in meters

# Calibration parameters
minsnr: 3.0  # Minimum SNR for calibration solutions
minblperant: 4  # Minimum baselines per antenna

# Logging
log_level: INFO  # DEBUG, INFO, WARNING, ERROR
log_to_console: true
log_to_file: true

# State management
state_file: pipeline_state.json
enable_checkpoints: true

# Plotting
enable_plots: true
plot_format: png
"""

    with open(config_path, 'w') as f:
        f.write(default_config_yaml)
