"""
Incremental Pipeline Launcher for EVLA Data Processing

This launcher allows incremental development and testing of the modernized
EVLA pipeline. Initially focused on flagging stages, then can be extended
step by step.

Features:
- Save/resume context at any point
- Incremental step addition
- Isolated testing environment
- JSON-based state management
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

from evla_pipe import exec_script, __version_str__
from evla_pipe.import_data import perform_data_import
from evla_pipe.metadata_extraction import perform_metadata_extraction
from evla_pipe.flagging import apply_stage1_flagging
from evla_pipe.utils import logprint


class PipelineLauncher:
    """Incremental pipeline launcher with save/resume functionality."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.context = {}
        self.context_file = "launcher_context.json"
        
    def log(self, message: str):
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f":: {message}")
        logprint(f"LAUNCHER: {message}", logfileout="logs/launcher.log")
        
    def save_context(self, filename: Optional[str] = None, stage: Optional[str] = None) -> str:
        """
        Save current context to JSON file with resumability information.
        
        Parameters
        ----------
        filename : str, optional
            Output filename. If None, uses default context file.
        stage : str, optional
            Current pipeline stage for resume capability
        """
        if filename is None:
            filename = self.context_file
            
        # Add resumability metadata
        resume_context = self.context.copy()
        resume_context["_pipeline_metadata"] = {
            "last_saved_stage": stage,
            "save_timestamp": time.time(),
            "pipeline_version": "2025.1",
            "context_file": str(filename),
            "resumable_stages": self._get_resumable_stages()
        }
            
        # Sanitize context for JSON serialization
        clean_context = {}
        skipped_keys = []
        
        for key, value in resume_context.items():
            try:
                json.dumps(value)  # Test if serializable
                clean_context[key] = value
            except (TypeError, ValueError):
                # Skip non-serializable values but log them
                skipped_keys.append(key)
                
        if skipped_keys:
            self.log(f"Skipping non-serializable context keys: {', '.join(skipped_keys)}")
            # Store list of skipped keys for debugging
            clean_context["_skipped_keys"] = skipped_keys
                
        with open(filename, 'w') as f:
            json.dump(clean_context, f, indent=2, sort_keys=True)
            
        self.log(f"Context saved to {filename}")
        if stage:
            self.log(f"Pipeline can be resumed from stage: {stage}")
            
        return filename
        
    def _get_resumable_stages(self) -> list[str]:
        """Get list of stages that can be resumed from current context."""
        stages = []
        
        # Check completion status of each stage
        stage_checks = {
            "import": "step_import_complete",
            "metadata": "step_metadata_complete", 
            "flagging": "step_stage1_flagging_complete",
            "split_calibrators": "step_calibrators_split_complete",
            "precalibration": "step_precalibration_complete"
        }
        
        for stage, check_key in stage_checks.items():
            if not self.context.get(check_key, False):
                stages.append(stage)
                
        return stages
        
    def load_context(self, filename: Optional[str] = None) -> bool:
        """
        Load context from JSON file with resumability validation.
        
        Parameters
        ----------
        filename : str, optional
            Context file to load. If None, uses default.
            
        Returns
        -------
        bool
            True if context loaded successfully
        """
        if filename is None:
            filename = self.context_file
            
        if not Path(filename).exists():
            self.log(f"Context file {filename} not found")
            return False
            
        try:
            with open(filename, 'r') as f:
                self.context = json.load(f)
                
            # Validate and log resumability information
            self._validate_loaded_context()
            
            self.log(f"Context loaded from {filename}")
            return True
            
        except Exception as e:
            self.log(f"Error loading context from {filename}: {e}")
            return False
            
    def _validate_loaded_context(self):
        """Validate loaded context and report resumability status."""
        metadata = self.context.get("_pipeline_metadata", {})
        
        if metadata:
            last_stage = metadata.get("last_saved_stage", "unknown")
            save_time = metadata.get("save_timestamp", 0)
            resumable_stages = metadata.get("resumable_stages", [])
            
            import datetime
            save_date = datetime.datetime.fromtimestamp(save_time).strftime("%Y-%m-%d %H:%M:%S")
            
            self.log(f"Context from stage '{last_stage}' (saved: {save_date})")
            if resumable_stages:
                self.log(f"Can resume from stages: {', '.join(resumable_stages)}")
            else:
                self.log("Pipeline appears to be complete")
        
        # Check for data files that should exist
        self._validate_data_files()
        
    def _validate_data_files(self):
        """Validate that expected data files exist for resumability."""
        missing_files = []
        
        # Check for MS file
        msname = self.context.get("msname")
        if msname and not Path(msname).exists():
            missing_files.append(f"Main MS: {msname}")
            
        # Check for calibrators.ms if it should exist
        if self.context.get("step_calibrators_split_complete", False):
            cal_ms = self.context.get("calibrators_ms", "calibrators.ms")
            if not Path(cal_ms).exists():
                missing_files.append(f"Calibrators MS: {cal_ms}")
                
        if missing_files:
            self.log(f"WARNING: Missing expected files for resume: {'; '.join(missing_files)}")
        else:
            self.log("All expected data files found for resumability")
            
    def step_import_with_hanning(self, apply_hanning: bool = False):
        """Step 1: Data import with optional Hanning smoothing."""
        self.log("=== Step 1: Data Import with Optional Hanning ===")
        try:
            self.context = perform_data_import(self.context, apply_hanning)
            self.context["step_import_complete"] = True
            self.log("Data import completed successfully")
        except Exception as e:
            self.log(f"Data import failed: {e}")
            raise
            
    def step_metadata_extraction(self):
        """Step 2: MS metadata extraction only."""
        self.log("=== Step 2: MS Metadata Extraction ===")
        try:
            from evla_pipe.metadata_extraction import extract_ms_metadata, identify_calibrators
            self.context = extract_ms_metadata(self.context)
            self.context = identify_calibrators(self.context)
            self.context["step_metadata_complete"] = True
            self.log("MS metadata extraction completed successfully")
        except Exception as e:
            self.log(f"MS metadata extraction failed: {e}")
            raise
            
    def step_stage1_flagging(self):
        """Step 3: Initial consolidated flagging on full MS."""
        self.log("=== Step 3: Initial Consolidated Flagging ===")
        try:
            self.context = apply_stage1_flagging(self.context)
            self.context["step_stage1_flagging_complete"] = True
            self.log("Stage 1 flagging completed successfully")
        except Exception as e:
            self.log(f"Stage 1 flagging failed: {e}")
            raise
            
    def step_split_calibrators(self):
        """Step 4: Split calibrators from flagged MS."""
        self.log("=== Step 4: Split Calibrators ===")
        try:
            from evla_pipe.metadata_extraction import split_calibrators
            self.context = split_calibrators(self.context)
            self.context["step_calibrators_split_complete"] = True
            self.log("Calibrator splitting completed successfully")
        except Exception as e:
            self.log(f"Calibrator splitting failed: {e}")
            raise
            
    def step_precalibration(self):
        """Step 5: Pre-calibration setup and setjy."""
        self.log("=== Step 5: Pre-calibration Setup ===")
        try:
            from evla_pipe.precalibration import perform_precalibration_setup
            self.context = perform_precalibration_setup(self.context)
            self.context["step_precalibration_complete"] = True
            self.log("Pre-calibration setup completed successfully")
        except Exception as e:
            self.log(f"Pre-calibration setup failed: {e}")
            raise
            
    def run_basic_pipeline(self, sdm_name: str, apply_hanning: bool = False):
        """
        Run the basic pipeline with optimal flagging and calibrator workflow.
        
        Pipeline order:
        1. Import + Hanning
        2. Metadata extraction  
        3. Initial flagging (full MS)
        4. Split calibrators (clean)
        5. Pre-calibration setup
        """
        self.log(f"Starting basic pipeline for {sdm_name}")
        self.context["SDM_name"] = sdm_name
        
        try:
            # Step 1: Import with optional Hanning
            if not self.context.get("step_import_complete", False):
                self.step_import_with_hanning(apply_hanning)
                self.save_context(stage="after_import")
                
            # Step 2: MS metadata extraction
            if not self.context.get("step_metadata_complete", False):
                self.step_metadata_extraction()
                self.save_context(stage="after_metadata")
                
            # Step 3: Initial consolidated flagging
            if not self.context.get("step_stage1_flagging_complete", False):
                self.step_stage1_flagging()
                self.save_context(stage="after_flagging")
                
            # Step 4: Split calibrators from flagged MS
            if not self.context.get("step_calibrators_split_complete", False):
                self.step_split_calibrators()
                self.save_context(stage="after_split_calibrators")
                
            # Step 5: Pre-calibration setup and setjy
            if not self.context.get("step_precalibration_complete", False):
                self.step_precalibration()
                self.save_context(stage="after_precalibration")
                
            self.log("Basic pipeline completed successfully!")
            return self.context
            
        except Exception as e:
            self.log(f"Pipeline failed: {e}")
            self.save_context("launcher_context_error.json")
            raise
            
    def resume_pipeline(self, context_file: Optional[str] = None):
        """Resume pipeline from saved context."""
        self.log("Resuming pipeline from saved context")
        
        if not self.load_context(context_file):
            raise RuntimeError("Failed to load context for resume")
            
        sdm_name = self.context.get("SDM_name")
        if not sdm_name:
            raise RuntimeError("No SDM_name found in context")
            
        apply_hanning = self.context.get("hanning_applied", False)
        
        # Continue from where we left off
        return self.run_basic_pipeline(sdm_name, apply_hanning)
        
    def show_status(self, context_file: Optional[str] = None):
        """Show current pipeline status."""
        if not self.load_context(context_file):
            print("No context file found")
            return
            
        print("=== Pipeline Status ===")
        print(f"SDM Name: {self.context.get('SDM_name', 'Not set')}")
        print(f"MS Name: {self.context.get('msname', 'Not set')}")
        print(f"Data Type: {self.context.get('data_type', 'Unknown')}")
        
        steps = [
            ("step_import_complete", "Import + Hanning"),
            ("step_metadata_complete", "Metadata + Calibrators"),
            ("step_stage1_flagging_complete", "Stage 1 Flagging"),
        ]
        
        for step_key, step_name in steps:
            status = "✓" if self.context.get(step_key, False) else "✗"
            print(f"{status} {step_name}")
            
        # Show calibrator information if available
        if self.context.get("step_metadata_complete", False):
            print("\n=== Calibrator Information ===")
            cal_fields = self.context.get("calibrator_fields", {})
            if cal_fields:
                print(f"Flux calibrators: {len(cal_fields.get('flux', []))}")
                print(f"Bandpass calibrators: {len(cal_fields.get('bandpass', []))}")
                print(f"Delay calibrators: {len(cal_fields.get('delay', []))}")
                print(f"Phase calibrators: {len(cal_fields.get('phase', []))}")
                print(f"Total calibrator fields: {len(cal_fields.get('all_calibrators', []))}")
                
                # Show if calibrators.ms was created
                if self.context.get("calibrators_ms_created", False):
                    cal_ms = self.context.get("calibrators_ms", "calibrators.ms")
                    cal_scans = self.context.get("calibrators_ms_scans", 0)
                    print(f"✓ Created {cal_ms} with {cal_scans} scans")
                else:
                    print("✗ calibrators.ms not created")
            else:
                print("No calibrator information available")
        
        # Show basic MS information if available
        basic_info = self.context.get("ms_basic_info", {})
        if basic_info:
            print("\n=== MS Information ===")
            print(f"Spectral windows: {basic_info.get('nspw', 'Unknown')}")
            print(f"Fields: {basic_info.get('nfields', 'Unknown')}")
            print(f"Antennas: {basic_info.get('nantennas', 'Unknown')}")
            print(f"Scans: {basic_info.get('nscans', 'Unknown')}")
            print(f"EVLA Band: {self.context.get('EVLA_band', 'Unknown')}")
            
        # Show flagging progression if available
        progression = self.context.get("flagging_progression", [])
        if progression:
            print("\n=== Flagging Progression ===")
            for i, summary in enumerate(progression):
                operation = summary.get("operation", "unknown")
                flagged_fraction = summary.get("flagged_fraction", 0.0)
                flags_added = summary.get("flags_added", 0)
                
                if i == 0:
                    print(f"{i+1}. {operation}: {flagged_fraction:.4f} flagged (initial)")
                else:
                    print(f"{i+1}. {operation}: {flagged_fraction:.4f} flagged (+{flags_added} flags)")
                    
                # Show warnings if present
                if summary.get("over_flagging_warning", False):
                    print(f"    ⚠️  WARNING: Possible over-flagging detected!")
        else:
            print("\n=== Flagging Progression ===")
            print("No flagging progression data available")


