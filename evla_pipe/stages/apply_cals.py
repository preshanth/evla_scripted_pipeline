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

from casatasks import applycal, split, statwt

from evla_pipe.context import PipelineContext
from evla_pipe.simple_utils import field_label
from evla_pipe.stages._flag_utils import (
    _append_snapshot,
    _flag_snapshot,
    _log_flag_snapshot,
)

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
    # Flag summary before applycal
    # ------------------------------------------------------------------
    snap_before = _flag_snapshot(
        ms, "apply_cals_before", "Apply cals — before (full MS)"
    )
    _log_flag_snapshot(snap_before, log)
    _append_snapshot(ctx, snap_before)

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
    snap_after = _flag_snapshot(ms, "apply_cals_after", "Apply cals — after (full MS)")
    _log_flag_snapshot(snap_after, log)
    _append_snapshot(ctx, snap_after)

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
    # Keep scalar fracs for test suite backward-compatibility.
    ctx["flag_frac_before_applycal"] = snap_before["frac"]
    ctx["flag_frac_after_applycal"] = snap_after["frac"]
    return ctx
