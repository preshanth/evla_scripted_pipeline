#!/usr/bin/env python3
"""
EVLA Pipeline CLI with State Management

Enhanced command-line interface with:
- Resume from any checkpoint
- Progress monitoring
- State inspection
- Error recovery
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .state_manager import PipelineStateManager
from .pipeline_executor import PipelineExecutor
from . import __version_str__


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="EVLA Scripted Pipeline with State Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s run dataset.ms
  
  # Resume from checkpoint
  %(prog)s run dataset.ms --resume-from EVLA_pipe_flagall
  
  # Resume automatically from last checkpoint
  %(prog)s run dataset.ms --resume
  
  # Stop at specific step
  %(prog)s run dataset.ms --stop-at EVLA_pipe_calprep
  
  # Enable polarization
  %(prog)s run dataset.ms --enable-polarization
  
  # State management
  %(prog)s status
  %(prog)s checkpoints
  %(prog)s reset
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the pipeline')
    run_parser.add_argument('sdm_name', help='SDM directory name')
    run_parser.add_argument('--skip-hanning', action='store_true',
                           help='Skip Hanning smoothing')
    run_parser.add_argument('--enable-polarization', action='store_true',
                           help='Enable polarization calibration')
    run_parser.add_argument('--disable-plots', action='store_true',
                           help='Disable plotting')
    run_parser.add_argument('--resume', action='store_true',
                           help='Resume from last checkpoint')
    run_parser.add_argument('--resume-from', metavar='STEP',
                           help='Resume from specific step')
    run_parser.add_argument('--stop-at', metavar='STEP',
                           help='Stop at specific step')
    run_parser.add_argument('--state-file', default='pipeline_state.json',
                           help='State file path')
    run_parser.add_argument('--verbose', '-v', action='store_true',
                           help='Enable verbose output')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show pipeline status')
    status_parser.add_argument('--state-file', default='pipeline_state.json',
                              help='State file path')
    
    # Checkpoints command
    checkpoints_parser = subparsers.add_parser('checkpoints', help='List checkpoints')
    checkpoints_parser.add_argument('--state-file', default='pipeline_state.json',
                                   help='State file path')
    checkpoints_parser.add_argument('--detailed', action='store_true',
                                   help='Show detailed checkpoint information')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset pipeline state')
    reset_parser.add_argument('--state-file', default='pipeline_state.json',
                             help='State file path')
    reset_parser.add_argument('--confirm', action='store_true',
                             help='Confirm reset without prompting')
    
    # Steps command
    steps_parser = subparsers.add_parser('steps', help='List available pipeline steps')
    
    # Version
    parser.add_argument('--version', action='version',
                       version=f'EVLA Scripted Pipeline v{__version_str__}')
    
    return parser


def cmd_run(args):
    """Run the pipeline."""
    try:
        executor = PipelineExecutor(args.state_file, args.verbose)
        
        resume_from = None
        if args.resume:
            resume_from = executor.state_manager.get_resume_point()
            if resume_from and args.verbose:
                print(f"Auto-resuming from: {resume_from}")
        elif args.resume_from:
            resume_from = args.resume_from
        
        result = executor.execute_pipeline(
            sdm_name=args.sdm_name,
            skip_hanning=args.skip_hanning,
            enable_polarization=args.enable_polarization,
            enable_plots=not args.disable_plots,
            resume_from=resume_from,
            stop_at=args.stop_at
        )
        
        print("✓ Pipeline completed successfully")
        
        # Show final progress
        progress = executor.get_progress()
        print(f"Final progress: {progress['completed_steps']}/{progress['total_steps']} steps completed")
        
    except KeyboardInterrupt:
        print("\\n⚠ Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Pipeline failed: {e}")
        sys.exit(1)


def cmd_status(args):
    """Show pipeline status."""
    state_manager = PipelineStateManager(args.state_file)
    progress = state_manager.get_pipeline_progress()
    
    print(f"Pipeline Status:")
    print(f"  Version: {state_manager.state.get('pipeline_version', 'unknown')}")
    print(f"  Progress: {progress['completed_steps']}/{progress['total_steps']} steps ({progress['progress_percent']:.1f}%)")
    print(f"  Current step: {progress['current_step'] or 'Not started'}")
    print(f"  Last updated: {progress['last_updated']}")
    
    if state_manager.state['checkpoints']:
        last_checkpoint = state_manager.state['checkpoints'][-1]
        print(f"  Last checkpoint: {last_checkpoint['step_name']} ({last_checkpoint['status']})")
        
        # Check if we can resume
        resume_point = state_manager.get_resume_point()
        if resume_point:
            print(f"  Can resume from: {resume_point}")
        else:
            print(f"  Pipeline appears complete")


def cmd_checkpoints(args):
    """List checkpoints."""
    state_manager = PipelineStateManager(args.state_file)
    checkpoints = state_manager.list_checkpoints()
    
    if not checkpoints:
        print("No checkpoints found")
        return
    
    print(f"Pipeline Checkpoints ({len(checkpoints)} total):")
    print()
    
    for i, cp in enumerate(checkpoints, 1):
        status_icon = "✓" if cp['status'] == 'completed' else "✗"
        print(f"{i:2d}. {status_icon} {cp['step_name']}")
        print(f"     Status: {cp['status']}")
        print(f"     Time: {cp['timestamp']}")
        print(f"     Duration: {cp['duration']:.1f}s")
        
        if args.detailed:
            if cp['error_message']:
                print(f"     Error: {cp['error_message'][:100]}...")
            print(f"     Context keys: {len(cp['context_snapshot'])} items")
        
        print()


def cmd_reset(args):
    """Reset pipeline state."""
    state_file = Path(args.state_file)
    
    if not state_file.exists():
        print(f"No state file found at: {state_file}")
        return
    
    if not args.confirm:
        response = input(f"Are you sure you want to reset pipeline state? (y/N): ")
        if response.lower() != 'y':
            print("Reset cancelled")
            return
    
    state_manager = PipelineStateManager(args.state_file)
    state_manager.reset_state()
    print("✓ Pipeline state reset")


def cmd_steps(args):
    """List available pipeline steps."""
    state_manager = PipelineStateManager()
    
    print("Available Pipeline Steps:")
    print()
    
    for i, step in enumerate(state_manager.pipeline_steps, 1):
        print(f"{i:2d}. {step}")


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'checkpoints':
        cmd_checkpoints(args)
    elif args.command == 'reset':
        cmd_reset(args)
    elif args.command == 'steps':
        cmd_steps(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()