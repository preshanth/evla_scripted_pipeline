"""
Pipeline Exception Hierarchy

Structured exceptions for better error handling and reporting.
"""


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    def __init__(self, message: str, step_name: str = None):
        self.step_name = step_name
        super().__init__(message)


class ConfigurationError(PipelineError):
    """Pipeline configuration is invalid or incomplete."""

    pass


class DataError(PipelineError):
    """Data validation or access failed."""

    pass


class CalibrationError(PipelineError):
    """Calibration step failed."""

    pass


class FlaggingError(PipelineError):
    """Flagging operation failed."""

    pass


class PlotError(PipelineError):
    """Plotting operation failed (non-critical)."""

    pass


class WeblogError(PipelineError):
    """Weblog generation failed (non-critical)."""

    pass


class StateError(PipelineError):
    """State management error."""

    pass


class CASAError(PipelineError):
    """CASA task execution failed."""

    def __init__(self, message: str, task_name: str = None, step_name: str = None):
        self.task_name = task_name
        super().__init__(message, step_name)
