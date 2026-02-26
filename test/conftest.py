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
def pipeline_workdir(tmp_path_factory) -> Path:
    """
    Session-scoped isolated output directory for pipeline integration tests.

    All CASA outputs (calibration tables, MS files, logs, plots) are written
    here rather than into the project root.
    """
    return tmp_path_factory.mktemp("pipeline_run")
