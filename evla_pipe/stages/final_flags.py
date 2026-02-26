"""
Section 6b — final flagging on target.ms (optional).

Runs rflag on the corrected column of target.ms and logs the final
flag fraction summary.  This is a best-effort stage; failures are
logged but do not abort the pipeline.

Context keys read
-----------------
target_ms : str   path produced by run_apply_cals
"""

import logging

from casatasks import flagdata

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)


def run_final_flags(ctx: PipelineContext) -> PipelineContext:
    """
    rflag on target.ms corrected column + final flag summary.

    No-op if target_ms is absent or empty.
    """
    target_ms = ctx.get("target_ms", "")
    if not target_ms:
        log.info("target_ms not set — skipping final flagging")
        return ctx

    log.info("Running rflag on %s (corrected column)", target_ms)
    try:
        flagdata(
            vis=target_ms,
            mode="rflag",
            datacolumn="corrected",
            action="apply",
            flagbackup=True,
            savepars=False,
        )
    except Exception:
        log.exception("rflag on target.ms failed — continuing")
        return ctx

    # Final flag fraction summary
    try:
        stats = flagdata(
            vis=target_ms,
            mode="summary",
            action="calculate",
            savepars=False,
        )
        total = stats.get("total", 0)
        flagged = stats.get("flagged", 0)
        if total > 0:
            log.info(
                "Final flag fraction: %.2f%% (%d / %d)",
                100.0 * flagged / total,
                flagged,
                total,
            )
    except Exception:
        log.exception("Flag summary on target.ms failed")

    return ctx
