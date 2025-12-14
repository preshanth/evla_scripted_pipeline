#!/usr/bin/env python3
"""
Example usage of the modular polarization calibration interface.

This script demonstrates different ways to use the polarization module:
1. High-level function usage (simplest)
2. Object-oriented interface with context manager
3. Step-by-step calibration with individual functions
4. Custom configuration
"""

import sys
from pathlib import Path

# Add the package to the path (if running as example)
sys.path.insert(0, str(Path(__file__).parent.parent))


# Example 1: High-level function usage (simplest approach)
def example_simple_polarization(msname):
    """Simplest way to run polarization calibration."""
    from evla_pipe.polarization import calibrate_polarization_full

    print("Example 1: Simple polarization calibration")
    print("-" * 40)

    try:
        # This does everything in one function call
        cal_tables = calibrate_polarization_full(msname)
        print(f"Created calibration tables: {list(cal_tables.keys())}")
        return cal_tables
    except Exception as e:
        print(f"Error: {e}")
        return None


# Example 2: Object-oriented interface with context manager
def example_object_oriented(msname):
    """Using the object-oriented interface with context manager."""
    from evla_pipe.polarization import PolarizationCalibrator, PolConfig

    print("\nExample 2: Object-oriented interface")
    print("-" * 40)

    # Custom configuration
    config = PolConfig(
        reference_antenna="ea01",
        minsnr=5.0,  # Higher SNR requirement
        solve_kcross=True,
        solve_leakage=True,
        solve_angle=True,
    )

    try:
        with PolarizationCalibrator(msname, config) as polcal:
            # Find calibrators
            calibrators = polcal.find_polarization_calibrators()
            print(
                f"Found calibrators: {[cal.name for cal in calibrators.values() if cal]}"
            )

            if calibrators["angle"] and calibrators["leakage"]:
                # Run full calibration sequence
                cal_tables = polcal.calibrate_polarization(calibrators)
                print(f"Created tables: {list(cal_tables.keys())}")
                return cal_tables
            else:
                print("Insufficient calibrators found")
                return None

    except Exception as e:
        print(f"Error: {e}")
        return None


# Example 3: Step-by-step calibration
def example_step_by_step(msname):
    """Step-by-step calibration with individual functions."""
    from evla_pipe.polarization import (
        PolConfig,
        find_pol_calibrators,
        set_pol_models,
        solve_pol_angle,
        solve_pol_kcross,
        solve_pol_leakage,
    )

    print("\nExample 3: Step-by-step calibration")
    print("-" * 40)

    config = PolConfig(reference_antenna="ea01")

    try:
        # Step 1: Find calibrators
        calibrators = find_pol_calibrators(msname, config)
        angle_cal = calibrators["angle"]
        leak_cal = calibrators["leakage"]

        if not angle_cal or not leak_cal:
            print("Insufficient calibrators found")
            return None

        print(f"Angle calibrator: {angle_cal.name}")
        print(f"Leakage calibrator: {leak_cal.name}")

        # Step 2: Set models
        set_pol_models(msname, calibrators)
        print("Set standard models")

        # Step 3: Solve Kcross
        kcross_table = solve_pol_kcross(msname, angle_cal, config=config)
        print(f"Solved Kcross: {kcross_table}")

        # Step 4: Solve D-terms
        dterms_table = solve_pol_leakage(msname, leak_cal, [kcross_table], config)
        print(f"Solved D-terms: {dterms_table}")

        # Step 5: Solve polarization angle
        polangle_table = solve_pol_angle(
            msname, angle_cal, [kcross_table, dterms_table], config
        )
        print(f"Solved pol angle: {polangle_table}")

        return {
            "kcross": kcross_table,
            "leakage": dterms_table,
            "angle": polangle_table,
        }

    except Exception as e:
        print(f"Error: {e}")
        return None


# Example 4: Integration with existing pipeline
def example_pipeline_integration(pipeline_context):
    """Show how to integrate with existing pipeline context."""
    from evla_pipe.polarization import integrate_polarization_calibration

    print("\nExample 4: Pipeline integration")
    print("-" * 40)

    # Simulate pipeline context
    if "msname" not in pipeline_context:
        print("No msname in pipeline context")
        return pipeline_context

    # Enable polarization
    pipeline_context["do_pol"] = True

    # Add some prior calibration tables (simulated)
    pipeline_context["delay_cal_table"] = "test.K0"
    pipeline_context["bpass_cal_table"] = "test.B0"
    pipeline_context["phase_cal_table"] = "test.G0"

    # Run integration function
    updated_context = integrate_polarization_calibration(pipeline_context)

    if updated_context.get("polarization_success"):
        print("Polarization calibration successful!")
        print(f"Tables: {updated_context.get('polarization_cal_tables', {})}")
    else:
        print(
            f"Polarization failed: {updated_context.get('polarization_error', 'Unknown error')}"
        )

    return updated_context


# Example 5: Interactive usage
def example_interactive():
    """Show how to use the module interactively."""
    print("\nExample 5: Interactive usage patterns")
    print("-" * 40)

    # This is how you would use it in a Python session or Jupyter notebook
    code_example = """
# Import what you need
from evla_pipe.polarization import PolarizationCalibrator, PolConfig

# Quick and simple
from evla_pipe import calibrate_polarization_full
tables = calibrate_polarization_full('my_data.ms')

# With custom config
from evla_pipe import PolConfig
config = PolConfig(reference_antenna='ea01', minsnr=5.0)
tables = calibrate_polarization_full('my_data.ms', config=config)

# Object-oriented approach
with PolarizationCalibrator('my_data.ms') as polcal:
    cals = polcal.find_polarization_calibrators()
    if cals['angle'] and cals['leakage']:
        tables = polcal.calibrate_polarization(cals)

# Find calibrators only
from evla_pipe import find_pol_calibrators
cals = find_pol_calibrators('my_data.ms')
print(f"Available: {[c.name for c in cals.values() if c]}")
"""

    print("Code examples for interactive use:")
    print(code_example)


def main():
    """Run all examples (with fake data for demonstration)."""
    print("EVLA Pipeline Polarization Module Usage Examples")
    print("=" * 60)

    # Use a fake MS name for demonstration
    fake_msname = "example_data.ms"

    print(f"Note: Using fake MS name '{fake_msname}' for demonstration")
    print("In real usage, replace with your actual measurement set path.")

    # Show the different usage patterns
    example_interactive()

    # The following would work with real data:
    # example_simple_polarization(fake_msname)
    # example_object_oriented(fake_msname)
    # example_step_by_step(fake_msname)

    # Pipeline integration example
    fake_context = {"msname": fake_msname}
    example_pipeline_integration(fake_context)

    print("\n" + "=" * 60)
    print("Key advantages of the new modular design:")
    print("• Clean, importable functions for any use case")
    print("• Object-oriented interface with context managers")
    print("• Flexible configuration with dataclasses")
    print("• Can be used interactively or in automated pipelines")
    print("• Separate functions for each calibration step")
    print("• Native integration with msmetadata for efficiency")


if __name__ == "__main__":
    main()
