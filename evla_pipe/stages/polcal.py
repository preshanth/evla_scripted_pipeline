"""
Section 5 — polarization calibration (optional).

Guard conditions (no-op return):
  - ctx["do_pol"] is False, OR
  - pol_angle_field_list is empty, OR
  - pol_leakage_field_list is empty

Calibration chain on calibrators.ms:
  1. KCROSS (cross-hand delay) on pol angle fields
     gaintable = final_caltables
  2. Df (leakage D-terms) on pol leakage fields
     gaintable = final_caltables + [kcross]

Context keys written
--------------------
table_kcross         : str
table_dterms         : str
pol_caltables        : list[str]
polarization_calibrated : bool
"""

import logging
from pathlib import Path

from casatasks import gaincal, polcal, rmtables

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)


def run_polcal(ctx: PipelineContext) -> PipelineContext:
    """
    Perform cross-hand delay (KCROSS) and D-term leakage (Df) calibration.

    No-op if do_pol is False or calibrator lists are empty.

    Reads from context
    ------------------
    do_pol, calibrators_ms, final_caltables, refAnt, minBL_for_cal,
    all_spw, pol_angle_field_list, pol_leakage_field_list

    Writes to context
    -----------------
    table_kcross, table_dterms, pol_caltables, polarization_calibrated
    """
    do_pol = ctx.get("do_pol", False)
    pol_angle = ctx.get("pol_angle_field_list", [])
    pol_leakage = ctx.get("pol_leakage_field_list", [])

    if not do_pol:
        log.info("do_pol=False — skipping polarization calibration")
        ctx["polarization_calibrated"] = False
        return ctx

    if not pol_angle:
        log.warning("pol_angle_field_list is empty — skipping polarization calibration")
        ctx["polarization_calibrated"] = False
        return ctx

    if not pol_leakage:
        log.warning(
            "pol_leakage_field_list is empty — skipping polarization calibration"
        )
        ctx["polarization_calibrated"] = False
        return ctx

    cal_ms = ctx["calibrators_ms"]
    final_caltables = ctx["final_caltables"]
    ref_ant = ctx["refAnt"]
    min_bl = ctx["minBL_for_cal"]
    all_spw = ctx["all_spw"]

    # Field select strings (comma-separated IDs or names, as stored in context)
    pol_angle_select = ",".join(str(f) for f in pol_angle)
    pol_leakage_select = ",".join(str(f) for f in pol_leakage)

    log.info("Polarization angle calibrators: %s", pol_angle_select)
    log.info("Polarization leakage calibrators: %s", pol_leakage_select)

    outdir = Path(ctx["workdir"]) / "final_caltables"
    outdir.mkdir(parents=True, exist_ok=True)

    t_kcross = str(outdir / "kcross.g")
    t_dterms = str(outdir / "dterms.d")

    n = len(final_caltables)

    # ------------------------------------------------------------------
    # 1. KCROSS — cross-hand delay on pol angle calibrators
    # ------------------------------------------------------------------
    log.info("Polcal step 1: KCROSS on %s", pol_angle_select)
    rmtables(t_kcross)
    gaincal(
        vis=cal_ms,
        caltable=t_kcross,
        field=pol_angle_select,
        spw=all_spw,
        solint="inf",
        combine="scan",
        preavg=-1.0,
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=3.0,
        gaintype="KCROSS",
        calmode="p",
        append=False,
        gaintable=final_caltables,
        gainfield=[""] * n,
        interp=[""] * n,
        parang=True,
    )
    log.info("KCROSS table written: %s", t_kcross)

    # ------------------------------------------------------------------
    # 2. Df — leakage D-terms on pol leakage calibrators
    # ------------------------------------------------------------------
    log.info("Polcal step 2: Df on %s", pol_leakage_select)
    rmtables(t_dterms)
    gt = final_caltables + [t_kcross]
    ng = len(gt)
    polcal(
        vis=cal_ms,
        caltable=t_dterms,
        field=pol_leakage_select,
        spw=all_spw,
        solint="inf",
        combine="scan",
        preavg=-1.0,
        minblperant=min_bl,
        minsnr=3.0,
        poltype="Df",
        append=False,
        gaintable=gt,
        gainfield=[""] * ng,
        interp=[""] * ng,
        parang=True,
    )
    log.info("Dterms table written: %s", t_dterms)

    ctx["table_kcross"] = t_kcross
    ctx["table_dterms"] = t_dterms
    ctx["pol_caltables"] = [t_kcross, t_dterms]
    ctx["polarization_calibrated"] = True

    log.info("Polarization calibration complete")
    return ctx
