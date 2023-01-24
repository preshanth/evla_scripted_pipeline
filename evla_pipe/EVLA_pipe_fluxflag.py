"""
Flag `fluxgaincal.g` interactively to remove bad times/antennas.

Note: Because this is not part of the regular pipeline script, we do not
      perform runtiming, otherwise `EVLA_pipe_restart.py` doesn't work.
"""

from casaplotms import plotms

from . import pipeline_save
from .utils import runtiming

logprint("Starting EVLA_pipe_fluxflag.py", logfileout='logs/fluxflag.log')

plotms(
    vis="fluxgaincal.g",
    xaxis="time",
    yaxis="amp",
    showgui=False,
    plotfile="fluxgaincal_time_amp.png",
    highres=True,
    overwrite=True,
)

logprint("Finished EVLA_pipe_fluxflag.py", logfileout='logs/fluxflag.log')

pipeline_save()
