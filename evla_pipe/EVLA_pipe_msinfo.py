######################################################################
#
# Copyright (C) 2013
# Associated Universities, Inc. Washington DC, USA,
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Library General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Library General Public
# License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with this library; if not, write to the Free Software Foundation,
# Inc., 675 Massachusetts Ave, Cambridge, MA 02139, USA.
#
# Correspondence concerning VLA Pipelines should be addressed as follows:
#    Please register and submit helpdesk tickets via: https://help.nrao.edu
#    Postal address:
#              National Radio Astronomy Observatory
#              VLA Pipeline Support Office
#              PO Box O
#              Socorro, NM,  USA
#
######################################################################
# FIXME Many operations in this script could be replaced by functions
# in the `msmetadata` toolkit instead of using the `table` tool directly.

import numpy as np

from casatasks import (listobs, plotweather, flagcmd, plotants)
from casatools import table
from casatools import ms as mstool
from casaplotms import plotms

from .utils import (
        uniq, runtiming, logprint, pipeline_save, find_EVLA_band, spwsforfield,
        find_3C84,
)

tb = table()
ms = mstool()


def task_logprint(msg):
    logprint(msg, logfileout="logs/msinfo.log")


task_logprint("Starting EVLA_pipe_msinfo.py")
time_list = runtiming("msinfo", "start")
QA2_msinfo = "Pass"

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
try:
    tb.open(msname + "/SPECTRAL_WINDOW")
    channels = tb.getcol("NUM_CHAN")
    originalBBClist = tb.getcol("BBC_NO")
    spw_bandwidths = tb.getcol("TOTAL_BANDWIDTH")
    reference_frequencies = tb.getcol("REF_FREQUENCY")
finally:
    tb.close()
center_frequencies = [
        reference + bandwidth / 2
        for reference, bandwidth in zip(reference_frequencies, spw_bandwidths)
]
bands = [find_EVLA_band(center) for center in center_frequencies]
unique_bands = uniq(bands)
unique_bands_string = ",".join(str(ii) for ii in unique_bands)
task_logprint(f"unique band string = {unique_bands_string}")
numSpws = len(channels)

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
tst_bpass_spw = tst_delay_spw

# Identify number of fields, positions, and source IDs
try:
    tb.open(f"{msname}/FIELD")
    numFields = tb.nrows()
    field_positions = tb.getcol("PHASE_DIR")
    field_ids = range(numFields)
    field_names = tb.getcol("NAME")
finally:
    tb.close()

# Map field IDs to spws
field_spws = [spwsforfield(msname, ii) for ii in range(numFields)]

# Identify scan numbers, map scans to field ID, and run scan summary
# (needed for figuring out integration time later).
try:
    tb.open(msname)
    scanNums = sorted(np.unique(tb.getcol("SCAN_NUMBER")))
    field_scans = []
    for ii in range(numFields):
        subtable = tb.query(f"FIELD_ID=={ii}")
        field_scans.append(list(np.unique(subtable.getcol("SCAN_NUMBER"))))
        subtable.close()
finally:
    tb.close()

## NOTE
## field_scans is now a list of lists containing the scans for each field.
## So, to access all the scans for the fields, one would:
#
# for ii in range(len(field_scans)):
#   for jj in range(len(field_scans[ii])):
#     pass
#
## the jj'th scan of the ii'th field is in field_scans[ii][jj]

# Identify intents
try:
    tb.open(f"{msname}/STATE")
    intents = tb.getcol("OBS_MODE")
finally:
    tb.close()

# Figure out integration time used
try:
    ms.open(msname)
    scan_summary = ms.getscansummary()
    ms_summary = ms.summary()
finally:
    ms.close()
startdate = float(ms_summary["BeginTime"])
sorted_scan_list = sorted([int(scan) for scan in scan_summary])
integration_times = [
        scan_summary[str(ii)]["0"]["IntegrationTime"]
        for ii in sorted_scan_list
]
maximum_integration_time = max(integration_times)
median_integration_time = np.median(integration_times)

if maximum_integration_time != median_integration_time:
    task_logprint("Warning:")
    task_logprint(f"Median integration time = {median_integration_time}")
    task_logprint(f"Maximum integration time = {maximum_integration_time}")

