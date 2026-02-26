"""
Section 3 — flux and polarization model initialisation.

Calls setjy on ``calibrators.ms`` for every standard calibrator found in the
observation, using the Perley-Butler 2017 flux standard.  For known
polarization angle calibrators (3C286, 3C138, 3C48, 3C147) it additionally
sets the full Stokes model via ``pol_setjy_utils``.

Source-specific caveats are logged clearly so the operator can assess them
without having to search pipeline history:

  3C138  — has been flaring since ~2018; flux is uncertain at any band.
  3C48   — depolarized below 4 GHz; pol model is unreliable there.
  3C147  — pol angle unreliable below 10 GHz.
  3C84   — resolved on long VLA baselines; uvrange restriction already set
            in context (``uvrange3C84``).

No context keys are written back — setjy modifies the MODEL column of
``calibrators.ms`` in-place.
"""

import logging

from casatasks import setjy

from evla_pipe.context import PipelineContext
from evla_pipe.pol_setjy_utils import integrate_polarization_setjy
from evla_pipe.utils import _extract_position_tuples, find_EVLA_band, find_standards

log = logging.getLogger(__name__)

# Perley-Butler 2017 standard flux calibrators
_STANDARD_NAMES = ["3C48", "3C138", "3C147", "3C286"]

# Known polarization angle calibrators (subset of standards)
_POL_ANGLE_CALS = {"3C286", "3C138", "3C48", "3C147"}


def _warn_source_caveats(
    field_name: str, center_frequencies: list[float], spws: list[int]
) -> None:
    """Log scientifically important caveats for specific calibrators."""
    if field_name == "3C138":
        log.warning(
            "3C138: Active flare ongoing since ~2018. Flux uncertainty can exceed 10%% "
            "at C-band and 4x at Q-band. Treat flux scale as approximate."
        )
    elif field_name == "3C48":
        spw_freqs = [center_frequencies[s] for s in spws if s < len(center_frequencies)]
        if spw_freqs and min(spw_freqs) < 4.0e9:
            log.warning(
                "3C48: Depolarized below 4 GHz. Polarization model is unreliable "
                "for the low-frequency SPWs in this observation."
            )
    elif field_name == "3C147":
        spw_freqs = [center_frequencies[s] for s in spws if s < len(center_frequencies)]
        if spw_freqs and min(spw_freqs) < 10.0e9:
            log.warning(
                "3C147: Polarization angle calibration unreliable below 10 GHz. "
                "Use intensity-only model if pol accuracy matters."
            )
    elif field_name == "3C84":
        log.warning(
            "3C84: Resolved on VLA baselines. uvrange restriction %s applied; "
            "verify no short-baseline contamination.",
        )


def _set_field_model(
    cal_ms: str,
    fid: int,
    src_name: str,
    valid_spws: list[int],
    center_frequencies: list[float],
    evla_band: str,
    pol_angle_fields: set[int],
    pol_angle_by_intent: set[int],
) -> None:
    """Set flux+pol or intensity-only model for one field."""
    if fid in pol_angle_fields and src_name in _POL_ANGLE_CALS:
        if fid not in pol_angle_by_intent:
            log.info(
                "Field %d (%s) lacks explicit pol intent — setting pol model anyway.",
                fid,
                src_name,
            )
        ref_freq_hz = center_frequencies[valid_spws[0]]
        log.info(
            "Setting full Stokes model for field %d (%s) band=%s",
            fid,
            src_name,
            evla_band,
        )
        try:
            integrate_polarization_setjy(
                vis=cal_ms,
                field_id=fid,
                field_name=src_name,
                spws=valid_spws,
                band=evla_band,
                ref_freq_hz=ref_freq_hz,
                obs_date=None,
                standard="Perley-Butler 2017",
                usescratch=True,
            )
            return
        except Exception as exc:
            log.warning(
                "Full pol model failed for %s (%s): %s — falling back to intensity-only",  # noqa: E501
                src_name,
                evla_band,
                exc,
            )

    log.info(
        "Setting intensity-only model for field %d (%s) band=%s",
        fid,
        src_name,
        evla_band,
    )
    setjy(
        vis=cal_ms,
        field=str(fid),
        spw=",".join(str(s) for s in valid_spws),
        selectdata=False,
        scalebychan=True,
        standard="Perley-Butler 2017",
        listmodels=False,
        usescratch=True,
    )


def run_setjy(ctx: PipelineContext) -> PipelineContext:
    """
    Set flux and polarization models for all standard calibrators.

    Reads from context
    -----------------
    calibrators_ms, field_positions, field_spws, center_frequencies,
    calibrator_field_select_string, field_names, pol_angle_field_list,
    pol_angle_field_list_by_name, uvrange3C84, scratch

    Writes to context
    -----------------
    (nothing — MODEL column of calibrators_ms is modified in-place)
    """
    cal_ms = ctx["calibrators_ms"]
    field_positions = ctx["field_positions"]
    field_spws = ctx["field_spws"]
    center_frequencies = ctx["center_frequencies"]

    # Union of pol angle fields detected by intent and by name
    pol_angle_by_intent = set(ctx.get("pol_angle_field_list", []))
    pol_angle_by_name = set(ctx.get("pol_angle_field_list_by_name", []))
    pol_angle_fields = pol_angle_by_intent | pol_angle_by_name

    # Identify which field IDs correspond to standard calibrators
    positions = _extract_position_tuples(field_positions)
    # list[list[int]], one entry per _STANDARD_NAMES entry
    standard_fields = find_standards(positions)

    if not any(standard_fields):
        log.warning(
            "No standard flux calibrator (3C48/138/147/286) found in this observation. "
            "Flux density scale will be arbitrary."
        )
        return ctx

    for source_idx, fids in enumerate(standard_fields):
        if not fids:
            continue
        src_name = _STANDARD_NAMES[source_idx]

        for fid in fids:
            if fid >= len(field_spws):
                log.warning(
                    "field_spws index %d out of range — skipping %s", fid, src_name
                )
                continue
            spws = field_spws[fid]
            if not spws:
                log.warning("No SPWs for field %d (%s) — skipping setjy", fid, src_name)
                continue

            valid_spws = [s for s in spws if s < len(center_frequencies)]
            if not valid_spws:
                log.warning("All SPW indices invalid for field %d (%s)", fid, src_name)
                continue

            ref_freq_hz = center_frequencies[valid_spws[0]]
            evla_band = find_EVLA_band(ref_freq_hz / 1e9)  # find_EVLA_band takes GHz

            _warn_source_caveats(src_name, center_frequencies, valid_spws)
            _set_field_model(
                cal_ms=cal_ms,
                fid=fid,
                src_name=src_name,
                valid_spws=valid_spws,
                center_frequencies=center_frequencies,
                evla_band=evla_band,
                pol_angle_fields=pol_angle_fields,
                pol_angle_by_intent=pol_angle_by_intent,
            )

    return ctx
