"""
Tests for run_initial_bp.

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
def initial_bp_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.msmd import run_msmd
    from evla_pipe.stages.preflag import run_preflag
    from evla_pipe.stages.priorcals import run_priorcals
    from evla_pipe.stages.setjy import run_setjy
    from evla_pipe.stages.initial_bp import run_initial_bp

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    ctx = run_import(ctx)
    ctx = run_msmd(ctx)
    ctx = run_preflag(ctx)
    ctx = run_priorcals(ctx)
    ctx = run_setjy(ctx)
    return run_initial_bp(ctx)


def test_refant_set(initial_bp_ctx):
    assert "refAnt" in initial_bp_ctx and initial_bp_ctx["refAnt"]


def test_init_gain_table_exists(initial_bp_ctx):
    tbl = initial_bp_ctx["table_test_bp_init_gain"]
    assert tbl and Path(tbl).exists(), f"Init gain table missing: {tbl}"


def test_bp_table_exists(initial_bp_ctx):
    tbl = initial_bp_ctx["table_test_bp"]
    assert tbl and Path(tbl).exists(), f"BP table missing: {tbl}"


def test_corrected_column_populated(initial_bp_ctx):
    """CORRECTED_DATA should be written to calibrators.ms after applycal."""
    from casatools import table
    tb = table()
    tb.open(initial_bp_ctx["calibrators_ms"])
    try:
        cols = tb.colnames()
        assert "CORRECTED_DATA" in cols, "applycal did not create CORRECTED_DATA column"
        corrected = tb.getcol("CORRECTED_DATA")
        assert corrected is not None and corrected.size > 0
    finally:
        tb.close()
