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
EVLA Scripted Pipeline

A Python package for automated calibration of VLA continuum data.
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

def exec_script(name, context, allow_failure=False):
    """Execute a pipeline script with given context."""
    from datetime import datetime
    import json
    from evla_pipe.utils import PIPELINE_CONTEXT_DIR
    
    script_path = str(PIPE_PATH / f"{name}.py")
    
    # Save context before each step for resume capability
    context_file = str(PIPELINE_CONTEXT_DIR / f"pipeline_context_{name}.json")
    try:
        # Create a serializable copy of context
        serializable_context = {}
        for key, value in context.items():
            try:
                json.dumps(value)  # Test if serializable
                serializable_context[key] = value
            except (TypeError, ValueError):
                # Skip non-serializable values
                continue
        
        serializable_context["last_step"] = name
        serializable_context["timestamp"] = datetime.now().isoformat()
        
        with open(context_file, 'w') as f:
            json.dump(serializable_context, f, indent=2)
    except Exception:
        pass  # Don't fail if context save fails
    
    # Try to import and call as function first (new pattern)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check if function exists
        if hasattr(module, name):
            func = getattr(module, name)
            result = func(context)
            return result
        else:
            raise ImportError(f"Function '{name}' not found in module {name}.py - all pipeline scripts must be converted to function-based pattern")
            
    except Exception as e:
        print(f"\n🚨 Pipeline step '{name}' failed with error: {e}")
        
        if not allow_failure:
            # Save context with failure state
            try:
                context[f"QA2_{name.replace('EVLA_pipe_', '')}"] = "Fail"
                context["failed_step"] = name
                context["failure_error"] = str(e)
                
                serializable_context = convert_to_serializable(context)
                serializable_context["timestamp"] = datetime.now().isoformat()
                
                with open(context_file, 'w') as f:
                    json.dump(serializable_context, f, indent=2)
                    
                print(f"\n📋 Pipeline state saved to: {context_file}")
            except Exception:
                print(f"\n📋 Failed to save pipeline state")
                
            print(f"⚠️  To resume from this point, fix the issue and run:")
            print(f"   python -m evla_pipe.run_pipeline --resume-from {name} <your_data.asdm>")
            print(f"\n💡 Or to skip this step (if non-critical):")
            print(f"   python -m evla_pipe.run_pipeline --skip {name} <your_data.asdm>")
            raise e
        else:
            print(f"⚠️  Continuing despite failure in non-critical step '{name}'")
            return context


# Import main pipeline functions
try:
    from evla_pipe.pipeline import continuum, check_casa_version
    from evla_pipe.state_manager import PipelineStateManager
    from evla_pipe.pipeline_executor import PipelineExecutor, execute_pipeline_with_state_management
    from evla_pipe import plotting
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
    "continuum",
    "check_casa_version", 
    "exec_script",
    "PolarizationCalibrator",
    "PolConfig", 
    "PolCalibrator",
    "find_pol_calibrators",
    "calibrate_polarization_full",
    "__version__",
    "__version_str__",
    "PIPE_PATH",
    "PipelineStateManager",
    "PipelineExecutor",
    "execute_pipeline_with_state_management",
    "plotting"
]
