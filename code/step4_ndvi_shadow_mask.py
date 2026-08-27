"""NDVI + shadow/vegetation mask for the Tanager scene, gridded to match
the trait map outputs from step2.

NDVI formula/bands match `bioscape_indices/indices/NDVI.json`
((R800-R660)/(R800+R660), 10 nm tolerance) for consistency with the rest
of the BioSCape processing chain. There's no dedicated shadow index in
that reference pipeline (checked config_indices.json's index list) --
shadow here is a simple NIR-brightness threshold, a standard heuristic
(shadowed pixels stay dark in the NIR even where the spectral *shape*
still looks vegetated). Thresholds were picked by looking at this scene's
actual R800/NDVI histograms (see CLAUDE.md), not assumed from elsewhere.
"""
import sys

import h5py
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from step2_apply_trait_model import TANAGER_H5, OUTPUT_DIR, read_tanager_scene, grid_swath_to_ortho, write_geotiff, NO_DATA

NDVI_WAVELENGTHS = (800, 660)
WAVELENGTH_TOLERANCE = 10  # nm, matches bioscape_indices/indices/NDVI.json

# Picked from this scene's own R800/NDVI histograms (see CLAUDE.md "NDVI +
# shadow mask" for the percentiles) -- roughly the bottom decile of each,
# where the distribution's low tail separates from the vegetated bulk.
SHADOW_R800_THRESHOLD = 0.05
VEG_NDVI_THRESHOLD = 0.2


def nearest_band(wavelengths, target, tolerance):
    idx = int(np.argmin(np.abs(wavelengths - target)))
    if abs(wavelengths[idx] - target) > tolerance:
        raise ValueError(f"No band within {tolerance} nm of {target} nm")
    return idx


def compute_and_write_mask(h5_path, out_path, shadow_threshold, veg_ndvi_threshold, scene=None):
    """Reusable across scenes -- Cape (this file's __main__) and
    California (step9) both call this, each with thresholds picked from
    that scene's OWN R800/NDVI histogram rather than reusing the other
    scene's numbers (surface reflectance levels aren't necessarily
    comparable band-for-band across acquisitions/processing runs).
    """
    if scene is None:
        scene = read_tanager_scene(h5_path)
    wl = scene["wavelengths"]

    i_nir = nearest_band(wl, NDVI_WAVELENGTHS[0], WAVELENGTH_TOLERANCE)
    i_red = nearest_band(wl, NDVI_WAVELENGTHS[1], WAVELENGTH_TOLERANCE)
    print(f"NDVI bands: NIR={wl[i_nir]:.1f}nm, red={wl[i_red]:.1f}nm")

    r_nir = scene["reflectance"][i_nir].astype(np.float64)
    r_red = scene["reflectance"][i_red].astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (r_nir - r_red) / (r_nir + r_red)
    # Near-zero denominators (very dark/shadowed pixels) blow NDVI up well
    # outside its physically valid range -- clip to [-1, 1], matching
    # bioscape_indices/indices/NDVI.json's own "output_range". Those pixels
    # are already caught by the shadow mask below, so clipping here just
    # keeps the NDVI band itself sane rather than double-handling them.
    ndvi = np.clip(ndvi, -1.0, 1.0)

    shadow_mask = (r_nir < shadow_threshold).astype(np.float32)
    veg_mask = ((ndvi >= veg_ndvi_threshold) & (r_nir >= shadow_threshold)).astype(np.float32)

    arrays = {
        "NDVI": ndvi.astype(np.float32),
        "shadow_mask": shadow_mask,
        "veg_mask": veg_mask,
    }
    for name in arrays:
        arrays[name][scene["nodata_pixels"]] = NO_DATA

    print("Gridding onto ortho target grid...")
    gridded, transform, epsg = grid_swath_to_ortho(arrays, scene["lat"], scene["lon"], scene["ortho_framing"])

    write_geotiff(out_path, gridded, transform, epsg, band_order=list(arrays.keys()))
    print(f"Wrote {out_path}")

    valid = ndvi[~scene["nodata_pixels"]]
    print(f"\nScene-wide (swath, pre-grid): NDVI median={np.median(valid):.2f}, "
          f"{shadow_mask[~scene['nodata_pixels']].mean()*100:.1f}% flagged shadow, "
          f"{veg_mask[~scene['nodata_pixels']].mean()*100:.1f}% flagged vegetated")
    return scene


def main():
    out_path = OUTPUT_DIR + "20250504_092952_87_4001_basic_sr_hdf5_ndvi_shadow_mask.tif"
    compute_and_write_mask(TANAGER_H5, out_path, SHADOW_R800_THRESHOLD, VEG_NDVI_THRESHOLD)


if __name__ == "__main__":
    main()
