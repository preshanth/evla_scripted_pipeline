"""
EVLA continuum calibration pipeline — orchestrator.

Entry point: ``continuum(sdm_name, ...)``

Stage sequence
--------------
1.  run_startup       — output directories
2.  run_import        — importasdm → MS
3.  run_hanning       — Hanning smooth (skippable)
4.  run_msmd          — populate context from MS metadata
5.  run_preflag       — online + shadow + tfcrop flags; split calibrators.ms
6.  run_priorcals     — gaincurve, opacities, requantizer, antpos
7.  run_setjy         — flux + pol models on calibrators.ms
8.  run_initial_bp    — short BP solve + applycal
9.  run_initial_rflag — rflag/tfcrop on residual; optional BP re-solve
10. run_semi_final_bp — pass 1: delay + BP + applycal on calibrators.ms
11. run_checkflag     — rflag on corrected calibrators.ms
12. run_semi_final_bp — pass 2 (intentional duplicate)
13. run_solint        — determine gain_solint2 from scan durations
14. run_test_gains    — validate gain_solint2 via flag fraction
15. run_flux_gains    — re-setjy flux cals + solve fluxgaincal.g
16. run_fluxboot      — fluxscale + power-law fit + setjy
17. run_final_cals    — final delay + BP + phase + amp tables
18. run_polcal        — KCROSS + Df (no-op if do_pol=False)
19. run_apply_cals    — applycal full MS + statwt + split target.ms
20. run_final_flags   — rflag on target.ms
21. run_weblog        — generate workdir/weblog/index.html (always runs)
"""

import time
from pathlib import Path

from evla_pipe.context import (
    PipelineContext,
    load_checkpoint,
    make_default_context,
    save_checkpoint,
)
from evla_pipe.stages.apply_cals import run_apply_cals
from evla_pipe.stages.cal_diagnostics import run_cal_diagnostics
from evla_pipe.stages.checkflag import run_checkflag
from evla_pipe.stages.final_cals import run_final_cals
from evla_pipe.stages.final_flags import run_final_flags
from evla_pipe.stages.flux_gains import run_flux_gains
from evla_pipe.stages.fluxboot import run_fluxboot
from evla_pipe.stages.import_data import run_hanning, run_import
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
from evla_pipe.weblog import run_weblog

try:
    from evla_pipe import __version_str__
except ImportError:
    __version_str__ = "unknown"


# Ordered list of (name, label, func) for all pipeline stages.
# The orchestrator loops over this to support resume/skip logic.
STAGE_SEQUENCE = [
    ("startup", "Startup", run_startup),
    ("import", "Import ASDM", run_import),
    ("hanning", "Hanning Smooth", run_hanning),
    ("msmd", "MS Metadata", run_msmd),
    ("preflag", "Pre-flag", run_preflag),
    ("priorcals", "Prior Calibrations", run_priorcals),
    ("setjy", "Set Flux Model", run_setjy),
    ("initial_bp", "Initial Bandpass", run_initial_bp),
    ("initial_rflag", "Initial RFlag", run_initial_rflag),
    ("semi_final_bp_1", "Semi-final BP (pass 1)", run_semi_final_bp),
    ("checkflag", "Checkflag", run_checkflag),
    ("semi_final_bp_2", "Semi-final BP (pass 2)", run_semi_final_bp),
    ("solint", "Solution Interval", run_solint),
    ("test_gains", "Test Gains", run_test_gains),
    ("flux_gains", "Flux Gains", run_flux_gains),
    ("fluxboot", "Flux Bootstrap", run_fluxboot),
    ("final_cals", "Final Calibrations", run_final_cals),
    ("polcal", "Polarization Cal", run_polcal),
    ("apply_cals", "Apply Calibrations", run_apply_cals),
    ("final_flags", "Final Flags", run_final_flags),
    ("cal_diagnostics", "Calibrator Diagnostics", run_cal_diagnostics),
]


