# EVLA_pipe_flag_baddeformatters.py
"""
Flag bad deformatters based on bandpass calibration statistics.

This module identifies and flags antennas/spws with poor bandpass solutions,
typically caused by bad deformatter boards or RFI.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

from casatasks import flagdata
from evla_pipe.utils import logprint, runtiming, getBCalStatistics, format_qa_status
from evla_pipe.pipeline_steps import register_step


def task_logprint(msg: str) -> None:
    """
    Centralized logging for bad deformatters flagging operations.

    Parameters
    ----------
    msg : str
        Message to log
    """
    logprint(msg, logfileout="logs/flag_baddeformatters.log")


def _flag_on_deformatters(
    pipeline_context: Dict[str, Any],
    testq: str = "amp",
    tstat: str = "rat",
    doprintall: bool = True,
    testlimit: float = 0.15,
    testunder: bool = True,
    nspwlimit: int = 4,
    doflagundernspwlimit: bool = True,
    doflagemptyspws: bool = False,
    calBPtablename: str = "testBPcal.b",
    flagreason: str = "bad_deformatters_amp or RFI",
) -> Dict[str, Any]:
    """
    Flag bad deformatters based on bandpass statistics.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing msname and startdate
    testq : str
        Quantity to test ('amp', 'phase', 'real', 'imag')
    tstat : str
        Statistic to use ('amp', 'phase', 'real', 'imag', 'rat', 'diff')
    doprintall : bool
        Print detailed information during processing
    testlimit : float
        Threshold for flagging
    testunder : bool
        Flag values under limit (True) or over limit (False)
    nspwlimit : int
        Number of bad spws to trigger baseband flagging
    doflagundernspwlimit : bool
        Flag individual spws when fewer than nspwlimit are bad
    doflagemptyspws : bool
        Flag spws with no unflagged channels
    calBPtablename : str
        Bandpass calibration table name
    flagreason : str
        Reason to record in flag commands

    Returns
    -------
    dict
        Updated pipeline context
    """
    assert testq in ("amp", "phase", "real", "imag"), f"Invalid testq: {testq}"
    assert tstat in ("amp", "phase", "real", "imag", "rat", "diff"), f"Invalid tstat: {tstat}"

    ms_active = pipeline_context.get("msname")
    startdate = pipeline_context.get("startdate", 0.0)

    task_logprint(f"Testing on quantity: {testq}")
    task_logprint(f"Using statistic: {tstat}")

    if testunder:
        task_logprint(f"Flagging values under limit = {testlimit}")
    else:
        task_logprint(f"Flagging values over limit = {testlimit}")

    task_logprint(f"Identifying basebands with more than {nspwlimit} bad spw")

    if doflagundernspwlimit:
        task_logprint(f"Identifying individual spw when less than {nspwlimit} bad spw")

    if doflagemptyspws:
        task_logprint("Identifying spw with no unflagged channels")

    task_logprint(f"Using flag REASON = {flagreason}")

    # Date threshold for actual flagging vs. reporting only
    may_15_2012 = 56062.7
    doflagdata = startdate > may_15_2012

    if doflagdata:
        task_logprint("Will flag data based on what we found")
    else:
        task_logprint("Will NOT flag data based on what we found (startdate <= May 15, 2012)")

    # Get bandpass calibration statistics
    try:
        calBPstatresult = getBCalStatistics(calBPtablename)
    except Exception as e:
        task_logprint(f"Error getting bandpass statistics: {e}")
        pipeline_context["QA2_flag_baddeformatters"] = "Fail"
        pipeline_context["error_message"] = f"Failed to get BP statistics: {str(e)}"
        return pipeline_context

    flaglist: List[str] = []
    extflaglist: List[str] = []

    # Iterate over antennas and analyze bandpass solutions
    for iant in calBPstatresult["antband"].keys():
        antName = calBPstatresult["antDict"][iant]
        badspwlist: List[int] = []
        flaggedspwlist: List[int] = []

        # Iterate over receivers and basebands
        for rrx in calBPstatresult["antband"][iant].keys():
            for bband in calBPstatresult["antband"][iant][rrx].keys():
                spwl = calBPstatresult["rxBasebandDict"][rrx][bband]
                nbadspws = 0
                badspws: List[int] = []
                flaggedspws: List[int] = []

                if len(spwl) > 0:
                    if doprintall:
                        task_logprint(
                            f" Ant {iant} ({antName}) {rrx} {bband} processing spws={spwl}"
                        )

                    # Check each spectral window
                    for ispw in spwl:
                        testvalid = False

                        if ispw in calBPstatresult["antspw"][iant]:
                            # Get statistics for this spw
                            for poln in calBPstatresult["antspw"][iant][ispw].keys():
                                inner_stats = calBPstatresult["antspw"][iant][ispw][poln]["inner"]
                                nbp = inner_stats["number"]

                                if nbp > 0:
                                    # Compute test statistic
                                    if tstat == "rat":
                                        bpmax = inner_stats[testq]["max"]
                                        bpmin = inner_stats[testq]["min"]
                                        tval = bpmin / bpmax if bpmax != 0.0 else 0.0
                                    elif tstat == "diff":
                                        bpmax = inner_stats[testq]["max"]
                                        bpmin = inner_stats[testq]["min"]
                                        tval = bpmax - bpmin
                                    else:
                                        tval = inner_stats[testq][tstat]

                                    if not testvalid:
                                        testval = tval
                                        testvalid = True
                                    elif testunder:
                                        if tval < testval:
                                            testval = tval
                                    else:
                                        if tval > testval:
                                            testval = tval

                                break  # Only need to test one polarization

                        # Classify spw based on test results
                        if not testvalid:
                            flaggedspws.append(ispw)
                        else:
                            if (testunder and testval < testlimit) or (
                                not testunder and testval > testlimit
                            ):
                                nbadspws += 1
                                badspws.append(ispw)
                                if doprintall:
                                    task_logprint(
                                        f"  Found Ant {iant} ({antName}) {rrx} {bband} "
                                        f"spw={ispw} {testq} {tstat}={testval:6.4f}"
                                    )

                    if doprintall and len(flaggedspws) > 0:
                        for ispw in flaggedspws:
                            task_logprint(
                                f"  Ant {iant} ({antName}) {rrx} {bband} "
                                f"spw={ispw} missing solution"
                            )

                # Decide whether to flag entire baseband or individual spws
                if nbadspws > 0 and nbadspws >= nspwlimit:
                    bbspws = calBPstatresult["rxBasebandDict"][rrx][bband]
                    badspwlist.extend(bbspws)
                    task_logprint(
                        f"Ant {iant} ({antName}) {rrx} {bband} bad baseband spws={bbspws}"
                    )
                elif nbadspws > 0 and doflagundernspwlimit:
                    badspwlist.extend(badspws)
                    task_logprint(
                        f"Ant {iant} ({antName}) {rrx} {bband} bad spws={badspws}"
                    )

                if len(flaggedspws) > 0 and doflagemptyspws:
                    flaggedspwlist.extend(flaggedspws)
                    task_logprint(
                        f"Ant {iant} ({antName}) {rrx} {bband} "
                        f"no unflagged solutions spws={flaggedspws}"
                    )

        # Build flag commands for this antenna
        if len(badspwlist) > 0:
            spwstr = ",".join(str(ispw) for ispw in badspwlist)
            reastr = flagreason
            flagstr = f"mode='manual' antenna='{antName}' spw='{spwstr}' reason='{reastr}'"
            flaglist.append(flagstr)

        if doflagemptyspws and len(flaggedspwlist) > 0:
            spwstr = ",".join(str(ispw) for ispw in flaggedspwlist)
            reastr = "no_unflagged_solutions"
            flagstr = f"mode='manual' antenna='{antName}' spw='{spwstr}' reason='{reastr}'"
            extflaglist.append(flagstr)

    # Apply flags if any were found
    nflagcmds = len(flaglist) + len(extflaglist)

    if nflagcmds < 1:
        task_logprint("No bad basebands/spws found")
    else:
        task_logprint("Possible bad basebands/spws found:")
        for flagstr in flaglist:
            task_logprint("   " + flagstr)

        if len(extflaglist) > 0:
            task_logprint("")
            for flagstr in extflaglist:
                task_logprint("   " + flagstr)
            flaglist.extend(extflaglist)

        if doflagdata:
            task_logprint("Flagging these in the ms")
            try:
                flagdata(
                    vis=ms_active,
                    mode="list",
                    inpfile=flaglist,
                    action="apply",
                    flagbackup=True,
                    savepars=True,
                )
                # Store flag commands in context for record keeping
                if "flag_commands" not in pipeline_context:
                    pipeline_context["flag_commands"] = []
                pipeline_context["flag_commands"].extend(flaglist)

            except Exception as e:
                task_logprint(f"Error applying flags: {e}")
                pipeline_context["QA2_flag_baddeformatters"] = "Fail"
                pipeline_context["error_message"] = f"Failed to apply flags: {str(e)}"
                return pipeline_context
        else:
            task_logprint("NOT flagging these in the ms (startdate <= May 15, 2012)")

    return pipeline_context


def flag_bad_deformatters(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flag bad deformatters based on bandpass calibration statistics.

    This function analyzes bandpass calibration solutions to identify antennas
    and spectral windows with poor performance, typically caused by bad
    deformatter boards or RFI. It flags based on both amplitude and phase
    characteristics.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context containing:
        - msname : str
            Name of measurement set
        - startdate : float
            Modified Julian Date of observation start
        - Other metadata from previous steps

    Returns
    -------
    dict
        Updated pipeline context with:
        - QA2_flag_baddeformatters : str
            QA status ('Pass' or 'Fail')
        - flag_commands : list
            List of flag commands applied (if any)
        - error_message : str
            Error message if QA failed (optional)

    Notes
    -----
    This function performs two flagging passes:
    1. Amplitude-based: Flags basebands/spws with amplitude ratio < 0.15
    2. Phase-based: Flags basebands/spws with phase difference > 50 degrees

    For observations after May 15, 2012, flags are actually applied.
    For earlier observations, flags are only reported but not applied.

    Sets QA2_flag_baddeformatters flag based on success/failure.
    """
    task_logprint("*** Starting EVLA_pipe_flag_baddeformatters ***")
    time_list = runtiming("flag_baddeformatters", "start")
    QA2_score = "Pass"

    try:
        # Flag based on amplitudes
        task_logprint("=" * 60)
        task_logprint("Flagging based on amplitude statistics")
        task_logprint("=" * 60)

        pipeline_context = _flag_on_deformatters(
            pipeline_context,
            testq="amp",
            tstat="rat",
            doprintall=True,
            testlimit=0.15,
            testunder=True,
            nspwlimit=4,
            doflagundernspwlimit=True,
            doflagemptyspws=False,
            calBPtablename="testBPcal.b",
            flagreason="bad_deformatters_amp or RFI",
        )

        # Check if amplitude flagging failed
        if pipeline_context.get("QA2_flag_baddeformatters") == "Fail":
            QA2_score = "Fail"
            task_logprint("Amplitude flagging failed")

        # Flag based on phase (only if amplitude flagging succeeded)
        if QA2_score == "Pass":
            task_logprint("")
            task_logprint("=" * 60)
            task_logprint("Flagging based on phase statistics")
            task_logprint("=" * 60)

            pipeline_context = _flag_on_deformatters(
                pipeline_context,
                testq="phase",
                tstat="diff",
                doprintall=True,
                testlimit=50.0,
                testunder=False,
                nspwlimit=4,
                doflagundernspwlimit=True,
                doflagemptyspws=False,
                calBPtablename="testBPcal.b",
                flagreason="bad_deformatters_phase or RFI",
            )

            # Check if phase flagging failed
            if pipeline_context.get("QA2_flag_baddeformatters") == "Fail":
                QA2_score = "Fail"
                task_logprint("Phase flagging failed")

    except Exception as e:
        task_logprint(f"Error in flag_bad_deformatters: {e}")
        QA2_score = "Fail"
        pipeline_context["error_message"] = str(e)

    # Set final QA score
    pipeline_context["QA2_flag_baddeformatters"] = QA2_score

    task_logprint("")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    task_logprint("*** Finished EVLA_pipe_flag_baddeformatters ***")

    time_list = runtiming("flag_baddeformatters", "end")
    pipeline_context["time_list"] = time_list

    return pipeline_context


# Main entry point for backward compatibility
@register_step("EVLA_pipe_flag_baddeformatters")
def EVLA_pipe_flag_baddeformatters(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for EVLA_pipe_flag_baddeformatters pipeline step.

    This is the primary function called by the pipeline executor.
    It wraps flag_bad_deformatters() for consistent naming conventions.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state

    Returns
    -------
    dict
        Updated pipeline context with QA scores and flag information

    See Also
    --------
    flag_bad_deformatters : Core implementation function
    """
    return flag_bad_deformatters(pipeline_context)
