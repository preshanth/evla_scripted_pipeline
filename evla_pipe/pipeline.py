######################################################################
#
# EVLA Pipeline Core Functions
#
######################################################################

"""
Core pipeline functions for EVLA data processing.
"""

import warnings
from . import exec_script, __version_str__
from .polarization import integrate_polarization_calibration


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


def continuum(sdm_name, skip_hanning=False, verbose=False, context=None, enable_polarization=False):
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
    
    # Set SDM name and polarization flag in context
    if sdm_name:
        context["SDM_name"] = sdm_name
    context["do_pol"] = enable_polarization
    
    try:
        # The following script includes all the definitions and functions and
        # prior inputs needed by a run of the pipeline.
        if verbose:
            print(":: Running startup script")
        exec_script("EVLA_pipe_startup", context)

        # Import the data to CASA.
        if verbose:
            print(":: Importing data")
        exec_script("EVLA_pipe_import", context)

        # Hanning smooth (optional step)
        if not skip_hanning:
            if verbose:
                print(":: Applying Hanning smoothing")
            exec_script("EVLA_pipe_hanning", context)
        elif verbose:
            print(":: Skipping Hanning smoothing")

        # Get information from the MS that will be needed later
        if verbose:
            print(":: Gathering MS information")
        exec_script("EVLA_pipe_msinfo", context)

        # Deterministic flagging
        if verbose:
            print(":: Applying deterministic flags")
        exec_script("EVLA_pipe_flagall", context)

        # Prepare for calibrations
        if verbose:
            print(":: Preparing calibrations")
        exec_script("EVLA_pipe_calprep", context)

        # Apply "prior" calibrations
        if verbose:
            print(":: Applying prior calibrations")
        exec_script("EVLA_pipe_priorcals", context)

        # Initial test calibrations
        if verbose:
            print(":: Running initial test calibrations")
        exec_script("EVLA_pipe_testBPdcals", context)

        # Flag bad deformatters
        if verbose:
            print(":: Flagging bad deformatters")
        exec_script("EVLA_pipe_flag_baddeformatters", context)

        # Flag RFI on bandpass calibrator
        if verbose:
            print(":: Flagging RFI on bandpass calibrator")
        exec_script("EVLA_pipe_checkflag", context)

        # Semi-final delay and bandpass calibrations
        if verbose:
            print(":: Running semi-final BP/delay calibrations")
        exec_script("EVLA_pipe_semiFinalBPdcals1", context)

        # Additional flagging on calibrators
        if verbose:
            print(":: Additional flagging on calibrators")
        exec_script("EVLA_pipe_checkflag_semiFinal", context)

        # Re-run semi-final calibrations
        if verbose:
            print(":: Re-running semi-final BP/delay calibrations")
        exec_script("EVLA_pipe_semiFinalBPdcals1", context)

        # Determine solution interval
        if verbose:
            print(":: Determining solution intervals")
        exec_script("EVLA_pipe_solint", context)

        # Test gain calibrations
        if verbose:
            print(":: Running test gain calibrations")
        exec_script("EVLA_pipe_testgains", context)

        # Flux density bootstrapping gains
        if verbose:
            print(":: Creating flux bootstrapping gains")
        exec_script("EVLA_pipe_fluxgains", context)

        # Flux density bootstrapping
        if verbose:
            print(":: Performing flux density bootstrapping")
        exec_script("EVLA_pipe_fluxboot", context)

        # Final calibration tables
        if verbose:
            print(":: Creating final calibration tables")
        exec_script("EVLA_pipe_finalcals", context)

        # Apply all calibrations
        if verbose:
            print(":: Applying all calibrations")
        exec_script("EVLA_pipe_applycals", context)

        # Polarization calibration (if enabled)
        if enable_polarization:
            if verbose:
                print(":: Running polarization calibration")
            context = integrate_polarization_calibration(context)

        # Target flagging
        if verbose:
            print(":: Flagging calibrated target data")
        exec_script("EVLA_pipe_targetflag", context)

        # Statistical weights
        if verbose:
            print(":: Calculating statistical weights")
        exec_script("EVLA_pipe_statwt", context)

        # Final plots
        if verbose:
            print(":: Creating final plots")
        exec_script("EVLA_pipe_plotsummary", context)

        # Collect files
        if verbose:
            print(":: Collecting output files")
        exec_script("EVLA_pipe_filecollect", context)

        # Write weblog
        if verbose:
            print(":: Writing weblog")
        exec_script("EVLA_pipe_weblog", context)
        
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