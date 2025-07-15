# EVLA_pipe_flag_baddeformatters.py (Refactored)

from casatasks import flagdata
from evla_pipe.utils import logprint, runtiming, getBCalStatistics, format_qa_status

def task_logprint(msg):
    logprint(msg, logfileout="logs/flag_baddeformatters.log")

def flag_bad_deformatters(pipeline_context):
    """
    Determine bad deformatters in the MS and flag them.
    Looks for bandpass solutions with small ratio of min/max amplitudes.

    Args:
        pipeline_context (dict): Dictionary containing pipeline parameters.
    """
    task_logprint("*** Starting EVLA_pipe_flag_baddeformatters.py (Refactored) ***")
    time_list = runtiming("flag_baddeformatters", "start")
    QA2_flag_baddeformatters = "Pass"

    ms_active = pipeline_context.get("msname")
    startdate = pipeline_context.get("startdate", 0.0)

    def flag_on_deformatters(
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
        ):
        assert testq in ("amp", "phase", "real", "imag")
        assert tstat in ("amp", "phase", "real", "imag", "rat", "diff")
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
        may_15_2012 = 56062.7
        doflagdata = startdate > may_15_2012
        if doflagdata:
            task_logprint("Will flag data based on what we found")
        else:
            task_logprint("Will NOT flag data based on what we found (just report)")
        calBPstatresult = getBCalStatistics(calBPtablename)
        flaglist = []
        extflaglist = []
        for iant in calBPstatresult["antband"].keys():
            antName = calBPstatresult["antDict"][iant]
            badspwlist = []
            flaggedspwlist = []
            for rrx in calBPstatresult["antband"][iant].keys():
                for bband in calBPstatresult["antband"][iant][rrx].keys():
                    spwl = calBPstatresult["rxBasebandDict"][rrx][bband]
                    nbadspws = 0
                    badspws = []
                    flaggedspws = []
                    if len(spwl) > 0:
                        if doprintall:
                            task_logprint(f" Ant {iant} ({antName}) {rrx} {bband} processing spws={spwl}")
                        for ispw in spwl:
                            testvalid = False
                            if ispw in calBPstatresult["antspw"][iant]:
                                for poln in calBPstatresult["antspw"][iant][ispw].keys():
                                    inner_stats = calBPstatresult["antspw"][iant][ispw][poln]["inner"]
                                    nbp = inner_stats["number"]
                                    if nbp > 0:
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
                                break # Only need to test one polarization
                            if not testvalid:
                                flaggedspws.append(ispw)
                            else:
                                if (testunder and testval < testlimit) or (
                                    not testunder and testval > testlimit
                                ):
                                    nbadspws += 1
                                    badspws.append(ispw)
                                    if doprintall:
                                        task_logprint(f"  Found Ant {iant} ({antName}) {rrx} {bband} spw={ispw} {testq} {tstat}={testval:6.4f}")
                        else:
                            if doprintall:
                                task_logprint(f"  Ant {iant} ({antName}) {rrx} {bband} spw={ispw} missing solution")
                    if nbadspws > 0 and nbadspws >= nspwlimit:
                        bbspws = calBPstatresult["rxBasebandDict"][rrx][bband]
                        badspwlist.extend(bbspws)
                        task_logprint(f"Ant {iant} ({antName}) {rrx} {bband} bad baseband spws={bbspws}")
                    elif nbadspws > 0 and doflagundernspwlimit:
                        badspwlist.extend(badspws)
                        task_logprint(f"Ant {iant} ({antName}) {rrx} {bband} bad spws={badspws}\n")
                    if len(flaggedspws) > 0 and doflagemptyspws:
                        flaggedspwlist.extend(flaggedspws)
                        task_logprint(f"Ant {iant} ({antName}) {rrx} {bband} no unflagged solutions spws={flaggedspws}")
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
        nflagcmds = len(flaglist) + len(extflaglist)
        if nflagcmds < 1:
            task_logprint("No bad basebands/spws found")
        else:
            task_logprint("Possible bad basebands/spws found:")
            for flagstr in flaglist:
                task_logprint("   " + flagstr)
            if len(extflaglist) > 0:
                task_logprint("   ")
                for flagstr in extflaglist:
                    task_logprint("   " + flagstr)
                flaglist.extend(extflaglist)
            if doflagdata:
                logprint("Flagging these in the ms:")
                flagdata(
                    vis=ms_active,
                    mode="list",
                    inpfile=flaglist,
                    action="apply",
                    flagbackup=True,
                    savepars=True,
                )
            else:
                logprint("NOT flagging these in the ms (startdate <= May 15, 2012)")
        return None

    task_logprint("Flag based on amplitudes.")
    flag_on_deformatters(
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

    task_logprint("Flag based on phase.")
    flag_on_deformatters(
        testq="phase",
        tstat="diff",
        doprintall=True,
        testlimit=50,
        testunder=False,
        nspwlimit=4,
        doflagundernspwlimit=True,
        doflagemptyspws=False,
        calBPtablename="testBPcal.b",
        flagreason="bad_deformatters_phase or RFI",
    )

    task_logprint(f"QA2 score: {format_qa_status(QA2_flag_baddeformatters)}")
    time_list = runtiming("flag_baddeformatters", "end")

    return None

def EVLA_pipe_flag_baddeformatters(pipeline_context):
    """
    Main entry point for EVLA_pipe_flag_baddeformatters pipeline step.
    
    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary containing configuration and state
        
    Returns
    -------
    dict
        Updated pipeline context
    """
    task_logprint("*** Starting EVLA_pipe_flag_baddeformatters.py ***")
    time_list = runtiming("flag_baddeformatters", "start")
    
    try:
        flag_bad_deformatters(pipeline_context)
        QA2_score = "Pass"
    except Exception as e:
        task_logprint(f"Error in EVLA_pipe_flag_baddeformatters: {e}")
        QA2_score = "Fail"
    
    task_logprint(f"Finished EVLA_pipe_flag_baddeformatters.py")
    task_logprint(f"QA2 score: {format_qa_status(QA2_score)}")
    time_list = runtiming("flag_baddeformatters", "end")
    
    pipeline_context["QA2_flag_baddeformatters"] = QA2_score
    pipeline_context["time_list"] = time_list
    
    return pipeline_context