task_logprint(f"Maximum integration time is {maximum_integration_time}s")

# Find scans for quacking
scan_list = [1]
old_scan = scan_summary[str(sorted_scan_list[0])]["0"]
old_field = old_scan["FieldId"]
old_spws = old_scan["SpwIds"]
for ii in range(1, len(sorted_scan_list)):
    new_scan = scan_summary[str(sorted_scan_list[ii])]["0"]
    new_field = new_scan["FieldId"]
    new_spws = new_scan["SpwIds"]
    if (new_field != old_field) or (set(new_spws) != set(old_spws)):
        scan_list.append(sorted_scan_list[ii])
        old_field = new_field
        old_spws = new_spws
quack_scan_string = ",".join(str(ii) for ii in scan_list)

# For 1 GHz wide basebands, figure out which spws are associated
# with the edges of the baseband filters.
sorted_frequencies = sorted(reference_frequencies)
sorted_indices = []
for ii in range(len(sorted_frequencies)):
    for jj in range(len(reference_frequencies)):
        if sorted_frequencies[ii] == reference_frequencies[jj]:
            sorted_indices.append(jj)

spwList = []
BBC_bandwidths = []
ii = 0

while ii < len(sorted_frequencies):
    upper_frequency = sorted_frequencies[ii] + spw_bandwidths[sorted_indices[ii]]
    BBC_bandwidth = spw_bandwidths[sorted_indices[ii]]
    thisSpwList = [sorted_indices[ii]]
    jj = ii + 1
    while jj < len(sorted_frequencies):
        lower_frequency = sorted_frequencies[jj]
        if (abs(lower_frequency - upper_frequency) < 1.0) and (
            originalBBClist[sorted_indices[ii]] == originalBBClist[sorted_indices[jj]]
        ):
            thisSpwList.append(sorted_indices[jj])
            upper_frequency += spw_bandwidths[sorted_indices[jj]]
            BBC_bandwidth += spw_bandwidths[sorted_indices[jj]]
            jj += 1
            ii += 1
        else:
            jj = len(sorted_frequencies)
    spwList.append(thisSpwList)
    BBC_bandwidths.append(BBC_bandwidth)
    ii += 1

# spwList is now a list of lists of contiguous spws, which have
# bandwidths in BBC_bandwidths
low_spws = []
high_spws = []
for ii in range(0, len(BBC_bandwidths)):
    if BBC_bandwidths[ii] > 1.0e9:  # 1 GHz
        low_spws.append(spwList[ii][0])
        high_spws.append(spwList[ii][len(spwList[ii]) - 1])

task_logprint(f"Bottom ends of baseband filters are spws: {low_spws}")
task_logprint(f"Top ends of baseband filters are spws: {high_spws}")

if len(low_spws) != len(high_spws):
    task_logprint("Error! Something is wrong with the spw identification")
    raise RuntimeError("Error! Something is wrong with the spw identification")


# Identify scans and fields associated with different calibrator intents.
# NOTE The scan intent definitions changed in the OPT on Feb 21, 2012 (MJD
# 55978.5) and are not likely to parse correctly. The intents handled from
# before are:
#  - CALIBRATE_BANDPASS
#  - CALIBRATE_DELAY
#  - CALIBRATE_POLARIZATION
#  - CALIBRATE_AMPLI
#  - CALIBRATE_PHASE
#  - CALIBRATE_POINTING
# and appears to be missing "CALIBRATE_FLUX".
bandpass_state_IDs = []
delay_state_IDs = []
flux_state_IDs = []
polarization_state_IDs = []
phase_state_IDs = []
amp_state_IDs = []
calibrator_state_IDs = []
pointing_state_IDs = []
for state_ID in range(len(intents)):
    state_intents = intents[state_ID].rsplit(",")
    for intent in range(len(state_intents)):
        scan_intent = state_intents[intent].rsplit("#")[0]
        subscan_intent = state_intents[intent].rsplit("#")[1]
        if scan_intent == "CALIBRATE_BANDPASS":
            bandpass_state_IDs.append(state_ID)
            calibrator_state_IDs.append(state_ID)
        elif scan_intent == "CALIBRATE_DELAY":
            delay_state_IDs.append(state_ID)
            calibrator_state_IDs.append(state_ID)
        elif scan_intent == "CALIBRATE_FLUX":
            flux_state_IDs.append(state_ID)
            calibrator_state_IDs.append(state_ID)
        elif scan_intent == "CALIBRATE_POLARIZATION":
            polarization_state_IDs.append(state_ID)
            calibrator_state_IDs.append(state_ID)
        elif scan_intent == "CALIBRATE_AMPLI":
            amp_state_IDs.append(state_ID)
            calibrator_state_IDs.append(state_ID)
        elif scan_intent == "CALIBRATE_PHASE":
            phase_state_IDs.append(state_ID)
            calibrator_state_IDs.append(state_ID)
        elif scan_intent == "CALIBRATE_POINTING":
            pointing_state_IDs.append(state_ID)
            calibrator_state_IDs.append(state_ID)

