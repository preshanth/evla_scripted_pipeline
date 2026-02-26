"""
Tests for run_preflag.

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
def preflag_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.msmd import run_msmd
    from evla_pipe.stages.preflag import run_preflag

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    ctx = run_import(ctx)
    ctx = run_msmd(ctx)
    return run_preflag(ctx)


def test_calibrators_ms_exists(preflag_ctx):
    assert Path(preflag_ctx["calibrators_ms"]).exists()


def test_calibrators_ms_contains_only_calibrators(preflag_ctx):
    from casatools import msmetadata
    cal_field_ids = set(
        int(f) for f in preflag_ctx["calibrator_field_select_string"].split(",")
    )
    msmd = msmetadata()
    msmd.open(preflag_ctx["calibrators_ms"])
    try:
        cal_ms_fields = set(range(msmd.nfields()))
    finally:
        msmd.close()
    # calibrators.ms is re-indexed from 0, so check count matches
    assert len(cal_ms_fields) == len(cal_field_ids)


def test_flagging_was_applied(preflag_ctx):
    from casatasks import flagdata
    stats = flagdata(vis=preflag_ctx["msname"], mode="summary")
    assert stats["flagged"] > 0, "No flags applied to full MS — flagdata list call may have failed"


def test_preflag_is_idempotent(preflag_ctx):
    """Second call must skip the split and return the same calibrators_ms path."""
    from evla_pipe.stages.preflag import run_preflag
    ctx2 = run_preflag(preflag_ctx)
    assert ctx2["calibrators_ms"] == preflag_ctx["calibrators_ms"]
