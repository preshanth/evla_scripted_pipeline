# EVLA Scripted Pipeline

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CASA 6.1+](https://img.shields.io/badge/CASA-6.1+-green.svg)](https://casa.nrao.edu/)

Automated continuum calibration pipeline for VLA data. Produces calibrated
target visibilities and diagnostic output from a raw ASDM in a single run.

---

## Requirements

- Python 3.10+ (required by CASA wheels)
- CASA 6.1+ (`casatools`, `casatasks`) — only needed for pipeline execution
- `numpy`, `scipy`

---

## Installation

```bash
git clone <repository-url> evla-pipeline
cd evla-pipeline

# Lightweight install (no CASA — for development and unit tests)
python -m pip install -c constraints.txt -e .

# With CASA extras
pip install -c constraints.txt -e .[casa]

# Developer setup (lint + test tooling via pixi)
pixi install
```

---

## Usage

```bash
# Basic run — output goes to <sdm_stem>_pipeline/ in the current directory
evla-pipeline your_data.asdm

# Specify output directory explicitly
evla-pipeline your_data.asdm --workdir /data/run1

# Enable polarization calibration (KCROSS + Df)
evla-pipeline your_data.asdm --polarization

# Apply Hanning smoothing after import
evla-pipeline your_data.asdm --hanning

# Auto-resume from the last successful stage checkpoint
evla-pipeline your_data.asdm --resume

# Resume from a specific stage (all prior stages are skipped)
evla-pipeline your_data.asdm --resume-from fluxboot

# Skip a stage
evla-pipeline your_data.asdm --skip run_final_flags

# Verbose logging (DEBUG level)
evla-pipeline your_data.asdm -v

# Or run as a module
python -m evla_pipe your_data.asdm --polarization
```

---

## Resume and checkpointing

A checkpoint is written atomically to `pipeline_context/checkpoint.json` after
each stage completes. If a run is interrupted (crash, Ctrl-C, wall-time limit),
you can resume without repeating completed work:

```bash
# Auto-resume — skips all stages already in the checkpoint
evla-pipeline your_data.asdm --resume

# Resume from a specific stage — skips everything before it
evla-pipeline your_data.asdm --resume-from fluxboot
evla-pipeline your_data.asdm --resume-from run_fluxboot   # both forms accepted
```

**Notes:**

- `--resume` reads the checkpoint from the same workdir the pipeline would use
  (default `<sdm_stem>_pipeline/`, or `--workdir` if specified).
- `run_msmd` always re-runs on resume — MS metadata contains numpy arrays that
  are not persisted in the checkpoint and must be re-derived.
- `run_startup` always re-runs — it is a no-op when directories already exist.
- `run_import` has its own disk guard and is a no-op if the MS already exists.
- Hanning smoothing writes a `<sdm>.hanning_done` marker after the first
  successful smooth; subsequent runs skip it automatically.
- The checkpoint validates that the SDM name and `--polarization` flag match
  the original run. Mismatches raise an error before any stages execute.

---

## Output layout

All pipeline outputs are written to the workdir (default `<sdm_stem>_pipeline/`):

```
TDRW0001_pipeline/
├── logs/
├── plots/
├── weblog/
├── pipeline_context/
│   └── checkpoint.json       (written after each stage; enables --resume)
├── final_caltables/
│   ├── gain_curves.g
│   ├── opacities.g
│   ├── finaldelay.k
│   ├── finalBPcal.b
│   ├── finalphasegaincal.g
│   ├── finalampgaincal.g
│   ├── kcross.g          (polarization only)
│   └── dterms.d          (polarization only)
├── intermediate_caltables/
├── test_caltables/
├── calibrators.ms
└── target.ms
```

The full MS (`<sdm>.ms`) is written to the working directory by `importasdm`
and is not moved.

---

## Pipeline stages

| # | Function | Description |
|---|---|---|
| 1 | `run_startup` | Validate SDM, create output directory tree |
| 2 | `run_import` | `importasdm` → MS |
| 3 | `run_hanning` | Hanning smooth (optional, `--hanning`) |
| 4 | `run_msmd` | Populate context from MS metadata |
| 5 | `run_preflag` | Online + shadow + tfcrop flags; split `calibrators.ms` |
| 6 | `run_priorcals` | Gain curves, opacities, requantizer, antenna positions |
| 7 | `run_setjy` | Flux + polarization models on `calibrators.ms` |
| 8 | `run_initial_bp` | Short phase gain + initial bandpass |
| 9 | `run_initial_rflag` | rflag/tfcrop on residual; optional BP re-solve |
| 10 | `run_semi_final_bp` | Pass 1: delay + BP + applycal on `calibrators.ms` |
| 11 | `run_checkflag` | rflag on corrected `calibrators.ms` |
| 12 | `run_semi_final_bp` | Pass 2 (intentional repeat after checkflag) |
| 13 | `run_solint` | Determine `gain_solint2` from scan durations |
| 14 | `run_test_gains` | Validate `gain_solint2` via flag fraction |
| 15 | `run_flux_gains` | Re-setjy flux cals + solve `fluxgaincal.g` |
| 16 | `run_fluxboot` | `fluxscale` + power-law fit + setjy on all cals |
| 17 | `run_final_cals` | Final delay + BP + phase + amp tables |
| 18 | `run_polcal` | KCROSS + Df (no-op if `--polarization` not set) |
| 19 | `run_apply_cals` | `applycal` full MS + `statwt` + split `target.ms` |
| 20 | `run_final_flags` | rflag on `target.ms` |

---

## Python API

```python
from evla_pipe.pipeline import continuum

# Fresh run
ctx = continuum(
    sdm_name="your_data.asdm",
    enable_polarization=True,
    workdir="/data/run1",
)
print(ctx["target_ms"])   # path to the calibrated target MS

# Resume from last checkpoint
ctx = continuum(
    sdm_name="your_data.asdm",
    workdir="/data/run1",
    resume=True,
)
```

---

## Testing

Two tiers:

**Lightweight** (no CASA, runs in CI):
```bash
pixi run pytest test/test_run_startup.py
pytest -q test/test_simple_utils.py
```

**Integration** (requires CASA + test ASDM):
```bash
export EVLA_TEST_SDM=/path/to/your.asdm
pixi run -e casa test
```

Integration tests are isolated — all CASA output goes to a pytest
`tmp_path` directory and does not pollute the project root.

---

## Architecture notes

- `evla_pipe/stages/` — one file per pipeline stage; each exports a single
  `run_<name>(ctx) -> ctx` function
- `evla_pipe/context.py` — `PipelineContext` TypedDict; single source of
  truth for all pipeline state; no CASA imports
- `evla_pipe/pipeline.py` — orchestrator; a plain list of function calls
- `evla_pipe/legacy/` — original `EVLA_pipe_*.py` scripts retained for
  reference; not imported by the active pipeline
- `evla_pipe/compat.py` — gates all CASA imports; package imports cleanly
  without CASA installed

---

## License & Credits

**License**: GNU General Public License (GPL) v2+
**Copyright**: 2013–2025 Associated Universities Inc.

**Original authors:** Claire Chandler, Emmanuel Momjian, Steve Myers (NRAO)
**Python 3 port:** Brian Svoboda (2023)
**Polarization integration:** Kelly Sanderson (2024)
**Refactor:** Preshanth Jagannathan (2024–2025)
