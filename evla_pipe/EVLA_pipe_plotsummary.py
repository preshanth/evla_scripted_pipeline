"""
Make final *uv* plots on all sources.
"""

from casaplotms import plotms

from . import pipeline_save
from .utils import logprint, runtiming


def task_logprint(msg):
    logprint(msg, logfileout="logs/plotsummary.log")


task_logprint("Starting EVLA_pipe_plotsummary.py")
time_list = runtiming("plotsummary", "start")
QA2_plotsummary = "Pass"

task_logprint("Making final UV plots.")

plotms(
    vis=ms_active,
    xaxis="time",
    yaxis="phase",
    ydatacolumn="corrected",
    selectdata=True,
    field=calibrator_field_select_string,
    correlation=corrstring,
    averagedata=True,
    avgchannel=str(max(channels)),
    avgtime="1e8",
    avgscan=False,
    transform=False,
    extendflag=False,
    iteraxis="",
    coloraxis="antenna2",
    plotrange=[],
    title="Calibrated phase vs. time, all calibrators",
    xlabel="",
    ylabel="",
    showmajorgrid=False,
    showminorgrid=False,
    plotfile="all_calibrators_phase_time.png",
    overwrite=True,
    highres=True,
    showgui=False,
)

plotms(
    vis=ms_active,
    xaxis="time",
    yaxis="amp",
    ydatacolumn="residual",
    selectdata=True,
    field=calibrator_field_select_string,
    correlation=corrstring,
    averagedata=True,
    avgchannel=str(max(channels)),
    avgtime="1e8",
    avgscan=False,
    transform=False,
    extendflag=False,
    iteraxis="",
    coloraxis="antenna2",
    plotrange=[],
    title="Corrected-model amp vs. time, all calibrators",
    xlabel="",
    ylabel="",
    showmajorgrid=False,
    showminorgrid=False,
    plotfile="all_calibrators_resid_amp_time.png",
    overwrite=True,
    highres=True,
    showgui=False,
)

for ii in field_ids:
    print(f"-- Field ID {ii}")
    plotms(
        vis=ms_active,
        xaxis="uvwave",
        yaxis="amp",
        ydatacolumn="corrected",
        selectdata=True,
        field=str(ii),
        correlation=corrstring,
        averagedata=True,
        avgchannel=str(max(channels)),
        avgtime="1e8",
        avgscan=False,
        transform=False,
        extendflag=False,
        iteraxis="",
        coloraxis="spw",
        plotrange=[],
        title=f"Field {field}, {field_names[ii]}",
        xlabel="",
        ylabel="",
        showmajorgrid=False,
        showminorgrid=False,
        plotfile=f"field{field}_amp_uvdist.png",
        overwrite=True,
        highres=True,
        showgui=False,
    )

# Make Amp vs. Freq plots per field per baseband for newer data sets that have
# the band, baseband and spw info, such as 'EVLA_X#A0C0#0'.
if "#" in spw_names[0]:
    for ii in field_ids:
        for BB in spws_info:
            band = BB[0]
            bband = BB[1]
            bbspw = BB[2]
            if band == "X" and len(bbspw) == 1:
                print("-- ", band, bband, bbspw)
                task_logprint(
                    "Seems to have encountered a reference pointing spw; "
                    "Amp vs. Freq plots will not be made for this spw."
                )
            else:
                print("-- ", band, bband, bbspw)
                plotms(
                    vis=ms_active,
                    xaxis="freq",
                    yaxis="amp",
                    ydatacolumn="corrected",
                    selectdata=True,
                    field=str(ii),
                    correlation=corrstring,
                    spw=str(bbspw).strip("[]"),
                    averagedata=True,
                    avgtime="1e8",
                    avgscan=True,
                    avgantenna=True,
                    transform=False,
                    extendflag=False,
                    iteraxis="",
                    coloraxis="antenna1",
                    plotrange=[0, 0, 0, 0],
                    title=f"Field {field}, {field_names[ii]}, {band}-Band, {bband}, spw={bbspw}",
                    xlabel="",
                    ylabel="",
                    showmajorgrid=False,
                    showminorgrid=False,
                    plotfile=f"field{field}_{band}-Band_{bband}_amp_freq.png",
                    overwrite=True,
                    highres=True,
                    showgui=False,
                )
