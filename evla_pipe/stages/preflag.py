"""
Section 2 — pre-calibration flagging and calibrator split.

Two responsibilities:
1. Apply all deterministic flags to the full MS in a single flagdata call:
   online flags (from importasdm) + shadow + clip zeros + tfcrop.
2. Split calibrator fields into calibrators.ms (keepflags=False).

The full MS is touched exactly once here after import.  All calibration
work from this point onward operates on calibrators.ms.  The full MS is
not opened again until final applycal.
"""

import logging
from pathlib import Path

from casatasks import flagdata, split

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)


def _read_online_flags(flagonline_txt: str) -> list[str]:
    """
    Read online flag commands written by importasdm.

    Returns an empty list (with a warning) if the file is missing rather
    than raising, so the pipeline can proceed with shadow + clip + tfcrop.
    """
    path = Path(flagonline_txt)
    if not path.exists():
        log.warning(
            "Online flag file not found: %s — skipping online flags", flagonline_txt
        )
        return []
    lines = [ln.strip() for ln in path.read_text().splitlines()]
    # Drop blank lines and comments
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    log.info("Read %d online flag commands from %s", len(lines), flagonline_txt)
    return lines


def run_preflag(ctx: PipelineContext) -> PipelineContext:
    """
    Apply all pre-calibration flags to the full MS in one flagdata call,
    then split calibrators into calibrators.ms.

    Flag command order (all in one flagdata list call):
      1. Online / antenna flags from importasdm
      2. Shadow flags
      3. Clip zero-amplitude data
      4. tfcrop (broadband RFI, no model required)
      5. Extend flags across polarizations

    After flagging, split calibrator fields into calibrators.ms with
    keepflags=False so flagged rows are dropped entirely.

    Sets
    ----
    ctx["calibrators_ms"] : str
        Path to the split calibrators-only MS.
    """
    msname = ctx["msname"]
    flagonline_txt = ctx["flagonline_txt"]
    cal_field_select = ctx["calibrator_field_select_string"]
    corrstring = ctx["corrstring"]

    # ------------------------------------------------------------------
    # Build the flag command list
    # ------------------------------------------------------------------
    cmds: list[str] = []

    # 1. Online flags from importasdm
    cmds += _read_online_flags(flagonline_txt)

    # 2. Shadow flags — antennas blocked by others in the array
    cmds.append("mode='shadow'")

    # 3. Clip zero amplitudes (dead antennas, correlator dropouts)
    cmds.append(f"mode='clip' clipzeros=True correlation='ABS_{corrstring}'")

    # 4. tfcrop — broadband RFI detection without a model.
    #    Conservative thresholds (3σ): real flagging happens post-split on residuals.
    #    Applied per correlation so RFI in one hand does not mask the other.
    cmds.append(
        f"mode='tfcrop' datacolumn='DATA' correlation='ABS_{corrstring}' "
        "ntime=51.0 combinescans=False "
        "freqdevscale=3.0 timedevscale=3.0 "
        "extendflags=False"
    )

    log.info("Applying %d flag commands to %s", len(cmds), msname)
    flagdata(vis=msname, mode="list", inpfile=cmds, flagbackup=True)
    log.info("Pre-calibration flagging complete")

    # ------------------------------------------------------------------
    # Split calibrators into working MS
    # ------------------------------------------------------------------
    calibrators_ms = ctx["calibrators_ms"]

    if Path(calibrators_ms).exists():
        log.info("calibrators.ms already exists, skipping split: %s", calibrators_ms)
    else:
        log.info(
            "Splitting calibrator fields [%s] -> %s", cal_field_select, calibrators_ms
        )
        split(
            vis=msname,
            outputvis=calibrators_ms,
            field=cal_field_select,
            datacolumn="data",
            keepflags=False,
        )
        log.info("Split complete: %s", calibrators_ms)

    ctx["calibrators_ms"] = calibrators_ms
    return ctx
