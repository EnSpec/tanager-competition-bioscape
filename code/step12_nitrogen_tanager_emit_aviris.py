"""Three-way Nitrogen comparison: Tanager, EMIT, and BioSCape's own
airborne AVIRIS-NG mosaic (step10) -- companion to step11's Tanager-vs-
EMIT figure, kept separate rather than folded in as a third column there.

Why separate, not a 3rd column in step11: AVIRIS-NG only covers 30.6% of
this scene's footprint (a third column would be mostly gray elsewhere,
reading as a data problem rather than intentional partial coverage), and
3 of the 4 traits in step11 have a model-variant mismatch against the
precomputed AVIRIS-NG tiles (IR-uvf there vs. FULL-uvf here -- see
CLAUDE.md "IR-uvf vs FULL-uvf: a real detour"). Nitrogen's precomputed
AVIRIS-NG tile is IR-uvf too, so the variant mismatch is still present --
but its median matched almost exactly anyway (16.02 mg/g both, see
CLAUDE.md "AVIRIS-NG AOI mosaic + comparison"), so it's the one trait
where showing a three-way comparison is empirically supported rather
than assumed; the other three traits' numbers don't back that up as
confidently.

Same veg_mask applied to all three panels (not just AVIRIS-NG's own
per-tile masking, which is sensor/pipeline-native and not necessarily
consistent with step4's Tanager-derived mask) -- same fix step11 needed
for its Calcium/EMIT lake issue, applied here from the start.
"""
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
AVIRIS_MOSAIC_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/aviris_aoi_mosaic/"
FIGURES_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/figures/"
TANAGER_STEM = "20250504_092952_87_4001_basic_sr_hdf5"
VEG_MASK_TIF = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_ndvi_shadow_mask.tif"

LO, HI = 4.71, 23.51  # CWM field p5-p95, mg/g -- same as step5/step11
CMAP_NAME = "YlGn"


def load_veg_mask():
    with rasterio.open(VEG_MASK_TIF) as src:
        veg_mask = src.read(3)
        nodata = src.nodata
    return (veg_mask == 1) & (veg_mask != nodata)


def tanager_grid():
    path = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif"
    with rasterio.open(path) as src:
        return src.transform, src.crs, src.shape


def load_tanager(veg_mask):
    path = TRAIT_OUTPUT_DIR + f"{TANAGER_STEM}_plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif"
    with rasterio.open(path) as src:
        mean = src.read(1)
        rmask = src.read(3)
        nodata = src.nodata
    return np.where((mean == nodata) | (rmask != 1) | (~veg_mask), np.nan, mean)


def reproject_generic(src_path, band, tanager_transform, tanager_crs, tanager_shape, resampling, extra_mask_band=None):
    with rasterio.open(src_path) as src:
        arr = src.read(band).astype(np.float32)
        nodata = src.nodata
        if nodata is not None and not np.isnan(nodata):
            arr = np.where(arr == nodata, np.nan, arr)
        if extra_mask_band is not None:
            rmask = src.read(extra_mask_band)
            arr = np.where(rmask != 1, np.nan, arr)
        src_transform = src.transform
        src_crs = src.crs

    dst = np.full(tanager_shape, np.nan, dtype=np.float32)
    reproject(
        source=arr, destination=dst,
        src_transform=src_transform, src_crs=src_crs,
        dst_transform=tanager_transform, dst_crs=tanager_crs,
        resampling=resampling, src_nodata=np.nan, dst_nodata=np.nan,
    )
    return dst


def main():
    veg_mask = load_veg_mask()
    tanager_transform, tanager_crs, tanager_shape = tanager_grid()

    tanager_arr = load_tanager(veg_mask)

    emit_path = TRAIT_OUTPUT_DIR + "emit_20260302_plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif"
    emit_arr = reproject_generic(emit_path, 1, tanager_transform, tanager_crs, tanager_shape,
                                  Resampling.bilinear, extra_mask_band=3)
    emit_arr[~veg_mask] = np.nan

    aviris_path = AVIRIS_MOSAIC_DIR + "Nitrogen_mean_mosaic.tif"
    aviris_arr = reproject_generic(aviris_path, 1, tanager_transform, tanager_crs, tanager_shape,
                                    Resampling.average)
    aviris_arr[~veg_mask] = np.nan

    cmap = matplotlib.colormaps[CMAP_NAME].copy()
    cmap.set_bad("lightgray")

    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    panels = [
        ("Tanager\n(2025-05-04)", tanager_arr),
        ("EMIT\n(2026-03-02)", emit_arr),
        ("AVIRIS-NG (airborne)\n(2023-11-22/25, 30.6% coverage)", aviris_arr),
    ]
    for ax, (title, arr) in zip(axes, panels):
        im = ax.imshow(arr, cmap=cmap, vmin=LO, vmax=HI)
        ax.set_title(title, fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])

    cbar = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
    cbar.set_label("Nitrogen (mg/g)", fontsize=10)

    fig.suptitle(
        "Nitrogen: Tanager vs. EMIT vs. BioSCape's own airborne AVIRIS-NG\n"
        "(color scale = region-wide CWM field-data p5-p95; gray = non-vegetated, out-of-range, "
        "or (AVIRIS-NG only) outside flightline coverage)",
        fontsize=10,
    )
    out_path = FIGURES_DIR + "nitrogen_tanager_emit_aviris.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")

    for name, arr in panels:
        valid = arr[~np.isnan(arr)]
        print(f"{name.splitlines()[0]}: n_valid={valid.size}, median={np.median(valid):.2f}" if valid.size else f"{name}: no valid pixels")


if __name__ == "__main__":
    main()
