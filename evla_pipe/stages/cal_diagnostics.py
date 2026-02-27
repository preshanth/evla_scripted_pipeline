"""
Calibrator diagnostic imaging stage.

For every calibrator field (flux, bandpass, delay, phase, amp, pol), images
each spectral window using a shallow clean (niter=500).  Polarization
calibrators are imaged in full IQUV; all others in Stokes I only.

Cell size is derived from the maximum baseline length and per-SPW centre
frequency stored in context by run_msmd — no extra MS queries needed.

For each field/SPW:
  1. tclean (niter=500, natural weighting, 256x256 px)
  2. imstat → peak_jy, rms_jy
  3. exportfits → .fits
  4. astropy + matplotlib → PNG in workdir/plots/
  5. Expected flux from ctx["flux_fitting_results"] power-law fit
  6. Cleanup auxiliary tclean products

Context keys read
-----------------
msname, field_names, center_frequencies, field_spws,
max_baseline_m, flux_fitting_results,
flux_field_list, bandpass_field_list, delay_field_list,
phase_field_list, amp_field_list,
pol_angle_field_list, pol_lkg_field_list

Context keys written
--------------------
cal_image_results : list[dict]
    {field_id, field_name, spw, freq_ghz, stokes,
     peak_jy, rms_jy, expected_jy, ratio, png}
"""

import logging
import shutil
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits as astrofits
from casatasks import exportfits, imstat, rmtables, tclean

from evla_pipe.context import PipelineContext
from evla_pipe.simple_utils import field_label

matplotlib.use("Agg")  # headless — no display required

log = logging.getLogger(__name__)

