"""Ternary (3-trait RGB composite) map from step2's trait GeoTIFFs.

Ports the "raw_rgb" method from
Workflow11_Trait_Map_Assess/code/make_ternary_map.R (direct per-trait
normalization into R/G/B, no perceptual color mixing) to Python, since
this project's pipeline is Python-only (no R/renv/tricolore/ggtern setup
here) and raw_rgb is that script's own documented lab default anyway.
That R script's docstring says raw_rgb is "equivalent to the Python
ternary script" -- found that precedent at
BioSCapeTownsend/PreliminaryAnalysisScripts/ternary_create__folder.py,
an older per-flightline prototype (ENVI input, NDVI-band masking, no
legend). This version applies step4's veg_mask instead of that script's
band-4 NDVI hack, and writes a matching ternary legend (neither the old
Python prototype nor a from-scratch legend existed for it).

Normalization ranges default to the region-wide CWM plot p5-p95 (from
CLAUDE.md's "Regional ballpark check") rather than this scene's own
predicted min/max -- "reasonable intervals" grounded in actual field
data, not the scene's own (partly biased, e.g. Calcium) prediction range.
"""
import os

import numpy as np
import rasterio

TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
STEM = "20250504_092952_87_4001_basic_sr_hdf5"

TRAIT_TIFS = {
    "Nitrogen": TRAIT_OUTPUT_DIR + f"{STEM}_plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif",
    "Calcium": TRAIT_OUTPUT_DIR + f"{STEM}_plsr__sampled_Calcium_mg_per_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif",
    "Lignin": TRAIT_OUTPUT_DIR + f"{STEM}_plsr__sampled_Lignin_recal_mg_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif",
    "Cellulose": TRAIT_OUTPUT_DIR + f"{STEM}_plsr__sampled_Cellulose_mg_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa.tif",
}
NDVI_MASK_TIF = TRAIT_OUTPUT_DIR + f"{STEM}_ndvi_shadow_mask.tif"

# Region-wide CWM plot p5-p95 (mg/g), from the regional ballpark check --
# NOT this scene's own predicted range, deliberately: using the scene's
# own min/max would make every map "well-stretched" regardless of how
# biased the underlying predictions are (Calcium's ~2.6x high bias would
# just get quietly renormalized away). All FULL-uvf -- see step2's
# comment / CLAUDE.md "IR-uvf vs FULL-uvf: a real detour" for why IR-uvf
# was tried and reverted.
#
# Default is Nitrogen/Lignin/Calcium, not Cellulose (2026-08-28, Henry's
# call): Cellulose only passes its own diagnostic range check on 53% of
# vegetated pixels (weakest of the four kept traits by a wide margin --
# see CLAUDE.md/report Section 3), so it's dropped from this headline
# figure and kept as a caveated table row instead. Calcium's own known
# high bias (~2.6x vs. field data) means it'll skew toward its channel's
# bright end almost everywhere in this scene -- a real tradeoff, not a
# clean win -- but Calcium and Cellulose are also plausibly biologically
# linked (Ca cross-links pectin in the cell wall matrix via calcium-
# pectate bridges, alongside cellulose's fibrillar backbone), which is
# at least a defensible reason to pair Calcium with Lignin/Nitrogen here
# rather than an arbitrary swap.
TRAIT_RANGES = {
    "Nitrogen": (4.71, 23.51),
    "Calcium": (1.51, 16.67),
    "Lignin": (55.83, 245.03),
    "Cellulose": (79.76, 316.16),
}

# R / G / B corner assignment
TRAIT1, TRAIT2, TRAIT3 = "Nitrogen", "Lignin", "Calcium"

OUTPUT_TIF = TRAIT_OUTPUT_DIR + f"{STEM}_{TRAIT1}_{TRAIT2}_{TRAIT3}_ternary.tif"
OUTPUT_LEGEND = TRAIT_OUTPUT_DIR + f"{STEM}_{TRAIT1}_{TRAIT2}_{TRAIT3}_ternary_legend.png"


