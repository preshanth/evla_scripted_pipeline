"""
Write the weblog HTML files.
"""

import os
import glob
import shutil

from . import __version_str__, casa_version, pipeline_save
from .utils import MAINLOG, logprint


logprint("Writing web logs", logfileout="logs/weblog.log")

# First, trap for any unknown QA2 scores and some other information:
try:
    QA2_import
except:
    QA2_import = "Unknown"

try:
    QA2_hanning
except:
    QA2_hanning = "Unknown"

try:
    QA2_msinfo
except:
    QA2_msinfo = "Unknown"

try:
    QA2_flagall
except:
    QA2_flagall = "Unknown"

try:
    QA2_calprep
except:
    QA2_calprep = "Unknown"

try:
    QA2_priorcals
except:
    QA2_priorcals = "Unknown"

try:
    QA2_testBPdcals
except:
    QA2_testBPdcals = "Unknown"

try:
    QA2_flag_baddeformatters
except:
    QA2_flag_baddeformatters = "Unknown"

try:
    QA2_flag_baddeformattersphase
except:
    QA2_flag_baddeformattersphase = "Unknown"

try:
    QA2_checkflag
except:
    QA2_checkflag = "Unknown"

try:
    QA2_semiFinalBPdcals1
except:
    QA2_semiFinalBPdcals1 = "Unknown"

try:
    QA2_checkflag_semiFinal
except:
    QA2_checkflag_semiFinal = "Unknown"

try:
    QA2_solint
except:
    QA2_solint = "Unknown"

try:
    QA2_testgains
except:
    QA2_testgains = "Unknown"

try:
    QA2_fluxgains
except:
    QA2_fluxgains = "Unknown"

try:
    QA2_fluxboot
except:
    QA2_fluxboot = "Unknown"

try:
    QA2_finalcals
except:
    QA2_finalcals = "Unknown"

try:
    QA2_applycals
except:
    QA2_applycals = "Unknown"

try:
    QA2_targetflag
except:
    QA2_targetflag = "Unknown"

try:
    QA2_statwt
except:
    QA2_statwt = "Unknown"

try:
    QA2_plotsummary
except:
    QA2_plotsummary = "Unknown"

# Calculate overall QA2 score:

all_QA2 = [
    QA2_import,
    QA2_hanning,
    QA2_msinfo,
    QA2_flagall,
    QA2_calprep,
    QA2_priorcals,
    QA2_testBPdcals,
    QA2_flag_baddeformatters,
    QA2_flag_baddeformattersphase,
    QA2_checkflag,
    QA2_semiFinalBPdcals1,
    QA2_checkflag_semiFinal,
    QA2_solint,
    QA2_testgains,
    QA2_fluxgains,
    QA2_fluxboot,
    QA2_finalcals,
    QA2_applycals,
    QA2_targetflag,
    QA2_statwt,
    QA2_plotsummary,
]
if "Fail" in all_QA2:
    QA2_pipeline = "Fail"
elif "Partial" in all_QA2:
    QA2_pipeline = "Partial"
else:
    QA2_pipeline = "Pass"

