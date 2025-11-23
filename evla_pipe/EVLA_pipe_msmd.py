# EVLA_pipe_msmd.py

import os
import numpy as np
import warnings

from casatasks import listobs, plotweather
from casatools import table, ms, msmetadata

from evla_pipe.utils import (
from evla_pipe.pipeline_steps import register_step
    uniq, runtiming, logprint, find_EVLA_band, format_qa_status
)

def task_logprint(msg):
    logprint(msg, logfileout="logs/msmd.log")

tb = table()
ms = ms()


def calculate_tau(msname):
    """
    Calculates the zenith opacity (tau) using plotweather.

    Args:
        msname (str): The name of the Measurement Set.

    Returns:
        float: The calculated zenith opacity (tau).
    """
    startdate = 0.0
    try:
        msmd = msmetadata()
        msmd.open(msname)
        summary = msmd.summary()
        startdate = float(summary.get("BeginTime", 0.0))
        msmd.close()
    except Exception as e:
        task_logprint(f"Error getting start time from MS: {e}")
        return 0.0

    if ((startdate >= 55918.80) and (startdate <= 55938.98)) or \
            ((startdate >= 56253.6) and (startdate <= 56271.6)):
        task_logprint(
            "Weather station broken during this period, using 100% "
            "seasonal model for calculating the zenith opacity"
        )
        tau = plotweather(vis=msname, seasonal_weight=1.0, doPlot=True)
    else:
        tau = plotweather(vis=msname, seasonal_weight=0.5, doPlot=True)
    return tau

