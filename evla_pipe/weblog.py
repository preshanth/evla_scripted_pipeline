"""
Weblog renderer for the EVLA continuum calibration pipeline.

Produces a single ``workdir/weblog/index.html`` from the pipeline context.
No external dependencies — pure Python f-string templating.

Layout: flat-scroll page with a fixed sticky sidebar (zero JS).
Plots are referenced as relative links ``../plots/{name}`` — the
``weblog/`` and ``plots/`` directories must stay together.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage metadata tables
# ---------------------------------------------------------------------------

# Map stage name (as used in _timed() calls) -> QA2 context key
_QA_KEY_MAP: dict[str, str] = {
    "priorcals": "QA2_priorcals",
    "initial_bp": "QA2_testBPdcals",
    "semi_final_bp_1": "QA2_semiFinal",
    "semi_final_bp_2": "QA2_semiFinal",
    "solint": "QA2_solint",
    "test_gains": "QA2_testgains",
    "flux_gains": "QA2_fluxgains",
    "fluxboot": "QA2_fluxboot",
    "final_cals": "QA2_finalcals",
    "polcal": "QA2_polcal",
    "apply_cals": "QA2_applycals",
}

# Map stage name -> list of context keys holding calibration table paths
_TABLE_KEY_MAP: dict[str, list[str]] = {
    "priorcals": [
        "table_gain_curves",
        "table_opacities",
        "table_requantizer",
        "table_switched_power",
        "table_antpos",
    ],
    "initial_bp": [
        "table_test_delay_init_gain",
        "table_test_delay",
        "table_test_bp_init_gain",
        "table_test_bp",
    ],
    "semi_final_bp_1": [
        "table_semifinal_delay_init_gain",
        "table_delay",
        "table_bp_init_gain",
        "table_bp",
    ],
    "semi_final_bp_2": [],
    "test_gains": ["table_test_gaincal"],
    "flux_gains": [
        "table_flux_phase_short",
        "table_phase_short",
        "table_flux_gaincal_fcal",
    ],
    "final_cals": [
        "table_final_delay_init_gain",
        "table_final_delay",
        "table_final_bp_init_gain",
        "table_final_bp",
        "table_final_phase_gain",
        "table_final_amp_gain",
        "table_flux_gaincal",
    ],
    "polcal": ["table_pol_Xf", "table_pol_Df", "table_pol_Xa"],
}

# Map stage name -> plot filename prefix (None = no plots for that stage)
_PLOT_PREFIX_MAP: dict[str, str | None] = {
    "startup": None,
    "import": None,
    "hanning": None,
    "msmd": None,
    "preflag": None,
    "priorcals": None,
    "setjy": None,
    "initial_bp": "initial_bp",
    "initial_rflag": None,
    "semi_final_bp_1": "semi_final_bp",
    "checkflag": None,
    "semi_final_bp_2": "semi_final_bp",
    "solint": None,
    "test_gains": "test_gains",
    "flux_gains": "flux_gains",
    "fluxboot": None,
    "final_cals": "final_cals",
    "polcal": "polcal",
    "apply_cals": None,
    "final_flags": None,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MJD_EPOCH = datetime(1858, 11, 17)


def _mjd_to_utc(mjd: float) -> str:
    dt = _MJD_EPOCH + timedelta(days=mjd)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _find_band(ctx: PipelineContext) -> str:
    """Best-effort band name from spw_names or center_frequencies."""
    spw_names: list[str] = ctx.get("spw_names", [])  # type: ignore[assignment]
    for name in spw_names:
        # Format: EVLA_L#A0C0#0 → band letter after "EVLA_"
        if name.startswith("EVLA_") and len(name) > 5:
            return name[5]
    freqs: list[float] = ctx.get("center_frequencies", [])  # type: ignore[assignment]
    if freqs:
        try:
            from evla_pipe.simple_utils import find_EVLA_band

            return find_EVLA_band(freqs[len(freqs) // 2])
        except (ValueError, ImportError):
            pass
    return "?"


def _field_names_for(ctx: PipelineContext, id_list_key: str) -> list[str]:
    """Return field name strings for a list of field IDs stored in ctx."""
    field_names: list[str] = ctx.get("field_names", [])  # type: ignore[assignment]
    ids: list[int] = ctx.get(id_list_key, [])  # type: ignore[assignment]
    return [field_names[i] for i in ids if i < len(field_names)]


def _stage_qa(stage_name: str, ctx: PipelineContext, ran: bool) -> str:
    """Return 'pass' | 'partial' | 'fail' | 'skip' for a stage."""
    if not ran:
        return "skip"
    qa_key = _QA_KEY_MAP.get(stage_name)
    if qa_key and qa_key in ctx:
        overall = ctx[qa_key].overall  # type: ignore[union-attr]
        return overall.lower()
    return "pass"


def _stage_tables(stage_name: str, ctx: PipelineContext) -> list[str]:
    """Return basenames of calibration tables for a stage that exist on disk."""
    keys = _TABLE_KEY_MAP.get(stage_name, [])
    result = []
    for k in keys:
        path_str: str = ctx.get(k, "")  # type: ignore[assignment]
        if path_str and Path(path_str).exists():
            result.append(Path(path_str).name)
    return result


def _stage_plots(stage_name: str, plots_dir: Path) -> list[str]:
    """Return plot basenames for a stage, matched by filename prefix."""
    prefix = _PLOT_PREFIX_MAP.get(stage_name)
    if not prefix or not plots_dir.exists():
        return []
    all_plots = sorted(p.name for p in plots_dir.glob(f"{prefix}_*.png"))
    # For the two semi_final_bp passes, filter by pass number in filename
    if stage_name == "semi_final_bp_1":
        return [p for p in all_plots if "pass_1" in p]
    if stage_name == "semi_final_bp_2":
        return [p for p in all_plots if "pass_2" in p]
    return all_plots


def _log_excerpt(stage_name: str, workdir: Path) -> list[str]:
    """Return last 20 lines from the stage log file, or empty list."""
    log_file = workdir / "logs" / f"{stage_name}.log"
    if not log_file.exists():
        return []
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-20:]
    except OSError:
        return []


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


# ---------------------------------------------------------------------------
# CSS (embedded)
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 15px; line-height: 1.5;
    display: flex; background: #f8f9fa; color: #212529;
}
#sidebar {
    width: 230px; min-height: 100vh; background: #2c3e50; color: #ecf0f1;
    position: fixed; top: 0; left: 0; overflow-y: auto; padding: 1rem 0;
}
.run-meta { padding: 0 1rem 1rem; border-bottom: 1px solid #3d5166; }
.run-meta h2 { font-size: 0.95rem; font-weight: 700; color: #fff; margin-bottom: 0.25rem; }
.run-meta p { font-size: 0.78rem; color: #95a5a6; margin: 0.1rem 0; }
#stage-list { list-style: none; padding: 0.4rem 0; }
#stage-list li a {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.35rem 1rem; color: #bdc3cb; text-decoration: none; font-size: 0.82rem;
}
#stage-list li a:hover { background: #3d5166; color: #fff; }
.qa-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.qa-pass .qa-dot  { background: #27ae60; }
.qa-partial .qa-dot { background: #f39c12; }
.qa-fail .qa-dot  { background: #e74c3c; }
.qa-skip .qa-dot  { background: #95a5a6; }
main { margin-left: 230px; padding: 2rem; max-width: 1080px; width: 100%; }
section {
    background: #fff; border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
    padding: 1.5rem; margin-bottom: 1.5rem;
    scroll-margin-top: 1rem;
}
.stage-header {
    display: flex; align-items: baseline; gap: 0.75rem;
    margin-bottom: 1rem; border-bottom: 1px solid #e9ecef; padding-bottom: 0.75rem;
}
.stage-header h2 { font-size: 1.05rem; font-weight: 600; }
.qa-badge {
    font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.5rem;
    border-radius: 3px; text-transform: uppercase; letter-spacing: 0.04em;
}
.qa-badge.pass    { background: #d4edda; color: #155724; }
.qa-badge.partial { background: #fff3cd; color: #856404; }
.qa-badge.fail    { background: #f8d7da; color: #721c24; }
.qa-badge.skip    { background: #e2e3e5; color: #383d41; }
.duration { font-size: 0.78rem; color: #6c757d; margin-left: auto; }
h3 {
    font-size: 0.82rem; font-weight: 600; color: #495057;
    margin: 1rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.05em;
}
.table-list { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.table-chip {
    background: #e9ecef; border-radius: 3px; padding: 0.15rem 0.45rem;
    font-size: 0.78rem; font-family: ui-monospace, "Menlo", monospace;
}
.plot-grid { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 0.4rem; }
.plot-grid img { height: 200px; border: 1px solid #dee2e6; border-radius: 4px; }
details { margin-top: 0.75rem; }
summary { font-size: 0.82rem; color: #6c757d; cursor: pointer; user-select: none; }
pre {
    background: #f1f3f5; padding: 0.6rem 0.75rem; border-radius: 4px;
    font-size: 0.73rem; font-family: ui-monospace, "Menlo", monospace;
    overflow-x: auto; margin-top: 0.35rem; white-space: pre-wrap; word-break: break-all;
}
.meta-table { border-collapse: collapse; width: 100%; font-size: 0.88rem; }
.meta-table td { padding: 0.3rem 0.6rem; border-bottom: 1px solid #f1f3f5; }
.meta-table td:first-child { font-weight: 500; color: #495057; width: 38%; }
.verdict-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
.verdict-box {
    border-radius: 5px; padding: 0.6rem 1rem; min-width: 120px; text-align: center;
}
.verdict-box .count { font-size: 1.6rem; font-weight: 700; }
.verdict-box .label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }
.verdict-box.pass    { background: #d4edda; color: #155724; }
.verdict-box.partial { background: #fff3cd; color: #856404; }
.verdict-box.fail    { background: #f8d7da; color: #721c24; }
.verdict-box.skip    { background: #e2e3e5; color: #383d41; }
@media print { #sidebar { display: none; } main { margin-left: 0; } }
"""

# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------


def _render_sidebar(ctx: PipelineContext, stage_records: list[dict]) -> str:
    ran_names = {r["name"] for r in stage_records}
    sdm = ctx.get("SDM_name", "unknown")
    band = _find_band(ctx)
    startdate: float = ctx.get("startdate", 0.0)  # type: ignore[assignment]
    date_str = _mjd_to_utc(startdate) if startdate else ""
    total_s = sum(r.get("duration_s", 0) for r in stage_records)

    items_html = ""
    for rec in stage_records:
        name = rec["name"]
        label = rec["label"]
        qa = _stage_qa(name, ctx, name in ran_names)
        items_html += (
            f'<li class="qa-{qa}">'
            f'<a href="#s-{name}"><span class="qa-dot"></span>{label}</a>'
            f"</li>\n"
        )

    return f"""
<nav id="sidebar">
  <div class="run-meta">
    <h2>EVLA Pipeline</h2>
    <p>{sdm}</p>
    {"<p>" + date_str + "</p>" if date_str else ""}
    {"<p>" + band + "-band</p>" if band != "?" else ""}
    <p>Total: {_fmt_duration(total_s)}</p>
  </div>
  <ul id="stage-list">
    <li><a href="#summary" style="color:#fff;font-weight:600;">&#9776; Summary</a></li>
{items_html}  </ul>
</nav>"""


