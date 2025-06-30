# EVLA Pipeline Testing Strategy

## Overview
This document outlines the incremental testing strategy for the refactored EVLA pipeline, focusing on ensuring reliability while maintaining compatibility with CASA and the original pipeline functionality.

## Testing Levels

### 1. Unit Tests
**Purpose**: Test individual functions and classes in isolation

**Coverage**:
- `evla_pipe.polarization` module functions
- `EVLA_pipe_msinfo.py` msmetadata operations  
- Utility functions in `utils.py`
- Configuration classes (PolConfig, etc.)

**Implementation**:
```python
# Example unit test structure
def test_pol_config_creation():
    from evla_pipe.polarization import PolConfig
    config = PolConfig(reference_antenna='ea01')
    assert config.reference_antenna == 'ea01'
    assert config.solve_kcross == True  # default

def test_msinfo_with_mock_data():
    # Test msmetadata integration with mock MS
    pass
```

### 2. Integration Tests  
**Purpose**: Test module interactions and pipeline flow

**Coverage**:
- Polarization module integration with main pipeline
- msinfo refactor integration with pipeline context
- CLI argument parsing and pipeline execution
- File I/O and CASA tool interactions

**Implementation**:
```python
def test_polarization_pipeline_integration():
    # Test that polarization integrates properly with main pipeline
    context = {'msname': 'test.ms', 'do_pol': True}
    result = integrate_polarization_calibration(context)
    assert 'polarization_success' in result

def test_msinfo_context_propagation():
    # Test that msinfo results propagate correctly through pipeline
    pass
```

### 3. System Tests
**Purpose**: Test complete pipeline execution with real/simulated data

**Coverage**:
- End-to-end pipeline execution
- Real CASA measurement set processing
- Output file generation and validation
- Performance benchmarking vs original pipeline

### 4. Regression Tests
**Purpose**: Ensure refactored code produces equivalent results to original

**Coverage**:
- Compare calibration table outputs
- Validate scientific results consistency
- Check log file consistency
- Performance regression detection

## Testing Framework

### Test Structure
```
tests/
├── unit/
│   ├── test_polarization.py
│   ├── test_msinfo_refactor.py
│   ├── test_utils.py
│   └── test_configuration.py
├── integration/
│   ├── test_pipeline_integration.py
│   ├── test_polarization_integration.py
│   └── test_cli_integration.py
├── system/
│   ├── test_end_to_end.py
│   ├── test_real_data.py
│   └── test_performance.py
├── regression/
│   ├── test_calibration_equivalence.py
│   └── test_output_comparison.py
└── fixtures/
    ├── mock_ms_data/
    ├── reference_outputs/
    └── test_configurations/
```

### Mock Data Strategy
For tests that don't require real CASA data:

```python
# Mock msmetadata for unit tests
class MockMSMetadata:
    def __init__(self, mock_data):
        self.data = mock_data
        
    def nspw(self):
        return self.data.get('nspw', 4)
        
    def fieldnames(self):
        return self.data.get('fields', ['3c286', '3c147', 'target'])
        
    def scansforfield(self, field_id):
        return self.data.get('scans', {}).get(field_id, [])
```

## Incremental Testing Approach

### Phase 1: Core Functionality (Current Priority)
**Status**: ✅ Completed
- [x] Import tests - verify modules can be imported
- [x] Configuration tests - verify dataclasses work correctly  
- [x] Basic integration tests - verify CLI and pipeline accept new parameters

### Phase 2: Isolated Module Testing
**Status**: 🔄 Next phase
- [ ] Unit tests for polarization module functions
- [ ] Unit tests for refactored msinfo functions
- [ ] Mock-based integration testing
- [ ] Configuration validation tests

**Implementation Priority**:
1. Polarization module unit tests
2. MSinfo refactor validation  
3. Pipeline context propagation tests
4. Error handling and edge cases

### Phase 3: Integration Testing
**Status**: 📋 Planned
- [ ] Pipeline integration with mock data
- [ ] Cross-module communication testing
- [ ] Error propagation and handling
- [ ] Resource management (file handles, memory)

### Phase 4: System & Regression Testing
**Status**: 📋 Planned  
- [ ] End-to-end pipeline execution
- [ ] Real data processing tests
- [ ] Performance benchmarking
- [ ] Output equivalence verification

## Test Data Requirements

### Mock Data Sets
1. **Minimal Test MS**: 
   - Small synthetic measurement set
   - Contains standard calibrators (3c286, 3c147)
   - Multiple spws, basic scan structure
   - Used for fast unit/integration tests

2. **Standard Test MS**:
   - Real VLA observation (small dataset)
   - Full calibrator complement
   - Representative of typical pipeline input
   - Used for system testing