def normalize(arr, lo, hi):
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def load_trait_mean(path):
    with rasterio.open(path) as src:
        mean = src.read(1)
        nodata = src.nodata
        profile = src.profile
    return mean, mean == nodata, profile


def main():
    r_val, r_nodata, profile = load_trait_mean(TRAIT_TIFS[TRAIT1])
    g_val, g_nodata, _ = load_trait_mean(TRAIT_TIFS[TRAIT2])
    b_val, b_nodata, _ = load_trait_mean(TRAIT_TIFS[TRAIT3])

    with rasterio.open(NDVI_MASK_TIF) as src:
        veg_mask = src.read(3)  # band 3 = veg_mask, from step4
        veg_nodata = src.nodata

    valid = (~r_nodata) & (~g_nodata) & (~b_nodata) & (veg_mask == 1) & (veg_mask != veg_nodata)
    print(f"Valid (vegetated, unmasked) pixels: {valid.sum()} / {valid.size} ({valid.mean()*100:.1f}%)")

    r_n = normalize(r_val, *TRAIT_RANGES[TRAIT1])
    g_n = normalize(g_val, *TRAIT_RANGES[TRAIT2])
    b_n = normalize(b_val, *TRAIT_RANGES[TRAIT3])

    rgb = np.zeros((3, *r_val.shape), dtype=np.uint8)
    for i, band in enumerate([r_n, g_n, b_n]):
        out = np.round(band * 255).astype(np.uint8)
        out[~valid] = 0
        rgb[i] = out

    alpha = np.where(valid, 255, 0).astype(np.uint8)

    out_profile = profile.copy()
    out_profile.update(count=4, dtype="uint8", nodata=None)
    with rasterio.open(OUTPUT_TIF, "w", **out_profile) as dst:
        dst.write(rgb[0], 1)
        dst.write(rgb[1], 2)
        dst.write(rgb[2], 3)
        dst.write(alpha, 4)
        dst.set_band_description(1, f"{TRAIT1}_R")
        dst.set_band_description(2, f"{TRAIT2}_G")
        dst.set_band_description(3, f"{TRAIT3}_B")
        dst.set_band_description(4, "alpha")
    print(f"Wrote {OUTPUT_TIF}")
    print("Load in QGIS: Multiband color render, R=1 G=2 B=3, alpha=4, no contrast enhancement.")

    make_legend()


def make_legend():
    import matplotlib.pyplot as plt

    n = 300
    fig, ax = plt.subplots(figsize=(5, 5))
    p1 = np.linspace(0, 1, n)
    p2 = np.linspace(0, 1, n)
    P1, P2 = np.meshgrid(p1, p2)
    P3 = 1 - P1 - P2
    img = np.stack([P1, P2, P3], axis=-1)
    img[P3 < 0] = np.nan

    ax.imshow(img, origin="lower", extent=[0, 1, 0, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    # img = stack([P1, P2, P3]) -> R=P1(trait1), G=P2(trait2), B=P3(trait3).
    # (x=1,y=0)->P1=1: pure red/trait1. (x=0,y=1)->P2=1: pure green/trait2.
    # (x=0,y=0)->P3=1: pure blue/trait3.
    ax.plot([0, 1, 0, 0], [0, 0, 1, 0], color="black", linewidth=1)
    ax.text(1.05, -0.05, TRAIT1, color="red", fontweight="bold", ha="left", va="top")
    ax.text(-0.05, 1.05, TRAIT2, color="green", fontweight="bold", ha="right", va="bottom")
    ax.text(-0.05, -0.05, TRAIT3, color="blue", fontweight="bold", ha="right", va="top")

    fig.savefig(OUTPUT_LEGEND, dpi=150, transparent=True, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUTPUT_LEGEND}")


if __name__ == "__main__":
    main()
