"""
EVLA Scripted Pipeline — automated calibration of VLA continuum data.
"""

import warnings
from pathlib import Path

__version__ = (2, 0, 0)
__version_str__ = ".".join(str(i) for i in __version__)
__author__ = "National Radio Astronomy Observatory"
__email__ = "help@nrao.edu"

PIPE_PATH = Path(__file__).parent

try:
    from casatasks import version as _casa_version_fn
    casa_version = tuple(_casa_version_fn())
except ImportError:
    casa_version = None


def check_casa_version():
    """Return CASA version tuple, or None if CASA is not installed."""
    if casa_version is None:
        warnings.warn("CASA not available — version check skipped", stacklevel=2)
        return None
    if casa_version[0] != 6:
        raise RuntimeError("This pipeline requires CASA 6.")
    if casa_version[:3] < (6, 1, 0):
        raise RuntimeError("This pipeline requires CASA >= 6.1.0.")
    return casa_version
