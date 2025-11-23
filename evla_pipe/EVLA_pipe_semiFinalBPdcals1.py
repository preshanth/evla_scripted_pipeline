"""
Semi-final delay and bandpass calibration module.

This module performs semi-final delay and bandpass calibrations on the
measurement set and applies them to all calibrators. It replaces the
procedural EVLA_pipe_semiFinalBPdcals1.py with a cleaner, modular approach.
"""

import copy
import os
from typing import Dict, Any, List, Optional

from casatasks import gaincal, bandpass, applycal
from casatools import table

from evla_pipe.utils import (
from evla_pipe.pipeline_steps import register_step
    logprint,
    runtiming,
    RefAntHeuristics,
    semiFinaldelays,
    getCalFlaggedSoln,
    format_qa_status,
)

tb = table()


def task_logprint(msg: str) -> None:
    """
    Centralized logging for semi-final BP/delay calibration operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/semiFinalBPdcals1_cal.log")


def find_reference_antenna(
    pipeline_context: Dict[str, Any]
) -> str:
    """
    Find optimal reference antenna for calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing MS and field information

    Returns
    -------
    str
        Reference antenna name

    Notes
    -----
    Uses geometry and flagging heuristics to select best reference antenna.
    """
    ms_active = pipeline_context.get("msname")
    calibrator_field_select_string = pipeline_context.get(
        "calibrator_field_select_string", ""
    )

    task_logprint("Finding reference antenna for semi-final delay and BP calibrations")

    findrefant = RefAntHeuristics(
        vis=ms_active,
        field=calibrator_field_select_string,
        geometry=True,
        flagging=True,
    )
    RefAntOutput = findrefant.calculate()
    refAnt = str(RefAntOutput[0])

    task_logprint(f"Selected reference antenna: {refAnt}")
    return refAnt


def compute_initial_delay_phase(
    pipeline_context: Dict[str, Any],
    refAnt: str,
    priorcals: List[str],
) -> None:
    """
    Compute initial phase solutions on delay calibrator.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibration parameters
    refAnt : str
        Reference antenna name
    priorcals : list of str
        List of prior calibration tables to apply

    Notes
    -----
    Creates semiFinaldelayinitialgain.g calibration table.
    """
    ms_active = pipeline_context.get("msname")
    delay_field_select_string = pipeline_context.get("delay_field_select_string", "")
    delay_scan_select_string = pipeline_context.get("delay_scan_select_string", "")
    tst_delay_spw = pipeline_context.get("tst_delay_spw", "")
    uvrange3C84 = pipeline_context.get("uvrange3C84", "")
    minBL_for_cal = pipeline_context.get("minBL_for_cal", 3)

    task_logprint("Computing initial phase solutions on delay calibrator")

    from evla_pipe.utils import get_caltable_path
    from casatasks import rmtables
    semiFinaldelayinitialgain_table = get_caltable_path("semiFinaldelayinitialgain.g", "intermediate")
    rmtables(semiFinaldelayinitialgain_table)

    gaincal(
        vis=ms_active,
        caltable=semiFinaldelayinitialgain_table,
        field=delay_field_select_string,
        spw=tst_delay_spw,
        intent="",
        selectdata=True,
        uvrange=uvrange3C84,
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

    task_logprint("Initial delay phase solutions complete")


def compute_semi_final_delay(
    pipeline_context: Dict[str, Any],
    refAnt: str,
    priorcals: List[str],
) -> Dict[str, Any]:
    """
    Compute semi-final delay calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibration parameters
    refAnt : str
        Reference antenna name
    priorcals : list of str
        List of prior calibration tables to apply

    Returns
    -------
    dict
        Dictionary containing flagged solution statistics with structure:
        {
            'all': {'fraction': float, 'total': int},
            'antmedian': {'fraction': float}
        }

    Notes
    -----
    Creates delay.k calibration table.
    """
    ms_active = pipeline_context.get("msname")
    delay_field_select_string = pipeline_context.get("delay_field_select_string", "")
    delay_scan_select_string = pipeline_context.get("delay_scan_select_string", "")
    cal3C84_d = pipeline_context.get("cal3C84_d", False)
    uvrange3C84 = pipeline_context.get("uvrange3C84", "")
    minBL_for_cal = pipeline_context.get("minBL_for_cal", 3)

    task_logprint("Computing semi-final delay calibration")

    from evla_pipe.utils import get_caltable_path
    from casatasks import rmtables
    delay_table = get_caltable_path("delay.k", "intermediate")
    rmtables(delay_table)

    flaggedDelaySolns = semiFinaldelays(
        ms_active,
        delay_table,
        delay_field_select_string,
        delay_scan_select_string,
        refAnt,
        minBL_for_cal,
        priorcals,
        cal3C84_d,
        uvrange3C84,
    )

    task_logprint(
        f"Fraction of flagged delay solutions = {flaggedDelaySolns['all']['fraction']:.4f}"
    )
    task_logprint(
        f"Median fraction of flagged delay solutions per antenna = "
        f"{flaggedDelaySolns['antmedian']['fraction']:.4f}"
    )
    task_logprint("Delay calibration complete")

    return flaggedDelaySolns


def assess_delay_quality(flaggedDelaySolns: Dict[str, Any], critfrac: float) -> str:
    """
    Assess quality of delay calibration solutions.

    Parameters
    ----------
    flaggedDelaySolns : dict
        Dictionary containing flagged solution statistics
    critfrac : float
        Critical fraction threshold for partial QA status

    Returns
    -------
    str
        QA2 status: 'Pass', 'Partial', or 'Fail'
    """
    if flaggedDelaySolns["all"]["total"] > 0:
        if flaggedDelaySolns["antmedian"]["fraction"] > critfrac:
            QA2_delay = "Partial"
        else:
            QA2_delay = "Pass"
    else:
        QA2_delay = "Fail"

    task_logprint(f"QA2_delay: {format_qa_status(QA2_delay)}")
    return QA2_delay


def compute_bp_initial_gain(
    pipeline_context: Dict[str, Any],
    refAnt: str,
    priorcals: List[str],
) -> None:
    """
    Compute initial gain calibration on bandpass calibrator.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibration parameters
    refAnt : str
        Reference antenna name
    priorcals : list of str
        List of prior calibration tables (includes delay.k)

    Notes
    -----
    Creates BPdinitialgain.g calibration table.
    """
    ms_active = pipeline_context.get("msname")
    bandpass_scan_select_string = pipeline_context.get(
        "bandpass_scan_select_string", ""
    )
    tst_bpass_spw = pipeline_context.get("tst_bpass_spw", "")
    cal3C84_bp = pipeline_context.get("cal3C84_bp", False)
    uvrange3C84 = pipeline_context.get("uvrange3C84", "")
    gain_solint1 = pipeline_context.get("gain_solint1", "")
    minBL_for_cal = pipeline_context.get("minBL_for_cal", 3)

    task_logprint("Computing initial gain calibration on BP calibrator")

    from evla_pipe.utils import get_caltable_path
    from casatasks import rmtables
    BPdinitialgain_table = get_caltable_path("BPdinitialgain.g", "intermediate")
    delay_table = get_caltable_path("delay.k", "intermediate")
    rmtables(BPdinitialgain_table)

    GainTables = copy.copy(priorcals)
    GainTables.append(delay_table)
    uvrange_bp = uvrange3C84 if cal3C84_bp else ""

    gaincal(
        vis=ms_active,
        caltable=BPdinitialgain_table,
        field="",
        spw=tst_bpass_spw,
        selectdata=True,
        uvrange=uvrange_bp,
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

    task_logprint("Initial gain calibration on BP calibrator complete")


def compute_bandpass_calibration(
    pipeline_context: Dict[str, Any],
    refAnt: str,
    priorcals: List[str],
) -> Dict[str, Any]:
    """
    Compute semi-final bandpass calibration.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibration parameters
    refAnt : str
        Reference antenna name
    priorcals : list of str
        List of prior calibration tables (includes delay.k and BPdinitialgain.g)

    Returns
    -------
    dict
        Dictionary containing flagged solution statistics with structure:
        {
            'all': {'fraction': float, 'total': int},
            'antmedian': {'fraction': float}
        }

    Notes
    -----
    Creates BPcal.b calibration table.
    """
    ms_active = pipeline_context.get("msname")
    bandpass_field_select_string = pipeline_context.get(
        "bandpass_field_select_string", ""
    )
    bandpass_scan_select_string = pipeline_context.get(
        "bandpass_scan_select_string", ""
    )
    cal3C84_bp = pipeline_context.get("cal3C84_bp", False)
    uvrange3C84 = pipeline_context.get("uvrange3C84", "")
    minBL_for_cal = pipeline_context.get("minBL_for_cal", 3)

    task_logprint("Computing semi-final bandpass calibration")

    from evla_pipe.utils import get_caltable_path
    from casatasks import rmtables
    BPcal_table = get_caltable_path("BPcal.b", "intermediate")
    delay_table = get_caltable_path("delay.k", "intermediate")
    BPdinitialgain_table = get_caltable_path("BPdinitialgain.g", "intermediate")
    rmtables(BPcal_table)

    BPGainTables = copy.copy(priorcals)
    BPGainTables.append(delay_table)
    BPGainTables.append(BPdinitialgain_table)
    uvrange_bp = uvrange3C84 if cal3C84_bp else ""

    bandpass(
        vis=ms_active,
        caltable=BPcal_table,
        field=bandpass_field_select_string,
        spw="",
        selectdata=True,
        uvrange=uvrange_bp,
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

    flaggedBPSolns = getCalFlaggedSoln(BPcal_table)

    task_logprint(
        f"Fraction of flagged BP solutions = {flaggedBPSolns['all']['fraction']:.4f}"
    )
    task_logprint(
        f"Median fraction of flagged BP solutions per antenna = "
        f"{flaggedBPSolns['antmedian']['fraction']:.4f}"
    )

    return flaggedBPSolns


def assess_bandpass_quality(flaggedBPSolns: Dict[str, Any]) -> str:
    """
    Assess quality of bandpass calibration solutions.

    Parameters
    ----------
    flaggedBPSolns : dict
        Dictionary containing flagged solution statistics

    Returns
    -------
    str
        QA2 status: 'Pass', 'Partial', or 'Fail'

    Notes
    -----
    Uses 0.2 as threshold for partial status (vs critfrac for delay).
    """
    if flaggedBPSolns["all"]["total"] > 0:
        if flaggedBPSolns["antmedian"]["fraction"] > 0.2:
            QA2_BP = "Partial"
        else:
            QA2_BP = "Pass"
    else:
        QA2_BP = "Fail"

    task_logprint(f"QA2_BP: {format_qa_status(QA2_BP)}")
    return QA2_BP


def apply_calibrations_to_calibrators(
    pipeline_context: Dict[str, Any],
    priorcals: List[str],
) -> None:
    """
    Apply semi-final delay and BP calibrations to all calibrators.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing MS and scan information
    priorcals : list of str
        List of prior calibration tables (includes delay.k and BPcal.b)

    Notes
    -----
    Applies calibrations with 'calflagstrict' mode to all calibrator scans.
    """
    ms_active = pipeline_context.get("msname")
    calibrator_scan_select_string = pipeline_context.get(
        "calibrator_scan_select_string", ""
    )

    task_logprint("Applying semi-final delay and BP calibrations to all calibrators")

    from evla_pipe.utils import get_caltable_path
    delay_table = get_caltable_path("delay.k", "intermediate")
    BPcal_table = get_caltable_path("BPcal.b", "intermediate")

    AllCalTables = copy.copy(priorcals)
    AllCalTables.append(delay_table)
    AllCalTables.append(BPcal_table)
    ntables = len(AllCalTables)

    applycal(
        vis=ms_active,
        field="",
        spw="",
        selectdata=True,
        scan=calibrator_scan_select_string,
        gaintable=AllCalTables,
        interp=[""],
        spwmap=[],
        parang=False,
        calwt=[False] * ntables,
        applymode="calflagstrict",
        flagbackup=False,
    )

    task_logprint("Applied semi-final delay and BP calibrations to calibrators")


def compute_overall_qa_status(QA2_delay: str, QA2_BP: str) -> str:
    """
    Compute overall QA2 status from delay and BP components.

    Parameters
    ----------
    QA2_delay : str
        QA2 status for delay calibration
    QA2_BP : str
        QA2 status for bandpass calibration

    Returns
    -------
    str
        Overall QA2 status: 'Pass', 'Partial', or 'Fail'

    Notes
    -----
    Fail if either component fails, Partial if either is partial, else Pass.
    """
    if QA2_delay == "Fail" or QA2_BP == "Fail":
        return "Fail"
    elif QA2_delay == "Partial" or QA2_BP == "Partial":
        return "Partial"
    else:
        return "Pass"


def semifinalbpdcals1(
    pipeline_context: Dict[str, Any],
    priorcals: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Perform semi-final delay and bandpass calibrations.

    This function computes semi-final delay and bandpass calibrations on the
    measurement set and applies them to all calibrators. It replaces the
    procedural EVLA_pipe_semiFinalBPdcals1.py script.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Measurement set name
        - calibrator_field_select_string : str
            Field selection for calibrators
        - delay_field_select_string : str
            Field selection for delay calibrator
        - delay_scan_select_string : str
            Scan selection for delay calibration
        - bandpass_field_select_string : str
            Field selection for bandpass calibrator
        - bandpass_scan_select_string : str
            Scan selection for bandpass calibration
        - calibrator_scan_select_string : str
            Scan selection for all calibrators
        - tst_delay_spw : str
            SPW selection for delay calibration
        - tst_bpass_spw : str
            SPW selection for bandpass calibration
        - uvrange3C84 : str
            UV range for 3C84 calibrator
        - cal3C84_d : bool
            Whether to use 3C84 for delay calibration
        - cal3C84_bp : bool
            Whether to use 3C84 for bandpass calibration
        - minBL_for_cal : int
            Minimum baselines per antenna for calibration
        - critfrac : float
            Critical fraction threshold for QA assessment
        - gain_solint1 : str
            Solution interval for initial BP gain calibration
    priorcals : list of str, optional
        List of prior calibration tables to apply. If None, uses
        ['gain_curves.g', 'opacities.g'] from context.

    Returns
    -------
    dict
        Updated pipeline context with new keys:
        - QA2_semiFinalBPdcals1 : str
            Overall QA2 status ('Pass', 'Partial', or 'Fail')
        - QA2_delay : str
            QA2 status for delay calibration
        - QA2_BP : str
            QA2 status for bandpass calibration
        - semifinal_refant : str
            Reference antenna used for calibration
        - delay_flagged_fraction : float
            Fraction of flagged delay solutions
        - bp_flagged_fraction : float
            Fraction of flagged bandpass solutions

    Notes
    -----
    Creates the following calibration tables:
    - semiFinaldelayinitialgain.g : Initial phase solutions on delay calibrator
    - delay.k : Semi-final delay calibration
    - BPdinitialgain.g : Initial gain solutions on BP calibrator
    - BPcal.b : Semi-final bandpass calibration

    Sets QA2 status based on:
    - Delay: Fail if no solutions, Partial if median flagged fraction > critfrac
    - BP: Fail if no solutions, Partial if median flagged fraction > 0.2
    - Overall: Fail if either fails, Partial if either partial, else Pass
    """
    task_logprint("*** Starting semi-final delay and BP calibrations ***")
    time_list = runtiming("semiFinalBPdcals1", "start")

    # Initialize QA flags
    QA2_semiFinalBPdcals1 = "Pass"
    QA2_delay = "Pass"
    QA2_BP = "Pass"

    # Get priorcals from parameter or context
    if priorcals is None:
        priorcals = pipeline_context.get("priorcals", ["gain_curves.g", "opacities.g"])

    # Get critical fraction threshold
    critfrac = pipeline_context.get("critfrac", 0.5)

    try:
        # Find reference antenna
        refAnt = find_reference_antenna(pipeline_context)
        pipeline_context["semifinal_refant"] = refAnt

        # Compute initial phase solutions on delay calibrator
        compute_initial_delay_phase(pipeline_context, refAnt, priorcals)

        # Compute semi-final delay calibration
        flaggedDelaySolns = compute_semi_final_delay(
            pipeline_context, refAnt, priorcals
        )
        QA2_delay = assess_delay_quality(flaggedDelaySolns, critfrac)
        pipeline_context["delay_flagged_fraction"] = float(
            flaggedDelaySolns["all"]["fraction"]
        )

        # Compute initial gain on BP calibrator
        compute_bp_initial_gain(pipeline_context, refAnt, priorcals)

        # Compute semi-final bandpass calibration
        flaggedBPSolns = compute_bandpass_calibration(
            pipeline_context, refAnt, priorcals
        )
        QA2_BP = assess_bandpass_quality(flaggedBPSolns)
        pipeline_context["bp_flagged_fraction"] = float(
            flaggedBPSolns["all"]["fraction"]
        )

        # Apply calibrations to all calibrators
        apply_calibrations_to_calibrators(pipeline_context, priorcals)

        # Compute overall QA status
        QA2_semiFinalBPdcals1 = compute_overall_qa_status(QA2_delay, QA2_BP)

        # Update context with QA results
        pipeline_context["QA2_semiFinalBPdcals1"] = QA2_semiFinalBPdcals1
        pipeline_context["QA2_delay"] = QA2_delay
        pipeline_context["QA2_BP"] = QA2_BP

    except Exception as e:
        task_logprint(f"Error in semi-final BP/delay calibration: {e}")
        pipeline_context["QA2_semiFinalBPdcals1"] = "Fail"
        pipeline_context["QA2_delay"] = "Fail"
        pipeline_context["QA2_BP"] = "Fail"
        pipeline_context["error_message"] = str(e)
        QA2_semiFinalBPdcals1 = "Fail"

    task_logprint(f"QA2 score: {format_qa_status(QA2_semiFinalBPdcals1)}")
    time_list = runtiming("semiFinalBPdcals1", "end")

    return pipeline_context


# Backward compatibility alias
EVLA_pipe_semiFinalBPdcals1 = semifinalbpdcals1



@register_step("EVLA_pipe_semiFinalBPdcals1")
def EVLA_pipe_semiFinalBPdcals1(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for semifinalbpdcals1() to match expected step name.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary

    Returns
    -------
    dict
        Updated pipeline context
    """
    return semifinalbpdcals1(pipeline_context)
