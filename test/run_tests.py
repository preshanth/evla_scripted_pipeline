#!/usr/bin/env python3

import os
import re
import warnings
from glob import glob

import pytest
import numpy as np

with warnings.catch_warnings() as w:
    # NOTE Ignore deprecation warning in `casatools/__cerberus__/schema.py` on
    # importing the ABCs from 'collections' instead of 'collections.abc'.
    warnings.simplefilter("ignore", category=DeprecationWarning)
    from casatools import table
    tb = table()


SDM_NAME = "test.sdm"
INITIAL_CAL_TABLES = [
        "BPcal.b",
        "BPinitialgain.g",
        "delay.k",
        "finalBPinitialgain.g",
        "finaldelayinitialgain.g",
        "fluxgaincalFcal.g",
        "fluxphaseshortgaincal.g",
        "phaseshortgaincal.g",
        "semiFinaldelayinitialgain.g",
        "testBPcal.b",
        "testBPdinitialgain.g",
        "testdelayinitialgain.g",
        "testdelay.k",
        "testgaincal.g",
]
FINAL_CAL_TABLES_DIR = "final_caltables"
FINAL_CAL_TABLES = [
        "antposcal.p",
        "averagephasegain.g",
        "finalampgaincal.g",
        "finalBPcal.b",
        "finaldelay.k",
        "finalphasegaincal.g",
        "fluxgaincal.g",
        "gain_curves.g",
        "opacities.g",
        "requantizergains.g",
        "switched_power.g",
]


def test_tables_exist():
    # FIXME change to `pathlib` in Python 3
    for filen in INITIAL_CAL_TABLES:
        assert os.path.exists(filen)


def test_calibrators_ms_exists():
    # FIXME use format-string in Python 3
    assert os.path.exists(SDM_NAME)
    for ext in ("ms", "ms.flagversions", "fluxdensities"):
        assert os.path.exists("{0}.{1}".format(SDM_NAME, ext))


def test_qa2_summary():
    filen = "weblog/qa2.html"
    assert os.path.exists(filen)
    with open(filen, "r") as f:
        text = f.read()
    # Zeroes fraction
    m = re.search(r"Fraction of zeroes: ([\.\d]+)", text)
    f_zero = float(m.group(1))
    assert np.isclose(f_zero, 0.0008182762003)
    # Total fraction of on-source data flagged
    m = re.search(r"flagging of end channels\): ([\.\d]+)", text)
    f_onsource = float(m.group(1))
    assert np.isclose(f_onsource, 0.31816045306)
    # Final fraction of on-source data flagged
    m = re.search(r"Final fraction of on-source data flagged: ([\.\d]+)", text)
    f_onsource_flagged = float(m.group(1))
    assert np.isclose(f_onsource_flagged, 0.334411407163)
    # QA2 score
    m = re.search(f"Overall QA2 score: (Fail|Pass)", text)
    assert m.group(1) == "Fail"
    # No missing scans
    assert re.search(r"There are no missing scans", text) is not None
    # Solution intervals
    m = re.search(r"interval used for gain calibrator: ([\.\d]+)s/([\.\d]+)s", text)
    assert np.isclose(float(m.group(1)), 2.0)  # short
    assert np.isclose(float(m.group(2)), 254.519998544)  # long
    # Final delays
    m = re.search(r"Final delays \[abs\(max\.delay\) = ([\.\d]+) ns\]", text)
    assert np.isclose(float(m.group(1)), 3.75783443451)


def test_qa2_scores():
    filen = "weblog/QA2_scores.txt"
    assert os.path.exists(filen)
    with open(filen, "r") as f:
        text = f.read()
    lines = text.split("\n")
    assert sum("Pass" in l for l in lines) == 21
    assert sum("Fail" in l for l in lines) ==  2


