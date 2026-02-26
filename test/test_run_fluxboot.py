"""
Tests for run_flux_gains, run_fluxboot, and run_final_cals.

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
def fluxboot_ctx(pipeline_workdir, sdm_name):
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
    from evla_pipe.stages.flux_gains import run_flux_gains
    from evla_pipe.stages.fluxboot import run_fluxboot
    from evla_pipe.stages.final_cals import run_final_cals

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
    ctx = run_test_gains(ctx)
    ctx = run_flux_gains(ctx)
    ctx = run_fluxboot(ctx)
    return run_final_cals(ctx)


def test_flux_gaincal_exists(fluxboot_ctx):
    assert Path(fluxboot_ctx["table_flux_gaincal"]).exists()


def test_flux_gaincal_fcal_exists(fluxboot_ctx):
    assert Path(fluxboot_ctx["table_flux_gaincal_fcal"]).exists()


def test_final_delay_exists(fluxboot_ctx):
    assert Path(fluxboot_ctx["table_final_delay"]).exists()


def test_final_bp_exists(fluxboot_ctx):
    assert Path(fluxboot_ctx["table_final_bp"]).exists()


def test_final_phase_gain_exists(fluxboot_ctx):
    assert Path(fluxboot_ctx["table_final_phase_gain"]).exists()


def test_final_amp_gain_exists(fluxboot_ctx):
    assert Path(fluxboot_ctx["table_final_amp_gain"]).exists()


def test_final_caltables_nonempty(fluxboot_ctx):
    fc = fluxboot_ctx["final_caltables"]
    assert len(fc) >= 4, "Expected at least delay+BP+phase+amp in final_caltables"


def test_all_final_caltables_exist_on_disk(fluxboot_ctx):
    for tbl in fluxboot_ctx["final_caltables"]:
        assert Path(tbl).exists(), f"final_caltables entry missing: {tbl}"
