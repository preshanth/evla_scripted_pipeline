"""
Tests for evla_pipe.weblog — no CASA required.

Exercises the HTML renderer against a synthetic pipeline context and checks
that structural invariants of the output hold regardless of real pipeline data.
"""

from pathlib import Path

import pytest

from evla_pipe.weblog import _render, _fmt_duration, _mjd_to_utc, run_weblog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(tmp_path: Path, stage_records: list[dict] | None = None) -> dict:
    """Build a minimal fake pipeline context sufficient for weblog rendering."""
    workdir = tmp_path / "pipeline"
    (workdir / "weblog").mkdir(parents=True)
    (workdir / "plots").mkdir()
    (workdir / "logs").mkdir()

    return {
        "SDM_name": "TDRW0001",
        "workdir": str(workdir),
        "do_pol": False,
        "enable_plots": True,
        "startdate": 58395.0,   # MJD
        "numAntenna": 27,
        "numSpws": 8,
        "corrstring": "RR,LL",
        "spw_names": ["EVLA_L#A0C0#0"],
        "center_frequencies": [1.5e9],
        "field_names": ["3C286", "J0319+4130", "MyTarget"],
        "flux_field_list": [0],
        "bandpass_field_list": [0],
        "phase_field_list": [1],
        "amp_field_list": [2],
        "stage_records": stage_records or [],
        "priorcals": [],
        "final_caltables": [],
        "pol_caltables": [],
    }


def _records(*pairs) -> list[dict]:
    """Build stage_records from (name, label) pairs with dummy duration."""
    return [{"name": n, "label": lbl, "duration_s": 10.0} for n, lbl in pairs]


# ---------------------------------------------------------------------------
# Unit tests — pure render functions
# ---------------------------------------------------------------------------

class TestFormatHelpers:
    def test_fmt_duration_seconds(self):
        assert _fmt_duration(45.0) == "45s"

    def test_fmt_duration_minutes(self):
        assert _fmt_duration(125.0) == "2m 5s"

    def test_mjd_to_utc_known(self):
        # MJD 51544 = 2000-01-01 00:00 UTC (J2000.0)
        result = _mjd_to_utc(51544.0)
        assert "2000-01-01" in result

    def test_mjd_to_utc_pipeline_date(self):
        # MJD 58395 ≈ 2018-09-27
        result = _mjd_to_utc(58395.0)
        assert "2018" in result


