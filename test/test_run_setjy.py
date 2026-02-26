"""
Tests for run_setjy.

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
def setjy_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.msmd import run_msmd
    from evla_pipe.stages.preflag import run_preflag
    from evla_pipe.stages.priorcals import run_priorcals
    from evla_pipe.stages.setjy import run_setjy

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    ctx = run_import(ctx)
    ctx = run_msmd(ctx)
    ctx = run_preflag(ctx)
    ctx = run_priorcals(ctx)
    return run_setjy(ctx)


def test_setjy_returns_context(setjy_ctx):
    assert setjy_ctx is not None


def test_model_column_populated(setjy_ctx):
    """MODEL column should be non-zero for at least one field after setjy."""
    from casatools import table
    tb = table()
    tb.open(setjy_ctx["calibrators_ms"])
    try:
        model = tb.getcol("MODEL_DATA")
        total_power = (model * model.conj()).real.sum()
        assert total_power > 0, "MODEL column appears to be all zeros after setjy"
    finally:
        tb.close()
