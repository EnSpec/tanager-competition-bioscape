"""Apply BioSCape AVIRIS-NG-trained PLSR trait models to a Tanager scene.

Mirrors the core PLSR math in
Airborne_Apply_Models/prairie_du_sac_2025_trait/trait_estimate_nc_glt_no_anc.py
(HyTools' apply_trait_models()) but reimplemented standalone against
h5py/numpy directly, because HyTools has no reader for Tanager's
basic_sr_hdf5 format -- see this repo's README ("Tanager basic_sr_hdf5
format") and CLAUDE.md ("Key finding") for why.

Cross-sensor resampling (Tanager -> AVIRIS-NG band grid)
----------------------------------------------------------
The trait models were trained on AVIRIS-NG reflectance at specific band
centers with AVIRIS-NG's own spectral response width (FWHM). The model
JSONs carry wavelengths but not FWHM (empty field), so real AVIRIS-NG FWHM
is pulled from an actual corrected BioSCape flightline netCDF instead
(AVIRIS_REFERENCE_NC below) -- confirmed all model wavelengths match that
425-band grid to <0.001 nm.

Rather than nearest-wavelength interpolation, each target (AVIRIS-NG) band
is built as a Gaussian relative spectral response centered at the model's
wavelength with the model sensor's FWHM, evaluated against Tanager's
*actual* band centers and FWHM (both sensors are close but not identical:
Tanager FWHM 5.2-6.8 nm depending on region, AVIRIS-NG 5.6-6.0 nm). Where
the target band is broader than Tanager's native band, the Gaussian
kernel used is the "matching" width (quadrature difference) needed to
broaden Tanager's narrower measurement to the target's resolution; where
Tanager's native band is already broader than the target (can't sharpen a
measurement below its native resolution), the kernel falls back to
Tanager's own width and that band is flagged in FWHM_CAVEAT_BANDS for the
write-up.

Vector normalization is computed AFTER resampling to the model's band
subset, matching how trait_estimate_nc_glt_no_anc.py orders it (and per
the modeling assumption that normalization is computed over exactly the
wavelength range used at training) -- not over Tanager's full 426 bands.
"""
import json
import os

import fsspec
import h5py
import numpy as np
import netCDF4 as nc
import pyproj
import rasterio
from rasterio.transform import Affine
from scipy.spatial import cKDTree

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

TANAGER_H5 = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/raw_h5/"
    "20250504_092952_87_4001_basic_sr_hdf5.h5"
)
# Any single corrected BioSCape AVIRIS-NG L2A flightline works here -- only
# its wavelength/fwhm variables are read (a few KB), never the reflectance
# cube. Used purely as the source of real AVIRIS-NG FWHM per band.
AVIRIS_REFERENCE_NC = (
    "/Volumes/Enspec/projects/BioScape/Lines_Corrected_Hyperspectral/"
    "ang20231022t092801_000_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1.nc"
)
TRAIT_MODEL_DIR = (
    "/Users/henryfrye/Dropbox/Intellectual_Endeavours/Wisconsin/"
    "Airborne_Apply_Models/bioscape/trait_models/"
)
# FULL-uvf models use the whole 452-2446 nm range; Tanager covers this
# fully, so FULL is preferred over the IR-only variant where available.
TRAIT_MODELS = [
    TRAIT_MODEL_DIR + "plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa.json",
    TRAIT_MODEL_DIR + "plsr__sampled_lma_cwm_iter_mean__FULL-uvf__ideny__rep__boa.json",
]
OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"

NO_DATA = -9999.0


# ---------------------------------------------------------------------------
# AVIRIS-NG reference FWHM
# ---------------------------------------------------------------------------

def get_aviris_ng_reference(nc_path):
    """Real AVIRIS-NG band centers + FWHM from a corrected BioSCape flightline."""
    ds = nc.Dataset(nc_path)
    refl = ds.groups["reflectance"]
    wavelength = np.array(refl.variables["wavelength"][:], dtype=float)
    fwhm = np.array(refl.variables["fwhm"][:], dtype=float)
    ds.close()
    return wavelength, fwhm


