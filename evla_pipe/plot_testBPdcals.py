# plot_testBPdcals.py (Separate plotting script - Continued)

import os
from evla_pipe.plotting import plotms
from casatools import table
from evla_pipe.utils import runtiming, logprint
import numpy as np

def task_logprint(msg):
    logprint(msg, logfileout="logs/testBPdcals_plots.log")

def plot_test_bandpass_and_delay(pipeline_context):
    """
    Plots the results of the test bandpass and delay calibration.
    """
    task_logprint("*** Starting plotting test bandpass and delay calibration results ***")
    time_list = runtiming("testBPdcals_plot", "start")

    ms_active = pipeline_context.get("msname")
    numAntenna = pipeline_context.get("numAntenna", 0)
    corrstring = pipeline_context.get("corrstring", "RR,LL") # Provide a default
    bandpass_field_select_string = pipeline_context.get("bandpass_field_select_string", "")
    bandpass_scan_select_string = pipeline_context.get("bandpass_scan_select_string", "")
    delay_scan_select_string = pipeline_context.get("delay_scan_select_string", "")

    nplots = int(numAntenna / 3) + (1 if (numAntenna % 3) > 0 else 0)

    # --- Plot test delays ---
    task_logprint("Plotting test delays")
    for ii in range(nplots):
        plotfile = f"testdelay{ii}.png"
        os.system(f"rm -rf {plotfile}")
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        plotms(
            vis="testdelay.k",
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
    task_logprint("Plotting test delays complete")

    # --- Plot amplitude gain solutions ---
    task_logprint("Plotting amplitude gain solutions")
    for ii in range(nplots):
        plotfile = f"testBPdinitialgainamp{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="testBPdinitialgain.g",
            xaxis="time",
            yaxis="amp",
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
    task_logprint("Plotting amplitude gain solutions complete")

    # --- Plot phase gain solutions ---
    task_logprint("Plotting phase gain solutions")
    for ii in range(nplots):
        plotfile = f"testBPdinitialgainphase{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="testBPdinitialgain.g",
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
    task_logprint("Plotting phase gain solutions complete")

    # --- Plot BP solutions ---
    task_logprint("Plotting bandpass solutions")
    try:
        tb = table()
        tb.open("testBPcal.b")
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
            tmparr_amp = amps[good]
            if len(tmparr_amp) > 0:
                maxamp = np.max(amps[good])
                if maxamp > maxmaxamp:
                    maxmaxamp = maxamp
            tmparr_phase = np.abs(phases[good])
            if len(tmparr_phase) > 0:
                maxphase = np.max(np.abs(phases[good])) * 180.0 / np.pi
                if maxphase > maxmaxphase:
                    maxmaxphase = maxphase
    except Exception as e:
        task_logprint(f"Error opening or reading testBPcal.b: {e}")
        if tb.isopen():
            tb.close()
        return

    ampplotmax = maxmaxamp
    phaseplotmax = maxmaxphase

    for ii in range(nplots):
        plotfile = f"testBPcal_amp{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="testBPcal.b",
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
        plotfile = f"testBPcal_phase{ii}.png"
        ant_select = str(ii * 3) + "~" + str(min(ii * 3 + 2, numAntenna - 1))
        os.system(f"rm -rf {plotfile}")
        plotms(
            vis="testBPcal.b",
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
    task_logprint("Plotting of test bandpass solutions complete")

    # --- Plot calibrated bandpass and delay calibrators ---
    task_logprint("Plot calibrated bandpass and delay calibrators")
    os.system("rm -rf testcalibratedBPcal.png")
    plotms(
        vis=ms_active,
        xaxis="freq",
        yaxis="amp",
        ydatacolumn="corrected",
        selectdata=True,
        field=bandpass_field_select_string,
        scan=bandpass_scan_select_string,
        correlation=corrstring,
        averagedata=True,
        avgtime="1e8",
        avgscan=True,
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
        plotfile="testcalibratedBPcal.png",
        showgui=False,
        highres=True,
        overwrite=True,
    )
    task_logprint("Plotting calibrated bandpass calibrator complete")

    # Plot calibrated delay calibrator, if different from BP cal
    if delay_scan_select_string != bandpass_scan_select_string:
        os.system("rm -rf testcalibrated_delaycal.png")
        plotms(
            vis=ms_active,
            xaxis="freq",
            yaxis="amp",
            ydatacolumn="corrected",
            selectdata=True,
            scan=delay_scan_select_string,
            correlation=corrstring,
            averagedata=True,
            avgtime="1e8",
            avgscan=True,
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
            plotfile="testcalibrated_delaycal.png",
            overwrite=True,
            showgui=False,
            highres=True,
        )
        task_logprint("Plotting calibrated delay calibrator complete")

    task_logprint("Finished plotting test bandpass and delay calibration results")
    time_list = runtiming("testBPdcals_plot", "end")