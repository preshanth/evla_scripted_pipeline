"""
Pipeline context definition for the EVLA scripted pipeline.

This module defines:
  - QAResult: structured per-spw and per-baseband QA reporting
  - PipelineContext: TypedDict of all pipeline state
  - compute_minBL / compute_critfrac: the two dataset-derived parameters
  - make_default_context: the only place defaults are set
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# QA result type
# ---------------------------------------------------------------------------


@dataclass
class QAResult:
    """
    Structured QA result for a calibration table or stage.

    Carries per-spw and per-baseband breakdown so "Partial" is always
    accompanied by which spws passed and which failed.

    Attributes
    ----------
    overall : str
        Stage-level rollup: "Pass", "Partial", or "Fail".
    per_spw : dict[int, str]
        Per-spw verdict keyed by spw ID, e.g. {0: "Pass", 3: "Fail"}.
    per_baseband : dict[str, str]
        Per-baseband verdict keyed by baseband name, e.g. {"A0C0": "Pass"}.
    flagged_fractions : dict[int, float]
        Flagged solution fraction per spw, e.g. {0: 0.05, 3: 0.92}.
    message : str
        Human-readable summary appended to log and weblog.
    """

    overall: str = "Pass"
    per_spw: dict[int, str] = field(default_factory=dict)
    per_baseband: dict[str, str] = field(default_factory=dict)
    flagged_fractions: dict[int, float] = field(default_factory=dict)
    message: str = ""

    def __str__(self) -> str:
        failing_spws = [k for k, v in self.per_spw.items() if v == "Fail"]
        partial_spws = [k for k, v in self.per_spw.items() if v == "Partial"]
        failing_bb = [k for k, v in self.per_baseband.items() if v == "Fail"]
        partial_bb = [k for k, v in self.per_baseband.items() if v == "Partial"]

        parts = [f"Overall: {self.overall}"]
        if failing_spws:
            parts.append(f"Fail spws: {','.join(str(s) for s in sorted(failing_spws))}")
        if partial_spws:
            spw_str = ",".join(str(s) for s in sorted(partial_spws))
            parts.append(f"Partial spws: {spw_str}")
        if failing_bb:
            parts.append(f"Fail basebands: {','.join(sorted(failing_bb))}")
        if partial_bb:
            parts.append(f"Partial basebands: {','.join(sorted(partial_bb))}")
        if self.message:
            parts.append(self.message)
        return " | ".join(parts)

    @classmethod
    def fail(cls, message: str) -> QAResult:
        """Convenience constructor for an outright failure with a reason."""
        return cls(overall="Fail", message=message)

    @classmethod
    def rollup(cls, results: list[QAResult]) -> str:
        """
        Roll up a list of QAResults into a single overall verdict string.

        Any Fail -> Fail. Any Partial -> Partial. All Pass -> Pass.
        """
        overalls = {r.overall for r in results}
        if "Fail" in overalls:
            return "Fail"
        if "Partial" in overalls:
            return "Partial"
        return "Pass"


# ---------------------------------------------------------------------------
# Pipeline context
# ---------------------------------------------------------------------------


class PipelineContext(TypedDict, total=False):
    """
    All pipeline state passed between stages.

    Keys are grouped by the stage that populates them.  Absence of a key
    means the stage that owns it has not yet run.  Stages must not assume
    a key exists unless it is documented as populated by an earlier stage.
    """

    # --- Input parameters (make_default_context) ---------------------------
    SDM_name: str  # base name, no .ms suffix
    msname: str  # SDM_name + ".ms"
    flagonline_txt: str  # path to online flag commands file written by importasdm
    workdir: str  # root output directory; all pipeline outputs land here
    do_pol: bool  # run polarization calibration
    do_hanning: bool  # apply Hanning smoothing after import
    enable_plots: bool  # generate diagnostic plots

    # --- msmd: basic MS dimensions -----------------------------------------
    numSpws: int
    numFields: int
    numAntenna: int
    startdate: float  # MJD of first integration
    int_time: float  # maximum integration time in seconds
    weather_seasonal_weight: float  # 0.5 normally; 1.0 during broken weather periods
    tau: list  # zenith opacity per SPW from plotweather (list[float])
    corrstring: str  # "RR,LL" or "XX,YY" from receptor type

    # --- msmd: field and spw metadata --------------------------------------
    field_names: list[str]
    field_positions: Any  # numpy array shape (2, 1, N) in radians
    center_frequencies: list[float]  # Hz, one per spw
    channels: list[int]  # number of channels per spw
    spw_names: list[str]  # EVLA_L#A0C0#0 style names
    basebands: list[str]  # unique baseband names, e.g. ["A0C0", "B0D0"]
    all_spw: str  # CASA selection string "0~N-1"
    tst_delay_spw: str  # CASA spw:chan selection, mid-channels per spw,
    # avoiding baseband edge roll-offs.
    # e.g. "0:32~96,1:32~96,..." for 128-chan spws.
    # Raw intent strings exactly as recorded in the MS, keyed by the full
    # intent string (e.g. "CALIBRATE_BANDPASS#UNSPECIFIED") so downstream
    # stages can pass them directly to CASA task intent= parameters or
    # build wildcard selections (e.g. "CALIBRATE_BANDPASS*").
    # Value keys: "fields" (list[int]), "scans" (list[int]), "spws" (list[int]).
    intents: dict[str, dict]  # intent_string -> {fields, scans, spws}
    field_spws: list[list[int]]  # field_id -> list of spw IDs
    field_scan_map: dict[int, list[int]]  # field_id -> list of scan IDs

    # --- msmd: calibrator field and scan lists -----------------------------
    flux_field_list: list[int]
    bandpass_field_list: list[int]
    delay_field_list: list[int]
    phase_field_list: list[int]
    amp_field_list: list[int]
    # Pol calibrators detected by CALIBRATE_POL_ANGLE / CALIBRATE_POL_LEAKAGE
    # intents in the MS state table.
    pol_angle_field_list: list[int]
    pol_lkg_field_list: list[int]

    # Pol calibrators detected by field name/position match against known
    # sources (3C286, 3C138, etc.) regardless of whether the MS carries
    # explicit pol intents.  These are the fields we CAN calibrate pol on
    # even if the observer did not set the intent.  msmd populates both
    # lists; run_polcal uses the union.
    pol_angle_field_list_by_name: list[int]
    pol_lkg_field_list_by_name: list[int]

    flux_scan_list: list[int]
    bandpass_scan_list: list[int]
    delay_scan_list: list[int]
    phase_scan_list: list[int]

    # --- msmd: CASA selection strings (comma-separated IDs) ----------------
    flux_field_select_string: str
    bandpass_field_select_string: str
    delay_field_select_string: str
    phase_field_select_string: str
    amp_field_select_string: str
    calibrator_field_select_string: str  # union of all calibrator fields

    bandpass_scan_select_string: str
    delay_scan_select_string: str
    phase_scan_select_string: str

    # --- msmd: computed calibration parameters -----------------------------
    # Both stored in context so they can be inspected and overridden.
    minBL_for_cal: int  # max(3, numAntenna // 2)
    critfrac: float  # per-baseband threshold: 0.9 / (numSpws / 8)
    critfrac_per_spw: float  # per-spw threshold: 0.9 / numSpws

    cal3C84_d: bool  # 3C84 (J0319+4130) is delay calibrator
    cal3C84_bp: bool  # 3C84 is bandpass calibrator
    uvrange3C84: str  # ">0.15klambda" when 3C84 present, else ""

    # --- Cumulative calibration table lists --------------------------------
    # priorcals: populated by run_priorcals, read-only after that.
    # Each entry is a path to a calibration table.
    priorcals: list[str]

    # final_caltables: assembled by run_final_cals.
    # This is the complete gaintable list passed to applycal.
    final_caltables: list[str]

    # pol_caltables: assembled by run_polcal. Empty if do_pol=False.
    # Appended to final_caltables in run_apply_cals.
    pol_caltables: list[str]

    # --- Named calibration table paths (set by the owning stage) ----------
    #
    # CASA tasks take gaintable as a list[str].  Each stage assembles that
    # list from these named keys at call time, following the same pattern
    # as the original pipeline:
    #
    #   gaintable = ctx["priorcals"] + [ctx["table_test_delay_init_gain"]]
    #
    # Never pass the named keys directly to CASA — always build the list
    # inside the stage function so the assembly logic is explicit and local.
    # Prior cals
    table_gain_curves: str
    table_opacities: str
    table_requantizer: str
    table_switched_power: str
    table_antpos: str

    # Test calibrations
    table_test_delay_init_gain: str
    table_test_delay: str
    table_test_bp_init_gain: str
    table_test_bp: str

    # Semi-final calibrations
    table_semifinal_delay_init_gain: str
    table_delay: str
    table_bp_init_gain: str
    table_bp: str

    # Test gains
    table_test_gaincal: str

    # Flux gains
    table_flux_phase_short: str
    table_phase_short: str
    table_flux_gaincal_fcal: str

    # Final cals
    table_final_delay_init_gain: str
    table_final_delay: str
    table_final_bp_init_gain: str
    table_final_bp: str
    table_final_phase_gain: str
    table_final_amp_gain: str
    table_average_phase_gain: str
    table_flux_gaincal: str

    # Polarization cals
    table_pol_Xf: str  # cross-hand delay
    table_pol_Df: str  # leakage D-terms
    table_pol_Xa: str  # polarization angle

    # --- testBPdcals / semiFinal -------------------------------------------
    refAnt: str  # reference antenna for gaincal/bandpass

    # --- solint ------------------------------------------------------------
    # gain_solint1 = integration time as CASA string e.g. "2.02s"
    # gain_solint2 = max scan duration × 1.01 as CASA string e.g. "123.45s"
    gain_solint1: str
    gain_solint2: str
    calibrators_ms: str  # path to split calibrators-only MS

    # --- QA2 per stage -----------------------------------------------------
    # Each value is a QAResult with per-spw and per-baseband breakdown.
    QA2_priorcals: QAResult
    QA2_calprep: QAResult
    QA2_testBPdcals: QAResult
    QA2_semiFinal: QAResult
    QA2_solint: QAResult
    QA2_testgains: QAResult
    QA2_fluxgains: QAResult
    QA2_fluxboot: QAResult
    QA2_finalcals: QAResult
    QA2_polcal: QAResult
    QA2_applycals: QAResult

    # --- polcal sub-QA -----------------------------------------------------
    QA2_polcal_Xf: QAResult
    QA2_polcal_Df: QAResult
    QA2_polcal_Xa: QAResult

    # --- fluxboot results --------------------------------------------------
    # Per-source power-law fitting results from fluxscale bootstrap.
    # Each entry: {"source", "spws", "flux_jy", "spix", "snr", "reffreq_ghz"}
    flux_fitting_results: list

    # --- applycal flag fractions -------------------------------------------
    flag_frac_before_applycal: float
    flag_frac_after_applycal: float

    # --- apply_cals output -------------------------------------------------
    target_ms: str  # path to split target.ms

    # --- weblog ------------------------------------------------------------
    # stage_records: populated by _timed() in pipeline.py as each stage runs.
    # Each entry: {"name": str, "label": str, "duration_s": float}
    stage_records: list
    weblog_path: str  # absolute path to workdir/weblog/index.html after run_weblog

    # --- cal_diagnostics ---------------------------------------------------
    # Maximum baseline length in metres; computed by run_msmd from
    # msmd.baselinelengths() and used to derive per-SPW cell sizes.
    max_baseline_m: float
    # Per-field/per-SPW imaging results from run_cal_diagnostics.
    # Each entry: {field_id, field_name, spw, freq_ghz, stokes,
    #              peak_jy, rms_jy, expected_jy, ratio, png}
    cal_image_results: list

    # --- flag snapshots ----------------------------------------------------
    # Accumulated by _append_snapshot() in _flag_utils.py after every stage
    # that modifies flags.  Each entry is a plain dict (JSON-serialisable):
    #   {stage, label, vis, total, flagged, frac, per_spw}
    # Populated by: preflag, initial_rflag, checkflag, apply_cals (×2), final_flags
    flag_snapshots: list

    # --- checkpoint (internal) ---------------------------------------------
    _completed_stages: list  # list of stage name strings; written by save_checkpoint


# ---------------------------------------------------------------------------
# Parameter formulas
# ---------------------------------------------------------------------------


def compute_minBL(num_antenna: int) -> int:
    """
    Minimum baselines per antenna for a valid solution.

    Rule from original pipeline: half the array, minimum 3.
    With 27 VLA antennas this gives 13.
    """
    return max(3, int(num_antenna / 2.0))


def compute_critfrac(num_spws: int) -> tuple[float, float]:
    """
    Flagged solution fraction thresholds.

    Returns (critfrac_per_baseband, critfrac_per_spw).

    Per baseband: 0.9 / (numSpws / 8) — groups of 8 spws per baseband.
    Per spw:      0.9 / numSpws

    For a standard 8-spw L-band observation:
      per_baseband = 0.9 / (8/8) = 0.9
      per_spw      = 0.9 / 8    = 0.1125

    For a 16-spw observation:
      per_baseband = 0.9 / (16/8) = 0.45
      per_spw      = 0.9 / 16    = 0.05625
    """
    if num_spws >= 8:
        critfrac_bb = 0.9 / int(num_spws / 8.0)
    else:
        critfrac_bb = 0.9 / float(num_spws)
    critfrac_spw = 0.9 / float(num_spws)
    return critfrac_bb, critfrac_spw


# ---------------------------------------------------------------------------
# Default context factory
# ---------------------------------------------------------------------------


def make_default_context(sdm_name: str, **kwargs) -> PipelineContext:
    """
    Create an initial pipeline context from an SDM name.

    Only input parameters and empty accumulator lists are set here.
    Everything else is populated by the stage that owns it.

    Parameters
    ----------
    sdm_name : str
        SDM directory name. Trailing slash and .ms suffix are stripped.
    **kwargs
        Override any default. E.g. do_pol=True, scratch=True.

    Returns
    -------
    PipelineContext
    """
    sdm_name = sdm_name.rstrip("/")
    if sdm_name.endswith(".ms"):
        sdm_name = sdm_name[:-3]

    ctx: PipelineContext = {
        "SDM_name": sdm_name,
        "msname": f"{sdm_name}.ms",
        "flagonline_txt": f"{sdm_name}.flagonline.txt",
        "workdir": "",  # filled by run_startup
        "calibrators_ms": "",  # filled by run_startup (workdir/calibrators.ms)
        "do_pol": False,
        "do_hanning": True,
        "enable_plots": True,
        "priorcals": [],
        "final_caltables": [],
        "pol_caltables": [],
        "stage_records": [],
        "flag_snapshots": [],
    }
    ctx.update(kwargs)
    return ctx


# ---------------------------------------------------------------------------
# Checkpoint serialization helpers
# ---------------------------------------------------------------------------

# These fields are non-JSON-serializable numpy arrays derived by run_msmd.
# They are excluded from the checkpoint and re-derived on resume.
_EXCLUDE_FROM_CHECKPOINT = {"field_positions"}


def _serialize_ctx(ctx: PipelineContext) -> dict:
    """Return a JSON-safe copy of ctx, dropping non-serializable fields."""
    out = {}
    for k, v in ctx.items():
        if k in _EXCLUDE_FROM_CHECKPOINT:
            continue
        if isinstance(v, QAResult):
            out[k] = {"__QAResult__": True, **asdict(v)}
        else:
            out[k] = v
    return out


def _deserialize_ctx(data: dict) -> PipelineContext:
    """Reconstruct ctx from a JSON-loaded dict."""
    ctx: PipelineContext = {}
    for k, v in data.items():
        if isinstance(v, dict) and v.get("__QAResult__"):
            d = {kk: vv for kk, vv in v.items() if kk != "__QAResult__"}
            ctx[k] = QAResult(**d)
        else:
            ctx[k] = v
    return ctx


def save_checkpoint(ctx: PipelineContext, stage_name: str) -> None:
    """Append stage_name to _completed_stages and atomically write checkpoint.

    Writes to ``<workdir>/pipeline_context/checkpoint.json`` via a tmp-then-
    rename to avoid a partial file if the process is killed mid-write.
    """
    workdir = ctx.get("workdir", "")
    if not workdir:
        return
    completed = list(ctx.get("_completed_stages") or [])
    completed.append(stage_name)
    ctx["_completed_stages"] = completed
    ckpt_dir = Path(workdir) / "pipeline_context"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "completed_stages": completed,
        "cli_fingerprint": {
            "SDM_name": ctx.get("SDM_name", ""),
            "do_pol": ctx.get("do_pol", False),
            "do_hanning": ctx.get("do_hanning", True),
        },
        "context": _serialize_ctx(ctx),
    }

    def _default(o):
        # numpy scalars (int64, float64, …) expose .item(); use it without
        # importing numpy so this module stays CASA-free.
        if hasattr(o, "item"):
            return o.item()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    tmp = ckpt_dir / "checkpoint.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2, default=_default))
    tmp.rename(ckpt_dir / "checkpoint.json")


def load_checkpoint(workdir: str) -> tuple[PipelineContext, list[str], dict]:
    """Load checkpoint from workdir.

    Returns
    -------
    (ctx, completed_stages, cli_fingerprint)
    """
    ckpt = Path(workdir) / "pipeline_context" / "checkpoint.json"
    if not ckpt.exists():
        raise FileNotFoundError(f"No checkpoint found at {ckpt}")
    payload = json.loads(ckpt.read_text())
    ctx = _deserialize_ctx(payload["context"])
    return ctx, payload["completed_stages"], payload["cli_fingerprint"]
