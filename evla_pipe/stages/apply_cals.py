"""
Section 6 — apply final calibration to full MS, statwt targets, split target.ms.

Applies ``ctx["final_caltables"]`` (and pol tables if polarization_calibrated)
to every field in the full measurement set, then:
  - statwt on target fields (reweighting by scatter in corrected data)
  - split corrected column of target fields → target.ms

Context keys written
--------------------
target_ms : str   path to split target measurement set
"""

import logging
from pathlib import Path

from casatasks import applycal, flagdata, split, statwt

from evla_pipe.context import PipelineContext
from evla_pipe.simple_utils import field_label

log = logging.getLogger(__name__)


def run_apply_cals(ctx: PipelineContext) -> PipelineContext:
    """
    Apply all calibration tables to the full MS, then split targets.

    Reads from context
    ------------------
    msname, final_caltables, do_pol, polarization_calibrated, pol_caltables,
    calibrator_field_select_string, target_field_select_string

    Writes to context
    -----------------
    target_ms
    """
    ms = ctx["msname"]
    final_caltables = ctx["final_caltables"]
    do_pol = ctx.get("do_pol", False)

    # Assemble complete gaintable list
    gaintable = list(final_caltables)
    if do_pol and ctx.get("polarization_calibrated", False):
        pol_tables = ctx.get("pol_caltables", [])
        if pol_tables:
            log.info("Appending pol caltables: %s", pol_tables)
            gaintable.extend(pol_tables)

    n = len(gaintable)
    log.info("applycal (%d tables): all fields in %s", n, ms)
    log.info("  gaintable: %s", gaintable)

    # ------------------------------------------------------------------
    # Flag summary before applycal (for logging)
    # ------------------------------------------------------------------
    before = flagdata(vis=ms, mode="summary", action="calculate", savepars=False)
    _log_flag_summary("before applycal", before)

    # ------------------------------------------------------------------
    # applycal — all fields in full MS
    # ------------------------------------------------------------------
    applycal(
        vis=ms,
        field="",
        gaintable=gaintable,
        gainfield=[""] * n,
        interp=[""] * n,
        spwmap=[[]] * n,
        calwt=[False] * n,
        parang=do_pol,
        applymode="calflagstrict",
        flagbackup=True,
    )
    log.info("applycal complete")

    # ------------------------------------------------------------------
    # Flag summary after applycal
    # ------------------------------------------------------------------
    after = flagdata(vis=ms, mode="summary", action="calculate", savepars=False)
    _log_flag_summary("after applycal", after)

    # ------------------------------------------------------------------
    # statwt — reweight target fields by scatter in corrected data
    # ------------------------------------------------------------------
    target_fields = ctx.get("target_field_select_string", "")
    if target_fields:
        log.info("statwt: field=%s in %s", field_label(ctx, target_fields), ms)
        statwt(
            vis=ms,
            field=target_fields,
            datacolumn="corrected",
        )
    else:
        log.warning("target_field_select_string not set — skipping statwt")

    # ------------------------------------------------------------------
    # Split target fields → target.ms
    # ------------------------------------------------------------------
    target_ms = str(Path(ctx["workdir"]) / "target.ms")
    if target_fields:
        log.info("split: field=%s → %s", field_label(ctx, target_fields), target_ms)
        split(
            vis=ms,
            outputvis=target_ms,
            field=target_fields,
            datacolumn="corrected",
            keepflags=False,
        )
        log.info("target.ms created")
    else:
        log.warning("target_field_select_string not set — skipping split to target.ms")
        target_ms = ""

    ctx["target_ms"] = target_ms
    # Store flag fractions for validation and weblog.
    ctx["flag_frac_before_applycal"] = (
        before.get("flagged", 0) / before["total"] if before.get("total") else 0.0
    )
    ctx["flag_frac_after_applycal"] = (
        after.get("flagged", 0) / after["total"] if after.get("total") else 0.0
    )
    return ctx


def _log_flag_summary(label: str, stats: dict) -> None:
    total = stats.get("total", 0)
    flagged = stats.get("flagged", 0)
    if total > 0:
        frac = 100.0 * flagged / total
        log.info("%s: flagged %.2f%% (%d / %d)", label, frac, flagged, total)
    else:
        log.info("%s: no data", label)
