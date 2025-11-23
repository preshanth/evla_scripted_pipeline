"""
Input data validation for pipeline.

Pre-flight checks to fail fast with clear error messages
instead of failing hours into pipeline execution.
"""

from pathlib import Path
from typing import Dict, Any

from evla_pipe.exceptions import DataError, ConfigurationError
from evla_pipe.logging_config import get_logger

logger = get_logger(__name__)


def validate_input_data(sdm_path: Path) -> Dict[str, Any]:
    """
    Validate SDM/MS before pipeline execution.

    Checks:
    - File exists
    - File size is reasonable
    - CASA can open it
    - Has required spectral windows
    - Has minimum number of antennas
    - Has calibration intents

    Parameters
    ----------
    sdm_path : Path
        Path to SDM or MS file

    Returns
    -------
    dict
        Metadata about the dataset

    Raises
    ------
    DataError
        If validation fails
    """
    logger.info(f"Validating input data: {sdm_path}")

    # Check exists
    if not sdm_path.exists():
        raise DataError(f"Data not found: {sdm_path}")

    # Check is directory (MS/SDM are directories)
    if not sdm_path.is_dir():
        raise DataError(f"Data is not a directory (MS/SDM must be directories): {sdm_path}")

    # Check size (MS/SDM should be > 1 MB)
    total_size = sum(f.stat().st_size for f in sdm_path.rglob('*') if f.is_file())
    if total_size < 1e6:  # < 1 MB
        raise DataError(
            f"Data suspiciously small: {total_size / 1e6:.2f} MB. "
            f"Expected at least 1 MB for valid MS/SDM"
        )

    logger.info(f"Data size: {total_size / 1e9:.2f} GB")

    # Try to open with CASA
    try:
        from casatools import msmetadata
        msmd = msmetadata()

        msmd.open(str(sdm_path))

        # Get basic metadata
        nspw = msmd.nspw()
        nant = msmd.nantennas()
        nscans = msmd.nscans()
        field_names = msmd.fieldnames()
        intents = msmd.intents()

        msmd.close()

        logger.info(f"Spectral windows: {nspw}")
        logger.info(f"Antennas: {nant}")
        logger.info(f"Scans: {nscans}")
        logger.info(f"Fields: {len(field_names)}")

    except ImportError:
        logger.warning("casatools not available, skipping CASA-based validation")
        return {'validated': True, 'method': 'basic'}
    except RuntimeError as e:
        raise DataError(f"Cannot open MS/SDM with CASA: {e}")

    # Validate spectral windows
    if nspw == 0:
        raise DataError("No spectral windows found in data")

    # Validate antennas
    if nant < 3:
        raise DataError(
            f"Too few antennas: {nant}. "
            f"Need at least 3 antennas for interferometry"
        )

    # Validate scans
    if nscans == 0:
        raise DataError("No scans found in data")

    # Check for calibration intents (warnings only, not errors)
    required_intents = ['CALIBRATE_BANDPASS', 'CALIBRATE_FLUX', 'CALIBRATE_PHASE']
    missing_intents = []
    for intent in required_intents:
        if intent not in intents:
            missing_intents.append(intent)

    if missing_intents:
        logger.warning(f"Missing calibration intents: {', '.join(missing_intents)}")
        logger.warning("Pipeline may fail if calibration scans are not present")

    # Return metadata
    metadata = {
        'validated': True,
        'path': str(sdm_path),
        'size_gb': total_size / 1e9,
        'nspw': nspw,
        'nant': nant,
        'nscans': nscans,
        'nfields': len(field_names),
        'field_names': field_names,
        'intents': intents,
        'missing_intents': missing_intents,
    }

    logger.info("Validation passed")
    return metadata


def validate_pipeline_context(context: Dict[str, Any]) -> None:
    """
    Validate pipeline context has required parameters.

    Parameters
    ----------
    context : dict
        Pipeline context dictionary

    Raises
    ------
    ConfigurationError
        If required parameters are missing
    """
    required_params = ['SDM_name', 'msname']

    missing = []
    for param in required_params:
        if param not in context or not context[param]:
            missing.append(param)

    if missing:
        raise ConfigurationError(
            f"Missing required pipeline parameters: {', '.join(missing)}"
        )

    # Validate refant if specified
    refant = context.get('refant')
    if refant:
        # Check refant format (should be like 'ea01', 'ea25')
        if not (refant.startswith('ea') and len(refant) >= 3):
            logger.warning(
                f"Reference antenna '{refant}' has unexpected format. "
                f"Expected format: 'ea01', 'ea25', etc."
            )


def check_disk_space(required_gb: float = 50.0) -> None:
    """
    Check available disk space.

    Parameters
    ----------
    required_gb : float
        Required disk space in GB

    Raises
    ------
    DataError
        If insufficient disk space
    """
    import shutil

    # Check current directory
    stat = shutil.disk_usage('.')
    available_gb = stat.free / 1e9

    logger.info(f"Available disk space: {available_gb:.1f} GB")

    if available_gb < required_gb:
        raise DataError(
            f"Insufficient disk space. "
            f"Available: {available_gb:.1f} GB, Required: {required_gb:.1f} GB. "
            f"Pipeline products can be large (logs, plots, caltables)"
        )


def validate_all(sdm_path: Path, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Run all validation checks.

    Parameters
    ----------
    sdm_path : Path
        Path to SDM/MS file
    context : dict, optional
        Pipeline context to validate

    Returns
    -------
    dict
        Validation metadata

    Raises
    ------
    DataError or ConfigurationError
        If any validation fails
    """
    logger.info("Running pre-flight validation checks")

    # Check disk space
    check_disk_space(required_gb=50.0)

    # Validate input data
    metadata = validate_input_data(sdm_path)

    # Validate context if provided
    if context:
        validate_pipeline_context(context)

    logger.info("All validation checks passed")
    return metadata
