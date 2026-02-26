"""
Section 3 — prior calibration tables.

Generates four deterministic prior calibration tables that are prepended to
every subsequent CASA gaintable list:

  1. Elevation gain curves    (caltype='gc')   — always required
  2. Atmospheric opacities    (caltype='opac') — always required
  3. Requantizer gains        (caltype='rq')   — only for data after 2011-02-24
  4. Antenna position offsets (caltype='antpos') — optional, may produce empty table

All tables are written to ``final_caltables/``.  On return ``ctx["priorcals"]``
is a list of every table that was created and is non-empty; downstream stages
prepend this list to their own gaintable arguments.
"""

import logging
from pathlib import Path

from casatasks import gencal

from evla_pipe.context import PipelineContext
from evla_pipe.utils import correct_ant_posns

log = logging.getLogger(__name__)

# MJD for 2011-02-24 — date when sensible switched-power tables became available
_RQ_CUTOFF_MJD = 55616.6


def run_priorcals(ctx: PipelineContext) -> PipelineContext:
    """
    Generate all deterministic prior calibration tables.

    Reads from context
    -----------------
    msname, all_spw, tau, startdate, numSpws

    Writes to context
    -----------------
    priorcals           : list[str]  — tables to prepend to every gaintable list
    table_gain_curves   : str
    table_opacities     : str
    table_requantizer   : str | None — None when startdate < 2011-02-24
    table_antpos        : str | None — None when no corrections are available
    """
    ms = ctx["msname"]
    all_spw = ctx["all_spw"]
    tau = ctx["tau"]
    startdate = ctx["startdate"]
    num_spws = ctx["numSpws"]

    outdir = Path(ctx["workdir"]) / "final_caltables"
    outdir.mkdir(parents=True, exist_ok=True)

    priorcals: list[str] = []

    # ------------------------------------------------------------------
    # 1. Elevation gain curves
    # ------------------------------------------------------------------
    gc_table = str(outdir / "gain_curves.g")
    log.info("Generating elevation gain curves → %s", gc_table)
    gencal(vis=ms, caltable=gc_table, caltype="gc", spw="", antenna="", pol="")
    if not Path(gc_table).exists():
        raise RuntimeError(f"gencal gc did not create {gc_table}")
    ctx["table_gain_curves"] = gc_table
    priorcals.append(gc_table)

    # ------------------------------------------------------------------
    # 2. Atmospheric opacities  (tau per spw, all the same value here)
    # ------------------------------------------------------------------
    opac_table = str(outdir / "opacities.g")
    tau_per_spw = [float(tau)] * num_spws
    log.info("Generating opacity table (tau=%.4f) → %s", tau, opac_table)
    gencal(
        vis=ms,
        caltable=opac_table,
        caltype="opac",
        spw=all_spw,
        antenna="",
        pol="",
        parameter=tau_per_spw,
    )
    if not Path(opac_table).exists():
        raise RuntimeError(f"gencal opac did not create {opac_table}")
    ctx["table_opacities"] = opac_table
    priorcals.append(opac_table)

    # ------------------------------------------------------------------
    # 3. Requantizer gains (post-2011 data only)
    # ------------------------------------------------------------------
    if startdate >= _RQ_CUTOFF_MJD:
        rq_table = str(outdir / "requantizergains.g")
        log.info("Generating requantizer gains → %s", rq_table)
        gencal(vis=ms, caltable=rq_table, caltype="rq", spw="", antenna="", pol="")
        if Path(rq_table).exists():
            ctx["table_requantizer"] = rq_table
            priorcals.append(rq_table)
        else:
            log.warning("gencal rq produced no table — skipping")
            ctx["table_requantizer"] = None
    else:
        log.info(
            "Skipping requantizer gains: startdate %.1f < cutoff %.1f MJD",
            startdate,
            _RQ_CUTOFF_MJD,
        )
        ctx["table_requantizer"] = None

    # ------------------------------------------------------------------
    # 4. Antenna position corrections (optional)
    # ------------------------------------------------------------------
    antpos_table = str(outdir / "antposcal.p")
    log.info("Generating antenna position corrections → %s", antpos_table)
    try:
        gencal(
            vis=ms,
            caltable=antpos_table,
            caltype="antpos",
            spw="",
            antenna="",
            pol="",
            parameter=[],
        )
        if Path(antpos_table).exists():
            offsets = correct_ant_posns(ms)
            if offsets:
                log.info("Antenna position offsets applied: %s", offsets)
                ctx["table_antpos"] = antpos_table
                priorcals.append(antpos_table)
            else:
                log.info("No antenna position corrections needed.")
                ctx["table_antpos"] = None
        else:
            ctx["table_antpos"] = None
    except Exception as exc:
        log.warning("Antenna position corrections unavailable: %s", exc)
        ctx["table_antpos"] = None

    ctx["priorcals"] = priorcals
    log.info("priorcals: %d tables ready: %s", len(priorcals), priorcals)
    return ctx
