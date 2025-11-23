# Changelog

All notable changes to the EVLA Scripted Pipeline are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2025-01-23

### Major Modernization Release

Complete architectural overhaul with modern Python best practices, enhanced polarization support, and improved reliability.

### Added

#### Modern Python Architecture
- **Registry pattern** for pipeline steps using `@register_step` decorator
- **Type hints** throughout codebase (`Dict[str, Any]` for pipeline contexts)
- **Structured exception hierarchy** with specific error types
- **Centralized configuration** via `PipelineConfig` dataclass
- **Standard Python logging** replacing custom logprint implementation
- **pip installable package** with CLI entry point (`evla-pipeline` command)

#### Enhanced CLI
- Comprehensive command-line interface with detailed help text
- User-friendly argument descriptions with examples
- Options for all pipeline features (hanning, polarization, plots, resume, skip)
- State management commands (--save, --restore)
- Debugging options (--verbose, --show-casa-output)

#### Documentation
- Professional README with table of contents and quick reference
- CONTRIBUTING.md with development guidelines and code standards
- INSTALL.md with platform-specific installation instructions
- Comprehensive docstrings in NumPy format
- Architecture documentation explaining registry pattern

#### Developer Tools
- isort configuration for import ordering (black profile, line length 100)
- black configuration for code formatting (Python 3.8-3.11 targets)
- mypy configuration for type checking (strict settings)
- Automation scripts for migration and type hint addition

### Changed

#### Architecture Improvements
- Replaced dynamic imports with registry-based step lookup
- Migrated all 24 pipeline steps to use `@register_step` decorator
- Centralized paths, thresholds, and defaults in `config.py`
- Standardized error handling with exception hierarchy
- Modernized logging with Python logging module

#### Weblog System
- Fixed navigation template rendering (circular dependency resolved)
- Fixed plots page to display actual PNG files from weblog directory
- Improved template engine with proper content passing
- Added responsive grid layout for plot display

#### Code Quality
- Added type hints to all pipeline step functions
- Improved docstrings with parameter descriptions and return types
- Formatted code with black (line length 100)
- Organized imports with isort (black profile)
- Removed legacy dynamic import code

### Fixed

- Weblog navigation broken links between pages
- Plots page showing placeholder text instead of actual plots
- Template rendering issues in `generate_full_page()`
- Function name mismatches in pipeline step registration
- Import ordering inconsistencies

### Removed

- Dynamic import fallback mechanism (legacy pattern)
- Undocumented implicit behaviors
- Redundant code patterns

---

## [1.5.0] - 2024-12-15

### Polarization Integration Release

Integration of full polarization calibration capabilities.

### Added

#### Polarization Features
- Automatic polarization model integration for all `setjy` operations
- Full polarization calibration with D-terms (Df) and cross-hand delays (Xf)
- 2019 VLA polarization calibrator measurements
- Dual-mode operation: intensity (default) and full polarization (optional)
- Automatic calibrator detection (3C48, 3C138, 3C147, 3C286)

#### Pipeline Steps
- `EVLA_pipe_polcal.py` - Full polarization calibration step
- Polarization utilities in `pol_setjy_utils.py`
- Polynomial fitting for polarization fraction and angle

#### Configuration
- `enable_polarization` flag for full polarization mode
- Fallback mechanisms for missing calibrators
- Date-based calibrator data selection

### Changed

- Enhanced `EVLA_pipe_calprep.py` with polarization model integration
- Updated `EVLA_pipe_applycals.py` to include Xf and Df tables
- Modified `setjy` calls to use polarization data when available

### Contributors

- Kelly Sanderson - Polarization calibration integration

---

## [1.0.0] - 2023-08-01

### Python 3 Port Release

Complete port from CASA 5 (Python 2) to CASA 6 (Python 3).

### Added

- CASA 6 compatibility (6.1.0 minimum requirement)
- Python 3.6+ support
- Modular CASA support (casatasks, casatools, casaplotms)
- State management and checkpointing
- Resume capability from any pipeline step
- Modern weblog generation

### Changed

- Ported all pipeline steps from Python 2 to Python 3
- Updated syntax for Python 3 (print statements, dict methods, etc.)
- Modernized CASA task calls for CASA 6 API
- Improved error handling and logging
- Enhanced directory organization

### Fixed

- Python 2 to 3 compatibility issues
- CASA 6 API changes
- Deprecated CASA task parameters

### Contributors

- Brian Svoboda - Python 3 port

---

## [0.9.0] - 2013-2022

### Original EVLA Pipeline

Legacy CASA 5-based pipeline (Python 2).

### Features

- Automated VLA continuum calibration
- Bandpass, delay, and gain calibration
- Flux density scale bootstrapping
- Automated flagging
- Diagnostic plotting
- Basic weblog generation

### Original Authors

- Claire Chandler (NRAO)
- Emmanuel Momjian (NRAO)
- Steve Myers (NRAO)

---

## Version History Summary

| Version | Release Date | Highlights |
|---------|--------------|------------|
| 2.0.0   | 2025-01-23   | Modern architecture, registry pattern, type hints |
| 1.5.0   | 2024-12-15   | Polarization calibration integration |
| 1.0.0   | 2023-08-01   | Python 3 port, CASA 6 support |
| 0.9.0   | 2013-2022    | Original CASA 5 pipeline |

---

## Upgrade Guide

### From 1.5.0 to 2.0.0

**Breaking Changes**:
- CLI now uses `evla-pipeline` command instead of `python -m evla_pipe.run_pipeline`
- Custom steps must use `@register_step` decorator
- Import paths changed for some modules

**Migration**:
```bash
# Old way
python -m evla_pipe.run_pipeline --enable-polarization data.asdm

# New way
evla-pipeline --polarization data.asdm
```

**Custom Steps**:
```python
# Old way (implicit registration)
def EVLA_pipe_mystep(pipeline_context):
    return pipeline_context

# New way (explicit registration)
from evla_pipe.pipeline_steps import register_step
from typing import Dict, Any

@register_step("EVLA_pipe_mystep")
def EVLA_pipe_mystep(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    return pipeline_context
```

**Benefits**:
- Faster execution with registry pattern
- Better error messages with structured exceptions
- Type checking support with mypy
- Professional CLI with detailed help
- Centralized configuration
- Standard Python logging

### From 1.0.0 to 1.5.0

**New Features**:
- Polarization calibration with `--enable-polarization` flag
- Automatic polarization model integration (no action required)

**Backward Compatibility**: Fully compatible. Intensity-only mode is default.

---

## Future Roadmap

### Planned for 2.1.0
- Integration with CASA 6.6
- Performance optimizations for large datasets
- Enhanced weblog with interactive plots
- Real-time QA monitoring

### Under Consideration
- GPU acceleration for imaging
- Cloud deployment support
- Containerization (Docker/Singularity)
- REST API for programmatic access
- Multi-dataset processing

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on:
- Development setup
- Coding standards
- Testing requirements
- Pull request process

---

## References

- CASA: https://casa.nrao.edu/
- VLA: https://science.nrao.edu/facilities/vla
- NRAO: https://www.nrao.edu/

---

## License

GNU General Public License v3.0 or later

Copyright (C) 2013-2025 Associated Universities, Inc.
