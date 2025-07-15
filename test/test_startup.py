#!/usr/bin/env python3
"""
Test script for EVLA pipeline startup functionality.
"""

import pytest
from unittest.mock import patch
import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_pipeline_startup_basic():
    """Test basic pipeline startup functionality."""
    from evla_pipe.EVLA_pipe_startup import pipeline_startup
    
    initial_context = {}
    updated_context = pipeline_startup(initial_context)
    
    # Check that context was updated with expected keys
    assert isinstance(updated_context, dict)
    assert "SDM_name" in updated_context
    assert "ms_active" in updated_context
    

def test_pipeline_startup_with_context():
    """Test pipeline startup with pre-filled context."""
    from evla_pipe.EVLA_pipe_startup import pipeline_startup
    
    initial_context = {
        "SDM_name": "test_dataset",
        "do_pol": True,
        "do_hanning": False
    }
    
    updated_context = pipeline_startup(initial_context)
    
    # Check that original values are preserved
    assert updated_context["SDM_name"] == "test_dataset"
    assert updated_context["do_pol"] == True
    assert updated_context["do_hanning"] == False


@patch('evla_pipe.EVLA_pipe_startup.path_exists')
def test_pipeline_startup_file_checks(mock_path_exists):
    """Test pipeline startup file existence checks."""
    from evla_pipe.EVLA_pipe_startup import pipeline_startup
    
    # Mock file existence
    mock_path_exists.return_value = True
    
    initial_context = {"SDM_name": "mock_dataset"}
    updated_context = pipeline_startup(initial_context)
    
    assert updated_context["SDM_name"] == "mock_dataset"


if __name__ == "__main__":
    pytest.main([__file__])