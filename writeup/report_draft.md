# Cross-Sensor Transfer of Airborne Trait Models to Tanager: A BioSCape Case Study

*Draft — 2026-08-27. Numbers and figure references below are pulled directly
from this project's `CLAUDE.md`/pipeline outputs; every figure referenced
already exists in `figures/` and `trait_outputs/`. Not yet copy-edited for
submission tone/length — flag anything that reads rough.*

---

## 1. Can Tanager Deliver Airborne-Quality Foliar Trait Maps From Orbit?

Measuring the distribution of foliar traits across landscapes is key to
understanding ecological processes at spatial extents relevant for
conservation decisions and policy making. Airborne imaging spectroscopy
has been used for decades to robustly predict a wide suite of structural
and biochemical plant traits across a variety of ecosystems. These
airborne acquisitions and their paired ground-collected data are
increasingly used to train models applied to space-borne sensors such as
EMIT. Tanager is well-poised to serve as an alternative source of
space-borne trait maps, with the advantage of being able to respond to
ecological disturbances more nimbly than current data sources and planned
missions like EAGLE-VSWIR.

The NASA-led Biodiversity Survey of the Cape ([BioSCape](https://www.bioscape.io)) offers a well-documented example of exactly this kind of
airborne-trained resource, and is a natural test case for whether it can be put to work on a new platform. The 2023 campaign acquired near wall-to-wall coverage with the AVIRIS-NG sensor over the Cape Floristic Region (CFR), a global biodiversity hotspot and a region particularly affected by global change. Along with fieldwork led by the [Townsend lab](https://townsend.russell.wisc.edu) resulting in 542 field plots and thousands of leaf chemistry samples, this project has built one of the
richest foliar trait-model libraries that exists for any biodiversity
hotspot on Earth (Cardoso et al., 2025). These efforts resulted in foliar trait maps for 20 traits across the CFR. These maps were trained entirely on one airborne sensor, over one campaign, in one region. Tanager is a new
question mark against all three: a different platform (spaceborne, not
airborne), built and calibrated independently, flying over the same
landscape roughly a year and a half later.

*[Figure: flight-box coverage + field sample sites over the CFR —
Henry to point to the existing figure file.]*

**Can an existing, independently-trained trait-model library transfer to
a brand-new commercial hyperspectral platform with *zero recalibration*?**
That's the question this project set out to answer, using Tanager's
example release scene over the Cape Floristic Region — and, once the
methodology proved out, a second scene over California to test whether it
generalizes across continents.

The answer, in short is **yes** — and the caveats along the way turn out to be
as informative as the successes.

Missions like EAGLE-VSWIR will inherit this exact question the moment
they launch: how trait models trained on one instrument transfer to
another, and what it takes to make that transfer honest rather than
aspirational. Tanager, already on orbit, is a chance to work out the
answer now.

## 2. Data and methods

**Sensors and products used:**

| Source | Role | Coverage used |
|---|---|---|
| Tanager (`basic_sr_hdf5`) | Primary test platform | Cape scene (2025-05-04), California scene (2025-04-07) |
| AVIRIS-NG (BioSCape campaign, Kovach et al. 2025) | Trait model training data + independent airborne validation | Nov 2023, Cape region |
| EMIT | Independent spaceborne cross-check | 2026-03-02, same Cape area of interest (AOI) |
| SHIFT campaign† | Trait model training data, California | Santa Barbara, exact dates TBC |

† *SHIFT background: [earthdata.nasa.gov/data/projects/shift](https://www.earthdata.nasa.gov/data/projects/shift). Candidate source datasets: [AVIRIS-NG plant trait mosaics](https://www.earthdata.nasa.gov/data/catalog/ornl-cloud-shift-avng-plant-trait-mosaics-2453-1), [foliar chemical analysis](https://www.earthdata.nasa.gov/data/catalog/ornl-cloud-shift-foliar-chemical-analysis-2337-1), [dried/ground leaf reflectance](https://www.earthdata.nasa.gov/data/catalog/ornl-cloud-shift-driedground-leaf-reflec-2244-1). The California model json's only training-data metadata is a `spectrometer: "avc+neon"` tag — read here as AVIRIS-Classic + NEON, but that's an inference from a terse field, not a confirmed description. It's possible this model pools data across multiple campaigns/sites rather than SHIFT-region data specifically. Need to confirm the exact composition with the colleague who provided the model before naming a specific dataset/citation.*

**Trait models**: BioSCape's PLSR (partial least squares regression)
foliar trait models — Nitrogen, Calcium, Lignin, Cellulose, and leaf mass
per area (LMA) of the 20 traits in the full product — were trained on
AVIRIS-NG L2B enhanced surface reflectance (Kovach et al., 2025) and
community-weighted-mean field chemistry from 542 plots collected
concurrent with image acquisition (median 9-day mismatch between plot
sampling and overpass). Training used an ensemble permutational approach:
an 85/15 train/validation split, with the 85% further split 30 times to
select the optimal number of PLSR components, repeated across 200
iterations to yield 200 models per trait — the mean prediction and the
standard deviation across those 200 iterations are what this project
treats as each trait's mean and uncertainty layers. A second,
independently-trained model set associated with the SHIFT campaign
(Santa Barbara, CA) was used for the California test — see the sensors
table footnote for what's confirmed vs. inferred about its training data.

**The core technical problem**: Tanager's `basic_sr_hdf5` format is not
readable by existing trait-modeling pipelines (HyTools, built for this
lab's airborne processing, has no reader for it — it's a different HDF5
schema entirely, not the NEON format its one HDF5 reader expects). We
built a standalone reader and resampling pipeline instead of forcing
Tanager into infrastructure designed for large airborne tiles.

**Cross-sensor spectral matching**: applying an AVIRIS-NG-trained model to
Tanager reflectance isn't a matter of matching wavelengths alone — the two
sensors have different spectral response widths (FWHM) at every band.
Tanager's FWHM runs 5.2–6.8 nm depending on wavelength; AVIRIS-NG's is
flatter, 5.6–6.0 nm. We built each target band as a Gaussian relative
spectral response, using the quadrature difference between the two
sensors' real FWHM to determine the matching kernel width — not a generic
resampling, and not assuming either sensor's nominal spec sheet FWHM
matches its as-flown FWHM (we pulled AVIRIS-NG's real per-band FWHM from
an actual corrected flightline rather than the trait model's own metadata,
which didn't carry it).

**Model variant**: BioSCape's trait models come in two spectral-range
flavors per trait — infrared-only (1000–2450 nm) and full-spectrum
(450–2450 nm). We used full-spectrum models for every trait in this
project (Section 3 shows why). *[Note: earlier drafts of this section
described the BioSCape team's own same-sensor comparison between the two
ranges in more detail — cut for now since that internal assessment is
still in review at the ORNL DAAC and not yet citable as published. Worth
revisiting how to reference it once we decide how to handle in-review
work throughout — see note at the end of this section.]*

**Vegetation masking**: model training for the BioSCape trait maps
excluded pixels below NDVI 0.4 or below 0.1 reflectance at 807 nm, to
remove non-vegetated and shadowed pixels (per internal project
documentation, in review at the ORNL DAAC as of this writing). We
independently derived masking thresholds for each scene used in this
project (Tanager Cape, Tanager California) directly from that scene's own
reflectance histogram rather than reusing these values outright, since
surface reflectance levels aren't necessarily comparable band-for-band
across sensors and processing pipelines — but landed on a similar
NDVI-plus-NIR-brightness approach.

*[Open question for Henry: several numbers in this section (542 plots,
the NRMSE/NSE table in Section 3, the masking thresholds above) come from
`bioscape_trait_map_V1_DAAC.docx`, which is in review, not published. My
suggestion: cite it as "BioSCape trait maps, in review at ORNL DAAC
(2026)" — standard practice for citing your own team's forthcoming work,
and accurate about its status — rather than removing the numbers
entirely, since they're genuinely useful grounding. But this is your call
given publication norms/embargo concerns I can't fully judge from here;
flag if you'd rather strip specifics until it's public.]*

## 3. Cape Floristic Region trait maps

Applying the BioSCape models to the Tanager scene, then checking predicted
values against 646 community-weighted-mean field plots from the same
region (none of which happen to fall inside this specific scene — see
Section 6), Nitrogen and Lignin transfer best:

| Trait | Predicted median | Field (CWM) median | % within model's own valid range |
|---|---|---|---|
| Nitrogen | 15.74 mg/g | 9.73 mg/g | 95.0% |
| Lignin | 130.68 mg/g | 148.81 mg/g | 94.0% |
| Calcium | 19.08 mg/g | 7.24 mg/g | 95.3% |
| Cellulose | 101–107 mg/g | 161.63 mg/g | 53.1% |

It's worth noting these traits weren't equally strong same-sensor models
to begin with: internal BioSCape validation (independent AVIRIS-NG
holdout data, not cross-sensor; in review at the ORNL DAAC as of this
writing) reports Nitrogen and Calcium as
the more reliable models here (NRMSE 0.109 and 0.081, Nash-Sutcliffe
Efficiency 0.313 and 0.26), with Lignin and Cellulose already weaker
same-sensor (NRMSE 0.192 and 0.164, NSE 0.182 and 0.247). Lignin's strong
cross-sensor field match despite a middling same-sensor score is notable
on its own; Cellulose's cross-sensor weakness is at least partly
inherited rather than purely a transfer artifact.

Lignin is the closest match to field values outright. Nitrogen and
Calcium both pass their own model's internal sanity check on ~95% of
vegetated pixels, but only Nitrogen's absolute values track the field
data closely — Calcium runs roughly 2.6x high, a finding that only
surfaced once we checked against real field values rather than trusting
the model's own diagnostic range (which just confirms a prediction is
in-distribution for the model, not realistic for the landscape). Cellulose
is the weakest of the four: only about half of vegetated pixels pass even
the model's own sanity check, so we're presenting it in tables with a
clear caveat rather than as a headline map. LMA was dropped from the Cape
analysis entirely — it produced physically impossible negative values
across most of the scene (Section 7 explains the fix that solved this for
California).

*[Figure: `figures/20250504_..._Nitrogen_Lignin_Cellulose_ternary.tif` +
legend — ternary composite, clear agricultural-field vs. natural-vegetation
contrast.]*

## 4. Cross-sensor comparison: EMIT

No EMIT overpass exists near Tanager's exact acquisition date — the
nearest same-year passes were 71–101 days off-season. Checking day-of-year
proximity across every EMIT acquisition ever made over this footprint
(EMIT's ISS-hosted, non-repeating orbit means opportunistic coverage, not
a fixed revisit) found a much closer seasonal match a year earlier
(15 days off), but that pass's swath only clips 17% of the scene. We chose
the best full-coverage option instead: 2026-03-02, 63 days off-season but
100% AOI coverage in a single granule.

Despite the platform difference, processing pipeline difference, and
~10-month acquisition gap, predicted trait values agree closely over the
same ground:

| Trait | Tanager median | EMIT median | Agreement |
|---|---|---|---|
| Nitrogen | 15.74 mg/g | 14.54 mg/g | ~8% |
| Cellulose | 101.33 mg/g | 96.58 mg/g | ~5% |
| Calcium | 19.08 mg/g | 21.46 mg/g | ~12% |
| Lignin | 130.68 mg/g | 160.24 mg/g | ~23% |

Calcium and Lignin's larger gaps run in the *same direction* as their
bias against field data (Section 3) — suggesting these are properties of
the cross-sensor transfer methodology itself, not something specific to
either satellite.

*[Figures: `figures/tanager_vs_emit_sidebyside_maps.png` (all 4 traits,
same field-referenced color scale), `figures/emit_vs_tanager_density.png`
(distribution overlays), `figures/tanager_emit_difference_map.png`
(per-pixel EMIT−Tanager).]*

The difference map is worth a closer look on its own: Lignin's offset is
close to **uniform across the entire scene** — consistent with a
systematic sensor/calibration difference rather than a landcover effect.
Calcium's disagreement, by contrast, has real **spatial structure** — the
southern part of the scene runs noticeably higher for EMIT than the
north, which is not what you'd expect from simple noise.

## 5. Cross-sensor comparison: airborne AVIRIS-NG

BioSCape's own AVIRIS-NG airborne campaign flew directly under part of
this Tanager scene in November 2023 — 30.6% of the footprint, across 24
processed flight-line tiles. That imagery had never been mosaicked for
this specific area before this project (it falls outside all six of
BioSCape's existing named regional mosaics). We built that mosaic and
compared it against the Tanager and EMIT predictions in the overlap area.

For Nitrogen, all three independently-processed products land close
together:

| Product | Median (mg/g) |
|---|---|
| Tanager | 15.72 |
| EMIT | 14.58 |
| AVIRIS-NG (airborne) | 16.92 |

*[Figure: `figures/nitrogen_tanager_emit_aviris.png` — three-panel
comparison; the AVIRIS-NG strip's spatial pattern visibly echoes the same
subregion in the Tanager and EMIT panels.]*

We're presenting this three-way comparison for Nitrogen only. The
precomputed AVIRIS-NG trait tiles use a different model variant
(IR-only) than what we determined works best for Tanager/EMIT
(Section 2) for three of the four traits — a real confound we'd rather
flag than paper over with a comparison that looks cleaner than it is.

## 6. Validation, reframed

This region is one of the most densely ground-truthed landscapes for
foliar traits anywhere. We checked two independent field datasets against
this scene's exact footprint:

- **646 community-weighted-mean plots** (BioSCape's own field campaign):
  zero overlap. Nearest cluster is 17.5 km outside the scene edge.
- **~2,500–9,500 individual leaf samples** (a broader regional survey,
  GCFR Dimensions data paper): zero overlap. Nearest sample ~60 km away.

Neither dataset — one built specifically for this region's remote sensing
validation, the other a much denser general survey — happens to fall
inside the one Tanager scene currently in the open catalog for this area.
Even BioSCape's own airborne imagery, flown specifically over this
landscape, only reaches 30% of it (Section 5), and that 30% had never been
processed into a usable product until this project. **The
infrastructure to validate hyperspectral products here is unusually
rich — and the current Tanager coverage still doesn't reach it.**

## 7. Generalizability: California

To test whether this cross-sensor methodology is Cape-specific or
general, we applied a second, independently-trained model set — from
NASA JPL's SHIFT campaign (Santa Barbara, CA), trained on a blend of
AVIRIS-Classic and NEON reflectance — to a Tanager scene over the SHIFT
study area, using the same FWHM-matching pipeline built for the Cape.

One trait needed a real fix along the way: LMA and Calcium in the SHIFT
models were fit on a square-root-transformed response (avoids negative
predictions by construction). Implementing that inverse transform
correctly — squaring each bootstrap prediction *before* averaging, not
after, since that matters for a nonlinear transform — fixed LMA's Cape
failure mode entirely: from 16% of pixels within a physically plausible
range to 99.8%, with a sensible median (80.5 g/m²) instead of runaway
negative values.

*[Figure: `figures/california_sidebyside_maps.png` — all 5 traits,
coherent mountain/valley/agricultural gradients, field-referenced color
scale.]*

No ground-truth check has been done for California in this project — this
section demonstrates that the *methodology* generalizes across two
different Mediterranean-climate ecosystems on two continents, using two
independently-trained model libraries, not that the California predictions
themselves are validated. We're stating that distinction explicitly rather
than letting the strong visual result imply more than it should.

## 8. The ask

Winning teams in this competition get to directly influence which 30
Tanager scenes Planet releases into the open catalog next. That's not a
footnote — it's the reason this project is worth entering.

**Two concrete requests, grounded in what this project found:**

1. **More Tanager coverage of the Cape Floristic Region**, specifically
   scenes that overlap BioSCape's existing ground-truth plot network and
   processed airborne imagery. This region has more validation
   infrastructure per square kilometer than almost anywhere else
   hyperspectral trait models get tested — the current open-catalog scene
   simply doesn't reach any of it.
2. **More Tanager coverage of the SHIFT study area in California**, for
   the same reason — an independently-trained, independently-validated
   model library already exists there, ready to be checked against new
   spaceborne data the moment coverage exists.

More speculatively: the methodology demonstrated here — real per-sensor
FWHM matching, explicit handling of where cross-sensor transfer breaks
down, honest reporting of what's validated vs. demonstrated — isn't
specific to the Cape or California. The same approach could extend to
other Mediterranean-climate regions with existing airborne trait-model
infrastructure: the Mediterranean Basin, central Chile, southwestern
Australia. We're not claiming that here — we've tested two of five. But
two independent confirmations, on two continents, using two different
model libraries, is a real starting point for that broader vision, not
just an assertion of it.

---

## References

Cardoso, A. W., Hestir, E. L., Slingsby, J. A., Forbes, C. J., Moncrieff,
G. R., Turner, W., Skowno, A. L., Nesslage, J., Brodrick, P. G., Gaddis,
K. D., & Wilson, A. M. (2025). The biodiversity survey of the Cape
(BioSCape), integrating remote sensing with biodiversity science. *npj
Biodiversity*, 4(1), 2. https://doi.org/10.1038/s44185-024-00071-5

Kovach, K. R., Ye, Z., Frye, H., & Townsend, P. A. (2025). BioSCape:
AVIRIS-NG L2B Enhanced Surface Reflectance (Version 1) [netCDF]. ORNL
Distributed Active Archive Center. https://doi.org/10.3334/ORNLDAAC/2385

*(SHIFT campaign and Tanager platform citations still needed — see Open
items below.)*

## Appendix: Figure inventory

| Figure | File |
|---|---|
| Cape ternary composite (Nitrogen/Lignin/Cellulose) | `trait_outputs/20250504_..._Nitrogen_Lignin_Cellulose_ternary.tif` + legend |
| Tanager vs. EMIT, all 4 traits, side by side | `figures/tanager_vs_emit_sidebyside_maps.png` |
| Tanager vs. EMIT, density distributions | `figures/emit_vs_tanager_density.png` |
| Tanager vs. EMIT, per-pixel difference | `figures/tanager_emit_difference_map.png` |
| Nitrogen: Tanager vs. EMIT vs. AVIRIS-NG | `figures/nitrogen_tanager_emit_aviris.png` |
| California, all 5 traits | `figures/california_sidebyside_maps.png` |

## Appendix: Open items before submission

- [ ] Decide whether to include the FWHM-curve-comparison figure
      mentioned in the outline (Section 2) — not yet built.
- [ ] Cellulose: confirm final call on presenting as a caveated table row
      only (recommended) vs. dropping entirely.
- [ ] Tighten Section 1/8 for final word count once overall length target
      is known.
- [ ] Fill in exact SHIFT campaign dates/citation once confirmed.
- [x] BioSCape/AVIRIS-NG citations and DOI added (Cardoso et al. 2025,
      Kovach et al. 2025) — pulled from
      `Manuscripts/bioscape_trait_map_V1_DAAC.docx`.
- [ ] Still need: SHIFT campaign citation, Tanager platform citation, and
      (once available) a citation/DOI for the BioSCape trait-map product
      itself (the DAAC doc this session pulled from is a pre-submission
      draft, not yet published with its own DOI).
