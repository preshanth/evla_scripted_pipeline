# EVLA_pipe_polcal.py

"""
Polarization calibration module for EVLA pipeline.

This module performs polarization calibration including:
- Cross-hand delay calibration (Xf)
- D-term leakage calibration (Df)

This script should run after finalcals but before applycals so that
the polarization calibration tables can be included in the calibration
application.
"""

from typing import Dict, Any, List, Optional
from casatasks import gaincal, polcal
from evla_pipe.utils import runtiming, logprint, get_log_path, get_caltable_path
from evla_pipe.pipeline_steps import register_step


def task_logprint(msg: str) -> None:
    """
    Centralized logging for polarization calibration operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout=str(get_log_path("polcal.log")))


def polcal(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform polarization calibration (Df, Xf) for the EVLA pipeline.

    This replaces EVLA_pipe_polcal.py with a cleaner, modular approach.
    Performs cross-hand delay calibration (Xf) and D-term leakage
    calibration (Df) using standard polarization calibrators.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Measurement set name
        - do_pol : bool
            Whether to perform polarization calibration
        - delay_cal_table : str, optional
            Delay calibration table path
        - bpass_cal_table : str, optional
            Bandpass calibration table path
        - gain_cal_table : str, optional
            Gain calibration table path
        - phase_int_cal_table : str, optional
            Phase calibration table path (alternative to gain_cal_table)
        - pol_angle_field : int, optional
            Field ID for polarization angle calibration
        - pol_leakage_field : int, optional
            Field ID for leakage calibration
        - refant : str
            Reference antenna
        - standard_source_names : list, optional
            List of standard calibrator names
        - field_names : list, optional
            List of field names in MS

    Returns
    -------
    dict
        Updated pipeline context with:
        - kcross_cal_table : str
            Path to cross-hand delay calibration table
        - dterms_cal_table : str
            Path to D-term leakage calibration table
        - pol_cal_tables : list
            List of all polarization calibration tables
        - polarization_calibrated : bool
            Whether polarization calibration succeeded
        - QA2_polcal : str
            Quality assessment status ("Pass", "Partial", or "Fail")
        - polarization_error : str, optional
            Error message if calibration failed

    Notes
    -----
    Sets QA2_polcal flag based on success/failure.
    If do_pol is False, skips calibration and returns unchanged context.
    Automatically detects polarization calibrators if not specified.
    """
    task_logprint("*** Starting Polarization Calibration ***")
    time_list = runtiming("polcal", "start")
    QA2_polcal = "Pass"

    # Get context variables
    ms_active = pipeline_context.get("msname")
    do_pol = pipeline_context.get("do_pol", False)

    if not do_pol:
        task_logprint("Polarization calibration disabled, skipping polcal")
        pipeline_context["QA2_polcal"] = "Pass"
        pipeline_context["time_list"] = time_list
        return pipeline_context

    if not ms_active:
        task_logprint("ERROR: No measurement set specified")
        QA2_polcal = "Fail"
        pipeline_context["QA2_polcal"] = QA2_polcal
        pipeline_context["time_list"] = time_list
        return pipeline_context

    # Build prior calibration tables list
    priorcals = _build_prior_calibrations(pipeline_context)

    # Get or detect polarization calibrator fields
    pol_angle_field, pol_leakage_field = _get_polarization_calibrators(pipeline_context)

    if pol_angle_field is None or pol_leakage_field is None:
        task_logprint("WARNING: No polarization calibrators found, skipping polarization calibration")
        QA2_polcal = "Partial"
        pipeline_context["QA2_polcal"] = QA2_polcal
        pipeline_context["time_list"] = time_list
        return pipeline_context

    refant = pipeline_context.get("refant", "")

    try:
        # Step 1: Cross-hand delay calibration (Xf)
        kcross_table = _perform_kcross_calibration(
            ms_active=ms_active,
            pol_angle_field=pol_angle_field,
            refant=refant,
            priorcals=priorcals
        )
        pipeline_context["kcross_cal_table"] = kcross_table

        # Step 2: D-term leakage calibration (Df)
        dterms_table = _perform_dterms_calibration(
            ms_active=ms_active,
            pol_leakage_field=pol_leakage_field,
            priorcals=priorcals,
            kcross_table=kcross_table
        )
        pipeline_context["dterms_cal_table"] = dterms_table

        # Update context with all polarization tables
        pol_cal_tables = [kcross_table, dterms_table]
        pipeline_context["pol_cal_tables"] = pol_cal_tables
        pipeline_context["polarization_calibrated"] = True

        task_logprint("Polarization calibration completed successfully")

    except Exception as e:
        task_logprint(f"ERROR in polarization calibration: {e}")
        QA2_polcal = "Fail"
        pipeline_context["polarization_calibrated"] = False
        pipeline_context["polarization_error"] = str(e)

    # Finalize
    task_logprint("Finished Polarization Calibration")

    # Import colored output function
    from evla_pipe.utils import format_qa_status
    task_logprint(f"QA2 score: {format_qa_status(QA2_polcal)}")

    time_list = runtiming("polcal", "end")

    # Update context and return
    pipeline_context["QA2_polcal"] = QA2_polcal
    pipeline_context["time_list"] = time_list

    return pipeline_context