def _render_summary(ctx: PipelineContext, stage_records: list[dict]) -> str:
    ran_names = {r["name"] for r in stage_records}
    qa_counts: dict[str, int] = {"pass": 0, "partial": 0, "fail": 0, "skip": 0}
    for rec in stage_records:
        qa = _stage_qa(rec["name"], ctx, rec["name"] in ran_names)
        qa_counts[qa] = qa_counts.get(qa, 0) + 1

    total_s = sum(r.get("duration_s", 0) for r in stage_records)

    sdm = ctx.get("SDM_name", "?")
    band = _find_band(ctx)
    startdate: float = ctx.get("startdate", 0.0)  # type: ignore[assignment]
    date_str = _mjd_to_utc(startdate) if startdate else "—"
    n_ant: int = ctx.get("numAntenna", 0)  # type: ignore[assignment]
    n_spw: int = ctx.get("numSpws", 0)  # type: ignore[assignment]
    corr: str = ctx.get("corrstring", "—")  # type: ignore[assignment]
    do_pol: bool = ctx.get("do_pol", False)  # type: ignore[assignment]

    flux_fields = ", ".join(_field_names_for(ctx, "flux_field_list")) or "—"
    bp_fields = ", ".join(_field_names_for(ctx, "bandpass_field_list")) or "—"
    phase_fields = ", ".join(_field_names_for(ctx, "phase_field_list")) or "—"
    target_fields = ", ".join(_field_names_for(ctx, "amp_field_list")) or "—"

    verdict_boxes = "".join(
        f'<div class="verdict-box {qa}">'
        f'<div class="count">{count}</div>'
        f'<div class="label">{qa.title()}</div>'
        f"</div>"
        for qa, count in qa_counts.items()
        if count > 0
    )

    return f"""
<section id="summary">
  <div class="stage-header">
    <h2>Pipeline Summary</h2>
    <span class="duration">{_fmt_duration(total_s)} total</span>
  </div>
  <table class="meta-table">
    <tr><td>Dataset</td><td>{sdm}</td></tr>
    <tr><td>Observation date</td><td>{date_str}</td></tr>
    <tr><td>Band</td><td>{band}-band</td></tr>
    <tr><td>Correlator</td><td>{corr}</td></tr>
    <tr><td>Antennas</td><td>{n_ant}</td></tr>
    <tr><td>Spectral windows</td><td>{n_spw}</td></tr>
    <tr><td>Flux calibrator</td><td>{flux_fields}</td></tr>
    <tr><td>Bandpass calibrator</td><td>{bp_fields}</td></tr>
    <tr><td>Phase calibrator</td><td>{phase_fields}</td></tr>
    <tr><td>Target(s)</td><td>{target_fields}</td></tr>
    <tr><td>Polarization</td><td>{"Enabled" if do_pol else "Disabled"}</td></tr>
  </table>
  <div class="verdict-row">{verdict_boxes}</div>
</section>"""


