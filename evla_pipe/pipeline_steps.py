"""
Pipeline step registry.

Provides a simple, pythonic way to register and execute pipeline steps
without dynamic imports or exec() calls.
"""

# Global registry mapping step names to functions
STEP_REGISTRY = {}


def register_step(name):
    """
    Decorator to register a pipeline step function.

    Usage:
        @register_step("EVLA_pipe_import")
        def import_data(context):
            # ... implementation
            return context
    """
    def decorator(func):
        STEP_REGISTRY[name] = func
        return func
    return decorator


def get_step(name):
    """Get a registered step function by name."""
    if name not in STEP_REGISTRY:
        raise KeyError(
            f"Pipeline step '{name}' not registered. "
            f"Available steps: {sorted(STEP_REGISTRY.keys())}"
        )
    return STEP_REGISTRY[name]


def list_steps():
    """List all registered pipeline steps."""
    return sorted(STEP_REGISTRY.keys())
