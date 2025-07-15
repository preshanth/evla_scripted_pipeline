"""
Modern Pipeline Executor with State Management

This module provides a modern execution framework for the EVLA pipeline with:
- Automatic state management and checkpointing
- Resume from any step
- Error handling and recovery
- Progress tracking
- Context isolation
"""

import time
import traceback
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from evla_pipe.state_manager import PipelineStateManager, save_pipeline_checkpoint
from evla_pipe import __version_str__


class PipelineExecutor:
    """
    Modern pipeline executor with state management.
    
    Features:
    - Automatic checkpointing after each step
    - Resume from any step
    - Error handling and recovery
    - Progress tracking
    - Context validation
    """
    
    def __init__(self, state_file: str = "pipeline_state.json", verbose: bool = False):
        self.state_manager = PipelineStateManager(state_file)
        self.verbose = verbose
        
        # Step execution mapping
        self.step_functions = {
            "EVLA_pipe_startup": self._exec_startup,
            "EVLA_pipe_import": self._exec_import,
            "EVLA_pipe_hanning": self._exec_hanning,
            "EVLA_pipe_msinfo": self._exec_msinfo,
            "EVLA_pipe_flagall": self._exec_flagall,
            "EVLA_pipe_calprep": self._exec_calprep,
            "EVLA_pipe_priorcals": self._exec_priorcals,
            "EVLA_pipe_testBPdcals": self._exec_testBPdcals,
            "EVLA_pipe_flag_baddeformatters": self._exec_flag_baddeformatters,
            "EVLA_pipe_checkflag": self._exec_checkflag,
            "EVLA_pipe_semiFinalBPdcals1": self._exec_semiFinalBPdcals1,
            "EVLA_pipe_checkflag_semiFinal": self._exec_checkflag_semiFinal,
            "EVLA_pipe_solint": self._exec_solint,
            "EVLA_pipe_testgains": self._exec_testgains,
            "EVLA_pipe_fluxgains": self._exec_fluxgains,
            "EVLA_pipe_fluxboot": self._exec_fluxboot,
            "EVLA_pipe_finalcals": self._exec_finalcals,
            "EVLA_pipe_polcal": self._exec_polcal,
            "EVLA_pipe_applycals": self._exec_applycals,
            "EVLA_pipe_targetflag": self._exec_targetflag,
            "EVLA_pipe_statwt": self._exec_statwt,
            "EVLA_pipe_plotsummary": self._exec_plotsummary,
            "EVLA_pipe_filecollect": self._exec_filecollect,
            "EVLA_pipe_weblog": self._exec_weblog
        }
    
    def execute_pipeline(self, sdm_name: str, skip_hanning: bool = False,
                        enable_polarization: bool = False, enable_plots: bool = True,
                        resume_from: Optional[str] = None, stop_at: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the full pipeline with state management.
        
        Args:
            sdm_name: SDM directory name
            skip_hanning: Skip Hanning smoothing
            enable_polarization: Enable polarization calibration
            enable_plots: Enable plotting
            resume_from: Step to resume from (None for auto-detection)
            stop_at: Step to stop at (None for full pipeline)
            
        Returns:
            Final pipeline context
        """
        
        if self.verbose:
            print(f":: EVLA scripted pipeline v{__version_str__} with modern state management")
        
        # Initialize or restore context
        if resume_from or self.state_manager.state["checkpoints"]:
            context = self.state_manager.get_context()
            if self.verbose:
                print(f":: Resuming from existing state")
        else:
            context = {
                "SDM_name": sdm_name,
                "do_pol": enable_polarization,
                "enable_plots": enable_plots,
                "skip_hanning": skip_hanning
            }
            if self.verbose:
                print(f":: Starting new pipeline execution")
        
        # Determine starting point
        start_step = resume_from or self.state_manager.get_resume_point()
        if start_step:
            start_index = self.state_manager.pipeline_steps.index(start_step)
            if self.verbose:
                print(f":: Resuming from step: {start_step}")
        else:
            start_index = 0
            if self.verbose:
                print(f":: Starting from beginning")
        
        # Determine stopping point
        if stop_at:
            stop_index = self.state_manager.pipeline_steps.index(stop_at)
        else:
            stop_index = len(self.state_manager.pipeline_steps) - 1
        
        # Execute pipeline steps
        for i in range(start_index, stop_index + 1):
            step_name = self.state_manager.pipeline_steps[i]
            
            # Skip steps based on configuration
            if step_name == "EVLA_pipe_hanning" and skip_hanning:
                if self.verbose:
                    print(f":: Skipping {step_name} (disabled)")
                continue
            
            if step_name == "EVLA_pipe_polcal" and not enable_polarization:
                if self.verbose:
                    print(f":: Skipping {step_name} (disabled)")
                continue
            
            # Execute step
            try:
                start_time = time.time()
                if self.verbose:
                    print(f":: Executing {step_name}")
                
                context = self._execute_step(step_name, context)
                
                duration = time.time() - start_time
                save_pipeline_checkpoint(step_name, context, "completed", duration)
                
                if self.verbose:
                    print(f":: Completed {step_name} in {duration:.1f}s")
                
            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"{str(e)}\\n{traceback.format_exc()}"
                save_pipeline_checkpoint(step_name, context, "failed", duration, error_msg)
                
                if self.verbose:
                    print(f":: Failed {step_name} after {duration:.1f}s: {e}")
                
                raise
        
        if self.verbose:
            progress = self.state_manager.get_pipeline_progress()
            print(f":: Pipeline progress: {progress['completed_steps']}/{progress['total_steps']} steps completed")
        
        return context
    
    def _execute_step(self, step_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single pipeline step."""
        
        if step_name in self.step_functions:
            return self.step_functions[step_name](context)
        else:
            # Fallback to original exec_script method
            from evla_pipe import exec_script
            exec_script(step_name, context)
            return context
    
    def _exec_startup(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute startup step."""
        from evla_pipe.EVLA_pipe_startup import EVLA_pipe_startup
        return EVLA_pipe_startup(context)
    
    def _exec_import(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute import step."""
        from evla_pipe.EVLA_pipe_import import EVLA_pipe_import
        return EVLA_pipe_import(context)
    
    def _exec_hanning(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hanning step."""
        from evla_pipe.EVLA_pipe_hanning import EVLA_pipe_hanning
        return EVLA_pipe_hanning(context)
    
    def _exec_msinfo(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute msinfo step."""
        from evla_pipe.EVLA_pipe_msinfo import EVLA_pipe_msinfo
        return EVLA_pipe_msinfo(context)
    
    def _exec_flagall(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute flagall step."""
        from evla_pipe.EVLA_pipe_flagall import EVLA_pipe_flagall
        return EVLA_pipe_flagall(context)
    
    def _exec_calprep(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute calprep step."""
        from evla_pipe.EVLA_pipe_calprep import EVLA_pipe_calprep
        return EVLA_pipe_calprep(context)
    
    def _exec_priorcals(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute priorcals step."""
        from evla_pipe.EVLA_pipe_priorcals import EVLA_pipe_priorcals
        return EVLA_pipe_priorcals(context)
    
    def _exec_testBPdcals(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute testBPdcals step."""
        from evla_pipe.EVLA_pipe_testBPdcals import EVLA_pipe_testBPdcals
        return EVLA_pipe_testBPdcals(context)
    
    def _exec_flag_baddeformatters(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute flag_baddeformatters step."""
        from evla_pipe.EVLA_pipe_flag_baddeformatters import EVLA_pipe_flag_baddeformatters
        return EVLA_pipe_flag_baddeformatters(context)
    
    def _exec_checkflag(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute checkflag step."""
        from evla_pipe.EVLA_pipe_checkflag import EVLA_pipe_checkflag
        return EVLA_pipe_checkflag(context)
    
    def _exec_semiFinalBPdcals1(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute semiFinalBPdcals1 step."""
        from evla_pipe.EVLA_pipe_semiFinalBPdcals1 import EVLA_pipe_semiFinalBPdcals1
        return EVLA_pipe_semiFinalBPdcals1(context)
    
    def _exec_checkflag_semiFinal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute checkflag_semiFinal step."""
        from evla_pipe.EVLA_pipe_checkflag_semiFinal import EVLA_pipe_checkflag_semiFinal
        return EVLA_pipe_checkflag_semiFinal(context)
    
    def _exec_solint(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute solint step."""
        from evla_pipe.EVLA_pipe_solint import EVLA_pipe_solint
        return EVLA_pipe_solint(context)
    
    def _exec_testgains(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute testgains step."""
        from evla_pipe.EVLA_pipe_testgains import EVLA_pipe_testgains
        return EVLA_pipe_testgains(context)
    
    def _exec_fluxgains(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fluxgains step."""
        from evla_pipe.EVLA_pipe_fluxgains import EVLA_pipe_fluxgains
        return EVLA_pipe_fluxgains(context)
    
    def _exec_fluxboot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fluxboot step."""
        from evla_pipe.EVLA_pipe_fluxboot import EVLA_pipe_fluxboot
        return EVLA_pipe_fluxboot(context)
    
    def _exec_finalcals(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute finalcals step."""
        from evla_pipe.EVLA_pipe_finalcals import EVLA_pipe_finalcals
        return EVLA_pipe_finalcals(context)
    
    def _exec_polcal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute polcal step."""
        from evla_pipe.EVLA_pipe_polcal import EVLA_pipe_polcal
        return EVLA_pipe_polcal(context)
    
    def _exec_applycals(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute applycals step."""
        from evla_pipe.EVLA_pipe_applycals import EVLA_pipe_applycals
        return EVLA_pipe_applycals(context)
    
    def _exec_targetflag(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute targetflag step."""
        from evla_pipe.EVLA_pipe_targetflag import EVLA_pipe_targetflag
        return EVLA_pipe_targetflag(context)
    
    def _exec_statwt(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute statwt step."""
        from evla_pipe.EVLA_pipe_statwt import EVLA_pipe_statwt
        return EVLA_pipe_statwt(context)
    
    def _exec_plotsummary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plotsummary step."""
        from evla_pipe.EVLA_pipe_plotsummary import EVLA_pipe_plotsummary
        return EVLA_pipe_plotsummary(context)
    
    def _exec_filecollect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute filecollect step."""
        from evla_pipe.EVLA_pipe_filecollect import EVLA_pipe_filecollect
        return EVLA_pipe_filecollect(context)
    
    def _exec_weblog(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute weblog step."""
        from evla_pipe.modern_weblog import EVLA_pipe_modern_weblog
        return EVLA_pipe_modern_weblog(context)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current pipeline progress."""
        return self.state_manager.get_pipeline_progress()
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all checkpoints."""
        return self.state_manager.list_checkpoints()
    
    def reset_state(self):
        """Reset pipeline state."""
        self.state_manager.reset_state()


def execute_pipeline_with_state_management(sdm_name: str, skip_hanning: bool = False,
                                         enable_polarization: bool = False, enable_plots: bool = True,
                                         resume_from: Optional[str] = None, stop_at: Optional[str] = None,
                                         verbose: bool = False) -> Dict[str, Any]:
    """
    Convenience function to execute pipeline with state management.
    
    Args:
        sdm_name: SDM directory name
        skip_hanning: Skip Hanning smoothing
        enable_polarization: Enable polarization calibration
        enable_plots: Enable plotting
        resume_from: Step to resume from (None for auto-detection)
        stop_at: Step to stop at (None for full pipeline)
        verbose: Enable verbose output
        
    Returns:
        Final pipeline context
    """
    executor = PipelineExecutor(verbose=verbose)
    return executor.execute_pipeline(
        sdm_name=sdm_name,
        skip_hanning=skip_hanning,
        enable_polarization=enable_polarization,
        enable_plots=enable_plots,
        resume_from=resume_from,
        stop_at=stop_at
    )