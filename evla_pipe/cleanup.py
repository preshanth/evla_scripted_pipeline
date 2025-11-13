"""
EVLA Pipeline Cleanup Utility

This module provides functions to clean up pipeline-generated files and directories.
Can be used programmatically or via command line.

Usage:
    python -m evla_pipe.cleanup [--ms] [--all] [directory]

    From Python:
    >>> from evla_pipe.cleanup import cleanup_pipeline_products
    >>> cleanup_pipeline_products('.', remove_ms=False)
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional


# Pipeline-generated directories
PIPELINE_DIRECTORIES = [
    'logs',
    'pipeline_context',
    'final_caltables',
    'intermediate_caltables',
    'test_caltables',
    'plots',
    'weblog',
    'measurement_sets',
    'pipeline_backups',
]

# Pipeline-generated file patterns (glob patterns)
PIPELINE_FILE_PATTERNS = [
    '*.flagversions',
    '*.log',
    '*.last',
    '*.restored',
    'pipeline_state.json',
    'calibrators.ms',
    '*.flagonline.txt',
]

# Calibration table patterns
CALTABLE_PATTERNS = [
    '*.cal',
    '*.gcal',
    '*.bcal',
    '*.kcal',
    '*.Df',
    '*.Xf',
    '*.testBPcal.*',
    '*.testdelay*',
    '*.testBPdinitialgain*',
    '*.testgain*',
    '*.semiFinaldelayinitialgain*',
    '*.semiFinaldelay*',
    '*.semiFinalBPinitialgain*',
    '*.semiFinalBP*',
    '*.averagephasegain*',
    '*.finalampgaincal*',
    '*.finalphasegaincal*',
    '*.finalBPcal*',
    '*.finaldelay*',
]


def get_measurement_sets(directory: Path) -> List[Path]:
    """
    Find all measurement sets in a directory.

    Parameters
    ----------
    directory : Path
        Directory to search

    Returns
    -------
    list of Path
        List of .ms directories found
    """
    ms_list = []

    # Look for .ms directories
    for item in directory.iterdir():
        if item.is_dir() and item.suffix == '.ms':
            ms_list.append(item)

    return ms_list


def remove_path(path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Remove a file or directory.

    Parameters
    ----------
    path : Path
        Path to remove
    dry_run : bool
        If True, only report what would be deleted

    Returns
    -------
    tuple of (bool, str)
        (success, message)
    """
    if not path.exists():
        return (False, f"Does not exist: {path}")

    if dry_run:
        if path.is_dir():
            return (True, f"Would remove directory: {path}")
        else:
            return (True, f"Would remove file: {path}")

    try:
        if path.is_dir():
            shutil.rmtree(path)
            return (True, f"Removed directory: {path}")
        else:
            path.unlink()
            return (True, f"Removed file: {path}")
    except Exception as e:
        return (False, f"Error removing {path}: {e}")


def cleanup_pipeline_products(
    directory: str = '.',
    remove_ms: bool = False,
    remove_caltables: bool = True,
    dry_run: bool = False,
    verbose: bool = True
) -> Tuple[int, int]:
    """
    Clean up pipeline-generated files and directories.

    Parameters
    ----------
    directory : str
        Directory to clean (default: current directory)
    remove_ms : bool
        If True, also remove measurement sets (default: False)
    remove_caltables : bool
        If True, remove calibration tables (default: True)
    dry_run : bool
        If True, only report what would be deleted (default: False)
    verbose : bool
        If True, print detailed messages (default: True)

    Returns
    -------
    tuple of (int, int)
        (number_removed, number_failed)
    """
    work_dir = Path(directory).resolve()

    if not work_dir.exists():
        print(f"Error: Directory does not exist: {work_dir}")
        return (0, 0)

    if not work_dir.is_dir():
        print(f"Error: Not a directory: {work_dir}")
        return (0, 0)

    print(f"Cleaning pipeline products in: {work_dir}")
    if dry_run:
        print("DRY RUN - nothing will be deleted")
    print()

    removed_count = 0
    failed_count = 0

    # Remove pipeline directories
    if verbose:
        print("Removing pipeline directories...")
    for dirname in PIPELINE_DIRECTORIES:
        dirpath = work_dir / dirname
        success, msg = remove_path(dirpath, dry_run)
        if success:
            removed_count += 1
            if verbose:
                print(f"  {msg}")
        elif dirpath.exists():
            failed_count += 1
            if verbose:
                print(f"  {msg}")

    # Remove pipeline files
    if verbose:
        print("\nRemoving pipeline files...")
    for pattern in PIPELINE_FILE_PATTERNS:
        for filepath in work_dir.glob(pattern):
            success, msg = remove_path(filepath, dry_run)
            if success:
                removed_count += 1
                if verbose:
                    print(f"  {msg}")
            else:
                failed_count += 1
                if verbose:
                    print(f"  {msg}")

    # Remove calibration tables
    if remove_caltables:
        if verbose:
            print("\nRemoving calibration tables...")
        for pattern in CALTABLE_PATTERNS:
            for filepath in work_dir.glob(pattern):
                success, msg = remove_path(filepath, dry_run)
                if success:
                    removed_count += 1
                    if verbose:
                        print(f"  {msg}")
                else:
                    failed_count += 1
                    if verbose:
                        print(f"  {msg}")

    # Remove measurement sets
    if remove_ms:
        if verbose:
            print("\nRemoving measurement sets...")
        ms_list = get_measurement_sets(work_dir)
        for ms_path in ms_list:
            success, msg = remove_path(ms_path, dry_run)
            if success:
                removed_count += 1
                if verbose:
                    print(f"  {msg}")
            else:
                failed_count += 1
                if verbose:
                    print(f"  {msg}")

    # Summary
    print(f"\n{'=' * 60}")
    if dry_run:
        print(f"Would remove: {removed_count} items")
    else:
        print(f"Removed: {removed_count} items")

    if failed_count > 0:
        print(f"Failed: {failed_count} items")

    return (removed_count, failed_count)


def main():
    """Command-line interface for cleanup utility."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean up EVLA pipeline-generated files and directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Clean current directory (keeps MS)
  %(prog)s --ms               # Clean current directory (remove MS too)
  %(prog)s --dry-run          # Show what would be deleted
  %(prog)s /path/to/data      # Clean specific directory
  %(prog)s --all              # Remove everything including MS
  %(prog)s --no-caltables     # Keep calibration tables
        """
    )

    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory to clean (default: current directory)'
    )

    parser.add_argument(
        '--ms',
        action='store_true',
        help='Also remove measurement sets (.ms directories)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Remove everything including measurement sets (same as --ms)'
    )

    parser.add_argument(
        '--no-caltables',
        action='store_true',
        help='Do not remove calibration tables'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Only show summary, not individual files'
    )

    args = parser.parse_args()

    # Determine whether to remove MS
    remove_ms = args.ms or args.all

    # Determine whether to remove caltables
    remove_caltables = not args.no_caltables

    # Run cleanup
    removed, failed = cleanup_pipeline_products(
        directory=args.directory,
        remove_ms=remove_ms,
        remove_caltables=remove_caltables,
        dry_run=args.dry_run,
        verbose=not args.quiet
    )

    # Exit with error code if any failed
    if failed > 0:
        exit(1)
    else:
        exit(0)


if __name__ == '__main__':
    main()
