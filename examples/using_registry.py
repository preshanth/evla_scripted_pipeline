"""
Example: Using the Pipeline Step Registry

This demonstrates the new pythonic way to register and use pipeline steps.
"""

from evla_pipe.pipeline_steps import register_step, STEP_REGISTRY


# Example 1: Register a simple step
@register_step("my_custom_step")
def my_calibration_step(context):
    """A custom calibration step."""
    print(f"Running custom calibration on {context.get('SDM_name')}")

    # Do some work...
    context['my_step_completed'] = True

    return context


# Example 2: Register with a different function name
@register_step("EVLA_pipe_custom_flag")
def custom_flagging(context):
    """Custom flagging step - function name doesn't need to match."""
    print("Running custom flagging")
    return context


# Example 3: Direct usage (without pipeline)
if __name__ == "__main__":
    # Create a test context
    test_context = {"SDM_name": "test_data.ms"}

    # Call the step directly
    result = my_calibration_step(test_context)
    print(f"Result: {result}")

    # Or get from registry
    func = STEP_REGISTRY["my_custom_step"]
    result = func(test_context)

    # List all registered steps
    print(f"\nRegistered steps: {list(STEP_REGISTRY.keys())}")
