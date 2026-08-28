# Tanager Data Competition Entry

Entry for Planet's [2026 Tanager Open Data Competition](https://learn.planet.com/2026-Tanager-Open-Data-Competition.html):
apply existing BioSCape-trained foliar trait models (Cape Floristic Region,
South Africa) to Planet's example Tanager-1 release-2 scene, produce trait
maps, and validate against BioSCape ground sites in the same area.

![Ternary trait composite (Nitrogen/Lignin/Calcium) over the Cape Floristic Region Tanager scene](writeup/figures/ternary_composite_preview.png)

*Nitrogen (red) / Lignin (green) / Calcium (blue) predicted from Tanager
reflectance, veg-masked. Normalized to this scene's own value range for
visual impact -- illustrative, not a quantitative figure (the report's
actual analysis figures use field-data-referenced ranges instead, so
trait bias stays visible rather than auto-stretched away). See `writeup/report_draft.md` for the full write-up, `code/step15_readme_banner_ternary.py` for this banner image, and `code/step5_ternary_map.py` for the report's field-referenced
version.*

## Reproducibility note

This repo's code is public and documents the full method, but not every
input is. Breakdown of what's independently obtainable vs. internal:

- **Publicly available, independent of this project**: the Tanager scenes
  (Planet's open STAC catalog), the EMIT granule (NASA Earthdata), and the
  AVIRIS-NG L2B reflectance product once [Kovach et al. 2025](https://doi.org/10.3334/ORNLDAAC/2385)
  is fully released.
- **Not yet public**: the BioSCape trait-model coefficient files this
  project applies to Tanager/EMIT (from Frye et al., in review at ORNL
  DAAC — see `writeup/report_draft.md` for citation details) and the SHIFT
  (California) trait models, provided directly by a collaborator and not
  deposited anywhere public yet.
- **Internal lab infrastructure, not part of this repo**: this project's
  own intermediate/output data lives on the lab's internal Enspec server
  (paths like `/Volumes/Enspec/...` below), and a few reference
  scripts/configs are reused from other, currently-private lab
  repositories (e.g. `Airborne_Apply_Models/...`,
  `Workflow11_Trait_Map_Assess/...`, `bioscape_indices/...`, referenced in
  code comments and the run order below). An external reader can follow
  the method in full from the code, but can't literally re-run this
  pipeline end to end without either lab server access or the
  not-yet-public model files above.
- **`CLAUDE.md` references below are dead links for external readers.**
  This README and the run order below point to `CLAUDE.md` throughout
  for extended detail on specific findings (it was this project's working
  session log). That file is intentionally not part of this public repo
  (kept locally, gitignored) since it's a candid internal log, not
  written for an outside audience. The same substance for the headline
  findings is written up properly in `writeup/report_draft.md` instead.

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
                      baked in, LMA/Calcium use a sqrt Y-transform
  figures/            presentation-ready plots (density comparisons,
                      QA previews) - distinct from trait_outputs/'s raw
                      GeoTIFFs
  aviris_aoi_mosaic/  BioSCape's own AVIRIS-NG imagery, mosaicked over
                      this scene's footprint (30.6% coverage, Nov 2023,
                      never mosaicked before this project) - see
                      CLAUDE.md "AVIRIS-NG AOI mosaic + comparison"
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
   **All four kept traits (Nitrogen, Calcium, Lignin, Cellulose) use
   FULL-uvf** — tried switching to IR-uvf (the lab's general same-sensor
   default) and reverted after it checked out worse against field data
   for every trait tried; see CLAUDE.md "IR-uvf vs FULL-uvf: a real
   detour" for the numbers and reasoning.
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
8. `step7_emit_tanager_density.py` — density-distribution comparison
   (KDE overlays) of Tanager vs. EMIT predicted values, same AOI as the
   percentile table above. `figures/emit_vs_tanager_density.png`.
9. `step8_apply_trait_model_california.py` — applies the colleague's
   SHIFT (Santa Barbara)-trained models to a Tanager scene over the same
   area. Confirms the sqrt Y-transform fix for LMA/Calcium works: LMA
   went from 16% in-range (Cape, no fix) to 99.8% in-range here, with
   physically plausible values throughout — see CLAUDE.md "California
   (SHIFT models) results".
10. `step9_ndvi_shadow_mask_california.py` — same treatment as step4 for
    the California scene (own thresholds from its own histogram, more
    cleanly bimodal than the Cape one). Cleans up the coastal/urban noise
    seen in the unmasked QA preview.
11. `step10_mosaic_aviris_aoi.R` — mosaics BioSCape's own AVIRIS-NG L3
    trait tiles (Nov 2023) over this scene's footprint (30.6% coverage,
    24 tiles across 6 flightlines, none previously mosaicked for this
    area). R/terra, not Python — reuses
    `Workflow11_Trait_Map_Assess/code/mosaic_trait_tiles.R` directly
    rather than reimplementing tile mosaicking. Output:
    `aviris_aoi_mosaic/`. See CLAUDE.md "AVIRIS-NG AOI mosaic +
    comparison" for tile-selection details and the comparison result
    (Nitrogen matches almost exactly; the other 3 traits carry a
    model-variant caveat — the precomputed BioSCape tiles use IR-uvf for
    everything except Lignin).
12. `step11_tanager_emit_sidebyside_maps.py` — side-by-side Tanager vs.
    EMIT trait maps, all 4 traits, EMIT reprojected onto Tanager's grid,
    same field-referenced color scale as the ternary map.
    `figures/tanager_vs_emit_sidebyside_maps.png` — strong spatial
    agreement between the two sensors, good headline figure candidate.
13. `step12_nitrogen_tanager_emit_aviris.py` — separate 3-panel figure
    (Tanager | EMIT | AVIRIS-NG airborne), Nitrogen only — the one trait
    where the AVIRIS-NG comparison is empirically supported. Kept out of
    step11's figure since AVIRIS-NG only covers 30.6% of the scene and
    the other 3 traits carry the IR-uvf/FULL-uvf model-variant caveat.
    `figures/nitrogen_tanager_emit_aviris.png`.
14. `step13_california_sidebyside_maps.py` — all 5 California SHIFT
    traits in one row, field-referenced color scale (each model's own
    `field_min`/`field_max`), veg-masked. `figures/california_sidebyside_maps.png`.
15. `step14_tanager_emit_difference_map.py` — per-pixel (EMIT-Tanager)
    difference, all 4 Cape traits. Diagnostic, not just cosmetic: Lignin
    shows a uniform offset (looks like sensor calibration), Calcium shows
    real spatial structure (south vs. north of the scene), Nitrogen is
    small/patternless, Cellulose is noisy. `figures/tanager_emit_difference_map.png`.

## Environment

- **Python**: this repo has its **own isolated venv** —
  `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
  Do **not** install into the shared `/opt/anaconda3` base conda env:
  `rasterio`/`pyproj` pull in numpy 2.x, which breaks version pins other
  projects rely on in that shared env (hit this during setup — see
  CLAUDE.md "Environment note"). Always run this repo's scripts with
  `.venv/bin/python3`.
