# EVLA_pipe_msinfo.py
import os
import numpy as np
import warnings
from glob import glob
from casatasks import (listobs, plotweather, flagcmd, plotants)
from casatools import table
from casatools import ms as mstool
from casaplotms import plotms
from casatools import msmetadata
from . import pipeline_save
from .utils import (
    uniq, runtiming, logprint, find_EVLA_band, spwsforfield, find_3C84,
    buildscans,
)

tb = table()
ms = mstool()


def calculate_tau(msname):
    """
    Calculates the zenith opacity (tau) using plotweather.

    Args:
        msname (str): The name of the Measurement Set.

    Returns:
        float: The calculated zenith opacity (tau).
    """
    task_logprint = lambda msg: logprint(msg, logfileout="logs/msinfo.log")
    startdate = 0.0
    try:
        msmd = msmetadata.msmetadata()
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
    Collects and logs various information about the Measurement Set using msmetadata.

    Args:
        pipeline_context (dict): A dictionary containing the pipeline's context,
                                 including the msname.

    Returns:
        dict: Updated pipeline context with MS information.
    """
    msname = pipeline_context.get("msname")
    do_pol = pipeline_context.get("do_pol")

    if not msname:
        logprint("Error: Missing msname in pipeline context for get_ms_info.", logfileout="logs/msinfo.log")
        return "Fail"

    task_logprint = lambda msg: logprint(msg, logfileout="logs/msinfo.log")
    task_logprint("*** Starting get_ms_info (using msmetadata) ***")
    time_list = runtiming("msinfo", "start")
    QA2_msinfo = "Pass"
    msmd = msmetadata.msmetadata()
    try:
        msmd.open(msname)

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

        # Identify SpW information.
        reference_frequencies = msmd.reffreqs()
        spw_bandwidths = msmd.bandwidths()
        numSpws = msmd.nspw()
        center_frequencies = [
            ref + bw / 2 for ref, bw in zip(reference_frequencies, spw_bandwidths)
        ]
        pipeline_context["center_frequencies"] = center_frequencies

        bands = [find_EVLA_band(center) for center in center_frequencies]
        unique_bands = uniq(bands)
        unique_bands_string = ",".join(map(str, unique_bands))
        task_logprint(f"unique band string = {unique_bands_string}")

        # Set up spw selection for initial gain solutions
        channels = [msmd.nchan(spwid) for spwid in range(numSpws)]
        tst_delay_spw = ""
        all_spw = ",".join(map(str, range(numSpws)))
        for ispw in range(numSpws):
            endch1 = int(channels[ispw] / 3)
            endch2 = int(2 * channels[ispw] / 3)
            if ispw < numSpws - 1:
                tst_delay_spw += f"{ispw}:{endch1}~{endch2},"
            else:
                tst_delay_spw += f"{ispw}:{endch1}~{endch2}"
        pipeline_context["tst_delay_spw"] = tst_delay_spw
        pipeline_context["all_spw"] = all_spw
        pipeline_context["tst_bpass_spw"] = tst_delay_spw

        # Identify number of fields, positions, and source IDs
        numFields = msmd.nfields()
        field_names = msmd.fieldnames()
        field_positions = msmd.phasecenters()
        field_ids = list(range(numFields))
        pipeline_context["numFields"] = numFields
        pipeline_context["field_names"] = field_names
        pipeline_context["field_positions"] = field_positions
        pipeline_context["field_ids"] = field_ids

        # Map field IDs to spws
        field_spws = [msmd.spwsforfield(fieldid) for fieldid in range(numFields)]
        pipeline_context["field_spws"] = field_spws

        # Get scan numbers and store field to scan mapping
        scan_numbers = msmd.scannumbers()
        field_scan_map = {field_id: msmd.scansforfield(field_id) for field_id in range(numFields)}
        pipeline_context["field_scan_map"] = field_scan_map

        # Get integration time
        max_integration_time = 0.0
        for scan_num in scan_numbers:
            times = msmd.timesforscan(scan_num)
            if times:
                integration_time = np.median(np.diff(times)) if len(times) > 1 else 0.0
                max_integration_time = max(max_integration_time, integration_time)
        pipeline_context["int_time"] = max_integration_time

        # Get unique intents
        intents = msmd.intents()
        pipeline_context["intents"] = intents

        # Identify calibrator fields and scans based on intent
        flux_fields = msmd.fieldsforintent('CALIBRATE_FLUX')
        bandpass_fields = msmd.fieldsforintent('CALIBRATE_BANDPASS')
        delay_fields = msmd.fieldsforintent('CALIBRATE_DELAY')
        polarization_angle_fields = msmd.fieldsforintent('CALIBRATE_POL_ANGLE')
        polarization_lkg_fields = msmd.fieldsforintent('CALIBRATE_POL_LEAKAGE')
        phase_fields = msmd.fieldsforintent('CALIBRATE_PHASE')
        amp_fields = msmd.fieldsforintent('CALIBRATE_AMPLI')
        pointing_fields = msmd.fieldsforintent('CALIBRATE_POINTING')

        pipeline_context["flux_field_list"] = flux_fields
        pipeline_context["bandpass_field_list"] = bandpass_fields
        pipeline_context["delay_field_list"] = delay_fields
        pipeline_context["polarization_angle_field_list"] = polarization_angle_fields
        pipeline_context["polarization_lkg_field_list"] = polarization_lkg_fields
        pipeline_context["phase_field_list"] = phase_fields
        pipeline_context["amp_field_list"] = amp_fields
        pipeline_context["pointing_field_list"] = pointing_fields

        flux_scans = sorted(list(set([scan for field_id in flux_fields for scan in msmd.scansforfield(field_id)])))
        bandpass_scans = sorted(list(set([scan for field_id in bandpass_fields for scan in msmd.scansforfield(field_id)])))
        delay_scans = sorted(list(set([scan for field_id in delay_fields for scan in msmd.scansforfield(field_id)])))
        polarization_angle_scans = sorted(list(set([scan for field_id in polarization_angle_fields for scan in msmd.scansforfield(field_id)])))
        polarization_lkg_scans = sorted(list(set([scan for field_id in polarization_lkg_fields for scan in msmd.scansforfield(field_id)])))
        phase_scans = sorted(list(set([scan for field_id in phase_fields for scan in msmd.scansforfield(field_id)])))
        amp_scans = sorted(list(set([scan for field_id in amp_fields for scan in msmd.scansforfield(field_id)])))
        pointing_scans = sorted(list(set([scan for field_id in pointing_fields for scan in msmd.scansforfield(field_id)])))

        pipeline_context["flux_scan_list"] = flux_scans
        pipeline_context["bandpass_scan_list"] = bandpass_scans
        pipeline_context["delay_scan_list"] = delay_scans
        pipeline_context["polarization_angle_scan_list"] = polarization_angle_scans
        pipeline_context["polarization_lkg_scan_list"] = polarization_lkg_scans
        pipeline_context["phase_scan_list"] = phase_scans
        pipeline_context["amp_scan_list"] = amp_scans
        pipeline_context["pointing_scan_list"] = pointing_scans

        pipeline_context["flux_field_select_string"] = ",".join(map(str, flux_fields)) if flux_fields else ""
        pipeline_context["bandpass_scan_select_string"] = ",".join(map(str, bandpass_scans)) if bandpass_scans else (",".join(map(str, flux_scans)) if flux_scans else "")
        pipeline_context["bandpass_field_select_string"] = ",".join(map(str, bandpass_fields)) if bandpass_fields else (",".join(map(str, flux_fields)) if flux_fields else "")
        pipeline_context["delay_scan_select_string"] = ",".join(map(str, delay_scans)) if delay_scans else (pipeline_context["bandpass_scan_select_string"] if bandpass_scans else "")
        pipeline_context["delay_field_select_string"] = ",".join(map(str, delay_fields)) if delay_fields else (pipeline_context["bandpass_field_select_string"] if bandpass_fields else "")
        pipeline_context["polarization_angle_scan_select_string"] = ",".join(map(str, polarization_angle_scans)) if polarization_angle_scans else ""
        pipeline_context["polarization_angle_field_select_string"] = ",".join(map(str, polarization_angle_fields)) if polarization_angle_fields else ""
        pipeline_context["polarization_lkg_scan_select_string"] = ",".join(map(str, polarization_lkg_scans)) if polarization_lkg_scans else ""
        pipeline_context["polarization_lkg_field_select_string"] = ",".join(map(str, polarization_lkg_fields)) if polarization_lkg_fields else ""
        pipeline_context["phase_scan_select_string"] = ",".join(map(str, phase_scans)) if phase_scans else ""
        pipeline_context["phase_field_select_string"] = ",".join(map(str, phase_fields)) if phase_fields else ""
        pipeline_context["amp_scan_select_string"] = ",".join(map(str, amp_scans)) if amp_scans else (pipeline_context["phase_scan_select_string"] if phase_scans else "")
        pipeline_context["amp_field_select_string"] = ",".join(map(str, amp_fields)) if amp_fields else (pipeline_context["phase_field_select_string"] if phase_fields else "")

        # Polarization Calibration Logic
        polcals_A = ['J1331+3030', '3c286', '3C286', 'J0521+1638', '3c138', '3C138', 'J0137+3309', '0137+331=3C48', '3c48', '3C48']
        polcals_C = ['J0542+4951', '3c147', '3C147', 'J1407+2827', 'OQ208', 'Oq208', 'oq208', 'J0259+0747']

        if not polarization_angle_fields and do_pol:
            warnings.warn("WARNING: No polarization angle calibration scans defined, checking for standard calibrators...")
            task_logprint("Searching for polarization angle calibrators...")
            for polcal in polcals_A:
                pol_angle_field_ids = msmd.fieldsforname(polcal)
                if pol_angle_field_ids:
                    pipeline_context["polarization_angle_field_list"].extend(pol_angle_field_ids)
                    pipeline_context["polarization_angle_scan_list"].extend(sorted(list(set([scan for field_id in pol_angle_field_ids for scan in msmd.scansforfield(field_id)]))))
                    break

        if not pipeline_context.get("polarization_angle_field_list") and do_pol:
            do_pol = False
            warnings.warn("WARNING: No polarization angle calibrator found. Skipping polarization calibration.")
            task_logprint("WARNING: No polarization angle calibrator found. Skipping polarization calibration.")

        if not polarization_lkg_fields and do_pol:
            warnings.warn("WARNING: No polarization leakage calibration scans defined, checking for standard calibrators...")
            task_logprint("Searching for polarization leakage calibrators...")
            for polcal in polcals_C:
                pol_lkg_field_ids = msmd.fieldsforname(polcal)
                if pol_lkg_field_ids:
                    pipeline_context["polarization_lkg_field_list"].extend(pol_lkg_field_ids)
                    pipeline_context["polarization_lkg_scan_list"].extend(sorted(list(set([scan for field_id in pol_lkg_field_ids for scan in msmd.scansforfield(field_id)]))))
                    break

        if not pipeline_context.get("polarization_lkg_field_list") and do_pol:
            warnings.warn('WARNING: None of the standard pol leakage calibrators are available. Skipping polarization calibration!')
            task_logprint('WARNING: None of the standard pol leakage calibrators are available. Skipping polarization calibration!')
            do_pol = False

        pipeline_context["polarization_angle_field_select_string"] = ",".join(map(str, pipeline_context.get("polarization_angle_field_list", [])))
        pipeline_context["polarization_angle_scan_select_string"] = ",".join(map(str, pipeline_context.get("polarization_angle_scan_list", [])))
        pipeline_context["polarization_lkg_field_select_string"] = ",".join(map(str, pipeline_context.get("polarization_lkg_field_list", [])))
        pipeline_context["polarization_lkg_scan_select_string"] = ",".join(map(str, pipeline_context.get("polarization_lkg_scan_list", [])))
        pipeline_context["do_pol"] = do_pol

        # Get number of antennas
        numAntenna = msmd.nantennas()
        pipeline_context["numAntenna"] = numAntenna
        pipeline_context["minBL_for_cal"] = max(3, int(numAntenna / 2.0))

        # Determine if 3C84 was used as a bandpass or delay calibrator
        fields_3C84_ids = msmd.fieldsforname('3C84')
        cal3C84_d = any(field_id in delay_fields for field_id in fields_3C84_ids) if fields_3C84_ids else False
        cal3C84_bp = any(field_id in bandpass_fields for field_id in fields_3C84_ids) if fields_3C84_ids else False
        pipeline_context["cal3C84_d"] = cal3C84_d
        pipeline_context["cal3C84_bp"] = cal3C84_bp
        pipeline_context["uvrange3C84"] = '0~1800klambda' if cal3C84_d or cal3C84_bp else ""

        # Identify bands/basebands/spws
        spw_names = msmd.namesforspws(range(numSpws))
        if spw_names and "#" in spw_names[0]:
            bands_basebands_subbands = []
            for i, spw_name in enumerate(spw_names):
                parts = spw_name.split("#")
                if len(parts) == 3:
                    receiver_name, baseband, subband = parts
                    receiver_band = (receiver_name.split("_"))[1]
                    bands_basebands_subbands.append([receiver_band, baseband, int(subband), i])
            if bands_basebands_subbands:
                spws_info = []
                bands = []
                for band, bb, sb, index in bands_basebands_subbands:
                    bands_basebands_subbands.sort(key=lambda x: (x[0], x[1], x[2])) # Sort by band, baseband, subband
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

                critfrac = 0.9 / (numSpws / 8.0) if numSpws >= 8 else 0.9 / float(numSpws)
                pipeline_context["critfrac"] = critfrac

        # Identify scans for quacking
        scan_list = [scan_numbers[0]] if scan_numbers else []
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
        task_logprint(f"Scans to quack: {pipeline_context.get('quack_scan_string', '')}")

        # Adjust numSpws2 based on pointing scans
        num_pointing_scans = len(pipeline_context.get("pointing_scan_list", []))
        if num_pointing_scans > 0:
            pipeline_context["numSpws2"] = numSpws - 2
        else:
            pipeline_context["numSpws2"] = numSpws

        # Calculate tau using the helper function
        pipeline_context["tau"] = calculate_tau(msname)
        task_logprint(f"Zenith opacities based on weather data are: {pipeline_context['tau']}")

        pipeline_context["QA2_msinfo"] = QA2_msinfo

    except Exception as e:
        task_logprint(f"Error during get_ms_info with msmetadata: {e}")
        pipeline_context["QA2_msinfo"] = "Fail"
    finally:
        msmd.close()
        task_logprint(f"Finished get_ms_info (using msmetadata)")
        task_logprint(f"QA2 score: {pipeline_context.get('QA2_msinfo', 'Unknown')}")
        time_list = runtiming("msinfo", "end")

        # pipeline_save() # We'll handle saving in the main orchestration

    return pipeline_context
