"""
Tests for run_msmd.

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
def msmd_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import
    from evla_pipe.stages.msmd import run_msmd

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    ctx = run_import(ctx)
    return run_msmd(ctx)


def test_basic_dimensions(msmd_ctx):
    assert msmd_ctx["numSpws"] > 0
    assert msmd_ctx["numFields"] > 0
    assert msmd_ctx["numAntenna"] > 0


def test_corrstring(msmd_ctx):
    assert msmd_ctx["corrstring"] in ("RR,LL", "XX,YY")


def test_spw_lists_consistent(msmd_ctx):
    n = msmd_ctx["numSpws"]
    assert len(msmd_ctx["center_frequencies"]) == n
    assert len(msmd_ctx["channels"]) == n
    assert len(msmd_ctx["spw_names"]) == n


def test_tst_delay_spw_format(msmd_ctx):
    parts = msmd_ctx["tst_delay_spw"].split(",")
    assert len(parts) == msmd_ctx["numSpws"]
    for part in parts:
        assert ":" in part and "~" in part


def test_flux_calibrator_found(msmd_ctx):
    assert len(msmd_ctx["flux_field_list"]) > 0, (
        "No flux calibrator — check CALIBRATE_FLUX intent in the ASDM"
    )


def test_bandpass_calibrator_found(msmd_ctx):
    assert len(msmd_ctx["bandpass_field_list"]) > 0, (
        "No bandpass calibrator found"
    )


def test_calibrator_select_string_nonempty(msmd_ctx):
    assert msmd_ctx["calibrator_field_select_string"] != ""


def test_critfrac_values(msmd_ctx):
    assert msmd_ctx["critfrac"] >= msmd_ctx["critfrac_per_spw"] > 0


def test_startdate_reasonable(msmd_ctx):
    assert msmd_ctx["startdate"] > 50000  # MJD after 1995