def load_trait_model(json_path, aviris_wl, aviris_fwhm):
    with open(json_path, "r") as f:
        model = json.load(f)

    wavelengths = np.array(model["wavelengths"], dtype=float)

    # Match each model wavelength to the AVIRIS-NG reference grid to pull
    # its real FWHM (the model json's own "fwhm" field is empty).
    idx = np.array([np.argmin(np.abs(aviris_wl - w)) for w in wavelengths])
    mismatch = np.abs(aviris_wl[idx] - wavelengths)
    if mismatch.max() > 0.01:
        raise ValueError(
            f"{json_path}: {mismatch.max():.3f} nm max mismatch matching model "
            "wavelengths to the AVIRIS-NG reference grid -- check "
            "AVIRIS_REFERENCE_NC is the same band grid this model was trained on."
        )
    fwhm = aviris_fwhm[idx]

    return {
        "name": model["name"],
        "units": model["units"],
        "wavelengths": wavelengths,
        "fwhm": fwhm,
        "transform": model["model"]["transform"],
        "coefficients": np.array(model["model"]["coefficients"]),
        "intercepts": np.array(model["model"]["intercepts"]),
        "diagnostics": model["model_diagnostics"],
    }


# ---------------------------------------------------------------------------
# Tanager scene
# ---------------------------------------------------------------------------

def read_tanager_scene(h5_path):
    opener = fsspec.open(h5_path, mode="rb") if h5_path.startswith("http") else open(h5_path, "rb")
    with opener as f:
        hf = h5py.File(f, "r")
        fields = hf["HDFEOS/SWATHS/HYP/Data Fields"]
        geo = hf["HDFEOS/SWATHS/HYP/Geolocation Fields"]

        sr = fields["surface_reflectance"]
        scene = {
            "reflectance": sr[:],  # (bands, along_track, cross_track)
            "wavelengths": np.array(sr.attrs["wavelengths"], dtype=float),
            "fwhm": np.array(sr.attrs["fwhm"], dtype=float),
            "good_wavelengths": np.array(sr.attrs["good_wavelengths"], dtype=bool),
            "nodata_pixels": fields["nodata_pixels"][:].astype(bool),
            "lat": geo["Latitude"][:],
            "lon": geo["Longitude"][:],
            "ortho_framing": json.loads(geo.attrs["Planet_Ortho_Framing"]),
        }
    return scene


# ---------------------------------------------------------------------------
# Gaussian spectral resampling (Tanager band grid -> AVIRIS-NG band grid)
# ---------------------------------------------------------------------------

FWHM_TO_SIGMA = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))


