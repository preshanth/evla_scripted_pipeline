# evaluate_gain_flags.py

from casatasks import rmtables
from casatools import table
from evla_pipe.utils import (logprint, runtiming, getCalFlaggedSoln)

tb = table()

def task_logprint(msg):
    logprint(msg, logfileout="logs/testgains_qa.log")

def evaluate_test_gain_flags():
    """
    Evaluate the fraction of flagged solutions in testgaincal.g
    and determine the QA2 score.

    Returns:
        str: The QA2 score for the test gains.
    """
    task_logprint("*** Starting evaluate_test_gain_flags.py ***")
    runtiming("testgains_qa", "start")
    QA2_testgains = "Pass"

    flaggedGainSolns = getCalFlaggedSoln("testgaincal.g")

    if flaggedGainSolns["all"]["total"] == 0:
        QA2_testgains = "Fail"
    elif flaggedGainSolns["antmedian"]["fraction"] > 0.1:
        QA2_testgains = "Partial"

    task_logprint(f"QA2 score: {QA2_testgains}")
    runtiming("testgains_qa", "end")

    return QA2_testgains