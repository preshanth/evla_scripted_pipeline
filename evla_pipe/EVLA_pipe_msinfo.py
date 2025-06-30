import os
import numpy as np
import warnings
from casatasks import (listobs, plotweather, flagcmd, plotants)
from casatools import msmetadata
from casaplotms import plotms
from . import pipeline_save
from .utils import (
    uniq, runtiming, logprint, find_EVLA_band, spwsforfield, find_3C84,
    buildscans,
)


def get_ms_info(pipeline_context):
    """
    Collects and logs various information about the Measurement Set using msmetadata.
    Significantly refactored to use high-level msmetadata methods instead of table operations.

    Args:
        pipeline_context (dict): A dictionary containing the pipeline's context,
                                 including the msname.

    Returns:
        dict: Updated pipeline context with MS information.
    """
    msname = pipeline_context.get("msname")
    do_pol = pipeline_context.get("do_pol", False)

    if not msname:
        logprint("Error: Missing msname in pipeline context for get_ms_info.", logfileout="logs/msinfo.log")
        return "Fail"

    task_logprint = lambda msg: logprint(msg, logfileout="logs/msinfo.log")
    task_logprint("*** Starting get_ms_info (msmetadata refactored) ***")
    time_list = runtiming("msinfo", "start")
    QA2_msinfo = "Pass"

    # Initialize msmetadata tool
    msmd = msmetadata()
    
    try:
        msmd.open(msname)
        
        # Generate listobs file
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

        # Get spectral window information using msmetadata
        numSpws = msmd.nspw()
        channels = [msmd.nchan(spw) for spw in range(numSpws)]
        spw_bandwidths = msmd.bandwidths()
        reference_frequencies = [msmd.reffreq(spw)['m0']['value'] for spw in range(numSpws)]
        spw_names = msmd.namesforspws()
        
        # Calculate center frequencies and bands
        center_frequencies = [
            ref + bw / 2 for ref, bw in zip(reference_frequencies, spw_bandwidths)
        ]
        bands = [find_EVLA_band(center) for center in center_frequencies]
        unique_bands = uniq(bands)
        unique_bands_string = ",".join(str(ii) for ii in unique_bands)
        task_logprint(f"unique band string = {unique_bands_string}")
        pipeline_context["center_frequencies"] = center_frequencies

        # Set up spw selection for initial gain solutions
        tst_delay_spw = ""
        all_spw = ""
        for ispw in range(numSpws):
            endch1 = int(channels[ispw] / 3)
            endch2 = int(2 * channels[ispw] / 3) + 1
            if ispw < numSpws - 1:
                tst_delay_spw += f"{ispw}:{endch1}~{endch2},"
                all_spw += f"{ispw},"
            else:
                tst_delay_spw += f"{ispw}:{endch1}~{endch2}"
                all_spw += str(ispw)
        
        pipeline_context.update({
            "tst_delay_spw": tst_delay_spw,
            "all_spw": all_spw,
            "tst_bpass_spw": tst_delay_spw,
            "numSpws": numSpws
        })

        # Get field information using msmetadata
        numFields = msmd.nfields()
        field_names = list(msmd.fieldnames())
        field_ids = list(range(numFields))
        
        # Get field positions - need to use lower-level access for this
        field_positions = []
        for field_id in range(numFields):
            phasecenter = msmd.phasecenter(field_id)
            field_positions.append([phasecenter['m0']['value'], phasecenter['m1']['value']])
        field_positions = np.array(field_positions).T
        
        pipeline_context.update({
            "numFields": numFields,
            "field_names": field_names,
            "field_ids": field_ids,
            "field_positions": field_positions
        })

        # Map field IDs to spws using msmetadata
        field_spws = [list(msmd.spwsforfield(field_id)) for field_id in range(numFields)]
        pipeline_context["field_spws"] = field_spws

        # Get scan information using msmetadata
        scanNums = list(msmd.scannumbers())
        field_scans = []
        for field_id in range(numFields):
            scans_for_field = list(msmd.scansforfield(field_id))
            field_scans.append(scans_for_field)
        pipeline_context.update({
            "scanNums": scanNums,
            "field_scans": field_scans
        })

        # Get intent information using msmetadata
        intents = list(msmd.intents())
        pipeline_context["intents"] = intents

        # Get integration time information
        # Note: For this we still need to use the ms tool as msmetadata doesn't provide scan summary
        from casatools import ms as mstool
        ms = mstool()
        ms.open(msname)
        scan_summary = ms.getscansummary()
        ms_summary = ms.summary()
        ms.close()
        
        startdate = float(ms_summary.get("BeginTime", 0.0))
        sorted_scan_list = sorted([int(scan) for scan in scan_summary])
        integration_times = [
            scan_summary[str(ii)]["0"].get("IntegrationTime", 0.0)
            for ii in sorted_scan_list
        ]
        maximum_integration_time = max(integration_times) if integration_times else 0.0
        int_time = maximum_integration_time
        median_integration_time = np.median(integration_times) if integration_times else 0.0
        
        pipeline_context.update({
            "scan_summary": scan_summary,
            "int_time": int_time,
            "startdate": startdate
        })

        if maximum_integration_time != median_integration_time and integration_times:
            task_logprint("Warning:")
            task_logprint(f"Median integration time = {median_integration_time}")
            task_logprint(f"Maximum integration time = {maximum_integration_time}")

        task_logprint(f"Maximum integration time is {maximum_integration_time}s")

        # Find scans for quacking
        scan_list = [1]
        if sorted_scan_list:
            old_scan = scan_summary.get(str(sorted_scan_list[0]), {}).get("0", {})
            old_field = old_scan.get("FieldId")
            old_spws = old_scan.get("SpwIds", [])
            for ii in range(1, len(sorted_scan_list)):
                new_scan = scan_summary.get(str(sorted_scan_list[ii]), {}).get("0", {})
                new_field = new_scan.get("FieldId")
                new_spws = new_scan.get("SpwIds", [])
                if (new_field != old_field) or (set(new_spws) != set(old_spws)):
                    scan_list.append(sorted_scan_list[ii])
                    old_field = new_field
                    old_spws = new_spws
        
        quack_scan_string = ",".join(str(ii) for ii in scan_list)
        pipeline_context["quack_scan_string"] = quack_scan_string
        task_logprint(f"Scans to quack: {quack_scan_string}")

        # Process baseband information (simplified)
        sorted_frequencies = sorted(reference_frequencies)
        low_spws = []
        high_spws = []
        
        # Simplified baseband detection - group by similar frequencies
        freq_groups = []
        current_group = [0]
        
        for i in range(1, len(sorted_frequencies)):
            if abs(sorted_frequencies[i] - sorted_frequencies[i-1]) < 1e9:  # 1 GHz threshold
                current_group.append(i)
            else:
                freq_groups.append(current_group)
                current_group = [i]
        freq_groups.append(current_group)
        
        # For groups with multiple spws, mark first and last as edge spws
        for group in freq_groups:
            if len(group) > 1:
                low_spws.append(group[0])
                high_spws.append(group[-1])
        
        pipeline_context.update({
            "low_spws": low_spws,
            "high_spws": high_spws
        })
        task_logprint(f"Bottom ends of baseband filters are spws: {low_spws}")
        task_logprint(f"Top ends of baseband filters are spws: {high_spws}")

        # Process calibrator intents using msmetadata
        flux_scans = []
        bandpass_scans = []
        delay_scans = []
        phase_scans = []
        amp_scans = []
        polarization_angle_scans = []
        polarization_lkg_scans = []
        
        # Get scans for different intents using msmetadata
        try:
            flux_scans = list(msmd.scansforintent("*FLUX*"))
        except:
            flux_scans = []
            
        try:
            bandpass_scans = list(msmd.scansforintent("*BANDPASS*"))
        except:
            bandpass_scans = []
            
        try:
            delay_scans = list(msmd.scansforintent("*DELAY*"))
        except:
            delay_scans = []
            
        try:
            phase_scans = list(msmd.scansforintent("*PHASE*"))
        except:
            phase_scans = []
            
        try:
            amp_scans = list(msmd.scansforintent("*AMPLI*"))
        except:
            amp_scans = []
            
        try:
            polarization_angle_scans = list(msmd.scansforintent("*POL*ANGLE*"))
            polarization_lkg_scans = list(msmd.scansforintent("*POL*LEAK*"))
        except:
            polarization_angle_scans = []
            polarization_lkg_scans = []

        # Handle fallbacks and get field information
        if not flux_scans:
            QA2_msinfo = "Fail"
            task_logprint("ERROR: No flux density calibration scans found")
            raise Exception("No flux density calibration scans found")
        
        flux_scan_select_string = ",".join(map(str, flux_scans))
        flux_fields = []
        for scan in flux_scans:
            flux_fields.extend(msmd.fieldsforscan(scan))
        flux_field_select_string = ",".join(map(str, set(flux_fields)))
        
        task_logprint(f"Flux density calibrator(s) scans are {flux_scan_select_string}")
        task_logprint(f"Flux density calibrator(s) are fields {flux_field_select_string}")

        # Handle bandpass calibrator
        if not bandpass_scans:
            task_logprint("No bandpass calibration scans defined, using flux density calibrator")
            bandpass_scan_select_string = flux_scan_select_string
            bandpass_field_select_string = flux_field_select_string
        else:
            bandpass_scan_select_string = ",".join(map(str, bandpass_scans))
            bandpass_fields = []
            for scan in bandpass_scans:
                bandpass_fields.extend(msmd.fieldsforscan(scan))
            bandpass_field_select_string = ",".join(map(str, set(bandpass_fields)))
            task_logprint(f"Bandpass calibrator(s) scans are {bandpass_scan_select_string}")
            task_logprint(f"Bandpass calibrator(s) are fields {bandpass_field_select_string}")

        # Handle delay calibrator
        if not delay_scans:
            task_logprint("No delay calibration scans defined, using bandpass calibrator")
            delay_scan_select_string = bandpass_scan_select_string
            delay_field_select_string = bandpass_field_select_string
        else:
            delay_scan_select_string = ",".join(map(str, delay_scans))
            delay_fields = []
            for scan in delay_scans:
                delay_fields.extend(msmd.fieldsforscan(scan))
            delay_field_select_string = ",".join(map(str, set(delay_fields)))
            task_logprint(f"Delay calibrator(s) scans are {delay_scan_select_string}")
            task_logprint(f"Delay calibrator(s) are fields {delay_field_select_string}")

        # Handle polarization calibrators
        polcals_A = ['J1331+3030', '3c286', '3C286', 'J0521+1638', '3c138', '3C138', 'J0137+3309', '0137+331=3C48', '3c48', '3C48']
        polcals_C = ['J0542+4951', '3c147', '3C147', 'J1407+2827', 'OQ208', 'Oq208', 'oq208', 'J0259+0747']
        
        polarization_angle_scan_select_string = ""
        polarization_angle_field_select_string = ""
        polarization_lkg_scan_select_string = ""
        polarization_lkg_field_select_string = ""

        if not polarization_angle_scans and do_pol:
            task_logprint("WARNING: No polarization calibration scans defined, but polarization calibration was requested.")
            task_logprint("Searching for polarization angle calibrators...")
            
            # Search for standard polarization calibrators in field names
            for polcal in polcals_A:
                if polcal in field_names:
                    pol_field_id = field_names.index(polcal)
                    pol_scans = list(msmd.scansforfield(pol_field_id))
                    if pol_scans:
                        polarization_angle_scans.extend(pol_scans)
                        task_logprint(f'Found scan for {polcal}!')
                        break
            
            if not polarization_angle_scans:
                do_pol = False
                task_logprint("WARNING: No polarization calibration scans found, no polarization calibration possible.")
            else:
                # Search for leakage calibrators
                for polcal in polcals_C:
                    if polcal in field_names:
                        pol_field_id = field_names.index(polcal)
                        pol_scans = list(msmd.scansforfield(pol_field_id))
                        if pol_scans:
                            polarization_lkg_scans.extend(pol_scans)
                            task_logprint(f'Found scan for {polcal}!')
                            break
                
                if not polarization_lkg_scans:
                    task_logprint('WARNING: None of the standard pol leakage calibrators are available in the MS')
                    do_pol = False

        # Format polarization scan strings
        if polarization_angle_scans:
            polarization_angle_scan_select_string = ",".join(map(str, polarization_angle_scans))
            pol_angle_fields = []
            for scan in polarization_angle_scans:
                pol_angle_fields.extend(msmd.fieldsforscan(scan))
            polarization_angle_field_select_string = ",".join(map(str, set(pol_angle_fields)))
            task_logprint(f"Polarization angle calibrator(s) scans are {polarization_angle_scan_select_string}")
            task_logprint(f"Polarization angle calibrator(s) are fields {polarization_angle_field_select_string}")

        if polarization_lkg_scans:
            polarization_lkg_scan_select_string = ",".join(map(str, polarization_lkg_scans))
            pol_lkg_fields = []
            for scan in polarization_lkg_scans:
                pol_lkg_fields.extend(msmd.fieldsforscan(scan))
            polarization_lkg_field_select_string = ",".join(map(str, set(pol_lkg_fields)))
            task_logprint(f"Polarization lkg calibrator(s) scans are {polarization_lkg_scan_select_string}")
            task_logprint(f"Polarization lkg calibrator(s) are fields {polarization_lkg_field_select_string}")

        # Handle phase calibrator
        if not phase_scans:
            QA2_msinfo = "Fail"
            task_logprint("ERROR: No gain calibration scans found")
            raise Exception("No gain calibration scans found")
        
        phase_scan_select_string = ",".join(map(str, phase_scans))
        phase_fields = []
        for scan in phase_scans:
            phase_fields.extend(msmd.fieldsforscan(scan))
        phase_field_select_string = ",".join(map(str, set(phase_fields)))
        task_logprint(f"Phase calibrator(s) scans are {phase_scan_select_string}")
        task_logprint(f"Phase calibrator(s) are fields {phase_field_select_string}")

        # Handle amplitude calibrator
        if not amp_scans:
            task_logprint("No amplitude calibration scans defined, will use phase calibrator")
            amp_scan_select_string = phase_scan_select_string
            amp_field_select_string = phase_field_select_string
        else:
            amp_scan_select_string = ",".join(map(str, amp_scans))
            amp_fields = []
            for scan in amp_scans:
                amp_fields.extend(msmd.fieldsforscan(scan))
            amp_field_select_string = ",".join(map(str, set(amp_fields)))
            task_logprint(f"Amplitude calibrator(s) scans are {amp_scan_select_string}")
            task_logprint(f"Amplitude calibrator(s) are fields {amp_field_select_string}")

        # Store all calibrator information in pipeline context
        pipeline_context.update({
            "flux_field_select_string": flux_field_select_string,
            "bandpass_scan_select_string": bandpass_scan_select_string,
            "bandpass_field_select_string": bandpass_field_select_string,
            "delay_scan_select_string": delay_scan_select_string,
            "delay_field_select_string": delay_field_select_string,
            "polarization_angle_scan_select_string": polarization_angle_scan_select_string,
            "polarization_angle_field_select_string": polarization_angle_field_select_string,
            "polarization_lkg_scan_select_string": polarization_lkg_scan_select_string,
            "polarization_lkg_field_select_string": polarization_lkg_field_select_string,
            "phase_scan_select_string": phase_scan_select_string,
            "phase_field_select_string": phase_field_select_string,
            "amp_scan_select_string": amp_scan_select_string,
            "amp_field_select_string": amp_field_select_string,
            "do_pol": do_pol
        })

        # Weather information
        if ((startdate >= 55918.80) and (startdate <= 55938.98)) or \
                ((startdate >= 56253.6) and (startdate <= 56271.6)):
            task_logprint(
                "Weather station broken during this period, using 100% "
                "seasonal model for calculating the zenith opacity"
            )
            tau = plotweather(vis=msname, seasonal_weight=1.0, doPlot=True)
        else:
            tau = plotweather(vis=msname, seasonal_weight=0.5, doPlot=True)
        pipeline_context["tau"] = tau

        # Get antenna information using msmetadata
        numAntenna = msmd.nantennas()
        nameAntenna = list(msmd.antennanames())
        pipeline_context.update({
            "numAntenna": numAntenna,
            "nameAntenna": nameAntenna
        })

        # Calculate pointing-adjusted spw count
        try:
            pointing_scans = list(msmd.scansforintent("*POINTING*"))
            numSpws2 = numSpws - 2 if pointing_scans else numSpws
        except:
            numSpws2 = numSpws
        pipeline_context["numSpws2"] = numSpws2

        task_logprint(f"Zenith opacities based on weather data are: {tau}")

        # Get correlation information
        scandict = buildscans(msname)
        corrstring_list = scandict.get("DataDescription", [{}])[0].get("corrdesc", [])
        removal_list = ["RL", "LR", "XY", "YX"]
        corrstring_list = list(set(corrstring_list).difference(set(removal_list)))
        corrstring = ",".join(corrstring_list)
        pipeline_context["corrstring"] = corrstring
        task_logprint(f"Correlations shown in plotms will be {corrstring}")

        minBL_for_cal = max(3, int(numAntenna / 2.0))
        pipeline_context["minBL_for_cal"] = minBL_for_cal

        # Check for 3C84 usage
        fields_3C84 = find_3C84(field_positions.T.squeeze()) if field_positions.size > 0 else []
        cal3C84_d = any(str(field_int) in delay_field_select_string for field_int in fields_3C84)
        cal3C84_bp = any(str(field_int) in bandpass_field_select_string for field_int in fields_3C84)
        
        uvrange3C84 = ""
        if cal3C84_d:
            task_logprint("WARNING: 3C84 was observed as a delay calibrator, uvrange limits may be used")
            uvrange3C84 = '0~1800klambda'
        elif cal3C84_bp:
            task_logprint("WARNING: 3C84 was observed as a BP calibrator, uvrange limits may be used")
            uvrange3C84 = '0~1800klambda'
        
        pipeline_context.update({
            "cal3C84_d": cal3C84_d,
            "cal3C84_bp": cal3C84_bp,
            "uvrange3C84": uvrange3C84
        })

        # Set critfrac based on spw count
        critfrac = 0.9 / int(len(spw_names) / 8.0) if len(spw_names) >= 8 else 0.9 / float(len(spw_names))
        pipeline_context["critfrac"] = critfrac

    except Exception as e:
        task_logprint(f"Error in get_ms_info: {e}")
        QA2_msinfo = "Fail"
        
    finally:
        msmd.close()

    pipeline_context["QA2_msinfo"] = QA2_msinfo
    task_logprint(f"Finished get_ms_info (msmetadata refactored)")
    task_logprint(f"QA2 score: {QA2_msinfo}")
    time_list = runtiming("msinfo", "end")

    return pipeline_context