def create_argument_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="EVLA Pipeline Launcher - Import + Flagging Development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run dataset.asdm                   # Run basic pipeline
  %(prog)s run dataset.asdm --hanning         # Include Hanning smoothing
  %(prog)s resume                            # Resume from saved context
  %(prog)s resume --context-file my.json     # Resume from specific file
  %(prog)s status                            # Show pipeline status
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the basic pipeline')
    run_parser.add_argument('sdm_name', help='SDM directory name (e.g., dataset.asdm)')
    run_parser.add_argument('--hanning', action='store_true', 
                           help='Apply Hanning smoothing after import')
    
    # Resume command
    resume_parser = subparsers.add_parser('resume', help='Resume from saved context')
    resume_parser.add_argument('--context-file', help='Context file to resume from')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show pipeline status')
    status_parser.add_argument('--context-file', help='Context file to check')
    
    # Global options
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--version', action='version',
                       version=f'EVLA Pipeline Launcher v{__version_str__}')
    
    return parser


def main():
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    launcher = PipelineLauncher(verbose=args.verbose)
    
    try:
        if args.command == 'run':
            launcher.run_basic_pipeline(args.sdm_name, args.hanning)
            
        elif args.command == 'resume':
            launcher.resume_pipeline(args.context_file)
            
        elif args.command == 'status':
            launcher.show_status(args.context_file)
            
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)
        
    print("Command completed successfully")


if __name__ == "__main__":
    main()