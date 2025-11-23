# Installation Guide

Comprehensive installation instructions for the EVLA Scripted Pipeline.

## Table of Contents

- [System Requirements](#system-requirements)
- [CASA Installation](#casa-installation)
- [Pipeline Installation](#pipeline-installation)
- [Verification](#verification)
- [Platform-Specific Notes](#platform-specific-notes)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements

- **Operating System**: Linux, macOS, or Windows with WSL2
- **Python**: 3.8 or later
- **CASA**: 6.1.0 or later (monolithic or modular)
- **RAM**: 8 GB minimum, 16 GB recommended
- **Disk Space**: 50 GB free space for pipeline and data products

### Recommended Requirements

- **Python**: 3.10 or later
- **CASA**: 6.5 or later
- **RAM**: 32 GB or more for large datasets
- **CPU**: Multi-core processor (4+ cores recommended)
- **Disk**: SSD for better I/O performance

---

## CASA Installation

The pipeline requires CASA (Common Astronomy Software Applications) version 6.1 or later.

### Option 1: Monolithic CASA (Recommended for Most Users)

Download and install monolithic CASA from the official website:

```bash
# Visit https://casa.nrao.edu/casa_obtaining.shtml
# Download the appropriate version for your platform
# Extract and add to PATH

# Example for Linux:
tar -xzf casa-6.5.0-15-py3.8.tar.gz
export PATH="$PWD/casa-6.5.0-15/bin:$PATH"

# Verify installation
casa --version
```

### Option 2: Modular CASA (For Python Developers)

Install CASA as Python modules using pip:

```bash
# Requires Python 3.8+
pip install casatasks==6.5.0.15
pip install casatools==6.5.0.15
pip install casaplotms==6.5.0.15

# Verify installation
python -c "import casatasks; print(casatasks.__version__)"
```

**Note**: Modular CASA versions must match exactly. Use the same version for all three packages.

### Version Compatibility

| CASA Version | Python Version | Pipeline Support |
|--------------|----------------|------------------|
| 6.1.x        | 3.6, 3.7, 3.8  | ✅ Supported      |
| 6.2.x        | 3.6, 3.7, 3.8  | ✅ Supported      |
| 6.4.x        | 3.6, 3.8       | ✅ Supported      |
| 6.5.x        | 3.8, 3.10      | ✅ Recommended    |
| 6.6.x        | 3.8, 3.10, 3.11| ✅ Recommended    |

---

## Pipeline Installation

### Standard Installation

For end users who want to run the pipeline:

```bash
# Clone the repository
git clone https://github.com/nrao/evla-scripted-pipeline.git
cd evla-scripted-pipeline

# Install the package
pip install -e .

# Verify installation
evla-pipeline --version
```

### Development Installation

For contributors who want to modify the pipeline:

```bash
# Clone the repository
git clone https://github.com/nrao/evla-scripted-pipeline.git
cd evla-scripted-pipeline

# Install in editable mode with development dependencies
pip install -e .
pip install -r test/requirements.txt

# Install code quality tools
pip install black isort mypy pytest pytest-cov

# Verify installation
evla-pipeline --version
python -m pytest test/ -v
```

### Virtual Environment (Recommended)

Using a virtual environment isolates the pipeline installation:

```bash
# Create virtual environment
python -m venv evla-env

# Activate (Linux/macOS)
source evla-env/bin/activate

# Activate (Windows)
evla-env\Scripts\activate

# Install pipeline
cd evla-scripted-pipeline
pip install -e .

# When done, deactivate
deactivate
```

### conda Environment (Alternative)

For conda users:

```bash
# Create conda environment
conda create -n evla python=3.10
conda activate evla

# Install CASA (if using modular)
pip install casatasks casatools casaplotms

# Install pipeline
cd evla-scripted-pipeline
pip install -e .

# Verify
evla-pipeline --version
```

---

## Verification

### Quick Verification

```bash
# Check pipeline version
evla-pipeline --version

# Check CASA availability
python -c "import casatasks; print('CASA OK')"

# Check Python version
python --version

# Run help
evla-pipeline --help
```

### Comprehensive Verification

```bash
# Run pipeline tests (requires test dependencies)
python -m pytest test/ -v

# Check type hints
mypy evla_pipe/

# Verify all imports
python -c "
from evla_pipe import continuum, exec_script
from evla_pipe.config import get_config
from evla_pipe.exceptions import PipelineError
from evla_pipe.logging_config import get_logger
print('All imports successful')
"
```

### Test Run (Optional)

If you have test data:

```bash
# Run pipeline on small test dataset
evla-pipeline --verbose test_data.asdm

# Check outputs
ls -lh logs/
ls -lh weblog/
ls -lh final_caltables/
```

---

## Platform-Specific Notes

### Linux

Most straightforward platform for CASA and the pipeline.

```bash
# Ubuntu/Debian dependencies
sudo apt-get update
sudo apt-get install python3-pip python3-venv git

# RHEL/CentOS dependencies
sudo yum install python3-pip python3-virtualenv git

# Install pipeline
git clone <repository-url>
cd evla-scripted-pipeline
pip3 install -e .
```

### macOS

CASA runs natively on macOS (Intel and Apple Silicon).

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.10

# Install pipeline
git clone <repository-url>
cd evla-scripted-pipeline
pip3 install -e .
```

**Apple Silicon (M1/M2) Note**: Use modular CASA with Rosetta 2 or wait for native ARM builds.

```bash
# Install Rosetta (one-time)
softwareupdate --install-rosetta

# Use x86_64 Python
arch -x86_64 pip3 install casatasks casatools casaplotms
```

### Windows (WSL2)

CASA is not supported on native Windows. Use Windows Subsystem for Linux 2 (WSL2).

```powershell
# In PowerShell (Administrator)
wsl --install
wsl --set-default-version 2

# Restart computer
# Open Ubuntu from Start menu
```

Then follow Linux instructions inside WSL2:

```bash
# Inside WSL2 Ubuntu
sudo apt-get update
sudo apt-get install python3-pip python3-venv git
git clone <repository-url>
cd evla-scripted-pipeline
pip3 install -e .
```

**Accessing Windows Files**: WSL2 can access Windows filesystems at `/mnt/c/`, `/mnt/d/`, etc.

---

## Troubleshooting

### CASA Import Errors

**Problem**: `ModuleNotFoundError: No module named 'casatasks'`

**Solution**:
```bash
# Check Python version
python --version  # Must be 3.8+

# Install modular CASA
pip install casatasks casatools casaplotms

# Or verify monolithic CASA is in PATH
casa --version
```

### Version Conflicts

**Problem**: `ImportError: CASA version mismatch`

**Solution**:
```bash
# Check all CASA module versions
pip list | grep casa

# Uninstall all
pip uninstall casatasks casatools casaplotms

# Reinstall matching versions
pip install casatasks==6.5.0.15 casatools==6.5.0.15 casaplotms==6.5.0.15
```

### Permission Denied

**Problem**: `PermissionError` during installation

**Solution**:
```bash
# Use virtual environment (recommended)
python -m venv evla-env
source evla-env/bin/activate
pip install -e .

# Or install to user directory
pip install --user -e .
```

### Pipeline Not Found After Installation

**Problem**: `evla-pipeline: command not found`

**Solution**:
```bash
# Check if pip bin directory is in PATH
python -m site --user-base

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# Add to PATH (macOS with Homebrew Python)
export PATH="/usr/local/opt/python@3.10/bin:$PATH"

# Or run directly
python -m evla_pipe.run_pipeline --help
```

### NumPy/SciPy Compatibility

**Problem**: `ImportError: NumPy version incompatible`

**Solution**:
```bash
# Update to compatible versions
pip install --upgrade "numpy>=1.20.0,<2.0"
pip install --upgrade "scipy>=1.5.0"
```

### Disk Space Issues

**Problem**: Pipeline fails with "No space left on device"

**Solution**:
```bash
# Check disk usage
df -h

# Clean up old pipeline runs
rm -rf logs/ weblog/ plots/ *_caltables/

# Use different working directory with more space
cd /path/to/large/disk
evla-pipeline /path/to/data.asdm
```

### Memory Issues

**Problem**: `MemoryError` or process killed

**Solution**:
```bash
# Check available memory
free -h

# Disable plotting to reduce memory
evla-pipeline --disable-plots your_data.asdm

# Process smaller chunks or increase swap space
sudo fallocate -l 32G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Post-Installation Configuration

### Environment Variables (Optional)

```bash
# Add to ~/.bashrc or ~/.zshrc

# CASA path (if using monolithic)
export PATH="/path/to/casa/bin:$PATH"

# Pipeline configuration
export EVLA_PIPELINE_LOG_LEVEL="DEBUG"
export EVLA_PIPELINE_PLOTS_ENABLED="true"

# Working directory
export EVLA_PIPELINE_WORKDIR="/data/pipeline_runs"
```

### Directory Setup

Create standard working directories:

```bash
# Create pipeline working directory
mkdir -p ~/pipeline_work/{logs,weblog,plots,final_caltables}
cd ~/pipeline_work

# Now run pipeline
evla-pipeline /path/to/data.asdm
```

---

## Upgrading

### Update Pipeline

```bash
# Navigate to pipeline directory
cd evla-scripted-pipeline

# Pull latest changes
git pull origin main

# Reinstall
pip install -e . --upgrade
```

### Update CASA

```bash
# For modular CASA
pip install --upgrade casatasks casatools casaplotms

# For monolithic CASA
# Download new version and update PATH
```

---

## Uninstallation

### Remove Pipeline

```bash
# If installed with pip
pip uninstall evla-pipeline

# Remove cloned repository
rm -rf evla-scripted-pipeline
```

### Remove CASA

```bash
# For modular CASA
pip uninstall casatasks casatools casaplotms

# For monolithic CASA
rm -rf /path/to/casa-*
```

---

## Getting Help

If you encounter issues not covered here:

1. Check the [README](README.md) for usage examples
2. Review [Troubleshooting](README.md#troubleshooting) section
3. Search existing GitHub issues
4. Open a new issue with:
   - Operating system and version
   - Python version (`python --version`)
   - CASA version (`casa --version` or `python -c "import casatasks; print(casatasks.__version__)"`)
   - Complete error message
   - Steps to reproduce

---

## Quick Start Summary

```bash
# 1. Install CASA
pip install casatasks casatools casaplotms

# 2. Clone and install pipeline
git clone <repository-url>
cd evla-scripted-pipeline
pip install -e .

# 3. Verify
evla-pipeline --version

# 4. Run
evla-pipeline your_data.asdm
```

For detailed usage, see the [README](README.md).
