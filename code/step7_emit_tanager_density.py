"""Density distribution comparison: Tanager vs. EMIT predicted trait
values, clipped to the same AOI (the Tanager scene footprint).

Companion to the percentile comparison in CLAUDE.md "EMIT vs. Tanager
comparison" -- same range_mask-valid, AOI-clipped pixel sets, plotted as
overlaid KDE curves instead of a percentile table.
"""
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
FIGURES_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/figures/"
TANAGER_STEM = "20250504_092952_87_4001_basic_sr_hdf5"

TRAITS = {
    "Nitrogen": ("Nitrogen_merged_cwm_iter_mean", "mg/g"),
    "Calcium": ("Calcium_mg_per_g_cwm_iter_mean", "mg/g"),
    "Lignin": ("Lignin_recal_mg_g_cwm_iter_mean", "mg/g"),
    "Cellulose": ("Cellulose_mg_g_cwm_iter_mean", "mg/g"),
}


def load_range_valid(path, window=None):
    with rasterio.open(path) as src:
        mean = src.read(1, window=window)
        rmask = src.read(3, window=window)
        nodata = src.nodata
    return mean[(mean != nodata) & (rmask == 1)]


def main():
    tanager_path = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif"
    with rasterio.open(tanager_path) as src:
        tanager_bounds = src.bounds
        tanager_crs = src.crs
    lon_min, lat_min, lon_max, lat_max = transform_bounds(tanager_crs, "EPSG:4326", *tanager_bounds)

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    for ax, (label, (stem, units)) in zip(axes.flat, TRAITS.items()):
        tanager_tif = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"
        emit_tif = TRAIT_OUTPUT_DIR + f"emit_20260302_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"

        tanager_vals = load_range_valid(tanager_tif)
        with rasterio.open(emit_tif) as src:
            window = from_bounds(lon_min, lat_min, lon_max, lat_max, src.transform)
        emit_vals = load_range_valid(emit_tif, window=window)

        lo = min(tanager_vals.min(), emit_vals.min())
        hi = max(tanager_vals.max(), emit_vals.max())
        x = np.linspace(lo, hi, 300)

        for vals, color, sensor_label in [(tanager_vals, "#d55e00", "Tanager (2025-05-04)"),
                                            (emit_vals, "#0072b2", "EMIT (2026-03-02)")]:
            kde = gaussian_kde(vals)
            ax.plot(x, kde(x), color=color, label=f"{sensor_label}, n={vals.size:,}", linewidth=1.8)
            ax.fill_between(x, kde(x), color=color, alpha=0.15)
            ax.axvline(np.median(vals), color=color, linestyle="--", linewidth=1, alpha=0.7)

        ax.set_title(f"{label} ({units})")
        ax.set_xlabel(units)
        ax.set_ylabel("density")
        ax.legend(fontsize=8)

    fig.suptitle("Predicted trait distributions, same AOI: Tanager vs. EMIT\n"
                  "(dashed lines = medians; range_mask-valid pixels only)", fontsize=12)
    fig.tight_layout()
    out_path = FIGURES_DIR + "emit_vs_tanager_density.png"
    fig.savefig(out_path, dpi=150)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
