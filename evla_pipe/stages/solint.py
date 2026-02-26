"""
Section 4 — solution interval determination.

Analyses phase-calibrator scan durations in ``calibrators.ms`` to determine
the two solution intervals used for all subsequent gaincal calls:

  gain_solint1  — short interval = integration time  ("Xs")
                  Used for per-integration phase solutions.
  gain_solint2  — long interval  = max(scan_duration) × 1.01  ("Xs")
                  Used for amplitude+phase solutions (scan-averaged).

Scanning is done directly from calibrators.ms (no re-split needed — the MS
was already created in Section 2 and is the working MS from this point on).

Contiguous scans on the same field with the same SPW set are merged before
taking the maximum, matching the behaviour of the original pipeline.

Context keys written
--------------------
gain_solint1 : str  — e.g. "2.02s"
gain_solint2 : str  — e.g. "123.45s"
"""

import logging

from casatools import ms as mstool

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)

_DAY_S = 86400.0  # seconds per day
_DEFAULT_LONG_SOLINT_S = 30.0  # fallback if no scan durations found


def _scan_durations(cal_ms: str, phase_scan_list: list[int]) -> list[float]:
    """
    Return effective on-source durations (seconds) for each group of
    contiguous phase-calibrator scans with the same field/SPW setup.
    """
    ms = mstool()
    ms.open(cal_ms)
    try:
        scan_summary = ms.getscansummary()
    finally:
        ms.close()

    durations: list[float] = []
    old_spws: list[int] = []
    old_field: str = ""
    old_begin: float = 0.0

    for kk, scan_id in enumerate(phase_scan_list):
        summary = scan_summary.get(str(scan_id))
        if not summary:
            log.warning(
                "Scan %d completely flagged or absent from calibrators.ms", scan_id
            )
            continue

        try:
            end_time = max(v["EndTime"] for v in summary.values())
            begin_time = min(v["BeginTime"] for v in summary.values())
            first = list(summary.values())[0]
            new_spws = list(first.get("SpwIds", []))
            new_field = str(first.get("FieldId", ""))

            contiguous = (
                kk > 0
                and phase_scan_list[kk - 1] == scan_id - 1
                and set(new_spws) == set(old_spws)
                and new_field == old_field
            )

            if contiguous:
                durations[-1] = _DAY_S * (end_time - old_begin)
            else:
                durations.append(_DAY_S * (end_time - begin_time))
                old_begin = begin_time

            log.info("Scan %d: %.2f s on source", scan_id, durations[-1])
            old_spws = new_spws
            old_field = new_field

        except (KeyError, ValueError) as exc:
            log.warning("Scan %d incomplete in calibrators.ms: %s", scan_id, exc)

    return durations


def run_solint(ctx: PipelineContext) -> PipelineContext:
    """
    Determine gain_solint1 and gain_solint2 from calibrators.ms.

    Reads from context
    -----------------
    calibrators_ms, phase_scan_list, int_time

    Writes to context
    -----------------
    gain_solint1 : str  — integration time as "Xs"
    gain_solint2 : str  — long solint as "Xs" (max scan duration × 1.01)
    """
    cal_ms = ctx["calibrators_ms"]
    phase_scan_list = ctx["phase_scan_list"]
    int_time = ctx["int_time"]

    # Short solint = integration time
    gain_solint1 = f"{int_time:.2f}s"

    # Long solint = max phase-calibrator scan duration with 1% headroom
    durations = _scan_durations(cal_ms, phase_scan_list)
    if durations:
        long_s = max(durations) * 1.01
        log.info(
            "Maximum phase-cal scan duration: %.2f s → solint2=%.2f s",
            max(durations),
            long_s,
        )
    else:
        long_s = _DEFAULT_LONG_SOLINT_S
        log.warning(
            "No valid phase-cal scan durations found — using default %.0f s", long_s
        )

    gain_solint2 = f"{long_s:.2f}s"

    ctx["gain_solint1"] = gain_solint1
    ctx["gain_solint2"] = gain_solint2
    log.info("gain_solint1=%s  gain_solint2=%s", gain_solint1, gain_solint2)
    return ctx