def test_fluxboot():
    filen = "test.sdm.fluxdensities"
    assert os.path.exists(filen)
    with open(filen, "r") as f:
        text = f.read().strip()
    reference_values = [
        # spw,   freq,     fit,        err,     snr, nfit
        [0, 1.557e+09, 1.04541, 0.00765684, 136.533, 52],
        [1, 1.685e+09, 1.06848, 0.00699644, 152.717, 52],
        [2, 1.813e+09, 1.07251, 0.00764253, 140.335, 52],
        [3, 1.941e+09, 1.07328, 0.00945151, 113.556, 52],
        [4, 1.057e+09, 1.16963, 0.00564467, 207.209, 52],
        [5, 1.185e+09, 1.11052, 0.00598697, 185.490, 52],
        [6, 1.313e+09, 1.12102, 0.00582628, 192.408, 52],
        [7, 1.441e+09, 1.11251, 0.00621539, 178.993, 52],
    ]
    lines = text.split("\n")
    print(lines[5].split("\t"))
    comments = [l.split("\t")[3] for l in lines]
    flux_entries = [c for c in comments if c.startswith("Flux density for")]
    for entry, ref_vals in zip(flux_entries, reference_values):
        m = re.search(r".+SpW=(\d+) \(freq=([e\.\d]+) Hz\) is: ([\.\d]+) \+/- ([\.\d]+) \(SNR = ([\.\d]+), N = (\d+)\)")
        for i in range(6):
            ref_val  = float(ref_vals[i])
            test_val = float(m.group(i+1))
            assert np.isclose(test_val, ref_val)


class test_all_plots_made():
    assert len(glob("weblog/BPcal_amp*.png")) == 9
    assert len(glob("weblog/BPcal_phase*.png")) == 9
    assert len(glob("weblog/BPinitialgainphase*.png")) == 9
    assert len(glob("weblog/Tsys*.png")) == 9
    assert len(glob("weblog/delay*.png")) == 9
    assert len(glob("weblog/field*_amp_freq.png")) == 6
    assert len(glob("weblog/field*_amp_uvdist.png")) == 3
    assert len(glob("weblog/field*_phase_freq.png")) == 6
    assert len(glob("weblog/finalBPcal_amp*.png")) == 9
    assert len(glob("weblog/finalBPcal_phase*.png")) == 9
    assert len(glob("weblog/finalampfreqcal*.png")) == 9
    assert len(glob("weblog/finalamptimecal*.png")) == 9
    assert len(glob("weblog/finaldelay*.png")) == 9
    assert len(glob("weblog/finalphasegaincal*.png")) == 9
    assert len(glob("weblog/phaseshortgaincal*.png")) == 9
    assert len(glob("weblog/semifinalcalibratedcals*.png")) == 2
    assert len(glob("weblog/switched_power*.png")) == 9
    assert len(glob("weblog/testBPcal_amp*.png")) == 9
    assert len(glob("weblog/testBPcal_phase*.png")) == 9
    assert len(glob("weblog/testBPdinitialgainamp*.png")) == 9
    assert len(glob("weblog/testBPdinitialgainphase*.png")) == 9
    assert len(glob("weblog/testdelay*.png")) == 9
    assert len(glob("weblog/testgaincal_amp*.png")) == 9
    assert len(glob("weblog/testgaincal_phase*.png")) == 9
    assert os.path.exists("weblog/bootstrappedFluxDensities.png")
    assert os.path.exists("weblog/plotants.png")
    assert os.path.exists("weblog/plotantslog.png")
    assert os.path.exists("weblog/all_calibrators_phase_time.png")
    assert os.path.exists("weblog/all_calibrators_phase_time.png")
    assert os.path.exists("weblog/comments.txt")
    assert os.path.exists("weblog/el_vs_time.png")
    assert os.path.exists("weblog/test.sdm.ms.plotweather.png")
    assert os.path.exists("weblog/testcalibratedBPcal.png")


def test_final_amp():
    filen = "final_caltables/finalampgaincal.g"
    assert os.path.exists(filen)
    try:
        tb.open(filen)
        gain = tb.getcol("CPARAM")
    finally:
        tb.close()
    again = np.abs(gain)
    rtol = 5e-2
    assert np.isclose(np.median(again), 0.997727870, rtol=5e-2)
    assert np.isclose(np.std(again),    0.020725715, rtol=1.0)
    assert np.isclose(np.max(again),    1.080380085, rtol=1.0)
    assert np.isclose(np.min(again),    0.813663491, rtol=1.0)



