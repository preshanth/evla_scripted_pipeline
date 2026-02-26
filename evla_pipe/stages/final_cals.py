"""
Section 4 — final calibration tables.

Produces four calibration tables on ``calibrators.ms`` using the
flux-bootstrapped MODEL column:

  1. Final delay         (K, solint='inf') → table_final_delay
  2. Final BP init gain  (G, calmode='p')  → table_final_bp_init_gain
  3. Final bandpass      (B, solint='inf') → table_final_bp
  4. Final phase gain    (G, calmode='p',  solint=gain_solint1) → table_final_phase_gain
  5. Final amp gain      (G, calmode='ap', solint=gain_solint2) → table_final_amp_gain

These five tables, prepended by priorcals, form ``ctx["final_caltables"]``
which is the complete gaintable list passed to the Section 6 applycal.

Context keys written
--------------------
table_final_delay_init_gain : str  (reused from semiFinal — not re-solved)
table_final_delay           : str
table_final_bp_init_gain    : str
table_final_bp              : str
table_final_phase_gain      : str
table_final_amp_gain        : str
final_caltables             : list[str]
"""

import logging
from pathlib import Path

from casatasks import bandpass, gaincal, rmtables

from evla_pipe.context import PipelineContext
from evla_pipe.utils import getCalFlaggedSoln

log = logging.getLogger(__name__)


def run_final_cals(ctx: PipelineContext) -> PipelineContext:
    """
    Produce final delay, bandpass, phase, and amplitude calibration tables.

    Reads from context
    -----------------
    calibrators_ms, priorcals, refAnt, minBL_for_cal,
    delay_field_select_string, delay_scan_select_string, tst_delay_spw,
    bandpass_field_select_string, bandpass_scan_select_string, all_spw,
    calibrator_field_select_string, phase_scan_select_string,
    gain_solint1, gain_solint2, int_time,
    cal3C84_d, cal3C84_bp, uvrange3C84, critfrac

    Writes to context
    -----------------
    table_final_delay, table_final_bp_init_gain, table_final_bp,
    table_final_phase_gain, table_final_amp_gain, final_caltables
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
    cal_fields = ctx["calibrator_field_select_string"]
    phase_scan = ctx["phase_scan_select_string"]
    gain_solint1 = ctx["gain_solint1"]
    gain_solint2 = ctx["gain_solint2"]
    cal3C84_d = ctx.get("cal3C84_d", False)
    cal3C84_bp = ctx.get("cal3C84_bp", False)
    uvrange3C84 = ctx.get("uvrange3C84", "")
    critfrac = ctx.get("critfrac", 0.1)

    uv_d = uvrange3C84 if cal3C84_d else ""
    uv_bp = uvrange3C84 if cal3C84_bp else ""

    outdir = Path(ctx["workdir"]) / "final_caltables"
    outdir.mkdir(parents=True, exist_ok=True)

    t_init = str(outdir / "finaldelayinitialgain.g")
    t_delay = str(outdir / "finaldelay.k")
    t_bp_init = str(outdir / "finalBPinitialgain.g")
    t_bp = str(outdir / "finalBPcal.b")
    t_phase = str(outdir / "finalphasegaincal.g")
    t_amp = str(outdir / "finalampgaincal.g")

    # ------------------------------------------------------------------
    # 1. Final delay phase init gain
    # ------------------------------------------------------------------
    log.info("Final cals step 1: short phase gain on delay calibrator")
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
        uvrange=uv_d,
    )

    # ------------------------------------------------------------------
    # 2. Final delay (K)
    # ------------------------------------------------------------------
    log.info("Final cals step 2: delay calibration")
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
        uvrange=uv_d,
    )
    _log_cal_quality("final delay", t_delay, critfrac)

    # ------------------------------------------------------------------
    # 3. Final BP init gain
    # ------------------------------------------------------------------
    log.info("Final cals step 3: BP phase init gain (solint=%s)", gain_solint1)
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
    # 4. Final bandpass
    # ------------------------------------------------------------------
    log.info("Final cals step 4: bandpass (solint='inf')")
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
    _log_cal_quality("final BP", t_bp, 0.2)

    # ------------------------------------------------------------------
    # 5. Final phase gain (short solint, all calibrators)
    # ------------------------------------------------------------------
    log.info("Final cals step 5: phase gain (solint=%s)", gain_solint1)
    rmtables(t_phase)
    gt = priorcals + [t_delay, t_bp]
    gaincal(
        vis=cal_ms,
        caltable=t_phase,
        field=cal_fields,
        spw=all_spw,
        scan=phase_scan,
        solint=gain_solint1,
        combine="",
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=3.0,
        gaintype="G",
        calmode="p",
        append=False,
        gaintable=gt,
        gainfield=[""] * len(gt),
        interp=[""] * len(gt),
    )
    _log_cal_quality("final phase gain", t_phase, critfrac)

    # ------------------------------------------------------------------
    # 6. Final amp gain (long solint, all calibrators)
    # ------------------------------------------------------------------
    log.info("Final cals step 6: amp gain (solint=%s)", gain_solint2)
    rmtables(t_amp)
    gt = priorcals + [t_delay, t_bp, t_phase]
    gaincal(
        vis=cal_ms,
        caltable=t_amp,
        field=cal_fields,
        spw=all_spw,
        scan=phase_scan,
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
    _log_cal_quality("final amp gain", t_amp, critfrac)

    # ------------------------------------------------------------------
    # Assemble final_caltables list for Section 6 applycal
    # ------------------------------------------------------------------
    final_caltables = priorcals + [t_delay, t_bp, t_phase, t_amp]

    ctx["table_final_delay_init_gain"] = t_init
    ctx["table_final_delay"] = t_delay
    ctx["table_final_bp_init_gain"] = t_bp_init
    ctx["table_final_bp"] = t_bp
    ctx["table_final_phase_gain"] = t_phase
    ctx["table_final_amp_gain"] = t_amp
    ctx["final_caltables"] = final_caltables

    log.info(
        "final_caltables assembled (%d entries): %s",
        len(final_caltables),
        final_caltables,
    )
    return ctx


def _log_cal_quality(label: str, table: str, threshold: float) -> None:
    if not Path(table).exists():
        log.warning("%s: table not found at %s", label, table)
        return
    stats = getCalFlaggedSoln(table)
    frac = stats.get("all", {}).get("fraction", 0.0)
    med = stats.get("antmedian", {}).get("fraction", 0.0)
    log.info("%s: flagged=%.4f  antenna-median=%.4f", label, frac, med)
    if med > threshold:
        log.warning(
            "%s antenna-median flagged fraction %.4f > threshold %.4f",
            label, med, threshold,
        )