def _build_prior_calibrations(pipeline_context: Dict[str, Any]) -> List[str]:
    """
    Build list of prior calibration tables from context.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing calibration table paths

    Returns
    -------
    list
        List of prior calibration table paths
    """
    priorcals = []

    # Add delay calibration table
    if "delay_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["delay_cal_table"])
        task_logprint(f"Using delay table: {pipeline_context['delay_cal_table']}")

    # Add bandpass calibration table
    if "bpass_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["bpass_cal_table"])
        task_logprint(f"Using bandpass table: {pipeline_context['bpass_cal_table']}")

    # Add gain calibration table
    if "gain_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["gain_cal_table"])
        task_logprint(f"Using gain table: {pipeline_context['gain_cal_table']}")
    elif "phase_int_cal_table" in pipeline_context:
        priorcals.append(pipeline_context["phase_int_cal_table"])
        task_logprint(f"Using phase table: {pipeline_context['phase_int_cal_table']}")

    return priorcals


def _get_polarization_calibrators(
    pipeline_context: Dict[str, Any]
) -> tuple[Optional[int], Optional[int]]:
    """
    Get or auto-detect polarization calibrator field IDs.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing field information

    Returns
    -------
    tuple
        (pol_angle_field, pol_leakage_field) - Field IDs for calibrators
    """
    pol_angle_field = pipeline_context.get("pol_angle_field")
    pol_leakage_field = pipeline_context.get("pol_leakage_field")

    # If already specified, return them
    if pol_angle_field is not None and pol_leakage_field is not None:
        task_logprint(f"Using specified polarization calibrators: angle={pol_angle_field}, leakage={pol_leakage_field}")
        return pol_angle_field, pol_leakage_field

    # Auto-detect from standard calibrators
    standard_source_names = pipeline_context.get("standard_source_names", ["3C48", "3C138", "3C147", "3C286"])
    field_names = pipeline_context.get("field_names", [])

    pol_angle_field = None
    pol_leakage_field = None

    for i, field_name in enumerate(field_names):
        field_upper = field_name.upper()
        if any(std in field_upper for std in standard_source_names):
            # 3C286 and 3C138 are good for angle calibration
            if "3C286" in field_upper or "3C138" in field_upper:
                pol_angle_field = i
            # Any standard calibrator can be used for leakage
            if pol_leakage_field is None:
                pol_leakage_field = i

    task_logprint(f"Auto-detected polarization calibrators: angle={pol_angle_field}, leakage={pol_leakage_field}")

    return pol_angle_field, pol_leakage_field


def _perform_kcross_calibration(
    ms_active: str,
    pol_angle_field: int,
    refant: str,
    priorcals: List[str]
) -> str:
    """
    Perform cross-hand delay calibration (Xf).

    Parameters
    ----------
    ms_active : str
        Measurement set name
    pol_angle_field : int
        Field ID for polarization angle calibration
    refant : str
        Reference antenna
    priorcals : list
        List of prior calibration tables

    Returns
    -------
    str
        Path to cross-hand delay calibration table
    """
    task_logprint("Performing cross-hand delay calibration (Xf)")

    kcross_table = str(get_caltable_path(ms_active, "Xf"))

    gaincal(
        vis=ms_active,
        caltable=kcross_table,
        field=str(pol_angle_field),
        spw="",
        intent="",
        selectdata=True,
        uvrange="",
        scan="",
        solint="inf",
        combine="scan",
        preavg=-1.0,
        refant=refant,
        minblpercal=4,
        minsnr=3.0,
        solnorm=False,
        gaintype="KCROSS",
        smodel=[],
        calmode="p",
        append=False,
        docallib=False,
        gaintable=priorcals,
        gainfield=[],
        interp=[],
        spwmap=[],
        parang=True
    )

    task_logprint(f"Cross-hand delay calibration completed: {kcross_table}")
    return kcross_table


def _perform_dterms_calibration(
    ms_active: str,
    pol_leakage_field: int,
    priorcals: List[str],
    kcross_table: str
) -> str:
    """
    Perform D-term leakage calibration (Df).

    Parameters
    ----------
    ms_active : str
        Measurement set name
    pol_leakage_field : int
        Field ID for leakage calibration
    priorcals : list
        List of prior calibration tables
    kcross_table : str
        Path to cross-hand delay calibration table

    Returns
    -------
    str
        Path to D-term leakage calibration table
    """
    task_logprint("Performing D-term leakage calibration (Df)")

    dterms_table = str(get_caltable_path(ms_active, "Df"))

    # Create gaintable list including the new Xf table
    pol_gaintables = priorcals + [kcross_table]

    polcal(
        vis=ms_active,
        caltable=dterms_table,
        field=str(pol_leakage_field),
        spw="",
        intent="",
        selectdata=True,
        uvrange="",
        scan="",
        solint="inf",
        combine="scan,field",
        preavg=-1.0,
        refant="",
        minblpercal=4,
        minsnr=3.0,
        poltype="Df",
        smodel=[],
        append=False,
        docallib=False,
        gaintable=pol_gaintables,
        gainfield=[],
        interp=[],
        spwmap=[],
        parang=True
    )

    task_logprint(f"D-term leakage calibration completed: {dterms_table}")
    return dterms_table



@register_step("EVLA_pipe_polcal")
def EVLA_pipe_polcal(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for polcal() to match expected step name.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary

    Returns
    -------
    dict
        Updated pipeline context
    """
    return polcal(pipeline_context)
