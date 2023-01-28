# EVLA Scripted Pipeline
The EVLA scripted pipeline applies a series of heuristics and automated
procedures to calibrate EVLA observational data. Diagnostic plots and
information are also written to a series of HTML pages or a "weblog".

This repository contains an updated version of the scripted pipeline for use
with CASA v6 and Python v3.  The pipeline should work with both "monolithic"
and "modular" versions of CASA.

The pipeline is undergoing (or needs) significant refactoring to follow current
software best practices. It is, however, fairly straightforward to modify, as
each `EVLA_pipe_*.py` module is executed in turn at global scope. So to modify
the pipeline, either (1) edit an existing script or (2) create a new script and
add it to the `run_pipeline` function.


## Quickstart
To run the pipeline, first clone this repository:

```bash
git clone https://gitlab.nrao.edu/bsvoboda/evla-scripted-pipeline .
```

and then modify the `evla_pipe/__init__.py` file if needed. In addition to
CASA, the pipeline depends on `numpy` and `scipy`. These can be installed using
`pip` by running `pip install -r requirements.txt` from the shell.

Next, enter the directory containing the ASDM file to be calibrated and start
CASA if using the "monolithic" version or start a Python REPL if using the
"modular" version (i.e., `casatasks`, etc.). Below we import the pipeline
directory into our runtime path and call the main function.

```python
import sys
sys.path.append("path/to/pipeline")

from evla_pipe import run_pipeline
context = run_pipeline()
```

The first startup script will query the user for the name of the SDM and a few
other questions. Restarting and restoring an incomplete pipeline run has not
been well-tested.

Certain individual scripts can also be re-run if they don't mutate the global
state or the measurement set in a breaking way, or if one wants to simply
run individual scripts for testing purposes:

```python
from evla_pipe import run_pipeline, exec_script
context = run_pipeline()
# ... perform other actions to inspect or modify the data
context = exec_script("EVLA_pipe_plotsummary", context.copy())
context = exec_script("EVLA_pipe_weblog", context.copy())
```


## License
This repository is copyright 2013 by Associated Universities Inc. and released
under the GNU General Public License (GPL) version 2. See the `LICENSE` file
for the full license text. The scripted pipeline was originally authored, in
part, by Claire Chandler, Emmanuel Momjian, and Steve Myers of the NRAO between
2011 and 2014. The port to Python 3 was done by Brian Svoboda in 2023.
