"""
Section 1 — MS metadata stage.

Populates the entire PipelineContext backbone from a single open of the
Measurement Set.  All downstream stages read from context rather than
re-querying the MS.

Clean port of EVLA_pipe_msmd.py.  Key changes vs the original:
- No intermediate ms_metadata dict; context is populated directly.
- No redundant ms_raw_api dump (pure duplication of earlier work).
- corrstring derived from receptor type, not assumed.
- tst_delay_spw uses inner third of channels per spw.
- Both critfrac values stored: per-baseband and per-spw.
- Pol calibrator detection: by intent first, then by name/position.
"""

import logging
from pathlib import Path

import numpy as np
from casatasks import listobs
from casatools import msmetadata

from evla_pipe.context import PipelineContext, compute_critfrac, compute_minBL
from evla_pipe.simple_utils import field_label
from evla_pipe.utils import find_EVLA_band, logprint, uniq

log = logging.getLogger(__name__)


def task_log(msg: str) -> None:
    logprint(msg, logfileout="logs/msmd.log")


# ---------------------------------------------------------------------------
# Known polarization calibrators (by name / alias)
# ---------------------------------------------------------------------------

# Pol angle calibrators: highly polarized, known position angle
_POL_ANGLE_CALS = [
    "J1331+3030",
    "1331+305",
    "3C286",
    "3c286",
    "J0521+1638",
    "0521+166",
    "3C138",
    "3c138",
    "J0137+3309",
    "0137+331",
    "3C48",
    "3c48",
]

# Leakage calibrators: low / zero intrinsic polarization
_POL_LKG_CALS = [
    "J0319+4130",
    "0316+413",
    "3C84",
    "3c84",
    "J1407+2827",
    "OQ208",
    "oq208",
    "J0542+4951",
    "0542+498",
    "3C147",
    "3c147",
    "J0259+0747",
]

# 3C84 variants (need uvrange treatment)
_3C84_VARIANTS = ["3c84", "3c 84", "j0319+4130", "0316+413"]


def _normalize(name: str) -> str:
    """Lowercase alphanumeric only — for robust name matching."""
    return "".join(c for c in name.lower() if c.isalnum())


def _fields_for_names(
    msmd_tool, field_names: list[str], aliases: list[str]
) -> list[int]:
    """
    Return field IDs whose names match any alias in the list.

    Tries msmd.fieldsforname first (exact), then normalized substring match.
    """
    found = []
    for alias in aliases:
        # Only call fieldsforname when the alias is an actual field name —
        # CASA logs a SEVERE at the C++ level before throwing for unknown names,
        # which we cannot suppress from Python even with try/except.
        if alias in field_names:
            ids = list(msmd_tool.fieldsforname(alias))
            if ids:
                found.extend(ids)
                break

        norm = _normalize(alias)
        for fid, fname in enumerate(field_names):
            if norm and norm in _normalize(fname):
                found.append(fid)
                break
        if found:
            break
    return sorted(set(found))


# ---------------------------------------------------------------------------
# corrstring from receptor type
# ---------------------------------------------------------------------------


def _corrstring(msmd_tool) -> str:
    """
    Derive parallel-hand correlation string from the first data description.

    CASA correlation type codes:
      RR=5, RL=6, LR=7, LL=8   → circular feeds (L-band and above)
      XX=9, XY=10, YX=11, YY=12 → linear feeds (P-band and 4-band)
    """
    try:
        ddids = msmd_tool.datadescids()
        polid = msmd_tool.polidfordatadesc(int(ddids[0]))
        corrtypes = msmd_tool.corrtypesforpol(int(polid))
        if 5 in corrtypes:  # RR present → circular
            return "RR,LL"
        if 9 in corrtypes:  # XX present → linear
            return "XX,YY"
    except Exception as e:
        task_log(f"Warning: could not determine corrstring: {e}")
    return "RR,LL"  # safe default for VLA


# ---------------------------------------------------------------------------
# tst_delay_spw: inner-third channel range per spw
# ---------------------------------------------------------------------------


def _tst_delay_spw(channels: list[int]) -> str:
    """
    Build CASA spw:chan selection using the inner third of each spw.

    Inner third avoids edge roll-offs and Gibbs ringing from Hanning.
    Example for 64-channel spws: "0:21~42,1:21~42,..."
    """
    parts = []
    for ispw, nchan in enumerate(channels):
        start = int(nchan / 3)
        end = int(2 * nchan / 3)
        parts.append(f"{ispw}:{start}~{end}")
    return ",".join(parts)


