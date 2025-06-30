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
import sys
from . import continuum, check_casa_version, pipeline_save, pipeline_restore
from . import __version_str__


def create_argument_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="EVLA Scripted Pipeline - Automated calibration pipeline for VLA data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s dataset.ms
  %(prog)s dataset.ms --skip-hanning
  %(prog)s dataset.ms --enable-polarization
  %(prog)s dataset.ms --skip-hanning --enable-polarization
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
        "--skip-hanning",
        action="store_true",
        help="Skip Hanning smoothing step (recommended for spectral line projects)"
    )
    
    parser.add_argument(
        "--enable-polarization",
        action="store_true",
        help="Enable polarization calibration"
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
    
    return parser


def main():
    """Main entry point for the EVLA pipeline CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    print(f":: EVLA scripted pipeline v{__version_str__}")
    
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
            skip_hanning=args.skip_hanning,
            verbose=args.verbose,
            enable_polarization=args.enable_polarization
        )
        
        if args.save:
            pipeline_save(args.save)
            print(f":: Saved pipeline state to {args.save}")
            
    except Exception as e:
        print(f"Pipeline error: {e}")
        sys.exit(1)
    
    print(":: Pipeline completed successfully")


if __name__ == "__main__":
    main()