tb.open(msname)

if len(flux_state_IDs) == 0:
    QA2_msinfo = "Fail"
    task_logprint("ERROR: No flux density calibration scans found")
    raise Exception("No flux density calibration scans found")
else:
    flux_state_select_string = "STATE_ID in [%s" % flux_state_IDs[0]
    for state_ID in range(1, len(flux_state_IDs)):
        flux_state_select_string += ",%s" % flux_state_IDs[state_ID]
    flux_state_select_string += "]"
    subtable = tb.query(flux_state_select_string)
    flux_scan_list = list(np.unique(subtable.getcol("SCAN_NUMBER")))
    flux_scan_select_string = ",".join(["%s" % ii for ii in flux_scan_list])
    task_logprint(f"Flux density calibrator(s) scans are {flux_scan_select_string}")
    flux_field_list = list(np.unique(subtable.getcol("FIELD_ID")))
    subtable.close()
    flux_field_select_string = ",".join(str(ii) for ii in flux_field_list)
    task_logprint(f"Flux density calibrator(s) are fields {flux_field_select_string}")

if len(bandpass_state_IDs) == 0:
    task_logprint("No bandpass calibration scans defined, using flux density calibrator")
    bandpass_scan_select_string = flux_scan_select_string
    task_logprint(f"Bandpass calibrator(s) scans are {bandpass_scan_select_string}")
    bandpass_field_select_string = flux_field_select_string
    task_logprint(f"Bandpass calibrator(s) are fields {bandpass_field_select_string}")
else:
    bandpass_state_select_string = "STATE_ID in [%s" % bandpass_state_IDs[0]
    for state_ID in range(1, len(bandpass_state_IDs)):
        bandpass_state_select_string += ",%s" % bandpass_state_IDs[state_ID]
    bandpass_state_select_string += "]"
    subtable = tb.query(bandpass_state_select_string)
    bandpass_scan_list = list(np.unique(subtable.getcol("SCAN_NUMBER")))
    bandpass_scan_select_string = ",".join(str(ii) for ii in bandpass_scan_list)
    task_logprint(f"Bandpass calibrator(s) scans are {bandpass_scan_select_string}")
    bandpass_field_list = list(np.unique(subtable.getcol("FIELD_ID")))
    subtable.close()
    bandpass_field_select_string = ",".join(str(ii) for ii in bandpass_field_list)
    task_logprint(f"Bandpass calibrator(s) are fields {bandpass_field_select_string}")
    if len(bandpass_field_list) > 1:
        task_logprint(
                "WARNING: "
                "More than one field is defined as the bandpass calibrator. "
                "Models are required for all BP calibrators if multiple fields "
                "are to be used, but is not yet implemented; the pipeline will "
                "use only the first field."
        )
        bandpass_field_select_string = str(bandpass_field_list[0])

if len(delay_state_IDs) == 0:
    task_logprint("No delay calibration scans defined, using bandpass calibrator")
    delay_scan_select_string = bandpass_scan_select_string
    task_logprint(f"Delay calibrator(s) scans are {delay_scan_select_string}")
    delay_field_select_string = bandpass_field_select_string
    task_logprint(f"Delay calibrator(s) are fields {delay_field_select_string}")
