# plot_test_gains.py

from casatasks import rmtables
from casatools import table
from casaplotms import plotms
import numpy as np
import os

tb = table()

def task_logprint(msg):
    logprint(msg, logfileout="logs/testgains_plot.log")

def plot_test_gain_solutions(pipeline_context, nplots):
    """
    Plot the amplitude and phase of the test gain solutions.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
        nplots (int): Number of plots to generate per type.
    """
    task_logprint("*** Starting plot_test_gain_solutions.py ***")
    runtiming("testgains_plot", "start")

    numAntenna = pipeline_context.get("numAntenna", 0)

    # Get maximum unflagged amplitude for plot maximum.
    maxamp = 1.0
    if os.path.exists("testgaincal.g"):
        try:
            tb.open("testgaincal.g")
            cpar = tb.getcol("CPARAM")
            flgs = tb.getcol("FLAG")
            amps = np.abs(cpar)
            good = np.logical_not(flgs)
            if np.any(amps[good]):
                maxamp = np.max(amps[good])
            else:
                task_logprint("WARNING: No unflagged amplitude data found in testgaincal.g for plotting range.")
        except Exception as e:
            task_logprint(f"Error opening or reading testgaincal.g: {e}")
        finally:
            tb.close()
    else:
        task_logprint("WARNING: testgaincal.g not found, using default amplitude plot range.")

    # Plot time vs amplitude for gain solutions.
    task_logprint("Plotting amplitude gain solutions.")
    for ii in range(nplots):
        plotfile = f"testgaincal_amp{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="testgaincal.g",
            xaxis="time",
            yaxis="amp",
            antenna=ant_select,
            spw="",
            timerange="",
            gridrows=3,
            coloraxis="spw",
            iteraxis="antenna",
            plotrange=[0, 0, 0, maxamp * 1.1], # Add a small buffer to the max
            showgui=False,
            plotfile=plotfile,
            highres=True,
            overwrite=True,
        )
    task_logprint("Plotting phase gain solutions")
    for ii in range(nplots):
        plotfile = f"testgaincal_phase{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="testgaincal.g",
            xaxis="time",
            yaxis="phase",
            antenna=ant_select,
            spw="",
            timerange="",
            gridrows=3,
            coloraxis="spw",
            iteraxis="antenna",
            plotrange=[0, 0, -180, 180],
            showgui=False,
            plotfile=plotfile,
            highres=True,
            overwrite=True,
        )
    task_logprint("Plotting finished.")

    runtiming("testgains_plot", "end")