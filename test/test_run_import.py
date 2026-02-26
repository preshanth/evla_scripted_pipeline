"""
Tests for run_import.

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
def import_ctx(pipeline_workdir, sdm_name):
    from evla_pipe.context import make_default_context
    from evla_pipe.stages.startup import run_startup
    from evla_pipe.stages.import_data import run_import

    ctx = make_default_context(sdm_name)
    ctx["workdir"] = str(pipeline_workdir)
    ctx = run_startup(ctx)
    return run_import(ctx)


def test_ms_exists(import_ctx):
    assert Path(import_ctx["msname"]).exists()


def test_flagonline_txt_written(import_ctx):
    assert Path(import_ctx["flagonline_txt"]).exists()


def test_import_is_idempotent(import_ctx):
    """Second call must skip the import and return the same context."""
    from evla_pipe.stages.import_data import run_import
    ctx2 = run_import(import_ctx)
    assert ctx2["msname"] == import_ctx["msname"]
