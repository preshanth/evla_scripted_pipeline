"""Lightweight, pure-Python utility helpers for unit testing and CI.

This module duplicates a small subset of `evla_pipe.utils` but without any
CASA imports so it can be safely imported in CI environments that do not
provide CASA packages.
"""

from pathlib import Path
from typing import List

import numpy as np


def format_qa_status(qa_status: str) -> str:
    if qa_status == "Pass":
        return "\u2713 Pass"
    elif qa_status == "Fail":
        return "\u2717 Fail"
    else:
        return f"! {qa_status}"


def get_caltable_path(table_name: str, table_type: str = "final") -> str:
    if table_type == "final":
        return str(Path("final_caltables") / table_name)
    elif table_type == "intermediate":
        return str(Path("intermediate_caltables") / table_name)
    elif table_type == "test":
        return str(Path("test_caltables") / table_name)
    elif table_type == "prior":
        return str(Path("intermediate_caltables") / table_name)
    else:
        return table_name


def get_log_path(log_name: str) -> Path:
    return Path("logs") / log_name


def get_weblog_path(filename: str) -> Path:
    return Path("weblog") / filename


def get_plot_path(filename: str) -> Path:
    return Path("plots") / filename


def should_plot(pipeline_context: dict) -> bool:
    return pipeline_context.get("enable_plots", True)


def get_plot_output_path(filename: str, pipeline_context: dict) -> str:
    if not should_plot(pipeline_context):
        return ""
    return str(get_plot_path(filename))


def ensure_dir_exists(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_exists(path) -> bool:
    return Path(path).exists()


def join_paths(*args) -> str:
    return str(Path(*args))


def uniq(inlist: List) -> List:
    return np.unique(inlist).tolist()


def field_label(ctx: dict, field_str: str) -> str:
    """Convert a CASA field select string to a human-readable label.

    Examples
    --------
    "0"   → "0 (3C286)"
    "0,2" → "0 (3C286), 2 (J0259+0747)"
    ""    → ""
    """
    field_names = ctx.get("field_names", [])
    if not field_names or not field_str:
        return str(field_str)
    parts = []
    for part in str(field_str).split(","):
        part = part.strip()
        try:
            fid = int(part)
            name = field_names[fid] if fid < len(field_names) else "?"
            parts.append(f"{fid} ({name})")
        except ValueError:
            parts.append(part)
    return ", ".join(parts)


def find_EVLA_band(frequency: float) -> str:
    band_freqs = {
        "4": (0.00, 0.15),
        "P": (0.15, 0.70),
        "L": (0.70, 2.00),
        "S": (2.00, 4.00),
        "C": (4.00, 8.00),
        "X": (8.00, 12.00),
        "U": (12.00, 18.00),
        "K": (18.00, 26.50),
        "A": (26.50, 40.00),
        "Q": (40.00, 56.00),
    }
    freq_ghz = frequency / 1e9
    for name, (f_lo, f_hi) in band_freqs.items():
        if f_lo < freq_ghz <= f_hi:
            return name
    raise ValueError(f"Invalid EVLA frequency: {frequency}")
