The test-suite is written against the results of the EVLA scripted pipeline
v1.4.2 on the test L Band dataset
`15A-397.sb31019491.eb31020561.57236.7198700463`. The SDM-BDF is about 7 GB in
size and can be downloaded from the NRAO [archive](https://data.nrao.edu). The
script assumes that the SDM-BDF has been renamed to `test.sdm`, that the real
model column is created, and that Hanning smoothing has been applied.

To run the full (integration) test-suite, call `pytest <path-to-"run_tests.py">`
from the command line in the directory where the pipeline has been run. The
full test-suite requires CASA (`casatools`), `numpy`, and access to the test
dataset described in this README.

Lightweight tests (recommended for CI and local quick checks)
-----------------------------------------------------------
There are some pure-Python/lightweight tests suitable for quick runs and CI.
To run the weblog-related lightweight test locally without CASA:

1. Create a virtual environment and install dev dependencies (example):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r ../dev-requirements.txt -c ../constraints.txt
```

2. Run the lightweight test:

```bash
pytest -q test/test_modern_weblog.py
```

This is the test the CI workflow runs by default; it does not require CASA.
