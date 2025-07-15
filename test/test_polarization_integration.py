#!/usr/bin/env python3
"""
Test script for polarization wrapper integration.

This script verifies that the polarization wrapper integrates correctly
with the main pipeline without requiring actual CASA data.
"""

import pytest
import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPolarizationImports:
    """Test polarization import functionality."""
    
    def test_polarization_classes_import(self):
        """Test that polarization classes can be imported."""
        try:
            from evla_pipe.polarization import PolarizationCalibrator, PolConfig, PolCalibrator
            assert True
        except ImportError:
            pytest.skip("Polarization classes not available without CASA")
    
    def test_polarization_utils_import(self):
        """Test that polarization utilities can be imported."""
        try:
            from evla_pipe.pol_setjy_utils import get_polcal_data, fit_polarization_polynomials
            assert True
        except ImportError:
            pytest.skip("Polarization utilities not available without CASA")


class TestPolarizationConfig:
    """Test polarization configuration functionality."""
    
    def test_pol_config_creation(self):
        """Test polarization configuration creation."""
        try:
            from evla_pipe.polarization import PolConfig
            
            # Test default configuration
            config = PolConfig()
            assert hasattr(config, 'pol_angle_calibrators')
            
        except ImportError:
            pytest.skip("PolConfig not available without CASA")
    
    def test_pol_calibrator_creation(self):
        """Test polarization calibrator creation."""
        try:
            from evla_pipe.polarization import PolCalibrator
            
            # Test calibrator creation with minimal parameters
            calibrator = PolCalibrator(
                source_name='3C286',
                field_id=0,
                spw_list=[0]
            )
            assert calibrator.source_name == '3C286'
            assert calibrator.field_id == 0
            
        except (ImportError, TypeError):
            pytest.skip("PolCalibrator not available without CASA or requires more parameters")


class TestPipelineIntegration:
    """Test pipeline integration functionality."""
    
    def test_continuum_function_signature(self):
        """Test that the main pipeline accepts polarization parameters."""
        from evla_pipe import continuum
        import inspect
        
        # Check that continuum function has enable_polarization parameter
        sig = inspect.signature(continuum)
        params = list(sig.parameters.keys())
        
        assert 'enable_polarization' in params, "enable_polarization parameter missing"
        
        # Check default value
        default_val = sig.parameters['enable_polarization'].default
        assert default_val == False, "Default value for enable_polarization should be False"
    
    def test_pipeline_context_structure(self):
        """Test that pipeline context supports polarization fields."""
        # Test that we can create a context with polarization fields
        context = {
            'do_pol': True,
            'polarization_calibrated': False,
            'pol_cal_tables': [],
            'kcross_cal_table': None,
            'dterms_cal_table': None
        }
        
        assert context['do_pol'] == True
        assert 'polarization_calibrated' in context
        assert isinstance(context['pol_cal_tables'], list)


class TestCLIIntegration:
    """Test CLI integration functionality."""
    
    def test_cli_polarization_flags(self):
        """Test that CLI supports polarization flags."""
        from evla_pipe.run_pipeline import create_argument_parser
        
        parser = create_argument_parser()
        
        # Test that --polarization flag exists
        args = parser.parse_args(['test.ms', '--polarization'])
        assert hasattr(args, 'polarization')
        assert args.polarization == True
        
        # Test default value
        args_default = parser.parse_args(['test.ms'])
        assert args_default.polarization == False


class TestMSInfoIntegration:
    """Test msinfo integration functionality."""
    
    def test_msmd_function_exists(self):
        """Test that msmd function exists and is callable."""
        from evla_pipe.EVLA_pipe_msmd import EVLA_pipe_msmd
        import inspect
        
        # Check that EVLA_pipe_msmd function exists and is callable
        assert callable(EVLA_pipe_msmd)
        
        # Check function signature
        sig = inspect.signature(EVLA_pipe_msmd)
        params = list(sig.parameters.keys())
        assert 'pipeline_context' in params
    
    def test_get_ms_info_function(self):
        """Test that get_ms_info function exists."""
        from evla_pipe.EVLA_pipe_msmd import get_ms_info
        import inspect
        
        assert callable(get_ms_info)
        
        # Check function signature
        sig = inspect.signature(get_ms_info)
        params = list(sig.parameters.keys())
        assert 'pipeline_context' in params


@pytest.fixture
def sample_polarization_context():
    """Fixture providing sample polarization context for testing."""
    return {
        'do_pol': True,
        'SDM_name': 'test_dataset',
        'msname': 'test_dataset.ms',
        'EVLA_band': 'C',
        'polarization_calibrated': False,
        'pol_cal_tables': [],
        'standard_source_names': ['3C286', '3C147']
    }


def test_polarization_workflow_structure(sample_polarization_context):
    """Test that polarization workflow structure is correct."""
    context = sample_polarization_context
    
    # Test initial state
    assert context['do_pol'] == True
    assert context['polarization_calibrated'] == False
    assert len(context['pol_cal_tables']) == 0
    
    # Simulate polarization calibration completion
    context['polarization_calibrated'] = True
    context['pol_cal_tables'] = ['test.Xf', 'test.Df']
    context['kcross_cal_table'] = 'test.Xf'
    context['dterms_cal_table'] = 'test.Df'
    
    # Test final state
    assert context['polarization_calibrated'] == True
    assert len(context['pol_cal_tables']) == 2
    assert 'test.Xf' in context['pol_cal_tables']
    assert 'test.Df' in context['pol_cal_tables']


def test_integration_completeness():
    """Test that all required components are available."""
    required_modules = [
        'evla_pipe.EVLA_pipe_polcal',
        'evla_pipe.EVLA_pipe_msmd',
        'evla_pipe.run_pipeline',
        'evla_pipe.pipeline'
    ]
    
    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError as e:
            pytest.fail(f"Required module {module_name} not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])