else:
    delay_state_select_string = "STATE_ID in [%s" % delay_state_IDs[0]
    for state_ID in range(1, len(delay_state_IDs)):
        delay_state_select_string += ",%s" % delay_state_IDs[state_ID]
    delay_state_select_string += "]"
    subtable = tb.query(delay_state_select_string)
    delay_scan_list = list(np.unique(subtable.getcol("SCAN_NUMBER")))
    delay_scan_select_string = ",".join(str(ii) for ii in delay_scan_list)
    task_logprint(f"Delay calibrator(s) scans are {delay_scan_select_string}")
    delay_field_list = list(np.unique(subtable.getcol("FIELD_ID")))
    subtable.close()
    delay_field_select_string = ",".join(str(ii) for ii in delay_field_list)
    task_logprint(f"Delay calibrator(s) are fields {delay_field_select_string}")

if len(polarization_state_IDs) == 0:
    task_logprint("No polarization calibration scans defined, no polarization calibration possible.")
    polarization_scan_select_string = ""
    polarization_field_select_string = ""
else:
    task_logprint("Warning: polarization calibration scans found, but polarization calibration not yet implemented")
    polarization_state_select_string = "STATE_ID in [%s" % polarization_state_IDs[0]
    for state_ID in range(1, len(polarization_state_IDs)):
        polarization_state_select_string += ",%s" % polarization_state_IDs[state_ID]
    polarization_state_select_string += "]"
    subtable = tb.query(polarization_state_select_string)
    polarization_scan_list = list(np.unique(subtable.getcol("SCAN_NUMBER")))
    polarization_scan_select_string = ",".join(str(ii) for ii in polarization_scan_list)
    task_logprint(f"Polarization calibrator(s) scans are {polarization_scan_select_string}")
    polarization_field_list = list(np.unique(subtable.getcol("FIELD_ID")))
    subtable.close()
    polarization_field_select_string = ",".join(str(ii) for ii in polarization_field_list)
    task_logprint(f"Polarization calibrator(s) are fields {polarization_field_select_string}")

if len(phase_state_IDs) == 0:
    QA2_msinfo = "Fail"
    task_logprint("ERROR: No gain calibration scans found")
    raise Exception("No gain calibration scans found")
else:
    phase_state_select_string = "STATE_ID in [%s" % phase_state_IDs[0]
    for state_ID in range(1, len(phase_state_IDs)):
        phase_state_select_string += ",%s" % phase_state_IDs[state_ID]
    phase_state_select_string += "]"
    subtable = tb.query(phase_state_select_string)
    phase_scan_list = list(np.unique(subtable.getcol("SCAN_NUMBER")))
    phase_scan_select_string = ",".join(str(ii) for ii in phase_scan_list)
    task_logprint(f"Phase calibrator(s) scans are {phase_scan_select_string}")
    phase_field_list = list(np.unique(subtable.getcol("FIELD_ID")))
    subtable.close()
    phase_field_select_string = ",".join(str(ii) for ii in phase_field_list)
    task_logprint(f"Phase calibrator(s) are fields {phase_field_select_string}")

if len(amp_state_IDs) == 0:
    task_logprint("No amplitude calibration scans defined, will use phase calibrator")
    amp_scan_select_string = phase_scan_select_string
    task_logprint(f"Amplitude calibrator(s) scans are {amp_scan_select_string}")
    amp_field_select_string = phase_scan_select_string
    task_logprint(f"Amplitude calibrator(s) are fields {amp_field_select_string}")
else:
    amp_state_select_string = "STATE_ID in [%s" % amp_state_IDs[0]
    for state_ID in range(1, len(amp_state_IDs)):
        amp_state_select_string += ",%s" % amp_state_IDs[state_ID]
    amp_state_select_string += "]"
    subtable = tb.query(amp_state_select_string)
    amp_scan_list = list(np.unique(subtable.getcol("SCAN_NUMBER")))
    amp_scan_select_string = ",".join(str(ii) for ii in amp_scan_list)
    task_logprint(f"Amplitude calibrator(s) scans are {amp_scan_select_string}")
    amp_field_list = list(np.unique(subtable.getcol("FIELD_ID")))
    subtable.close()
    amp_field_select_string = ",".join(str(ii) for ii in amp_field_list)
    task_logprint(f"Amplitude calibrator(s) are fields {amp_field_select_string}")

