# EVLA Scripted Pipeline

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![CASA 6+](https://img.shields.io/badge/CASA-6.1+-green.svg)](https://casa.nrao.edu/)
[![Polarization Ready](https://img.shields.io/badge/polarization-integrated-purple.svg)](#polarization-calibration)

**A modern, robust, and fully integrated VLA data calibration pipeline with polarization support**

The EVLA Scripted Pipeline provides automated calibration for Very Large Array (VLA) continuum and polarization observations. Built on modern Python practices, it leverages advanced heuristics and automated procedures to calibrate interferometric data with comprehensive diagnostic plots and weblogs.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Architecture](#architecture)
- [Pipeline Steps](#pipeline-steps)
- [Polarization Calibration](#polarization-calibration)
- [Output Structure](#output-structure)
- [Error Recovery](#error-recovery)
- [Advanced Usage](#advanced-usage)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

### Modern Python Architecture
- **Registry-based pipeline steps**: Decorator pattern (`@register_step`) for clean, explicit registration
- **Type hints throughout**: Full type annotations for better IDE support and type checking
- **Structured exceptions**: Hierarchical exception system for precise error handling
- **Centralized configuration**: Single source of truth for paths, thresholds, and defaults
- **Standard logging**: Python logging module with file and console handlers
- **Pip installable**: Standard Python package with CLI entry point

### Integrated Polarization Calibration
- Automatic polarization model integration for all observations
- Full polarization calibration including D-terms (Df) and cross-hand delays (Xf)
- 2019 calibrator measurements with fallback to Perley-Butler 2013
- Dual-mode operation: intensity calibration (default) and full polarization (optional)

### Reliability & User Experience
- **State management**: Automatic checkpointing for resume capability
- **Clear error messages**: Actionable instructions with recovery options
- **Comprehensive CLI**: User-friendly command-line interface with detailed help
- **Organized outputs**: Structured directories for logs, plots, calibration tables, and weblogs
- **Flexible execution**: Skip steps, resume from any point, backup and restore state

---

## Requirements

- **CASA 6.1+** (monolithic or modular)
- **Python 3.8+**
- **Dependencies**: NumPy, SciPy, casatasks, casatools, casaplotms

The pipeline automatically detects and adapts to your CASA installation. Tested with CASA 6.1+ in both configurations.

---

## Installation

### Standard Installation

```bash
# Clone the repository
git clone <repository-url> evla-pipeline
cd evla-pipeline

# Install the package
pip install -e .

# Verify installation
evla-pipeline --version
casa --version  # or import casatasks in Python
```

### Development Installation

```bash
# Clone and install with test dependencies
git clone <repository-url> evla-pipeline
cd evla-pipeline
pip install -e .
pip install -r test/requirements.txt

# Run tests
python -m pytest test/
```

---

## Quick Start

### Basic Continuum Calibration

```bash
# Run pipeline with default settings
evla-pipeline your_data.asdm

# Enable verbose output
evla-pipeline --verbose your_data.asdm

# Disable plotting for faster execution
evla-pipeline --disable-plots your_data.asdm
```

### Polarization Calibration

```bash
# Enable full polarization calibration
evla-pipeline --polarization your_data.asdm

# Combine options
evla-pipeline --polarization --hanning --verbose your_data.asdm
```

### Get Help

```bash
# Show all options
evla-pipeline --help

# Show version
evla-pipeline --version
```

---

## Usage

### Command-Line Interface

The pipeline provides a comprehensive CLI with detailed help for all options:

```bash
evla-pipeline [OPTIONS] SDM_NAME

Positional Arguments:
  SDM_NAME              SDM directory or MS file (e.g., 'dataset.ms' or 'dataset.asdm')

Optional Arguments:
  --hanning             Apply Hanning smoothing (recommended for spectral line)
  --polarization        Enable full polarization calibration
  --disable-plots       Disable diagnostic plots for better performance
  --resume-from STEP    Resume from specific pipeline step
  --skip STEP           Skip one or more steps (can specify multiple times)
  --restore FILE        Restore pipeline state from backup
  --save FILE           Save pipeline state to backup
  --verbose, -v         Enable verbose console output
  --show-casa-output    Display CASA task output to console
  --version             Show version and exit
```

### Programmatic Usage

```python
from evla_pipe import continuum

# Basic continuum calibration
context = continuum('your_data.asdm')

# With polarization
context = continuum('your_data.asdm', enable_polarization=True)

# Full configuration
context = continuum(
    sdm_name='your_data.asdm',
    enable_polarization=True,
    skip_hanning=False,
    verbose=True,
    enable_plots=True,
    resume_from=None,
    skip_steps=[]
)

# Check results
print(f"Pipeline completed. MS: {context['msname']}")
if context.get('polarization_calibrated'):
    print("Full polarization calibration successful.")
```

### Modular Step Execution

```python
from evla_pipe import exec_script

# Initialize context
context = {
    'SDM_name': 'your_data.asdm',
    'do_hanning': True,
    'do_pol': True
}

# Execute individual steps
context = exec_script('EVLA_pipe_startup', context)
context = exec_script('EVLA_pipe_import', context)
context = exec_script('EVLA_pipe_hanning', context)
context = exec_script('EVLA_pipe_calprep', context)
context = exec_script('EVLA_pipe_finalcals', context)
context = exec_script('EVLA_pipe_polcal', context)
context = exec_script('EVLA_pipe_applycals', context)
```

---

## Architecture

### Registry Pattern

The pipeline uses a decorator-based registry system for clean, explicit step registration:

```python
from evla_pipe.pipeline_steps import register_step
from typing import Dict, Any

@register_step("EVLA_pipe_example")
def EVLA_pipe_example(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """Example pipeline step."""
    # Your calibration logic here
    return pipeline_context
```

This replaces dynamic imports with a pythonic, maintainable pattern used by frameworks like Flask, Click, and Pytest.

### Exception Hierarchy

Structured exceptions provide precise error handling:

```python
from evla_pipe.exceptions import (
    PipelineError,          # Base exception
    ConfigurationError,     # Invalid configuration
    DataError,              # Data validation failed
    CalibrationError,       # Calibration step failed
    FlaggingError,          # Flagging operation failed
    CASAError,              # CASA task failed
    WeblogError,            # Weblog generation failed (non-critical)
    PlotError,              # Plotting failed (non-critical)
    StateError,             # State management error
)
```

### Centralized Configuration

Single source of truth for all pipeline settings:

```python
from evla_pipe.config import PipelineConfig, get_config

# Get default configuration
config = get_config()

# Access paths
log_path = config.get_log_path('calibration')
plot_path = config.get_plot_path('bandpass.png')
caltable = config.get_caltable_path('delays.cal')

# Access thresholds
flag_threshold = config.flag_critfrac  # 0.6
min_snr = config.minsnr  # 3.0
```

### Standard Logging

Python logging module with structured output:

```python
from evla_pipe.logging_config import get_logger, setup_logging

# Setup logging
setup_logging(log_level="INFO", log_to_console=True, log_to_file=True)

# Get module-specific logger
logger = get_logger(__name__)
logger.info("Starting calibration")
logger.warning("Low SNR detected")
logger.error("Calibration failed", exc_info=True)
```

---

## Pipeline Steps

### Standard Workflow

The pipeline executes 22 calibration steps in sequence:

1. **EVLA_pipe_startup** - Initialize pipeline context and validate inputs
2. **EVLA_pipe_import** - Import SDM/ASDM data to measurement set
3. **EVLA_pipe_hanning** - Apply Hanning smoothing (optional)
4. **EVLA_pipe_msmd** - Extract measurement set metadata
5. **EVLA_pipe_flagall** - Initial automated flagging
6. **EVLA_pipe_calprep** - Prepare calibration setup
7. **EVLA_pipe_priorcals** - Apply antenna position and opacity corrections
8. **EVLA_pipe_testBPdcals** - Test bandpass and delay calibration
9. **EVLA_pipe_checkflag** - QA flagging after test calibration
10. **EVLA_pipe_semiFinalBPdcals1** - Semi-final bandpass calibration
11. **EVLA_pipe_checkflag_semiFinal** - QA flagging after semi-final BP
12. **EVLA_pipe_solint** - Determine optimal solution intervals
13. **EVLA_pipe_testgains** - Test gain calibration
14. **EVLA_pipe_fluxgains** - Flux density scale calibration
15. **EVLA_pipe_fluxboot** - Bootstrap flux scale to secondary calibrators
16. **EVLA_pipe_finalcals** - Final calibration table generation
17. **EVLA_pipe_polcal** - Polarization calibration (if enabled)
18. **EVLA_pipe_applycals** - Apply all calibration tables
19. **EVLA_pipe_targetflag** - Flag target source data
20. **EVLA_pipe_statwt** - Statistical weight calculation
21. **EVLA_pipe_plotsummary** - Generate diagnostic plots
22. **EVLA_pipe_weblog** - Create comprehensive weblog

### Skip or Resume Steps

```bash
# Skip specific steps
evla-pipeline --skip EVLA_pipe_hanning --skip EVLA_pipe_plotsummary your_data.asdm

# Resume from a specific step
evla-pipeline --resume-from EVLA_pipe_finalcals your_data.asdm
```

---

## Polarization Calibration

### Two Modes of Operation

#### Mode 1: Intensity Calibration (Default)
- Automatic polarization model integration during all `setjy` operations
- Uses modern calibrator data (2019) with fallback to Perley-Butler 2013
- Improves intensity calibration accuracy for all observations
- No user action required

#### Mode 2: Full Polarization Calibration (Optional)
- Enable with `--polarization` flag
- Performs complete polarization calibration for Stokes Q, U, V analysis
- Requires polarization calibrators in the observation
- Generates D-term (Df) and cross-hand delay (Xf) calibration tables
- Outputs fully calibrated data suitable for polarization science

### Calibration Flow

```
1. Cross-hand delays (KCross)
2. D-term leakage (Df)
3. Polarization angle (Xf)
4. Apply all tables together in applycal
```

### Automatic Calibrator Detection

The pipeline automatically:
- Detects standard polarization calibrators (3C48, 3C138, 3C147, 3C286)
- Selects appropriate calibrator data based on observation date
- Handles missing calibrators with graceful fallbacks
- Uses 2019 measurements when available, falls back to Perley-Butler 2013

### Example

```bash
# Full polarization calibration
evla-pipeline --polarization your_data.asdm

# Check results in logs
tail -f logs/polcal.log

# Verify output tables
ls -lh final_caltables/*.Xf
ls -lh final_caltables/*.Df
```

---

## Output Structure

The pipeline creates an organized directory structure:

```
your_working_directory/
├── logs/                          # Detailed execution logs per step
│   ├── startup.log
│   ├── import.log
│   ├── calprep.log
│   ├── finalcals.log
│   └── polcal.log
├── weblog/                        # Interactive HTML weblog
│   ├── index.html
│   ├── calibration.html
│   ├── flagging.html
│   ├── plots.html
│   └── qa.html
├── plots/                         # Diagnostic plots (PNG)
│   ├── bandpass_*.png
│   ├── delays_*.png
│   ├── gains_*.png
│   └── flux_*.png
├── final_caltables/               # Final calibration tables
│   ├── delays.cal
│   ├── bandpass.cal
│   ├── gains.cal
│   ├── flux.cal
│   ├── *.Xf                       # Polarization angle (if enabled)
│   └── *.Df                       # D-terms (if enabled)
├── intermediate_caltables/        # Intermediate calibration products
├── test_caltables/                # Test calibration tables
├── pipeline_context/              # State checkpoints (JSON)
│   ├── pipeline_context_EVLA_pipe_startup.json
│   ├── pipeline_context_EVLA_pipe_import.json
│   └── ...
├── pipeline_backups/              # Manual backups (optional)
├── measurement_sets/              # Processed measurement sets
└── your_data.ms                   # Calibrated measurement set
```

---

## Error Recovery

### Automatic State Saving

The pipeline automatically saves state after each step to `pipeline_context/`. If a step fails:

```bash
# Pipeline will display:
🚨 Pipeline step 'EVLA_pipe_finalcals' failed: <error message>
📋 Pipeline state saved to: pipeline_context/pipeline_context_EVLA_pipe_finalcals.json
⚠️  To resume: evla-pipeline --resume-from EVLA_pipe_finalcals <data.asdm>
💡 To skip: evla-pipeline --skip EVLA_pipe_finalcals <data.asdm>
```

### Resume from Failure

```bash
# After fixing the issue, resume from failed step
evla-pipeline --resume-from EVLA_pipe_finalcals your_data.asdm

# Or skip the problematic step
evla-pipeline --skip EVLA_pipe_finalcals your_data.asdm
```

### Manual State Management

```bash
# Save state manually
evla-pipeline --save pipeline_backups/checkpoint_$(date +%Y%m%d).restore your_data.asdm

# Restore from backup
evla-pipeline --restore pipeline_backups/checkpoint_20250123.restore
```

---

## Advanced Usage

### Custom Configuration

```python
from evla_pipe.config import PipelineConfig
from pathlib import Path

# Create custom configuration
config = PipelineConfig(
    log_dir=Path("custom_logs"),
    weblog_dir=Path("custom_weblog"),
    plots_dir=Path("custom_plots"),
    flag_critfrac=0.7,  # More conservative flagging
    minsnr=4.0,  # Higher SNR requirement
    log_level="DEBUG"  # More verbose logging
)

# Use in pipeline
from evla_pipe import continuum
context = continuum('your_data.asdm', verbose=True)
```

### Integrate Polarization in Custom Workflows

```python
from evla_pipe.pol_setjy_utils import integrate_polarization_setjy

# Apply polarization model to specific field
integrate_polarization_setjy(
    vis='your_data.ms',
    field_id=0,
    field_name='3C286',
    spws=[0, 1, 2, 3],
    band='C',
    ref_freq_hz=6e9
)
```

### Debugging with CASA Output

```bash
# Show CASA task output for debugging
evla-pipeline --show-casa-output --verbose your_data.asdm

# Monitor logs in real-time
tail -f logs/finalcals.log
```

---

## Development

### Project Structure

```
evla_pipeline/
├── evla_pipe/                     # Main package
│   ├── __init__.py                # Package initialization and exec_script
│   ├── config.py                  # Centralized configuration
│   ├── exceptions.py              # Exception hierarchy
│   ├── logging_config.py          # Logging setup
│   ├── pipeline_steps.py          # Registry system
│   ├── pipeline.py                # Main continuum() function
│   ├── state_manager.py           # State management
│   ├── run_pipeline.py            # CLI entry point
│   ├── weblog_templates.py        # Weblog template engine
│   ├── modern_weblog.py           # Weblog generator
│   ├── EVLA_pipe_*.py             # Individual pipeline steps
│   └── utils.py                   # Utility functions
├── test/                          # Test suite
│   ├── test_weblog_generation.py
│   ├── test_polarization.py
│   └── requirements.txt
├── scripts/                       # Development scripts
│   ├── migrate_to_registry.py
│   ├── add_wrappers.py
│   └── add_type_hints.py
├── pyproject.toml                 # Package configuration
├── README.md                      # This file
└── LICENSE                        # GPL-3.0
```

### Code Style

The project follows modern Python best practices:

- **Type hints**: All functions use type annotations
- **Docstrings**: Comprehensive documentation for all public APIs
- **Formatting**: Black (line length 100)
- **Import ordering**: isort with black profile
- **Type checking**: mypy with strict settings

### Run Type Checking

```bash
# Install mypy
pip install mypy

# Run type checker
mypy evla_pipe/
```

### Run Code Formatting

```bash
# Install formatters
pip install black isort

# Format code
black evla_pipe/
isort evla_pipe/
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the code style
4. Add type hints and docstrings
5. Run tests (`python -m pytest test/`)
6. Run type checking (`mypy evla_pipe/`)
7. Format code (`black evla_pipe/ && isort evla_pipe/`)
8. Commit your changes (`git commit -m 'Add amazing feature'`)
9. Push to the branch (`git push origin feature/amazing-feature`)
10. Open a Pull Request

---

## Troubleshooting

### Common Issues

#### CASA Version Not Supported

```
Error: This scripted pipeline requires CASA v6.1.0 or later.
```

**Solution**: Update CASA to version 6.1 or later.

```bash
casa --version
# Ensure output shows CASA Version 6.1.0 or higher
```

#### No Polarization Calibrators Found

```
Warning: No standard polarization calibrators detected in observation
```

**Solution**: Pipeline automatically falls back to intensity-only calibration. To enable full polarization calibration, ensure your observation includes standard calibrators (3C48, 3C138, 3C147, 3C286) and use `--polarization` flag.

#### Pipeline Step Failed

```
🚨 Pipeline step 'EVLA_pipe_finalcals' failed: <error>
```

**Solution**: Check logs for details, then either:
1. Resume from the failed step: `evla-pipeline --resume-from EVLA_pipe_finalcals your_data.asdm`
2. Skip the step: `evla-pipeline --skip EVLA_pipe_finalcals your_data.asdm`
3. Review logs: `tail -f logs/finalcals.log`

#### Import Errors

```
ModuleNotFoundError: No module named 'casatasks'
```

**Solution**: Ensure CASA is properly installed and accessible:

```bash
# Verify CASA installation
python -c "import casatasks; print(casatasks.__version__)"

# If using modular CASA
pip install casatasks casatools casaplotms
```

### Debugging Tips

```bash
# Enable verbose output
evla-pipeline --verbose your_data.asdm

# Show CASA output for debugging CASA tasks
evla-pipeline --show-casa-output --verbose your_data.asdm

# Monitor specific log file
tail -f logs/calprep.log

# Check pipeline context for state
cat pipeline_context/pipeline_context_EVLA_pipe_finalcals.json | python -m json.tool

# Enable DEBUG level logging
python -c "
from evla_pipe.logging_config import setup_logging
from evla_pipe import continuum
setup_logging(log_level='DEBUG')
continuum('your_data.asdm', verbose=True)
"
```

### Getting Help

1. Check logs in `logs/` directory
2. Review weblog at `weblog/index.html`
3. Enable verbose and CASA output for debugging
4. Consult CASA documentation: https://casa.nrao.edu/
5. Report issues: <repository-issues-url>

---

## License & Credits

**License**: GNU General Public License (GPL) v3 or later
**Copyright**: 2013-2025 Associated Universities, Inc.

### Original Authors

- Claire Chandler (NRAO)
- Emmanuel Momjian (NRAO)
- Steve Myers (NRAO)

### Modernization Contributors

- Python 3 port: Brian Svoboda (2023)
- Polarization integration: Kelly Sanderson (2024)
- Modernization and refactoring: Preshanth Jagannathan (2024-2025)

### Scientific References

- Perley & Butler 2013: "An Accurate Flux Density Scale from 1 to 50 GHz"
- Perley & Butler 2017: "An Accurate Flux Density Scale from 50 MHz to 50 GHz"

---

## Quick Reference

```bash
# Installation
pip install -e .

# Basic usage
evla-pipeline your_data.asdm

# Polarization
evla-pipeline --polarization your_data.asdm

# Help
evla-pipeline --help

# Resume
evla-pipeline --resume-from EVLA_pipe_finalcals your_data.asdm

# Skip steps
evla-pipeline --skip EVLA_pipe_hanning your_data.asdm

# Debugging
evla-pipeline --verbose --show-casa-output your_data.asdm
```

For detailed documentation, examples, and troubleshooting, see the sections above.
