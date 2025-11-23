# Contributing to EVLA Scripted Pipeline

Thank you for your interest in contributing to the EVLA Scripted Pipeline. This document provides guidelines and best practices for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Adding Pipeline Steps](#adding-pipeline-steps)

---

## Code of Conduct

This project adheres to professional and collaborative standards. We expect all contributors to:

- Be respectful and constructive in communications
- Focus on technical merit and scientific accuracy
- Provide evidence-based feedback
- Help maintain code quality and documentation

---

## Getting Started

### Prerequisites

- Python 3.8 or later
- CASA 6.1 or later
- Git
- Familiarity with radio interferometry and VLA data

### Fork and Clone

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/your-username/evla-scripted-pipeline.git
cd evla-scripted-pipeline

# Add upstream remote
git remote add upstream https://github.com/original-org/evla-scripted-pipeline.git
```

---

## Development Setup

### Install in Development Mode

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package in editable mode
pip install -e .

# Install development dependencies
pip install -r test/requirements.txt
pip install black isort mypy pytest pytest-cov
```

### Verify Installation

```bash
# Run tests
python -m pytest test/ -v

# Check type hints
mypy evla_pipe/

# Verify CLI
evla-pipeline --version
```

---

## Architecture Overview

### Registry Pattern

The pipeline uses a decorator-based registry system for pipeline steps:

```python
from evla_pipe.pipeline_steps import register_step
from typing import Dict, Any

@register_step("EVLA_pipe_mystep")
def EVLA_pipe_mystep(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    My custom pipeline step.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """
    # Your implementation here
    return pipeline_context
```

### Key Components

- **evla_pipe/__init__.py**: Package initialization and `exec_script()`
- **evla_pipe/pipeline_steps.py**: Registry system (STEP_REGISTRY, register_step)
- **evla_pipe/config.py**: Centralized configuration (PipelineConfig)
- **evla_pipe/exceptions.py**: Exception hierarchy
- **evla_pipe/logging_config.py**: Logging setup
- **evla_pipe/pipeline.py**: Main `continuum()` function
- **evla_pipe/run_pipeline.py**: CLI entry point
- **evla_pipe/EVLA_pipe_*.py**: Individual pipeline steps

### Data Flow

```
User Input → CLI/API → continuum() → exec_script() → Registry Lookup → Step Function → Context Update → Next Step
```

---

## Coding Standards

### Python Style Guide

Follow PEP 8 with these specifics:

- **Line length**: 100 characters
- **Formatter**: Black
- **Import sorter**: isort (black profile)
- **Type checker**: mypy

### Type Hints

All functions must have type hints:

```python
from typing import Dict, Any, List, Optional, Tuple

def my_function(
    pipeline_context: Dict[str, Any],
    optional_param: Optional[str] = None
) -> Dict[str, Any]:
    """Function with proper type hints."""
    return pipeline_context
```

### Docstrings

Use NumPy-style docstrings:

```python
def calibrate_bandpass(
    pipeline_context: Dict[str, Any],
    refant: str,
    minsnr: float = 3.0
) -> Dict[str, Any]:
    """
    Perform bandpass calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing MS name and configuration
    refant : str
        Reference antenna (e.g., 'ea01')
    minsnr : float, optional
        Minimum SNR for solutions, by default 3.0

    Returns
    -------
    dict
        Updated pipeline context with bandpass table path

    Raises
    ------
    CalibrationError
        If bandpass calibration fails

    Examples
    --------
    >>> context = {'msname': 'data.ms', 'refant': 'ea01'}
    >>> result = calibrate_bandpass(context, refant='ea01', minsnr=3.0)
    """
    # Implementation
    return pipeline_context
```

### Error Handling

Use structured exceptions:

```python
from evla_pipe.exceptions import CalibrationError, CASAError

try:
    # CASA task call
    gaincal(vis=msname, caltable=caltable)
except RuntimeError as e:
    raise CASAError(
        f"Gain calibration failed for {msname}",
        task_name="gaincal",
        step_name="EVLA_pipe_finalcals"
    ) from e
```

### Logging

Use standard Python logging:

```python
from evla_pipe.logging_config import get_logger

logger = get_logger(__name__)

def my_step(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Starting my custom step")
    logger.debug(f"Processing MS: {pipeline_context.get('msname')}")
    logger.warning("Low SNR detected in some solutions")
    logger.error("Critical failure", exc_info=True)
    return pipeline_context
```

### Configuration Access

Use centralized configuration:

```python
from evla_pipe.config import get_config

config = get_config()
log_path = config.get_log_path('mystep')
plot_path = config.get_plot_path('mystep_diagnostic.png')
threshold = config.flag_critfrac
```

---

## Testing

### Writing Tests

Place tests in `test/` directory:

```python
# test/test_mystep.py
import pytest
from evla_pipe import exec_script

def test_mystep_basic():
    """Test basic functionality of mystep."""
    context = {'msname': 'test.ms', 'refant': 'ea01'}
    result = exec_script('EVLA_pipe_mystep', context)
    assert result['QA2_mystep'] == 'Pass'

def test_mystep_missing_msname():
    """Test error handling when msname is missing."""
    context = {}
    with pytest.raises(DataError):
        exec_script('EVLA_pipe_mystep', context)
```

### Running Tests

```bash
# Run all tests
python -m pytest test/ -v

# Run with coverage
python -m pytest test/ --cov=evla_pipe --cov-report=html

# Run specific test
python -m pytest test/test_mystep.py::test_mystep_basic -v
```

### Mocking CASA Tasks

For unit tests, mock CASA tasks:

```python
from unittest.mock import Mock, patch

@patch('evla_pipe.EVLA_pipe_mystep.gaincal')
def test_mystep_with_mock(mock_gaincal):
    """Test mystep with mocked CASA task."""
    mock_gaincal.return_value = None

    context = {'msname': 'test.ms'}
    result = exec_script('EVLA_pipe_mystep', context)

    # Verify gaincal was called correctly
    mock_gaincal.assert_called_once()
    assert result['QA2_mystep'] == 'Pass'
```

---

## Pull Request Process

### Before Submitting

1. **Update from upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**:
   ```bash
   # Format code
   black evla_pipe/
   isort evla_pipe/

   # Type checking
   mypy evla_pipe/

   # Tests
   python -m pytest test/ -v
   ```

3. **Update documentation**: Ensure README and docstrings reflect your changes

### Commit Messages

Write clear, descriptive commit messages:

```
Add polarization angle calibration to polcal step

- Implement Xf table generation using polcal task
- Add automatic polarization calibrator detection
- Update applycals to include Xf tables
- Add unit tests for Xf calibration flow

Fixes #123
```

### Pull Request Template

```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes Made
- [ ] Add/modify pipeline step
- [ ] Update configuration
- [ ] Add tests
- [ ] Update documentation

## Testing
How was this tested?

## Checklist
- [ ] Code follows style guidelines (black, isort)
- [ ] Type hints added
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Commit messages are clear
```

### Review Process

1. Automated checks must pass (tests, type checking)
2. At least one maintainer approval required
3. Address review comments promptly
4. Maintainer will merge when approved

---

## Adding Pipeline Steps

### Step Template

```python
# evla_pipe/EVLA_pipe_mystep.py
from typing import Dict, Any
from evla_pipe.pipeline_steps import register_step
from evla_pipe.utils import runtiming, logprint, format_qa_status
from evla_pipe.logging_config import get_logger
from evla_pipe.exceptions import CalibrationError, CASAError

logger = get_logger(__name__)

@register_step("EVLA_pipe_mystep")
def EVLA_pipe_mystep(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    My custom pipeline step description.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """
    # Initialize logging
    task_logprint = lambda msg: logprint(msg, logfileout="logs/mystep.log")
    task_logprint("*** Starting EVLA_pipe_mystep ***")
    time_list = runtiming('mystep', 'start')

    # Extract required variables
    msname = pipeline_context.get("msname")
    if not msname:
        raise ConfigurationError(
            "Missing msname in pipeline context",
            step_name="EVLA_pipe_mystep"
        )

    # Initialize QA score
    QA2_score = "Pass"

    try:
        # Your calibration logic here
        logger.info(f"Processing {msname}")
        task_logprint(f"Running calibration on {msname}")

        # Call CASA tasks
        # Update pipeline context
        pipeline_context["mystep_output"] = "success"

    except Exception as e:
        logger.error(f"Mystep failed: {e}", exc_info=True)
        task_logprint(f"Error: {e}")
        QA2_score = "Fail"
        raise CalibrationError(
            f"My step calibration failed: {e}",
            step_name="EVLA_pipe_mystep"
        ) from e

    finally:
        # Always record timing and QA
        task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
        time_list = runtiming('mystep', 'end')

        pipeline_context["QA2_mystep"] = QA2_score
        pipeline_context["time_list"] = time_list

    task_logprint("*** Finished EVLA_pipe_mystep ***")
    return pipeline_context
```

### Register in Pipeline Flow

Add your step to the workflow in `evla_pipe/pipeline.py`:

```python
# In continuum() function
steps = [
    "EVLA_pipe_startup",
    "EVLA_pipe_import",
    # ... existing steps ...
    "EVLA_pipe_mystep",  # Add your step
    "EVLA_pipe_weblog",
]
```

### Add Tests

```python
# test/test_mystep.py
import pytest
from evla_pipe import exec_script
from evla_pipe.exceptions import ConfigurationError

def test_mystep_success():
    """Test successful execution."""
    context = {'msname': 'test.ms'}
    result = exec_script('EVLA_pipe_mystep', context)
    assert result['QA2_mystep'] == 'Pass'
    assert 'mystep_output' in result

def test_mystep_no_msname():
    """Test error when msname missing."""
    context = {}
    with pytest.raises(ConfigurationError):
        exec_script('EVLA_pipe_mystep', context)
```

---

## Questions or Issues?

- Check existing issues and documentation first
- Open a new issue for bugs or feature requests
- Use discussions for general questions
- Be specific and provide examples

Thank you for contributing to the EVLA Scripted Pipeline!
