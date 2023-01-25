"""
Make final gain calibration tables.
"""

import copy

import numpy as np
import scipy as sp

from casatasks import rmtables, gaincal, bandpass, flagdata, applycal, split, setjy
from casatools import table
from casaplotms import plotms

from .utils import logprint, runtiming, RefAntHeuristics

tb = table()


def task_logprint(msg):
    logprint(msg, logfileout="logs/finalcals.log")


def fitfunc(p, x):
    return p[0] + p[1] * x


def errfunc(p, x, y, err):
    return (y - fitfunc(p, x)) / err


task_logprint("Starting EVLA_pipe_finalcals.py")
time_list = runtiming("finalcals", "start")
QA2_finalcals = "Pass"

# Find reference antenna again in case there has been more flagging

refantspw = ""
refantfield = calibrator_field_select_string

findrefant = RefAntHeuristics(
    vis=ms_active, field=refantfield, geometry=True, flagging=True
)
RefAntOutput = findrefant.calculate()
refAnt = ",".join(str(RefAntOutput[i]) for i in range(4))

task_logprint(f"The pipeline will use antenna(s) {refAnt} as the reference")


# Initial phase solutions on delay calibrator
uvrange = uvrange3C84 if cal3C84_d else ""
rmtables("finaldelayinitialgain.g")
gaincal(
    vis=ms_active,
    caltable="finaldelayinitialgain.g",
    field=delay_field_select_string,
    spw=tst_delay_spw,
    intent="",
    selectdata=True,
    uvrange=uvrange,
    scan=delay_scan_select_string,
    solint="int",
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=3.0,
    solnorm=False,
    gaintype="G",
    smodel=[],
    calmode="p",
    append=False,
    docallib=False,
    gaintable=priorcals,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)
GainTables = copy.copy(priorcals)
GainTables.append("finaldelayinitialgain.g")

uvrange = uvrange3C84 if cal3C84_d else ""
rmtables("finaldelay.k")
gaincal(
    vis=ms_active,
    caltable="finaldelay.k",
    field=delay_field_select_string,
    spw="",
    intent="",
    selectdata=True,
    uvrange=uvrange,
    scan=delay_scan_select_string,
    solint="inf",
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=3.0,
    solnorm=False,
    gaintype="K",
    smodel=[],
    calmode="p",
    append=False,
    docallib=False,
    gaintable=GainTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)
GainTables = copy.copy(priorcals)
GainTables.append("finaldelay.k")
task_logprint("Delay calibration complete")

uvrange = uvrange3C84 if cal3C84_bp else ""
rmtables("finalBPinitialgain.g")
gaincal(
    vis=ms_active,
    caltable="finalBPinitialgain.g",
    field="",
    spw=tst_bpass_spw,
    selectdata=True,
    uvrange=uvrange,
    scan=bandpass_scan_select_string,
    solint=gain_solint1,
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=3.0,
    solnorm=False,
    gaintype="G",
    smodel=[],
    calmode="p",
    append=False,
    docallib=False,
    gaintable=GainTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)
task_logprint("Initial BP gain calibration complete")


uvrange = uvrange3C84 if cal3C84_bp else ""
rmtables("finalBPcal.b")
BPGainTables = copy.copy(priorcals)
BPGainTables.append("finaldelay.k")
BPGainTables.append("finalBPinitialgain.g")
bandpass(
    vis=ms_active,
    caltable="finalBPcal.b",
    field=bandpass_field_select_string,
    spw="",
    selectdata=True,
    uvrange=uvrange3C84,
    scan=bandpass_scan_select_string,
    solint="inf",
    combine="scan",
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=5.0,
    solnorm=False,
    bandtype="B",
    fillgaps=0,
    smodel=[],
    append=False,
    docallib=False,
    gaintable=BPGainTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)
task_logprint("Bandpass calibration complete")

AllCalTables = copy.copy(priorcals)
AllCalTables.append("finaldelay.k")
AllCalTables.append("finalBPcal.b")

# Derive an average phase solution for the bandpass calibrator to apply
# to all data to make QA plots easier to interpret.
gaincal(
    vis=ms_active,
    caltable="averagephasegain.g",
    field=bandpass_field_select_string,
    spw="",
    selectdata=True,
    uvrange="",
    scan=bandpass_scan_select_string,
    solint="inf",
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=1.0,
    solnorm=False,
    gaintype="G",
    smodel=[],
    calmode="p",
    append=False,
    docallib=False,
    gaintable=AllCalTables,
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)