# ---------------------------------------------------------------------------
# Quack scan identification
# ---------------------------------------------------------------------------


def _quack_scan_string(msmd_tool, scan_numbers: list[int]) -> str:
    """
    Identify first scan of each new field+spw combination for quacking.

    Returns a comma-separated string of scan IDs.
    """
    scan_list = [scan_numbers[0]] if scan_numbers else []
    if len(scan_numbers) > 1:
        prev_fields = set(msmd_tool.fieldsforscan(scan_numbers[0]))
        prev_spws = set(msmd_tool.spwsforscan(scan_numbers[0]))
        for scan in scan_numbers[1:]:
            cur_fields = set(msmd_tool.fieldsforscan(scan))
            cur_spws = set(msmd_tool.spwsforscan(scan))
            if cur_fields != prev_fields or cur_spws != prev_spws:
                scan_list.append(scan)
                prev_fields, prev_spws = cur_fields, cur_spws
    return ",".join(map(str, sorted(scan_list)))


# ---------------------------------------------------------------------------
# Calibrator intent matching
# ---------------------------------------------------------------------------

_INTENT_KEYS = {
    "CALIBRATE_FLUX": "flux",
    "CALIBRATE_BANDPASS": "bandpass",
    "CALIBRATE_DELAY": "delay",
    "CALIBRATE_PHASE": "phase",
    "CALIBRATE_AMPLI": "ampli",
    "CALIBRATE_POL_ANGLE": "pol_angle",
    "CALIBRATE_POL_LEAKAGE": "pol_leakage",
    "CALIBRATE_POINTING": "pointing",
}


def _calibrator_lists(msmd_tool, all_intents: list[str]) -> tuple[dict, dict]:
    """
    Extract calibrator field and scan lists keyed by intent type.

    Uses case-insensitive substring matching to handle intent suffixes
    such as CALIBRATE_FLUX#UNSPECIFIED.

    Returns (cal_fields, cal_scans) — both dicts keyed by short intent name.
    """
    cal_fields: dict[str, list[int]] = {v: [] for v in _INTENT_KEYS.values()}
    cal_scans: dict[str, list[int]] = {v: [] for v in _INTENT_KEYS.values()}

    for intent_str in all_intents:
        for full_intent, key in _INTENT_KEYS.items():
            if full_intent.lower() in intent_str.lower():
                try:
                    fields = list(msmd_tool.fieldsforintent(intent_str))
                    scans = list(msmd_tool.scansforintent(intent_str))
                    cal_fields[key].extend(fields)
                    cal_scans[key].extend(scans)
                except Exception:
                    pass

    # Deduplicate and sort
    for key in cal_fields:
        cal_fields[key] = sorted(set(cal_fields[key]))
        cal_scans[key] = sorted(set(cal_scans[key]))

    return cal_fields, cal_scans


def _select_string(ids: list[int]) -> str:
    return ",".join(map(str, ids))


# ---------------------------------------------------------------------------
# tau
# ---------------------------------------------------------------------------


def _weather_seasonal_weight(startdate: float) -> float:
    """
    Return the plotweather seasonal_weight for this observation.

    Known broken VLA weather-station periods require 100% seasonal model.
    All other observations use the default 50/50 blend.
    """
    broken = (55918.80 <= startdate <= 55938.98) or (56253.6 <= startdate <= 56271.6)
    if broken:
        task_log("Weather station broken during this period, using seasonal_weight=1.0")
    return 1.0 if broken else 0.5


# ---------------------------------------------------------------------------
# Main stage
# ---------------------------------------------------------------------------


