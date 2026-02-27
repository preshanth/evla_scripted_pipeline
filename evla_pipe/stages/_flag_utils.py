"""
Shared flag-snapshot helpers for stages that modify flags.

Three functions are exported:

  _flag_snapshot(vis, stage, label) -> dict
      Calls flagdata(mode="summary") and returns a JSON-serialisable dict
      with total/flagged counts and per-SPW breakdown.

  _log_flag_snapshot(snap, log) -> None
      Prints a compact block: overall fraction + one line of per-SPW %s
      (4 SPWs per line, *** on heavy SPWs >20%).

  _append_snapshot(ctx, snap) -> None
      Appends snap to ctx["flag_snapshots"], initialising the list if absent.

These helpers import casatasks, so they are only importable inside the
`casa` pixi environment.  Lightweight tests must not import this module.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from casatasks import flagdata

if TYPE_CHECKING:
    from evla_pipe.context import PipelineContext

_HEAVY_THRESHOLD = 0.20  # SPWs above this fraction get *** markers


def _flag_snapshot(vis: str, stage: str, label: str) -> dict:
    """
    Run flagdata(mode="summary") and return a compact snapshot dict.

    Parameters
    ----------
    vis : str
        Path to the MS (or caltable) to summarise.
    stage : str
        Machine-readable stage key, e.g. "preflag", "apply_cals_before".
    label : str
        Human-readable label, e.g. "Pre-flag (full MS)".

    Returns
    -------
    dict with keys:
        stage, label, vis, total (int), flagged (int), frac (float),
        per_spw: {spw_id (int): {total, flagged, frac}}
    """
    summary = flagdata(
        vis=vis,
        mode="summary",
        spwchan=True,
        action="calculate",
        savepars=False,
    )
    total = int(summary.get("total", 0))
    flagged = int(summary.get("flagged", 0))
    frac = flagged / total if total else 0.0

    per_spw: dict[int, dict] = {}
    for spw_id, sd in summary.get("spw", {}).items():
        t = int(sd.get("total", 0))
        f = int(sd.get("flagged", 0))
        per_spw[int(spw_id)] = {"total": t, "flagged": f, "frac": f / t if t else 0.0}

    return {
        "stage": stage,
        "label": label,
        "vis": vis,
        "total": total,
        "flagged": flagged,
        "frac": frac,
        "per_spw": per_spw,
    }


def _log_flag_snapshot(snap: dict, log: logging.Logger) -> None:
    """
    Log a compact flag-state block for a snapshot.

    Format::

        Flag state after preflag (full MS): 12.3% flagged (1234567 / 10000000)
          SPW  0:  8.1%   SPW  1: 14.2% ***   SPW  2:  9.0%   SPW  3:  7.5%
          SPW  4: 21.4% ***   SPW  5: 11.2%   ...

    SPWs above 20% get a *** marker.  Four SPWs are printed per line.
    """
    label = snap["label"]
    frac = snap["frac"]
    flagged = snap["flagged"]
    total = snap["total"]
    log.info(
        "Flag state after %s: %.1f%% flagged (%d / %d)",
        label,
        frac * 100,
        flagged,
        total,
    )

    per_spw = snap.get("per_spw", {})
    if not per_spw:
        return

    spw_ids = sorted(per_spw.keys())
    line_parts: list[str] = []
    for i, spw_id in enumerate(spw_ids):
        spw_frac = per_spw[spw_id]["frac"]
        marker = " ***" if spw_frac > _HEAVY_THRESHOLD else ""
        line_parts.append(f"SPW {spw_id:2d}: {spw_frac * 100:5.1f}%{marker}")
        # Flush every 4 entries
        if len(line_parts) == 4 or i == len(spw_ids) - 1:
            log.info("  %s", "   ".join(line_parts))
            line_parts = []


def _append_snapshot(ctx: PipelineContext, snap: dict) -> None:
    """Append snap to ctx['flag_snapshots'], initialising the list if absent."""
    snapshots = ctx.setdefault("flag_snapshots", [])
    snapshots.append(snap)
