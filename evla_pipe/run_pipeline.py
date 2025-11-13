#!/usr/bin/env python3
######################################################################
#
# EVLA Pipeline CLI Runner
#
######################################################################

"""
Command line interface for the EVLA scripted pipeline.
"""

import argparse
import traceback
import sys
from evla_pipe import continuum, check_casa_version
from evla_pipe import __version_str__


def create_argument_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="EVLA Scripted Pipeline - Automated calibration pipeline for VLA data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s dataset.ms
  %(prog)s dataset.ms --hanning
  %(prog)s dataset.ms --polarization
  %(prog)s dataset.ms --disable-plots
  %(prog)s dataset.ms --hanning --polarization --disable-plots
  %(prog)s dataset.ms --restore pipeline_backup.restore
  %(prog)s --version
        """
    )
    
    parser.add_argument(
        "sdm_name", 
        nargs="?",
        help="SDM directory name (without .ms extension)"
    )
    
    parser.add_argument(
        "--version", 
        action="version",
        version=f"EVLA Scripted Pipeline v{__version_str__}"
    )
    
    parser.add_argument(
        "--hanning",
        action="store_true",
        help="Enable Hanning smoothing (default: disabled)"
    )
    
    parser.add_argument(
        "--polarization",
        action="store_true",
        help="Enable polarization calibration (default: disabled)"
    )
    
    parser.add_argument(
        "--disable-plots",
        action="store_true",
        help="Disable all plotting (improves performance)"
    )
    
    parser.add_argument(
        "--resume-from",
        metavar="STEP",
        help="Resume pipeline from specific step (e.g., EVLA_pipe_finalcals)"
    )
    
    parser.add_argument(
        "--skip",
        metavar="STEP", 
        action="append",
        help="Skip specific pipeline step(s)"
    )
    
    parser.add_argument(
        "--restore",
        metavar="FILE",
        help="Restore pipeline state from backup file"
    )
    
    parser.add_argument(
        "--save",
        metavar="FILE",
        help="Save pipeline state to backup file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--show-casa-output",
        action="store_true",
        help="Show CASA task output to console (default: suppressed, still goes to log files)"
    )

    return parser


def main():
    """Main entry point for the EVLA pipeline CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    print(f":: EVLA scripted pipeline v{__version_str__}")

    # Set CASA output visibility flag
    if args.show_casa_output:
        import evla_pipe.utils as utils
        utils.SHOW_CASA_OUTPUT = True
        if args.verbose:
            print(":: CASA console output enabled")

    try:
        casa_version = check_casa_version()
        if casa_version and args.verbose:
            print(f":: Using CASA version {'.'.join(str(v) for v in casa_version)}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    if args.restore:
        try:
            pipeline_restore(args.restore)
            print(f":: Restored pipeline state from {args.restore}")
        except Exception as e:
            print(f"Error restoring pipeline state: {e}")
            sys.exit(1)
    
    if not args.sdm_name and not args.restore:
        parser.error("SDM name is required unless restoring from backup")
    
    try:
        result = continuum(
            sdm_name=args.sdm_name,
            skip_hanning=not args.hanning,  # Note: CLI --hanning flag enables it, continuum skip_hanning disables it
            verbose=args.verbose,
            enable_polarization=args.polarization,
            enable_plots=not args.disable_plots,
            resume_from=args.resume_from,
            skip_steps=args.skip or []
        )
            
    except Exception as e:
        print(f"Pipeline error: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    print(":: Pipeline completed successfully")


if __name__ == "__main__":
    main()