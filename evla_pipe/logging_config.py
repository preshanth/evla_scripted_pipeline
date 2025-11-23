"""
Standard Python Logging Configuration

Replaces custom logprint with Python's logging module.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from evla_pipe.config import get_config


# Logger instances for each module
_loggers = {}


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module.

    Parameters
    ----------
    name : str
        Module name (usually __name__)

    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    _loggers[name] = logger
    return logger


def setup_logging(
    log_level: str = "INFO",
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_file: Optional[Path] = None,
) -> None:
    """
    Configure logging for the pipeline.

    Parameters
    ----------
    log_level : str
        Logging level (DEBUG, INFO, WARNING, ERROR)
    log_to_console : bool
        Whether to log to console
    log_to_file : bool
        Whether to log to file
    log_file : Path, optional
        Log file path (default: logs/pipeline.log)
    """
    config = get_config()

    # Root logger
    root_logger = logging.getLogger("evla_pipe")
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_to_file:
        if log_file is None:
            log_file = config.get_log_path("pipeline")

        log_file.parent.mkdir(exist_ok=True, parents=True)
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(logging.DEBUG)  # Always DEBUG to file
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def log_to_file(logger: logging.Logger, filename: str) -> None:
    """
    Add file handler for specific log file.

    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    filename : str
        Log filename (e.g., "hanning.log")
    """
    config = get_config()
    log_path = config.get_log_path(filename)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, mode="a")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# Backward compatibility: logprint function
def logprint(
    message: str,
    logfileout: Optional[str] = None,
    printonly: bool = False,
) -> None:
    """
    Legacy logprint function for backward compatibility.

    Parameters
    ----------
    message : str
        Message to log
    logfileout : str, optional
        Log file path (e.g., "logs/hanning.log")
    printonly : bool
        If True, only print to console
    """
    logger = get_logger("evla_pipe.legacy")

    # Log at INFO level
    logger.info(message)

    # If specific log file requested, add handler
    if logfileout and not printonly:
        # Extract filename from path
        filename = Path(logfileout).name
        log_to_file(logger, filename)


# Initialize default logging
setup_logging()
