"""
Make a gain table that includes gain and opacity corrections for final
amplitude calibration and for flux density bootstrapping.
"""

from casatasks import setjy, gaincal

from . import pipeline_save
from .utils import (
        runtiming,
        logprint,
        find_standards,
        find_EVLA_band,
        RefAntHeuristics,
)


def task_logprint(msg):
    logprint(msg, logfileout="logs/fluxgains.log")


task_logprint("Starting EVLA_pipe_fluxgains.py")
time_list = runtiming("fluxgains", "start")
QA2_fluxgains = "Pass"

task_logprint("Setting models for standard primary calibrators")

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

task_logprint("Making gain tables for flux density bootstrapping")

task_logprint(f"Short solint = {new_gain_solint1}")
task_logprint(f"Long solint = {gain_solint2}")

task_logprint("\nFinding a reference antenna.\n")

refantspw = ""
refantfield = calibrator_field_select_string
findrefant = RefAntHeuristics(
    vis="calibrators.ms", field=refantfield, geometry=True, flagging=True
)
RefAntOutput = findrefant.calculate()
refAnt = ",".join(str(RefAntOutput[i]) for i in range(4))
task_logprint(f"The pipeline will use antenna(s) {refAnt} as the reference")


# Derive amp gain table.  Note that gaincurves and opacity corrections have
# already been applied during applycal and split in semiFinalBPdcals/solint.py.

# FIXME Need to add check for 3C84 in here, when heuristics have been sorted out.
gaincal(
    vis="calibrators.ms",
    caltable="fluxphaseshortgaincal.g",
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
    caltable="fluxgaincal.g",
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
    gaintable=["fluxphaseshortgaincal.g"],
    gainfield=[""],
    interp=[""],
    spwmap=[],
    parang=False,
)


task_logprint("Gain table fluxgaincal.g is ready for flagging")

# Calculate fractions of flagged solutions for final QA2; note, can
# tolerate higher fraction of flagged solutions for this step than in
# other gain tables

flaggedGainSolns = getCalFlaggedSoln("fluxgaincal.g")

if flaggedGainSolns["all"]["total"] == 0:
    QA2_fluxgains = "Fail"
elif flaggedGainSolns["antmedian"]["fraction"] > 0.2:
    QA2_fluxgains = "Partial"

task_logprint(f"QA2 score: {QA2_fluxgains}")
task_logprint("Finished EVLA_pipe_fluxgains.py")
time_list = runtiming("fluxgains", "end")

pipeline_save()