def _render_stage_panel(
    rec: dict,
    ctx: PipelineContext,
    plots_dir: Path,
    workdir: Path,
    ran: bool,
) -> str:
    name: str = rec["name"]
    label: str = rec["label"]
    duration_s: float = rec.get("duration_s", 0.0)
    qa = _stage_qa(name, ctx, ran)

    tables = _stage_tables(name, ctx)
    plots = _stage_plots(name, plots_dir)
    log_lines = _log_excerpt(name, workdir)

    # Tables section
    tables_html = ""
    if tables:
        chips = "".join(f'<span class="table-chip">{t}</span>' for t in tables)
        tables_html = f"<h3>Tables</h3><div class='table-list'>{chips}</div>"

    # Plots section
    plots_html = ""
    if plots:
        imgs = "".join(f'<img src="../plots/{p}" alt="{p}" title="{p}">' for p in plots)
        plots_html = f"<h3>Plots</h3><div class='plot-grid'>{imgs}</div>"

    # Log section — open by default for fail/partial
    log_html = ""
    if log_lines:
        open_attr = " open" if qa in ("fail", "partial") else ""
        escaped = "\n".join(log_lines).replace("&", "&amp;").replace("<", "&lt;")
        log_html = (
            f"<details{open_attr}>"
            f"<summary>Log (last {len(log_lines)} lines)</summary>"
            f"<pre>{escaped}</pre>"
            f"</details>"
        )

    qa_message = ""
    qa_key = _QA_KEY_MAP.get(name)
    if qa_key and qa_key in ctx:
        qa_obj = ctx[qa_key]  # type: ignore[literal-required]
        if hasattr(qa_obj, "message") and qa_obj.message:
            qa_message = f"<p style='font-size:0.85rem;color:#495057;margin-top:0.5rem'>{qa_obj.message}</p>"

    return f"""
<section id="s-{name}">
  <div class="stage-header">
    <h2>{label}</h2>
    <span class="qa-badge {qa}">{qa}</span>
    <span class="duration">{_fmt_duration(duration_s)}</span>
  </div>
  {qa_message}
  {tables_html}
  {plots_html}
  {log_html}
</section>"""


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------


def _render(ctx: PipelineContext, stage_records: list[dict]) -> str:
    workdir = Path(ctx.get("workdir", "."))  # type: ignore[arg-type]
    plots_dir = workdir / "plots"
    sdm = ctx.get("SDM_name", "EVLA Pipeline")

    ran_names = {r["name"] for r in stage_records}
    sidebar = _render_sidebar(ctx, stage_records)
    summary = _render_summary(ctx, stage_records)

    panels = "".join(
        _render_stage_panel(rec, ctx, plots_dir, workdir, rec["name"] in ran_names)
        for rec in stage_records
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EVLA Pipeline — {sdm}</title>
  <style>{_CSS}</style>
</head>
<body>
{sidebar}
<main>
{summary}
{panels}
</main>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point (called from pipeline.py)
# ---------------------------------------------------------------------------


def run_weblog(ctx: PipelineContext) -> PipelineContext:
    """
    Generate ``workdir/weblog/index.html`` from ctx and stage_records.

    Always runs via try/finally in pipeline.py. Raises on failure so the
    error is visible — a missing weblog after a successful pipeline run is
    a bug, not an acceptable silent degradation.
    """
    stage_records: list[dict] = ctx.get("stage_records", [])  # type: ignore[assignment]
    workdir = Path(ctx.get("workdir", "."))  # type: ignore[arg-type]
    out_dir = workdir / "weblog"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"

    html = _render(ctx, stage_records)
    out.write_text(html, encoding="utf-8")
    ctx["weblog_path"] = str(out)
    log.info("Weblog written to %s", out)
    return ctx