def _build_resume_skip_set(
    ctx: PipelineContext,
    workdir: str | None,
    resume_from: str | None,
    skip_steps: list | None,
) -> tuple[PipelineContext, set[str]]:
    """Load checkpoint and return (updated_ctx, skip_set).

    Called only when ``resume`` or ``resume_from`` is set.
    """
    _workdir = workdir or (Path(ctx.get("SDM_name", "")).stem + "_pipeline")
    loaded_ctx, completed, fingerprint = load_checkpoint(_workdir)
    _check_fingerprint(fingerprint, ctx)

    # Restore checkpoint state, then re-apply CLI overrides
    sdm = ctx.get("SDM_name", "")
    do_pol = ctx.get("do_pol", False)
    do_hanning = ctx.get("do_hanning", True)
    enable_plots = ctx.get("enable_plots", True)
    ctx = loaded_ctx
    ctx["SDM_name"] = sdm
    ctx["do_pol"] = do_pol
    ctx["do_hanning"] = do_hanning
    ctx["enable_plots"] = enable_plots
    if workdir:
        ctx["workdir"] = workdir

    skip_set: set[str] = set(skip_steps or [])
    if resume_from:
        target = resume_from.removeprefix("run_")
        for name, _, _ in STAGE_SEQUENCE:
            if name == target:
                break
            skip_set.add(name)
    else:
        skip_set.update(completed)

    # msmd always re-runs (field_positions not persisted); startup is safe to re-run
    skip_set.discard("msmd")
    skip_set.discard("startup")
    return ctx, skip_set


def _run_stages(
    ctx: PipelineContext,
    skip_set: set[str],
    skip_hanning: bool,
    verbose: bool,
) -> PipelineContext:
    """Execute STAGE_SEQUENCE, skipping stages in skip_set."""

    def _timed(name: str, label: str, func) -> PipelineContext:
        nonlocal ctx
        if verbose:
            print(f":: {label}")
        t0 = time.monotonic()
        ctx = func(ctx)
        dt = time.monotonic() - t0
        ctx.setdefault("stage_records", []).append(
            {"name": name, "label": label, "duration_s": round(dt, 1)}
        )
        save_checkpoint(ctx, name)
        return ctx

    try:
        for name, label, func in STAGE_SEQUENCE:
            if name == "hanning" and skip_hanning:
                continue
            if name in skip_set:
                if verbose:
                    print(f":: SKIP {label} (checkpoint)")
                continue
            ctx = _timed(name, label, func)
    finally:
        ctx = run_weblog(ctx)
    return ctx


def _check_fingerprint(stored: dict, ctx: PipelineContext) -> None:
    """Raise ValueError if checkpoint was made for a different SDM or pol setting."""
    if stored.get("SDM_name") != ctx.get("SDM_name"):
        raise ValueError(
            f"Checkpoint SDM '{stored['SDM_name']}' does not match "
            f"current SDM '{ctx['SDM_name']}'. Wrong workdir?"
        )
    if stored.get("do_pol") != ctx.get("do_pol"):
        raise ValueError(
            "Polarization flag differs from checkpoint. "
            "Use --force-resume to override (not yet implemented)."
        )


def continuum(
    sdm_name: str,
    skip_hanning: bool = False,
    verbose: bool = False,
    context: dict | None = None,
    enable_polarization: bool = False,
    enable_plots: bool = True,
    workdir: str | None = None,
    resume: bool = False,
    resume_from: str | None = None,
    skip_steps: list | None = None,
) -> PipelineContext:
    """
    Run the EVLA continuum calibration pipeline.

    Parameters
    ----------
    sdm_name : str
        SDM directory name (without .ms extension).
    skip_hanning : bool
        Skip Hanning smoothing (recommended for spectral line projects).
    verbose : bool
        Print stage banners to stdout.
    context : dict, optional
        Seed context.  A fresh default context is used if None.
    enable_polarization : bool
        Enable polarization calibration (default: False).
    enable_plots : bool
        Enable plotting output (default: True).
    resume : bool
        Auto-resume from last checkpoint in workdir.
    resume_from : str, optional
        Resume from a specific stage name (e.g. "fluxboot" or "run_fluxboot").
        All prior stages are skipped.
    skip_steps : list, optional
        Explicit list of stage names to skip.

    Returns
    -------
    PipelineContext
        Final pipeline context (includes weblog_path if weblog was written).
    """
    if verbose:
        print(f":: Starting EVLA continuum pipeline v{__version_str__}")

    ctx: PipelineContext = (
        make_default_context(sdm_name) if context is None else dict(context)
    )

    # Seed top-level inputs
    ctx["SDM_name"] = sdm_name
    ctx["do_pol"] = enable_polarization
    ctx["do_hanning"] = not skip_hanning
    ctx["enable_plots"] = enable_plots
    if workdir:
        ctx["workdir"] = workdir

    # --- Resume: build skip_set ---
    skip_set: set[str] = set()
    if resume or resume_from:
        ctx, skip_set = _build_resume_skip_set(ctx, workdir, resume_from, skip_steps)
    elif skip_steps:
        skip_set = set(skip_steps)

    ctx = _run_stages(ctx, skip_set, skip_hanning, verbose)

    if verbose:
        print(f":: Pipeline complete — weblog: {ctx.get('weblog_path', 'not written')}")

    return ctx
