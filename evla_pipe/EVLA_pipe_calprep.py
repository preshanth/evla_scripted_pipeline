# EVLA_pipe_calprep.py (Refactored)

from casatasks import setjy
from casatools import measures as mstool
from evla_pipe.utils import runtiming, logprint, find_EVLA_band, find_standards , format_qa_status
from evla_pipe.pol_setjy_utils import integrate_polarization_setjy


me = mstool()

def task_logprint(msg):
    logprint(msg, logfileout="logs/calprep.log")

def EVLA_pipe_calprep(pipeline_context):
    """
    Prepare for calibrations: Set models for primary calibrators.
    """
    task_logprint("*** Starting EVLA_pipe_calprep.py (Refactored) ***")
    time_list = runtiming("calprep", "start")
    QA2_calprep = "Pass"

    ms_active = pipeline_context.get("msname")
    field_positions = pipeline_context.get("field_positions")
    field_spws = pipeline_context.get("field_spws")
    center_frequencies = pipeline_context.get("center_frequencies")
    scratch = True  # Setting scratch to True directly
    
    # Debug: Check what we actually have
    task_logprint(f"Debug: field_positions type: {type(field_positions)}, length: {len(field_positions) if field_positions else 'None'}")
    task_logprint(f"Debug: field_spws type: {type(field_spws)}, value: {field_spws}")
    task_logprint(f"Debug: center_frequencies type: {type(center_frequencies)}, length: {len(center_frequencies) if center_frequencies else 'None'}")

    task_logprint("Setting models for standard primary calibrators")

    if field_positions is None:
        task_logprint("ERROR: field_positions not found in pipeline context.")
        QA2_calprep = "Fail"
    elif field_spws is None:
        task_logprint("ERROR: field_spws not found in pipeline context.")
        QA2_calprep = "Fail"
    elif center_frequencies is None:
        task_logprint("ERROR: center_frequencies not found in pipeline context.")
        QA2_calprep = "Fail"
    else:
        # Convert CASA measure dictionaries to (lon, lat) tuples in radians
        positions = []
        for field_pos in field_positions:
            if isinstance(field_pos, dict) and 'm0' in field_pos and 'm1' in field_pos:
                # Extract longitude and latitude from measure dict
                lon = field_pos['m0']['value']  # RA in radians
                lat = field_pos['m1']['value']  # Dec in radians
                positions.append((lon, lat))
            else:
                task_logprint(f"Warning: Unexpected field position format: {field_pos}")
                positions.append((0.0, 0.0))  # Fallback
        
        standard_source_names = ["3C48", "3C138", "3C147", "3C286"]
        standard_source_fields = find_standards(positions)

        standard_source_found = any(standard_source_fields)
        if not standard_source_found:
            task_logprint(
                "ERROR: No standard flux density calibrator observed, flux density scale will be arbitrary."
            )
            QA2_calprep = "Fail"

        for ii, fields in enumerate(standard_source_fields):
            for field in fields:
                if field < len(field_spws):
                    spws = field_spws[field]
                    field_name = standard_source_names[ii]
                    
                    # Get the band from the first spw (all spws in a field should be in the same band)
                    if len(spws) > 0 and spws[0] < len(center_frequencies):
                        reference_frequency = center_frequencies[spws[0]]
                        EVLA_band = find_EVLA_band(reference_frequency)
                        model_image = f"{field_name}_{EVLA_band}.im"
                        
                        task_logprint(f"Setting model for field {field} ({field_name}) in {EVLA_band} band")
                        task_logprint(f"SPWs: {spws}")
                        
                        # Calculate average frequency for reference
                        valid_spws = [spw for spw in spws if spw < len(center_frequencies)]
                        if valid_spws:
                            avg_freq = sum(center_frequencies[spw] for spw in valid_spws) / len(valid_spws)
                            
                            try:
                                # Set full polarization models for all spws at once
                                task_logprint(f"Setting full polarization models for {field_name}")
                                
                                integrate_polarization_setjy(
                                    vis=ms_active,
                                    field_id=field,
                                    field_name=field_name,
                                    spws=valid_spws,  # Pass all spws for this field
                                    band=EVLA_band,
                                    ref_freq_hz=avg_freq * 1e9,  # Convert GHz to Hz
                                    obs_date=None,  # Will use 2019 data by default
                                    use_model_image=model_image,  # Include the model image
                                    standard="Perley-Butler 2017",  # Pass through the standard
                                    usescratch=scratch
                                )
                                task_logprint(f"Successfully set full polarization models for {field_name}")
                                    
                            except Exception as e:
                                task_logprint(f"Error setting polarization models for field {field}: {e}")
                                task_logprint("Falling back to intensity-only setjy per spw")
                                
                                # Fallback to standard intensity-only setjy for each spw
                                for spw in valid_spws:
                                    try:
                                        setjy(
                                            vis=ms_active,
                                            field=str(field),
                                            spw=str(spw),
                                            selectdata=False,
                                            scalebychan=True,
                                            standard="Perley-Butler 2017",
                                            model=model_image,
                                            listmodels=False,
                                            usescratch=scratch,
                                        )
                                        task_logprint(f"Fallback intensity-only setjy succeeded for field {field} spw {spw}")
                                    except Exception as fallback_e:
                                        task_logprint(f"Fallback setjy also failed for field {field} spw {spw}: {fallback_e}")
                        else:
                            task_logprint(f"WARNING: No valid spws found for field {field}")
                    else:
                        task_logprint(f"WARNING: No spws or invalid spw indices for field {field}")
                else:
                    task_logprint(f"WARNING: field_spws index {field} out of range.")

    task_logprint("Finished setting models for known calibrators")

    task_logprint("Finished EVLA_pipe_calprep.py (Refactored)")
        # Import colored output function
    task_logprint(f"QA2 score: {format_qa_status(QA2_calprep)}")
    time_list = runtiming("calprep", "end")

    return pipeline_context
