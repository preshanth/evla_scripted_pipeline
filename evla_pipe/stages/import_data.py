"""
Section 1 — import and Hanning smoothing stages.

Both are single CASA task calls with minimal logic; grouped here because
they are always sequential and neither justifies its own file.
"""

import logging
import shutil
from pathlib import Path

from casatasks import hanningsmooth, importasdm

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)


def run_import(ctx: PipelineContext) -> PipelineContext:
    """
    Import an ASDM into a CASA Measurement Set via importasdm.

    Skips the import if the MS already exists (resume support).
    """
    sdm_name = ctx["SDM_name"]
    msname = ctx["msname"]

    if Path(msname).exists():
        log.info("MS already exists, skipping import: %s", msname)
        return ctx

    flagonline_txt = ctx["flagonline_txt"]
    log.info("Importing %s -> %s", sdm_name, msname)
    importasdm(
        asdm=sdm_name,
        vis=msname,
        ocorr_mode="co",
        compression=False,
        asis="Receiver CalAtmosphere",
        scans="",
        savecmds=True,
        outfile=flagonline_txt,
        flagbackup=False,
        process_flags=True,
        applyflags=False,
        with_pointing_correction=True,
        convert_ephem2geo=True,
        polyephem_tabtimestep=0.001,
    )
    log.info("Import complete: %s  online flags: %s", msname, flagonline_txt)
    return ctx


def run_hanning(ctx: PipelineContext) -> PipelineContext:
    """
    Apply Hanning smoothing to reduce Gibbs ringing.

    Skipped when ctx["do_hanning"] is False (spectral line mode).
    Operates in-place on ctx["msname"].
    """
    if not ctx.get("do_hanning", True):
        log.info("Hanning smoothing disabled, skipping")
        return ctx

    if ctx.get("do_pol", False):
        log.warning(
            "Hanning smoothing skipped: polarization calibration is enabled. "
            "Hanning smoothing mixes adjacent channels and corrupts the "
            "cross-hand phase needed for polarization calibration."
        )
        return ctx

    msname = ctx["msname"]
    marker = Path(msname).parent / (Path(msname).stem + ".hanning_done")
    if marker.exists():
        log.info("Hanning already applied (marker found), skipping: %s", msname)
        return ctx

    tmp_ms = msname + ".hanning"
    log.info("Applying Hanning smoothing: %s -> %s", msname, tmp_ms)

    # CASA hanningsmooth requires a distinct outputvis — smooth to a temp path,
    # then replace the original so the rest of the pipeline sees the same msname.
    if Path(tmp_ms).exists():
        shutil.rmtree(tmp_ms)

    hanningsmooth(vis=msname, datacolumn="data", outputvis=tmp_ms)

    shutil.rmtree(msname)
    shutil.move(tmp_ms, msname)
    marker.touch()
    log.info("Hanning smoothing complete: %s", msname)
    return ctx