def get_ms_info(pipeline_context):
    """
    Collects ALL available metadata from the Measurement Set using msmetadata.
    
    This function extracts comprehensive metadata and stores it in a structured
    format within the pipeline context for use by any pipeline step.

    Args:
        pipeline_context (dict): A dictionary containing the pipeline's context,
                                 including the msname.

    Returns:
        dict: Updated pipeline context with comprehensive MS metadata.
    """
    msname = pipeline_context.get("msname")
    do_pol = pipeline_context.get("do_pol")

    if not msname:
        logprint("Error: Missing msname in pipeline context for get_ms_info.", logfileout="logs/msinfo.log")
        return pipeline_context

    task_logprint("*** Starting comprehensive MS metadata extraction ***")
    time_list = runtiming("msinfo", "start")
    QA2_msinfo = "Pass"
    msmd = msmetadata()
    
    # Initialize comprehensive metadata dictionary
    ms_metadata = {
        'basic_info': {},
        'spectral_windows': {},
        'fields': {},
        'antennas': {},
        'scans': {},
        'observations': {},
        'intents': {},
        'polarization': {},
        'source': {},
        'calibration': {},
        'time_info': {},
        'frequency_info': {},
        'baseline_info': {},
        'state_info': {}
    }
    
    try:
        msmd.open(msname)

        # Generate listobs output
        task_logprint("Listing ms contents")
        listname = msname.rstrip("ms") + "listobs"
        os.system(f"rm -rf {listname}")
        listobs(
            vis=msname,
            selectdata=False,
            listfile=listname,
            overwrite=True,
            verbose=True,
        )

        # ==================== BASIC INFORMATION ====================
        task_logprint("Extracting basic MS information...")
        ms_metadata['basic_info'] = {
            'msname': msname,
            'summary': msmd.summary(),
            'name': msmd.name(),
            'nspw': msmd.nspw(),
            'nfields': msmd.nfields(),
            'nantennas': msmd.nantennas(),
            'nscans': msmd.nscans(),
            'nobservations': msmd.nobservations(),
            'nstates': msmd.nstates(),
            'nsources': msmd.nsources(),
            'nbaselines': msmd.nbaselines(),
            'nbaselines_with_autocorr': msmd.nbaselines(ac=True),
            'nrows': msmd.nrows(),
            'nrows_cross_only': msmd.nrows(autoc=False),
            'nrows_unflagged': msmd.nrows(flagged=False),
            'effective_exposure_time': msmd.effexposuretime()
        }
        
        basic = ms_metadata['basic_info']
        task_logprint(f"MS: {basic['nspw']} spws, {basic['nfields']} fields, {basic['nantennas']} antennas, {basic['nscans']} scans")

        # ==================== SPECTRAL WINDOWS ====================
        task_logprint("Extracting spectral window information...")
        ms_metadata['spectral_windows'] = {}
        
        for spwid in range(basic['nspw']):
            spw_info = {}
            
            # Basic spw info
            spw_info['nchan'] = msmd.nchan(spwid)
            spw_info['name'] = msmd.namesforspws([spwid])[0] if msmd.namesforspws([spwid]) else f"spw{spwid}"
            
            # Frequency information - handle measure dicts safely
            ref_freq_dict = msmd.reffreq(spwid)
            if isinstance(ref_freq_dict, dict) and 'm0' in ref_freq_dict:
                spw_info['reffreq_hz'] = ref_freq_dict['m0']['value']
                spw_info['reffreq_unit'] = ref_freq_dict['m0']['unit']
                spw_info['reffreq_frame'] = ref_freq_dict.get('refer', 'Unknown')
            else:
                spw_info['reffreq_hz'] = 0.0
                spw_info['reffreq_unit'] = 'Hz'
                spw_info['reffreq_frame'] = 'Unknown'
            
            # Bandwidth information
            bandwidth = msmd.bandwidths(spwid)
            if hasattr(bandwidth, '__len__') and len(bandwidth) == 1:
                spw_info['bandwidth_hz'] = bandwidth[0]
            elif hasattr(bandwidth, '__len__'):
                spw_info['bandwidth_hz'] = np.sum(bandwidth)
            else:
                spw_info['bandwidth_hz'] = bandwidth
                
            # Channel information  
            spw_info['chanfreqs_hz'] = msmd.chanfreqs(spwid)
            spw_info['chanwidths_hz'] = msmd.chanwidths(spwid)
            spw_info['chanres_hz'] = msmd.chanres(spwid)
            spw_info['chaneffbws_hz'] = msmd.chaneffbws(spwid)
            spw_info['meanfreq_hz'] = msmd.meanfreq(spwid)
            
            # Calculate center frequency
            spw_info['centerfreq_hz'] = spw_info['reffreq_hz'] + spw_info['bandwidth_hz'] / 2
            
            # EVLA band identification
            spw_info['evla_band'] = find_EVLA_band(spw_info['centerfreq_hz'])
            
            # Optional ALMA-specific info (will be empty for non-ALMA data)
            try:
                spw_info['baseband'] = msmd.baseband(spwid)
            except:
                spw_info['baseband'] = None
            try:
                spw_info['sideband'] = msmd.sideband(spwid)
            except:
                spw_info['sideband'] = None
            try:
                spw_info['corrbit'] = msmd.corrbit(spwid)
            except:
                spw_info['corrbit'] = None
                
            ms_metadata['spectral_windows'][spwid] = spw_info

        # ==================== FIELDS ====================
        task_logprint("Extracting field information...")
        ms_metadata['fields'] = {}
        
        field_names = msmd.fieldnames()
        for fieldid in range(basic['nfields']):
            field_info = {}
            field_info['name'] = field_names[fieldid] if fieldid < len(field_names) else f"field{fieldid}"
            field_info['phasecenter'] = msmd.phasecenter(fieldid)
            field_info['refdir'] = msmd.refdir(fieldid)
            field_info['sourceid'] = msmd.sourceidforfield(fieldid)
            field_info['spws'] = msmd.spwsforfield(fieldid)
            field_info['scans'] = msmd.scansforfield(fieldid)
            field_info['intents'] = msmd.intentsforfield(fieldid)
            field_info['times'] = msmd.timesforfield(fieldid)
            
            ms_metadata['fields'][fieldid] = field_info

        # ==================== ANTENNAS ====================
        task_logprint("Extracting antenna information...")
        ms_metadata['antennas'] = {}
        
        antenna_names = msmd.antennanames()
        for antid in range(basic['nantennas']):
            ant_info = {}
            ant_info['name'] = antenna_names[antid] if antid < len(antenna_names) else f"ant{antid}"
            ant_info['position'] = msmd.antennaposition(antid)
            ant_info['offset'] = msmd.antennaoffset(antid)
            ant_info['diameter'] = msmd.antennadiameter(antid)
            ant_info['station'] = msmd.antennastations([antid])[0] if msmd.antennastations([antid]) else f"station{antid}"
            
            ms_metadata['antennas'][antid] = ant_info

        # ==================== SCANS ====================
        task_logprint("Extracting scan information...")
        ms_metadata['scans'] = {}
        
        scan_numbers = msmd.scannumbers()
        for scan_num in scan_numbers:
            scan_info = {}
            scan_info['fields'] = msmd.fieldsforscan(scan_num)
            scan_info['spws'] = msmd.spwsforscan(scan_num)
            scan_info['antennas'] = msmd.antennasforscan(scan_num)
            scan_info['intents'] = msmd.intentsforscan(scan_num)
            scan_info['states'] = msmd.statesforscan(scan_num)
            scan_info['times'] = msmd.timesforscan(scan_num)
            
            # Calculate integration time for this scan
            if len(scan_info['times']) > 1:
                scan_info['integration_time'] = np.median(np.diff(scan_info['times']))
            else:
                scan_info['integration_time'] = 0.0
                
            ms_metadata['scans'][scan_num] = scan_info

        # ==================== OBSERVATIONS ====================
        task_logprint("Extracting observation information...")
        ms_metadata['observations'] = {}
        
        try:
            observatory_names = msmd.observatorynames()
            observers = msmd.observers()  
            projects = msmd.projects()
            
            for obsid in range(basic['nobservations']):
                obs_info = {}
                obs_info['observatory'] = observatory_names[obsid] if obsid < len(observatory_names) else f"obs{obsid}"
                obs_info['observer'] = observers[obsid] if obsid < len(observers) else f"observer{obsid}"
                obs_info['project'] = projects[obsid] if obsid < len(projects) else f"project{obsid}"
                obs_info['timerange'] = msmd.timerangeforobs(obsid)
                obs_info['schedule'] = msmd.schedule(obsid)
                
                # Get observatory position
                try:
                    obs_info['position'] = msmd.observatoryposition(obsid)
                except:
                    obs_info['position'] = None
                    
                ms_metadata['observations'][obsid] = obs_info
        except Exception as e:
            task_logprint(f"Warning: Could not extract all observation info: {e}")
            ms_metadata['observations'] = {}

        # ==================== INTENTS ====================
        task_logprint("Extracting intent information...")
        ms_metadata['intents'] = {}
        
        all_intents = msmd.intents()
        for intent in all_intents:
            intent_info = {}
            intent_info['fields'] = msmd.fieldsforintent(intent)
            intent_info['scans'] = msmd.scansforintent(intent)
            intent_info['spws'] = msmd.spwsforintent(intent)
            intent_info['times'] = msmd.timesforintent(intent)
            
            ms_metadata['intents'][intent] = intent_info

        # ==================== POLARIZATION ====================
        task_logprint("Extracting polarization information...")
        ms_metadata['polarization'] = {}
        
        # Get data description info to understand polarization setup
        try:
            # Get all data description IDs
            ddids = msmd.datadescids()
            for ddid in ddids:
                pol_info = {}
                pol_info['polid'] = msmd.polidfordatadesc(ddid)
                pol_info['spwid'] = msmd.spwfordatadesc(ddid)
                
                # Get correlation info for this polarization ID
                if pol_info['polid'] >= 0:
                    pol_info['ncorr'] = msmd.ncorrforpol(pol_info['polid'])
                    pol_info['corrtypes'] = msmd.corrtypesforpol(pol_info['polid'])
                    pol_info['corrprods'] = msmd.corrprodsforpol(pol_info['polid'])
                    
                ms_metadata['polarization'][ddid] = pol_info
        except Exception as e:
            task_logprint(f"Warning: Could not extract polarization info: {e}")

        # ==================== SOURCE INFORMATION ====================
        task_logprint("Extracting source information...")
        ms_metadata['source'] = {}
        
        try:
            source_ids = msmd.sourceidsfromsourcetable()
            source_names = msmd.sourcenames()
            source_dirs = msmd.sourcedirs()
            source_times = msmd.sourcetimes()
            proper_motions = msmd.propermotions()
            
            for i, src_id in enumerate(source_ids):
                src_info = {}
                src_info['source_id'] = src_id
                src_info['name'] = source_names[i] if i < len(source_names) else f"source{src_id}"
                src_info['direction'] = source_dirs.get(str(i), None)
                src_info['time'] = source_times.get(str(i), None)
                src_info['proper_motion'] = proper_motions.get(str(i), None)
                
                # Get rest frequencies and transitions if available
                for spwid in range(basic['nspw']):
                    try:
                        rest_freqs = msmd.restfreqs(src_id, spwid)
                        transitions = msmd.transitions(src_id, spwid)
                        src_info[f'restfreqs_spw{spwid}'] = rest_freqs
                        src_info[f'transitions_spw{spwid}'] = transitions
                    except:
                        pass
                        
                ms_metadata['source'][src_id] = src_info
        except Exception as e:
            task_logprint(f"Warning: Could not extract source info: {e}")

        # ==================== TIME INFORMATION ====================
        task_logprint("Extracting time information...")
        ms_metadata['time_info'] = {
            'scan_times': {},
            'field_times': {},
            'spw_times': {},
            'integration_times': {}
        }
        
        # Integration times per scan
        max_integration_time = 0.0
        for scan_num in scan_numbers:
            times = ms_metadata['scans'][scan_num]['times']
            if len(times) > 1:
                int_time = np.median(np.diff(times))
                ms_metadata['time_info']['integration_times'][scan_num] = int_time
                max_integration_time = max(max_integration_time, int_time)
        
        ms_metadata['time_info']['max_integration_time'] = max_integration_time

        # ==================== BASELINE INFORMATION ====================
        task_logprint("Extracting baseline information...")
        ms_metadata['baseline_info'] = {
            'baselines_matrix': msmd.baselines(),
            'nbaselines_cross': basic['nbaselines'],
            'nbaselines_with_auto': basic['nbaselines_with_autocorr']
        }

        # ==================== STATE INFORMATION ====================
        task_logprint("Extracting state information...")
        ms_metadata['state_info'] = {}
        
        for scan_num in scan_numbers:
            states = ms_metadata['scans'][scan_num]['states']
            for state in states:
                if state not in ms_metadata['state_info']:
                    ms_metadata['state_info'][state] = {
                        'scans': [],
                        'associated_scans': msmd.scansforstate(state)
                    }
                ms_metadata['state_info'][state]['scans'].append(scan_num)

        # ==================== DERIVED PIPELINE VARIABLES ====================
        task_logprint("Computing pipeline-specific variables...")
        
        # Store the comprehensive metadata
        pipeline_context["ms_metadata"] = ms_metadata
        
        # Extract commonly used variables for backward compatibility
        pipeline_context["numSpws"] = basic['nspw']
        pipeline_context["numFields"] = basic['nfields'] 
        pipeline_context["numAntenna"] = basic['nantennas']
        pipeline_context["field_names"] = field_names
        pipeline_context["intents"] = all_intents
        
        # Spectral window derived info
        reference_frequencies = [ms_metadata['spectral_windows'][spw]['reffreq_hz'] for spw in range(basic['nspw'])]
        spw_bandwidths = [ms_metadata['spectral_windows'][spw]['bandwidth_hz'] for spw in range(basic['nspw'])]
        center_frequencies = [ms_metadata['spectral_windows'][spw]['centerfreq_hz'] for spw in range(basic['nspw'])]
        channels = [ms_metadata['spectral_windows'][spw]['nchan'] for spw in range(basic['nspw'])]
        
        pipeline_context["center_frequencies"] = center_frequencies
        pipeline_context["channels"] = channels
        
        # EVLA bands
        bands = [ms_metadata['spectral_windows'][spw]['evla_band'] for spw in range(basic['nspw'])]
        unique_bands = uniq(bands)
        unique_bands_string = ",".join(map(str, unique_bands))
        task_logprint(f"EVLA bands present: {unique_bands_string}")

        # Field information
        field_positions = [ms_metadata['fields'][fid]['phasecenter'] for fid in range(basic['nfields'])]
        field_ids = list(range(basic['nfields']))
        pipeline_context["field_positions"] = field_positions
        pipeline_context["field_ids"] = field_ids
        
        # Field-spw mapping
        field_spws = [ms_metadata['fields'][fid]['spws'] for fid in range(basic['nfields'])]
        pipeline_context["field_spws"] = field_spws
        
        # Field-scan mapping
        field_scan_map = {fid: ms_metadata['fields'][fid]['scans'] for fid in range(basic['nfields'])}
        pipeline_context["field_scan_map"] = field_scan_map
        
        # Integration time
        pipeline_context["int_time"] = ms_metadata['time_info']['max_integration_time']
        
        # Calibration field extraction from intents
        calibration_intents = [
            'CALIBRATE_FLUX', 'CALIBRATE_BANDPASS', 'CALIBRATE_DELAY',
            'CALIBRATE_POL_ANGLE', 'CALIBRATE_POL_LEAKAGE', 'CALIBRATE_PHASE',
            'CALIBRATE_AMPLI', 'CALIBRATE_POINTING'
        ]
        
        cal_fields = {}
        cal_scans = {}
        cal_strings = {}
        
        for intent in calibration_intents:
            intent_key = intent.lower().replace('calibrate_', '')
            if intent in ms_metadata['intents']:
                cal_fields[intent_key] = ms_metadata['intents'][intent]['fields']
                cal_scans[intent_key] = ms_metadata['intents'][intent]['scans']
                cal_strings[f"{intent_key}_field_select_string"] = ",".join(map(str, cal_fields[intent_key]))
                cal_strings[f"{intent_key}_scan_select_string"] = ",".join(map(str, cal_scans[intent_key]))
            else:
                cal_fields[intent_key] = []
                cal_scans[intent_key] = []
                cal_strings[f"{intent_key}_field_select_string"] = ""
                cal_strings[f"{intent_key}_scan_select_string"] = ""
        
        # Store calibration info with legacy names
        pipeline_context["flux_field_list"] = cal_fields['flux']
        pipeline_context["bandpass_field_list"] = cal_fields['bandpass'] 
        pipeline_context["delay_field_list"] = cal_fields['delay']
        pipeline_context["polarization_angle_field_list"] = cal_fields['pol_angle']
        pipeline_context["polarization_lkg_field_list"] = cal_fields['pol_leakage']
        pipeline_context["phase_field_list"] = cal_fields['phase']
        pipeline_context["amp_field_list"] = cal_fields['ampli']
        pipeline_context["pointing_field_list"] = cal_fields['pointing']
        
        pipeline_context["flux_scan_list"] = cal_scans['flux']
        pipeline_context["bandpass_scan_list"] = cal_scans['bandpass']
        pipeline_context["delay_scan_list"] = cal_scans['delay']
        pipeline_context["polarization_angle_scan_list"] = cal_scans['pol_angle']
        pipeline_context["polarization_lkg_scan_list"] = cal_scans['pol_leakage']
        pipeline_context["phase_scan_list"] = cal_scans['phase']
        pipeline_context["amp_scan_list"] = cal_scans['ampli']
        pipeline_context["pointing_scan_list"] = cal_scans['pointing']
        
        # Selection strings with fallbacks
        pipeline_context["flux_field_select_string"] = cal_strings["flux_field_select_string"]
        pipeline_context["bandpass_field_select_string"] = cal_strings["bandpass_field_select_string"] or cal_strings["flux_field_select_string"]
        pipeline_context["delay_field_select_string"] = cal_strings["delay_field_select_string"] or cal_strings["bandpass_field_select_string"] or cal_strings["flux_field_select_string"]
        pipeline_context["phase_field_select_string"] = cal_strings["phase_field_select_string"]
        pipeline_context["amp_field_select_string"] = cal_strings["ampli_field_select_string"] or cal_strings["phase_field_select_string"]
        
        pipeline_context["flux_scan_select_string"] = cal_strings["flux_scan_select_string"]
        pipeline_context["bandpass_scan_select_string"] = cal_strings["bandpass_scan_select_string"] or cal_strings["flux_scan_select_string"]
        pipeline_context["delay_scan_select_string"] = cal_strings["delay_scan_select_string"] or cal_strings["bandpass_scan_select_string"]
        pipeline_context["phase_scan_select_string"] = cal_strings["phase_scan_select_string"]
        pipeline_context["amp_scan_select_string"] = cal_strings["ampli_scan_select_string"] or cal_strings["phase_scan_select_string"]
        
        pipeline_context["polarization_angle_field_select_string"] = cal_strings["pol_angle_field_select_string"]
        pipeline_context["polarization_angle_scan_select_string"] = cal_strings["pol_angle_scan_select_string"]
        pipeline_context["polarization_lkg_field_select_string"] = cal_strings["pol_leakage_field_select_string"]
        pipeline_context["polarization_lkg_scan_select_string"] = cal_strings["pol_leakage_scan_select_string"]

        # Polarization calibration logic
        polcals_A = ['J1331+3030', '3c286', '3C286', 'J0521+1638', '3c138', '3C138', 'J0137+3309', '0137+331=3C48', '3c48', '3C48']
        polcals_C = ['J0542+4951', '3c147', '3C147', 'J1407+2827', 'OQ208', 'Oq208', 'oq208', 'J0259+0747']

        if len(cal_fields['pol_angle']) == 0 and do_pol:
            task_logprint("Searching for standard polarization angle calibrators...")
            for polcal in polcals_A:
                try:
                    pol_angle_field_ids = msmd.fieldsforname(polcal)
                except:
                    pol_angle_field_ids = []
                if pol_angle_field_ids:
                    pipeline_context["polarization_angle_field_list"].extend(pol_angle_field_ids)
                    for field_id in pol_angle_field_ids:
                        scans = msmd.scansforfield(field_id)
                        pipeline_context["polarization_angle_scan_list"].extend(scans)
                    pipeline_context["polarization_angle_scan_list"] = sorted(list(set(pipeline_context["polarization_angle_scan_list"])))
                    break

        if not pipeline_context.get("polarization_angle_field_list") and do_pol:
            do_pol = False
            task_logprint("WARNING: No polarization angle calibrator found. Disabling polarization calibration.")

        if len(cal_fields['pol_leakage']) == 0 and do_pol:
            task_logprint("Searching for standard polarization leakage calibrators...")
            for polcal in polcals_C:
                try:
                    pol_lkg_field_ids = msmd.fieldsforname(polcal)
                except:
                    pol_lkg_field_ids = []
                if pol_lkg_field_ids:
                    pipeline_context["polarization_lkg_field_list"].extend(pol_lkg_field_ids)
                    for field_id in pol_lkg_field_ids:
                        scans = msmd.scansforfield(field_id)
                        pipeline_context["polarization_lkg_scan_list"].extend(scans)
                    pipeline_context["polarization_lkg_scan_list"] = sorted(list(set(pipeline_context["polarization_lkg_scan_list"])))
                    break

        if not pipeline_context.get("polarization_lkg_field_list") and do_pol:
            do_pol = False
            task_logprint("WARNING: No polarization leakage calibrator found. Disabling polarization calibration.")

        pipeline_context["do_pol"] = do_pol

        # Update polarization selection strings
        pipeline_context["polarization_angle_field_select_string"] = ",".join(map(str, pipeline_context.get("polarization_angle_field_list", [])))
        pipeline_context["polarization_angle_scan_select_string"] = ",".join(map(str, pipeline_context.get("polarization_angle_scan_list", [])))
        pipeline_context["polarization_lkg_field_select_string"] = ",".join(map(str, pipeline_context.get("polarization_lkg_field_list", [])))
        pipeline_context["polarization_lkg_scan_select_string"] = ",".join(map(str, pipeline_context.get("polarization_lkg_scan_list", [])))

        # Create combined calibrator field and scan selection strings
        # Union of all calibrator types (flux, BP, delay, phase, amp, pointing, pol)
        all_cal_fields = set()
        all_cal_scans = set()

        for cal_type in ['flux', 'bandpass', 'delay', 'phase', 'ampli', 'pointing']:
            all_cal_fields.update(cal_fields.get(cal_type, []))
            all_cal_scans.update(cal_scans.get(cal_type, []))

        # Add polarization calibrators if they exist
        all_cal_fields.update(pipeline_context.get("polarization_angle_field_list", []))
        all_cal_fields.update(pipeline_context.get("polarization_lkg_field_list", []))
        all_cal_scans.update(pipeline_context.get("polarization_angle_scan_list", []))
        all_cal_scans.update(pipeline_context.get("polarization_lkg_scan_list", []))

        # If no calibrators found via intents, try to identify non-target fields
        if not all_cal_fields:
            task_logprint("WARNING: No calibrators found via intents, attempting to identify by field names")
            # Look for standard calibrator names
            standard_cal_names = [
                '3c286', '3c138', '3c147', '3c48', '3c84',
                'j1331+3030', 'j0521+1638', 'j0137+3309', 'j0542+4951',
                '0137+331', '0542+498', '1331+305'
            ]

            for field_id, field_name in enumerate(field_names):
                field_name_lower = field_name.lower().replace(' ', '').replace('_', '')
                for cal_name in standard_cal_names:
                    if cal_name in field_name_lower:
                        all_cal_fields.add(field_id)
                        # Get scans for this field
                        try:
                            field_scans = msmd.scansforfield(field_id)
                            all_cal_scans.update(field_scans)
                            task_logprint(f"Identified calibrator by name: {field_name} (field {field_id})")
                        except:
                            pass
                        break

        # Create selection strings
        pipeline_context["calibrator_field_list"] = sorted(list(all_cal_fields))
        pipeline_context["calibrator_scan_list"] = sorted(list(all_cal_scans))
        pipeline_context["calibrator_field_select_string"] = ",".join(map(str, sorted(all_cal_fields)))
        pipeline_context["calibrator_scan_select_string"] = ",".join(map(str, sorted(all_cal_scans)))

        task_logprint(f"Identified {len(all_cal_fields)} calibrator field(s): {pipeline_context['calibrator_field_select_string']}")
        task_logprint(f"Identified {len(all_cal_scans)} calibrator scan(s): {pipeline_context['calibrator_scan_select_string']}")

        # Additional pipeline variables
        pipeline_context["minBL_for_cal"] = max(3, int(basic['nantennas'] / 2.0))

        # Check for 3C84 usage - search actual field names for 3C84 variants
        fields_3C84_ids = []
        field_names_lower = [name.lower() for name in field_names]
        c84_variants = ['3c84', '3c 84', 'j0319+4130', '0316+413']
        
        for i, field_name in enumerate(field_names_lower):
            if any(variant in field_name for variant in c84_variants):
                fields_3C84_ids.append(i)
                task_logprint(f"Found 3C84 variant field: {field_names[i]} (field {i})")
        
        cal3C84_d = any(field_id in cal_fields['delay'] for field_id in fields_3C84_ids) if fields_3C84_ids else False
        cal3C84_bp = any(field_id in cal_fields['bandpass'] for field_id in fields_3C84_ids) if fields_3C84_ids else False
        pipeline_context["cal3C84_d"] = cal3C84_d
        pipeline_context["cal3C84_bp"] = cal3C84_bp
        pipeline_context["uvrange3C84"] = '0~1800klambda' if cal3C84_d or cal3C84_bp else ""

        # SPW selection strings for calibration
        tst_delay_spw = ""
        all_spw = ",".join(map(str, range(basic['nspw'])))
        for ispw in range(basic['nspw']):
            endch1 = int(channels[ispw] / 3)
            endch2 = int(2 * channels[ispw] / 3)
            if ispw < basic['nspw'] - 1:
                tst_delay_spw += f"{ispw}:{endch1}~{endch2},"
            else:
                tst_delay_spw += f"{ispw}:{endch1}~{endch2}"
        pipeline_context["tst_delay_spw"] = tst_delay_spw
        pipeline_context["all_spw"] = all_spw
        pipeline_context["tst_bpass_spw"] = tst_delay_spw

        # Baseband/subband information for EVLA data
        spw_names = msmd.namesforspws()
        if len(spw_names) > 0 and "#" in spw_names[0]:
            bands_basebands_subbands = []
            for i, spw_name in enumerate(spw_names):
                parts = spw_name.split("#")
                if len(parts) == 3:
                    receiver_name, baseband, subband = parts
                    receiver_band = (receiver_name.split("_"))[1]
                    bands_basebands_subbands.append([receiver_band, baseband, int(subband), i])
            if bands_basebands_subbands:
                spws_info = []
                bands_basebands_subbands.sort(key=lambda x: (x[0], x[1], x[2]))
                current_band_bb = None
                current_spws = []
                current_indices = []
                for band, bb, sb, index in bands_basebands_subbands:
                    if (band, bb) == current_band_bb:
                        current_spws.append(sb)
                        current_indices.append(index)
                    else:
                        if current_band_bb is not None:
                            spws_info.append([current_band_bb[0], current_band_bb[1], sorted(current_spws), sorted(current_indices)])
                        current_band_bb = (band, bb)
                        current_spws = [sb]
                        current_indices = [index]
                if current_band_bb is not None:
                    spws_info.append([current_band_bb[0], current_band_bb[1], sorted(current_spws), sorted(current_indices)])
                pipeline_context["spws_info"] = spws_info
                
                critfrac = 0.9 / (basic['nspw'] / 8.0) if basic['nspw'] >= 8 else 0.9 / float(basic['nspw'])
                pipeline_context["critfrac"] = critfrac

        # Quacking scan identification
        scan_list = [scan_numbers[0]] if len(scan_numbers) > 0 else []
        if len(scan_numbers) > 1:
            first_scan_fields = set(msmd.fieldsforscan(scan_numbers[0]))
            first_scan_spws = set(msmd.spwsforscan(scan_numbers[0]))
            for i in range(1, len(scan_numbers)):
                current_scan_fields = set(msmd.fieldsforscan(scan_numbers[i]))
                current_scan_spws = set(msmd.spwsforscan(scan_numbers[i]))
                if (current_scan_fields != first_scan_fields) or (current_scan_spws != first_scan_spws):
                    scan_list.append(scan_numbers[i])
                    first_scan_fields = current_scan_fields
                    first_scan_spws = current_scan_spws
        pipeline_context["quack_scan_string"] = ",".join(map(str, sorted(scan_list))) if scan_list else ""

        # numSpws2 adjustment for pointing
        num_pointing_scans = len(cal_scans['pointing'])
        pipeline_context["numSpws2"] = basic['nspw'] - 2 if num_pointing_scans > 0 else basic['nspw']

        # Calculate tau
        pipeline_context["tau"] = calculate_tau(msname)
        task_logprint(f"Zenith opacity (tau): {pipeline_context['tau']}")

        # Extract startdate from summary for requantizer gain check
        summary = ms_metadata.get('basic_info', {}).get('summary', {})
        pipeline_context["startdate"] = float(summary.get("BeginTime", 0.0))
        task_logprint(f"Observation start date: {pipeline_context['startdate']:.2f} MJD")

        # ==================== RAW MSMD API DICT ====================
        task_logprint("Extracting raw msmd API calls for future reference...")
        ms_raw_api = {}
        
        # Basic scalar API calls
        ms_raw_api['summary'] = msmd.summary()
        ms_raw_api['name'] = msmd.name()
        ms_raw_api['nspw'] = msmd.nspw()
        ms_raw_api['nfields'] = msmd.nfields()
        ms_raw_api['nantennas'] = msmd.nantennas()
        ms_raw_api['nscans'] = msmd.nscans()
        ms_raw_api['nobservations'] = msmd.nobservations()
        ms_raw_api['nstates'] = msmd.nstates()
        ms_raw_api['nsources'] = msmd.nsources()
        ms_raw_api['nbaselines'] = msmd.nbaselines()
        ms_raw_api['nbaselines_ac'] = msmd.nbaselines(ac=True)
        ms_raw_api['nrows'] = msmd.nrows()
        ms_raw_api['nrows_cross'] = msmd.nrows(autoc=False)
        ms_raw_api['nrows_unflagged'] = msmd.nrows(flagged=False)
        ms_raw_api['effexposuretime'] = msmd.effexposuretime()
        
        # Array API calls
        ms_raw_api['scannumbers'] = msmd.scannumbers()
        ms_raw_api['fieldnames'] = msmd.fieldnames()
        ms_raw_api['antennanames'] = msmd.antennanames()
        ms_raw_api['intents'] = msmd.intents()
        ms_raw_api['observatorynames'] = msmd.observatorynames()
        ms_raw_api['observers'] = msmd.observers()
        ms_raw_api['projects'] = msmd.projects()
        ms_raw_api['namesforspws'] = msmd.namesforspws()
        ms_raw_api['baselines'] = msmd.baselines()
        ms_raw_api['datadescids'] = msmd.datadescids()
        
        # Per-spw API calls
        ms_raw_api['spw_api'] = {}
        for spwid in range(basic['nspw']):
            spw_api = {}
            spw_api['nchan'] = msmd.nchan(spwid)
            spw_api['reffreq'] = msmd.reffreq(spwid)
            spw_api['bandwidths'] = msmd.bandwidths(spwid)
            spw_api['chanfreqs'] = msmd.chanfreqs(spwid)
            spw_api['chanwidths'] = msmd.chanwidths(spwid)
            spw_api['chanres'] = msmd.chanres(spwid)
            spw_api['chaneffbws'] = msmd.chaneffbws(spwid)
            spw_api['meanfreq'] = msmd.meanfreq(spwid)
            try:
                spw_api['baseband'] = msmd.baseband(spwid)
            except:
                spw_api['baseband'] = None
            try:
                spw_api['sideband'] = msmd.sideband(spwid)
            except:
                spw_api['sideband'] = None
            try:
                spw_api['corrbit'] = msmd.corrbit(spwid)
            except:
                spw_api['corrbit'] = None
            ms_raw_api['spw_api'][spwid] = spw_api
            
        # Per-field API calls
        ms_raw_api['field_api'] = {}
        for fieldid in range(basic['nfields']):
            field_api = {}
            field_api['phasecenter'] = msmd.phasecenter(fieldid)
            field_api['refdir'] = msmd.refdir(fieldid)
            field_api['sourceid'] = msmd.sourceidforfield(fieldid)
            field_api['spws'] = msmd.spwsforfield(fieldid)
            field_api['scans'] = msmd.scansforfield(fieldid)
            field_api['intents'] = msmd.intentsforfield(fieldid)
            field_api['times'] = msmd.timesforfield(fieldid)
            ms_raw_api['field_api'][fieldid] = field_api
            
        # Per-antenna API calls
        ms_raw_api['antenna_api'] = {}
        for antid in range(basic['nantennas']):
            ant_api = {}
            ant_api['position'] = msmd.antennaposition(antid)
            ant_api['offset'] = msmd.antennaoffset(antid)
            ant_api['diameter'] = msmd.antennadiameter(antid)
            ant_api['stations'] = msmd.antennastations([antid])
            ms_raw_api['antenna_api'][antid] = ant_api
            
        # Per-scan API calls
        ms_raw_api['scan_api'] = {}
        for scan_num in scan_numbers:
            scan_api = {}
            scan_api['fields'] = msmd.fieldsforscan(scan_num)
            scan_api['spws'] = msmd.spwsforscan(scan_num)
            scan_api['antennas'] = msmd.antennasforscan(scan_num)
            scan_api['intents'] = msmd.intentsforscan(scan_num)
            scan_api['states'] = msmd.statesforscan(scan_num)
            scan_api['times'] = msmd.timesforscan(scan_num)
            ms_raw_api['scan_api'][scan_num] = scan_api
            
        # Per-intent API calls
        ms_raw_api['intent_api'] = {}
        for intent in all_intents:
            intent_api = {}
            intent_api['fields'] = msmd.fieldsforintent(intent)
            intent_api['scans'] = msmd.scansforintent(intent)
            intent_api['spws'] = msmd.spwsforintent(intent)
            intent_api['times'] = msmd.timesforintent(intent)
            ms_raw_api['intent_api'][intent] = intent_api
            
        # Per-observation API calls
        ms_raw_api['observation_api'] = {}
        for obsid in range(basic['nobservations']):
            obs_api = {}
            obs_api['timerange'] = msmd.timerangeforobs(obsid)
            obs_api['schedule'] = msmd.schedule(obsid)
            try:
                obs_api['position'] = msmd.observatoryposition(obsid)
            except:
                obs_api['position'] = None
            ms_raw_api['observation_api'][obsid] = obs_api
            
        # Source table API calls (if available)
        try:
            ms_raw_api['sourceidsfromsourcetable'] = msmd.sourceidsfromsourcetable()
            ms_raw_api['sourcenames'] = msmd.sourcenames()
            ms_raw_api['sourcedirs'] = msmd.sourcedirs()
            ms_raw_api['sourcetimes'] = msmd.sourcetimes()
            ms_raw_api['propermotions'] = msmd.propermotions()
        except:
            ms_raw_api['source_table_error'] = "Source table not accessible"
            
        # Store the complete raw API dict
        pipeline_context["ms_raw_api"] = ms_raw_api
        task_logprint("✓ Raw msmd API extraction completed")

        # Success
        pipeline_context["QA2_msinfo"] = QA2_msinfo
        task_logprint("✓ Comprehensive MS metadata extraction completed successfully")

    except Exception as e:
        import traceback
        task_logprint(f"Error during get_ms_info with msmetadata: {e}")
        task_logprint(f"Full traceback: {traceback.format_exc()}")
        pipeline_context["QA2_msinfo"] = "Fail"
    finally:
        msmd.close()
        task_logprint(f"Finished get_ms_info (using msmetadata)")
        task_logprint(f"QA2 score: {format_qa_status(pipeline_context.get('QA2_msinfo', 'Unknown'))}")
        time_list = runtiming("msinfo", "end")

    return pipeline_context


@register_step("EVLA_pipe_msmd")
def EVLA_pipe_msmd(pipeline_context):
    """
    Main entry point for EVLA_pipe_msmd pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_msmd.py ***")
    time_list = runtiming("msmd", "start")
    
    # Call the main MS info gathering function
    pipeline_context = get_ms_info(pipeline_context)
    QA2_score = pipeline_context.get("QA2_msinfo", "Fail")
    
    # If msmd failed, raise exception to stop pipeline
    if QA2_score == "Fail":
        raise RuntimeError("MS metadata extraction failed - cannot proceed with pipeline")
    
    task_logprint(f"Finished EVLA_pipe_msmd.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("msmd", "end")
        
    # Update context and return
    pipeline_context["QA2_msmd"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context