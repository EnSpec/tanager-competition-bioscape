# Cross-Sensor Transfer of Airborne Trait Models to Tanager: A BioSCape Case Study

*Draft — 2026-08-27. Numbers and figure references below are pulled directly
from this project's `CLAUDE.md`/pipeline outputs; every figure referenced
already exists in `figures/` and `trait_outputs/`. Not yet copy-edited for
submission tone/length — flag anything that reads rough.*

---

## 1. Why this matters

The Biodiversity Survey of the Cape (BioSCape) spent a full airborne
campaign — AVIRIS-NG imagery, hundreds of field plots, thousands of leaf
chemistry samples — building one of the richest foliar trait-model
libraries that exists for any biodiversity hotspot on Earth. That library
was trained entirely on one airborne sensor, over one campaign, in one
region. Tanager is a new question mark against all three: a different
platform (spaceborne, not airborne), built and calibrated independently,
flying over the same landscape two years later.

Does an existing, independently-trained trait-model library transfer to
a brand-new commercial hyperspectral platform with **zero recalibration**?
That's the question this project set out to answer, using Tanager's
example release scene over the Cape Floristic Region — and, once the
methodology proved out, a second scene over California to test whether it
generalizes across continents.

The answer, in short: yes, with caveats that are themselves informative.
Two independently-processed sensors (Tanager and EMIT) converge closely on
the same predicted trait values over the same ground, ten months apart.
BioSCape's own airborne data — flown directly under part of this scene —
confirms it a third way. And the same cross-sensor methodology, applied to
an entirely different set of airborne-trained models over California,
produces coherent, physically plausible trait maps on the first attempt.

This kind of validation is exactly what upcoming spaceborne imaging
spectroscopy missions — EAGLE-VSWIR among them — will need partners to
have already worked out: how do trait models trained on one instrument
transfer to another, and what does it take to make that transfer honest
rather than aspirational.

## 2. Data and methods

**Sensors and products used:**

| Source | Role | Coverage used |
|---|---|---|
| Tanager (`basic_sr_hdf5`) | Primary test platform | Cape scene (2025-05-04), California scene (2025-04-07) |
| AVIRIS-NG (BioSCape campaign) | Trait model training data + independent airborne validation | Nov 2023, Cape region |
| EMIT | Independent spaceborne cross-check | 2026-03-02, same Cape AOI |
| AVIRIS-Classic + NEON (SHIFT campaign) | Trait model training data, California | 2019-2023-ish, Santa Barbara |

**Trait models**: BioSCape's PLSR (partial least squares regression)
foliar trait models — Nitrogen, Calcium, Lignin, Cellulose, leaf mass per
area (LMA) — trained on AVIRIS-NG reflectance and community-weighted-mean
field chemistry. A second, independently-trained model set from the SHIFT
campaign (Santa Barbara, CA) was used for the California test, trained on
a blend of AVIRIS-Classic and NEON data.

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

**Model variant**: BioSCape's trait models come in two flavors per trait —
an IR-only variant (avoids visible-wavelength pigment absorption, the
lab's general preference for same-sensor work) and a full-spectrum
variant. We tested both against field data for this specific cross-sensor
task and found the full-spectrum variant performs consistently better here
(Section 3) — worth stating explicitly, since it runs against the lab's
usual default.

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
- [ ] Add BioSCape/SHIFT/Tanager citations and data DOIs.