3. **Regression Test MS**:
   - Known dataset with validated outputs
   - Original pipeline results archived
   - Used for regression testing

### Test Configurations
```python
# Example test configurations
TEST_CONFIGS = {
    'minimal': {
        'polarization': False,
        'hanning': False,
        'calibrators': ['3c286']
    },
    'standard': {
        'polarization': True, 
        'hanning': True,
        'calibrators': ['3c286', '3c147']
    },
    'stress': {
        'polarization': True,
        'large_dataset': True,
        'memory_constraints': True
    }
}
```

## Performance Testing

### Benchmarks
1. **MSinfo Refactor Performance**:
   - Compare msmetadata vs table tool performance
   - Memory usage comparison
   - Execution time benchmarks

2. **Polarization Module Performance**: 
   - Calibration solving times
   - Memory efficiency
   - Scaling with dataset size

3. **Overall Pipeline Performance**:
   - End-to-end execution time
   - Memory usage patterns
   - I/O efficiency

### Performance Targets
- MSinfo refactor: ≥20% speed improvement over original
- Polarization module: Comparable performance to original modules
- Overall pipeline: No significant performance regression (±5%)

## Continuous Integration

### Test Automation
```yaml
# Example CI configuration
test_matrix:
  - python_version: [3.7, 3.8, 3.9, 3.10]
  - casa_version: [6.1.0, 6.2.0, 6.4.0] 
  - test_suite: [unit, integration, system]

test_phases:
  1. unit_tests:
     - Run without CASA dependencies
     - Fast execution (<5 minutes)
     - Required for all PRs
     
  2. integration_tests:
     - Require CASA installation
     - Medium execution time (15-30 minutes)
     - Required for main branch merges
     
  3. system_tests:
     - Full pipeline execution
     - Long execution time (1-3 hours)
     - Nightly execution on main branch
```

### Test Coverage Goals
- Unit tests: >90% code coverage
- Integration tests: >80% feature coverage
- System tests: 100% major use cases
- Regression tests: 100% critical scientific outputs

## Documentation Testing

### Code Examples
All documentation code examples should be tested:
```python
def test_documentation_examples():
    """Test that all code examples in docs actually work."""
    # Extract code from docstrings and README
    # Execute in isolated environment
    # Verify expected behavior
```

### API Documentation
- Verify all public functions have docstrings
- Test docstring examples with doctest
- Validate type hints consistency

## Error Handling Testing

### Exception Scenarios
1. **Missing calibrators**: No pol calibrators found
2. **CASA tool failures**: MSmetadata connection issues
3. **Resource constraints**: Insufficient memory/disk space
4. **Invalid inputs**: Malformed MS, missing files
5. **Interrupted execution**: Signal handling, cleanup

### Recovery Testing
- Test pipeline restart capabilities
- Validate temporary file cleanup
- Verify graceful degradation modes

## Testing Tools & Infrastructure

### Required Tools
- `pytest`: Primary testing framework
- `pytest-cov`: Coverage reporting
- `pytest-mock`: Mocking capabilities
- `pytest-benchmark`: Performance testing
- `tox`: Multi-environment testing

### Custom Testing Utilities
```python
# Testing utilities for pipeline
class PipelineTestCase:
    """Base class for pipeline tests."""
    
    def setup_mock_ms(self, config):
        """Create mock measurement set."""
        pass
        
    def compare_cal_tables(self, table1, table2):
        """Compare calibration table contents."""
        pass
        
    def assert_scientific_equivalence(self, result1, result2, tolerance=1e-6):
        """Assert scientific results are equivalent within tolerance."""
        pass
```

## Success Criteria

### Functionality
- ✅ All refactored modules import successfully
- ✅ Basic pipeline execution completes without errors
- 🔄 Polarization calibration produces valid results
- 📋 Scientific output matches original pipeline (within tolerance)

### Performance  
- 📋 MSinfo refactor shows performance improvement
- 📋 Overall pipeline performance maintained
- 📋 Memory usage optimized

### Maintainability
- ✅ Code follows pythonic patterns
- ✅ Clear module separation and interfaces
- ✅ Comprehensive documentation
- 🔄 Test coverage meets targets

### Usability
- ✅ Can be imported and used programmatically
- ✅ CLI interface maintained and enhanced
- ✅ Clear examples and usage patterns
- 🔄 Error messages are clear and actionable

## Next Steps

1. **Immediate** (Phase 2): Implement unit tests for polarization module
2. **Short-term**: Add integration tests with mock data
3. **Medium-term**: System testing with real data
4. **Long-term**: Performance optimization and regression testing

This testing strategy ensures the refactored EVLA pipeline maintains scientific accuracy while gaining the benefits of modern, pythonic design patterns.