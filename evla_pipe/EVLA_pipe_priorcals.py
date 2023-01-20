"""
Prior calibrations
==================
This module calculates deterministic calibration steps such as gain curves,
opacities, antenna position corrections, and requantizer gains.
"""

import os

from casatasks import gencal
from casaplotms import plotms

from . import pipeline_save
from .utils import runtiming, logprint, correct_ant_posns


def task_logprint(msg):
    logprint(msg, logfileout="logs/priorcals.log")


task_logprint("Starting EVLA_pipe_priorcals.py")
time_list = runtiming("priorcals", "start")
QA2_priorcals = "Pass"

priorcals = []

# Table for elevation gain curves
gencal(
    vis=ms_active,
    caltable="gain_curves.g",
    caltype="gc",
    spw="",
    antenna="",
    pol="",
    parameter=[],
)
priorcals.append("gain_curves.g")

# Table for atmospheric opacities
gencal(
    vis=ms_active,
    caltable="opacities.g",
    caltype="opac",
    spw=all_spw,
    antenna="",
    pol="",
    parameter=tau,
)
priorcals.append("opacities.g")

# Apply switched power calibration (when commissioned); for now, just
# requantizer gains (needs casa4.1!), and only for data with sensible switched
# power tables (Feb 24, 2011)
feb_24_2011 = 55616.6  # mjd
if startdate >= feb_24_2011:
    gencal(
        vis=ms_active,
        caltable="requantizergains.g",
        caltype="rq",
        spw="",
        antenna="",
        pol="",
        parameter=[],
    )
    priorcals.append("requantizergains.g")

# Correct for antenna position errors, if known.
# NB: for the realtime pipeline these will not be available yet, but all
# SBs that do not have good antenna positions should be re-processed when
# they are available
try:
    gencal(
        vis=ms_active,
        caltable="antposcal.p",
        caltype="antpos",
        spw="",
        antenna="",
        pol="",
        parameter=[],
    )
    if os.path.exists("antposcal.p"):
        priorcals.append("antposcal.p")
        antenna_offsets = correct_ant_posns(ms_active)
        task_logprint("Correcting for known antenna position errors")
        task_logprint(str(antenna_offsets))
    else:
        task_logprint("No antenna position corrections found/needed")
except:
    task_logprint("No antenna position corrections found/needed")

# Lastly, make switched power table.  This is not used in the pipeline, but may
# be used for QA and for flagging, especially at S-band for fields near the
# geostationary satellite belt.  Only relevant for data taken on 24-Feb-2011 or
# later.
if startdate >= feb_24_2011:
    gencal(
        vis=ms_active,
        caltable="switched_power.g",
        caltype="swpow",
        spw="",
        antenna="",
        pol="",
        parameter=[],
    )
    # Plot switched power gain and system temperature. The factors of 3 are for
    # generating sets of 3x3 sub-plots paginated by antenna.
    task_logprint("Plotting switched power table")
    nplots = int(numAntenna / 3)
    if (numAntenna % 3) > 0:
        nplots += 1
    for ii in range(nplots):
        ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
        for plotfile, yaxis in (
                (f"switched_power{ii}.png", "spgain"),
                (f"Tsys{ii}.png", "tsys"),
        ):
            plotms(
                vis="switched_power.g",
                xaxis="time",
                yaxis=yaxis,
                correlation="R",
                antenna=ant_select,
                spw="",
                timerange="",
                gridrows=3,
                coloraxis="spw",
                iteraxis="antenna",
                plotrange=[],
                showgui=False,
                plotfile=plotfile,
                highres=True,
                overwrite=True,
            )

# Until we know what error messages to search for in priorcals,
# leave QA2 score set to "Pass".

task_logprint(f"QA2 score: {QA2_priorcals}")
task_logprint("Finished EVLA_pipe_priorcals.py")
time_list = runtiming("priorcals", "end")

pipeline_save()
