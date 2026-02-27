"""
Section 4 — validate the long solution interval.

Runs a test gaincal on ``calibrators.ms`` using ``gain_solint2`` and inspects
the fraction of flagged solutions.  If the fraction exceeds ``critfrac`` we
log a warning but do not abort — the user can adjust ``gain_solint2`` in the
context before re-running final_cals.

Context keys written
--------------------
table_test_gaincal : str  — path to the test gain table ("testgaincal.g")
"""

import logging
from pathlib import Path

from casatasks import gaincal, rmtables

from evla_pipe.context import PipelineContext
from evla_pipe.utils import getCalFlaggedSoln

log = logging.getLogger(__name__)


def run_test_gains(ctx: PipelineContext) -> PipelineContext:
    """
    Validate gain_solint2 by inspecting flagged solution fraction.

    Reads from context
    -----------------
    calibrators_ms, priorcals, table_delay, table_bp,
    phase_scan_select_string, refAnt, minBL_for_cal, all_spw,
    gain_solint2, critfrac

    Writes to context
    -----------------
    table_test_gaincal : str
    """
    cal_ms = ctx["calibrators_ms"]
    priorcals = ctx["priorcals"]
    t_delay = ctx["table_delay"]
    t_bp = ctx["table_bp"]
    phase_scan = ctx["phase_scan_select_string"]
    ref_ant = ctx["refAnt"]
    min_bl = ctx["minBL_for_cal"]
    all_spw = ctx["all_spw"]
    gain_solint2 = ctx["gain_solint2"]
    critfrac = ctx.get("critfrac", 0.1)

    t_test = str(Path(ctx["workdir"]) / "testgaincal.g")
    rmtables(t_test)

    gt = priorcals + [t_delay, t_bp]
    log.info(
        "gaincal (ap, solint=%s): scan=%s, spw=%s → %s",
        gain_solint2,
        phase_scan,
        all_spw,
        t_test,
    )
    gaincal(
        vis=cal_ms,
        caltable=t_test,
        field="",
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

    stats = getCalFlaggedSoln(t_test)
    frac = stats.get("all", {}).get("fraction", 0.0)
    med = stats.get("antmedian", {}).get("fraction", 0.0)
    log.info(
        "Test gain (solint=%s): flagged=%.4f  antenna-median=%.4f",
        gain_solint2,
        frac,
        med,
    )
    if med > critfrac:
        log.warning(
            "Test gain flagged fraction %.4f > critfrac %.4f — "
            "consider increasing gain_solint2 before running final_cals",
            med,
            critfrac,
        )

    ctx["table_test_gaincal"] = t_test
    return ctx