# In case any antenna is flagged by this process, unflag all solutions
# in this gain table (if an antenna does exist or has bad solutions from
# other steps, it will be flagged by those gain tables).

flagdata(
    vis="averagephasegain.g",
    mode="unflag",
    action="apply",
    flagbackup=False,
    savepars=False,
)

AllCalTables = copy.copy(priorcals)
AllCalTables.append("finaldelay.k")
AllCalTables.append("finalBPcal.b")
AllCalTables.append("averagephasegain.g")

ntables = len(AllCalTables)

applycal(
    vis=ms_active,
    field="",
    spw="",
    selectdata=True,
    scan=calibrator_scan_select_string,
    docallib=False,
    gaintable=AllCalTables,
    interp=[""],
    spwmap=[],
    calwt=[False] * ntables,
    parang=False,
    applymode="calflagstrict",
    flagbackup=False,
)


os.system("rm -rf calibrators.ms")
split(
    vis=ms_active,
    outputvis="calibrators.ms",
    datacolumn="corrected",
    field="",
    spw="",
    width=int(max(channels)),
    antenna="",
    timebin="0s",
    timerange="",
    scan=calibrator_scan_select_string,
    intent="",
    array="",
    uvrange="",
    correlation="",
    observation="",
    keepflags=False,
)


# FIXME The code from here until the `setjy`-loop is duplicated from `fluxboot`
positions = field_positions.T.squeeze()
standard_source_names = ["3C48", "3C138", "3C147", "3C286"]
standard_source_fields = find_standards(positions)
for ii, fields in enumerate(standard_source_fields):
    for myfield in fields:
        for myspw in field_spws[myfield]:
            reference_frequency = center_frequencies[myspw]
            EVLA_band = find_EVLA_band(reference_frequency)
            task_logprint(
                f"Center freq for spw {myspw} = {reference_frequency}, "
                f"observing band = {EVLA_band}"
            )
            model_image = f"{standard_source_names[ii]}_{EVLA_band}.im"
            task_logprint(
                f"Setting model for field {myfield} spw {myspw} using {model_image}"
            )
            try:
                setjy(
                    vis="calibrators.ms",
                    field=str(myfield),
                    spw=str(myspw),
                    selectdata=False,
                    scalebychan=True,
                    standard="Perley-Butler 2017",
                    model=model_image,
                    listmodels=False,
                    usescratch=scratch,
                )
            except:
                task_logprint(f"No data found for field {myfield} spw {myspw}")

if not os.path.exists(fluxscale_output):
    task_logprint(f"Error: fluxscale output '{fluxscale_output}' does not exist.")

sources = []
flux_densities = []
spws = []
for field_id in fluxscale_result.keys():
    try:
        int(field_id)
    except ValueError:
        continue  # not a field ID, "freq", "spwName", etc.
    sourcename = fluxscale_result[field_id]["fieldName"]
    secondary_keys = list(fluxscale_result[field_id].keys())
    for spw_id in secondary_keys:
        try:
            int(spw_id)
        except ValueError:
            continue  # not a SpW ID, "fitRefFreq", "spidx", etc.
        flux_items = fluxscale_result[field_id][spw_id]
        flux_d = list(flux_items["fluxd"])
        flux_d_err = list(flux_items["fluxdErr"])
        for f_d, f_e in zip(flux_d, flux_d_err):
            if f_d != -1 and f_d != 0:
                sources.append(sourcename)
                flux_densities.append([float(f_d), float(f_e)])
                spws.append(int(spw_id))

