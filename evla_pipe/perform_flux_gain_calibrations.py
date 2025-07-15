# perform_flux_gain_calibrations.py

from casatasks import gaincal
from evla_pipe.utils import (
        runtiming,
        logprint,
        RefAntHeuristics,
)

def task_logprint(msg):
    logprint(msg, logfileout="logs/fluxgains_gaincal.log")

def perform_flux_gain_calibrations(pipeline_context, new_gain_solint1, gain_solint2, minBL_for_cal):
    """
    Make gain tables for flux density bootstrapping.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
        new_gain_solint1 (str): Short solution interval.
        gain_solint2 (str): Long solution interval.
        minBL_for_cal (int): Minimum baselines per antenna for calibration.
    """
    task_logprint("*** Starting perform_flux_gain_calibrations.py ***")
    runtiming("fluxgains_gaincal", "start")

    calibrators_ms = pipeline_context.get("msname", "calibrators.ms") # Default to calibrators.ms
    calibrator_field_select_string = pipeline_context.get("calibrator_field_select_string", "")

    task_logprint(f"Short solint = {new_gain_solint1}")
    task_logprint(f"Long solint = {gain_solint2}")
    task_logprint("\nFinding a reference antenna.\n")

    findrefant = RefAntHeuristics(
        vis=calibrators_ms, field=calibrator_field_select_string, geometry=True, flagging=True
    )
    RefAntOutput = findrefant.calculate()
    refAnt = ",".join(str(RefAntOutput[i]) for i in range(min(4, len(RefAntOutput))))
    task_logprint(f"The pipeline will use antenna(s) {refAnt} as the reference")

    # Derive amp gain table.
    gaincal(
        vis=calibrators_ms,
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
        vis=calibrators_ms,
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
    runtiming("fluxgains_gaincal", "end")