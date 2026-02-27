import pytest

from evla_pipe import simple_utils as su


def test_format_qa_status():
    assert su.format_qa_status("Pass").startswith("\u2713")
    assert su.format_qa_status("Fail").startswith("\u2717")
    assert "Unknown" in su.format_qa_status("Unknown")


def test_get_caltable_path_defaults(tmp_path):
    p = su.get_caltable_path("mycal.g")
    assert "final_caltables" in p
    assert p.endswith("mycal.g")


def test_path_helpers_and_dirs(tmp_path, monkeypatch):
    # point directories to tmp_path by monkeypatching Path locations via env
    logs = tmp_path / "logs"
    plots = tmp_path / "plots"
    weblog = tmp_path / "weblog"
    # Ensure ensure_dir_exists works
    su.ensure_dir_exists(logs)
    su.ensure_dir_exists(plots)
    su.ensure_dir_exists(weblog)
    assert su.path_exists(logs)
    assert su.get_log_path("a.log").name == "a.log"
    assert su.get_plot_path("p.png").name == "p.png"
    assert su.get_weblog_path("w.html").name == "w.html"


def test_should_and_get_plot_output_path():
    ctx = {"enable_plots": False}
    assert su.get_plot_output_path("p.png", ctx) == ""
    ctx = {"enable_plots": True}
    out = su.get_plot_output_path("p.png", ctx)
    assert out.endswith("p.png")


def test_join_and_uniq():
    p = su.join_paths("a", "b", "c.txt")
    assert p.endswith("a/b/c.txt") or p.endswith("a\\b\\c.txt")
    assert su.uniq([3, 1, 3, 2]) == [1, 2, 3]


def test_find_evla_band():
    assert su.find_EVLA_band(1.5e9) == "L"
    assert su.find_EVLA_band(3.0e9) == "S"
    with pytest.raises(ValueError):
        su.find_EVLA_band(1e12)


def test_checkpoint_roundtrip(tmp_path):
    from evla_pipe.context import (
        QAResult,
        load_checkpoint,
        make_default_context,
        save_checkpoint,
    )

    ctx = make_default_context("test.asdm")
    ctx["workdir"] = str(tmp_path)
    ctx["gain_solint1"] = "5.00s"
    ctx["QA2_priorcals"] = QAResult(overall="Pass", message="ok")

    save_checkpoint(ctx, "priorcals")
    loaded_ctx, completed, fingerprint = load_checkpoint(str(tmp_path))

    assert completed == ["priorcals"]
    assert loaded_ctx["gain_solint1"] == "5.00s"
    assert isinstance(loaded_ctx["QA2_priorcals"], QAResult)
    assert loaded_ctx["QA2_priorcals"].overall == "Pass"
    assert loaded_ctx["QA2_priorcals"].message == "ok"
    assert fingerprint["SDM_name"] == "test.asdm"