results = []
for source in np.unique(sources):
    indices = np.argwhere(np.array(sources) == source).squeeze(axis=1)
    bands = [find_EVLA_band(center_frequencies[spws[i]]) for i in indices]
    for band in np.unique(bands):
        lfreqs = []
        lfds = []
        lerrs = []
        uspws = []
        for ii in indices:
            center_freq = center_frequencies[spws[ii]]
            if find_EVLA_band(center_freq) == band:
                lfreqs.append(np.log10(center_freq))
                lfds.append(np.log10(flux_densities[ii][0]))
                ratio = flux_densities[ii][1] / flux_densities[ii][0]
                lerrs.append(np.log10(np.e) * ratio)
                uspws.append(spws[ii])
        if len(lfds) <= 2:
            aa = lfds[0]
            bb = 0.0
            SNR = 0.0
        else:
            alfds = np.array(lfds)
            alerrs = np.array(lerrs)
            alfreqs = np.array(lfreqs)
            pinit = [0.0, 0.0]
            fit_out = sp.optimize.leastsq(
                errfunc,
                pinit,
                args=(alfreqs, alfds, alerrs),
                full_output=True,
            )
            aa, bb = fit_out[0]
            covar = fit_out[1]
            summed_error = 0.0
            for freq, data in zip(alfreqs, alfds):
                model = aa + bb * freq
                summed_error += (model - data) ** 2
            residual_variance = summed_error / (len(alfds) - 2)
            SNR = np.abs(bb) / np.sqrt(covar[1][1] * residual_variance)
        # Take as the reference frequency the lowest one (although this
        # shouldn't matter, in principle).
        reffreq = 10 ** lfreqs[0] / 1e9
        fluxdensity = 10 ** (aa + bb * lfreqs[0])
        spix = bb
        results.append([source, uspws, fluxdensity, spix, SNR, reffreq])
        task_logprint(f"{source} {band} fitted spectral index = {spix} and SNR = {SNR}")
        task_logprint("Frequency, data, error, and fitted data:")
        for ii in range(len(lfreqs)):
            flux_exp = 10 ** lfreqs[ii] / 1e9
            err_exp = 10 ** lfds[ii]
            SS = fluxdensity * (flux_exp / reffreq) ** spix
            fderr = lerrs[ii] * err_exp / np.log10(np.e)
            task_logprint(f"    {flux_exp} {err_exp} {fderr} {SS}")

task_logprint("Setting power-law fit in the model column")
for result in results:
    for spw_i in result[1]:
        task_logprint(f"Running setjy on spw {spw_i}")
        setjy(
            vis="calibrators.ms",
            field=str(result[0]),
            spw=str(spw_i),
            selectdata=False,
            scalebychan=True,
            standard="manual",
            fluxdensity=[result[2], 0, 0, 0],
            spix=result[3],
            reffreq=str(result[5]) + "GHz",
            usescratch=scratch,
        )
task_logprint("Flux density bootstrapping finished.")

# Derive gain tables.  Note that gaincurves, opacity corrections and antenna
# position corrections have already been applied during applycal and split in
# above.

# FIXME Need to add check for 3C84 in here, when heuristics have been sorted
# out.
gaincal(
    vis="calibrators.ms",
    caltable="phaseshortgaincal.g",
    field="",
    spw="",
    intent="",
    selectdata=False,
    solint=new_gain_solint1,
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=3.0,
    solnorm=False,
    gaintype="G",
    smodel=[],
    calmode="p",
    append=False,
    docallib=False,
    gaintable=[""],
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)

gaincal(
    vis="calibrators.ms",
    caltable="finalampgaincal.g",
    field="",
    spw="",
    intent="",
    selectdata=False,
    solint=gain_solint2,
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=5.0,
    solnorm=False,
    gaintype="G",
    smodel=[],
    calmode="ap",
    append=False,
    docallib=False,
    gaintable=["phaseshortgaincal.g"],
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)

gaincal(
    vis="calibrators.ms",
    caltable="finalphasegaincal.g",
    field="",
    spw="",
    intent="",
    selectdata=False,
    solint=gain_solint2,
    combine="scan",
    preavg=-1.0,
    refant=refAnt,
    minblperant=minBL_for_cal,
    minsnr=3.0,
    solnorm=False,
    gaintype="G",
    smodel=[],
    calmode="p",
    append=False,
    docallib=False,
    gaintable=["finalampgaincal.g"],
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)
task_logprint("Final calibration tables created")


try:
    tb.open("finaldelay.k")
    fpar = tb.getcol("FPARAM")
finally:
    tb.close()
delays = np.abs(fpar)
maxdelay = np.max(delays)


task_logprint("Plotting final calibration tables")
nplots = int(numAntenna / 3)
if (numAntenna % 3) > 0:
    nplots += 1

for ii in range(nplots):
    plotfile = f"finaldelay{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="finaldelay.k",
        xaxis="freq",
        yaxis="delay",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

for ii in range(nplots):
    plotfile = f"finalBPinitialgainphase{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="finalBPinitialgain.g",
        xaxis="time",
        yaxis="phase",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, -180, 180],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

try:
    tb.open("finalBPcal.b")
    dataVarCol = tb.getvarcol("CPARAM")
    flagVarCol = tb.getvarcol("FLAG")
finally:
    tb.close()
rowlist = dataVarCol.keys()
nrows = len(rowlist)
maxmaxamp = 0.0
maxmaxphase = 0.0

