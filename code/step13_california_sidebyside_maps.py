"""California SHIFT-model trait maps, all 5 traits side by side in one
figure -- companion to step11 (Cape), but single-sensor (no EMIT/AVIRIS-NG
counterpart exists for this scene), so this is a 1xN grid rather than a
2-column comparison.

Color scale per trait is each SHIFT model's own `field_min`/`field_max`
(the training data's observed range, straight from the model json's
`model_diagnostics`) -- the California equivalent of the Cape maps' CWM
p5-p95 field-referenced scale (no CA ground-plot dataset has been pulled
into this project the way the Cape CWM/GCFR ones were, so the model's own
field range is the best available field-grounded reference).

Veg-masked via step9's veg_mask (same fix as step11/12 -- apply the real
NDVI-derived mask, not each trait's own diagnostic range_mask, so masking
is consistent across all 5 panels).
"""
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
FIGURES_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/figures/"
CA_STEM = "20250407_192247_40_4001_basic_sr_hdf5"
VEG_MASK_TIF = TRAIT_OUTPUT_DIR + f"{CA_STEM}_ndvi_shadow_mask.tif"

# (label, stem, units, field_min/field_max from the SHIFT model jsons, colormap)
TRAITS = [
    ("Nitrogen", "nitrogen", "mg/g", (3.80, 44.20), "YlGn"),
    ("Calcium", "calcium", "mg/g", (0.80, 29.70), "PuBu"),
    ("Lignin", "lignin", "mg/g", (10.20, 332.30), "YlOrBr"),
    ("Cellulose", "cellulose", "mg/g", (47.00, 271.00), "viridis"),
    ("LMA", "LMA", "g/m2", (43.89, 682.18), "magma"),
]


def load_veg_mask():
    with rasterio.open(VEG_MASK_TIF) as src:
        veg_mask = src.read(3)
        nodata = src.nodata
    return (veg_mask == 1) & (veg_mask != nodata)


def load_masked(stem, veg_mask):
    path = TRAIT_OUTPUT_DIR + f"{CA_STEM}_shift_{stem}.tif"
    with rasterio.open(path) as src:
        mean = src.read(1)
        rmask = src.read(3)
        nodata = src.nodata
    return np.where((mean == nodata) | (rmask != 1) | (~veg_mask), np.nan, mean)


def main():
    veg_mask = load_veg_mask()
    fig, axes = plt.subplots(1, len(TRAITS), figsize=(4 * len(TRAITS), 5))

    for ax, (label, stem, units, (lo, hi), cmap_name) in zip(axes, TRAITS):
        cmap = matplotlib.colormaps[cmap_name].copy()
        cmap.set_bad("lightgray")

        arr = load_masked(stem, veg_mask)
        im = ax.imshow(arr, cmap=cmap, vmin=lo, vmax=hi)
        ax.set_title(f"{label}\n({units})", fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        valid = arr[~np.isnan(arr)]
        print(f"{label}: n_valid={valid.size}, median={np.median(valid):.2f}" if valid.size else f"{label}: no valid pixels")

    fig.suptitle(
        "California (SHIFT models) predicted trait maps, 2025-04-07\n"
        "(color scale = each model's own field-data range; gray = non-vegetated or outside diagnostic range)",
        fontsize=11,
    )
    out_path = FIGURES_DIR + "california_sidebyside_maps.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