# Write all QA2 scores to file
with open("QA2_scores.txt", "w") as qalog:
    qalog.write("QA2_import=" + QA2_import + "\n")
    qalog.write("QA2_hanning=" + QA2_hanning + "\n")
    qalog.write("QA2_msinfo=" + QA2_msinfo + "\n")
    qalog.write("QA2_flagall=" + QA2_flagall + "\n")
    qalog.write("QA2_calprep=" + QA2_calprep + "\n")
    qalog.write("QA2_priorcals=" + QA2_priorcals + "\n")
    qalog.write("QA2_testBPdcals=" + QA2_testBPdcals + "\n")
    qalog.write("QA2_flag_baddeformatters=" + QA2_flag_baddeformatters + "\n")
    qalog.write("QA2_flag_baddeformattersphase=" + QA2_flag_baddeformattersphase + "\n")
    qalog.write("QA2_checkflag=" + QA2_checkflag + "\n")
    qalog.write("QA2_semiFinalBPdcals1=" + QA2_semiFinalBPdcals1 + "\n")
    qalog.write("QA2_checkflag_semiFinal=" + QA2_checkflag_semiFinal + "\n")
    qalog.write("QA2_solint=" + QA2_solint + "\n")
    qalog.write("QA2_testgains=" + QA2_testgains + "\n")
    qalog.write("QA2_fluxgains=" + QA2_fluxgains + "\n")
    qalog.write("QA2_fluxboot=" + QA2_fluxboot + "\n")
    qalog.write("QA2_finalcals=" + QA2_finalcals + "\n")
    qalog.write("QA2_applycals=" + QA2_applycals + "\n")
    qalog.write("QA2_targetflag=" + QA2_targetflag + "\n")
    qalog.write("QA2_statwt=" + QA2_statwt + "\n")
    qalog.write("QA2_plotsummary=" + QA2_plotsummary + "\n")
    qalog.write("QA2_pipeline=" + QA2_pipeline + "\n")


with open("comments.txt", "w") as commentlog:
    commentlog.write(
        "QA feedback from NRAO staff:\n\n\n"
        "One of your Scheduling Blocks, , has been processed through the VLA\n"
        "CASA Calibration Pipeline, which is designed to handle Stokes I\n"
        "continuum data, and has received a QA2 score of "
        ". NRAO staff have\n"
        "checked the calibrated data and no major issues have been identified.\n"
        "Some data may need further flagging before imaging as described below:\n\n\n\n"
        "- If your science involves spectral lines, you should be aware of the following:\n\n"
        "1) The pipeline applies Hanning-smoothing by default, which may make the\n"
        "   calibrated data set not optimal for certain spectral-line science.\n\n"
        "2) During the calibration process, several edge channels in each sub\n"
        "   band get flagged by default because they are noisier. Therefore,\n"
        "   breaks in the frequency span get introduced in the pipeline\n"
        "   calibrated data, which in turn may make the output not suitable\n"
        "   for certain spectral-line science.\n\n"
        "3) The pipeline runs an RFI flagging algorithm which should flag strong\n"
        "   lines and may remove spectral lines of interest to your science.\n\n\n"
        "- If your observations used a resolved calibrator source (i.e., has UV\n"
        "  limits) but does not have standard model images in CASA, the calibrated\n"
        "  data through the pipeline would not be accurate. In such instances,\n"
        "  re-calibration using UV limits, or imaging the calibrator first and\n"
        "  using the resulting image model, will be needed.\n\n"
    )

os.system("rm -rf *.html")

with open("index.html", "w") as wlog:
    wlog.write(
        "<html>\n"
        "<head>\n"
        "<title>VLA Pipeline Web Log</title>\n"
        "</head>\n"
        "<body>\n"
        "<br>\n"
        "<hr>\n"
        '<table border="1" width="100%">\n'
        "<tr>\n"
        '<th><a href="./splash.html">Splash Page</a></th>\n'
        '<th><a href="./obssum.html">Observation Summary</a></th>\n'
        '<th><a href="./qa2.html">QA2</a></th>\n'
        '<th><a href="./tasksum.html">Task Summary</a></th>\n'
        "</tr>\n"
        "</table>\n"
        "<br>\n"
        "<hr>\n"
        "</body>\n"
        "</html>\n"
    )

