"""
Section 4 — semi-final RFI flagging on calibrated residuals.

Runs rflag on the CORRECTED column of ``calibrators.ms`` after the first
semi-final delay+BP pass.  This is more sensitive than the earlier rflag on
the initial-BP residuals because:

  - The delay solution removes fringe-rate smearing that can mimic RFI.
  - The full-data BP solution (minsnr=5) produces a flatter residual,
    making low-level RFI stand out more clearly.

Only rflag is used here (no tfcrop): rflag's spectral coherence test is
the most effective first pass after a proper delay+BP solution.  tfcrop
was already applied in Section 3.

Context keys written
--------------------
(none — flags are applied in-place to calibrators.ms)
"""

import logging

from casatasks import flagdata

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)


def run_checkflag(ctx: PipelineContext) -> PipelineContext:
    """
    rflag on calibrators.ms corrected residuals between semiFinal runs.

    Reads from context
    -----------------
    calibrators_ms, calibrator_field_select_string, corrstring, all_spw
    """
    cal_ms = ctx["calibrators_ms"]
    cal_fields = ctx["calibrator_field_select_string"]
    corrstring = ctx["corrstring"]
    all_spw = ctx["all_spw"]

    log.info("Checkflag: rflag on calibrators.ms CORRECTED column")
    flagdata(
        vis=cal_ms,
        mode="rflag",
        field=cal_fields,
        spw=all_spw,
        correlation="ABS_" + corrstring,
        ntime="scan",
        combinescans=False,
        datacolumn="corrected",
        winsize=3,
        timedevscale=4.0,
        freqdevscale=4.0,
        extendflags=False,
        action="apply",
        flagbackup=False,
        savepars=True,
    )

    summary = flagdata(
        vis=cal_ms, mode="summary", action="calculate", savepars=False
    )
    total = int(summary.get("total", 0))
    flagged = int(summary.get("flagged", 0))
    frac = flagged / total if total else 0.0
    log.info(
        "After checkflag: %.1f%% of calibrators.ms data flagged", frac * 100
    )

    return ctx
