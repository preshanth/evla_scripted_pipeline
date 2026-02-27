"""
Shared pytest fixtures for the EVLA pipeline test suite.

Integration tests (those that run CASA against a real ASDM) are isolated
via the ``pipeline_workdir`` and ``sdm_name`` session-scoped fixtures.  All
CASA output is directed to a temporary directory so the project root stays
clean between runs.

Usage in a test module
----------------------
    def test_something(pipeline_workdir, sdm_name):
        from evla_pipe.context import make_default_context
        ctx = make_default_context(sdm_name)
        ctx["workdir"] = str(pipeline_workdir)
        ...
"""

import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Integration test SDM path
# ---------------------------------------------------------------------------

_SDM_ENV = os.environ.get("EVLA_TEST_SDM", "test.sdm")
# Resolve to absolute at import time so chdir inside tests doesn't break it
SDM_NAME = str(Path(_SDM_ENV).resolve())


@pytest.fixture(scope="session")
def sdm_name() -> str:
    """Absolute path to the test ASDM/SDM used by all integration tests."""
    return SDM_NAME


@pytest.fixture(scope="session")
def pipeline_workdir() -> Path:
    """
    Session-scoped output directory for pipeline integration tests.

    Fixed location under test/pipeline_output/ so outputs are inspectable
    between runs. The MS is deleted at the start of each run to ensure a
    clean import.

    NOTE: When resume support is added, the MS deletion here will need a
    guard — do not delete if resuming from an existing checkpoint.
    """
    import shutil

    here = Path(__file__).parent
    workdir = here / "pipeline_output" / "sdm_pipeline"
    workdir.mkdir(parents=True, exist_ok=True)

    # Blow up any existing MS so the pipeline starts from a clean import.
    # TODO: guard this when resume is implemented.
    ms_path = workdir / (Path(SDM_NAME).stem + ".ms")
    if ms_path.exists():
        shutil.rmtree(ms_path)

    return workdir
