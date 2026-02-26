"""
Section 1 — import and Hanning smoothing stages.

Both are single CASA task calls with minimal logic; grouped here because
they are always sequential and neither justifies its own file.
"""

import logging
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

    msname = ctx["msname"]
    log.info("Applying Hanning smoothing to %s", msname)
    hanningsmooth(vis=msname, datacolumn="data", outputvis="")
    log.info("Hanning smoothing complete")
    return ctx
