"""
End-to-end pipeline validation test.

Runs the full EVLA continuum pipeline once against a real ASDM and checks
calibration outputs against recorded reference values.

Requirements
------------
- CASA installed (casatasks/casatools)
- EVLA_TEST_SDM set to the ASDM path, e.g.:
    EVLA_TEST_SDM=data/TDRW0001.sb35624494.eb35628826.58395.23719237269 \\
    pixi run -e casa pytest test/test_run_e2e.py -v

Reference values
----------------
The REF_* constants below were recorded from a reference pipeline run on
dataset TDRW0001 (L-band, 10 spws, 27 antennas, 2018-09-27).
They define the expected scientific output of a correct calibration.
If your pipeline run matches these values within tolerance, the calibration
is scientifically consistent with the reference.

To update reference values after a pipeline change that is expected to shift
them: run with --update-ref (not yet implemented — edit this file directly
and document the reason in a comment).
"""

from pathlib import Path

import numpy as np
import pytest

from conftest import SDM_NAME

pytest.importorskip("casatasks", reason="CASA not installed")

pytestmark = pytest.mark.skipif(
    not Path(SDM_NAME).exists(),
    reason=f"ASDM '{SDM_NAME}' not found — set EVLA_TEST_SDM",
)

# ---------------------------------------------------------------------------
# Reference values — recorded from reference run on TDRW0001
# Set to None until first pipeline run populates them.
# ---------------------------------------------------------------------------

# Observation geometry — TDRW0001 (L-band, 10 spws, 27 antennas, 2018-09-27)
REF_NUM_ANTENNA = 27
REF_NUM_SPWS = 10
REF_CORRSTRING = "RR,LL"
REF_BAND = None               # str  e.g. "L" — not yet extracted from ctx

# Solution intervals determined by run_solint (strings, not floats)
# gain_solint1 = integration time; gain_solint2 = max scan duration × 1.01
REF_GAIN_SOLINT1 = None       # str  e.g. "2.02s" — populate after reference run
REF_GAIN_SOLINT2 = None       # str  e.g. "123.45s" — populate after reference run

# Reference antenna chosen by heuristics
REF_REFANT = "ea28"

# Flag fractions (full MS, before and after applycal)
REF_FLAG_FRAC_BEFORE = 0.09504468669139465
REF_FLAG_FRAC_AFTER = 0.20229557172961837

# Flux bootstrapping: phase calibrator flux density at reference frequency
# Recorded from reference run on TDRW0001.
REF_FLUX_FITTING = [
    {
        "source": "J0259+0747",
        "spws": [2, 3, 4, 5, 6, 7, 8, 9],
        "flux_jy": 0.9295731726914271,
        "spix": 0.13053928442938615,
        "snr": 11.506182370413266,
        "reffreq_ghz": 2.5510000000000002,
    },
    {
        "source": "J2355+4950",
        "spws": [2, 3, 4, 5, 6, 7, 8, 9],
        "flux_jy": 0.3882893982028951,
        "spix": -0.5522832748055851,
        "snr": 6.594785614006618,
        "reffreq_ghz": 2.5510000000000002,
    },
]

# Final amplitude gain table statistics (median, std of |CPARAM|)
REF_FINAL_AMP_MEDIAN = 1.010039391
REF_FINAL_AMP_STD = 0.016190088

# Final BP table: fraction of flagged solutions across all antennas/spws
REF_FINAL_BP_FLAG_FRAC = 0.343026620

# QA2 stage verdicts — not yet implemented in stages; leave None until populated
REF_QA2 = None                # dict[str, str]  e.g. {"priorcals": "Pass", ...}


def _ref_set(val):
    """True if a reference value has been populated (is not None)."""
    return val is not None


# ---------------------------------------------------------------------------
# Session fixture — runs the full pipeline exactly once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pipeline_ctx(pipeline_workdir, sdm_name):
    """Run the full continuum pipeline and return the final context."""
    from evla_pipe.pipeline import continuum

    ctx = continuum(
        sdm_name=sdm_name,
        workdir=str(pipeline_workdir),
        enable_plots=False,   # skip plots for speed; add True for full run
        verbose=True,
    )
    return ctx


