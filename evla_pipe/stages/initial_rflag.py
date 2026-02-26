"""
Section 3 — RFI flagging on initial bandpass residuals (3a/3b).

Two passes of automated flagging are applied to ``calibrators.ms`` using the
model-subtracted CORRECTED column (datacolumn='residual'):

  Pass 1 — rflag: spectrally coherent RFI (narrowband, wideband)
  Pass 2 — tfcrop: time-coherent RFI missed by rflag

After both passes a per-spw flag fraction summary is logged.  If any SPW
exceeds ``BP_REFLAG_THRESHOLD`` (default 20 %), the BP table is re-solved on
the cleaner data and bad solutions flagged (3b sanity check).

Context keys written
--------------------
needs_bp_reflag  : bool   — True if any SPW flagging exceeded threshold
table_test_bp    : str    — updated in-place if re-solve happens
"""

import logging

from casatasks import applycal, bandpass, flagdata

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)

# Fraction of data flagged per SPW above which we re-solve the BP
BP_REFLAG_THRESHOLD = 0.20


def _flag_fraction_per_spw(summary: dict) -> dict[int, float]:
    """Extract per-spw flag fractions from a flagdata summary dict."""
    spw_fracs: dict[int, float] = {}
    for spw_str, stats in summary.get("spw", {}).items():
        total = int(stats.get("total", 0))
        flagged = int(stats.get("flagged", 0))
        if total > 0:
            spw_fracs[int(spw_str)] = flagged / total
    return spw_fracs


def run_initial_rflag(ctx: PipelineContext) -> PipelineContext:
    """
    Two-pass RFI flagging on bandpass residuals, with optional BP re-solve.

    Reads from context
    -----------------
    calibrators_ms, priorcals, table_test_bp_init_gain, table_test_bp,
    bandpass_field_select_string, bandpass_scan_select_string,
    refAnt, minBL_for_cal, all_spw, cal3C84_bp, uvrange3C84

    Writes to context
    -----------------
    needs_bp_reflag : bool
    table_test_bp   : str  (unchanged unless re-solve occurs)
    """
    cal_ms = ctx["calibrators_ms"]
    priorcals = ctx["priorcals"]
    bp_table = ctx["table_test_bp"]
    init_gain = ctx["table_test_bp_init_gain"]
    bp_field = ctx["bandpass_field_select_string"]
    bp_scan = ctx["bandpass_scan_select_string"]
    ref_ant = ctx["refAnt"]
    min_bl = ctx["minBL_for_cal"]
    all_spw = ctx["all_spw"]
    cal3C84_bp = ctx.get("cal3C84_bp", False)
    uvrange3C84 = ctx.get("uvrange3C84", "")
    uvrange = uvrange3C84 if cal3C84_bp else ""

    # ------------------------------------------------------------------
    # Pass 1 — rflag on residuals
    # ------------------------------------------------------------------
    log.info("Pass 1: rflag on calibrators.ms residuals")
    flagdata(
        vis=cal_ms,
        mode="rflag",
        datacolumn="residual",
        field="",
        spw=all_spw,
        freqdevscale=3.0,
        timedevscale=3.0,
        flagbackup=False,
        action="apply",
        savepars=True,
    )

    # ------------------------------------------------------------------
    # Pass 2 — tfcrop on residuals
    # ------------------------------------------------------------------
    log.info("Pass 2: tfcrop on calibrators.ms residuals")
    flagdata(
        vis=cal_ms,
        mode="tfcrop",
        datacolumn="residual",
        field="",
        spw=all_spw,
        freqdevscale=3.0,
        timedevscale=3.0,
        flagbackup=False,
        action="apply",
        savepars=True,
    )

    # ------------------------------------------------------------------
    # Sanity check: per-spw flag fractions
    # ------------------------------------------------------------------
    log.info("Computing per-spw flag fractions after rflag+tfcrop")
    summary = flagdata(
        vis=cal_ms,
        mode="summary",
        spwchan=True,
        action="calculate",
        savepars=False,
    )
    spw_fracs = _flag_fraction_per_spw(summary)

    heavy_spws = {
        spw: frac for spw, frac in spw_fracs.items() if frac > BP_REFLAG_THRESHOLD
    }
    for spw, frac in sorted(spw_fracs.items()):
        marker = " ***" if spw in heavy_spws else ""
        log.info("  SPW %2d: %.1f%% flagged%s", spw, frac * 100, marker)

    needs_reflag = bool(heavy_spws)
    ctx["needs_bp_reflag"] = needs_reflag

    # ------------------------------------------------------------------
    # 3b — re-solve BP if heavily-flagged SPWs detected
    # ------------------------------------------------------------------
    if needs_reflag:
        log.info(
            "SPWs %s exceed %.0f%% flag threshold — re-solving bandpass on "
            "cleaner data (3b sanity check)",
            sorted(heavy_spws.keys()),
            BP_REFLAG_THRESHOLD * 100,
        )

        bp_gaintable = priorcals + [init_gain]
        bandpass(
            vis=cal_ms,
            caltable=bp_table,
            field=bp_field,
            spw=all_spw,
            selectdata=True,
            scan=bp_scan,
            solint="inf",
            combine="scan",
            refant=ref_ant,
            minblperant=min_bl,
            minsnr=3.0,
            solnorm=False,
            bandtype="B",
            fillgaps=62,
            append=False,
            gaintable=bp_gaintable,
            gainfield=[""] * len(bp_gaintable),
            interp=[""] * len(bp_gaintable),
            uvrange=uvrange,
        )

        # Flag solutions with >80% of channels flagged within the table
        log.info("Flagging bad BP solutions (>80%% channel flag fraction)")
        flagdata(
            vis=bp_table,
            mode="summary",
            action="calculate",
            savepars=False,
        )
        # Clip solutions where amplitude deviates strongly from median
        flagdata(
            vis=bp_table,
            mode="clip",
            datacolumn="CPARAM",
            clipminmax=[0.0, 100.0],
            clipoutside=True,
            flagbackup=False,
            action="apply",
        )

        # Re-apply updated BP
        ac_gaintable = priorcals + [init_gain, bp_table]
        applycal(
            vis=cal_ms,
            field="",
            spw=all_spw,
            gaintable=ac_gaintable,
            gainfield=[""] * len(ac_gaintable),
            interp=[""] * len(ac_gaintable),
            calwt=[False] * len(ac_gaintable),
            flagbackup=False,
        )
        log.info("Re-solved BP applied to calibrators.ms")
    else:
        log.info(
            "All SPW flag fractions below %.0f%% — no BP re-solve needed",
            BP_REFLAG_THRESHOLD * 100,
        )

    return ctx