# Find all calibrator scans and fields
calibrator_state_select_string = "STATE_ID in [%s" % calibrator_state_IDs[0]
for state_ID in range(1, len(calibrator_state_IDs)):
    calibrator_state_select_string += ",%s" % calibrator_state_IDs[state_ID]

calibrator_state_select_string += "]"
subtable = tb.query(calibrator_state_select_string)
calibrator_scan_list = list(np.unique(subtable.getcol("SCAN_NUMBER")))
calibrator_scan_select_string = ",".join(str(ii) for ii in calibrator_scan_list)
calibrator_field_list = list(np.unique(subtable.getcol("FIELD_ID")))
subtable.close()
calibrator_field_select_string = ",".join(str(ii) for ii in calibrator_field_list)

tb.close()


if ((startdate >= 55918.80) and (startdate <= 55938.98)) or
    ((startdate >= 56253.6) and (startdate <= 56271.6)):
    task_logprint(
            "Weather station broken during this period, using 100% "
            "seasonal model for calculating the zenith opacity"
    )
    tau = plotweather(vis=msname, seasonal_weight=1.0, doPlot=True)
else:
    tau = plotweather(vis=msname, seasonal_weight=0.5, doPlot=True)

# If there are any pointing state IDs, subtract 2 from the number of
# science spws -- needed for QA scores
if len(pointing_state_IDs) > 0:
    numSpws2 = numSpws - 2
else:
    numSpws2 = numSpws

task_logprint(f"Zenith opacities based on weather data are: {tau}")

# Prep string listing of correlations from dictionary created by method buildscans
# For now, only use the parallel hands.  Cross hands will be implemented later.
scandict = buildscans(msname)
corrstring_list = scandict["DataDescription"][0]["corrdesc"]
removal_list = ["RL", "LR", "XY", "YX"]
corrstring_list = list(set(corrstring_list).difference(set(removal_list)))
corrstring = string.join(corrstring_list, ",")
task_logprint(f"Correlations shown in plotms will be {corrstring}")

try:
    tb.open(f"{msname}/ANTENNA")
    nameAntenna = tb.getcol("NAME")
    numAntenna = len(nameAntenna)
finally:
    tb.close()

minBL_for_cal = max(3, int(numAntenna / 2.0))

# Determine if 3C84 was used as a bandpass or delay calibrator
positions = []
for ii in range(0, len(field_positions[0][0])):
    positions.append([field_positions[0][0][ii], field_positions[1][0][ii]])

fields_3C84 = find_3C84(positions)
cal3C84_d = False
cal3C84_bp = False
# uvrange3C84 = '0~1800klambda'
uvrange3C84 = ""
if fields_3C84:
    for field_int in fields_3C84:
        if str(field_int) in delay_field_select_string:
            cal3C84_d = True
            task_logprint("WARNING: 3C84 was observed as a delay calibrator, uvrange limits may be used")
        if str(field_int) in bandpass_field_select_string:
            cal3C84_bp = True
            task_logprint("WARNING: 3C84 was observed as a BP calibrator, uvrange limits may be used")

# Identify bands/basebands/spws
try:
    tb.open(msname + "/SPECTRAL_WINDOW")
    spw_names = tb.getcol("NAME")
finally:
    tb.close()

# If the dataset is too old to have the bandname in it, assume that
# either there are 8 spws per baseband (and allow for one or two for
# pointing), or that this is a dataset with one spw per baseband
if len(spw_names) >= 8:
    critfrac = 0.9 / int(len(spw_names) / 8.0)
else:
    critfrac = 0.9 / float(len(spw_names))

