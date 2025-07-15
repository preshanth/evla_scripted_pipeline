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
    corrstring = pipeline_context.get("corrstring", "RR,LL")
    channels = pipeline_context.get("channels", [64])  # Default channel count
    target_field_select_string = pipeline_context.get("target_field_select_string", "")
    
    task_logprint("Making final UV plots.")

    try:
        # Skip plotting if no calibrator fields defined
        if not calibrator_field_select_string:
            task_logprint("No calibrator fields defined, skipping calibrator plots")
        else:
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
                title="Calibrated amplitude vs. time, all calibrators",
                xlabel="",
                ylabel="",
                showmajorgrid=False,
                showminorgrid=False,
                plotfile="all_calibrators_amp_time.png",
                overwrite=True,
                highres=True,
                showgui=False,
            )

        # Skip target plots if no target fields defined
        if not target_field_select_string:
            task_logprint("No target fields defined, skipping target plots")
        else:
            plotms(
                vis=ms_active,
                xaxis="time",
                yaxis="phase",
                ydatacolumn="corrected",
                selectdata=True,
                field=target_field_select_string,
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
                title="Calibrated phase vs. time, all targets",
                xlabel="",
                ylabel="",
                showmajorgrid=False,
                showminorgrid=False,
                plotfile="all_targets_phase_time.png",
                overwrite=True,
                highres=True,
                showgui=False,
            )

            plotms(
                vis=ms_active,
                xaxis="time",
                yaxis="amp",
                ydatacolumn="corrected",
                selectdata=True,
                field=target_field_select_string,
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
                title="Calibrated amplitude vs. time, all targets",
                xlabel="",
                ylabel="",
                showmajorgrid=False,
                showminorgrid=False,
                plotfile="all_targets_amp_time.png",
                overwrite=True,
                highres=True,
                showgui=False,
            )

        task_logprint("Finished creating final plots")
        
    except Exception as e:
        task_logprint(f"Error creating plots: {e}")
        QA2_plotsummary = "Fail"

    task_logprint(f"QA2 score: {format_qa_status(QA2_plotsummary)}")
    time_list = runtiming("plotsummary", "end")
    
    return QA2_plotsummary

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
    
    try:
        # Call the main function if it exists
        if "create_final_plots" in globals():
            QA2_score = create_final_plots(pipeline_context)
        else:
            # Default implementation - this needs to be customized per script
            QA2_score = "Pass"
            task_logprint("Default implementation - needs customization")
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
