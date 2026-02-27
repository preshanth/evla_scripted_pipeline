"""
Section 4 — flux gain model initialisation.

Two responsibilities:
1. Re-run setjy on ``calibrators.ms`` for standard flux calibrators.
   The MODEL column may have drifted from the initial Section 3 setjy
   due to CASA internal handling; this ensures a clean reference before
   fluxscale.
2. Solve a short amp+phase gain table on ALL calibrators using the current
   delay+BP solution.  This table (``fluxgaincal.g``) is the input caltable
   to ``fluxscale`` in the next stage.

Context keys written
--------------------
table_flux_gaincal : str  — path to "fluxgaincal.g"
"""

import logging
from pathlib import Path

from casatasks import gaincal, rmtables, setjy

from evla_pipe.context import PipelineContext
from evla_pipe.pol_setjy_utils import integrate_polarization_setjy
from evla_pipe.simple_utils import field_label
from evla_pipe.utils import _extract_position_tuples, find_EVLA_band, find_standards

log = logging.getLogger(__name__)

_STANDARD_NAMES = ["3C48", "3C138", "3C147", "3C286"]


def _refresh_setjy(ctx: PipelineContext) -> None:
    """Re-run setjy on calibrators.ms for all detected standard calibrators."""
    cal_ms = ctx["calibrators_ms"]
    field_positions = ctx["field_positions"]
    field_spws = ctx["field_spws"]
    center_frequencies = ctx["center_frequencies"]

    positions = _extract_position_tuples(field_positions)
    standard_fields = find_standards(positions)

    for source_idx, fids in enumerate(standard_fields):
        if not fids:
            continue
        src_name = _STANDARD_NAMES[source_idx]

        for fid in fids:
            if fid >= len(field_spws) or not field_spws[fid]:
                continue
            valid_spws = [s for s in field_spws[fid] if s < len(center_frequencies)]
            if not valid_spws:
                continue

            ref_freq_hz = center_frequencies[valid_spws[0]]
            evla_band = find_EVLA_band(ref_freq_hz / 1e9)

            log.info(
                "Refreshing flux model for field %d (%s) band=%s",
                fid,
                src_name,
                evla_band,
            )
            try:
                integrate_polarization_setjy(
                    vis=cal_ms,
                    field_id=fid,
                    field_name=src_name,
                    spws=valid_spws,
                    band=evla_band,
                    ref_freq_hz=ref_freq_hz,
                    obs_date=None,
                    standard="Perley-Butler 2017",
                    usescratch=True,
                )
            except Exception as exc:
                log.warning(
                    "Pol setjy failed for %s — using intensity-only: %s", src_name, exc
                )
                setjy(
                    vis=cal_ms,
                    field=str(fid),
                    spw=",".join(str(s) for s in valid_spws),
                    selectdata=False,
                    scalebychan=True,
                    standard="Perley-Butler 2017",
                    listmodels=False,
                    usescratch=True,
                )


def run_flux_gains(ctx: PipelineContext) -> PipelineContext:
    """
    Refresh setjy and solve fluxgaincal.g for fluxscale input.

    Reads from context
    -----------------
    calibrators_ms, priorcals, table_delay, table_bp,
    calibrator_field_select_string, phase_scan_select_string,
    refAnt, minBL_for_cal, all_spw, gain_solint2,
    field_positions, field_spws, center_frequencies, scratch

    Writes to context
    -----------------
    table_flux_gaincal : str
    """
    cal_ms = ctx["calibrators_ms"]
    priorcals = ctx["priorcals"]
    t_delay = ctx["table_delay"]
    t_bp = ctx["table_bp"]
    cal_fields = ctx["calibrator_field_select_string"]
    ref_ant = ctx["refAnt"]
    min_bl = ctx["minBL_for_cal"]
    all_spw = ctx["all_spw"]
    gain_solint2 = ctx["gain_solint2"]

    # ------------------------------------------------------------------
    # 1. Refresh MODEL column for flux calibrators
    # ------------------------------------------------------------------
    log.info("Refreshing setjy models on calibrators.ms")
    _refresh_setjy(ctx)

    # ------------------------------------------------------------------
    # 2. Short amp+phase gain solve on all calibrators → fluxgaincal.g
    # ------------------------------------------------------------------
    t_flux = str(Path(ctx["workdir"]) / "fluxgaincal.g")
    rmtables(t_flux)

    gt = priorcals + [t_delay, t_bp]
    log.info(
        "gaincal (ap, solint=%s): field=%s, spw=%s → %s",
        gain_solint2,
        field_label(ctx, cal_fields),
        all_spw,
        t_flux,
    )
    gaincal(
        vis=cal_ms,
        caltable=t_flux,
        field=cal_fields,
        spw=all_spw,
        solint=gain_solint2,
        combine="",
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=3.0,
        gaintype="G",
        calmode="ap",
        append=False,
        gaintable=gt,
        gainfield=[""] * len(gt),
        interp=[""] * len(gt),
    )

    ctx["table_flux_gaincal"] = t_flux
    log.info("fluxgaincal.g ready for fluxscale")
    return ctx