if "#" in spw_names[0]:
    # I assume that if any of the spw_names have '#', they all do...
    bands_basebands_subbands = []
    for spw_name in spw_names:
        receiver_name, baseband, subband = spw_name.split("#")
        receiver_band = (receiver_name.split("_"))[1]
        bands_basebands_subbands.append([receiver_band, baseband, int(subband)])
    spws_info = [
        [bands_basebands_subbands[0][0], bands_basebands_subbands[0][1], [], []]
    ]
    bands = [bands_basebands_subbands[0][0]]
    for ii in range(len(bands_basebands_subbands)):
        band, baseband, subband = bands_basebands_subbands[ii]
        found = -1
        for jj in range(len(spws_info)):
            oband, obaseband, osubband, ospw_list = spws_info[jj]
            if band == oband and baseband == obaseband:
                osubband.append(subband)
                ospw_list.append(ii)
                found = jj
                break
        if found >= 0:
            spws_info[found] = [oband, obaseband, osubband, ospw_list]
        else:
            spws_info.append([band, baseband, [subband], [ii]])
            bands.append(band)
    task_logprint("Bands/basebands/spws are:")
    for spw_info in spws_info:
        spw_info_string = (
            spw_info[0]
            + "   "
            + spw_info[1]
            + "   ["
            + ",".join(["%d" % ii for ii in spw_info[2]])
            + "]   ["
            + ",".join(["%d" % ii for ii in spw_info[3]])
            + "]"
        )
        task_logprint(spw_info_string)
    # Critical fraction of flagged solutions in delay cal to avoid an
    # entire baseband being flagged on all antennas
    critfrac = 0.9 / float(len(spws_info))
elif ":" in spw_names[0]:
    task_logprint("old spw names with ':'")
else:
    task_logprint("unknown spw names")


# Check for missing scans
missingScans = 0
missingScanStr = ""
for i in range(max(scanNums)):
    if scanNums.count(i + 1) == 1:
        pass
    else:
        task_logprint(f"WARNING: Scan {i+1} is not present")
        missingScans += 1
        missingScanStr += f"{i+1}, "

if missingScans > 0:
    task_logprint(f"WARNING: There were {missingScans} missing scans in this MS")
else:
    task_logprint("No missing scans found.")


# Plot raw data
# FIXME Needs to be done; Miriam has something in her script for this.


# Plot online flags
task_logprint("Plotting online flags")
os.system("rm -rf onlineFlags.png")
flagcmd(
        vis=msname,
        inpmode="list",
        inpfile="onlineFlags.txt",
        action="plot",
        plotfile="onlineFlags.png",
        savepars=False,
)
task_logprint("Online flags plot onlineFlags.png")


# Plot antenna locations
task_logprint("Plotting antenna positions (linear)")
os.system("rm -rf plotants.png")
plotants(
        vis=msname,
        logpos=False,
        figfile="plotants.png",
)
task_logprint("Antenna positions plot (linear) plotants.png")

task_logprint("Plotting antenna positions (logarithmic)")
os.system("rm -rf plotantslog.png")
default("plotants")
plotants(
        vis=msname,
        logpos=True,
        figfile="plotantslog.png",
)
task_logprint("Antenna positions plot (logarithmic) plotantslog.png")


# Make elevation vs. time plot
# FIXME This channel selection may fail for Hanning or data that has
# had WIDAR channel averaging applied.
task_logprint("Plotting elevation vs. time for all fields")
os.system("rm -rf el_vs_time.png")
plotms(
        vis=msname,
        xaxis="time",
        yaxis="elevation",
        selectdata=True,
        spw="*:31",
        antenna="0&1;2&3;4&5;6&7",
        correlation=corrstring,
        averagedata=False,
        transform=False,
        extendflag=False,
        iteraxis="",
        customsymbol=False,
        coloraxis="field",
        customflaggedsymbol=False,
        plotrange=[],
        title="Elevation vs. time",
        xlabel="",
        ylabel="",
        showmajorgrid=False,
        showminorgrid=False,
        plotfile="el_vs_time.png",
        highres=True,
        overwrite=True,
        showgui=False,
)
task_logprint("Elevation vs. time plot el_vs_time.png")


task_logprint("Finished EVLA_pipe_msinfo.py")
task_logprint(f"QA2 score: {QA2_msinfo}")
time_list = runtiming("msinfo", "end")

pipeline_save()

