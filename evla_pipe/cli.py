"""
Command-line interface for the EVLA scripted pipeline.

Usage
-----
    evla-pipeline <sdm>
    evla-pipeline <sdm> --polarization
    evla-pipeline <sdm> --hanning
    evla-pipeline <sdm> --resume-from <stage>
    evla-pipeline <sdm> --skip <stage>          # repeatable
    evla-pipeline --version
"""

import argparse
import logging
import sys

from evla_pipe import __version_str__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evla-pipeline",
        description="EVLA scripted pipeline — automated VLA continuum calibration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  evla-pipeline dataset.asdm
  evla-pipeline dataset.asdm --polarization
  evla-pipeline dataset.asdm --hanning
  evla-pipeline dataset.asdm --resume-from run_fluxboot
  evla-pipeline dataset.asdm --skip run_final_flags
        """,
    )

    parser.add_argument("sdm_name", help="path to the ASDM/SDM directory")

    parser.add_argument(
        "--polarization",
        action="store_true",
        help="enable polarization calibration (KCROSS + Df)",
    )
    parser.add_argument(
        "--hanning",
        action="store_true",
        help="apply Hanning smoothing after import",
    )
    parser.add_argument(
        "--workdir",
        metavar="DIR",
        help="output directory (default: <sdm_stem>_pipeline/ in current directory)",
    )
    parser.add_argument(
        "--resume-from",
        metavar="STAGE",
        help="resume from a named stage function (e.g. run_fluxboot)",
    )
    parser.add_argument(
        "--skip",
        metavar="STAGE",
        action="append",
        dest="skip_steps",
        default=[],
        help="skip a named stage (repeatable)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"evla-pipeline {__version_str__}",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="enable DEBUG logging",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Import here so the package loads cleanly without CASA at import time
    from evla_pipe.pipeline import continuum

    try:
        continuum(
            sdm_name=args.sdm_name,
            skip_hanning=not args.hanning,
            enable_polarization=args.polarization,
            workdir=args.workdir,
            resume_from=args.resume_from,
            skip_steps=args.skip_steps,
        )
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        logging.getLogger(__name__).error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
