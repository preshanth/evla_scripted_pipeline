######################################################################
#
# EVLA Pipeline Core Functions
#
######################################################################

"""
Core pipeline functions for EVLA data processing.
"""

import warnings
from evla_pipe import exec_script, __version_str__
from evla_pipe.compat import import_casa_modules

# Test CASA availability and import polarization module accordingly
casa_modules = import_casa_modules()
if casa_modules['available']:
    try:
        from .polarization import integrate_polarization_calibration
        POLARIZATION_AVAILABLE = True
    except ImportError as e:
        warnings.warn(f"Polarization module not available: {e}")
        POLARIZATION_AVAILABLE = False
        
        def integrate_polarization_calibration(*args, **kwargs):
            raise NotImplementedError("Polarization calibration requires CASA to be available")
else:
    warnings.warn(f"CASA modules not available: {casa_modules.get('error', 'Unknown error')}")
    POLARIZATION_AVAILABLE = False
    
    def integrate_polarization_calibration(*args, **kwargs):
        raise NotImplementedError("Polarization calibration requires CASA to be available")


def check_casa_version():
    """Check CASA version compatibility."""
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


def continuum(sdm_name, skip_hanning=False, verbose=False, context=None, enable_polarization=False, enable_plots=True, resume_from=None, skip_steps=None):
    """
    Run the EVLA continuum calibration pipeline.
    
    Parameters
    ----------
    sdm_name : str
        SDM directory name (without .ms extension)
    skip_hanning : bool, optional
        Skip Hanning smoothing step (recommended for spectral line projects)
    verbose : bool, optional
        Enable verbose output
    context : dict, optional
        Pipeline context dictionary. If None, a new context is created.
    enable_polarization : bool, optional
        Enable polarization calibration (default: False)
    enable_plots : bool, optional
        Enable plotting output (default: True)
    
    Returns
    -------
    dict
        Updated pipeline context
        
    Examples
    --------
    >>> from evla_pipe import continuum
    >>> result = continuum('my_dataset')
    >>> result = continuum('my_dataset', skip_hanning=True)
    """
    if verbose:
        print(f":: Starting EVLA continuum pipeline v{__version_str__}")
        
    if context is None:
        context = {}
    
    # Set SDM name, polarization flag, and plotting flag in context
    if sdm_name:
        context["SDM_name"] = sdm_name
    context["do_pol"] = enable_polarization
    context["do_hanning"] = not skip_hanning  # Convert skip_hanning to do_hanning
    context["enable_plots"] = enable_plots
    
    if skip_steps is None:
        skip_steps = []
    
    # Try to load previous context if resuming
    if resume_from:
        import json
        context_file = f"pipeline_context_{resume_from}.json"
        try:
            with open(context_file, 'r') as f:
                saved_context = json.load(f)
                context.update(saved_context)
                if verbose:
                    print(f":: Resumed context from {context_file}")
        except FileNotFoundError:
            if verbose:
                print(f":: Context file {context_file} not found, starting fresh")
    
    def should_skip_step(step_name):
        """Check if step should be skipped."""
        return step_name in skip_steps
    
    def should_resume_from_step(step_name):
        """Check if we should start from this step."""
        if resume_from is None:
            return True
        return step_name == resume_from or context.get("started_resume", False)
    
    def exec_step(step_name, allow_failure=False):
        """Execute a pipeline step with skip/resume logic."""
        if should_skip_step(step_name):
            if verbose:
                print(f":: Skipping {step_name} (user requested)")
            return
        
        if not should_resume_from_step(step_name):
            if verbose:
                print(f":: Skipping {step_name} (not at resume point yet)")
            return
            
        # Mark that we've started resuming
        if resume_from == step_name:
            context["started_resume"] = True
            
        return exec_script(step_name, context, allow_failure=allow_failure)
    
    try:
        # The following script includes all the definitions and functions and
        # prior inputs needed by a run of the pipeline.
        if verbose:
            print(":: Running startup script")
        exec_step("EVLA_pipe_startup")

        # Import the data to CASA.
        if verbose:
            print(":: Importing data")
        exec_step("EVLA_pipe_import")

        # Hanning smooth (optional step)
        if not skip_hanning:
            if verbose:
                print(":: Applying Hanning smoothing")
            exec_step("EVLA_pipe_hanning", allow_failure=True)  # Non-critical
        elif verbose:
            print(":: Skipping Hanning smoothing")

        # Get information from the MS that will be needed later (modern msmetadata API)
        if verbose:
            print(":: Gathering MS information")
        exec_step("EVLA_pipe_msmd")

        # Deterministic flagging
        if verbose:
            print(":: Applying deterministic flags")
        exec_step("EVLA_pipe_flagall")

        # Prepare for calibrations
        if verbose:
            print(":: Preparing calibrations")
        exec_step("EVLA_pipe_calprep")

        # Apply "prior" calibrations
        if verbose:
            print(":: Applying prior calibrations")
        exec_step("EVLA_pipe_priorcals")

        # Initial test calibrations
        if verbose:
            print(":: Running initial test calibrations")
        exec_step("EVLA_pipe_testBPdcals")

        # Flag bad deformatters
        if verbose:
            print(":: Flagging bad deformatters")
        exec_step("EVLA_pipe_flag_baddeformatters", allow_failure=True)  # Non-critical

        # Flag RFI on bandpass calibrator
        if verbose:
            print(":: Flagging RFI on bandpass calibrator")
        exec_step("EVLA_pipe_checkflag", allow_failure=True)  # Non-critical

        # Semi-final delay and bandpass calibrations
        if verbose:
            print(":: Running semi-final BP/delay calibrations")
        exec_step("EVLA_pipe_semiFinalBPdcals1")

        # Additional flagging on calibrators
        if verbose:
            print(":: Additional flagging on calibrators")
        exec_step("EVLA_pipe_checkflag_semiFinal", allow_failure=True)  # Non-critical

        # Re-run semi-final calibrations
        if verbose:
            print(":: Re-running semi-final BP/delay calibrations")
        exec_step("EVLA_pipe_semiFinalBPdcals1")

        # Determine solution interval
        if verbose:
            print(":: Determining solution intervals")
        exec_step("EVLA_pipe_solint", allow_failure=True)  # Can use defaults

        # Test gain calibrations
        if verbose:
            print(":: Running test gain calibrations")
        exec_step("EVLA_pipe_testgains", allow_failure=True)  # Can use defaults

        # Flux density bootstrapping gains
        if verbose:
            print(":: Creating flux bootstrapping gains")
        exec_step("EVLA_pipe_fluxgains", allow_failure=True)  # Can skip if problematic

        # Flux density bootstrapping
        if verbose:
            print(":: Performing flux density bootstrapping")
        exec_step("EVLA_pipe_fluxboot", allow_failure=True)  # Can skip if problematic

        # Final calibration tables
        if verbose:
            print(":: Creating final calibration tables")
        exec_step("EVLA_pipe_finalcals")

        # Polarization calibration (if enabled) - must run BEFORE applycals
        if enable_polarization:
            if verbose:
                print(":: Running polarization calibration (Df, Xf)")
            context = integrate_polarization_calibration(context)

        # Apply all calibrations (including polarization if enabled)
        if verbose:
            print(":: Applying all calibrations")
        exec_step("EVLA_pipe_applycals")

        # Target flagging
        if verbose:
            print(":: Flagging calibrated target data")
        exec_step("EVLA_pipe_targetflag")

        # Statistical weights
        if verbose:
            print(":: Calculating statistical weights")
        exec_step("EVLA_pipe_statwt")

        # Final plots
        if verbose:
            print(":: Creating final plots")
        exec_step("EVLA_pipe_plotsummary", allow_failure=True)  # Plots are non-critical

        # Collect files
        if verbose:
            print(":: Collecting output files")
        exec_step("EVLA_pipe_filecollect", allow_failure=True)  # File collection is non-critical

        # Write weblog
        if verbose:
            print(":: Generating modern weblog")
        from .modern_weblog import EVLA_pipe_modern_weblog
        context = EVLA_pipe_modern_weblog(context)
        
    except KeyboardInterrupt as e:
        if verbose:
            print(f":: Pipeline interrupted: {e}")
        raise
    except Exception as e:
        if verbose:
            print(f":: Pipeline error: {e}")
        raise
    
    if verbose:
        print(":: Pipeline completed successfully")
    
    return context