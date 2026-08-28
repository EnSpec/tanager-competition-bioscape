"""README banner ternary composite -- Nitrogen/Lignin/Cellulose, same
traits as step5_ternary_map.py's default, but normalized differently on
purpose.

step5 normalizes to region-wide CWM field-data ranges deliberately, so
that each trait's known bias stays visible rather than getting
auto-stretched away -- correct for the report's quantitative figures
(CLAUDE.md "Ternary map" explains why).

This script normalizes each trait to THIS SCENE's own 2nd-98th percentile
range instead, purely for a more visually engaging README banner image.
That tradeoff is the opposite of step5's: much more colorful/striking,
but the bias-visibility property is gone -- this version must not be
read as implying anything about absolute trait accuracy. It's a
landscape-pattern illustration, not a quantitative figure, and the
README caption says so explicitly.

Cellulose's own scene range came out skewed (2nd/98th percentile roughly
-111 to 230 mg/g) reflecting how noisy this trait's predictions are here
(see CLAUDE.md/report Section 3) -- some of the magenta speckling in the
agricultural area is plausibly Cellulose noise, not pure signal. Worth
knowing even though the image reads well.
"""
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
STEM = "20250504_092952_87_4001_basic_sr_hdf5"

TRAITS = ("Nitrogen_merged_cwm_iter_mean", "Lignin_recal_mg_g_cwm_iter_mean", "Cellulose_mg_g_cwm_iter_mean")
OUT_PATH = "writeup/figures/ternary_composite_preview.png"


def load(name):
    path = f"{TRAIT_OUTPUT_DIR}{STEM}_plsr__sampled_{name}__FULL-uvf__ideny__rep__boa.tif"
    with rasterio.open(path) as src:
        mean = src.read(1)
        nodata = src.nodata
    return mean, mean == nodata


def scene_norm(arr, valid):
    lo, hi = np.percentile(arr[valid], [2, 98])
    return np.clip((arr - lo) / (hi - lo), 0, 1), lo, hi


def main():
    with rasterio.open(f"{TRAIT_OUTPUT_DIR}{STEM}_ndvi_shadow_mask.tif") as src:
        veg_mask = src.read(3)
        veg_nodata = src.nodata
    veg_ok = (veg_mask == 1) & (veg_mask != veg_nodata)

    vals, bads = zip(*(load(t) for t in TRAITS))
    valid = veg_ok
    for bad in bads:
        valid = valid & ~bad

    channels = []
    for name, arr in zip(TRAITS, vals):
        norm, lo, hi = scene_norm(arr, valid)
        print(f"{name}: scene 2nd-98th pct range used = {lo:.2f} to {hi:.2f}")
        channels.append(norm)

    rgb = np.stack(channels, axis=-1)
    rgb[~valid] = np.nan

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(rgb)
    ax.axis("off")
    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
