#!/usr/bin/env python3
"""
Test script for polarization wrapper integration.

This script verifies that the polarization wrapper integrates correctly
with the main pipeline without requiring actual CASA data.
"""

import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_polarization_imports():
    """Test that polarization classes can be imported."""
    print("Testing polarization imports...")
    
    try:
        from evla_pipe import PolarizationCalibrationManager, PolarizationConfig
        print("✓ Successfully imported polarization classes")
        return True
    except ImportError as e:
        print(f"✗ Failed to import polarization classes: {e}")
        return False

def test_polarization_config():
    """Test polarization configuration creation."""
    print("Testing polarization configuration...")
    
    try:
        from evla_pipe.polarization_wrapper import PolarizationConfig
        
        # Test default configuration
        config = PolarizationConfig()
        assert not config.enable_polarization
        assert config.pol_angle_calibrators is not None
        assert len(config.pol_angle_calibrators) > 0
        assert '3c286' in config.pol_angle_calibrators
        
        # Test custom configuration
        config_custom = PolarizationConfig(
            enable_polarization=True,
            reference_antenna='ea01',
            pol_mode='linear'
        )
        assert config_custom.enable_polarization
        assert config_custom.reference_antenna == 'ea01'
        assert config_custom.pol_mode == 'linear'
        
        print("✓ Polarization configuration works correctly")
        return True
    except Exception as e:
        print(f"✗ Polarization configuration test failed: {e}")
        return False

def test_pipeline_integration():
    """Test that the main pipeline accepts polarization parameters."""
    print("Testing pipeline integration...")
    
    try:
        from evla_pipe import continuum
        import inspect
        
        # Check that continuum function has enable_polarization parameter
        sig = inspect.signature(continuum)
        params = list(sig.parameters.keys())
        
        assert 'enable_polarization' in params, "enable_polarization parameter missing"
        
        # Check default value
        default_val = sig.parameters['enable_polarization'].default
        assert default_val == False, "Default value for enable_polarization should be False"
        
        print("✓ Pipeline integration successful")
        return True
    except Exception as e:
        print(f"✗ Pipeline integration test failed: {e}")
        return False

def test_cli_integration():
    """Test that CLI supports polarization flags."""
    print("Testing CLI integration...")
    
    try:
        from evla_pipe.run_pipeline import create_argument_parser
        
        parser = create_argument_parser()
        
        # Test that --enable-polarization flag exists
        args = parser.parse_args(['test.ms', '--enable-polarization'])
        assert hasattr(args, 'enable_polarization')
        assert args.enable_polarization == True
        
        # Test default value
        args_default = parser.parse_args(['test.ms'])
        assert args_default.enable_polarization == False
        
        print("✓ CLI integration successful")
        return True
    except Exception as e:
        print(f"✗ CLI integration test failed: {e}")
        return False

def test_msinfo_integration():
    """Test that msinfo refactor includes polarization context."""
    print("Testing msinfo integration...")
    
    try:
        from evla_pipe.EVLA_pipe_msinfo import get_ms_info
        import inspect
        
        # Check that get_ms_info function exists and is callable
        assert callable(get_ms_info)
        
        # Check function signature
        sig = inspect.signature(get_ms_info)
        params = list(sig.parameters.keys())
        assert 'pipeline_context' in params
        
        print("✓ msinfo integration successful")
        return True
    except Exception as e:
        print(f"✗ msinfo integration test failed: {e}")
        return False

def main():
    """Run all integration tests."""
    print("=" * 60)
    print("EVLA Pipeline Polarization Integration Tests")
    print("=" * 60)
    
    tests = [
        test_polarization_imports,
        test_polarization_config,
        test_pipeline_integration,
        test_cli_integration,
        test_msinfo_integration,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())