def _log_context_summary(ctx: PipelineContext) -> None:
    """Log a structured summary of pipeline metadata after run_msmd completes."""
    field_names = ctx.get("field_names", [])

    # Build role map: field_id → list of roles
    role_map: dict[int, list[str]] = {fid: [] for fid in range(len(field_names))}
    for ctx_key, role in [
        ("flux_field_list", "flux"),
        ("bandpass_field_list", "bandpass"),
        ("delay_field_list", "delay"),
        ("phase_field_list", "phase"),
        ("amp_field_list", "amp"),
        ("pol_angle_field_list", "pol_angle"),
        ("pol_lkg_field_list", "pol_leakage"),
    ]:
        for fid in ctx.get(ctx_key, []):
            if fid < len(field_names):
                role_map[fid].append(role)

    cal_fids = {fid for fid, roles in role_map.items() if roles}
    for fid in range(len(field_names)):
        if fid not in cal_fids:
            role_map[fid].append("target")

    sep = "=" * 62
    lines = [
        sep,
        "  Pipeline metadata summary",
        sep,
        f"  MS         : {ctx.get('msname', '?')}",
        f"  Antennas   : {ctx.get('numAntenna', '?')}",
        f"  SPWs       : {ctx.get('numSpws', '?')}  ({ctx.get('all_spw', '')})",
        f"  Corr       : {ctx.get('corrstring', '?')}",
        f"  Int time   : {ctx.get('int_time', 0):.2f}s",
        "",
        "  Fields",
        "  " + "-" * 58,
    ]
    for fid, name in enumerate(field_names):
        roles = ", ".join(role_map.get(fid, ["target"]))
        lines.append(f"  {fid:3d}  {name:<24s}  {roles}")

    lines += ["", "  Intents (from MS)", "  " + "-" * 58]
    for intent_str, info in ctx.get("intents", {}).items():
        fids = info.get("fields", [])
        scans = info.get("scans", [])
        lines.append(f"  {intent_str:<48s}  fields={fids}  scans={scans}")

    lines += ["", "  Polarization calibrators", "  " + "-" * 58]
    pol_angle = ctx.get("pol_angle_field_list", [])
    pol_lkg = ctx.get("pol_lkg_field_list", [])
    pol_angle_by_name = ctx.get("pol_angle_field_list_by_name", [])
    pol_lkg_by_name = ctx.get("pol_lkg_field_list_by_name", [])

    if pol_angle:
        for fid in pol_angle:
            via = "name" if fid in pol_angle_by_name else "intent"
            name = field_names[fid] if fid < len(field_names) else "?"
            lines.append(f"  Angle  : {field_label(ctx, str(fid))}  [via {via}]")
    else:
        lines.append("  Angle  : none detected")
    if pol_lkg:
        for fid in pol_lkg:
            via = "name" if fid in pol_lkg_by_name else "intent"
            name = field_names[fid] if fid < len(field_names) else "?"
            lines.append(f"  Leakage: {field_label(ctx, str(fid))}  [via {via}]")
    else:
        lines.append("  Leakage: none detected")

    lines += [
        "",
        "  Key parameters",
        "  " + "-" * 58,
        f"  minBL_for_cal = {ctx.get('minBL_for_cal', '?')}",
        f"  critfrac(bb)  = {ctx.get('critfrac', 0):.4f}",
        f"  critfrac(spw) = {ctx.get('critfrac_per_spw', 0):.4f}",
        sep,
    ]

    for line in lines:
        log.info(line)
        task_log(line)


