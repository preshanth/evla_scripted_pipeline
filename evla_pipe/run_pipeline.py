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
        help="SDM directory or MS file to process. Can be either 'dataset.ms' or 'dataset.asdm'"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"EVLA Scripted Pipeline v{__version_str__}"
    )

    parser.add_argument(
        "--hanning",
        action="store_true",
        help="Apply Hanning smoothing to visibility data. Recommended for spectral line "
             "observations to reduce Gibbs ringing. Default: disabled for continuum observations"
    )

    parser.add_argument(
        "--polarization",
        action="store_true",
        help="Enable full polarization calibration including cross-hand delays, leakage terms, "
             "and polarization angle calibration. Requires polarization calibrators in the data. "
             "Default: disabled"
    )

    parser.add_argument(
        "--disable-plots",
        action="store_true",
        help="Disable all diagnostic plot generation. Significantly improves performance but "
             "reduces QA capability. Plots are saved to plots/ directory when enabled. "
             "Default: plotting enabled"
    )

    parser.add_argument(
        "--resume-from",
        metavar="STEP",
        help="Resume pipeline execution from a specific step. Useful after fixing errors or "
             "manual intervention. Example: --resume-from EVLA_pipe_finalcals. "
             "Use with checkpointed pipeline state in pipeline_context/"
    )

    parser.add_argument(
        "--skip",
        metavar="STEP",
        action="append",
        help="Skip one or more pipeline steps. Can be specified multiple times. "
             "Example: --skip EVLA_pipe_hanning --skip EVLA_pipe_testBPdcals. "
             "Use with caution as skipping steps may affect calibration quality"
    )

    parser.add_argument(
        "--restore",
        metavar="FILE",
        help="Restore complete pipeline state from a backup file created with --save. "
             "Allows restarting the pipeline from the exact state it was in when the backup "
             "was created. Example: --restore pipeline_backups/backup_20250123.restore"
    )

    parser.add_argument(
        "--save",
        metavar="FILE",
        help="Save current pipeline state to a backup file for later restoration. "
             "Creates a checkpoint that can be restored with --restore. "
             "Example: --save pipeline_backups/my_backup.restore"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose console output showing detailed progress information, "
             "CASA version details, and step-by-step execution status. "
             "All output is always logged to files regardless of this flag"
    )

    parser.add_argument(
        "--show-casa-output",
        action="store_true",
        help="Display CASA task output directly to console. By default, CASA output is "
             "suppressed from console but always saved to log files in logs/ directory. "
             "Enable this for debugging CASA task issues"
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