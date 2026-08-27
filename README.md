# Tanager Data Competition Entry

Entry for Planet's [2026 Tanager Open Data Competition](https://learn.planet.com/2026-Tanager-Open-Data-Competition.html):
apply existing BioSCape-trained foliar trait models (Cape Floristic Region,
South Africa) to Planet's example Tanager-1 release-2 scene, produce trait
maps, and validate against BioSCape ground sites in the same area.

## Data

All data lives on the Enspec server, **not** in this repo:
```
/Volumes/Enspec/projects/BioScape/tanager_competition/
  raw_h5/            downloaded Tanager basic_sr_hdf5 scene(s)
  trait_outputs/     trait map GeoTIFFs
  ground_validation/ CWM ground-plot geojson (copied from
                      Workflow9_community_weighted_means - see CLAUDE.md,
                      zero plots overlap this scene)
  emit_comparison/   EMIT L2A scene (2026-03-02, see CLAUDE.md "EMIT
                      scene selection" for why this date) + its trait
                      outputs live in trait_outputs/ (emit_* prefix)
  shift_models_Aug2026/ California (SHIFT campaign)-trained PLSR trait
                      models from a colleague - IR-range, own FWHM
                      baked in. Not yet applied (needs a CA Tanager
                      scene) - see CLAUDE.md "Next up"
```

**Example scene**: `20250504_092952_87_4001_basic_sr_hdf5.h5` (~1 GB), from
[open-cogs/planet-stac/tanager1-release2-core-imagery](https://storage.googleapis.com/open-cogs/planet-stac/tanager1-release2-core-imagery/basic_sr_hdf5/20250504_092952_87_4001_basic_sr_hdf5.h5).
Covers roughly lat -33.76 to -33.55, lon 19.33 to 19.61 (Cape Town /
Jonkershoek area) — good overlap with BioSCape validation sites.

## Tanager `basic_sr_hdf5` format

**Not** NEON-schema HDF5 — HyTools' `neon` reader (or any of its other
`file_type`s: `envi`, `emit`, `ncav`) will not open this file. It's an
HDF-EOS5 **swath** product:

- Reflectance: `HDFEOS/SWATHS/HYP/Data Fields/surface_reflectance`, shape
  `(426 bands, 587 along-track, 607 cross-track)`, float32, band-first.
- `wavelengths`, `fwhm`, `good_wavelengths` (QA mask, 368/426 good) are
  **attrs on the reflectance dataset itself**, not separate datasets.
  376.4–2499.0 nm.
- Geolocation is per-pixel `Latitude`/`Longitude` swath grids (not an
  affine transform on the data) — this is unprojected swath geometry.
  A `Planet_Ortho_Framing` attr on the Geolocation Fields group gives a
  target ortho grid to warp onto: `859 cols x 767 rows`, 30 m, EPSG:32734
  (UTM 34S), geotransform `[345660.0, 30.0, 0.0, 6286110.0, 0.0, -30.0]`.
- Other per-pixel fields available: `sensor_zenith/azimuth`,
  `sun_zenith/azimuth`, `sensor_to_ground_path_length`,
  `aerosol_optical_depth`, `column_water_vapour`, `beta_cloud_mask`,
  `beta_cirrus_mask`, `nodata_pixels`.

Full structure dump: `code/step1_inspect_tanager_h5.py` (reads the file via
`fsspec` HTTP range requests — no download needed to re-inspect).

**Approach**: the scene is small (426×587×607 float32 ≈ 575 MB, fits in
RAM) — HyTools' Ray/chunked-iterator machinery exists for tiles too big to
hold in memory and isn't worth adapting here. Trait application is a
standalone `h5py` + `numpy` script that mirrors the core PLSR math from
`Airborne_Apply_Models/prairie_du_sac_2025_trait/trait_estimate_nc_glt_no_anc.py`
(vector-normalize, coefficient dot product + intercept) rather than a new
HyTools reader.

## Run order

1. `step1_inspect_tanager_h5.py` — dump the h5 structure (done; see above)
2. Download the scene to `raw_h5/` (done)
3. `step2_apply_trait_model.py` — reads the h5 cube, Gaussian-resamples
   onto the BioSCape (AVIRIS-NG-trained) trait models' band grid, applies
   PLSR coefficients, grids the swath onto the `Planet_Ortho_Framing` UTM
   target via the Lat/Lon arrays, writes GeoTIFFs to `trait_outputs/`.
   Uses the BioSCape-trained models
   (`Airborne_Apply_Models/bioscape/trait_models/*FULL-uvf*.json`), not
   the NEON-trained ones used earlier in the Prairie du Sac smoke test —
   see CLAUDE.md "Trait application pipeline" for the cross-sensor FWHM
   matching approach and first-run results (Nitrogen looks good; LMA has
   a real cross-sensor sensitivity issue, not a bug — see CLAUDE.md).
4. `step3_ground_validation.py` — checks CWM ground plots against the
   scene footprint; currently reports **zero overlap** for this scene
   (nearest plot cluster ~17.5 km outside the edge). A denser regional
   leaf-trait survey (GCFR Dimensions data paper, thousands of points)
   also has zero overlap (nearest ~60 km) — see CLAUDE.md "Ground
   validation check" / "Regional ballpark check". No formal or ballpark
   validation is possible against this specific scene; folded into the
   coverage-gap pitch instead.
5. `step4_ndvi_shadow_mask.py` — NDVI (matching
   `bioscape_indices/indices/NDVI.json`'s formula) + a simple
   NIR-brightness shadow mask + combined veg mask, gridded to match the
   trait maps. See CLAUDE.md "NDVI + shadow mask" for threshold choices.
6. `step5_ternary_map.py` — 3-trait RGB composite (default:
   Nitrogen/Lignin/Cellulose), normalized to region-wide CWM field-data
   ranges (not the scene's own range — see CLAUDE.md "Ternary map" for
   why), veg-masked via step4. First figure candidate, visually checked.
7. `step6_apply_trait_model_emit.py` — same trait models applied to an
   EMIT L2A scene (2026-03-02) for a cross-sensor comparison. Result:
   strong agreement with Tanager over the same AOI (Nitrogen/Cellulose
   within ~5-8% at the median, Calcium/Lignin within ~12-23% but in the
   same direction as their known field-data biases) — see CLAUDE.md
   "EMIT vs. Tanager comparison".
8. California cross-model comparison — back on (colleague delivered the
   models after all), not yet started — see CLAUDE.md "Next up"

## Environment

- **Python**: this repo has its **own isolated venv** —
  `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
  Do **not** install into the shared `/opt/anaconda3` base conda env:
  `rasterio`/`pyproj` pull in numpy 2.x, which breaks version pins other
  projects rely on in that shared env (hit this during setup — see
  CLAUDE.md "Environment note"). Always run this repo's scripts with
  `.venv/bin/python3`.
