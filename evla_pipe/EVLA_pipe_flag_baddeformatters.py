"""
Determine bad deformatters in the MS and flag them.  Looks for bandpass
solutions that have small ratio of min/max amplitudes.
"""

from casatasks import flagdata

from .utils import getBCalStatistics


def task_logprint(msg):
    logprint(msg, logfileout="logs/flag_baddeformatters.log")


task_logprint("Starting EVLA_pipe_flag_baddeformatters.py")
time_list = runtiming("flag_baddeformatters", "start")
QA2_flag_baddeformatters = "Pass"

# Set control parameters here
# Which quantity to test? ['amp','phase','real','imag']
testq = "amp"
# Which stat to use? ['min','max','mean','var'] or 'rat'=min/max or 'diff'=max-min
tstat = "rat"
# Print detailed flagging stats
doprintall = True
# Limit for test (flag values under/over this limit)
testlimit = 0.15
testunder = True
# Number of spw per baseband to trigger flagging entire baseband
nspwlimit = 4
# Flag individual spws when below nspwlimit
doflagundernspwlimit = True
# Flag data for spws with no unflagged channel solutions in any poln?
doflagemptyspws = False
# Actually flag the data based on the derived flags (or just report)?
may_15_2012 = 56062.7
if startdate <= may_15_2012:
    doflagdata = False
else:
    doflagdata = True
# Define the table to run this on
calBPtablename = "testBPcal.b"
# Define the REASON given for the flags
flagreason = "bad_deformatters_amp or RFI"


task_logprint(f"Will test on quantity: {testq}")

task_logprint(f"Will test using statistic: {tstat}")

if testunder:
    task_logprint(f"Will flag values under limit = {testlimit}")
else:
    task_logprint(f"Will flag values over limit = {testlimit}")

task_logprint(f"Will identify basebands with more than {nspwlimit} bad spw")

if doflagundernspwlimit:
    task_logprint(f"Will identify individual spw when less than {nspwlimit} bad spw")

if doflagemptyspws:
    task_logprint("Will identify spw with no unflagged channels")

task_logprint(f"Will use flag REASON = {flagreason}")

if doflagdata:
    task_logprint("Will flag data based on what we found")
else:
    task_logprint("Will NOT flag data based on what we found")


calBPstatresult = getBCalStatistics(calBPtablename)
flaglist = []
extflaglist = []
for iant in calBPstatresult["antband"].keys():
    antName = calBPstatresult["antDict"][iant]
    badspwlist = []
    flaggedspwlist = []
    for rrx in calBPstatresult["antband"][iant].keys():
        for bband in calBPstatresult["antband"][iant][rrx].keys():
            # List of spw in this baseband
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
                            # Get stats of this ant/spw/poln
                            inner_stats = calBPstatresult["antspw"][iant][ispw][poln]["inner"]
                            nbp = inner_stats["number"]
                            if nbp > 0:
                                if tstat == "rat":
                                    bpmax = inner_stats[testq]["max"]
                                    bpmin = inner_stats[testq]["min"]
                                    if bpmax == 0.0:
                                        tval = 0.0
                                    else:
                                        tval = bpmin / bpmax
                                elif tstat == "diff":
                                    bpmax = inner_stats[testq]["max"]
                                    bpmin = inner_stats[testq]["min"]
                                    tval = bpmax - bpmin
                                else:
                                    # simple test on quantity
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
                        # Test on extrema of the polarizations for this ant/spw
                        if not testvalid:
                            # these have no unflagged channels in any poln
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
                        # this spw is missing from this antenna/rx
                        if doprintall:
                            task_logprint(f"  Ant {iant} ({antName}) {rrx} {bband} spw={ispw} missing solution")
            # Test to see if this baseband should be entirely flagged
            if nbadspws > 0 and nbadspws >= nspwlimit:
                # Flag all spw in this baseband
                bbspws = calBPstatresult["rxBasebandDict"][rrx][bband]
                badspwlist.extend(bbspws)
                task_logprint(f"Ant {iant} ({antName}) {rrx} {bband} bad baseband spws={bbspws}")
            elif nbadspws > 0 and doflagundernspwlimit:
                # Flag spws individually
                badspwlist.extend(badspws)
                task_logprint(f"Ant {iant} ({antName}) {rrx} {bband} bad spws={badspws}\n")
            if len(flaggedspws) > 0:
                # These spws have no unflagged channels in any pol
                flaggedspwlist.extend(flaggedspws)
                task_logprint(f"Ant {iant} ({antNAme}) {rrx} {bband} no unflagged solutions spws={flaggedspws}")
    if len(badspwlist) > 0:
        spwstr = ""
        for ispw in badspwlist:
            if spwstr == "":
                spwstr = str(ispw)
            else:
                spwstr += "," + str(ispw)
        reastr = flagreason
        # Add entry for this antenna
        # flagstr = "mode='manual' antenna='"+str(iant)+"' spw='"+spwstr+"' reason='"+reastr+"'"
        # Use name for flagging
        flagstr = f"mode='manual' antenna='{antName}' spw='{spwstr}'"
        flaglist.append(flagstr)
    if doflagemptyspws and len(flaggedspwlist) > 0:
        spwstr = ""
        for ispw in flaggedspwlist:
            if spwstr == "":
                spwstr = str(ispw)
            else:
                spwstr += "," + str(ispw)
        # Add entry for this antenna
        reastr = "no_unflagged_solutions"
        # Use name for flagging
        flagstr = f"mode='manual' antenna='{antName}' spw='{spwstr}'"
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
        # Now flag with flaglist
        flagdata(
            vis=ms_active,
            mode="list",
            inpfile=flaglist,
            action="apply",
            flagbackup=True,
            savepars=True,
        )

# Until we know what the QA criteria are for this script, leave QA2
# set score to "Pass".

logprint(f"QA2 score: {QA2_flag_baddeformatters}")
logprint("Finished EVLA_pipe_flag_baddeformatters.py")
time_list = runtiming("flag_baddeformatters", "end")

pipeline_save()