# ---------------------------------------------------------------------------
# Observation metadata
# ---------------------------------------------------------------------------


def test_num_antenna(pipeline_ctx):
    assert pipeline_ctx["numAntenna"] > 0
    if _ref_set(REF_NUM_ANTENNA):
        assert pipeline_ctx["numAntenna"] == REF_NUM_ANTENNA


def test_num_spws(pipeline_ctx):
    assert pipeline_ctx["numSpws"] > 0
    if _ref_set(REF_NUM_SPWS):
        assert pipeline_ctx["numSpws"] == REF_NUM_SPWS


def test_corrstring(pipeline_ctx):
    assert pipeline_ctx["corrstring"] in ("RR,LL", "XX,YY", "RR,RL,LR,LL", "XX,XY,YX,YY")
    if _ref_set(REF_CORRSTRING):
        assert pipeline_ctx["corrstring"] == REF_CORRSTRING


# ---------------------------------------------------------------------------
# Calibration infrastructure
# ---------------------------------------------------------------------------


def test_solint(pipeline_ctx):
    # run_solint writes gain_solint1 (integration time) and gain_solint2
    # (max scan duration × 1.01) as strings e.g. "2.02s". Not a float.
    solint1 = pipeline_ctx.get("gain_solint1", "")
    solint2 = pipeline_ctx.get("gain_solint2", "")
    assert solint1.endswith("s"), f"gain_solint1 missing or malformed: {solint1!r}"
    assert solint2.endswith("s"), f"gain_solint2 missing or malformed: {solint2!r}"
    if _ref_set(REF_GAIN_SOLINT1):
        assert solint1 == REF_GAIN_SOLINT1
    if _ref_set(REF_GAIN_SOLINT2):
        assert solint2 == REF_GAIN_SOLINT2


def test_refant_set(pipeline_ctx):
    assert pipeline_ctx.get("refAnt", "") != ""
    if _ref_set(REF_REFANT):
        assert pipeline_ctx["refAnt"] == REF_REFANT


def test_all_final_caltables_exist(pipeline_ctx):
    for tbl in pipeline_ctx["final_caltables"]:
        assert Path(tbl).exists(), f"Missing final caltable: {tbl}"


def test_priorcals_all_exist(pipeline_ctx):
    for tbl in pipeline_ctx["priorcals"]:
        assert Path(tbl).exists(), f"Missing priorcal: {tbl}"


# ---------------------------------------------------------------------------
# Flag fractions
# ---------------------------------------------------------------------------


def test_flag_frac_increases_after_applycal(pipeline_ctx):
    """Flag fraction should be >= before applycal (calflagstrict can add flags)."""
    before = pipeline_ctx.get("flag_frac_before_applycal", 0.0)
    after = pipeline_ctx.get("flag_frac_after_applycal", 0.0)
    assert after >= before - 0.01   # allow tiny float noise


def test_flag_frac_before_applycal(pipeline_ctx):
    if _ref_set(REF_FLAG_FRAC_BEFORE):
        frac = pipeline_ctx.get("flag_frac_before_applycal", 0.0)
        assert np.isclose(frac, REF_FLAG_FRAC_BEFORE, atol=0.02)


def test_flag_frac_after_applycal(pipeline_ctx):
    if _ref_set(REF_FLAG_FRAC_AFTER):
        frac = pipeline_ctx.get("flag_frac_after_applycal", 0.0)
        assert np.isclose(frac, REF_FLAG_FRAC_AFTER, atol=0.02)


# ---------------------------------------------------------------------------
# Flux bootstrapping
# ---------------------------------------------------------------------------


def test_flux_fitting_results_populated(pipeline_ctx):
    results = pipeline_ctx.get("flux_fitting_results", [])
    assert len(results) > 0, "No flux fitting results — fluxboot may have failed"


def test_flux_fitting_results_reasonable(pipeline_ctx):
    """All bootstrapped sources should have positive flux and finite spectral index."""
    for r in pipeline_ctx.get("flux_fitting_results", []):
        assert r["flux_jy"] > 0, f"Negative flux for {r['source']}"
        assert abs(r["spix"]) < 5.0, f"|spix| > 5 for {r['source']} — unreliable fit"
        assert r["snr"] > 0


