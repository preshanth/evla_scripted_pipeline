"""
Section 3 — initial bandpass calibration.

Solves a coarse bandpass on ``calibrators.ms`` using all available data
(solint='inf') to enable RFI flagging on residuals.  A short per-integration
phase solution is computed first so that inter-antenna phase drifts do not
smear the bandpass amplitudes.

No delay calibration is applied before this step.  Delay is easily affected
by RFI; the purpose of this initial BP is solely to produce a reference model
for subsequent rflag passes.  Once RFI is flagged, semiFinalBPdcals will
re-derive delay + bandpass on clean data.

Context keys written
--------------------
table_test_bp_init_gain : str  — short per-integration phase table
table_test_bp           : str  — initial bandpass table
"""

import logging
from pathlib import Path

from casatasks import applycal, bandpass, gaincal

from evla_pipe.context import PipelineContext
from evla_pipe.simple_utils import field_label
from evla_pipe.utils import RefAntHeuristics

log = logging.getLogger(__name__)


def run_initial_bp(ctx: PipelineContext) -> PipelineContext:
    """
    Solve initial bandpass (no prior delay).

    Reads from context
    -----------------
    calibrators_ms, priorcals, bandpass_field_select_string,
    bandpass_scan_select_string, refAnt, minBL_for_cal,
    cal3C84_bp, uvrange3C84, corrstring, all_spw

    Writes to context
    -----------------
    table_test_bp_init_gain : str
    table_test_bp           : str
    """
    cal_ms = ctx["calibrators_ms"]
    priorcals = ctx["priorcals"]
    bp_field = ctx["bandpass_field_select_string"]
    bp_scan = ctx["bandpass_scan_select_string"]
    min_bl = ctx["minBL_for_cal"]

    # Compute reference antenna if not already set by a prior stage
    if "refAnt" not in ctx:
        log.info("refAnt not in context — computing from heuristics on calibrators_ms")
        findrefant = RefAntHeuristics(
            vis=cal_ms, field=bp_field, geometry=True, flagging=True
        )
        ref_ant_list = findrefant.calculate()
        ref_ant = str(ref_ant_list[0])
        ctx["refAnt"] = ref_ant
        log.info("Reference antenna selected: %s", ref_ant)
    else:
        ref_ant = ctx["refAnt"]
    all_spw = ctx["all_spw"]
    cal3C84_bp = ctx.get("cal3C84_bp", False)
    uvrange3C84 = ctx.get("uvrange3C84", "")

    uvrange = uvrange3C84 if cal3C84_bp else ""

    wd = Path(ctx["workdir"])
    init_gain_table = str(wd / "testBPdinitialgain.g")
    bp_table = str(wd / "testBPcal.b")

    # ------------------------------------------------------------------
    # 1. Short per-integration phase solutions
    #    These correct antenna-based phase offsets so BP amplitudes
    #    are not smeared by phase scatter across integrations.
    # ------------------------------------------------------------------
    log.info(
        "gaincal (phase, solint=int): field=%s, scan=%s, spw=%s → %s",
        field_label(ctx, bp_field),
        bp_scan,
        all_spw,
        init_gain_table,
    )
    gaincal(
        vis=cal_ms,
        caltable=init_gain_table,
        field=bp_field,
        spw=all_spw,
        selectdata=True,
        scan=bp_scan,
        solint="int",
        refant=ref_ant,
        minblperant=min_bl,
        minsnr=3.0,
        solnorm=False,
        gaintype="G",
        calmode="p",
        append=False,
        gaintable=priorcals,
        gainfield=[""] * len(priorcals),
        interp=[""] * len(priorcals),
        uvrange=uvrange,
    )
    if not Path(init_gain_table).exists():
        raise RuntimeError(f"gaincal did not produce {init_gain_table}")
    ctx["table_test_bp_init_gain"] = init_gain_table

    # ------------------------------------------------------------------
    # 2. Bandpass with infinite solution interval (all data combined)
    # ------------------------------------------------------------------
    log.info(
        "bandpass (solint=inf, combine=scan): field=%s, scan=%s, spw=%s → %s",
        field_label(ctx, bp_field),
        bp_scan,
        all_spw,
        bp_table,
    )
    bp_gaintable = priorcals + [init_gain_table]
    bp_gainfield = [""] * len(bp_gaintable)
    bp_interp = [""] * len(bp_gaintable)

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
        gainfield=bp_gainfield,
        interp=bp_interp,
        uvrange=uvrange,
    )
    if not Path(bp_table).exists():
        raise RuntimeError(f"bandpass did not produce {bp_table}")
    ctx["table_test_bp"] = bp_table

    # ------------------------------------------------------------------
    # 3. Apply to calibrators.ms so residuals are available for rflag
    # ------------------------------------------------------------------
    log.info(
        "applycal (%d tables): all fields in %s",
        len(priorcals) + 2,
        cal_ms,
    )
    ac_gaintable = priorcals + [init_gain_table, bp_table]
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
    log.info("Initial bandpass applied — CORRECTED column ready for rflag")

    return ctx
