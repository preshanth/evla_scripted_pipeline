"""
Section 4 — semi-final delay + bandpass calibration.

Solves a four-step calibration chain on ``calibrators.ms``:

  1. Short per-integration phase gain (priorcals only) — phase reference for delay
  2. Delay (K) — wideband fringe rate; uses mid-channels (tst_delay_spw)
  3. BP phase init gain (priorcals + delay) — phase reference for bandpass
  4. Bandpass (B, solint='inf') — full spectral response

Then applies the complete chain back to calibrators.ms so residuals are
available for ``run_checkflag``.

This function is called **twice** by the orchestrator with ``run_checkflag``
between the two calls.  The second call overwrites the intermediate tables
in-place; final table paths remain the same.

Context keys written
--------------------
table_semifinal_delay_init_gain : str
table_delay                     : str
table_bp_init_gain              : str
table_bp                        : str
"""

import logging
from pathlib import Path

from casatasks import applycal, bandpass, gaincal, rmtables

from evla_pipe.context import PipelineContext
from evla_pipe.utils import getCalFlaggedSoln

log = logging.getLogger(__name__)


def run_semi_final_bp(ctx: PipelineContext) -> PipelineContext:
    """
    Solve delay + bandpass on calibrators.ms and apply back.

    Reads from context
    -----------------
    calibrators_ms, priorcals, refAnt, minBL_for_cal,
    delay_field_select_string, delay_scan_select_string, tst_delay_spw,
    bandpass_field_select_string, bandpass_scan_select_string, all_spw,
    int_time, cal3C84_d, cal3C84_bp, uvrange3C84, critfrac

    Writes to context
    -----------------
    table_semifinal_delay_init_gain, table_delay,
    table_bp_init_gain, table_bp
    """
    cal_ms = ctx["calibrators_ms"]
    priorcals = ctx["priorcals"]
    ref_ant = ctx["refAnt"]
    min_bl = ctx["minBL_for_cal"]
    delay_field = ctx["delay_field_select_string"]
    delay_scan = ctx["delay_scan_select_string"]
    tst_delay_spw = ctx["tst_delay_spw"]
    bp_field = ctx["bandpass_field_select_string"]
    bp_scan = ctx["bandpass_scan_select_string"]
    all_spw = ctx["all_spw"]
    int_time = ctx["int_time"]
    cal3C84_d = ctx.get("cal3C84_bp", False)
    cal3C84_bp = ctx.get("cal3C84_bp", False)
    uvrange3C84 = ctx.get("uvrange3C84", "")
    critfrac = ctx.get("critfrac", 0.1)

    uv_delay = uvrange3C84 if cal3C84_d else ""
    uv_bp = uvrange3C84 if cal3C84_bp else ""
    gain_solint1 = f"{int_time:.2f}s"

    wd = Path(ctx["workdir"])
    t_init = str(wd / "semiFinaldelayinitialgain.g")
    t_delay = str(wd / "delay.k")
    t_bp_init = str(wd / "BPdinitialgain.g")
    t_bp = str(wd / "BPcal.b")

    # ------------------------------------------------------------------
    # 1. Short per-integration phase gain (phase reference for delay)
    # ------------------------------------------------------------------
    log.info("Step 1: Short phase gain on delay calibrator")
    rmtables(t_init)
    gaincal(
        vis=cal_ms,
        caltable=t_init,
        field=delay_field,
        spw=tst_delay_spw,
        scan=delay_scan,
        solint="int",
        combine="scan",
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=3.0,
        gaintype="G",
        calmode="p",
        append=False,
        gaintable=priorcals,
        gainfield=[""] * len(priorcals),
        interp=[""] * len(priorcals),
        uvrange=uv_delay,
    )

    # ------------------------------------------------------------------
    # 2. Delay calibration (K)
    # ------------------------------------------------------------------
    log.info("Step 2: Delay calibration")
    rmtables(t_delay)
    gt = priorcals + [t_init]
    gaincal(
        vis=cal_ms,
        caltable=t_delay,
        field=delay_field,
        spw=tst_delay_spw,
        scan=delay_scan,
        solint="inf",
        combine="scan",
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=3.0,
        gaintype="K",
        append=False,
        gaintable=gt,
        gainfield=[""] * len(gt),
        interp=[""] * len(gt),
        uvrange=uv_delay,
    )
    if Path(t_delay).exists():
        stats = getCalFlaggedSoln(t_delay)
        frac = stats.get("all", {}).get("fraction", 0.0)
        med = stats.get("antmedian", {}).get("fraction", 0.0)
        log.info("Delay: flagged fraction=%.4f  antenna-median=%.4f", frac, med)
        if med > critfrac:
            log.warning(
                "Delay flagged fraction %.4f exceeds critfrac %.4f", med, critfrac
            )

    # ------------------------------------------------------------------
    # 3. BP phase init gain (phase reference for bandpass)
    # ------------------------------------------------------------------
    log.info("Step 3: BP phase init gain (solint=%s)", gain_solint1)
    rmtables(t_bp_init)
    gt = priorcals + [t_delay]
    gaincal(
        vis=cal_ms,
        caltable=t_bp_init,
        field=bp_field,
        spw=all_spw,
        scan=bp_scan,
        solint=gain_solint1,
        combine="scan",
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=3.0,
        gaintype="G",
        calmode="p",
        append=False,
        gaintable=gt,
        gainfield=[""] * len(gt),
        interp=[""] * len(gt),
        uvrange=uv_bp,
    )

    # ------------------------------------------------------------------
    # 4. Bandpass (all data combined, high-SNR solution)
    # ------------------------------------------------------------------
    log.info("Step 4: Bandpass calibration (solint='inf')")
    rmtables(t_bp)
    gt = priorcals + [t_delay, t_bp_init]
    bandpass(
        vis=cal_ms,
        caltable=t_bp,
        field=bp_field,
        spw=all_spw,
        scan=bp_scan,
        solint="inf",
        combine="scan",
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=5.0,
        solnorm=False,
        bandtype="B",
        fillgaps=62,
        append=False,
        gaintable=gt,
        gainfield=[""] * len(gt),
        interp=[""] * len(gt),
        uvrange=uv_bp,
    )
    if Path(t_bp).exists():
        stats = getCalFlaggedSoln(t_bp)
        frac = stats.get("all", {}).get("fraction", 0.0)
        med = stats.get("antmedian", {}).get("fraction", 0.0)
        log.info("BP: flagged fraction=%.4f  antenna-median=%.4f", frac, med)
        if med > 0.2:
            log.warning("BP flagged fraction %.4f exceeds 0.2 threshold", med)

    # ------------------------------------------------------------------
    # 5. Apply to calibrators.ms
    # ------------------------------------------------------------------
    log.info("Step 5: Applying delay+BP to calibrators.ms")
    gt = priorcals + [t_delay, t_bp]
    applycal(
        vis=cal_ms,
        field="",
        spw=all_spw,
        gaintable=gt,
        gainfield=[""] * len(gt),
        interp=[""] * len(gt),
        calwt=[False] * len(gt),
        applymode="calflagstrict",
        flagbackup=False,
    )

    ctx["table_semifinal_delay_init_gain"] = t_init
    ctx["table_delay"] = t_delay
    ctx["table_bp_init_gain"] = t_bp_init
    ctx["table_bp"] = t_bp

    log.info("Semi-final BP complete — calibrators.ms ready for checkflag")
    return ctx
