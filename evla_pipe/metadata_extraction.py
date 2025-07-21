"""
MS Metadata Extraction Module for EVLA Pipeline

This module handles comprehensive metadata extraction from measurement sets
and calibrator identification/splitting functionality.

Key Functions:
- extract_ms_metadata: Complete MS metadata extraction
- identify_calibrators: Find calibrator fields by intent
- split_calibrators: Create calibrators.ms for efficient processing
"""

import os
import numpy as np
from typing import Dict, Any, List, Tuple
from pathlib import Path

from casatasks import listobs, plotweather, split, rmtables
from casatools import table, ms, msmetadata
from evla_pipe.utils import (
    uniq, runtiming, logprint, find_EVLA_band, 
    format_qa_status, get_log_path
)
from evla_pipe.import_data import track_flagging_progression

tb = table()
ms_tool = ms()


def task_logprint(msg: str, step: str = "metadata"):
    """Centralized logging for metadata operations."""
    logprint(msg, logfileout=str(get_log_path(f"{step}.log")))


def _safe_get_exposure_time(msmd) -> float:
    """Safely extract effective exposure time from msmetadata."""
    try:
        if hasattr(msmd, 'effexposuretime'):
            result = msmd.effexposuretime()
            if isinstance(result, dict):
                # If it's a quantity dict, extract the value
                if 'value' in result:
                    return float(result['value'])
                elif 'm0' in result and isinstance(result['m0'], dict) and 'value' in result['m0']:
                    return float(result['m0']['value'])
                else:
                    task_logprint(f"Unexpected effexposuretime dict structure: {result}")
                    return 0.0
            elif isinstance(result, (int, float)):
                return float(result)
            else:
                task_logprint(f"Unexpected effexposuretime type: {type(result)}")
                return 0.0
        else:
            return 0.0
    except Exception as e:
        task_logprint(f"Error getting effective exposure time: {e}")
        return 0.0


