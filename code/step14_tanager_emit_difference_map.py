"""Tanager vs. EMIT difference map (EMIT - Tanager), per pixel, all 4
Cape traits -- companion to step11 (side-by-side) and step7 (aggregate
density comparison). step11's docstring flagged reprojecting EMIT onto
Tanager's exact grid "keeps the door open for a difference map later
without redoing the regridding" -- this is that map.

Diverging colormap centered at 0, symmetric range from the p2-p98 of
|difference| (not the full min/max, which lets a handful of extreme
edge-of-mask pixels wash out the color scale for the bulk of the scene).
Same veg_mask as step11 for consistent masking across all 4 panels.
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

TRAITS = [
    ("Nitrogen", "Nitrogen_merged_cwm_iter_mean", "mg/g"),
    ("Calcium", "Calcium_mg_per_g_cwm_iter_mean", "mg/g"),
    ("Lignin", "Lignin_recal_mg_g_cwm_iter_mean", "mg/g"),
    ("Cellulose", "Cellulose_mg_g_cwm_iter_mean", "mg/g"),
]


def load_veg_mask():
    with rasterio.open(VEG_MASK_TIF) as src:
        veg_mask = src.read(3)
        nodata = src.nodata
    return (veg_mask == 1) & (veg_mask != nodata)


def load_tanager(stem, veg_mask):
    path = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"
    with rasterio.open(path) as src:
        mean = src.read(1)
        rmask = src.read(3)
        nodata = src.nodata
        transform, crs, shape = src.transform, src.crs, src.shape
    arr = np.where((mean == nodata) | (rmask != 1) | (~veg_mask), np.nan, mean)
    return arr, transform, crs, shape


def reproject_emit(stem, tanager_transform, tanager_crs, tanager_shape, veg_mask):
    path = TRAIT_OUTPUT_DIR + f"emit_20260302_plsr__sampled_{stem}__FULL-uvf__ideny__rep__boa.tif"
    with rasterio.open(path) as src:
        mean = src.read(1).astype(np.float32)
        rmask = src.read(3)
        nodata = src.nodata
        mean = np.where((mean == nodata) | (rmask != 1), np.nan, mean)
        src_transform, src_crs = src.transform, src.crs

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
    fig, axes = plt.subplots(2, 2, figsize=(10, 9))

    for ax, (label, stem, units) in zip(axes.flat, TRAITS):
        tanager_arr, transform, crs, shape = load_tanager(stem, veg_mask)
        emit_arr = reproject_emit(stem, transform, crs, shape, veg_mask)
        diff = emit_arr - tanager_arr

        valid = diff[~np.isnan(diff)]
        bound = np.percentile(np.abs(valid), 98)

        cmap = matplotlib.colormaps["RdBu_r"].copy()
        cmap.set_bad("lightgray")
        im = ax.imshow(diff, cmap=cmap, vmin=-bound, vmax=bound)
        ax.set_title(f"{label} (EMIT - Tanager, {units})", fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(units, fontsize=9)

        print(f"{label}: median diff={np.median(valid):.2f}, mean diff={np.mean(valid):.2f}, "
              f"98th pct |diff|={bound:.2f}")

    fig.suptitle(
        "Tanager vs. EMIT: per-pixel difference (EMIT - Tanager), same AOI\n"
        "(blue = EMIT higher, red = Tanager higher; scale = 2nd-98th percentile of |difference| per trait)",
        fontsize=11,
    )
    out_path = FIGURES_DIR + "tanager_emit_difference_map.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