def build_resampling_matrix(target_wl, target_fwhm, source_wl, source_fwhm, source_good, window_sigmas=4.0):
    """Gaussian relative-spectral-response resampling matrix, (n_target, n_source).

    Each row integrates Tanager's native bands against a Gaussian centered
    at the target (AVIRIS-NG) wavelength. The kernel width is the
    quadrature difference between target and per-source-band FWHM where
    the target is broader (proper band-broadening deconvolution-free
    match); where Tanager's native band is already >= the target width,
    falls back to the source's own width (can't sharpen below native
    resolution) and flags that target band as a caveat.
    """
    n_target = len(target_wl)
    n_source = len(source_wl)
    matrix = np.zeros((n_target, n_source))
    caveat_bands = []

    target_sigma = target_fwhm * FWHM_TO_SIGMA
    source_sigma = source_fwhm * FWHM_TO_SIGMA

    for t in range(n_target):
        candidates = np.where(source_good & (np.abs(source_wl - target_wl[t]) < window_sigmas * target_sigma[t] + 15))[0]
        if len(candidates) == 0:
            # No usable Tanager bands nearby (e.g. inside a masked absorption
            # feature) -- widen the search once before giving up.
            candidates = np.where(source_good)[0]
            candidates = candidates[np.argsort(np.abs(source_wl[candidates] - target_wl[t]))[:5]]

        # Per-candidate: where the target is broader, use the quadrature-
        # difference kernel; where a candidate's own native band is already
        # as wide or wider than the target, fall back to ITS width rather
        # than an artificial near-zero sigma (which would silently underflow
        # every candidate's Gaussian weight to 0 whenever the nearest
        # candidate isn't at exactly zero offset -- Tanager and AVIRIS-NG
        # don't share a sampling grid, so that's the common case, not an
        # edge case).
        diff_sq = target_sigma[t] ** 2 - source_sigma[candidates] ** 2
        conv_sigma = np.where(diff_sq > 0, np.sqrt(np.clip(diff_sq, 1e-12, None)), source_sigma[candidates])
        if np.all(diff_sq <= 0):
            caveat_bands.append(target_wl[t])

        weights = np.exp(-0.5 * ((source_wl[candidates] - target_wl[t]) / conv_sigma) ** 2)
        weight_sum = weights.sum()
        if weight_sum <= 0:
            # Should not happen given source/target sampling density, but
            # guard against silently propagating NaN into every pixel's
            # trait estimate -- fall back to the single nearest candidate.
            nearest = candidates[np.argmin(np.abs(source_wl[candidates] - target_wl[t]))]
            matrix[t, nearest] = 1.0
            continue
        weights /= weight_sum
        matrix[t, candidates] = weights

    return matrix, sorted(set(caveat_bands))


# ---------------------------------------------------------------------------
# Trait model application
# ---------------------------------------------------------------------------

def apply_trait_model(resampled_reflectance, trait_model):
    """resampled_reflectance: (n_model_bands, lines, cols) already on the
    model's exact wavelength grid. Returns mean, std, range_mask arrays
    of shape (lines, cols).
    """
    bands, lines, cols = resampled_reflectance.shape
    spectra = resampled_reflectance.reshape(bands, -1).T  # (n_pixels, bands)

    for step in trait_model["transform"]:
        if step == "vector":
            norm = np.linalg.norm(spectra, axis=1, keepdims=True)
            spectra = spectra / norm
        elif step == "absorb":
            spectra = np.log(1.0 / spectra)
        elif step == "mean":
            spectra = spectra / spectra.mean(axis=1, keepdims=True)

    # (n_pixels, bands) . (bootstraps, bands).T -> (n_pixels, bootstraps)
    pred = spectra @ trait_model["coefficients"].T + trait_model["intercepts"]

    trait_mean = pred.mean(axis=1).reshape(lines, cols)
    trait_std = pred.std(axis=1, ddof=1).reshape(lines, cols)

    diag = trait_model["diagnostics"]
    range_mask = (trait_mean > diag["min"]) & (trait_mean < diag["max"])

    return trait_mean, trait_std, range_mask


# ---------------------------------------------------------------------------
# Swath -> ortho grid
# ---------------------------------------------------------------------------

