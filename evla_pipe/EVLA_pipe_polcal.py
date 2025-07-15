# EVLA_pipe_polcal.py

"""
Polarization calibration module for EVLA pipeline.

This module performs polarization calibration including:
- Cross-hand delay calibration (Xf)
- D-term leakage calibration (Df)

This script should run after finalcals but before applycals so that
the polarization calibration tables can be included in the calibration
application.
"""

from casatasks import gaincal, polcal
from evla_pipe.utils import runtiming, logprint, get_log_path, get_caltable_path


def task_logprint(msg):
    logprint(msg, logfileout=str(get_log_path("polcal.log")))


def EVLA_pipe_polcal(pipeline_context):
    """
    Perform polarization calibration (Df, Xf) for the EVLA pipeline.
    
    This function performs:
    1. Cross-hand delay calibration (Xf) 
    2. D-term leakage calibration (Df)
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing MS name and calibration information
        
    Returns
    -------
    dict
        Updated pipeline context with polarization calibration tables
    """
    task_logprint("*** Starting EVLA_pipe_polcal.py ***")
    time_list = runtiming("polcal", "start")
    QA2_polcal = "Pass"
    
    # Get context variables
    ms_active = pipeline_context.get("msname")
    do_pol = pipeline_context.get("do_pol", False)
    
    if not do_pol:
        task_logprint("Polarization calibration disabled, skipping polcal")
        return pipeline_context
        
    if not ms_active:
        task_logprint("ERROR: No measurement set specified")
        QA2_polcal = "Fail"
        return pipeline_context
        
    # Get calibration tables from context
    priorcals = []
    
    # Add delay calibration table
    if "delay_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["delay_cal_table"])
        task_logprint(f"Using delay table: {pipeline_context['delay_cal_table']}")
        
    # Add bandpass calibration table  
    if "bpass_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["bpass_cal_table"])
        task_logprint(f"Using bandpass table: {pipeline_context['bpass_cal_table']}")
        
    # Add gain calibration table
    if "gain_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["gain_cal_table"])
        task_logprint(f"Using gain table: {pipeline_context['gain_cal_table']}")
    elif "phase_int_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["phase_int_cal_table"])
        task_logprint(f"Using phase table: {pipeline_context['phase_int_cal_table']}")
        
    # Get polarization calibrator information
    pol_angle_field = pipeline_context.get("pol_angle_field")
    pol_leakage_field = pipeline_context.get("pol_leakage_field") 
    refant = pipeline_context.get("refant", "")
    
    # If no specific pol calibrators specified, try to find standard ones
    if pol_angle_field is None or pol_leakage_field is None:
        standard_source_names = pipeline_context.get("standard_source_names", ["3C48", "3C138", "3C147", "3C286"])
        field_names = pipeline_context.get("field_names", [])
        
        # Find polarization calibrators
        pol_angle_field = None
        pol_leakage_field = None
        
        for i, field_name in enumerate(field_names):
            if any(std in field_name.upper() for std in standard_source_names):
                if "3C286" in field_name.upper() or "3C138" in field_name.upper():
                    pol_angle_field = i  # Good for angle calibration
                if pol_leakage_field is None:
                    pol_leakage_field = i  # Any standard calibrator for leakage
                    
        task_logprint(f"Auto-detected polarization calibrators: angle={pol_angle_field}, leakage={pol_leakage_field}")
    
    if pol_angle_field is None or pol_leakage_field is None:
        task_logprint("WARNING: No polarization calibrators found, skipping polarization calibration")
        QA2_polcal = "Partial"
        return pipeline_context
        
    try:
        # Step 1: Cross-hand delay calibration (Xf)
        task_logprint("Performing cross-hand delay calibration (Xf)")
        
        kcross_table = str(get_caltable_path(ms_active, "Xf"))
        
        gaincal(
            vis=ms_active,
            caltable=kcross_table,
            field=str(pol_angle_field),
            spw="",
            intent="",
            selectdata=True,
            uvrange="",
            scan="",
            solint="inf",
            combine="scan",
            preavg=-1.0,
            refant=refant,
            minblpercal=4,
            minsnr=3.0,
            solnorm=False,
            gaintype="KCROSS",
            smodel=[],
            calmode="p",
            append=False,
            docallib=False,
            gaintable=priorcals,
            gainfield=[],
            interp=[],
            spwmap=[],
            parang=True
        )
        
        task_logprint(f"Cross-hand delay calibration completed: {kcross_table}")
        pipeline_context["kcross_cal_table"] = kcross_table
        
        # Step 2: D-term leakage calibration (Df)
        task_logprint("Performing D-term leakage calibration (Df)")
        
        dterms_table = str(get_caltable_path(ms_active, "Df"))
        
        # Create gaintable list including the new Xf table
        pol_gaintables = priorcals + [kcross_table]
        
        polcal(
            vis=ms_active,
            caltable=dterms_table,
            field=str(pol_leakage_field),
            spw="",
            intent="",
            selectdata=True,
            uvrange="",
            scan="",
            solint="inf",
            combine="scan,field",
            preavg=-1.0,
            refant="",
            minblpercal=4,
            minsnr=3.0,
            poltype="Df",
            smodel=[],
            append=False,
            docallib=False,
            gaintable=pol_gaintables,
            gainfield=[],
            interp=[],
            spwmap=[],
            parang=True
        )
        
        task_logprint(f"D-term leakage calibration completed: {dterms_table}")
        pipeline_context["dterms_cal_table"] = dterms_table
        
        # Update context with all polarization tables
        pol_cal_tables = [kcross_table, dterms_table]
        pipeline_context["pol_cal_tables"] = pol_cal_tables
        pipeline_context["polarization_calibrated"] = True
        
        task_logprint("Polarization calibration completed successfully")
        
    except Exception as e:
        task_logprint(f"ERROR in polarization calibration: {e}")
        QA2_polcal = "Fail"
        pipeline_context["polarization_calibrated"] = False
        pipeline_context["polarization_error"] = str(e)
        
    task_logprint("Finished EVLA_pipe_polcal.py")
        # Import colored output function
    from evla_pipe.utils import format_qa_status
    task_logprint(f"QA2 score: {format_qa_status(QA2_polcal)}")
    time_list = runtiming("polcal", "end")
    
    # Update context and return
    pipeline_context["QA2_polcal"] = QA2_polcal
    pipeline_context["time_list"] = time_list
    
    return pipeline_context