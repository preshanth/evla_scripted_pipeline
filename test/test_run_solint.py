"""
Tests for run_solint and run_test_gains.

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
def solint_ctx(pipeline_workdir, sdm_name):
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
    from evla_pipe.stages.solint import run_solint
    from evla_pipe.stages.test_gains import run_test_gains

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
    ctx = run_semi_final_bp(ctx)
    ctx = run_checkflag(ctx)
    ctx = run_semi_final_bp(ctx)
    ctx = run_solint(ctx)
    return run_test_gains(ctx)


def test_gain_solint1_is_string(solint_ctx):
    s = solint_ctx["gain_solint1"]
    assert isinstance(s, str) and s.endswith("s")


def test_gain_solint2_is_string(solint_ctx):
    s = solint_ctx["gain_solint2"]
    assert isinstance(s, str) and s.endswith("s")


def test_gain_solint2_positive(solint_ctx):
    val = float(solint_ctx["gain_solint2"].rstrip("s"))
    assert val > 0


def test_test_gaincal_exists(solint_ctx):
    assert Path(solint_ctx["table_test_gaincal"]).exists()