def grid_swath_to_ortho(arrays, lat, lon, ortho_framing, fill_value=NO_DATA):
    """Nearest-neighbor grid swath-geometry arrays onto the Planet_Ortho_Framing
    UTM target grid. `arrays` is a dict of name -> (lines, cols) array.
    Returns (dict of name -> gridded array, rasterio Affine transform, EPSG code).
    """
    epsg = ortho_framing["epsg_code"]
    gt = ortho_framing["geotransform"]
    n_cols, n_rows = ortho_framing["cols"], ortho_framing["rows"]
    transform = Affine(gt[1], gt[2], gt[0], gt[4], gt[5], gt[3])

    transformer = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    src_x, src_y = transformer.transform(lon.ravel(), lat.ravel())
    src_xy = np.column_stack([src_x, src_y])

    col_idx, row_idx = np.meshgrid(np.arange(n_cols), np.arange(n_rows))
    dst_x = gt[0] + (col_idx + 0.5) * gt[1]
    dst_y = gt[3] + (row_idx + 0.5) * gt[5]
    dst_xy = np.column_stack([dst_x.ravel(), dst_y.ravel()])

    tree = cKDTree(src_xy)
    max_dist = 1.5 * abs(gt[1])  # nearest source pixel must be within ~1 target pixel
    dist, nearest = tree.query(dst_xy, k=1, distance_upper_bound=max_dist)
    valid = np.isfinite(dist)

    gridded = {}
    for name, arr in arrays.items():
        flat = arr.ravel()
        out = np.full(n_rows * n_cols, fill_value, dtype=np.float32)
        out[valid] = flat[nearest[valid]]
        gridded[name] = out.reshape(n_rows, n_cols)

    return gridded, transform, epsg


def write_geotiff(path, gridded, transform, epsg, band_order, no_data=NO_DATA):
    n_rows, n_cols = next(iter(gridded.values())).shape
    with rasterio.open(
        path, "w", driver="GTiff",
        height=n_rows, width=n_cols, count=len(band_order),
        dtype="float32", crs=f"EPSG:{epsg}", transform=transform,
        nodata=no_data, compress="lzw",
    ) as dst:
        for i, name in enumerate(band_order, start=1):
            dst.write(gridded[name].astype(np.float32), i)
            dst.set_band_description(i, name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading AVIRIS-NG reference FWHM...")
    aviris_wl, aviris_fwhm = get_aviris_ng_reference(AVIRIS_REFERENCE_NC)

    print("Reading Tanager scene...")
    scene = read_tanager_scene(TANAGER_H5)
    print(f"  reflectance shape: {scene['reflectance'].shape}")

    for model_path in TRAIT_MODELS:
        print(f"\nApplying {os.path.basename(model_path)}")
        trait_model = load_trait_model(model_path, aviris_wl, aviris_fwhm)

        matrix, caveat_bands = build_resampling_matrix(
            trait_model["wavelengths"], trait_model["fwhm"],
            scene["wavelengths"], scene["fwhm"], scene["good_wavelengths"],
        )
        if caveat_bands:
            print(
                f"  NOTE: {len(caveat_bands)} target bands are narrower than "
                f"Tanager's native FWHM there (can't sharpen); nearest-native-"
                f"resolution match used instead: {[round(w, 1) for w in caveat_bands[:8]]}"
                + (" ..." if len(caveat_bands) > 8 else "")
            )

        bands, lines, cols = scene["reflectance"].shape
        source_flat = scene["reflectance"].reshape(bands, -1)
        resampled = (matrix @ source_flat).reshape(len(trait_model["wavelengths"]), lines, cols)

        trait_mean, trait_std, range_mask = apply_trait_model(resampled, trait_model)

        trait_mean[scene["nodata_pixels"]] = NO_DATA
        trait_std[scene["nodata_pixels"]] = NO_DATA
        range_mask_f = range_mask.astype(np.float32)
        range_mask_f[scene["nodata_pixels"]] = NO_DATA

        arrays = {
            f"{trait_model['name']}_mean": trait_mean,
            f"{trait_model['name']}_std": trait_std,
            "range_mask": range_mask_f,
        }
        print("  Gridding onto ortho target grid...")
        gridded, transform, epsg = grid_swath_to_ortho(arrays, scene["lat"], scene["lon"], scene["ortho_framing"])

        out_path = os.path.join(
            OUTPUT_DIR,
            os.path.splitext(os.path.basename(TANAGER_H5))[0] + f"_{trait_model['name']}.tif",
        )
        write_geotiff(out_path, gridded, transform, epsg, band_order=list(arrays.keys()))
        print(f"  Wrote {out_path}")


if __name__ == "__main__":
    main()
