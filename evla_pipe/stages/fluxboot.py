"""
Section 4 — flux density bootstrapping.

Uses fluxscale to transfer the absolute flux scale from the primary standard
(3C48/138/147/286) to all phase/amplitude calibrators, then fits a power law
to the bootstrapped fluxes and sets the MODEL column via setjy.

This is the step that gives phase calibrators a correct flux density so that
amplitude calibration produces physically meaningful Jy values rather than
arbitrary units.

Context keys written
--------------------
table_flux_gaincal_fcal : str  — fluxtable output of fluxscale
"""

import logging
from pathlib import Path

import numpy as np
import scipy.optimize
from casatasks import fluxscale, rmtables, setjy

from evla_pipe.context import PipelineContext
from evla_pipe.utils import find_EVLA_band

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Power-law fitting helpers
# ---------------------------------------------------------------------------

def _log_power_law(log_nu: np.ndarray, log_s0: float, spix: float) -> np.ndarray:
    return log_s0 + spix * log_nu


def _fit_one_band(
    lfreqs: list, lfds: list, lerrs: list
) -> tuple[float, float, float]:
    """Fit log(S) = aa + bb*log(ν). Returns (aa, bb, snr)."""
    if len(lfds) <= 2:
        return (lfds[0] if lfds else 0.0), 0.0, 0.0
    try:
        popt, pcov = scipy.optimize.curve_fit(
            _log_power_law,
            np.array(lfreqs),
            np.array(lfds),
            sigma=np.array(lerrs),
            absolute_sigma=True,
            p0=[lfds[0], 0.0],
        )
        aa, bb = popt
        snr = abs(bb) / np.sqrt(pcov[1, 1]) if pcov[1, 1] > 0 else 0.0
        return aa, bb, snr
    except Exception as exc:
        log.warning("Power-law fit failed: %s", exc)
        return lfds[0], 0.0, 0.0


def _parse_fluxscale(
    fluxscale_result: dict,
) -> tuple[list[str], list[list[float]], list[int]]:
    """Extract parallel lists of (source, [fd, fe], spw) from fluxscale dict."""
    sources: list[str] = []
    flux_densities: list[list[float]] = []
    spws: list[int] = []
    for field_id, field_data in fluxscale_result.items():
        try:
            int(field_id)
        except ValueError:
            continue
        src = field_data.get("fieldName")
        if not src:
            continue
        for spw_id, spw_data in field_data.items():
            try:
                int(spw_id)
            except ValueError:
                continue
            for fd, fe in zip(spw_data.get("fluxd", []), spw_data.get("fluxdErr", [])):
                if fd not in (-1, 0):
                    sources.append(src)
                    flux_densities.append([float(fd), float(fe)])
                    spws.append(int(spw_id))
    return sources, flux_densities, spws


def _band_data(
    idx: np.ndarray,
    band: str,
    spws: list[int],
    flux_densities: list[list[float]],
    center_frequencies: list[float],
) -> tuple[list, list, list, list]:
    """Collect log-space freq/flux/err/spw lists for one source+band."""
    lfreqs, lfds, lerrs, uspws = [], [], [], []
    for i in idx:
        if spws[i] >= len(center_frequencies):
            continue
        cf = center_frequencies[spws[i]]
        if find_EVLA_band(cf / 1e9) != band:
            continue
        fd, fe = flux_densities[i]
        lfreqs.append(np.log10(cf))
        lfds.append(np.log10(fd))
        ratio = fe / fd if fd else 0.0
        lerrs.append(np.log10(np.e) * ratio if ratio else 1e-6)
        uspws.append(spws[i])
    return lfreqs, lfds, lerrs, uspws


def _fit_power_law(
    fluxscale_result: dict, center_frequencies: list[float]
) -> list[list]:
    """
    Fit log(S) = log_s0 + spix * log(ν) per source per band.

    Returns list of [source, spws, fluxdensity, spix, SNR, reffreq_ghz].
    """
    sources, flux_densities, spws = _parse_fluxscale(fluxscale_result)

    results = []
    for source in np.unique(sources):
        idx = np.where(np.array(sources) == source)[0]
        bands = {
            find_EVLA_band(center_frequencies[spws[i]] / 1e9)
            for i in idx
            if spws[i] < len(center_frequencies)
        }
        for band in bands:
            lfreqs, lfds, lerrs, uspws = _band_data(
                idx, band, spws, flux_densities, center_frequencies
            )
            if not lfds:
                continue
            aa, bb, snr = _fit_one_band(lfreqs, lfds, lerrs)
            reffreq = 10 ** lfreqs[0] / 1e9  # GHz
            fluxd = 10 ** (aa + bb * lfreqs[0])
            log.info(
                "%s %s: flux=%.3f Jy  spix=%.3f  SNR=%.1f", source, band, fluxd, bb, snr
            )
            results.append([source, uspws, fluxd, bb, snr, reffreq])

    return results


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

def run_fluxboot(ctx: PipelineContext) -> PipelineContext:
    """
    Bootstrap flux scale from primary calibrator to all transfer fields.

    Reads from context
    -----------------
    calibrators_ms, msname, table_flux_gaincal, flux_field_select_string,
    center_frequencies, scratch

    Writes to context
    -----------------
    table_flux_gaincal_fcal : str
    """
    cal_ms = ctx["calibrators_ms"]
    ms = ctx["msname"]
    t_flux = ctx["table_flux_gaincal"]
    flux_field = ctx["flux_field_select_string"]
    center_frequencies = ctx["center_frequencies"]

    t_fcal = str(Path(ctx["workdir"]) / "fluxgaincalFcal.g")
    rmtables(t_fcal)

    log.info("Running fluxscale: reference=%s", flux_field)
    fluxscale_result = fluxscale(
        vis=cal_ms,
        caltable=t_flux,
        fluxtable=t_fcal,
        reference=[flux_field],
        transfer=[""],
        listfile="",
        append=False,
        refspwmap=[-1],
        incremental=False,
        fitorder=1,
    )

    fitting_results = _fit_power_law(fluxscale_result, center_frequencies)

    # Set fitted power-law model on both calibrators.ms and full MS
    for result in fitting_results:
        source, uspws, fluxd, spix, snr, reffreq_ghz = result
        if abs(spix) > 5.0:
            log.warning(
                "%s: |spix|=%.2f > 5 — flux scale may be unreliable", source, spix
            )
        for spw_i in uspws:
            for vis in (cal_ms, ms):
                try:
                    setjy(
                        vis=vis,
                        field=str(source),
                        spw=str(spw_i),
                        selectdata=False,
                        scalebychan=True,
                        standard="manual",
                        fluxdensity=[fluxd, 0, 0, 0],
                        spix=spix,
                        reffreq=f"{reffreq_ghz}GHz",
                        usescratch=True,
                    )
                except Exception as exc:
                    log.warning(
                        "setjy failed for %s spw %d in %s: %s", source, spw_i, vis, exc
                    )

    ctx["table_flux_gaincal_fcal"] = t_fcal
    log.info("Flux bootstrapping complete — MODEL column updated for all calibrators")
    return ctx