else:
    task_logprint(
        "These are old EVLA data; will make one Amp vs. Freq plot per "
        "field with all available spectral windows"
    )
    for ii in field_ids:
        plotms(
            vis=ms_active,
            xaxis="freq",
            yaxis="amp",
            ydatacolumn="corrected",
            selectdata=True,
            field=str(ii),
            correlation=corrstring,
            averagedata=True,
            avgtime="1e8",
            avgscan=True,
            avgantenna=True,
            transform=False,
            extendflag=False,
            iteraxis="",
            coloraxis="antenna1",
            plotrange=[0, 0, 0, 0],
            title="Field {field}, {field_names[ii]}",
            xlabel="",
            ylabel="",
            showmajorgrid=False,
            showminorgrid=False,
            plotfile="field{field}_amp_freq.png",
            overwrite=True,
            highres=True,
            showgui=False,
        )

# Make Phase vs. Freq plots per field per baseband for newer data sets that
# have the band, baseband and spw info such as 'EVLA_X#A0C0#0'.
if "#" in spw_names[0]:
    for ii in field_ids:
        for BB in spws_info:
            band = BB[0]
            bband = BB[1]
            bbspw = BB[2]
            if band == "X" and len(bbspw) == 1:
                print("-- ", band, bband, bbspw)
                task_logprint(
                    "Seems to have encountered a reference pointing spw; "
                    "Phase vs. Freq plots will not be made for this spw."
                )
            else:
                print("-- ", band, bband, bbspw)
                plotms(
                    vis=ms_active,
                    xaxis="freq",
                    yaxis="phase",
                    ydatacolumn="corrected",
                    selectdata=True,
                    field=str(ii),
                    correlation=corrstring,
                    spw=str(bbspw).strip("[]"),
                    averagedata=True,
                    avgtime="1e8",
                    avgscan=True,
                    avgantenna=True,
                    transform=False,
                    extendflag=False,
                    iteraxis="",
                    coloraxis="antenna1",
                    plotrange=[0, 0, -180, 180],
                    title=f"Field {field}, {field_names[ii]}, {band}-Band {bband}, spw={bbspw}",
                    xlabel="",
                    ylabel="",
                    showmajorgrid=False,
                    showminorgrid=False,
                    plotfile=f"field{field}_{band}-Band_{bband}_phase_freq.png",
                    overwrite=True,
                    highres=True,
                    showgui=False,
                )
else:
    task_logprint(
        "These are old EVLA data; will make one Phase vs. Freq plot per "
        "field with all available spectral windows."
    )
    for ii in field_ids:
        plotms(
            vis=ms_active,
            xaxis="freq",
            yaxis="phase",
            ydatacolumn="corrected",
            selectdata=True,
            field=str(ii),
            correlation=corrstring,
            averagedata=True,
            avgtime="1e8",
            avgscan=True,
            avgantenna=True,
            transform=False,
            extendflag=False,
            iteraxis="",
            coloraxis="antenna1",
            plotrange=[0, 0, -180, 180],
            title=f"Field {field}, {field_names[ii]}",
            xlabel="",
            ylabel="",
            showmajorgrid=False,
            showminorgrid=False,
            plotfile=f"field{field}_phase_freq.png",
            overwrite=True,
            showgui=False,
        )


task_logprint(f"QA2 score: {QA2_plotsummary}")
task_logprint("Finished EVLA_pipe_plotsummary.py")
time_list = runtiming("plotsummary", "end")

pipeline_save()
