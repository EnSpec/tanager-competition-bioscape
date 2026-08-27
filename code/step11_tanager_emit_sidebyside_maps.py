"""Side-by-side Tanager vs. EMIT trait maps, same AOI, same color scale
per trait -- the figure Henry asked for directly, companion to the
density-distribution comparison in step7.

EMIT is reprojected onto Tanager's exact grid (EPSG:32734, 30 m,
Planet_Ortho_Framing) via rasterio.warp so both panels show pixel-
identical extents -- not required for a side-by-side figure, but keeps
the door open for a difference map later without redoing the regridding.

Color scale per trait is the region-wide CWM field-data p5-p95 (same
values step5's ternary map uses), not either sensor's own predicted
range -- deliberately, for the same reason step5 does it: an
independent, field-grounded scale makes cross-sensor differences and
biases visible instead of each panel auto-stretching to look equally
"good" regardless of how biased its predictions are.
"""
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
FIGURES_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/figures/"
TANAGER_STEM = "20250504_092952_87_4001_basic_sr_hdf5"

# (stem, units, CWM field p5-p95 range -- same values as step5_ternary_map.py)
TRAITS = [
    ("Nitrogen", "Nitrogen_merged_cwm_iter_mean", "mg/g", (4.71, 23.51), "YlGn"),
    ("Calcium", "Calcium_mg_per_g_cwm_iter_mean", "mg/g", (1.51, 16.67), "PuBu"),
    ("Lignin", "Lignin_recal_mg_g_cwm_iter_mean", "mg/g", (55.83, 245.03), "YlOrBr"),
    ("Cellulose", "Cellulose_mg_g_cwm_iter_mean", "mg/g", (79.76, 316.16), "BuPu"),
]


def load_masked(path):
    with rasterio.open(path) as src:
        mean = src.read(1)
        rmask = src.read(3)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
    mean = np.where((mean == nodata) | (rmask != 1), np.nan, mean)
    return mean, transform, crs


def reproject_to_tanager(emit_path, tanager_transform, tanager_crs, tanager_shape):
    with rasterio.open(emit_path) as src:
        mean = src.read(1).astype(np.float32)
        rmask = src.read(3)
        nodata = src.nodata
        mean = np.where((mean == nodata) | (rmask != 1), np.nan, mean)
        src_transform = src.transform
        src_crs = src.crs

    dst = np.full(tanager_shape, np.nan, dtype=np.float32)
    reproject(
        source=mean, destination=dst,
        src_transform=src_transform, src_crs=src_crs,
        dst_transform=tanager_transform, dst_crs=tanager_crs,
        resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan,
    )
    return dst


def main():
    fig, axes = plt.subplots(len(TRAITS), 2, figsize=(9, 4 * len(TRAITS)))

    for row, (label, stem, units, (lo, hi), cmap) in enumerate(TRAITS):
        tanager_path = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"
        emit_path = TRAIT_OUTPUT_DIR + f"emit_20260302_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"

        tanager_arr, tanager_transform, tanager_crs = load_masked(tanager_path)
        emit_arr = reproject_to_tanager(emit_path, tanager_transform, tanager_crs, tanager_arr.shape)

        ax_t, ax_e = axes[row]
        im = ax_t.imshow(tanager_arr, cmap=cmap, vmin=lo, vmax=hi)
        ax_e.imshow(emit_arr, cmap=cmap, vmin=lo, vmax=hi)

        ax_t.set_ylabel(f"{label}\n({units})", fontsize=11)
        ax_t.set_xticks([]); ax_t.set_yticks([])
        ax_e.set_xticks([]); ax_e.set_yticks([])
        if row == 0:
            ax_t.set_title("Tanager (2025-05-04)", fontsize=12)
            ax_e.set_title("EMIT (2026-03-02)", fontsize=12)

        cbar = fig.colorbar(im, ax=[ax_t, ax_e], fraction=0.025, pad=0.02)
        cbar.set_label(units, fontsize=9)

    fig.suptitle(
        "Tanager vs. EMIT predicted trait maps, same AOI\n"
        "(color scale = region-wide CWM field-data p5-p95, not either sensor's own range;\n"
        "gray = masked out by each model's own diagnostic range check)",
        fontsize=11,
    )
    out_path = FIGURES_DIR + "tanager_vs_emit_sidebyside_maps.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
