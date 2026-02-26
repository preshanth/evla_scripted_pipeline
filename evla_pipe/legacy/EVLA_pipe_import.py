# EVLA_pipe_import.py

import shutil

from casatasks import importasdm

from evla_pipe.utils import (
    MEASUREMENT_SETS_DIR,
    cleanup_import_files,
    format_qa_status,
    get_measurement_set_path,
    logprint,
    runtiming,
)


def task_logprint(msg):
    logprint(msg, logfileout="logs/import.log")


def import_data(pipeline_context):
    """
    Imports the SDM data into a CASA measurement set.

    Args:
        pipeline_context (dict): A dictionary containing the pipeline's context,
                                 including variables like SDM_name and msname.

    Returns:
        dict: Updated pipeline context. Returns "Fail" if critical parameters are missing.
    """
    SDM_name = pipeline_context.get("SDM_name")
    msname = pipeline_context.get("msname")

    if not SDM_name or not msname:
        logprint(
            "Error: Missing SDM_name or msname in pipeline context for import_data.",
            logfileout="logs/import.log",
        )
        return {"QA2_import": "Fail"}

    def task_logprint(msg):
        return logprint(msg, logfileout="logs/import.log")

    task_logprint("*** Starting import_data ***")
    time_list = runtiming("import", "start")
    QA2_import = "Pass"

    # Get organized paths
    ms_path = get_measurement_set_path(msname)
    flags_path = MEASUREMENT_SETS_DIR / "onlineFlags.txt"

    # Clean up any existing files that might interfere
    task_logprint("Cleaning up existing files...")
    cleanup_import_files(SDM_name)

    # Update context with organized paths
    pipeline_context["msname"] = str(ms_path)
    pipeline_context["ms_active"] = str(ms_path)

    if not ms_path.exists():
        task_logprint("Creating measurement set")
        try:
            importasdm(
                asdm=SDM_name,
                vis=str(ms_path),
                ocorr_mode="co",
                compression=False,
                asis="",
                process_flags=True,
                applyflags=False,
                savecmds=True,
                outfile=str(flags_path),
                flagbackup=False,
                overwrite=False,
                verbose=True,
            )
            task_logprint(f"Measurement set '{ms_path}' created")
            task_logprint("Copying xml files to the output ms")
            for xml_file in ("Flag", "Antenna", "SpectralWindow"):
                shutil.copy2(f"{SDM_name}/{xml_file}.xml", f"{ms_path}/")
        except Exception as e:
            task_logprint(f"Error during importasdm: {e}")
            QA2_import = "Fail"
            return {"QA2_import": QA2_import}
    else:
        task_logprint(f"Measurement set already exists, will use '{ms_path}'")

    task_logprint("Finished import_data")
    time_list = runtiming("import", "end")

    # Update context with results and organized paths
    pipeline_context["QA2_import"] = QA2_import
    pipeline_context["time_list"] = time_list
    pipeline_context["onlineFlags_path"] = str(flags_path)

    # Log the organized structure
    task_logprint(f"Measurement set: {ms_path}")
    task_logprint(f"Online flags: {flags_path}")
    task_logprint(f"All import products organized in: {MEASUREMENT_SETS_DIR}")

    return pipeline_context


def EVLA_pipe_import(pipeline_context):
    """
    Main entry point for EVLA_pipe_import pipeline step.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_import.py ***")
    time_list = runtiming("import", "start")

    # Extract variables from context
    pipeline_context.get("msname", "")

    try:
        # Call the main function
        result = import_data(pipeline_context)
        pipeline_context.update(result)
        QA2_score = result.get("QA2_import", "Pass")
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_import: {e}")
        QA2_score = "Fail"

    task_logprint("Finished EVLA_pipe_import.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("import", "end")

    # Update context and return
    pipeline_context["QA2_import"] = QA2_score
    pipeline_context["time_list"] = time_list

    return pipeline_context
