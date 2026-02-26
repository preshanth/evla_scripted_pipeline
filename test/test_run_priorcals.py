"""
Tests for run_priorcals.

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
def priorcals_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.msmd import run_msmd
    from evla_pipe.stages.preflag import run_preflag
    from evla_pipe.stages.priorcals import run_priorcals

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    ctx = run_import(ctx)
    ctx = run_msmd(ctx)
    ctx = run_preflag(ctx)
    return run_priorcals(ctx)


def test_priorcals_list_nonempty(priorcals_ctx):
    assert len(priorcals_ctx["priorcals"]) >= 2, (
        "Expected at least gain_curves + opacities in priorcals"
    )


def test_gain_curves_table_exists(priorcals_ctx):
    tbl = priorcals_ctx["table_gain_curves"]
    assert tbl and Path(tbl).exists(), f"Gain curves table missing: {tbl}"


def test_opacities_table_exists(priorcals_ctx):
    tbl = priorcals_ctx["table_opacities"]
    assert tbl and Path(tbl).exists(), f"Opacities table missing: {tbl}"


def test_priorcals_all_exist_on_disk(priorcals_ctx):
    for tbl in priorcals_ctx["priorcals"]:
        assert Path(tbl).exists(), f"priorcals entry missing on disk: {tbl}"


def test_priorcals_in_final_caltables_dir(priorcals_ctx):
    for tbl in priorcals_ctx["priorcals"]:
        assert "final_caltables" in tbl, (
            f"Expected prior cal in final_caltables/: {tbl}"
        )