_SPEED_OF_LIGHT = 2.99792458e8  # m/s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_name(name: str) -> str:
    """Sanitize a field name for use in file paths."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _cell_arcsec(freq_hz: float, max_baseline_m: float) -> str:
    """Half-beam cell size in arcsec from frequency and maximum baseline."""
    wavelength_m = _SPEED_OF_LIGHT / freq_hz
    resolution_rad = wavelength_m / max_baseline_m
    cell_arcsec = resolution_rad * 206265.0 / 2.0
    return f"{cell_arcsec:.4f}arcsec"


def _expected_flux(
    field_name: str, freq_hz: float, flux_results: list[dict]
) -> float | None:
    """
    Extrapolate expected flux density from a power-law fit in flux_fitting_results.

    Returns None if no matching source is found or the fit is incomplete.
    """
    freq_ghz = freq_hz / 1e9
    fname_lower = field_name.lower()
    for result in flux_results:
        source = result.get("source", "")
        if source.lower() in fname_lower or fname_lower in source.lower():
            flux_jy = result.get("flux_jy", 0.0)
            spix = result.get("spix", 0.0)
            reffreq_ghz = result.get("reffreq_ghz", 1.0)
            if reffreq_ghz > 0 and flux_jy > 0:
                return float(flux_jy * (freq_ghz / reffreq_ghz) ** spix)
    return None


def _fits_to_png(fits_path: str, png_path: str, title: str) -> None:
    """
    Render a CASA-exported FITS image to PNG.

    Handles both single-Stokes (2D after squeeze) and multi-Stokes (3D)
    images.  Multi-Stokes planes are shown in a 2×2 grid labelled I,Q,U,V.
    """
    with astrofits.open(fits_path) as hdul:
        data = hdul[0].data  # typically (stokes, freq, y, x) from CASA

    data = np.squeeze(data).astype(float)

    if data.ndim == 2:
        stokes_planes = [("I", data)]
    elif data.ndim == 3:
        labels = ["I", "Q", "U", "V"][: data.shape[0]]
        stokes_planes = list(zip(labels, data))
    else:
        log.warning("Unexpected FITS data shape %s — skipping PNG", data.shape)
        return

    n = len(stokes_planes)
    ncols = min(n, 2)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(
        nrows, ncols, figsize=(5 * ncols, 4.5 * nrows), squeeze=False
    )
    fig.suptitle(title, fontsize=11)

    for idx, (label, plane) in enumerate(stokes_planes):
        ax = axes[idx // ncols][idx % ncols]
        vmax = float(np.nanpercentile(np.abs(plane), 99.5))
        vmax = vmax if vmax > 0 else 1.0
        im = ax.imshow(
            plane,
            origin="lower",
            cmap="RdBu_r",
            vmin=-vmax,
            vmax=vmax,
            aspect="auto",
        )
        ax.set_title(f"Stokes {label}", fontsize=9)
        ax.set_xlabel("RA pixel", fontsize=8)
        ax.set_ylabel("Dec pixel", fontsize=8)
        ax.tick_params(labelsize=7)
        plt.colorbar(im, ax=ax, label="Jy/beam", pad=0.02)

    for idx in range(n, nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    plt.tight_layout()
    plt.savefig(png_path, dpi=100, bbox_inches="tight")
    plt.close(fig)


def _cleanup_tclean(image_base: str) -> None:
    """Remove all tclean auxiliary products (keep nothing — PNG is the output)."""
    for suffix in [
        ".image",
        ".psf",
        ".residual",
        ".model",
        ".pb",
        ".sumwt",
        ".mask",
        ".fits",
    ]:
        p = Path(image_base + suffix)
        if p.exists():
            shutil.rmtree(str(p)) if p.is_dir() else p.unlink()


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def run_cal_diagnostics(ctx: PipelineContext) -> PipelineContext:
    """
    Shallow-clean image every calibrator field per SPW and record peak/RMS.

    Reads from context
    -----------------
    msname, field_names, center_frequencies, field_spws, max_baseline_m,
    flux_fitting_results, *_field_list keys

    Writes to context
    -----------------
    cal_image_results : list[dict]
    """
    ms = ctx["msname"]
    field_names = ctx.get("field_names", [])
    center_frequencies = ctx.get("center_frequencies", [])
    field_spws = ctx.get("field_spws", [])
    max_baseline_m = ctx.get("max_baseline_m", 0.0)
    flux_results = ctx.get("flux_fitting_results", [])

    plots_dir = Path(ctx["workdir"]) / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    # Identify all calibrator fields and which are polarization calibrators
    pol_fids = set(
        ctx.get("pol_angle_field_list", []) + ctx.get("pol_lkg_field_list", [])
    )
    cal_fid_sets = [
        ctx.get("flux_field_list", []),
        ctx.get("bandpass_field_list", []),
        ctx.get("delay_field_list", []),
        ctx.get("phase_field_list", []),
        ctx.get("amp_field_list", []),
        ctx.get("pol_angle_field_list", []),
        ctx.get("pol_lkg_field_list", []),
    ]
    all_cal_fids = sorted({fid for lst in cal_fid_sets for fid in lst})

    if not all_cal_fids:
        log.warning("No calibrator fields identified — skipping cal_diagnostics")
        ctx["cal_image_results"] = []
        return ctx

    results: list[dict] = []

    for field_id in all_cal_fids:
        fname = field_names[field_id] if field_id < len(field_names) else str(field_id)
        stokes = "IQUV" if field_id in pol_fids else "I"
        spws_for_field = field_spws[field_id] if field_id < len(field_spws) else []

        log.info(
            "cal_diagnostics: imaging field=%s, stokes=%s, %d spws",
            field_label(ctx, str(field_id)),
            stokes,
            len(spws_for_field),
        )

        for spw_id in spws_for_field:
            if spw_id >= len(center_frequencies):
                continue
            freq_hz = center_frequencies[spw_id]
            if max_baseline_m > 0:
                cell = _cell_arcsec(freq_hz, max_baseline_m)
            else:
                cell = "1arcsec"
            image_base = str(
                plots_dir / f"caldiag_{field_id}_{_safe_name(fname)}_spw_{spw_id}"
            )

            try:
                rmtables(image_base + ".*")
                log.info(
                    "  tclean: field=%d spw=%d  cell=%s  stokes=%s",
                    field_id,
                    spw_id,
                    cell,
                    stokes,
                )
                tclean(
                    vis=ms,
                    imagename=image_base,
                    field=str(field_id),
                    spw=str(spw_id),
                    datacolumn="corrected",
                    stokes=stokes,
                    cell=[cell],
                    imsize=[256, 256],
                    niter=500,
                    threshold="0mJy",
                    deconvolver="hogbom",
                    gridder="standard",
                    weighting="natural",
                    pbcor=False,
                    interactive=False,
                )

                # Measure peak and RMS from CASA image before exporting
                peak_jy, rms_jy = 0.0, 0.0
                image_path = image_base + ".image"
                if Path(image_path).exists():
                    stats = imstat(imagename=image_path)
                    peak_jy = float(stats.get("max", [0.0])[0])
                    rms_jy = float(stats.get("rms", [0.0])[0])

                # Export to FITS then render PNG
                fits_path = image_base + ".fits"
                exportfits(
                    imagename=image_path,
                    fitsimage=fits_path,
                    overwrite=True,
                )
                png_path = image_base + ".png"
                title = (
                    f"Field {field_id} ({fname})  SPW {spw_id}"
                    f"  {freq_hz / 1e9:.3f} GHz  Stokes {stokes}"
                )
                _fits_to_png(fits_path, png_path, title)

                expected_jy = _expected_flux(fname, freq_hz, flux_results)
                ratio = peak_jy / expected_jy if expected_jy else None

                log.info(
                    "  field=%d spw=%d  peak=%.4f Jy  rms=%.2f mJy"
                    "  expected=%s Jy  ratio=%s",
                    field_id,
                    spw_id,
                    peak_jy,
                    rms_jy * 1e3,
                    f"{expected_jy:.4f}" if expected_jy else "N/A",
                    f"{ratio:.3f}" if ratio else "N/A",
                )

                results.append(
                    {
                        "field_id": field_id,
                        "field_name": fname,
                        "spw": spw_id,
                        "freq_ghz": round(freq_hz / 1e9, 4),
                        "stokes": stokes,
                        "peak_jy": round(peak_jy, 6),
                        "rms_jy": round(rms_jy, 6),
                        "expected_jy": (round(expected_jy, 6) if expected_jy else None),
                        "ratio": round(ratio, 4) if ratio else None,
                        "png": png_path,
                    }
                )

            except Exception:
                log.exception(
                    "cal_diagnostics failed for field %d spw %d — continuing",
                    field_id,
                    spw_id,
                )
            finally:
                _cleanup_tclean(image_base)

    ctx["cal_image_results"] = results
    log.info("cal_diagnostics complete: %d field/SPW images produced", len(results))
    return ctx