wlog = open("splash.html", "w")
wlog.write("<html>\n")
wlog.write("<head>\n")
wlog.write("<title>VLA Pipeline Splash Page</title>\n")
wlog.write("</head>\n")
wlog.write("<body>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write('<table border="1" width="100%">\n')
wlog.write("<tr>\n")
wlog.write('<th><a href="./splash.html">Splash Page</a></th>\n')
wlog.write('<th><a href="./obssum.html">Observation Summary</a></th>\n')
wlog.write('<th><a href="./qa2.html">QA2</a></th>\n')
wlog.write('<th><a href="./tasksum.html">Task Summary</a></th>\n')
wlog.write("</tr>\n")
wlog.write("</table>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Project code: " + projectCode + " \n")
wlog.write("<br>PI name: " + piName + " \n")
wlog.write("<br>PI global ID: " + piGlobalId + " \n")
filename = SDM_name[right_index + 1 :]
wlog.write("<br>Full SB ID: " + filename + "\n")
wlog.write("<br>Date of observation: " + observeDateString + " \n")
wlog.write("<br>QA2 score: " + QA2_pipeline + " \n")
wlog.write("<br>Date of pipeline execution: " + pipelineDateString + " \n")
wlog.write("<br>Pipeline version: " + __version_str__ + " \n")
wlog.write("<br>CASA version: " + str(casa_version))
wlog.write(
    '<br>Notes to PI from QA2 evaluation: <a href="./comments.txt" type="text/plain" target="_blank">link</a>\n'
)
wlog.write("<br>Observing log: \n")
wlog.write(
    "<br>Calibrated data (available for 15 days following processing): submit helpdesk request specifying SB ID indicated above\n"
)
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write(
    '<br><a href="https://science.nrao.edu/observing/helpdesk">NRAO Helpdesk</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/data-archive/evla/index">VLA Data Archive</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/observing/opt">VLA Observation Preparation Tool</a>\n'
)
wlog.write("</body>\n")
wlog.write("</html>\n")
wlog.close()

wlog = open("obssum.html", "w")
wlog.write("<html>\n")
wlog.write("<head>\n")
wlog.write("<title>VLA Pipeline Observation Summary</title>\n")
wlog.write("</head>\n")
wlog.write("<body>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write('<table border="1" width="100%">\n')
wlog.write("<tr>\n")
wlog.write('<th><a href="./splash.html">Splash Page</a></th>\n')
wlog.write('<th><a href="./obssum.html">Observation Summary</a></th>\n')
wlog.write('<th><a href="./qa2.html">QA2</a></th>\n')
wlog.write('<th><a href="./tasksum.html">Task Summary</a></th>\n')
wlog.write("</tr>\n")
wlog.write("</table>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
filename = SDM_name[right_index + 1 :]
wlog.write("<br>Full SB ID: " + filename + "\n")
wlog.write("<br>Date of observation: " + observeDateString + " \n")
listobs_right_index = listname.rfind("/")
filename = listname[listobs_right_index + 1 :]
wlog.write(
    '<br>Listobs output: <a href="./'
    + filename
    + '" type="text/plain" target="_blank">link</a>\n'
)
wlog.write("<br>Observing bands: " + unique_bands_string + " \n")
wlog.write("<br>Antenna positions: \n")
wlog.write('<br><img src="./plotants.png">\n')
wlog.write('<br><img src="./plotantslog.png">\n')
if os.path.exists("final_caltables/antposcal.p"):
    wlog.write(
        "<br>Antenna position corrections applied: " + str(antenna_offsets) + "\n"
    )
else:
    wlog.write("<br>No antenna position corrections applied\n")
if os.path.exists("weblog/onlineFlags.png"):
    wlog.write("<br>Online flags: \n")
    wlog.write('<br><img src="./onlineFlags.png">\n')
else:
    wlog.write("<br>No online flags applied\n")
wlog.write("<br>Weather plot: \n")
filename = SDM_name[right_index + 1 :] + ".ms.plotweather.png"
wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Elevation vs. time: \n")
wlog.write('<br><img src="./el_vs_time.png">\n')
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write('<table border="1" width="100%">\n')
wlog.write("<tr>\n")
wlog.write('<th><a href="./splash.html">Splash Page</a></th>\n')
wlog.write('<th><a href="./obssum.html">Observation Summary</a></th>\n')
wlog.write('<th><a href="./qa2.html">QA2</a></th>\n')
wlog.write('<th><a href="./tasksum.html">Task Summary</a></th>\n')
wlog.write("</tr>\n")
wlog.write("</table>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write(
    '<br><a href="https://science.nrao.edu/observing/helpdesk">NRAO Helpdesk</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/data-archive/evla/index">VLA Data Archive</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/observing/opt">VLA Observation Preparation Tool</a>\n'
)
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("</body>\n")
wlog.write("</html>\n")
wlog.close()

wlog = open("qa2.html", "w")
wlog.write("<html>\n")
wlog.write("<head>\n")
wlog.write("<title>VLA Pipeline QA2</title>\n")
wlog.write("</head>\n")
wlog.write("<body>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write('<table border="1" width="100%">\n')
wlog.write("<tr>\n")
wlog.write('<th><a href="./splash.html">Splash Page</a></th>\n')
wlog.write('<th><a href="./obssum.html">Observation Summary</a></th>\n')
wlog.write('<th><a href="./qa2.html">QA2</a></th>\n')
wlog.write('<th><a href="./tasksum.html">Task Summary</a></th>\n')
wlog.write("</tr>\n")
wlog.write("</table>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Fraction of zeroes: " + str(zero_flagged / afterzero_total) + " \n")
wlog.write(
    "<br>Total fraction of on-source data flagged before calibration (NB: expect approx. 0.1 from flagging of end channels): "
    + str(frac_flagged_on_source1)
    + " \n"
)
try:
    wlog.write(
        "<br>Final fraction of on-source data flagged: "
        + str(frac_flagged_on_source2)
        + " \n"
    )
except:
    wlog.write("<br>Final fraction of on-source data flagged not available\n")
wlog.write(
    '<br>QA2 scores for each step of pipeline: <a href="./QA2_scores.txt" type="text/plain" target="_blank">link</a>\n'
)
wlog.write("<br>Overall QA2 score: " + QA2_pipeline + " \n")
if missingScans > 0:
    wlog.write("<br>The following scans are missing: " + missingScanStr + " \n")
else:
    wlog.write("<br>There are no missing scans \n")
wlog.write("<br>Gain solution interval used for initial delay calibration: int \n")
wlog.write("<br>Gain solution interval used for BP calibrator: " + gain_solint1 + " \n")
wlog.write(
    "<br>Short/long gain solution interval used for gain calibrator: "
    + new_gain_solint1
    + "/"
    + gain_solint2
    + " \n"
)
if standard_source_found == False:
    wlog.write(
        "<br>ERROR: No standard flux density calibrator observed, flux density scale will be arbitrary"
    )
wlog.write(
    '<br>Fitted flux densities: <a href="./logs/fluxboot.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write(f"<br>Final delays [abs(max.delay) = {maxdelay} ns]: \n")
for filen in glob.glob("./weblog/finaldelay*.png"):
    wlog.write(f'<br><img src="./{os.path.basename(filen)}">\n')
wlog.write("<br>Final bandpass solutions: \n")
for filen in glob.glob("./weblog/finalBPcal_amp*.png"):
    wlog.write(f'<br><img src="./{os.path.basename(filen)}">\n')
for filen in glob.glob("./weblog/finalBPcal_phase*.png"):
    wlog.write(f'<br><img src="./{os.path.basename(filen)}">\n')
wlog.write("<br>Final amplitude gain solutions: \n")
for filen in glob.glob("./weblog/finalamptimecal*.png"):
    wlog.write(f'<br><img src="./{os.path.basename(filen)}">\n')
for filen in glob.glob("./weblog/finalampfreqcal*.png"):
    wlog.write(f'<br><img src="./{os.path.basename(filen)}">\n')
wlog.write("<br>Final phase gain solutions: \n")
for filen in glob.glob("./weblog/finalphasegaincal*.png"):
    wlog.write(f'<br><img src="./{os.path.basename(filen)}">\n')
wlog.write("<br>Phase vs. time for calibrated calibrators: \n")
wlog.write('<br><img src="./all_calibrators_phase_time.png">\n')
wlog.write("<br>Amplitude vs. uv-distance for all fields: \n")
for filen in glob.glob("./weblog/field*_amp_uvdist.png"):
    wlog.write(f'<br><img src="./{os.path.basename(filen)}">\n')
wlog.write("<br>\n")
wlog.write("<br>Amplitude and Phase vs. Frequency for all fields: \n")
ampli_files = sorted(glob.glob("./weblog/field*_amp_freq.png"))
phase_files = sorted(glob.glob("./weblog/field*_phase_freq.png"))
for filen_a, filen_p in zip(ampli_files, phase_files):
    wlog.write(
            f'<br><img src="./{os.path.basename(filen_a)}" height="50%">'
            f'<img src="./{os.path.basename(filen_p)}" height="50%">\n'
    )
wlog.write("<br>\n")
wlog.write(
    '<br>Notes to PI from QA2 evaluation: <a href="./comments.txt" type="text/plain" target="_blank">link</a>\n'
)
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write('<table border="1" width="100%">\n')
wlog.write("<tr>\n")
wlog.write('<th><a href="./splash.html">Splash Page</a></th>\n')
wlog.write('<th><a href="./obssum.html">Observation Summary</a></th>\n')
wlog.write('<th><a href="./qa2.html">QA2</a></th>\n')
wlog.write('<th><a href="./tasksum.html">Task Summary</a></th>\n')
wlog.write("</tr>\n")
wlog.write("</table>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write(
    '<br><a href="https://science.nrao.edu/observing/helpdesk">NRAO Helpdesk</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/data-archive/evla/index">VLA Data Archive</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/observing/opt">VLA Observation Preparation Tool</a>\n'
)
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("</body>\n")
wlog.write("</html>\n")
wlog.close()

wlog = open("tasksum.html", "w")
wlog.write("<html>\n")
wlog.write("<head>\n")
wlog.write("<title>VLA Pipeline Task Summary</title>\n")
wlog.write("</head>\n")
wlog.write("<body>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write('<table border="1" width="100%">\n')
wlog.write("<tr>\n")
wlog.write('<th><a href="./splash.html">Splash Page</a></th>\n')
wlog.write('<th><a href="./obssum.html">Observation Summary</a></th>\n')
wlog.write('<th><a href="./qa2.html">QA2</a></th>\n')
wlog.write('<th><a href="./tasksum.html">Task Summary</a></th>\n')
wlog.write("</tr>\n")
wlog.write("</table>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
casa_right_index = MAINLOG.rfind("/")
filename = MAINLOG[casa_right_index + 1 :]
wlog.write(
    '<br>Main CASA log file: <a href="./'
    + filename
    + '" type="text/plain" target="_blank">link</a> \n'
)
if os.path.exists("stderr.casa"):
    wlog.write(
        '<br>CASA stderr output: <a href="./stderr.casa" type="text/plain" target="_blank">link</a>\n'
    )
if os.path.exists("stdout.casa"):
    wlog.write(
        '<br>CASA stdout output: <a href="./stdout.casa" type="text/plain" target="_blank">link</a>\n'
    )
# wlog.write('<br>PPR document: \n')
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write(
    "<br><h3>Script, log file, QA score, and other outputs for each step of pipeline:</h3>\n"
)
wlog.write("<br>Import raw data to MS: \n")
wlog.write("<br>\n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_import.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/import.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_import + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<hr>\n")
wlog.write("<br>Hanning smooth data: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_hanning.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/hanning.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_hanning + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<hr>\n")
wlog.write("<br>Information from the MS: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_msinfo.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/msinfo.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_msinfo + " </li>\n")
wlog.write("<li>Fields/scans used for calibration: \n")
wlog.write("<li>Flux density field(s): " + flux_field_select_string + " </li>\n")
wlog.write("<li>Flux density scans(s): " + flux_scan_select_string + " </li>\n")
wlog.write("<li>Bandpass field: " + bandpass_field_select_string + " </li>\n")
wlog.write("<li>Bandpass scan(s): " + bandpass_scan_select_string + " </li>\n")
wlog.write("<li>Delay field: " + delay_field_select_string + " </li>\n")
wlog.write("<li>Delay scan(s): " + delay_scan_select_string + " </li>\n")
wlog.write("<li>Gain calibrator field(s): " + phase_field_select_string + " </li>\n")
wlog.write("<li>Gain calibrator scans(s): " + phase_scan_select_string + " </li>\n")
wlog.write(
    "<li>All calibrator field(s): " + calibrator_field_select_string + " </li>\n"
)
wlog.write("<li>All calibrator scans(s): " + calibrator_scan_select_string + " </li>\n")
wlog.write("<li>Plots: \n")
wlog.write("<br>Antenna positions: \n")
wlog.write('<br><img src="./plotants.png">\n')
wlog.write('<br><img src="./plotantslog.png">\n')
if os.path.exists("weblog/onlineFlags.png"):
    wlog.write("<br>Online flags: \n")
    wlog.write('<br><img src="./onlineFlags.png">\n')
else:
    wlog.write("<br>No online flags applied\n")
wlog.write("<br>Elevation vs. time: \n")
wlog.write('<br><img src="./el_vs_time.png">\n')
wlog.write("<br>Weather plot: \n")
filename = SDM_name[right_index + 1 :] + ".ms.plotweather.png"
wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("</li>\n")
filename = listname[listobs_right_index + 1 :]
wlog.write(
    '<br>Listobs output: <a href="./'
    + filename
    + '" type="text/plain" target="_blank">link</a>\n'
)
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Deterministic flagging: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_flagall.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/flagall.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_flagall + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Calibration preparation: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_calprep.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/calprep.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_calprep + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Prior calibrations: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_priorcals.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/priorcals.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_priorcals + " </li>\n")
if os.path.exists("final_caltables/switched_power.g"):
    wlog.write("<li>Plots: \n")
    wlog.write("<br>Switched power: \n")
    nplots = int(numAntenna / 3)
    if (numAntenna % 3) > 0:
        nplots = nplots + 1
    for ii in range(nplots):
        filename = "switched_power" + str(ii) + ".png"
        wlog.write('<br><img src="./' + filename + '">\n')
    wlog.write("<br>System temperature: \n")
    for ii in range(nplots):
        filename = "Tsys" + str(ii) + ".png"
        wlog.write('<br><img src="./' + filename + '">\n')
if os.path.exists("final_caltables/antposcal.p"):
    wlog.write(
        "<li>Antenna position corrections applied: " + str(antenna_offsets) + "</li>\n"
    )
else:
    wlog.write("<li>No antenna position corrections applied</li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Test BP/delay calibrations: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_testBPdcals.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/testBPdcals.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_testBPdcals + " </li>\n")
wlog.write("<li>Plots: \n")
wlog.write("<br>Delays: \n")
nplots = int(numAntenna / 3)
if (numAntenna % 3) > 0:
    nplots = nplots + 1
for ii in range(nplots):
    filename = "testdelay" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Initial gain amplitudes: \n")
for ii in range(nplots):
    filename = "testBPdinitialgainamp" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Initial gain phases: \n")
for ii in range(nplots):
    filename = "testBPdinitialgainphase" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Test bandpass calibration amplitudes: \n")
for ii in range(nplots):
    filename = "testBPcal_amp" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Test bandpass calibration phases: \n")
for ii in range(nplots):
    filename = "testBPcal_phase" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Calibrated bandpass calibrator: \n")
wlog.write('<br><img src="./testcalibratedBPcal.png">\n')
if os.path.exists("weblog/testcalibrated_delaycal.png"):
    wlog.write("<br>Calibrated delay calibrator: \n")
    wlog.write('<br><img src="./testcalibrated_delaycal.png">\n')
wlog.write("</li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write(
    "<br>Identify basebands/spws with bad deformatters/RFI based on BP table amplitudes: \n"
)
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_flag_baddeformatters.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/flag_baddeformatters.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_flag_baddeformatters + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write(
    "<br>Identify basebands/spws with bad deformatters/RFI based on BP table phases: \n"
)
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_flag_baddeformattersphase.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/flag_baddeformattersphase.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_flag_baddeformattersphase + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>RFLAG on calibrated BP/delay calibrators: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_checkflag.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/checkflag.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_checkflag + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Semi-final BP/delay calibrations (first run): \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_semiFinalBPdcals1.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/semiFinalBPdcals1.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_semiFinalBPdcals1 + " </li>\n")
wlog.write("<li>Plots: \n")
wlog.write("<br>Bandpass-calibrated calibrators: \n")
wlog.write('<br><img src="./semifinalcalibratedcals1.png">\n')
wlog.write("</li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>RFLAG on calibrated calibrators: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_checkflag_semiFinal.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/checkflag_semiFinal.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_checkflag_semiFinal + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Determine long solint for gain calibrations: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_solint.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/solint.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_solint + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Determine short solint for gain calibrations: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_testgains.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/testgains.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_testgains + " </li>\n")
wlog.write("<li>Plots: \n")
wlog.write("<br>Test gain calibration amplitudes: \n")
for ii in range(nplots):
    filename = "testgaincal_amp" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Test gain calibration phases: \n")
for ii in range(nplots):
    filename = "testgaincal_phase" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("</li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Make gain table for flux density bootstrapping: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_fluxgains.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/fluxgains.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_fluxgains + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Bootstrap flux densities: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_fluxboot.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/fluxboot.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_fluxboot + " </li>\n")
wlog.write("<li>Plots: \n")
wlog.write("<br>Bootstrapped flux densities: \n")
wlog.write('<br><img src="./bootstrappedFluxDensities.png">\n')
wlog.write("</li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Make final calibration tables: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_finalcals.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/finalcals.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_finalcals + " </li>\n")
wlog.write("<li>Plots: \n")
wlog.write("<br>Final delays: \n")
for ii in range(nplots):
    filename = "finaldelay" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Final version of initial gain phases on BP calibrator: \n")
for ii in range(nplots):
    filename = "finalBPinitialgainphase" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Final bandpass calibration amplitudes: \n")
for ii in range(nplots):
    filename = "finalBPcal_amp" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Final bandpass calibration phases: \n")
for ii in range(nplots):
    filename = "finalBPcal_phase" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Short solint phase solutions: \n")
for ii in range(nplots):
    filename = "phaseshortgaincal" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Final amplitude gain solutions, amp vs. time: \n")
for ii in range(nplots):
    filename = "finalamptimecal" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Final amplitude gain solutions, amp vs. frequency: \n")
for ii in range(nplots):
    filename = "finalampfreqcal" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Final phase gain solutions: \n")
for ii in range(nplots):
    filename = "finalphasegaincal" + str(ii) + ".png"
    wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("</li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Apply final calibrations: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_applycals.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/applycals.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_applycals + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>RFLAG on all calibrated data: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_targetflag.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/targetflag.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_targetflag + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Calculate weights per spectral window for all fields: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_statwt.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/statwt.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_statwt + " </li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<br>Final UV plots: \n")
wlog.write("<ul>\n")
wlog.write("<li>Script: EVLA_pipe_plotsummary.py</li>\n")
wlog.write(
    '<li>Log: <a href="./logs/plotsummary.log" type="text/plain" target="_blank">link</a></li>\n'
)
wlog.write("<li>QA2 score: " + QA2_plotsummary + " </li>\n")
wlog.write("<li>Plots: \n")
wlog.write("<br>Phase vs. time for calibrated calibrators: \n")
filename = "all_calibrators_phase_time.png"
wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>Amplitude vs. uv-distance for all fields: \n")
for ii in field_ids:
    filename = "field" + str(field_ids[ii]) + "_amp_uvdist.png"
    if os.path.exists("weblog/" + filename):
        wlog.write('<br><img src="./' + filename + '">\n')
wlog.write("<br>\n")
wlog.write("<br>Amplitude and Phase vs. Frequency for all fields: \n")
for ii in field_ids:
    if "#" in spw_names[0]:
        for iii in range(0, len(spws_info)):
            BB = spws_info[iii]
            band = BB[0]
            bband = BB[1]
            filename_a = (
                "field"
                + str(field_ids[ii])
                + "_"
                + band
                + "-Band_"
                + bband
                + "_amp_freq.png"
            )
            filename_p = (
                "field"
                + str(field_ids[ii])
                + "_"
                + band
                + "-Band_"
                + bband
                + "_phase_freq.png"
            )
            if (os.path.exists("weblog/" + filename_a)) or (
                os.path.exists("weblog/" + filename_p)
            ):
                wlog.write(
                    '<br><img src="./'
                    + filename_a
                    + '" height="50%"><img src="./'
                    + filename_p
                    + '" height="50%">\n'
                )
    else:
        filename_a = "field" + str(field_ids[ii]) + "_amp_freq.png"
        filename_p = "field" + str(field_ids[ii]) + "_phase_freq.png"
        if (os.path.exists("weblog/" + filename_a)) or (
            os.path.exists("weblog/" + filename_p)
        ):
            wlog.write(
                '<br><img src="./'
                + filename_a
                + '" height="50%"><img src="./'
                + filename_p
                + '" height="50%">\n'
            )
wlog.write("<br>\n")

wlog.write("</li>\n")
wlog.write("</ul>\n")
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("<hr>\n")
wlog.write('<table border="1" width="100%">\n')
wlog.write("<tr>\n")
wlog.write('<th><a href="./splash.html">Splash Page</a></th>\n')
wlog.write('<th><a href="./obssum.html">Observation Summary</a></th>\n')
wlog.write('<th><a href="./qa2.html">QA2</a></th>\n')
wlog.write('<th><a href="./tasksum.html">Task Summary</a></th>\n')
wlog.write("</tr>\n")
wlog.write("</table>\n")
wlog.write("<br>\n")
#
wlog.write("<hr>\n")
wlog.write(
    '<br><a href="https://science.nrao.edu/observing/helpdesk">NRAO Helpdesk</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/data-archive/evla/index">VLA Data Archive</a>\n'
)
wlog.write(
    '<br><a href="https://science.nrao.edu/facilities/vla/observing/opt">VLA Observation Preparation Tool</a>\n'
)
wlog.write("<br>\n")
wlog.write("<hr>\n")
wlog.write("</body>\n")
wlog.write("</html>\n")
wlog.close()

# Finish up by moving logs and html output to weblog subdirectory
all_logs = glob.glob("./logs")
for filen in all_logs:
    try:
        shutil.move(filen, weblog_dir + "/.")
    except:
        logprint("Unable to move " + filen, logfileout="logs/filecollect.log")

for filen in glob.glob("./*.html"):
    dest = os.path.join(weblog_dir, filen)
    try:
        if os.path.exists(dest):
            os.remove(dest)
        shutil.move(filen, dest)
    except:
        logprint(f"Unable to move {filen}", logfileout="logs/filecollect.log")

if os.path.exists("stderr.casa"):
    std_casa = glob.glob("./stderr.casa")
    for filen in std_casa:
        try:
            shutil.copy(filen, weblog_dir + "/.")
        except:
            logprint("Unable to move " + filen, logfileout="logs/filecollect.log")

if os.path.exists("stdout.casa"):
    std_casa = glob.glob("./stdout.casa")
    for filen in std_casa:
        try:
            shutil.copy(filen, weblog_dir + "/.")
        except:
            logprint("Unable to move " + filen, logfileout="logs/filecollect.log")

casa_logs = glob.glob("./casa*.log")
for filen in casa_logs:
    try:
        shutil.copy(filen, weblog_dir + "/.")
    except:
        logprint("Unable to copy " + filen, logfileout="logs/filecollect.log")

comments = glob.glob("./comments.txt")
for filen in comments:
    try:
        shutil.move(filen, weblog_dir + "/.")
    except:
        logprint("Unable to move " + filen, logfileout="logs/filecollect.log")

comments = glob.glob("./QA2_scores.txt")
for filen in comments:
    try:
        shutil.move(filen, weblog_dir + "/.")
    except:
        logprint("Unable to move " + filen, logfileout="logs/filecollect.log")

pipeline_save()
