# plot_semi_final_cals.py (Continued)

import os
from casaplotms import plotms
from casatools import table
from .utils import logprint, runtiming
import numpy as np

tb = table()

def task_logprint(msg):
    logprint(msg, logfileout="logs/semiFinalBPdcals1_plots.log")

def plot_semi_final_calibration_results(pipeline_context):
    """
    Plots the results of the semi-final delay and bandpass calibrations.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
    """
    task_logprint("*** Starting plotting semi-final delay and BP calibration results ***")
    time_list = runtiming("semiFinalBPdcals1_plot", "start")

    ms_active = pipeline_context.get("msname")
    numAntenna = pipeline_context.get("numAntenna", 0)
    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")

    nplots = int(numAntenna / 3) + (1 if (numAntenna % 3) > 0 else 0)

    # --- Plotting delays ---
    task_logprint("Plotting delays")
    for ii in range(nplots):
        plotfile = f"delay{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="delay.k",
            xaxis="freq",
            yaxis="delay",
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
    task_logprint("Plotting delays complete")

    # --- Plotting initial phase gain calibration on BP calibrator ---
    task_logprint("Plotting initial phase gain calibration on BP calibrator")
    for ii in range(nplots):
        plotfile = f"BPinitialgainphase{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="BPdinitialgain.g",
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
    task_logprint("Plotting initial phase gain calibration on BP calibrator complete")

    # --- Plotting bandpass solutions ---
    task_logprint("Plotting bandpass solutions")
    try:
        tb.open("BPcal.b")
        dataVarCol = tb.getvarcol("CPARAM")
        flagVarCol = tb.getvarcol("FLAG")
        rowlist = dataVarCol.keys()
        maxmaxamp = 0.0
        maxmaxphase = 0.0
        for rrow in rowlist:
            dataArr = dataVarCol[rrow]
            flagArr = flagVarCol[rrow]
            amps = np.abs(dataArr)
            phases = np.arctan2(np.imag(dataArr), np.real(dataArr))
            good = np.logical_not(flagArr)
            tmparr = amps[good]
            if len(tmparr) > 0:
                maxamp = np.max(amps[good])
                if maxamp > maxmaxamp:
                    maxmaxamp = maxamp
            tmparr = np.abs(phases[good])
            if len(tmparr) > 0:
                maxphase = np.max(np.abs(phases[good])) * 180.0 / np.pi
                if maxphase > maxmaxphase:
                    maxmaxphase = maxphase
    except Exception as e:
        task_logprint(f"Error opening or reading BPcal.b: {e}")
        if tb.isopen():
            tb.close()
        return

    ampplotmax = maxmaxamp
    phaseplotmax = maxmaxphase

    for ii in range(nplots):
        plotfile = f"BPcal_amp{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="BPcal.b",
            xaxis="freq",
            yaxis="amp",
            antenna=ant_select,
            spw="",
            timerange="",
            gridrows=3,
            coloraxis="spw",
            iteraxis="antenna",
            plotrange=[0, 0, 0, ampplotmax],
            showgui=False,
            plotfile=plotfile,
            highres=True,
            overwrite=True,
        )

    for ii in range(nplots):
        plotfile = f"BPcal_phase{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="BPcal.b",
            xaxis="freq",
            yaxis="phase",
            antenna=ant_select,
            spw="",
            timerange="",
            gridrows=3,
            coloraxis="spw",
            iteraxis="antenna",
            plotrange=[0, 0, -phaseplotmax, phaseplotmax],
            showgui=False,
            plotfile=plotfile,
            highres=True,
            overwrite=True,
        )
    task_logprint("Plotting bandpass solutions complete")

    # --- Plot calibrated calibrators to check for further flagging/RFI ---
    task_logprint("Plot calibrated calibrators to check for further flagging/RFI")
    os.system("rm -rf semifinalcalibratedcals1.png")
    plotms(
        vis=ms_active,
        xaxis="freq",
        yaxis="amp",
        ydatacolumn="corrected",
        selectdata=True,
        scan=pipeline_context.get("calibrator_scan_select_string", ""),
        correlation=corrstring,
        averagedata=True,
        avgtime="1e8",
        avgscan=False,
        transform=False,
        extendflag=False,
        iteraxis="",
        coloraxis="antenna2",
        plotrange=[],
        title="",
        xlabel="",
        ylabel="",
        showmajorgrid=False,
        showminorgrid=False,
        plotfile="semifinalcalibratedcals1.png",
        showgui=False,
        highres=True,
        overwrite=True,
    )
    task_logprint("Plotting calibrated calibrators complete")

    task_logprint("Finished plotting semi-final delay and BP calibration results")
    time_list = runtiming("semiFinalBPdcals1_plot", "end")