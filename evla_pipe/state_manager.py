"""
Modern Pipeline State Management System

This module provides robust state management for the EVLA pipeline with:
- Automatic state saving/restoration
- Checkpoint-based resumption
- JSON-based persistence (more portable than shelve)
- Automatic context tracking
- Step-by-step resumption control
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import traceback


@dataclass
class PipelineCheckpoint:
    """Represents a pipeline checkpoint."""
    step_name: str
    step_index: int
    timestamp: str
    context_snapshot: Dict[str, Any]
    status: str  # 'completed', 'failed', 'running'
    duration: float = 0.0
    error_message: Optional[str] = None


class PipelineStateManager:
    """
    Modern state management for EVLA pipeline.
    
    Features:
    - Automatic checkpointing after each step
    - JSON-based persistence (portable)
    - Resume from any checkpoint
    - Context validation and sanitization
    - Backup management
    """
    
    def __init__(self, state_file: str = "pipeline_state.json", 
                 backup_dir: str = "pipeline_backups"):
        self.state_file = Path(state_file)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Pipeline steps in order
        self.pipeline_steps = [
            "EVLA_pipe_startup",
            "EVLA_pipe_import", 
            "EVLA_pipe_hanning",
            "EVLA_pipe_msinfo",
            "EVLA_pipe_flagall",
            "EVLA_pipe_calprep",
            "EVLA_pipe_priorcals",
            "EVLA_pipe_testBPdcals",
            "EVLA_pipe_flag_baddeformatters",
            "EVLA_pipe_checkflag",
            "EVLA_pipe_semiFinalBPdcals1",
            "EVLA_pipe_checkflag_semiFinal",
            "EVLA_pipe_semiFinalBPdcals1",  # Re-run
            "EVLA_pipe_solint",
            "EVLA_pipe_testgains",
            "EVLA_pipe_fluxgains",
            "EVLA_pipe_fluxboot",
            "EVLA_pipe_finalcals",
            "EVLA_pipe_polcal",  # Optional
            "EVLA_pipe_applycals",
            "EVLA_pipe_targetflag",
            "EVLA_pipe_statwt",
            "EVLA_pipe_plotsummary",
            "EVLA_pipe_filecollect",
            "EVLA_pipe_weblog"
        ]
        
        self.state = {
            "pipeline_version": "2.0.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "current_step": None,
            "current_step_index": -1,
            "checkpoints": [],
            "context": {},
            "configuration": {},
            "metadata": {}
        }
        
        # Load existing state if available
        self.load_state()
    
    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize context for JSON serialization.
        Remove non-serializable objects and large data structures.
        """
        sanitized = {}
        
        # Types that can be safely serialized
        safe_types = (str, int, float, bool, list, dict, type(None))
        
        for key, value in context.items():
            if isinstance(value, safe_types):
                # For dict and list, recursively sanitize
                if isinstance(value, dict):
                    sanitized[key] = self._sanitize_dict(value)
                elif isinstance(value, list):
                    sanitized[key] = self._sanitize_list(value)
                else:
                    sanitized[key] = value
            else:
                # Store type information for non-serializable objects
                sanitized[f"__{key}__type"] = str(type(value))
                sanitized[f"__{key}__repr"] = repr(value)[:200]  # Truncate long representations
        
        return sanitized
    
    def _sanitize_dict(self, d: dict) -> dict:
        """Recursively sanitize dictionary."""
        sanitized = {}
        for k, v in d.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                sanitized[k] = v
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_dict(v)
            elif isinstance(v, list):
                sanitized[k] = self._sanitize_list(v)
            else:
                sanitized[f"__{k}__type"] = str(type(v))
        return sanitized
    
    def _sanitize_list(self, lst: list) -> list:
        """Recursively sanitize list."""
        sanitized = []
        for item in lst:
            if isinstance(item, (str, int, float, bool, type(None))):
                sanitized.append(item)
            elif isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item))
            elif isinstance(item, list):
                sanitized.append(self._sanitize_list(item))
            else:
                sanitized.append({"__type": str(type(item)), "__repr": repr(item)[:100]})
        return sanitized
    
    def save_checkpoint(self, step_name: str, context: Dict[str, Any], 
                       status: str = "completed", duration: float = 0.0,
                       error_message: Optional[str] = None):
        """Save a checkpoint after completing a step."""
        
        step_index = self.pipeline_steps.index(step_name) if step_name in self.pipeline_steps else -1
        
        checkpoint = PipelineCheckpoint(
            step_name=step_name,
            step_index=step_index,
            timestamp=datetime.now().isoformat(),
            context_snapshot=self._sanitize_context(context),
            status=status,
            duration=duration,
            error_message=error_message
        )
        
        self.state["checkpoints"].append(asdict(checkpoint))
        self.state["current_step"] = step_name
        self.state["current_step_index"] = step_index
        self.state["context"] = self._sanitize_context(context)
        self.state["last_updated"] = datetime.now().isoformat()
        
        self.save_state()
        
        # Create backup
        self._create_backup(step_name)
        
        print(f"✓ Checkpoint saved: {step_name} ({status})")
    
    def get_resume_point(self, target_step: Optional[str] = None) -> Optional[str]:
        """
        Determine where to resume pipeline execution.
        
        Args:
            target_step: Specific step to resume from, or None for automatic detection
            
        Returns:
            Step name to resume from, or None if starting from beginning
        """
        if not self.state["checkpoints"]:
            return None
        
        if target_step:
            # Resume from specific step
            if target_step in self.pipeline_steps:
                return target_step
            else:
                raise ValueError(f"Unknown step: {target_step}")
        
        # Find last successful checkpoint
        for checkpoint in reversed(self.state["checkpoints"]):
            if checkpoint["status"] == "completed":
                next_index = checkpoint["step_index"] + 1
                if next_index < len(self.pipeline_steps):
                    return self.pipeline_steps[next_index]
        
        return None
    
    def get_context(self) -> Dict[str, Any]:
        """Get current pipeline context."""
        return self.state["context"].copy()
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all checkpoints."""
        return self.state["checkpoints"]
    
    def save_state(self):
        """Save current state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Could not save state: {e}")
    
    def load_state(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    loaded_state = json.load(f)
                    self.state.update(loaded_state)
                print(f"✓ Loaded pipeline state from {self.state_file}")
            except Exception as e:
                print(f"Warning: Could not load state: {e}")
    
    def _create_backup(self, step_name: str):
        """Create a backup of the current state."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"pipeline_state_{step_name}_{timestamp}.json"
        
        try:
            with open(backup_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Could not create backup: {e}")
    
    def reset_state(self):
        """Reset pipeline state (use with caution)."""
        self.state = {
            "pipeline_version": "2.0.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "current_step": None,
            "current_step_index": -1,
            "checkpoints": [],
            "context": {},
            "configuration": {},
            "metadata": {}
        }
        self.save_state()
        print("✓ Pipeline state reset")
    
    def get_pipeline_progress(self) -> Dict[str, Any]:
        """Get pipeline progress summary."""
        total_steps = len(self.pipeline_steps)
        completed_steps = len([cp for cp in self.state["checkpoints"] if cp["status"] == "completed"])
        
        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "progress_percent": (completed_steps / total_steps) * 100,
            "current_step": self.state["current_step"],
            "current_step_index": self.state["current_step_index"],
            "last_updated": self.state["last_updated"]
        }


# Global state manager instance
_state_manager = None

def get_state_manager(state_file: str = "pipeline_state.json") -> PipelineStateManager:
    """Get or create global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = PipelineStateManager(state_file)
    return _state_manager


def save_pipeline_checkpoint(step_name: str, context: Dict[str, Any], 
                           status: str = "completed", duration: float = 0.0,
                           error_message: Optional[str] = None):
    """Convenience function to save a checkpoint."""
    state_manager = get_state_manager()
    state_manager.save_checkpoint(step_name, context, status, duration, error_message)


def get_pipeline_context() -> Dict[str, Any]:
    """Convenience function to get current context."""
    state_manager = get_state_manager()
    return state_manager.get_context()


def get_resume_point(target_step: Optional[str] = None) -> Optional[str]:
    """Convenience function to get resume point."""
    state_manager = get_state_manager()
    return state_manager.get_resume_point(target_step)