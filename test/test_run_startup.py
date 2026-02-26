"""
Tests for run_startup.

No CASA required. run_startup only validates the SDM path and creates
output directories — pure filesystem operations.
"""

import pytest
from pathlib import Path

from evla_pipe.context import make_default_context
from evla_pipe.stages.startup import _SUBDIRS, run_startup


def test_output_dirs_created(tmp_path):
    (tmp_path / "test.sdm").mkdir()
    ctx = make_default_context("test.sdm")
    ctx["workdir"] = str(tmp_path / "test_pipeline")
    run_startup(ctx)

    workdir = Path(ctx["workdir"])
    for d in _SUBDIRS:
        assert (workdir / d).is_dir(), f"Expected subdir '{d}' not created in workdir"


def test_workdir_auto_named_from_sdm(tmp_path, monkeypatch):
    """When workdir is not pre-set, run_startup names it <sdm_stem>_pipeline."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test.sdm").mkdir()

    ctx = make_default_context("test.sdm")
    # workdir is empty — startup should compute it
    run_startup(ctx)

    assert ctx["workdir"].endswith("test_pipeline")
    assert Path(ctx["workdir"]).is_dir()


def test_calibrators_ms_rooted_in_workdir(tmp_path):
    (tmp_path / "obs.sdm").mkdir()
    ctx = make_default_context("obs.sdm")
    ctx["workdir"] = str(tmp_path / "obs_pipeline")
    run_startup(ctx)

    assert ctx["calibrators_ms"] == str(
        Path(ctx["workdir"]) / "calibrators.ms"
    )


def test_raises_if_neither_sdm_nor_ms_exist(tmp_path):
    ctx = make_default_context("nonexistent.sdm")
    ctx["workdir"] = str(tmp_path / "out")
    with pytest.raises(FileNotFoundError):
        run_startup(ctx)


def test_proceeds_if_ms_already_exists(tmp_path):
    """Resume case: SDM is gone but the MS was already imported."""
    (tmp_path / "obs.sdm.ms").mkdir()
    ctx = make_default_context("obs.sdm")
    ctx["msname"] = str(tmp_path / "obs.sdm.ms")
    ctx["workdir"] = str(tmp_path / "obs_pipeline")
    run_startup(ctx)  # should not raise
