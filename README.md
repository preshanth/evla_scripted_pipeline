# EVLA Scripted Pipeline

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![CASA 6+](https://img.shields.io/badge/CASA-6.0+-green.svg)](https://casa.nrao.edu/)
[![Polarization Ready](https://img.shields.io/badge/polarization-integrated-purple.svg)](#polarization-calibration)

**A modern, robust, and fully integrated VLA data calibration pipeline with polarization support**

The EVLA Scripted Pipeline provides automated calibration for Very Large Array (VLA) continuum and polarization observations. It leverages advanced heuristics and automated procedures to calibrate interferometric data, producing comprehensive diagnostic plots and weblogs.

---

## Overview of Modernization

This release is a complete overhaul of the original pipeline, featuring:

### Integrated Polarization Calibration
- Automatic polarization model integration for all observations
- Full polarization calibration, including D-terms (Df) and cross-hand delays (Xf)
- Utilizes 2019 calibrator measurements with fallback to Perley-Butler 2013
- Dual-mode operation: enhanced intensity calibration and optional full polarization

### Modern Architecture
- Modular, function-based Python package
- Command-line interface with intuitive options
- Significant codebase reduction and improved maintainability

### Enhanced User Experience
- Simple command-line usage: `python -m evla_pipe.run_pipeline your_data.asdm`
- Automatic error recovery and resume functionality
- Organized output directories for logs, calibration tables, and results
- Comprehensive logging and robust handling of CASA data types

### Reliability & Recovery
- Automatic state saving for resume capability
- Clear error messages with actionable instructions
- Flexible step skipping and resume options
- Intelligent calibration table resolution and graceful fallbacks

---

## Requirements & Installation

Minimum: Python 3.8+ (3.12 tested). This project separates CASA
dependencies from the core package so you can develop and run
lightweight tests without CASA installed.

Recommended quick install (no CASA):

```bash
git clone <repository-url> evla-pipeline
cd evla-pipeline
# Create a virtualenv and install (protobuf pinned via constraints.txt)
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -c constraints.txt -e .
```

If you need CASA (`casatools`, `casatasks`, `casaplotms`) install them via
your CASA distribution or use the optional extra (may require available
wheels for your Python version):

```bash
# install CASA extras from PyPI where available
pip install -c constraints.txt -e .[casa]
```

Developer bootstrap (installs lint/test tooling):

```bash
./scripts/setup_dev_env.sh .venv
source .venv/bin/activate
```

### Error Recovery & Resume
If the pipeline encounters an error, it saves the state and provides resume instructions:
```bash
python -m evla_pipe.run_pipeline --resume-from EVLA_pipe_testBPdcals your_data.asdm
python -m evla_pipe.run_pipeline --skip EVLA_pipe_fluxboot your_data.asdm
python -m evla_pipe.run_pipeline --skip EVLA_pipe_fluxboot --skip EVLA_pipe_plotsummary your_data.asdm
python -m evla_pipe.run_pipeline --resume-from EVLA_pipe_finalcals --enable-polarization your_data.asdm
```

### Directory Structure
```
your_working_directory/
├── logs/
├── pipeline_context/
├── final_caltables/
├── intermediate_caltables/
├── test_caltables/
├── plots/
├── weblog/
├── calibrators.ms
└── measurement_sets/
```

### Testing

There are two test tiers:
- Lightweight unit tests (no CASA) — fast, run in CI.
- Full integration tests — require CASA and the large test dataset; run locally when needed.

Run lightweight tests:

```bash
pip install pytest
pytest -q test/test_simple_utils.py
```

Full integration tests and the historical `test/run_tests.py` require CASA and
the test SDM/MS dataset; see `test/README.md` for details.
```

### Output Files
```
your_data.ms/
your_data.ms.*.cal
your_data.ms.Xf
your_data.ms.Df
logs/
plots/
weblog/
```

---

## Testing & Validation

### Quick Validation
```python
from evla_pipe.pol_setjy_utils import get_polcal_data, fit_polarization_polynomials

cal_data = get_polcal_data('3C286')
print(f"Loaded 3C286: {len(cal_data.frequencies)} frequency points")

pol_frac_coeffs, pol_angle_coeffs, pol_frac_ref = fit_polarization_polynomials(
    '3C286', 'C', 6.0
)
print(f"Polarization fraction at 6 GHz: {pol_frac_ref:.4f}")

context = continuum('test_data.asdm', enable_polarization=True, verbose=True)
if context.get('polarization_calibrated'):
    print("Full polarization calibration successful.")
```

### Validation Checklist

**Basic:**
- [ ] Pipeline completes without errors
- [ ] Measurement set and calibration tables generated
- [ ] Weblog with diagnostic plots created

**Polarization (Mode 1):**
- [ ] Log shows polarization model integration
- [ ] Standard calibrators detected
- [ ] Fallback to intensity-only if needed

**Full Polarization (Mode 2):**
- [ ] Xf and Df tables created
- [ ] Polarization tables included in applycal
- [ ] Log shows polarization calibration steps

---

## Troubleshooting

### Common Issues

**No polarization calibrators found**
- Cause: No standard polarization calibrators in observation
- Solution: Pipeline falls back to intensity-only mode
- Action: Ensure field names match standard calibrators

**CASA version not supported**
- Cause: CASA version < 6.1.0
- Solution: Update CASA
- Action: Run `casa --version` or import casatasks

**Pipeline interrupted or failed**
- Cause: Various
- Solution: Check logs, use resume functionality
- Action: Review logs, use `--verbose`, or run steps individually

**Polarization calibration failed**
- Cause: Insufficient calibrator data or S/N
- Solution: Pipeline continues with intensity calibration
- Action: No user action needed except to note the reason for skipping polcal.

### Debugging
```bash
python -m evla_pipe.run_pipeline --enable-polarization --verbose your_data.asdm
tail -f logs/calprep.log
tail -f logs/polcal.log
tail -f logs/applycals.log
```

### Manual Step Execution
```python
from evla_pipe import exec_script

context = {'SDM_name': 'problematic_data.asdm', 'do_pol': True}
try:
    context = exec_script('EVLA_pipe_startup', context)
    context = exec_script('EVLA_pipe_import', context)
    # Continue as needed
except Exception as e:
    print(f"Failed at step: {e}")
```

---

## Advanced Configuration

### Pipeline State Management
```bash
python -m evla_pipe.run_pipeline --save backup.restore your_data.asdm
python -m evla_pipe.run_pipeline --restore backup.restore
```

### Custom Polarization Data
```python
from evla_pipe import continuum

context = continuum(
    'your_data.asdm', 
    enable_polarization=True,
)

from evla_pipe.pol_setjy_utils import get_polcal_data

cal_data = get_polcal_data('3C286', obs_date='2015-01-01')
cal_data = get_polcal_data('3C286', obs_date='2020-01-01')
```

### Workflow Integration
```python
from evla_pipe.pol_setjy_utils import integrate_polarization_setjy
from evla_pipe.utils import find_EVLA_band

integrate_polarization_setjy(
    vis='your_data.ms',
    field_id=0,
    field_name='3C286',
    spws=[0, 1, 2, 3],
    band='C',
    ref_freq_hz=6e9
)
```

---

## Documentation

### References
- **`test/TESTING_STRATEGY.md`**: Testing framework
- **`examples/polarization_usage.py`**: Usage examples
- **`logs/`**: Runtime logs

### Scientific References
- Perley & Butler 2013: "An Accurate Flux Density Scale from 1 to 50 GHz"

### Development

Use `./scripts/setup_dev_env.sh` to create a development venv and install lint/test
tools. Run the lightweight unit tests during development; only run full
integration tests when CASA and the dataset are available.

Contributions: follow PEP 8, keep tests meaningful and fast, and add integration
tests only where necessary.

---

## License & Credits

**License**: GNU General Public License (GPL) v3  
**Copyright**: 2013-2025 Associated Universities Inc.

**Original Authors:**  
- Claire Chandler (NRAO)
- Emmanuel Momjian (NRAO)
- Steve Myers (NRAO)

**Modernization & Polarization Integration:**  
- Python 3 port: Brian Svoboda (2023)
- Polarization integration : Kelly Sanderson(2024)
- Modernization: Preshanth Jagannathan (2024-2025)

---

## Getting Started

```bash
python -m evla_pipe.run_pipeline your_continuum_data.asdm
python -m evla_pipe.run_pipeline --enable-polarization your_polarization_data.asdm
python -m evla_pipe.run_pipeline --help
```
