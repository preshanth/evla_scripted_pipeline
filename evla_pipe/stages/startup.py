"""
Section 1 — startup stage.

Validates the SDM exists, creates the pipeline output directory tree, and
sets the workdir-rooted paths for all subsequent outputs.

Output directory layout
-----------------------
<workdir>/
    logs/
    plots/
    weblog/
    pipeline_context/
    final_caltables/
    intermediate_caltables/
    test_caltables/

workdir defaults to ``<sdm_stem>_pipeline/`` in the current working directory
if not already set in context by the caller (e.g. via --workdir or tests).
"""

import logging
from pathlib import Path

from evla_pipe.context import PipelineContext

log = logging.getLogger(__name__)

_SUBDIRS = [
    "logs",
    "plots",
    "weblog",
    "pipeline_context",
    "final_caltables",
    "intermediate_caltables",
    "test_caltables",
]


def run_startup(ctx: PipelineContext) -> PipelineContext:
    """
    Validate the SDM and create the output directory tree.

    Reads from context
    ------------------
    SDM_name, msname, workdir (may be empty — computed here if so)

    Writes to context
    -----------------
    workdir        : str  — absolute path to the pipeline output root
    calibrators_ms : str  — workdir/calibrators.ms
    """
    sdm_name = ctx["SDM_name"]
    msname = ctx["msname"]

    sdm_path = Path(sdm_name)
    ms_path = Path(msname)

    if not sdm_path.exists() and not ms_path.exists():
        raise FileNotFoundError(
            f"Neither SDM '{sdm_name}' nor MS '{msname}' found in {Path.cwd()}"
        )

    # Determine workdir — caller may have pre-set it (tests, --workdir flag)
    workdir_str = ctx.get("workdir", "")
    if not workdir_str:
        sdm_stem = sdm_path.stem if sdm_path.exists() else ms_path.stem
        workdir_str = str(Path.cwd() / f"{sdm_stem}_pipeline")

    workdir = Path(workdir_str)
    workdir.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (workdir / sub).mkdir(exist_ok=True)

    ctx["workdir"] = str(workdir)
    ctx["calibrators_ms"] = str(workdir / "calibrators.ms")

    log.info("Startup complete: workdir=%s", workdir)
    return ctx
