# EVLA Scripted Pipeline

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![CASA 6+](https://img.shields.io/badge/CASA-6.0+-green.svg)](https://casa.nrao.edu/)
[![Polarization Ready](https://img.shields.io/badge/polarization-integrated-purple.svg)](#polarization-calibration)

**A completely modernized and enhanced VLA data calibration pipeline with integrated polarization support**

Automated calibration pipeline for Very Large Array (VLA) continuum and polarization observations. This pipeline applies sophisticated heuristics and automated procedures to calibrate interferometric data while generating comprehensive diagnostic plots and web logs.

---

## 🚀 **What's New - Complete Modernization**

This version represents a **complete transformation** from the original pipeline:

### ⭐ **Integrated Polarization Calibration** 
- **Automatic polarization model integration** for all observations
- **Full polarization calibration** with D-terms (Df) and cross-hand delays (Xf)  
- **Modern 2019 measurements** with intelligent fallback to Perley-Butler 2013
- **Dual-mode operation**: Enhanced intensity calibration + optional full polarization

### 🏗 **Modern Architecture**
- **Function-based modules** replacing global-scope scripts
- **Complete CLI interface** with intuitive command-line options
- **Modular Python package** with proper imports and structure
- **65% code reduction** through modernization (e.g., msinfo: 1349→479 lines)

### 🛠 **Enhanced User Experience**
- **Simple command-line usage**: `python -m evla_pipe.run_pipeline your_data.asdm`
- **Automatic error recovery**: Resume from any step after fixing issues
- **Smart directory organization**: Clean separation of logs, calibration tables, and outputs
- **Comprehensive logging**: Detailed progress tracking and debugging information
- **Production-ready reliability**: Robust handling of CASA data types and edge cases

### 🔧 **Reliability & Recovery Features**
- **Automatic state saving**: Pipeline context saved before each step for resume capability
- **Intelligent error handling**: Clear error messages with specific fix instructions
- **Resume functionality**: `--resume-from STEP_NAME` to continue after failures
- **Step skipping**: `--skip STEP_NAME` for non-critical steps
- **Smart table resolution**: Finds calibration tables in multiple possible locations
- **Graceful fallbacks**: Pipeline continues with available data when possible

---

## 📋 **Requirements**

- **CASA 6.1+** (monolithic or modular installation)
- **Python 3.8+**
- **NumPy, SciPy** (automatically installed)

**CASA Compatibility**: Tested with CASA 6.1+ in both monolithic and modular modes. The pipeline automatically detects your CASA installation and adapts accordingly.

---

## 🚀 **Quick Start**

### 1. **Installation**
```bash
# Clone the repository  
git clone <repository-url> evla-pipeline
cd evla-pipeline

# Install Python dependencies
pip install -r requirements.txt

# Verify CASA is available
casa --version  # or import casatasks in Python
```

### 2. **Basic Usage - Command Line**
```bash
# Standard intensity calibration
python -m evla_pipe.run_pipeline your_data.asdm

# Full polarization calibration  
python -m evla_pipe.run_pipeline --enable-polarization your_data.asdm

# Skip Hanning smoothing (for spectral line data)
python -m evla_pipe.run_pipeline --skip-hanning your_data.asdm

# Verbose output for debugging
python -m evla_pipe.run_pipeline --enable-polarization --verbose your_data.asdm
```

### 2.1 **Error Recovery & Resume Functionality**
The pipeline now includes robust error handling with automatic state saving and resume capabilities:

```bash
# If pipeline fails, it will show resume instructions like:
# 🚨 Pipeline step 'EVLA_pipe_testBPdcals' failed with error: ...
# 📋 Pipeline state saved to: pipeline_context/pipeline_context_EVLA_pipe_testBPdcals.json
# ⚠️  To resume from this point, fix the issue and run:
#    python -m evla_pipe.run_pipeline --resume-from EVLA_pipe_testBPdcals <your_data.asdm>

# Resume from a specific step after fixing issues
python -m evla_pipe.run_pipeline --resume-from EVLA_pipe_testBPdcals your_data.asdm

# Skip problematic non-critical steps
python -m evla_pipe.run_pipeline --skip EVLA_pipe_fluxboot your_data.asdm

# Skip multiple steps
python -m evla_pipe.run_pipeline --skip EVLA_pipe_fluxboot --skip EVLA_pipe_plotsummary your_data.asdm

# Resume with additional options
python -m evla_pipe.run_pipeline --resume-from EVLA_pipe_finalcals --enable-polarization your_data.asdm
```

### 2.2 **Directory Organization**
The pipeline automatically creates an organized directory structure:
```
your_working_directory/
├── logs/                    # Detailed log files for each step
├── pipeline_context/        # JSON state files for resume capability
├── final_caltables/         # Final calibration tables  
├── intermediate_caltables/  # Prior & intermediate calibrations
├── test_caltables/          # Test calibrations
├── plots/                   # Diagnostic plots
├── weblog/                  # Web-based summary report
├── calibrators.ms           # Split calibrator data for efficiency
└── measurement_sets/        # Processed measurement sets
```

### 3. **Programmatic Usage**
```python
import sys
sys.path.append('/path/to/evla-pipeline')

from evla_pipe import continuum

# Basic intensity calibration
context = continuum('your_data.asdm')

# Full polarization calibration
context = continuum('your_data.asdm', enable_polarization=True, verbose=True)

# Advanced options
context = continuum(
    sdm_name='your_data.asdm',
    enable_polarization=True,
    skip_hanning=False,
    verbose=True
)

print(f"Pipeline completed. MS: {context['msname']}")
if context.get('polarization_calibrated'):
    print("✅ Full polarization calibration successful!")
```

### 4. **Modular Usage**
```python
from evla_pipe import exec_script

# Run individual pipeline steps
context = {'SDM_name': 'your_data.asdm', 'do_pol': True}

context = exec_script('EVLA_pipe_startup', context)
context = exec_script('EVLA_pipe_import', context)  
context = exec_script('EVLA_pipe_calprep', context)    # Includes polarization models
context = exec_script('EVLA_pipe_finalcals', context)
context = exec_script('EVLA_pipe_polcal', context)     # Df/Xf calibration (if do_pol=True)
context = exec_script('EVLA_pipe_applycals', context)  # Applies all calibrations
context = exec_script('EVLA_pipe_weblog', context)     # Generate final weblog
```

---

## 🔬 **Polarization Calibration - Dual Mode System**

The pipeline operates in **two complementary polarization modes**:

### **Mode 1: Enhanced Intensity Calibration** (Always Active)
**Automatic polarization model integration during standard setjy calls**

- **When**: Automatically runs during all `setjy` operations
- **Purpose**: Sets accurate Stokes I, Q, U, V models for calibrators  
- **Impact**: Improves intensity calibration accuracy for all observations
- **Sources**: 3C48, 3C138, 3C147, 3C286, 3C196, 3C295
- **Data**: Modern 2019 measurements with Perley-Butler 2013 fallback
- **User Action**: None required - completely automatic

```bash
# This mode is ALWAYS active - no flags needed
python -m evla_pipe.run_pipeline your_data.asdm
```

### **Mode 2: Full Polarization Calibration** (Optional)
**Complete polarization calibration with instrumental corrections**

- **When**: Enabled with `--enable-polarization` flag
- **Purpose**: Full polarization calibration for Stokes Q, U, V analysis
- **Requirements**: Polarization calibrators in the observation
- **Output**: Fully calibrated data ready for polarization science

**Calibration Steps**:
1. **Cross-hand delay calibration (Xf)**: Corrects R-L instrumental delays
2. **D-term leakage calibration (Df)**: Corrects instrumental polarization leakage  
3. **Integrated application**: All calibrations applied together in `applycal`

```bash
# Enable full polarization calibration
python -m evla_pipe.run_pipeline --enable-polarization your_data.asdm
```

### **Automatic Calibrator Detection**
Both modes automatically:
- ✅ **Detect standard calibrators** in your observation
- ✅ **Select appropriate data** (2019 vs 2013) based on observation date
- ✅ **Handle missing calibrators** gracefully with fallbacks
- ✅ **Optimize for VLA band** (L, S, C, X, Ku, K, Ka, Q)

---

## 📁 **Pipeline Steps & Output**

### **Standard Pipeline Flow**
```
1. EVLA_pipe_startup       → Initialize pipeline, gather user inputs
2. EVLA_pipe_import        → Import ASDM to measurement set
3. EVLA_pipe_hanning       → Hanning smoothing (optional, skip with --skip-hanning)  
4. EVLA_pipe_msinfo        → Extract observation metadata
5. EVLA_pipe_flagall       → Apply deterministic flagging
6. EVLA_pipe_calprep       → Set calibrator models (+ Mode 1 polarization)
7. EVLA_pipe_priorcals     → Apply antenna position and requantizer corrections
8. EVLA_pipe_testBPdcals   → Initial bandpass and delay calibration
9. EVLA_pipe_checkflag     → Flag RFI on bandpass calibrator
10. EVLA_pipe_semiFinalBPdcals1 → Semi-final bandpass/delay calibration  
11. EVLA_pipe_checkflag_semiFinal → Additional calibrator flagging
12. EVLA_pipe_solint       → Determine optimal solution intervals
13. EVLA_pipe_testgains    → Test gain calibrations
14. EVLA_pipe_fluxgains    → Flux bootstrapping gains (+ Mode 1 polarization)
15. EVLA_pipe_fluxboot     → Flux density bootstrapping
16. EVLA_pipe_finalcals    → Create final calibration tables
17. EVLA_pipe_polcal       → Polarization calibration (Mode 2 only)
18. EVLA_pipe_applycals    → Apply all calibrations
19. EVLA_pipe_targetflag   → Flag calibrated target data  
20. EVLA_pipe_statwt       → Calculate statistical weights
21. EVLA_pipe_plotsummary  → Generate diagnostic plots
22. EVLA_pipe_weblog       → Create HTML summary
```

### **Output Files**
```
your_data.ms/              # Calibrated measurement set
your_data.ms.*.cal         # Calibration tables  
your_data.ms.Xf            # Cross-hand delay table (Mode 2)
your_data.ms.Df            # D-term leakage table (Mode 2)
logs/                      # Detailed log files
plots/                     # Diagnostic plots
weblog/                    # HTML summary report
```

---

## 🧪 **Testing & Validation**

### **Quick Validation Test**
```python
# Test polarization data loading
from evla_pipe.pol_setjy_utils import get_polcal_data, fit_polarization_polynomials

# Verify data files are accessible
cal_data = get_polcal_data('3C286')
print(f"✅ Loaded 3C286: {len(cal_data.frequencies)} frequency points")

# Test polynomial fitting
pol_frac_coeffs, pol_angle_coeffs, pol_frac_ref = fit_polarization_polynomials(
    '3C286', 'C', 6.0  # C-band at 6 GHz
)
print(f"✅ Polarization fraction at 6 GHz: {pol_frac_ref:.4f}")

# Test pipeline execution
context = continuum('test_data.asdm', enable_polarization=True, verbose=True)
if context.get('polarization_calibrated'):
    print("✅ Full polarization calibration successful")
```

### **Validation Checklist**
When testing with real VLA data:

**Basic Validation**:
- [ ] Pipeline completes without critical errors
- [ ] Measurement set created successfully  
- [ ] Calibration tables generated
- [ ] Weblog created with diagnostic plots

**Polarization Validation** (Mode 1 - Always):
- [ ] Log shows "Setting combined intensity + polarization model" messages
- [ ] Standard calibrators detected automatically
- [ ] Fallback to intensity-only works if polarization data unavailable

**Full Polarization Validation** (Mode 2 - `--enable-polarization`):
- [ ] Cross-hand delay calibration (Xf) table created
- [ ] D-term leakage calibration (Df) table created  
- [ ] Polarization tables included in final applycal
- [ ] Log shows "Running polarization calibration (Df, Xf)" message

---

## 🚨 **Troubleshooting**

### **Common Issues & Solutions**

**❌ "No polarization calibrators found"**
```
Cause: Observation doesn't contain standard polarization calibrators
Solution: Pipeline automatically falls back to intensity-only mode
Action: Check field names match: 3C48, 3C138, 3C147, 3C286, 3C196, 3C295
```

**❌ "CASA version not supported"**  
```
Cause: CASA version older than 6.1.0
Solution: Update CASA or check CASA environment
Action: Run 'casa --version' or import casatasks in Python
```

**❌ "Pipeline interrupted or failed"**
```
Cause: Various - check logs for specific error
Solution: Pipeline supports restart from most steps
Action: 
1. Check logs/ directory for detailed error messages
2. Use --verbose flag for more debugging information  
3. Try running individual steps with exec_script()
```

**❌ "Polarization calibration failed"**
```
Cause: Insufficient polarization calibrator data or S/N
Solution: Pipeline automatically continues with intensity calibration
Action: Check observation has adequate polarization calibrator coverage
```

### **Debug Mode**
```bash
# Run with maximum verbosity
python -m evla_pipe.run_pipeline --enable-polarization --verbose your_data.asdm

# Check specific logs
tail -f logs/calprep.log      # Calibration preparation
tail -f logs/polcal.log       # Polarization calibration  
tail -f logs/applycals.log    # Calibration application
```

### **Manual Intervention**
```python
# Run pipeline step-by-step for debugging
from evla_pipe import exec_script

context = {'SDM_name': 'problematic_data.asdm', 'do_pol': True}

# Run each step individually
try:
    context = exec_script('EVLA_pipe_startup', context)
    context = exec_script('EVLA_pipe_import', context)
    # ... continue step by step
except Exception as e:
    print(f"Failed at step: {e}")
    # Investigate specific step
```

---

## 🔧 **Advanced Configuration**

### **Pipeline State Management**
```bash
# Save pipeline state for later restart
python -m evla_pipe.run_pipeline --save backup.restore your_data.asdm

# Restore from saved state  
python -m evla_pipe.run_pipeline --restore backup.restore
```

### **Custom Polarization Data**
```python
# Use custom observation date for data selection
from evla_pipe import continuum

context = continuum(
    'your_data.asdm', 
    enable_polarization=True,
    # Pipeline will automatically select best data source based on obs date
)

# For advanced users: manual data source selection
from evla_pipe.pol_setjy_utils import get_polcal_data

# Force specific data source
cal_data = get_polcal_data('3C286', obs_date='2015-01-01')  # Will use 2013 data
cal_data = get_polcal_data('3C286', obs_date='2020-01-01')  # Will use 2019 data
```

### **Integration with Existing Workflows**
```python
# Use pipeline components in existing scripts
from evla_pipe.pol_setjy_utils import integrate_polarization_setjy
from evla_pipe.utils import find_EVLA_band

# Manual polarization model setting
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

## 📚 **Further Documentation**

### **Detailed References**
- **`COMPREHENSIVE_CONTEXT.md`**: Complete modernization documentation
- **`test/TESTING_STRATEGY.md`**: Comprehensive testing framework
- **`examples/polarization_usage.py`**: Detailed usage examples
- **`logs/`**: Runtime logs with detailed progress information

### **Scientific References**
- **Perley & Butler 2013**: "An Accurate Flux Density Scale from 1 to 50 GHz"
- **2019 VLA Polarization Measurements**: Updated calibrator properties
- **CASA Documentation**: https://casa.nrao.edu/
- **VLA Observational Guide**: https://science.nrao.edu/facilities/vla/

### **Development & Contributing**
```bash
# Development setup
git clone <repository> evla-pipeline
cd evla-pipeline
pip install -r requirements.txt
pip install -r test/requirements.txt

# Run test suite
python -m pytest test/

# Code style
# Follow PEP 8, use type hints, include docstrings
```

---

## 📄 **License & Credits**

**License**: GNU General Public License (GPL) version 2  
**Copyright**: 2013-2024 Associated Universities Inc.

### **Original Authors**
- Claire Chandler (NRAO)
- Emmanuel Momjian (NRAO)  
- Steve Myers (NRAO)

### **Modernization & Polarization Integration** 
- Python 3 port: Brian Svoboda (2023)
- Architecture modernization & polarization integration (2024)

---

## 🎯 **Ready to Get Started?**

```bash
# For VLA continuum observations
python -m evla_pipe.run_pipeline your_continuum_data.asdm

# For VLA polarization observations  
python -m evla_pipe.run_pipeline --enable-polarization your_polarization_data.asdm

# Need help?
python -m evla_pipe.run_pipeline --help
```

**The modernized EVLA pipeline makes VLA data calibration simple, robust, and scientifically accurate. Both intensity and polarization observations are fully supported with automatic calibrator detection and intelligent data source selection.**