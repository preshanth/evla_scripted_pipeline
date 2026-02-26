"""
Tests for run_semi_final_bp (called twice) and run_checkflag.

Requires CASA and a real ASDM. Set EVLA_TEST_SDM to the ASDM path.
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
def semi_final_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.msmd import run_msmd
    from evla_pipe.stages.preflag import run_preflag
    from evla_pipe.stages.priorcals import run_priorcals
    from evla_pipe.stages.setjy import run_setjy
    from evla_pipe.stages.initial_bp import run_initial_bp
    from evla_pipe.stages.initial_rflag import run_initial_rflag
    from evla_pipe.stages.semi_final_bp import run_semi_final_bp
    from evla_pipe.stages.checkflag import run_checkflag

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    ctx = run_import(ctx)
    ctx = run_msmd(ctx)
    ctx = run_preflag(ctx)
    ctx = run_priorcals(ctx)
    ctx = run_setjy(ctx)
    ctx = run_initial_bp(ctx)
    ctx = run_initial_rflag(ctx)
    ctx = run_semi_final_bp(ctx)   # first pass
    ctx = run_checkflag(ctx)
    ctx = run_semi_final_bp(ctx)   # second pass
    return ctx


def test_delay_table_exists(semi_final_ctx):
    assert Path(semi_final_ctx["table_delay"]).exists()


def test_bp_table_exists(semi_final_ctx):
    assert Path(semi_final_ctx["table_bp"]).exists()


def test_semifinal_init_gain_exists(semi_final_ctx):
    assert Path(semi_final_ctx["table_semifinal_delay_init_gain"]).exists()


def test_corrected_column_populated(semi_final_ctx):
    from casatools import table
    tb = table()
    tb.open(semi_final_ctx["calibrators_ms"])
    try:
        assert "CORRECTED_DATA" in tb.colnames()
    finally:
        tb.close()
