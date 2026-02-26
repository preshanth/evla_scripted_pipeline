"""
Tests for run_initial_rflag.

Requires CASA and a real ASDM. Set EVLA_TEST_SDM to the ASDM path.
Skipped automatically if either is absent.
"""

from pathlib import Path

import pytest

from conftest import SDM_NAME

pytest.importorskip("casatasks", reason="CASA not installed")

pytestmark = pytest.mark.skipif(
    not Path(SDM_NAME).exists(),
    reason=f"ASDM '{SDM_NAME}' not found — set EVLA_TEST_SDM",
)


@pytest.fixture(scope="module")
def rflag_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.msmd import run_msmd
    from evla_pipe.stages.preflag import run_preflag
    from evla_pipe.stages.priorcals import run_priorcals
    from evla_pipe.stages.setjy import run_setjy
    from evla_pipe.stages.initial_bp import run_initial_bp
    from evla_pipe.stages.initial_rflag import run_initial_rflag

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    ctx = run_import(ctx)
    ctx = run_msmd(ctx)
    ctx = run_preflag(ctx)
    ctx = run_priorcals(ctx)
    ctx = run_setjy(ctx)
    ctx = run_initial_bp(ctx)
    return run_initial_rflag(ctx)


def test_needs_bp_reflag_is_set(rflag_ctx):
    assert "needs_bp_reflag" in rflag_ctx
    assert isinstance(rflag_ctx["needs_bp_reflag"], bool)


def test_rflag_applied_some_flags(rflag_ctx):
    """rflag+tfcrop should have flagged at least something."""
    from casatasks import flagdata
    stats = flagdata(vis=rflag_ctx["calibrators_ms"], mode="summary")
    assert stats["flagged"] > 0, "No flags found after rflag+tfcrop passes"


def test_bp_table_still_exists(rflag_ctx):
    """BP table must still exist (re-solve overwrites in-place if needed)."""
    tbl = rflag_ctx["table_test_bp"]
    assert Path(tbl).exists(), f"BP table gone after rflag: {tbl}"
