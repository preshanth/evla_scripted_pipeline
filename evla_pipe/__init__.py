######################################################################
#
# Copyright (C) 2025
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
EVLA Scripted Pipeline - Automated VLA Data Calibration

Modern, pythonic pipeline for VLA continuum observations.

Quick Start
-----------
From Python:
    >>> from evla_pipe import continuum
    >>> result = continuum('my_data.sdm')
    >>> result = continuum('my_data.sdm', enable_polarization=True)

From command line:
    $ evla-pipeline my_data.sdm
    $ evla-pipeline my_data.sdm --polarization --skip-hanning

Features
--------
- Automated calibration workflow
- Registry-based pipeline steps
- State management with checkpointing
- Modern weblog generation
- Polarization calibration support
- Resume from any step

See Also
--------
- Pipeline steps: evla_pipe.pipeline_steps
- Configuration: evla_pipe.config
- Exceptions: evla_pipe.exceptions
"""

import os
import warnings
from pathlib import Path

__version__ = (2, 0, 0)
__version_str__ = ".".join(str(i) for i in __version__)
__author__ = "National Radio Astronomy Observatory"
__email__ = "help@nrao.edu"
__description__ = "Automated calibration pipeline for VLA data"

# Package path
PIPE_PATH = Path(__file__).parent

# CASA version detection
try:
    from casatasks import version
    casa_version = tuple(version())
except ImportError:
    casa_version = None

def convert_to_serializable(context):
    """Convert context to JSON-serializable form."""
    import json
    serializable_context = {}
    for key, value in context.items():
        try:
            json.dumps(value)
            serializable_context[key] = value
        except (TypeError, ValueError):
            continue
    return serializable_context


def exec_script(name, context, allow_failure=False):
    """
    Execute a pipeline step.

    First tries to find step in registry (new pattern).
    Falls back to dynamic import for legacy scripts.
    """
    from datetime import datetime
    import json
    from evla_pipe.utils import PIPELINE_CONTEXT_DIR
    from evla_pipe.pipeline_steps import STEP_REGISTRY

    # Save context before each step
    context_file = str(PIPELINE_CONTEXT_DIR / f"pipeline_context_{name}.json")
    try:
        serializable_context = convert_to_serializable(context)
        serializable_context["last_step"] = name
        serializable_context["timestamp"] = datetime.now().isoformat()

        with open(context_file, 'w') as f:
            json.dump(serializable_context, f, indent=2)
    except Exception:
        pass

    try:
        # Registry lookup - all steps must be registered
        if name not in STEP_REGISTRY:
            raise KeyError(
                f"Pipeline step '{name}' not registered.\n"
                f"Available steps: {sorted(STEP_REGISTRY.keys())}\n"
                f"To register: Add '@register_step(\"{name}\")' decorator to function."
            )

        func = STEP_REGISTRY[name]
        result = func(context)
        return result

    except Exception as e:
        print(f"\n🚨 Pipeline step '{name}' failed: {e}")

        if not allow_failure:
            try:
                context[f"QA2_{name.replace('EVLA_pipe_', '')}"] = "Fail"
                context["failed_step"] = name
                context["failure_error"] = str(e)

                serializable_context = convert_to_serializable(context)
                serializable_context["timestamp"] = datetime.now().isoformat()

                with open(context_file, 'w') as f:
                    json.dump(serializable_context, f, indent=2)

                print(f"📋 Pipeline state saved to: {context_file}")
            except Exception:
                print("📋 Failed to save pipeline state")

            print(f"⚠️  To resume: python -m evla_pipe.run_pipeline --resume-from {name} <data.asdm>")
            print(f"💡 To skip: python -m evla_pipe.run_pipeline --skip {name} <data.asdm>")
            raise

        print(f"⚠️  Continuing despite failure in non-critical step '{name}'")
        return context


# Import main pipeline functions
try:
    from evla_pipe.pipeline import continuum, check_casa_version
    from evla_pipe.state_manager import PipelineStateManager
    from evla_pipe.pipeline_executor import PipelineExecutor, execute_pipeline_with_state_management
    from evla_pipe import plotting, pipeline_steps
    from evla_pipe.cleanup import cleanup_pipeline_products
    from evla_pipe.config import PipelineConfig, get_config
    from evla_pipe.exceptions import (
        PipelineError,
        ConfigurationError,
        DataError,
        CalibrationError,
        FlaggingError,
        CASAError,
    )
    from evla_pipe.logging_config import get_logger, setup_logging
    try:
        from evla_pipe.polarization import PolarizationCalibrator, PolConfig, PolCalibrator
        from evla_pipe.polarization import find_pol_calibrators, calibrate_polarization_full
    except ImportError:
        # Handle missing polarization dependencies
        class PolarizationCalibrator:
            def __init__(self, *args, **kwargs):
                raise NotImplementedError("Polarization module requires CASA to be available")
        
        class PolConfig:
            def __init__(self, *args, **kwargs):
                raise NotImplementedError("Polarization module requires CASA to be available")
                
        class PolCalibrator:
            def __init__(self, *args, **kwargs):
                raise NotImplementedError("Polarization module requires CASA to be available")
        
        def find_pol_calibrators(*args, **kwargs):
            raise NotImplementedError("Polarization module requires CASA to be available")
            
        def calibrate_polarization_full(*args, **kwargs):
            raise NotImplementedError("Polarization module requires CASA to be available")
    
    try:
        from evla_pipe.modern_weblog import EVLA_pipe_modern_weblog
        from evla_pipe.weblog_templates import create_weblog_generator
    except ImportError:
        def EVLA_pipe_modern_weblog(*args, **kwargs):
            raise NotImplementedError("Weblog module not available")
        def create_weblog_generator(*args, **kwargs):
            raise NotImplementedError("Weblog module not available")
            
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
    
    class PipelineStateManager:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("State management module not yet implemented")
    
    class PipelineExecutor:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Pipeline executor module not yet implemented")
    
    def execute_pipeline_with_state_management(*args, **kwargs):
        raise NotImplementedError("State management module not yet implemented")
    
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
    # Core pipeline
    "continuum",
    "check_casa_version",
    "exec_script",
    # Polarization
    "PolarizationCalibrator",
    "PolConfig",
    "PolCalibrator",
    "find_pol_calibrators",
    "calibrate_polarization_full",
    # Version info
    "__version__",
    "__version_str__",
    "casa_version",
    "PIPE_PATH",
    # State management
    "PipelineStateManager",
    "PipelineExecutor",
    "execute_pipeline_with_state_management",
    # Configuration
    "PipelineConfig",
    "get_config",
    # Exceptions
    "PipelineError",
    "ConfigurationError",
    "DataError",
    "CalibrationError",
    "FlaggingError",
    "CASAError",
    # Logging
    "get_logger",
    "setup_logging",
    # Modules
    "plotting",
    "cleanup_pipeline_products",
    "pipeline_steps",
]
