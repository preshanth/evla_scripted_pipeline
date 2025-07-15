"""
Make final *uv* plots on all sources.
"""

from evla_pipe.plotting import plotms
from evla_pipe.utils import logprint, runtiming, format_qa_status

def task_logprint(msg):
    logprint(msg, logfileout="logs/plotsummary.log")

def create_final_plots(pipeline_context):
    """
    Create final UV plots on all sources.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
    """
    task_logprint("*** Starting create_final_plots ***")
    time_list = runtiming("plotsummary", "start")
    QA2_plotsummary = "Pass"

    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")
    corrstring = pipeline_context.get("corrstring", "")
    channels = pipeline_context.get("channels", [64])  # Default channel count
    field_ids = pipeline_context.get("field_ids", [])
    field_names = pipeline_context.get("field_names", {})
    spw_names = pipeline_context.get("spw_names", [""])
    spws_info = pipeline_context.get("spws_info", [])

    task_logprint("Making final UV plots.")

    try:
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
                title=f"Field {ii}, {field_names.get(ii, 'Unknown')}",
                xlabel="",
                ylabel="",
                showmajorgrid=False,
                showminorgrid=False,
                plotfile=f"field{ii}_amp_uvdist.png",
                overwrite=True,
                highres=True,
                showgui=False,
            )

        # Amp vs. Freq plots per field per baseband for newer data sets
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
                            title=f"Field {ii}, {field_names.get(ii, 'Unknown')}, {band}-Band, {bband}, spw={bbspw}",
                            xlabel="",
                            ylabel="",
                            showmajorgrid=False,
                            showminorgrid=False,
                            plotfile=f"field{ii}_{band}-Band_{bband}_amp_freq.png",
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
                    title=f"Field {ii}, {field_names.get(ii, 'Unknown')}",
                    xlabel="",
                    ylabel="",
                    showmajorgrid=False,
                    showminorgrid=False,
                    plotfile=f"field{ii}_amp_freq.png",
                    overwrite=True,
                    highres=True,
                    showgui=False,
                )

        # Phase vs. Freq plots per field per baseband for newer data sets
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
                            title=f"Field {ii}, {field_names.get(ii, 'Unknown')}, {band}-Band {bband}, spw={bbspw}",
                            xlabel="",
                            ylabel="",
                            showmajorgrid=False,
                            showminorgrid=False,
                            plotfile=f"field{ii}_{band}-Band_{bband}_phase_freq.png",
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
                    title=f"Field {ii}, {field_names.get(ii, 'Unknown')}",
                    xlabel="",
                    ylabel="",
                    showmajorgrid=False,
                    showminorgrid=False,
                    plotfile=f"field{ii}_phase_freq.png",
                    overwrite=True,
                    highres=True,
                    showgui=False,
                )

        task_logprint(f"QA2 score: {format_qa_status(QA2_plotsummary)}")
    except Exception as e:
        task_logprint(f"Error in create_final_plots: {e}")
        QA2_plotsummary = "Fail"

    task_logprint("Finished EVLA_pipe_plotsummary.py")
    time_list = runtiming("plotsummary", "end")
    pipeline_context["QA2_plotsummary"] = QA2_plotsummary
    pipeline_context["time_list"] = time_list
    return pipeline_context

def EVLA_pipe_plotsummary(pipeline_context):
    """
    Main entry point for EVLA_pipe_plotsummary pipeline step.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_plotsummary.py ***")
    time_list = runtiming("plotsummary", "start")

    # Extract variables from context
    ms_active = pipeline_context.get("msname", "")
    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    channels = pipeline_context.get("channels", [1])
    field_ids = pipeline_context.get("field_ids", [])
    field_names = pipeline_context.get("field_names", {})

    try:
        task_logprint("Making final UV plots.")

        # Plot 1: Calibrated phase vs. time, all calibrators
        plotms(
            vis=ms_active,
            xaxis="time",
            yaxis="phase",
            ydatacolumn="corrected",
            selectdata=True,
            field=calibrator_field_select_string,
            correlation=corrstring,
            averagedata=True,
            avgchannel=str(max(channels)) if channels else "1",
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

        # Plot 2: Corrected-model amp vs. time, all calibrators
        plotms(
            vis=ms_active,
            xaxis="time",
            yaxis="amp",
            ydatacolumn="residual",
            selectdata=True,
            field=calibrator_field_select_string,
            correlation=corrstring,
            averagedata=True,
            avgchannel=str(max(channels)) if channels else "1",
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

        # Plot 3: Individual field plots
        for ii in field_ids:
            plotms(
                vis=ms_active,
                xaxis="uvwave",
                yaxis="amp",
                ydatacolumn="corrected",
                selectdata=True,
                field=str(ii),
                correlation=corrstring,
                averagedata=True,
                avgchannel=str(max(channels)) if channels else "1",
                avgtime="1e8",
                avgscan=False,
                transform=False,
                extendflag=False,
                iteraxis="",
                coloraxis="spw",
                plotrange=[],
                title=f"Field {ii}, {field_names.get(ii, 'Unknown')}",
                xlabel="",
                ylabel="",
                showmajorgrid=False,
                showminorgrid=False,
                plotfile=f"field_{ii}_amp_uvwave.png",
                overwrite=True,
                highres=True,
                showgui=False,
            )

        QA2_score = "Pass"

    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_plotsummary: {e}")
        QA2_score = "Fail"

    task_logprint(f"Finished EVLA_pipe_plotsummary.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("plotsummary", "end")

    # Update context and return
    pipeline_context["QA2_plotsummary"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context