def extract_ms_metadata(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from the measurement set.
    
    This replaces EVLA_pipe_msmd.py with a cleaner, modular approach.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname
        
    Returns
    -------
    dict
        Updated pipeline context with complete MS metadata
    """
    msname = pipeline_context.get("msname")
    if not msname:
        task_logprint("Error: Missing msname in pipeline context")
        pipeline_context["QA2_metadata"] = "Fail"
        return pipeline_context
        
    task_logprint("*** Starting MS Metadata Extraction ***")
    start_time = runtiming("metadata", "start")
    
    msmd = msmetadata()
    
    try:
        msmd.open(msname)
        
        # Generate listobs output for reference
        task_logprint("Generating listobs output")
        listname = msname.rstrip("ms") + "listobs"
        if os.path.exists(listname):
            os.remove(listname)
        listobs(vis=msname, selectdata=False, listfile=listname, 
                overwrite=True, verbose=True)
        
        # Basic MS information
        task_logprint("Extracting basic MS information")
        summary = msmd.summary()
        basic_info = {
            'msname': str(msname),
            'summary': summary if isinstance(summary, dict) else str(summary),
            'nspw': int(msmd.nspw()),
            'nfields': int(msmd.nfields()),
            'nantennas': int(msmd.nantennas()),
            'nscans': int(msmd.nscans()),
            'nobservations': int(msmd.nobservations()),
            'nstates': int(msmd.nstates()),
            'nsources': int(msmd.nsources()),
            'nbaselines': int(msmd.nbaselines()),
            'nrows': int(msmd.nrows()),
            'effective_exposure_time': _safe_get_exposure_time(msmd)
        }
        
        task_logprint(f"MS: {basic_info['nspw']} spws, {basic_info['nfields']} fields, "
                     f"{basic_info['nantennas']} antennas, {basic_info['nscans']} scans")
        
        # Spectral window information
        task_logprint("Extracting spectral window information")
        spw_info = {}
        channels = []
        
        for spwid in range(basic_info['nspw']):
            nchan = msmd.nchan(spwid)
            channels.append(nchan)
            
            # Get reference frequency safely
            ref_freq_dict = msmd.reffreq(spwid)
            if isinstance(ref_freq_dict, dict) and 'm0' in ref_freq_dict:
                if isinstance(ref_freq_dict['m0'], dict) and 'value' in ref_freq_dict['m0']:
                    reffreq_hz = ref_freq_dict['m0']['value']
                else:
                    reffreq_hz = ref_freq_dict['m0']  # Already a number
            else:
                reffreq_hz = float(ref_freq_dict) if isinstance(ref_freq_dict, (int, float)) else 0.0
                
            # Get bandwidth safely
            bandwidth = msmd.bandwidths(spwid)
            if isinstance(bandwidth, dict):
                # Handle quantity dict
                if 'value' in bandwidth:
                    bandwidth_hz = bandwidth['value']
                else:
                    bandwidth_hz = 0.0
            elif hasattr(bandwidth, '__len__') and len(bandwidth) == 1:
                bandwidth_hz = bandwidth[0]
            else:
                bandwidth_hz = bandwidth if not hasattr(bandwidth, '__len__') else np.sum(bandwidth)
                
            centerfreq_hz = reffreq_hz + bandwidth_hz / 2
            evla_band = find_EVLA_band(centerfreq_hz)
            
            # Convert CASA objects to JSON with type info for reconstruction
            chanfreqs = msmd.chanfreqs(spwid)
            chanwidths = msmd.chanwidths(spwid)
            
            spw_info[spwid] = {
                'nchan': int(nchan),
                'reffreq_hz': float(reffreq_hz),
                'bandwidth_hz': float(bandwidth_hz),
                'centerfreq_hz': float(centerfreq_hz),
                'evla_band': str(evla_band),
                'chanfreqs_hz': {
                    'data': chanfreqs.tolist() if hasattr(chanfreqs, 'tolist') else list(chanfreqs),
                    'type': 'numpy_array',
                    'dtype': str(chanfreqs.dtype) if hasattr(chanfreqs, 'dtype') else 'float64'
                },
                'chanwidths_hz': {
                    'data': chanwidths.tolist() if hasattr(chanwidths, 'tolist') else list(chanwidths),
                    'type': 'numpy_array', 
                    'dtype': str(chanwidths.dtype) if hasattr(chanwidths, 'dtype') else 'float64'
                }
            }
            
        # Field information
        task_logprint("Extracting field information")
        field_info = {}
        field_names = msmd.fieldnames()
        
        for field_id in range(basic_info['nfields']):
            # Convert CASA objects to JSON-serializable types
            direction = msmd.phasecenter(field_id)
            intents = msmd.intentsforfield(field_id)
            scans = msmd.scansforfield(field_id)
            spws = msmd.spwsforfield(field_id)
            times = msmd.timesforfield(field_id)
            
            field_info[field_id] = {
                'name': str(field_names[field_id] if field_id < len(field_names) else f"field_{field_id}"),
                'direction': {
                    'data': direction if isinstance(direction, dict) else str(direction),
                    'type': 'casa_direction'
                },
                'intents': {
                    'data': list(intents) if hasattr(intents, '__iter__') else [str(intents)],
                    'type': 'string_list'
                },
                'scans': {
                    'data': scans.tolist() if hasattr(scans, 'tolist') else list(scans),
                    'type': 'numpy_array',
                    'dtype': str(scans.dtype) if hasattr(scans, 'dtype') else 'int32'
                },
                'spws': {
                    'data': spws.tolist() if hasattr(spws, 'tolist') else list(spws),
                    'type': 'numpy_array',
                    'dtype': str(spws.dtype) if hasattr(spws, 'dtype') else 'int32'
                },
                'times': {
                    'data': times.tolist() if hasattr(times, 'tolist') else list(times),
                    'type': 'numpy_array',
                    'dtype': str(times.dtype) if hasattr(times, 'dtype') else 'float64'
                }
            }
            
        # Scan information  
        task_logprint("Extracting scan information")
        scan_info = {}
        
        for scan_id in msmd.scannumbers():
            # Convert CASA objects to JSON-serializable types
            fields = msmd.fieldsforscan(scan_id)
            spws = msmd.spwsforscan(scan_id)
            intents = msmd.intentsforscan(scan_id)
            times = msmd.timesforscan(scan_id)
            antennas = msmd.antennasforscan(scan_id)
            
            scan_info[scan_id] = {
                'fields': {
                    'data': fields.tolist() if hasattr(fields, 'tolist') else list(fields),
                    'type': 'numpy_array',
                    'dtype': str(fields.dtype) if hasattr(fields, 'dtype') else 'int32'
                },
                'spws': {
                    'data': spws.tolist() if hasattr(spws, 'tolist') else list(spws),
                    'type': 'numpy_array',
                    'dtype': str(spws.dtype) if hasattr(spws, 'dtype') else 'int32'
                },
                'intents': {
                    'data': list(intents) if hasattr(intents, '__iter__') else [str(intents)],
                    'type': 'string_list'
                },
                'times': {
                    'data': times.tolist() if hasattr(times, 'tolist') else list(times),
                    'type': 'numpy_array',
                    'dtype': str(times.dtype) if hasattr(times, 'dtype') else 'float64'
                },
                'antennas': {
                    'data': antennas.tolist() if hasattr(antennas, 'tolist') else list(antennas),
                    'type': 'numpy_array',
                    'dtype': str(antennas.dtype) if hasattr(antennas, 'dtype') else 'int32'
                }
            }
            
        # Antenna information
        task_logprint("Extracting antenna information")
        antenna_names = msmd.antennanames()
        # Convert antenna data to JSON-serializable types
        positions = []
        diameters = []
        for i in range(basic_info['nantennas']):
            pos = msmd.antennaposition(i)
            diam = msmd.antennadiameter(i)
            positions.append(pos if isinstance(pos, (list, tuple)) else str(pos))
            diameters.append(float(diam) if isinstance(diam, (int, float)) else str(diam))
        
        stations = msmd.antennastations()
        
        antenna_info = {
            'names': {
                'data': list(antenna_names) if hasattr(antenna_names, '__iter__') else [str(antenna_names)],
                'type': 'string_list'
            },
            'positions': {
                'data': positions,
                'type': 'casa_position_list'
            },
            'diameters': {
                'data': diameters,
                'type': 'float_list'
            },
            'stations': {
                'data': stations.tolist() if hasattr(stations, 'tolist') else list(stations),
                'type': 'string_list'
            }
        }
        
        # Time and observation information
        task_logprint("Extracting time and observation information")
        summary = msmd.summary()
        
        # Get available scans and observations
        scan_numbers = msmd.scannumbers()
        first_scan = scan_numbers[0] if len(scan_numbers) > 0 else 0
        
        # Get first valid observation ID (0-based index)
        first_obsid = 0 if basic_info['nobservations'] > 0 else -1
        
        # Get timerange for first observation
        if basic_info['nobservations'] > 0:
            try:
                timerange = msmd.timerangeforobs(obsid=first_obsid)
            except Exception as e:
                task_logprint(f"Could not get timerange for obsid={first_obsid}: {e}")
                timerange = {'begin': {'value': 0.0}, 'end': {'value': 0.0}}
        else:
            timerange = {'begin': {'value': 0.0}, 'end': {'value': 0.0}}
        
        # Get exposure time using first available scan, spw, and observation
        exposure_time = 0.0
        if len(scan_numbers) > 0 and basic_info['nspw'] > 0 and basic_info['nobservations'] > 0:
            try:
                exposure_time_dict = msmd.exposuretime(scan=first_scan, spwid=0, obsid=first_obsid)
                if isinstance(exposure_time_dict, dict):
                    # Handle quantity dictionary
                    if 'value' in exposure_time_dict:
                        exposure_time = float(exposure_time_dict['value'])
                    elif 'm0' in exposure_time_dict and isinstance(exposure_time_dict['m0'], dict):
                        exposure_time = float(exposure_time_dict['m0'].get('value', 0.0))
                    else:
                        task_logprint(f"Unknown exposure time dict format: {exposure_time_dict}")
                        exposure_time = 0.0
                elif isinstance(exposure_time_dict, (int, float)):
                    exposure_time = float(exposure_time_dict)
                else:
                    task_logprint(f"Unknown exposure time type: {type(exposure_time_dict)}")
                    exposure_time = 0.0
            except Exception as e:
                task_logprint(f"Could not get exposure time for scan={first_scan}, spwid=0, obsid={first_obsid}: {e}")
                # Try to get from summary
                summary_exp = summary.get('ExposureTime', 0.0)
                exposure_time = float(summary_exp) if isinstance(summary_exp, (int, float)) else 0.0
        
        time_info = {
            'timerange': timerange,
            'exposure_time': exposure_time,
            'start_time': summary.get("BeginTime", 0.0),
            'end_time': summary.get("EndTime", 0.0)
        }
        
        # Calculate tau (atmospheric opacity)
        task_logprint("Calculating atmospheric opacity (tau)")
        try:
            tau = calculate_tau(msname, time_info['start_time'])
            task_logprint(f"Calculated tau = {tau}")
        except Exception as e:
            task_logprint(f"Warning: Could not calculate tau: {e}")
            tau = 0.0
            
        # Identify EVLA band
        if spw_info:
            # Use first SPW for band identification
            first_spw = list(spw_info.values())[0]
            evla_band = first_spw['evla_band']
        else:
            evla_band = "Unknown"
            
        # Store all metadata in context
        pipeline_context.update({
            'ms_basic_info': basic_info,
            'spw_info': spw_info,
            'field_info': field_info,
            'scan_info': scan_info,
            'antenna_info': antenna_info,
            'time_info': time_info,
            'channels': channels,
            'numSpws': basic_info['nspw'],
            'numAntenna': basic_info['nantennas'],
            'numfields': basic_info['nfields'],
            'EVLA_band': evla_band,
            'tau': tau,
            'int_time': time_info.get('exposure_time', 1.0),
            'startdate': time_info['start_time'],
            'QA2_metadata': "Pass"
        })
        
        # Print comprehensive summary
        print_metadata_summary(pipeline_context)
        
        # Print comprehensive summary for debugging
        print_comprehensive_summary(pipeline_context)
        
        task_logprint("MS metadata extraction completed successfully")
        
    except Exception as e:
        task_logprint(f"Error extracting MS metadata: {e}")
        pipeline_context["QA2_metadata"] = "Fail"
        raise
        
    finally:
        msmd.done()
        runtiming("metadata", "end")
        
    return pipeline_context


def calculate_tau(msname: str, start_time: float) -> float:
    """Calculate atmospheric opacity using plotweather."""
    try:
        # Check for known problematic periods
        if ((start_time >= 55918.80) and (start_time <= 55938.98)) or \
           ((start_time >= 56253.6) and (start_time <= 56271.6)):
            task_logprint("Weather station broken during this period, using 100% seasonal model")
            tau = plotweather(vis=msname, seasonal_weight=1.0, doPlot=True)
        else:
            tau = plotweather(vis=msname, seasonal_weight=0.5, doPlot=True)
        return tau
    except Exception as e:
        task_logprint(f"Error calculating tau: {e}")
        return 0.0


def identify_calibrators(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Identify calibrator fields based on observing intents.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with field_info
        
    Returns
    -------
    dict
        Updated context with calibrator field lists and selection strings
    """
    task_logprint("*** Starting Calibrator Identification ***")
    
    field_info = pipeline_context.get('field_info', {})
    if not field_info:
        task_logprint("Error: No field information available")
        return pipeline_context
        
    # Initialize calibrator categories
    cal_fields = {
        'flux': [],
        'bandpass': [],
        'delay': [],
        'phase': [],
        'ampli': [],
        'pol_angle': [],
        'pol_leakage': [],
        'all_calibrators': []
    }
    
    # Intent mappings
    intent_mappings = {
        'flux': ['AMPLITUDE', 'FLUX'],
        'bandpass': ['BANDPASS'],
        'delay': ['DELAY'],
        'phase': ['PHASE'],
        'ampli': ['AMPLITUDE'],
        'pol_angle': ['POLARIZATION_ANGLE', 'POL_ANGLE'],
        'pol_leakage': ['POLARIZATION_LEAKAGE', 'POL_LEAKAGE']
    }
    
    # Scan through fields and categorize by intent
    for field_id, field_data in field_info.items():
        field_name = field_data['name']
        intents = field_data.get('intents', [])
        
        # Check if field has any calibrator intent
        is_calibrator = any('CALIBRATE' in intent for intent in intents)
        
        if is_calibrator:
            cal_fields['all_calibrators'].append(field_id)
            
            # Categorize by specific intent
            for cal_type, intent_keywords in intent_mappings.items():
                if any(keyword in ' '.join(intents) for keyword in intent_keywords):
                    cal_fields[cal_type].append(field_id)
                    task_logprint(f"Field {field_id} ({field_name}) identified as {cal_type} calibrator")
    
    # Create selection strings
    cal_strings = {}
    field_names = [pipeline_context['field_info'][fid]['name'] for fid in range(pipeline_context['numfields'])]
    
    for cal_type, field_ids in cal_fields.items():
        if field_ids:
            # Create comma-separated string of field IDs
            cal_strings[f"{cal_type}_field_select_string"] = ','.join(map(str, field_ids))
            # Also create name-based string for reference
            names = [field_names[fid] for fid in field_ids if fid < len(field_names)]
            cal_strings[f"{cal_type}_field_names"] = ','.join(names)
        else:
            cal_strings[f"{cal_type}_field_select_string"] = ""
            cal_strings[f"{cal_type}_field_names"] = ""
    
    # Create scan selection strings for calibrators
    calibrator_scans = []
    for field_id in cal_fields['all_calibrators']:
        field_data = field_info.get(field_id, {})
        scans = field_data.get('scans', [])
        calibrator_scans.extend(scans)
    
    calibrator_scans = sorted(list(set(calibrator_scans)))
    cal_strings['calibrator_scan_select_string'] = ','.join(map(str, calibrator_scans))
    
    # Store in context with legacy naming for compatibility
    pipeline_context.update({
        'calibrator_fields': cal_fields,
        'calibrator_strings': cal_strings,
        # Legacy field lists
        'flux_field_list': cal_fields['flux'],
        'bandpass_field_list': cal_fields['bandpass'],
        'delay_field_list': cal_fields['delay'],
        'phase_field_list': cal_fields['phase'],
        'polarization_angle_field_list': cal_fields['pol_angle'],
        'polarization_lkg_field_list': cal_fields['pol_leakage'],
        'all_calibrator_field_list': cal_fields['all_calibrators'],
        # Legacy selection strings
        'flux_field_select_string': cal_strings['flux_field_select_string'],
        'bandpass_field_select_string': cal_strings['bandpass_field_select_string'],
        'delay_field_select_string': cal_strings['delay_field_select_string'],
        'phase_field_select_string': cal_strings['phase_field_select_string'],
        'calibrator_scan_select_string': cal_strings['calibrator_scan_select_string'],
        'calibrator_field_select_string': cal_strings['all_calibrators_field_select_string']
    })
    
    task_logprint(f"Identified {len(cal_fields['all_calibrators'])} calibrator fields")
    task_logprint(f"Flux: {len(cal_fields['flux'])}, Bandpass: {len(cal_fields['bandpass'])}, "
                 f"Delay: {len(cal_fields['delay'])}, Phase: {len(cal_fields['phase'])}")
    
    return pipeline_context


def split_calibrators(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Split calibrator data into separate MS for efficient processing.
    
    This creates calibrators.ms earlier in the pipeline (after metadata)
    instead of waiting until solint step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with calibrator information
        
    Returns
    -------
    dict
        Updated context with calibrators.ms information
    """
    task_logprint("*** Starting Calibrator Splitting ***")
    start_time = runtiming("split_calibrators", "start")
    
    msname = pipeline_context.get("msname")
    calibrator_scan_select_string = pipeline_context.get("calibrator_scan_select_string", "")
    channels = pipeline_context.get("channels", [])
    
    if not msname:
        task_logprint("Error: No msname in context")
        return pipeline_context
        
    if not calibrator_scan_select_string:
        task_logprint("Warning: No calibrator scans identified, skipping split")
        pipeline_context["calibrators_ms_created"] = False
        return pipeline_context
    
    # Track flagging before split
    pipeline_context = track_flagging_progression(pipeline_context, "before_calibrator_split")
    
    output_ms = "calibrators.ms"
    task_logprint(f"Splitting calibrators from {msname} to {output_ms}")
    task_logprint(f"Using scans: {calibrator_scan_select_string}")
    
    # Remove existing calibrators.ms
    rmtables(output_ms)
    
    try:
        # Determine channel width for split
        width = int(max(channels)) if channels else 1
        
        split(
            vis=msname,
            outputvis=output_ms,
            datacolumn="data",
            field="",
            spw="",
            width=width,
            antenna="",
            timebin="0s",
            timerange="",
            scan=calibrator_scan_select_string,
            intent="",
            array="",
            uvrange="",
            correlation="",
            observation="",
            keepflags=False,  # Drop flagged data for efficiency
        )
        
        task_logprint(f"Successfully created {output_ms}")
        
        # Verify the split was successful
        if os.path.exists(output_ms):
            # Get summary of calibrators.ms
            ms_tool.open(output_ms)
            scan_summary = ms_tool.getscansummary()
            ms_tool.close()
            
            num_scans = len(scan_summary)
            task_logprint(f"Calibrators.ms contains {num_scans} scans")
            
            pipeline_context.update({
                "calibrators_ms": output_ms,
                "calibrators_ms_created": True,
                "calibrators_ms_scans": num_scans,
                "QA2_split_calibrators": "Pass"
            })
        else:
            task_logprint("Error: calibrators.ms was not created")
            pipeline_context["QA2_split_calibrators"] = "Fail"
            
    except Exception as e:
        task_logprint(f"Error creating calibrators.ms: {e}")
        task_logprint(f"msname: {msname}")
        task_logprint(f"calibrator_scan_select_string: {calibrator_scan_select_string}")
        pipeline_context["QA2_split_calibrators"] = "Fail"
        raise
        
    runtiming("split_calibrators", "end")
    return pipeline_context


def extract_metadata_and_calibrators(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point: Extract metadata, identify calibrators, and split them.
    
    This replaces the EVLA_pipe_msmd step and adds early calibrator splitting.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context
        
    Returns
    -------
    dict
        Updated context with complete metadata and calibrator information
    """
    task_logprint("*** Starting Metadata Extraction and Calibrator Processing ***")
    
    # Step 1: Extract comprehensive MS metadata
    pipeline_context = extract_ms_metadata(pipeline_context)
    
    if pipeline_context.get("QA2_metadata") == "Fail":
        task_logprint("Metadata extraction failed, skipping calibrator processing")
        return pipeline_context
    
    # Step 2: Identify calibrator fields
    pipeline_context = identify_calibrators(pipeline_context)
    
    # Step 3: Split calibrator data for efficient processing
    pipeline_context = split_calibrators(pipeline_context)
    
    task_logprint("*** Metadata Extraction and Calibrator Processing Complete ***")
    return pipeline_context


# Convenience function for pipeline integration
def perform_metadata_extraction(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for pipeline integration."""
    return extract_metadata_and_calibrators(pipeline_context)


def restore_numpy_types(typed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert typed JSON data back to original numpy/CASA types.
    
    This recursively processes the metadata structure and converts
    data marked with type information back to numpy arrays.
    
    Parameters
    ----------
    typed_data : dict
        Dictionary containing data with type information
        
    Returns
    -------
    dict
        Dictionary with numpy arrays restored
    """
    if not isinstance(typed_data, dict):
        return typed_data
        
    result = {}
    
    for key, value in typed_data.items():
        if isinstance(value, dict) and 'type' in value and 'data' in value:
            # This is typed data - convert back
            data_type = value['type']
            data = value['data']
            
            if data_type == 'numpy_array':
                dtype = value.get('dtype', 'float64')
                result[key] = np.array(data, dtype=dtype)
            elif data_type in ['string_list', 'float_list']:
                result[key] = data  # Keep as list
            elif data_type == 'casa_direction':
                result[key] = data  # Keep CASA direction as-is
            elif data_type == 'casa_position_list':
                result[key] = data  # Keep position list as-is
            else:
                result[key] = data  # Default: keep as-is
                
        elif isinstance(value, dict):
            # Recursively process nested dictionaries
            result[key] = restore_numpy_types(value)
        else:
            # Regular data
            result[key] = value
            
    return result


def get_numpy_array(field_data: Dict[str, Any], key: str) -> np.ndarray:
    """
    Helper to extract numpy array from typed field data.
    
    Parameters
    ----------
    field_data : dict
        Field/scan/spw data dictionary
    key : str
        Key to extract (e.g., 'scans', 'times', 'chanfreqs_hz')
        
    Returns
    -------
    numpy.ndarray
        The requested array
    """
    if key in field_data and isinstance(field_data[key], dict):
        typed_data = field_data[key]
        if typed_data.get('type') == 'numpy_array':
            dtype = typed_data.get('dtype', 'float64')
            return np.array(typed_data['data'], dtype=dtype)
    
    # Fallback for non-typed data
    return np.array(field_data.get(key, []))


def get_string_list(field_data: Dict[str, Any], key: str) -> List[str]:
    """
    Helper to extract string list from typed field data.
    
    Parameters
    ----------
    field_data : dict
        Field/scan data dictionary
    key : str
        Key to extract (e.g., 'intents')
        
    Returns
    -------
    list
        List of strings
    """
    if key in field_data and isinstance(field_data[key], dict):
        typed_data = field_data[key]
        if typed_data.get('type') == 'string_list':
            return typed_data['data']
    
    # Fallback for non-typed data
    return field_data.get(key, [])


def print_metadata_summary(pipeline_context: Dict[str, Any]):
    """
    Print comprehensive metadata summary with sources, scans, times, and intents.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with extracted metadata
    """
    task_logprint("="*80)
    task_logprint("COMPREHENSIVE MS METADATA SUMMARY")
    task_logprint("="*80)
    
    # Basic info
    basic_info = pipeline_context.get('ms_basic_info', {})
    msname = basic_info.get('msname', 'Unknown')
    
    task_logprint(f"MS: {msname}")
    task_logprint(f"Fields: {basic_info.get('nfields', 0)}")
    task_logprint(f"Spectral Windows: {basic_info.get('nspw', 0)}")
    task_logprint(f"Antennas: {basic_info.get('nantennas', 0)}")
    task_logprint(f"Scans: {basic_info.get('nscans', 0)}")
    task_logprint(f"Observations: {basic_info.get('nobservations', 0)}")
    
    # Time information
    time_info = pipeline_context.get('time_info', {})
    start_time = time_info.get('start_time', 0)
    end_time = time_info.get('end_time', 0)
    
    if start_time and end_time:
        duration_sec = (end_time - start_time) * 86400  # Convert to seconds
        duration_hours = duration_sec / 3600
        task_logprint(f"Observation Duration: {duration_hours:.2f} hours ({duration_sec:.0f} seconds)")
    
    task_logprint("")
    
    # Field summary with intents
    task_logprint("FIELD SUMMARY:")
    task_logprint("-" * 80)
    task_logprint(f"{'ID':<3} {'Name':<20} {'Intents':<40} {'Scans':<15}")
    task_logprint("-" * 80)
    
    field_info = pipeline_context.get('field_info', {})
    scan_info = pipeline_context.get('scan_info', {})
    
    for field_id in sorted(field_info.keys()):
        field_data = field_info[field_id]
        name = field_data.get('name', f'field_{field_id}')
        
        # Get intents safely
        intents_data = field_data.get('intents', {})
        if isinstance(intents_data, dict) and 'data' in intents_data:
            intents = intents_data['data']
        else:
            intents = intents_data if isinstance(intents_data, list) else []
        
        # Get scans safely  
        scans_data = field_data.get('scans', {})
        if isinstance(scans_data, dict) and 'data' in scans_data:
            scans = scans_data['data']
        else:
            scans = scans_data if isinstance(scans_data, list) else []
        
        # Format intents and scans
        intent_str = ','.join(intents) if intents else 'None'
        scan_str = ','.join(map(str, scans)) if scans else 'None'
        
        # Truncate for display
        if len(intent_str) > 35:
            intent_str = intent_str[:32] + "..."
        if len(scan_str) > 12:
            scan_str = scan_str[:9] + "..."
            
        task_logprint(f"{field_id:<3} {name:<20} {intent_str:<40} {scan_str:<15}")
    
    task_logprint("")
    
    # Scan summary with times
    task_logprint("SCAN SUMMARY:")
    task_logprint("-" * 80)
    task_logprint(f"{'Scan':<5} {'Fields':<15} {'Intents':<30} {'Duration':<10}")
    task_logprint("-" * 80)
    
    for scan_id in sorted(scan_info.keys()):
        scan_data = scan_info[scan_id]
        
        # Get fields safely
        fields_data = scan_data.get('fields', {})
        if isinstance(fields_data, dict) and 'data' in fields_data:
            fields = fields_data['data']
        else:
            fields = fields_data if isinstance(fields_data, list) else []
        
        # Get intents safely
        intents_data = scan_data.get('intents', {})
        if isinstance(intents_data, dict) and 'data' in intents_data:
            intents = intents_data['data']
        else:
            intents = intents_data if isinstance(intents_data, list) else []
        
        # Get times safely
        times_data = scan_data.get('times', {})
        if isinstance(times_data, dict) and 'data' in times_data:
            times = np.array(times_data['data'])
        else:
            times = np.array(times_data) if isinstance(times_data, list) else np.array([])
        
        # Calculate duration
        if len(times) > 1:
            duration_sec = (times.max() - times.min()) * 86400
            duration_str = f"{duration_sec:.0f}s"
        else:
            duration_str = "N/A"
        
        # Format for display
        fields_str = ','.join(map(str, fields)) if fields else 'None'
        intent_str = ','.join(intents) if intents else 'None'
        
        if len(fields_str) > 12:
            fields_str = fields_str[:9] + "..."
        if len(intent_str) > 27:
            intent_str = intent_str[:24] + "..."
            
        task_logprint(f"{scan_id:<5} {fields_str:<15} {intent_str:<30} {duration_str:<10}")
    
    task_logprint("")
    
    # Calibrator summary
    task_logprint("CALIBRATOR SUMMARY:")
    task_logprint("-" * 50)
    
    cal_types = {
        'flux_field_list': 'Flux Calibrators',
        'bandpass_field_list': 'Bandpass Calibrators', 
        'delay_field_list': 'Delay Calibrators',
        'phase_field_list': 'Phase Calibrators',
        'polarization_angle_field_list': 'Polarization Angle',
        'polarization_lkg_field_list': 'Polarization Leakage'
    }
    
    for cal_key, cal_name in cal_types.items():
        cal_fields = pipeline_context.get(cal_key, [])
        if cal_fields:
            names = [get_field_name(pipeline_context, fid) for fid in cal_fields]
            task_logprint(f"{cal_name:<25}: {', '.join(names)}")
        else:
            task_logprint(f"{cal_name:<25}: None identified")
    
    # Selection strings
    cal_scan_string = pipeline_context.get("calibrator_scan_select_string", "")
    if cal_scan_string:
        task_logprint(f"Calibrator scans: {cal_scan_string}")
    else:
        task_logprint("Calibrator scans: None identified")
    
    task_logprint("="*80)


def get_field_name(pipeline_context: Dict[str, Any], field_id: int) -> str:
    """Get field name from field ID."""
    field_info = pipeline_context.get("field_info", {})
    if field_id in field_info:
        return field_info[field_id].get("name", f"field_{field_id}")
    return f"field_{field_id}"


def print_comprehensive_summary(pipeline_context: Dict[str, Any]):
    """
    Print comprehensive summary of MS metadata for debugging.
    
    Shows all sources, scans, times, and intents to help debug
    calibrator identification issues.
    """
    task_logprint("=" * 60)
    task_logprint("COMPREHENSIVE MS METADATA SUMMARY")
    task_logprint("=" * 60)
    
    # Basic info
    basic_info = pipeline_context.get('ms_basic_info', {})
    msname = basic_info.get('msname', 'unknown')
    task_logprint(f"MS: {msname}")
    task_logprint(f"Fields: {basic_info.get('nfields', 0)}")
    task_logprint(f"Scans: {basic_info.get('nscans', 0)}")
    task_logprint(f"SPWs: {basic_info.get('nspw', 0)}")
    task_logprint(f"Antennas: {basic_info.get('nantennas', 0)}")
    
    # Field information with intents
    field_info = pipeline_context.get('field_info', {})
    scan_info = pipeline_context.get('scan_info', {})
    
    task_logprint("")
    task_logprint("FIELD INFORMATION:")
    task_logprint("-" * 40)
    
    for field_id, field_data in field_info.items():
        if isinstance(field_data, dict):
            name = field_data.get('name', f'field_{field_id}')
            intents = get_string_list(field_data, 'intents')
            scans = get_numpy_array(field_data, 'scans').tolist() if 'scans' in field_data else []
            
            task_logprint(f"Field {field_id}: {name}")
            task_logprint(f"  Intents: {intents}")
            task_logprint(f"  Scans: {scans}")
    
    task_logprint("")
    task_logprint("SCAN INFORMATION:")
    task_logprint("-" * 40)
    
    for scan_id, scan_data in scan_info.items():
        if isinstance(scan_data, dict):
            fields = get_numpy_array(scan_data, 'fields').tolist() if 'fields' in scan_data else []
            intents = get_string_list(scan_data, 'intents')
            times = get_numpy_array(scan_data, 'times')
            
            # Calculate scan duration
            if len(times) > 1:
                duration = (times.max() - times.min()) * 86400  # Convert to seconds
            else:
                duration = 0
                
            task_logprint(f"Scan {scan_id}:")
            task_logprint(f"  Fields: {fields}")
            task_logprint(f"  Intents: {intents}")
            task_logprint(f"  Duration: {duration:.1f}s")
    
    # Calibrator identification results
    task_logprint("")
    task_logprint("CALIBRATOR IDENTIFICATION:")
    task_logprint("-" * 40)
    
    cal_types = [
        ('flux_field_list', 'Flux calibrators'),
        ('bandpass_field_list', 'Bandpass calibrators'),
        ('delay_field_list', 'Delay calibrators'),
        ('phase_field_list', 'Phase calibrators'),
        ('polarization_angle_field_list', 'Pol angle calibrators'),
        ('polarization_lkg_field_list', 'Pol leakage calibrators')
    ]
    
    total_calibrators = 0
    for cal_key, cal_desc in cal_types:
        cal_fields = pipeline_context.get(cal_key, [])
        if cal_fields:
            total_calibrators += len(cal_fields)
            field_names = []
            for fid in cal_fields:
                if fid in field_info:
                    field_names.append(field_info[fid].get('name', f'field_{fid}'))
            task_logprint(f"{cal_desc}: {cal_fields} ({', '.join(field_names)})")
        else:
            task_logprint(f"{cal_desc}: None")
    
    # Selection strings
    task_logprint("")
    task_logprint("CALIBRATOR SELECTION STRINGS:")
    task_logprint("-" * 40)
    
    cal_scan_string = pipeline_context.get('calibrator_scan_select_string', '')
    task_logprint(f"Calibrator scans: '{cal_scan_string}'")
    
    if not cal_scan_string:
        task_logprint("*** WARNING: No calibrator scans identified! ***")
        task_logprint("This is why calibrator splitting was skipped.")
    
    task_logprint("=" * 60)