class TestRenderOutput:
    def test_summary_section_present(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        html = _render(ctx, [])
        assert 'id="summary"' in html

    def test_sdm_name_in_title(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        html = _render(ctx, [])
        assert "TDRW0001" in html

    def test_stage_section_ids(self, tmp_path):
        records = _records(
            ("startup", "Startup"),
            ("initial_bp", "Initial Bandpass"),
        )
        ctx = _make_ctx(tmp_path, records)
        html = _render(ctx, records)
        assert 'id="s-startup"' in html
        assert 'id="s-initial_bp"' in html

    def test_sidebar_links_present(self, tmp_path):
        records = _records(("priorcals", "Prior Calibrations"))
        ctx = _make_ctx(tmp_path, records)
        html = _render(ctx, records)
        assert 'href="#s-priorcals"' in html

    def test_field_names_in_summary(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        html = _render(ctx, [])
        assert "3C286" in html       # flux cal
        assert "MyTarget" in html    # target

    def test_band_derived_from_spw_names(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        html = _render(ctx, [])
        assert "L-band" in html

    def test_total_duration_in_summary(self, tmp_path):
        records = _records(("startup", "Startup"), ("msmd", "MS Metadata"))
        # each record has duration_s=10 → total 20s
        ctx = _make_ctx(tmp_path, records)
        html = _render(ctx, records)
        assert "20s" in html

    def test_plots_referenced_with_relative_path(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        plots_dir = Path(ctx["workdir"]) / "plots"
        (plots_dir / "initial_bp_ap_spw_0.png").write_bytes(b"")
        records = _records(("initial_bp", "Initial Bandpass"))
        html = _render(ctx, records)
        assert "../plots/initial_bp_ap_spw_0.png" in html

    def test_no_base64_in_output(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        plots_dir = Path(ctx["workdir"]) / "plots"
        (plots_dir / "initial_bp_ap_spw_0.png").write_bytes(b"\x89PNG")
        records = _records(("initial_bp", "Initial Bandpass"))
        html = _render(ctx, records)
        assert "data:image" not in html

    def test_print_media_query_present(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        html = _render(ctx, [])
        assert "@media print" in html


class TestQABadges:
    def test_pass_badge_for_completed_stage_no_qa_key(self, tmp_path):
        records = _records(("startup", "Startup"))
        ctx = _make_ctx(tmp_path, records)
        html = _render(ctx, records)
        # startup has no QA key → defaults to pass
        assert 'class="qa-badge pass"' in html

    def test_fail_badge_when_qa_result_is_fail(self, tmp_path):
        from evla_pipe.context import QAResult
        records = _records(("priorcals", "Prior Calibrations"))
        ctx = _make_ctx(tmp_path, records)
        ctx["QA2_priorcals"] = QAResult(overall="Fail", message="test failure")
        html = _render(ctx, records)
        assert 'class="qa-badge fail"' in html

    def test_partial_badge(self, tmp_path):
        from evla_pipe.context import QAResult
        records = _records(("priorcals", "Prior Calibrations"))
        ctx = _make_ctx(tmp_path, records)
        ctx["QA2_priorcals"] = QAResult(overall="Partial", message="some spws failed")
        html = _render(ctx, records)
        assert 'class="qa-badge partial"' in html


class TestLogExcerpts:
    def test_log_collapsed_for_pass_stage(self, tmp_path):
        records = _records(("startup", "Startup"))
        ctx = _make_ctx(tmp_path, records)
        log_file = Path(ctx["workdir"]) / "logs" / "startup.log"
        log_file.write_text("line1\nline2\nline3\n")
        html = _render(ctx, records)
        # pass stage → <details> without 'open'
        assert "<details>" in html
        assert "<details open>" not in html

    def test_log_expanded_for_fail_stage(self, tmp_path):
        from evla_pipe.context import QAResult
        records = _records(("priorcals", "Prior Calibrations"))
        ctx = _make_ctx(tmp_path, records)
        ctx["QA2_priorcals"] = QAResult(overall="Fail", message="fail")
        log_file = Path(ctx["workdir"]) / "logs" / "priorcals.log"
        log_file.write_text("error line\n")
        html = _render(ctx, records)
        assert "<details open>" in html

    def test_missing_log_file_does_not_crash(self, tmp_path):
        records = _records(("startup", "Startup"))
        ctx = _make_ctx(tmp_path, records)
        html = _render(ctx, records)  # no log file created
        assert "startup" in html  # page still renders


# ---------------------------------------------------------------------------
# Integration — run_weblog writes to disk
# ---------------------------------------------------------------------------

class TestRunWeblog:
    def test_writes_index_html(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx = run_weblog(ctx)
        out = Path(ctx["workdir"]) / "weblog" / "index.html"
        assert out.exists()

    def test_weblog_path_set_in_ctx(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx = run_weblog(ctx)
        assert "weblog_path" in ctx
        assert ctx["weblog_path"].endswith("index.html")

    def test_weblog_survives_broken_ctx(self, tmp_path):
        """run_weblog should not raise even with a nearly empty context."""
        ctx = {
            "workdir": str(tmp_path),
            "stage_records": [],
            "priorcals": [],
            "final_caltables": [],
            "pol_caltables": [],
        }
        (tmp_path / "weblog").mkdir()
        result = run_weblog(ctx)
        # Should return ctx without raising
        assert isinstance(result, dict)

    def test_semi_final_bp_pass_filtering(self, tmp_path):
        """Plots for pass_1 and pass_2 are correctly separated."""
        ctx = _make_ctx(tmp_path)
        plots_dir = Path(ctx["workdir"]) / "plots"
        (plots_dir / "semi_final_bp_ap_spw_0_pass_1.png").write_bytes(b"")
        (plots_dir / "semi_final_bp_ap_spw_0_pass_2.png").write_bytes(b"")

        records = _records(
            ("semi_final_bp_1", "Semi-final BP (pass 1)"),
            ("semi_final_bp_2", "Semi-final BP (pass 2)"),
        )
        ctx["stage_records"] = records
        html = _render(ctx, records)

        # pass_1 plot in pass_1 panel, pass_2 plot in pass_2 panel — not crossed
        assert 'id="s-semi_final_bp_1"' in html
        assert 'id="s-semi_final_bp_2"' in html
        # Each img src appears exactly once
        assert html.count('src="../plots/semi_final_bp_ap_spw_0_pass_1.png"') == 1
        assert html.count('src="../plots/semi_final_bp_ap_spw_0_pass_2.png"') == 1