def test_flux_fitting_reference(pipeline_ctx):
    if not _ref_set(REF_FLUX_FITTING):
        pytest.skip("REF_FLUX_FITTING not yet populated")
    results = {r["source"]: r for r in pipeline_ctx.get("flux_fitting_results", [])}
    for ref in REF_FLUX_FITTING:
        src = ref["source"]
        assert src in results, f"Source {src} not in flux fitting results"
        assert np.isclose(results[src]["flux_jy"], ref["flux_jy"], rtol=0.05)
        assert np.isclose(results[src]["spix"], ref["spix"], atol=0.3)


# ---------------------------------------------------------------------------
# Calibration table values (read with casatools.table)
# ---------------------------------------------------------------------------


def test_final_amp_gain_statistics(pipeline_ctx):
    """Median and std of |CPARAM| in final amp gaincal table."""
    from casatools import table as CasaTable

    tbl_path = pipeline_ctx.get("table_final_amp_gain", "")
    if not tbl_path or not Path(tbl_path).exists():
        pytest.skip("table_final_amp_gain not found")

    tb = CasaTable()
    try:
        tb.open(tbl_path)
        cparam = tb.getcol("CPARAM")
        flag = tb.getcol("FLAG")
    finally:
        tb.close()

    amp = np.abs(cparam[~flag])
    median_amp = float(np.median(amp))
    std_amp = float(np.std(amp))

    assert 0.5 < median_amp < 2.0, f"Unexpected median amp gain: {median_amp:.4f}"
    assert std_amp < 0.5, f"Unexpectedly large amp gain scatter: {std_amp:.4f}"

    if _ref_set(REF_FINAL_AMP_MEDIAN):
        assert np.isclose(median_amp, REF_FINAL_AMP_MEDIAN, rtol=0.05)
    if _ref_set(REF_FINAL_AMP_STD):
        assert np.isclose(std_amp, REF_FINAL_AMP_STD, rtol=0.5)


def test_final_bp_flag_fraction(pipeline_ctx):
    """Flagged solution fraction in final BP table should be reasonable."""
    from casatools import table as CasaTable

    tbl_path = pipeline_ctx.get("table_final_bp", "")
    if not tbl_path or not Path(tbl_path).exists():
        pytest.skip("table_final_bp not found")

    tb = CasaTable()
    try:
        tb.open(tbl_path)
        flag = tb.getcol("FLAG")
    finally:
        tb.close()

    flag_frac = float(np.mean(flag))
    assert flag_frac < 0.5, f"More than 50% of BP solutions flagged: {flag_frac:.3f}"

    if _ref_set(REF_FINAL_BP_FLAG_FRAC):
        assert np.isclose(flag_frac, REF_FINAL_BP_FLAG_FRAC, atol=0.05)


# ---------------------------------------------------------------------------
# QA2 scores
# ---------------------------------------------------------------------------


def test_qa2_scores_present(pipeline_ctx):
    """At least the core stages should have QA2 results."""
    core_keys = [
        "QA2_priorcals", "QA2_testBPdcals", "QA2_semiFinal",
        "QA2_finalcals", "QA2_applycals",
    ]
    for key in core_keys:
        assert key in pipeline_ctx, f"Missing QA2 key: {key}"
        assert pipeline_ctx[key].overall in ("Pass", "Partial", "Fail")


def test_qa2_reference(pipeline_ctx):
    if not _ref_set(REF_QA2):
        pytest.skip("REF_QA2 not yet populated")
    qa_key_map = {
        "priorcals": "QA2_priorcals",
        "testBPdcals": "QA2_testBPdcals",
        "semiFinal": "QA2_semiFinal",
        "solint": "QA2_solint",
        "testgains": "QA2_testgains",
        "fluxgains": "QA2_fluxgains",
        "fluxboot": "QA2_fluxboot",
        "finalcals": "QA2_finalcals",
        "applycals": "QA2_applycals",
    }
    for stage, ref_verdict in REF_QA2.items():
        ctx_key = qa_key_map.get(stage)
        if ctx_key and ctx_key in pipeline_ctx:
            actual = pipeline_ctx[ctx_key].overall
            assert actual == ref_verdict, (
                f"QA2 mismatch for {stage}: expected {ref_verdict}, got {actual}"
            )