for rrow in rowlist:
    dataArr = dataVarCol[rrow]
    flagArr = flagVarCol[rrow]
    amps = np.abs(dataArr)
    phases = np.arctan2(np.imag(dataArr), np.real(dataArr))
    good = np.logical_not(flagArr)
    tmparr = amps[good]
    if len(tmparr) > 0:
        maxamp = np.max(amps[good])
        if maxamp > maxmaxamp:
            maxmaxamp = maxamp
    tmparr = np.abs(phases[good])
    if len(tmparr) > 0:
        maxphase = np.max(np.abs(phases[good])) * 180.0 / np.pi
        if maxphase > maxmaxphase:
            maxmaxphase = maxphase
ampplotmax = maxmaxamp
phaseplotmax = maxmaxphase

for ii in range(nplots):
    plotfile = f"finalBPcal_amp{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="finalBPcal.b",
        xaxis="freq",
        yaxis="amp",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, 0, ampplotmax],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

for ii in range(nplots):
    plotfile = f"finalBPcal_phase{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="finalBPcal.b",
        xaxis="freq",
        yaxis="phase",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, -phaseplotmax, phaseplotmax],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

for ii in range(nplots):
    plotfile = f"phaseshortgaincal{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="phaseshortgaincal.g",
        xaxis="time",
        yaxis="phase",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, -180, 180],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

try:
    tb.open("finalampgaincal.g")
    cpar = tb.getcol("CPARAM")
    flgs = tb.getcol("FLAG")
finally:
    tb.close()
amps = np.abs(cpar)
good = np.logical_not(flgs)
maxamp = np.max(amps[good])
plotmax = max(2.0, maxamp)

for ii in range(nplots):
    plotfile = f"finalamptimecal{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="finalampgaincal.g",
        xaxis="time",
        yaxis="amp",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, 0, plotmax],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

for ii in range(nplots):
    plotfile = f"finalampfreqcal{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="finalampgaincal.g",
        xaxis="freq",
        yaxis="amp",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, 0, plotmax],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )

for ii in range(nplots):
    plotfile = f"finalphasegaincal{ii}.png"
    ant_select = str(ii * 3) + "~" + str(ii * 3 + 2)
    plotms(
        vis="finalphasegaincal.g",
        xaxis="time",
        yaxis="phase",
        antenna=ant_select,
        spw="",
        timerange="",
        gridrows=3,
        coloraxis="spw",
        iteraxis="antenna",
        plotrange=[0, 0, -180, 180],
        showgui=False,
        plotfile=plotfile,
        highres=True,
        overwrite=True,
    )


# Calculate fractions of flagged solutions for final QA2
flaggedDelaySolns = getCalFlaggedSoln("finaldelay.k")
flaggedBPSolns = getCalFlaggedSoln("finalBPcal.b")
flaggedAmpSolns = getCalFlaggedSoln("finalampgaincal.g")
flaggedPhaseSolns = getCalFlaggedSoln("finalphasegaincal.g")

if flaggedDelaySolns["all"]["total"] > 0:
    if flaggedDelaySolns["antmedian"]["fraction"] > critfrac:
        QA2_delay = "Partial"
    else:
        QA2_delay = "Pass"
else:
    QA2_delay = "Fail"

if flaggedBPSolns["all"]["total"] > 0:
    if flaggedBPSolns["antmedian"]["fraction"] > 0.2:
        QA2_BP = "Partial"
    else:
        QA2_BP = "Pass"
else:
    QA2_BP = "Fail"

if flaggedAmpSolns["all"]["total"] > 0:
    if flaggedAmpSolns["antmedian"]["fraction"] > 0.1:
        QA2_amp = "Partial"
    else:
        QA2_amp = "Pass"
else:
    QA2_amp = "Fail"

if flaggedPhaseSolns["all"]["total"] > 0:
    if flaggedPhaseSolns["antmedian"]["fraction"] > 0.1:
        QA2_phase = "Partial"
    else:
        QA2_phase = "Pass"
else:
    QA2_phase = "Fail"

if QA2_delay == "Fail" or QA2_BP == "Fail" or QA2_amp == "Fail" or QA2_phase == "Fail":
    QA2_finalcals = "Fail"
elif (
    QA2_delay == "Partial"
    or QA2_BP == "Partial"
    or QA2_amp == "Partial"
    or QA2_phase == "Partial"
):
    QA2_finalcals = "Partial"

task_logprint(f"QA2 score: {QA2_finalcals}")
task_logprint("Finished EVLA_pipe_finalcals.py")
time_list = runtiming("finalcals", "end")

pipeline_save()
