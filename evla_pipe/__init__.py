######################################################################
#
# Copyright (C) 2013
# Associated Universities, Inc. Washington DC, USA,
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Library General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Library General Public
# License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with this library; if not, write to the Free Software Foundation,
# Inc., 675 Massachusetts Ave, Cambridge, MA 02139, USA.
#
# Correspondence concerning VLA Pipelines should be addressed as follows:
#    Please register and submit helpdesk tickets via: https://help.nrao.edu
#    Postal address:
#              National Radio Astronomy Observatory
#              VLA Pipeline Support Office
#              PO Box O
#              Socorro, NM,  USA
#
######################################################################

"""
EVLA Scripted Pipeline

A Python package for automated calibration of VLA continuum data.
"""

import os
import shelve
import warnings
from pathlib import Path

__version__ = (2, 0, 0)
__version_str__ = ".".join(str(i) for i in __version__)
__author__ = "National Radio Astronomy Observatory"
__email__ = "help@nrao.edu"
__description__ = "Automated calibration pipeline for VLA data"

# Package path
PIPE_PATH = Path(__file__).parent

# Utility functions for pipeline state management
def pipeline_save(filen="pipeline_shelf.restore"):
    """Save pipeline state to a shelf file."""
    with shelve.open(filen, "c") as shelf:
        with open(PIPE_PATH / "EVLA_pipe_restore.list") as f:
            lines = f.read().split("\n")
        for key in lines:
            if key == "":
                continue
            try:
                shelf[key] = globals()[key]
            except KeyError:
                pass


def pipeline_restore(filen="pipeline_shelf.restore"):
    """Restore pipeline state from a shelf file."""
    if not os.path.exists(filen):
        raise ValueError(f"Restore point does not exist: {filen}")
    else:
        with shelve.open(filen) as shelf:
            globals().update(shelf)


def execfile(filepath, global_vars=None):
    """Execute a Python file with given global variables."""
    if global_vars is None:
        global_vars = {}
    global_vars.update({
        "__file__": filepath,
        "__name__": "__main__",
    })
    with open(filepath, "rb") as f:
        source = compile(f.read(), filepath, "exec")
    exec(source, global_vars, global_vars)


def exec_script(name, context):
    """Execute a pipeline script with given context."""
    script_path = str(PIPE_PATH / f"{name}.py")
    execfile(script_path, global_vars=context)


# Import main pipeline functions
try:
    from .pipeline import continuum, check_casa_version
    from .polarization import PolarizationCalibrator, PolConfig, PolCalibrator
    from .polarization import find_pol_calibrators, calibrate_polarization_full
except ImportError:
    # Fallback if pipeline module doesn't exist yet
    def continuum(*args, **kwargs):
        raise NotImplementedError("Pipeline module not yet implemented")
    
    def check_casa_version():
        try:
            from casatasks import version
            casa_version = tuple(version())
            assert len(casa_version) == 4
            if casa_version[0] != 6:
                raise RuntimeError("This scripted pipeline is built for use with CASA 6.")
            if casa_version[:-1] < (6, 1, 0):
                raise RuntimeError("This scripted pipeline requires CASA v6.1.0 or later.")
            return casa_version
        except ImportError:
            warnings.warn("CASA not available - version check skipped")
            return None
    
    class PolarizationCalibrator:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Polarization module not yet implemented")
    
    class PolConfig:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Polarization module not yet implemented")
            
    class PolCalibrator:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Polarization module not yet implemented")
    
    def find_pol_calibrators(*args, **kwargs):
        raise NotImplementedError("Polarization module not yet implemented")
        
    def calibrate_polarization_full(*args, **kwargs):
        raise NotImplementedError("Polarization module not yet implemented")

__all__ = [
    "continuum",
    "check_casa_version", 
    "pipeline_save",
    "pipeline_restore",
    "execfile",
    "exec_script",
    "PolarizationCalibrator",
    "PolConfig", 
    "PolCalibrator",
    "find_pol_calibrators",
    "calibrate_polarization_full",
    "__version__",
    "__version_str__",
    "PIPE_PATH"
]