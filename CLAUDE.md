# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Lightweight tests (no CASA required) — runs in CI
pixi run pytest test/test_simple_utils.py test/test_run_weblog.py -q

# Lint (scoped to actively maintained modules)
pixi run lint

# CASA integration tests — requires real ASDM + casa pixi env
EVLA_TEST_SDM=data/TDRW0001.sb35624494.eb35628826.58395.23719237269 \
  pixi run -e casa pytest test/test_run_e2e.py -v -s

# E2E reference value discovery (run once to populate REF_* in test_run_e2e.py)
EVLA_TEST_SDM=data/TDRW0001.sb35624494.eb35628826.58395.23719237269 \
  pixi run -e casa pytest test/test_run_e2e.py::test_print_reference_values -v -s

# Run the pipeline
python -m evla_pipe.cli your_data.asdm
python -m evla_pipe.cli --enable-polarization your_data.asdm
python -m evla_pipe.cli --workdir /path/to/output your_data.asdm
```

## Architecture

### Entry point
`evla_pipe/pipeline.py::continuum()` is the sole orchestrator. It calls each stage
via `_timed(name, label, func, ctx)` which records timing into `ctx["stage_records"]`.
`run_weblog` runs last in a `try/finally` so a partial weblog is always written.
CLI is `evla_pipe/cli.py`, registered as `evla-pipeline` in pyproject.toml.

### Stage model
Each stage is a pure function: `def run_X(ctx: PipelineContext) -> PipelineContext`.
All stage files live in `evla_pipe/stages/`. Legacy EVLA_pipe_*.py files are in
`evla_pipe/legacy/` (archival, not imported by the active pipeline).

### Stage sequence (pipeline.py)
1. `run_startup` — create workdir + subdirs
2. `run_import` — importasdm → MS
3. `run_hanning` — Hanning smooth (skippable via skip_hanning=True)
4. `run_msmd` — populate context from MS metadata
5. `run_preflag` — online + shadow + tfcrop; split calibrators.ms
6. `run_priorcals` — gaincurve, opacities, requantizer, antpos
7. `run_setjy` — flux + pol models
8. `run_initial_bp` — short BP solve
9. `run_initial_rflag` — rflag on residuals
10. `run_semi_final_bp` (pass 1) — delay + BP + applycal on calibrators.ms
11. `run_checkflag` — rflag on corrected calibrators.ms
12. `run_semi_final_bp` (pass 2, intentional repeat after checkflag)
13. `run_solint` — determine gain solution interval
14. `run_test_gains` — validate solint
15. `run_flux_gains` — flux-bootstrapped gain solve
16. `run_fluxboot` — fluxscale + power-law fit + setjy
17. `run_final_cals` — final delay + BP + phase + amp tables
18. `run_polcal` — polarization cal (no-op if do_pol=False)
19. `run_apply_cals` — applycal full MS + statwt + split target.ms
20. `run_final_flags` — rflag on target.ms
21. `run_weblog` — generate workdir/weblog/index.html (always runs)

### Context dict is the backbone
`evla_pipe/context.py` defines `PipelineContext` (TypedDict, total=False) — the
sole inter-stage interface. `run_msmd` (stage 4) populates the bulk of it.
Key accumulator lists: `priorcals`, `final_caltables`, `pol_caltables`, `stage_records`.
No CASA imports in context.py — importable without CASA.

### workdir layout
```
workdir/                       (default: <sdm_stem>_pipeline/ in CWD)
  logs/                        per-stage log files
  plots/                       diagnostic PNGs
  weblog/index.html            HTML diagnostic report
  pipeline_context/            JSON checkpoints
  final_caltables/             tables passed to applycal
  intermediate_caltables/
  test_caltables/
  calibrators.ms               split calibrators-only MS
  target.ms                    split target MS (post-applycal)
```

### Plot naming convention
`{stage_prefix}_{quantity}_{dim_key}_{dim_val}.png`
- stage prefixes: `initial_bp`, `semi_final_bp`, `test_gains`, `flux_gains`, `final_cals`, `delay`, `polcal`
- quantity: `amp`, `phase`, `ap` (both)
- dimensions: `spw_{N}`, `ant_{name}`, `solint_{val}`, `pass_{N}`
- Example: `semi_final_bp_ap_spw_0_pass_1.png`

### Weblog
`evla_pipe/weblog.py` renders `workdir/weblog/index.html` from ctx + stage_records.
Pure Python f-string templating, zero JS, zero CDN, works at file://.
Flat scroll with sticky TOC sidebar. `<details open>` for FAIL/PARTIAL log excerpts.

### Two-tier test split
- **Lightweight** (`test/test_simple_utils.py`, `test/test_run_weblog.py`): no CASA, run in CI.
- **Integration** (`test/test_run_e2e.py`, `test/test_run_*.py`): requires CASA + real ASDM.
  E2E test runs full pipeline once (session fixture) and checks calibration values.
  `REF_*` constants at top of `test_run_e2e.py` are populated after first reference run.

### CASA dependency isolation
Stage files import CASA at module level — they raise ImportError cleanly when CASA
is absent. Lightweight tests never import stage files. `evla_pipe/context.py`,
`evla_pipe/weblog.py`, `evla_pipe/simple_utils.py` have zero CASA imports.

## Key constraints

- `protobuf==3.20.3` pinned in casa pixi feature — required for CASA compatibility.
- `setuptools` pinned in casa pixi feature — casatasks needs `pkg_resources` at startup.
- `semiFinalBPdcals` runs **twice** (stages 10 and 12) — intentional, second pass uses updated flags.
- `hanningsmooth` requires a distinct `outputvis` in current CASA — smoothed to `.hanning` temp, then replaced.
- `usescratch=True` required in all `setjy` calls — MODEL column must be written explicitly.
- `run_weblog` always runs via `try/finally` in pipeline.py — even partial runs produce a weblog.
- Lint scope is `evla_pipe/stages/ evla_pipe/weblog.py evla_pipe/pipeline.py evla_pipe/context.py evla_pipe/cli.py` — legacy/ and utils.py excluded (pre-existing debt, tracked separately).
- `ruff format` is the formatter of record. Do not run `black`.
