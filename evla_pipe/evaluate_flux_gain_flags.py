# evaluate_flux_gain_flags.py

from evla_pipe.utils import (
        runtiming,
        logprint,
        getCalFlaggedSoln,
)

def task_logprint(msg):
    logprint(msg, logfileout="logs/fluxgains_qa.log")

def evaluate_flux_gain_flags():
    """
    Evaluate the fraction of flagged solutions in fluxgaincal.g
    and determine the QA2 score.

    Returns:
        str: The QA2 score for the flux gains.
    """
    task_logprint("*** Starting evaluate_flux_gain_flags.py ***")
    runtiming("fluxgains_qa", "start")
    QA2_fluxgains = "Pass"

    flaggedGainSolns = getCalFlaggedSoln("fluxgaincal.g")

    if flaggedGainSolns["all"]["total"] == 0:
        QA2_fluxgains = "Fail"
    elif flaggedGainSolns["antmedian"]["fraction"] > 0.2:
        QA2_fluxgains = "Partial"

    task_logprint(f"QA2 score: {QA2_fluxgains}")
    runtiming("fluxgains_qa", "end")

    return QA2_fluxgains