"""
Tests for run_apply_cals (and implicitly run_polcal + run_final_flags).

Runs the full pipeline through to target.ms split.
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
def apply_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.apply_cals import run_apply_cals
    from evla_pipe.stages.checkflag import run_checkflag
    from evla_pipe.stages.final_cals import run_final_cals
    from evla_pipe.stages.final_flags import run_final_flags
    from evla_pipe.stages.flux_gains import run_flux_gains
    from evla_pipe.stages.fluxboot import run_fluxboot
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.initial_bp import run_initial_bp
    from evla_pipe.stages.initial_rflag import run_initial_rflag
    from evla_pipe.stages.msmd import run_msmd
    from evla_pipe.stages.polcal import run_polcal
    from evla_pipe.stages.preflag import run_preflag
    from evla_pipe.stages.priorcals import run_priorcals
    from evla_pipe.stages.semi_final_bp import run_semi_final_bp
    from evla_pipe.stages.setjy import run_setjy
    from evla_pipe.stages.solint import run_solint
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.test_gains import run_test_gains

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx["do_pol"] = True
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
    ctx = run_test_gains(ctx)
    ctx = run_flux_gains(ctx)
    ctx = run_fluxboot(ctx)
    ctx = run_final_cals(ctx)
    ctx = run_polcal(ctx)
    ctx = run_apply_cals(ctx)
    return run_final_flags(ctx)


def test_target_ms_key_set(apply_ctx):
    assert "target_ms" in apply_ctx


def test_target_ms_exists(apply_ctx):
    target = apply_ctx.get("target_ms", "")
    if target:
        assert Path(target).exists(), f"target.ms not found at {target}"


def test_corrected_column_in_full_ms(apply_ctx):
    """CORRECTED_DATA column must exist in the full MS after applycal."""
    from casatools import table

    ms = apply_ctx["msname"]
    tb = table()
    tb.open(ms)
    try:
        cols = tb.colnames()
        assert "CORRECTED_DATA" in cols, "CORRECTED_DATA column missing after applycal"
    finally:
        tb.close()


def test_final_caltables_all_used(apply_ctx):
    """final_caltables must be non-empty (sanity: applycal had something to apply)."""
    assert len(apply_ctx["final_caltables"]) >= 4
