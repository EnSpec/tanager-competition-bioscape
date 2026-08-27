"""Apply the colleague's SHIFT (Santa Barbara, CA)-trained PLSR trait
models to a Tanager scene over the SHIFT study area -- Mediterranean-
climate cross-region comparison against the Cape models (step2/step6).

Scene: 20250407_192247_40_4001_basic_sr_hdf5.h5, chosen by Henry as
close to SHIFT's growing-season training window. Confirmed on download:
lat 34.00-34.22, lon -119.02 to -118.68 -- Santa Barbara area, EPSG:32611
(UTM 11N), same basic_sr_hdf5 schema as the Cape scene (426 bands,
376-2499 nm).

Unlike the BioSCape/AVIRIS-NG models, these SHIFT jsons carry their own
real FWHM already (spectrometer "avc+neon" -- AVIRIS-Classic + NEON
training data) -- no need to borrow a reference flightline's FWHM like
step2/step6 do. They also use a 215-band, 1003-2400 nm IR-only grid
(narrower than the Cape "FULL-uvf" 341-band range) and, for LMA and
Calcium specifically, a sqrt Y-transform (fit on sqrt(trait), so
predictions need squaring -- implemented as a step2 change, not
duplicated here). Y_transform is None for nitrogen/lignin/cellulose --
checked each model file directly rather than assuming only LMA needed it,
since the colleague only mentioned LMA but Calcium turned out to have the
same sqrt transform.
"""
import glob
import json
import os

import numpy as np

from step2_apply_trait_model import (
    read_tanager_scene, build_resampling_matrix, apply_trait_model,
    grid_swath_to_ortho, write_geotiff, NO_DATA,
)

CA_H5 = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/raw_h5/"
    "20250407_192247_40_4001_basic_sr_hdf5.h5"
)
SHIFT_MODEL_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/shift_models_Aug2026/"
OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"


def load_shift_trait_model(json_path):
    with open(json_path, "r") as f:
        model = json.load(f)

    y_transform_list = model["model"].get("Y_transform", [None])
    y_transform = y_transform_list[0] if y_transform_list else None

    return {
        "name": model["name"],
        "units": model["units"],
        "wavelengths": np.array(model["wavelengths"], dtype=float),
        "fwhm": np.array(model["fwhm"], dtype=float),
        "transform": model["model"]["transform"],
        "y_transform": y_transform,
        "coefficients": np.array(model["model"]["coefficients"]),
        "intercepts": np.array(model["model"]["intercepts"]),
        "diagnostics": model["model_diagnostics"],
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Reading California Tanager scene...")
    scene = read_tanager_scene(CA_H5)
    print(f"  reflectance shape: {scene['reflectance'].shape}")

    model_paths = sorted(glob.glob(SHIFT_MODEL_DIR + "*.json"))
    for model_path in model_paths:
        trait_model = load_shift_trait_model(model_path)
        print(f"\nApplying {trait_model['name']} (y_transform={trait_model['y_transform']}, "
              f"{len(trait_model['wavelengths'])} bands, {trait_model['wavelengths'].min():.0f}-"
              f"{trait_model['wavelengths'].max():.0f} nm)")

        matrix, caveat_bands = build_resampling_matrix(
            trait_model["wavelengths"], trait_model["fwhm"],
            scene["wavelengths"], scene["fwhm"], scene["good_wavelengths"],
        )
        if caveat_bands:
            print(f"  NOTE: {len(caveat_bands)}/{len(trait_model['wavelengths'])} target bands "
                  f"can't be sharpened to Tanager's native resolution there.")

        bands, lines, cols = scene["reflectance"].shape
        source_flat = scene["reflectance"].reshape(bands, -1)
        resampled = (matrix @ source_flat).reshape(len(trait_model["wavelengths"]), lines, cols)

        trait_mean, trait_std, range_mask = apply_trait_model(resampled, trait_model)

        trait_mean[scene["nodata_pixels"]] = NO_DATA
        trait_std[scene["nodata_pixels"]] = NO_DATA
        range_mask_f = range_mask.astype(np.float32)
        range_mask_f[scene["nodata_pixels"]] = NO_DATA

        n_valid = (~scene["nodata_pixels"]).sum()
        n_in_range = (range_mask & ~scene["nodata_pixels"]).sum()
        print(f"  {n_in_range}/{n_valid} pixels ({n_in_range/n_valid*100:.1f}%) within "
              f"diagnostic range [{trait_model['diagnostics']['min']:.1f}, "
              f"{trait_model['diagnostics']['max']:.1f}] {trait_model['units']}")

        arrays = {
            f"{trait_model['name']}_mean": trait_mean,
            f"{trait_model['name']}_std": trait_std,
            "range_mask": range_mask_f,
        }
        gridded, transform, epsg = grid_swath_to_ortho(arrays, scene["lat"], scene["lon"], scene["ortho_framing"])

        out_path = os.path.join(
            OUTPUT_DIR,
            os.path.splitext(os.path.basename(CA_H5))[0] + f"_shift_{trait_model['name']}.tif",
        )
        write_geotiff(out_path, gridded, transform, epsg, band_order=list(arrays.keys()))
        print(f"  Wrote {out_path}")


if __name__ == "__main__":
    main()
