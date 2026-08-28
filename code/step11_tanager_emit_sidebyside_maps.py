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

Masking (fixed 2026-08-27, per Henry's review): originally masked each
panel by only its own trait model's range_mask (band 3) -- a diagnostic
"is this prediction within plausible training bounds" check, NOT a real
vegetation/water mask. That made masking look inconsistent across panels
(e.g. the lake showed through on EMIT's Calcium map but not elsewhere)
because it's coincidental whether a given trait+sensor combination
happens to predict an in-bounds-but-wrong value over water. Now applies
step4's real NDVI-derived veg_mask -- computed once on the Tanager grid,
reused for BOTH columns (both are already on that grid) -- so water/
urban areas are excluded identically everywhere, on top of each panel's
own range_mask for physically-implausible-but-vegetated pixels.
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
VEG_MASK_TIF = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_ndvi_shadow_mask.tif"

# (stem, units, CWM field p5-p95 range -- same values as step5_ternary_map.py,
# colormap chosen to stay visually saturated at the low end -- a light-
# starting sequential map (e.g. BuPu) becomes indistinguishable from masked
# whenever a trait's predictions cluster low in-scene, as Cellulose's do)
TRAITS = [
    ("Nitrogen", "Nitrogen_merged_cwm_iter_mean", "mg/g", (4.71, 23.51), "YlGn"),
    ("Calcium", "Calcium_mg_per_g_cwm_iter_mean", "mg/g", (1.51, 16.67), "PuBu"),
    ("Lignin", "Lignin_recal_mg_g_cwm_iter_mean", "mg/g", (55.83, 245.03), "YlOrBr"),
    ("Cellulose", "Cellulose_mg_g_cwm_iter_mean", "mg/g", (79.76, 316.16), "viridis"),
]


def load_veg_mask():
    with rasterio.open(VEG_MASK_TIF) as src:
        veg_mask = src.read(3)
        nodata = src.nodata
    return (veg_mask == 1) & (veg_mask != nodata)


def load_masked(path, veg_mask):
    with rasterio.open(path) as src:
        mean = src.read(1)
        rmask = src.read(3)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
    mean = np.where((mean == nodata) | (rmask != 1) | (~veg_mask), np.nan, mean)
    return mean, transform, crs


def reproject_to_tanager(emit_path, tanager_transform, tanager_crs, tanager_shape, veg_mask):
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
    dst[~veg_mask] = np.nan
    return dst


def main():
    veg_mask = load_veg_mask()
    # 2 rows x 4 cols (two trait-pairs per row) instead of 4 rows x 2 cols --
    # the tall 1-column layout left large blank gaps when scaled to page
    # width in the report (2026-08-29, per Henry's review).
    fig, axes = plt.subplots(2, 4, figsize=(18, 9))

    for i, (label, stem, units, (lo, hi), cmap_name) in enumerate(TRAITS):
        row, pair = divmod(i, 2)
        ax_t, ax_e = axes[row, pair * 2], axes[row, pair * 2 + 1]
        cmap = matplotlib.colormaps[cmap_name].copy()
        cmap.set_bad("lightgray")

        tanager_path = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"
        emit_path = TRAIT_OUTPUT_DIR + f"emit_20260302_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"

        tanager_arr, tanager_transform, tanager_crs = load_masked(tanager_path, veg_mask)
        emit_arr = reproject_to_tanager(emit_path, tanager_transform, tanager_crs, tanager_arr.shape, veg_mask)

        im = ax_t.imshow(tanager_arr, cmap=cmap, vmin=lo, vmax=hi)
        ax_e.imshow(emit_arr, cmap=cmap, vmin=lo, vmax=hi)

        ax_t.set_title(f"{label} ({units})\nTanager", fontsize=13)
        ax_e.set_title(f"{label} ({units})\nEMIT", fontsize=13)
        ax_t.set_xticks([]); ax_t.set_yticks([])
        ax_e.set_xticks([]); ax_e.set_yticks([])

        cbar = fig.colorbar(im, ax=[ax_t, ax_e], fraction=0.04, pad=0.03)
        cbar.ax.tick_params(labelsize=10)

    fig.subplots_adjust(hspace=0.3, wspace=0.25, top=0.86)
    fig.suptitle(
        "Tanager (2025-05-04) vs. EMIT (2026-03-02) predicted trait maps, same AOI\n"
        "(color scale = region-wide CWM field-data p5-p95, not either sensor's own range;\n"
        "gray = non-vegetated (NDVI mask) or outside each model's diagnostic range)",
        fontsize=14,
    )
    out_path = FIGURES_DIR + "tanager_vs_emit_sidebyside_maps.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