def run_msmd(ctx: PipelineContext) -> PipelineContext:
    """
    Populate the entire PipelineContext backbone from the Measurement Set.

    Opens the MS once with msmetadata, extracts all pipeline-required
    information, then closes it.  Nothing else opens the MS again until
    a CASA task explicitly needs it.

    Raises
    ------
    RuntimeError
        If the MS cannot be opened or critical metadata is missing.
    """
    msname = ctx["msname"]
    task_log(f"*** Starting run_msmd: {msname} ***")

    msmd = msmetadata()

    try:
        msmd.open(msname)

        # --- Basic dimensions -------------------------------------------
        n_spw = msmd.nspw()
        n_fields = msmd.nfields()
        n_ant = msmd.nantennas()
        scan_numbers = list(msmd.scannumbers())
        field_names = list(msmd.fieldnames())
        all_intents = list(msmd.intents())

        # Store raw intent strings as the MS records them (e.g.
        # "CALIBRATE_BANDPASS#UNSPECIFIED") with their associated fields,
        # scans, and spws.  Downstream stages can pass these strings directly
        # to CASA task intent= parameters or build wildcard selections from them.
        # Times are omitted — they are numpy arrays and rarely needed for msselect.
        intents_ctx: dict[str, dict] = {}
        for intent_str in all_intents:
            try:
                intents_ctx[intent_str] = {
                    "fields": list(msmd.fieldsforintent(intent_str)),
                    "scans": list(msmd.scansforintent(intent_str)),
                    "spws": list(msmd.spwsforintent(intent_str)),
                }
            except Exception as e:
                task_log(
                    f"Warning: could not extract info for intent '{intent_str}': {e}"
                )
        ctx["intents"] = intents_ctx
        task_log(f"Intents recorded: {list(intents_ctx.keys())}")

        ctx["numSpws"] = n_spw
        ctx["numFields"] = n_fields
        ctx["numAntenna"] = n_ant

        # Maximum baseline length — used by cal_diagnostics for cell size.
        baseline_lengths = msmd.baselinelengths()
        ctx["max_baseline_m"] = float(np.max(baseline_lengths))

        task_log(
            f"MS: {n_spw} spws, {n_fields} fields, {n_ant} antennas, "
            f"{len(scan_numbers)} scans, "
            f"max_baseline={ctx['max_baseline_m']:.0f}m"
        )

        # --- Start date (MJD days) ---------------------------------------
        # msmd.summary() returns BeginTime in MJD seconds; convert to days.
        summary = msmd.summary()
        startdate_s = float(summary.get("begin time", summary.get("BeginTime", 0.0)))
        ctx["startdate"] = startdate_s / 86400.0
        task_log(f"Observation start: {ctx['startdate']:.4f} MJD")

        # --- Spectral window info ---------------------------------------
        center_frequencies = []
        channels = []
        spw_names = []

        for spw in range(n_spw):
            nchan = msmd.nchan(spw)
            channels.append(nchan)
            center_frequencies.append(msmd.meanfreq(spw))
            name = msmd.namesforspws([spw])
            spw_names.append(name[0] if name else f"spw{spw}")

        ctx["center_frequencies"] = center_frequencies
        ctx["channels"] = channels
        ctx["spw_names"] = spw_names
        ctx["all_spw"] = ",".join(map(str, range(n_spw)))
        ctx["tst_delay_spw"] = _tst_delay_spw(channels)

        # Parse basebands from EVLA spw name format: EVLA_L#A0C0#0
        basebands: list[str] = []
        if spw_names and "#" in spw_names[0]:
            for name in spw_names:
                parts = name.split("#")
                if len(parts) == 3:
                    bb = parts[1]
                    if bb not in basebands:
                        basebands.append(bb)
        ctx["basebands"] = basebands

        # EVLA bands present
        bands = [find_EVLA_band(f) for f in center_frequencies]
        task_log(f"EVLA bands present: {','.join(uniq(bands))}")

        # --- Integration time -------------------------------------------
        int_times = []
        for scan in scan_numbers:
            times = msmd.timesforscan(scan)
            if len(times) > 1:
                int_times.append(float(np.median(np.diff(times))))
        ctx["int_time"] = float(max(int_times)) if int_times else 0.0

        # --- Corrstring from receptor type ------------------------------
        ctx["corrstring"] = _corrstring(msmd)
        task_log(f"Correlation string: {ctx['corrstring']}")

        # --- Field metadata ---------------------------------------------
        field_positions = [msmd.phasecenter(fid) for fid in range(n_fields)]
        ctx["field_names"] = field_names
        ctx["field_positions"] = field_positions
        ctx["field_spws"] = [list(msmd.spwsforfield(fid)) for fid in range(n_fields)]
        ctx["field_scan_map"] = {
            fid: list(msmd.scansforfield(fid)) for fid in range(n_fields)
        }

        # --- Calibrator assignments by intent ---------------------------
        cal_fields, cal_scans = _calibrator_lists(msmd, all_intents)

        ctx["flux_field_list"] = cal_fields["flux"]
        ctx["bandpass_field_list"] = cal_fields["bandpass"]
        ctx["delay_field_list"] = cal_fields["delay"]
        ctx["phase_field_list"] = cal_fields["phase"]
        ctx["amp_field_list"] = cal_fields["ampli"]
        ctx["pol_angle_field_list"] = cal_fields["pol_angle"]
        ctx["pol_lkg_field_list"] = cal_fields["pol_leakage"]

        ctx["flux_scan_list"] = cal_scans["flux"]
        ctx["bandpass_scan_list"] = cal_scans["bandpass"]
        ctx["delay_scan_list"] = cal_scans["delay"]
        ctx["phase_scan_list"] = cal_scans["phase"]

        # Select strings — with intent-chain fallbacks matching original pipeline
        ctx["flux_field_select_string"] = _select_string(cal_fields["flux"])
        ctx["bandpass_field_select_string"] = _select_string(
            cal_fields["bandpass"]
        ) or _select_string(cal_fields["flux"])
        ctx["delay_field_select_string"] = (
            _select_string(cal_fields["delay"]) or ctx["bandpass_field_select_string"]
        )
        ctx["phase_field_select_string"] = _select_string(cal_fields["phase"])
        ctx["amp_field_select_string"] = (
            _select_string(cal_fields["ampli"]) or ctx["phase_field_select_string"]
        )
        ctx["bandpass_scan_select_string"] = _select_string(
            cal_scans["bandpass"]
        ) or _select_string(cal_scans["flux"])
        ctx["delay_scan_select_string"] = (
            _select_string(cal_scans["delay"]) or ctx["bandpass_scan_select_string"]
        )
        ctx["phase_scan_select_string"] = _select_string(cal_scans["phase"])

        # Union of all calibrator fields for refant selection
        all_cal_fields: set[int] = set()
        for key in [
            "flux",
            "bandpass",
            "delay",
            "phase",
            "ampli",
            "pol_angle",
            "pol_leakage",
        ]:
            all_cal_fields.update(cal_fields[key])
        ctx["calibrator_field_select_string"] = _select_string(sorted(all_cal_fields))

        # --- Pol calibrators by name (intent-independent) ---------------
        ctx["pol_angle_field_list_by_name"] = _fields_for_names(
            msmd, field_names, _POL_ANGLE_CALS
        )
        ctx["pol_lkg_field_list_by_name"] = _fields_for_names(
            msmd, field_names, _POL_LKG_CALS
        )

        # If intent-based lists are empty, try name-based as fallback and
        # update the unified lists that run_polcal will use
        if not ctx["pol_angle_field_list"] and ctx["pol_angle_field_list_by_name"]:
            task_log(
                "No POL_ANGLE intent found; using name-matched pol angle calibrators"
            )
            ctx["pol_angle_field_list"] = ctx["pol_angle_field_list_by_name"]

        if not ctx["pol_lkg_field_list"] and ctx["pol_lkg_field_list_by_name"]:
            task_log(
                "No POL_LEAKAGE intent found; using name-matched leakage calibrators"
            )
            ctx["pol_lkg_field_list"] = ctx["pol_lkg_field_list_by_name"]

        if not ctx["pol_angle_field_list"]:
            task_log(
                "WARNING: No pol angle calibrator found; polarization cal disabled"
            )
            ctx["do_pol"] = False

        # --- 3C84 detection ---------------------------------------------
        fields_3c84 = [
            fid
            for fid, name in enumerate(field_names)
            if any(v in name.lower() for v in _3C84_VARIANTS)
        ]
        ctx["cal3C84_d"] = any(f in cal_fields["delay"] for f in fields_3c84)
        ctx["cal3C84_bp"] = any(f in cal_fields["bandpass"] for f in fields_3c84)
        ctx["uvrange3C84"] = (
            "0~1800klambda" if (ctx["cal3C84_d"] or ctx["cal3C84_bp"]) else ""
        )

        if fields_3c84:
            task_log(
                f"3C84 present as field(s) {fields_3c84}; "
                f"cal3C84_d={ctx['cal3C84_d']}, cal3C84_bp={ctx['cal3C84_bp']}"
            )

        # --- Computed calibration parameters ----------------------------
        ctx["minBL_for_cal"] = compute_minBL(n_ant)
        critfrac_bb, critfrac_spw = compute_critfrac(n_spw)
        ctx["critfrac"] = critfrac_bb
        ctx["critfrac_per_spw"] = critfrac_spw
        task_log(
            f"minBL_for_cal={ctx['minBL_for_cal']}, "
            f"critfrac(bb)={critfrac_bb:.4f}, critfrac(spw)={critfrac_spw:.4f}"
        )

        # --- Quack scan string ------------------------------------------
        ctx["quack_scan_string"] = _quack_scan_string(msmd, scan_numbers)

        # --- numSpws2 (adjusted for pointing scans) ---------------------
        n_pointing = len(cal_scans["pointing"])
        ctx["numSpws2"] = n_spw - 2 if n_pointing > 0 else n_spw

    finally:
        msmd.close()

    # --- weather seasonal weight (used by priorcals for plotweather) ---
    ctx["weather_seasonal_weight"] = _weather_seasonal_weight(ctx.get("startdate", 0.0))

    # --- listobs -------------------------------------------------------
    logs_dir = Path(ctx["workdir"]) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    listfile = str(logs_dir / (Path(msname).stem + ".listobs"))
    try:
        listobs(vis=msname, listfile=listfile, overwrite=True, verbose=True)
    except Exception as e:
        task_log(f"Warning: listobs failed: {e}")

    _log_context_summary(ctx)
    task_log("*** run_msmd complete ***")
    return ctx
