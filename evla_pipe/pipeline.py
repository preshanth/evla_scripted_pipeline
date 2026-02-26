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
"""

import warnings

from evla_pipe.context import PipelineContext, make_default_context
from evla_pipe.stages.apply_cals import run_apply_cals
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

try:
    from evla_pipe import __version_str__
except ImportError:
    __version_str__ = "unknown"


def continuum(
    sdm_name: str,
    skip_hanning: bool = False,
    verbose: bool = False,
    context: dict | None = None,
    enable_polarization: bool = False,
    enable_plots: bool = True,
    workdir: str | None = None,
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
    resume_from : str, optional
        Unused — reserved for future resume support.
    skip_steps : list, optional
        Unused — reserved for future skip support.

    Returns
    -------
    PipelineContext
        Final pipeline context.
    """
    if resume_from or skip_steps:
        warnings.warn(
            "resume_from and skip_steps are not yet implemented"
            " in the refactored pipeline",
            stacklevel=2,
        )

    if verbose:
        print(f":: Starting EVLA continuum pipeline v{__version_str__}")

    ctx: PipelineContext = make_default_context() if context is None else dict(context)

    # Seed top-level inputs
    ctx["SDM_name"] = sdm_name
    ctx["do_pol"] = enable_polarization
    ctx["do_hanning"] = not skip_hanning
    ctx["enable_plots"] = enable_plots
    if workdir:
        ctx["workdir"] = workdir

    def _step(name: str) -> None:
        if verbose:
            print(f":: {name}")

    _step("startup")
    ctx = run_startup(ctx)

    _step("import")
    ctx = run_import(ctx)

    if not skip_hanning:
        _step("hanning")
        ctx = run_hanning(ctx)

    _step("msmd")
    ctx = run_msmd(ctx)

    _step("preflag + calibrators.ms split")
    ctx = run_preflag(ctx)

    _step("priorcals")
    ctx = run_priorcals(ctx)

    _step("setjy")
    ctx = run_setjy(ctx)

    _step("initial BP")
    ctx = run_initial_bp(ctx)

    _step("initial rflag")
    ctx = run_initial_rflag(ctx)

    _step("semiFinalBPdcals pass 1")
    ctx = run_semi_final_bp(ctx)

    _step("checkflag")
    ctx = run_checkflag(ctx)

    _step("semiFinalBPdcals pass 2")
    ctx = run_semi_final_bp(ctx)

    _step("solint")
    ctx = run_solint(ctx)

    _step("test gains")
    ctx = run_test_gains(ctx)

    _step("flux gains")
    ctx = run_flux_gains(ctx)

    _step("fluxboot")
    ctx = run_fluxboot(ctx)

    _step("final cals")
    ctx = run_final_cals(ctx)

    _step("polcal")
    ctx = run_polcal(ctx)

    _step("applycal + statwt + split")
    ctx = run_apply_cals(ctx)

    _step("final flags on target.ms")
    ctx = run_final_flags(ctx)

    if verbose:
        print(":: Pipeline completed successfully")

    return ctx
