"""
Facilitates the restart of the pipeline. The `EVLA_pipe_restore.py` script
needs to be run before this one.
"""

from . import exec_script
from .utils import logprint


pipeline_scripts = [
    "startup",
    "import",
    "hanning",
    "msinfo",
    "flagall",
    "calprep",
    "priorcals",
    "testBPdcals",
    "flag_baddeformatters",
    "flag_baddeformattersphase",
    "checkflag",
    "semiFinalBPdcals1",
    "checkflag_semiFinal",
    "semiFinalBPdcals1",
    "solint",
    "testgains",
    "fluxgains",
    "fluxboot",
    "finalcals",
    "applycals",
    "targetflag",
    "statwt",
    "plotsummary",
    "filecollect",
    "weblog",
]

# Last script that was started
last_state = time_list[-1]["pipestate"]
last_status = time_list[-1]["status"]

# Find index where we need to pick up at
script_index = [i for i, x in enumerate(pipeline_scripts) if last_state == x][0]

# If script ended successfully then start on next script
if last_status == "end":
    script_index += 1

if last_status == "start":
    time_list.pop(-1)

for script_name in pipeline_scripts[script_index:]:
    try:
        exec_script(f"EVLA_pipe_{script_name}", globals())
    except Exception as e:
        logprint(f"Exiting script: {e}")
    except KeyboardInterrupt as e:
        logprint(f"Keyboard Interrupt: {e}")