# ---------------------------------------------------------------------------
# Weblog
# ---------------------------------------------------------------------------


def test_weblog_written(pipeline_ctx):
    weblog = Path(pipeline_ctx.get("weblog_path", ""))
    assert weblog.exists(), "weblog/index.html was not written"


def test_weblog_contains_stage_sections(pipeline_ctx):
    weblog = Path(pipeline_ctx.get("weblog_path", ""))
    if not weblog.exists():
        pytest.skip("weblog not written")
    html = weblog.read_text(encoding="utf-8")
    assert 'id="summary"' in html
    assert 'id="s-priorcals"' in html
    assert 'id="s-final_cals"' in html


# ---------------------------------------------------------------------------
# Utility: print reference values (run with -s to capture)
# ---------------------------------------------------------------------------


def test_print_reference_values(pipeline_ctx):
    """
    Not a real assertion — prints current pipeline output values so they can
    be copied into the REF_* constants above.

    Run with: pytest test/test_run_e2e.py::test_print_reference_values -v -s
    """
    print("\n\n=== REFERENCE VALUES FOR test_run_e2e.py ===")
    print(f"REF_NUM_ANTENNA = {pipeline_ctx.get('numAntenna')}")
    print(f"REF_NUM_SPWS = {pipeline_ctx.get('numSpws')}")
    print(f"REF_CORRSTRING = {pipeline_ctx.get('corrstring')!r}")
    print(f"REF_GAIN_SOLINT1 = {pipeline_ctx.get('gain_solint1')!r}")
    print(f"REF_GAIN_SOLINT2 = {pipeline_ctx.get('gain_solint2')!r}")
    print(f"REF_REFANT = {pipeline_ctx.get('refAnt')!r}")
    print(f"REF_FLAG_FRAC_BEFORE = {pipeline_ctx.get('flag_frac_before_applycal')}")
    print(f"REF_FLAG_FRAC_AFTER = {pipeline_ctx.get('flag_frac_after_applycal')}")

    results = pipeline_ctx.get("flux_fitting_results", [])
    print(f"REF_FLUX_FITTING = {results!r}")

    from casatools import table as CasaTable
    tbl_path = pipeline_ctx.get("table_final_amp_gain", "")
    if tbl_path and Path(tbl_path).exists():
        tb = CasaTable()
        try:
            tb.open(tbl_path)
            cparam = tb.getcol("CPARAM")
            flag = tb.getcol("FLAG")
        finally:
            tb.close()
        amp = np.abs(cparam[~flag])
        print(f"REF_FINAL_AMP_MEDIAN = {np.median(amp):.9f}")
        print(f"REF_FINAL_AMP_STD = {np.std(amp):.9f}")

    tbl_bp = pipeline_ctx.get("table_final_bp", "")
    if tbl_bp and Path(tbl_bp).exists():
        tb = CasaTable()
        try:
            tb.open(tbl_bp)
            flag = tb.getcol("FLAG")
        finally:
            tb.close()
        print(f"REF_FINAL_BP_FLAG_FRAC = {np.mean(flag):.9f}")

    qa_key_map = {
        "priorcals": "QA2_priorcals",
        "testBPdcals": "QA2_testBPdcals",
        "semiFinal": "QA2_semiFinal",
        "solint": "QA2_solint",
        "testgains": "QA2_testgains",
        "fluxgains": "QA2_fluxgains",
        "fluxboot": "QA2_fluxboot",
        "finalcals": "QA2_finalcals",
        "applycals": "QA2_applycals",
    }
    qa_dict = {
        k: pipeline_ctx[v].overall
        for k, v in qa_key_map.items()
        if v in pipeline_ctx
    }
    print(f"REF_QA2 = {qa_dict!r}")
    print("==============================================\n")
