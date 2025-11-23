"""
Progress reporting for pipeline execution.

Provides progress bars and time estimates for long-running pipeline operations.
"""

from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
import time

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


class PipelineProgressBar:
    """
    Progress bar for pipeline execution.

    Shows step-by-step progress with time estimates and QA status.
    """

    def __init__(self, steps: List[str], desc: str = "Pipeline Progress", disable: bool = False):
        """
        Initialize progress bar.

        Parameters
        ----------
        steps : list of str
            List of pipeline step names
        desc : str
            Description for progress bar
        disable : bool
            Disable progress bar (for non-interactive environments)
        """
        self.steps = steps
        self.total_steps = len(steps)
        self.current_step = 0
        self.start_time = datetime.now()
        self.step_times = []

        # Create tqdm progress bar if available
        if TQDM_AVAILABLE and not disable:
            self.pbar = tqdm(
                total=self.total_steps,
                desc=desc,
                unit="step",
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}'
            )
        else:
            self.pbar = None

    def update(self, step_name: str, qa_status: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Update progress bar after completing a step.

        Parameters
        ----------
        step_name : str
            Name of completed step
        qa_status : str, optional
            QA status (Pass/Fail/Partial)
        context : dict, optional
            Pipeline context with QA scores
        """
        self.current_step += 1
        self.step_times.append(time.time())

        if self.pbar:
            # Build postfix with current step and QA
            postfix = f"Step: {step_name}"

            if qa_status:
                postfix += f", QA: {qa_status}"
            elif context:
                # Try to extract QA from context
                qa_key = f"QA2_{step_name.replace('EVLA_pipe_', '')}"
                if qa_key in context:
                    postfix += f", QA: {context[qa_key]}"

            self.pbar.set_postfix_str(postfix)
            self.pbar.update(1)
        else:
            # Fallback: simple print
            elapsed = (datetime.now() - self.start_time).total_seconds()
            progress_pct = (self.current_step / self.total_steps) * 100
            status_str = f" [{qa_status}]" if qa_status else ""
            print(f"[{progress_pct:5.1f}%] {self.current_step}/{self.total_steps} - {step_name}{status_str} ({elapsed:.1f}s)")

    def set_description(self, desc: str):
        """Update progress bar description."""
        if self.pbar:
            self.pbar.set_description(desc)

    def close(self):
        """Close progress bar."""
        if self.pbar:
            self.pbar.close()

        # Print summary
        total_time = (datetime.now() - self.start_time).total_seconds()
        avg_time = total_time / max(1, self.current_step)

        print(f"\nPipeline completed: {self.current_step} steps in {total_time:.1f}s (avg: {avg_time:.1f}s/step)")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def run_with_progress(
    steps: List[str],
    step_executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    context: Dict[str, Any],
    desc: str = "Pipeline Progress",
    disable: bool = False
) -> Dict[str, Any]:
    """
    Run pipeline steps with progress bar.

    Parameters
    ----------
    steps : list of str
        List of pipeline step names
    step_executor : callable
        Function to execute each step (e.g., exec_script)
    context : dict
        Initial pipeline context
    desc : str
        Progress bar description
    disable : bool
        Disable progress bar

    Returns
    -------
    dict
        Updated pipeline context

    Examples
    --------
    >>> from evla_pipe import exec_script
    >>> steps = ['EVLA_pipe_import', 'EVLA_pipe_flagall', 'EVLA_pipe_finalcals']
    >>> context = {'SDM_name': 'data.asdm'}
    >>> context = run_with_progress(steps, exec_script, context)
    """
    with PipelineProgressBar(steps, desc=desc, disable=disable) as pbar:
        for step in steps:
            pbar.set_description(f"Running {step}")

            # Execute step
            context = step_executor(step, context)

            # Update progress
            pbar.update(step, context=context)

    return context


def format_time_estimate(seconds: float) -> str:
    """
    Format time estimate in human-readable form.

    Parameters
    ----------
    seconds : float
        Time in seconds

    Returns
    -------
    str
        Formatted time string

    Examples
    --------
    >>> format_time_estimate(65)
    '1m 5s'
    >>> format_time_estimate(3665)
    '1h 1m 5s'
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {mins}m {secs}s"
