"""Apply the same BioSCape AVIRIS-NG trait models to an EMIT L2A scene,
for a same-season cross-sensor comparison against the Tanager trait maps.

EMIT date/coverage decision (see CLAUDE.md "EMIT scene selection" for the
full table): no EMIT overpass exists near Tanager's actual date
(2025-05-04) -- nearest 2025 passes are 71-101 days off-season. The
closest seasonal match in the whole archive (2024-05-18, 15 days off) only
clips ~17% of the scene footprint (the swath edge cuts across our AOI).
Chose 2026-03-02 instead: 63 days off-season, but ONE granule gives 100%
footprint coverage, which matters more for a full trait-map comparison
than shaving off a few weeks of seasonal offset against a scene that's
mostly missing data.

Unlike Tanager, EMIT already carries its own FWHM (no need to borrow it
from a reference flightline) and ships its own GLT (glt_x/glt_y) for
orthorectifying the downtrack/crosstrack swath directly onto a WGS84
grid via the file's own geotransform -- no per-pixel lat/lon KDTree
lookup needed like step2 does for Tanager.
"""
import json
import os
import sys

import netCDF4 as nc
import numpy as np
import rasterio
from rasterio.transform import Affine

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from step2_apply_trait_model import (
    get_aviris_ng_reference, load_trait_model, build_resampling_matrix,
    apply_trait_model, NO_DATA,
)

EMIT_NC = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/emit_comparison/"
    "EMIT_L2A_RFL_001_20260302T092128_2606106_004.nc"
)
AVIRIS_REFERENCE_NC = (
    "/Volumes/Enspec/projects/BioScape/Lines_Corrected_Hyperspectral/"
    "ang20231022t092801_000_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1.nc"
)
TRAIT_MODEL_DIR = (
    "/Users/henryfrye/Dropbox/Intellectual_Endeavours/Wisconsin/"
    "Airborne_Apply_Models/bioscape/trait_models/"
)
# Same variant choice as step2 -- FULL-uvf for all four. Tried IR-uvf
# (the lab's general same-sensor convention) and reverted after checking
# against CWM field data: IR-uvf was worse for every trait in this
# cross-sensor context. See step2's comment / CLAUDE.md "IR-uvf vs
# FULL-uvf: a real detour" for the numbers.
TRAIT_MODELS = [
    TRAIT_MODEL_DIR + "plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa.json",
    TRAIT_MODEL_DIR + "plsr__sampled_Calcium_mg_per_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa.json",
    TRAIT_MODEL_DIR + "plsr__sampled_Lignin_recal_mg_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa.json",
    TRAIT_MODEL_DIR + "plsr__sampled_Cellulose_mg_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa.json",
]
OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"

# Same AOI used throughout this project (Tanager scene footprint).
AOI_LON = (19.33433183204153, 19.614125009380633)
AOI_LAT = (-33.76373629693137, -33.55413777965097)


def read_emit_scene(nc_path):
    ds = nc.Dataset(nc_path)
    reflectance = ds.variables["reflectance"][:]  # (downtrack, crosstrack, bands)
    sbp = ds.groups["sensor_band_parameters"]
    loc = ds.groups["location"]

    scene = {
        "reflectance": np.moveaxis(np.array(reflectance), -1, 0),  # -> (bands, downtrack, crosstrack)
        "wavelengths": np.array(sbp.variables["wavelengths"][:], dtype=float),
        "fwhm": np.array(sbp.variables["fwhm"][:], dtype=float),
        "good_wavelengths": np.array(sbp.variables["good_wavelengths"][:], dtype=bool),
        "glt_x": np.array(loc.variables["glt_x"][:], dtype=np.int32),
        "glt_y": np.array(loc.variables["glt_y"][:], dtype=np.int32),
        "geotransform": np.array(ds.getncattr("geotransform"), dtype=float),
        "fill_value": reflectance.fill_value if hasattr(reflectance, "fill_value") else -9999.0,
    }
    ds.close()
    return scene


def apply_glt(swath_bands, glt_x, glt_y, fill_value=NO_DATA):
    """Warp (n_bands, downtrack, crosstrack) swath arrays onto the GLT's
    ortho grid. glt_x/glt_y are 1-indexed crosstrack/downtrack coordinates
    into the swath, 0 = fill (no data at that ortho pixel).
    """
    n_bands = swath_bands.shape[0]
    ortho_shape = glt_x.shape
    fill_mask = (glt_x != 0) & (glt_y != 0)

    out = np.full((n_bands, *ortho_shape), fill_value, dtype=np.float32)
    gy = glt_y[fill_mask] - 1
    gx = glt_x[fill_mask] - 1
    for b in range(n_bands):
        band_out = out[b]
        band_out[fill_mask] = swath_bands[b, gy, gx]
    return out, fill_mask


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading AVIRIS-NG reference FWHM...")
    aviris_wl, aviris_fwhm = get_aviris_ng_reference(AVIRIS_REFERENCE_NC)

    print("Reading EMIT scene...")
    scene = read_emit_scene(EMIT_NC)
    print(f"  reflectance shape: {scene['reflectance'].shape}")
    print(f"  ortho grid shape: {scene['glt_x'].shape}")

    gt = scene["geotransform"]
    transform = Affine(gt[1], gt[2], gt[0], gt[4], gt[5], gt[3])
    n_rows, n_cols = scene["glt_x"].shape

    for model_path in TRAIT_MODELS:
        print(f"\nApplying {os.path.basename(model_path)}")
        trait_model = load_trait_model(model_path, aviris_wl, aviris_fwhm)

        matrix, caveat_bands = build_resampling_matrix(
            trait_model["wavelengths"], trait_model["fwhm"],
            scene["wavelengths"], scene["fwhm"], scene["good_wavelengths"],
        )
        if caveat_bands:
            print(f"  NOTE: {len(caveat_bands)} target bands can't be sharpened to EMIT's native "
                  f"resolution there (EMIT FWHM ~8.5nm vs AVIRIS-NG ~5.6-6.0nm -- expected to be most bands).")

        bands, downtrack, crosstrack = scene["reflectance"].shape
        source_flat = scene["reflectance"].reshape(bands, -1)
        resampled = (matrix @ source_flat).reshape(len(trait_model["wavelengths"]), downtrack, crosstrack)

        trait_mean, trait_std, range_mask = apply_trait_model(resampled, trait_model)

        stack = np.stack([trait_mean, trait_std, range_mask.astype(np.float32)])
        gridded, fill_mask = apply_glt(stack, scene["glt_x"], scene["glt_y"])
        gridded[:, ~fill_mask] = NO_DATA

        out_path = os.path.join(
            OUTPUT_DIR, f"emit_20260302_{trait_model['name']}.tif",
        )
        with rasterio.open(
            out_path, "w", driver="GTiff", height=n_rows, width=n_cols, count=3,
            dtype="float32", crs="EPSG:4326", transform=transform,
            nodata=NO_DATA, compress="lzw",
        ) as dst:
            names = [f"{trait_model['name']}_mean", f"{trait_model['name']}_std", "range_mask"]
            for i, name in enumerate(names, start=1):
                dst.write(gridded[i - 1], i)
                dst.set_band_description(i, name)
        print(f"  Wrote {out_path}")


if __name__ == "__main__":
    main()
