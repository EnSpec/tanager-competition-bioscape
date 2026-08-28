"""California SHIFT-model trait maps, all 5 traits side by side in one
figure -- companion to step11 (Cape), but single-sensor (no EMIT/AVIRIS-NG
counterpart exists for this scene), so this is a 1xN grid rather than a
2-column comparison.

No ground-truth check has been run for California in this project (see
CLAUDE.md / report Section 7) -- unlike the Cape maps, there's no
field-referenced range to validate against here. Displaying continuous
numeric values with a units-labeled colorbar would visually imply a
precision this map doesn't have. Instead, each trait is binned into
Low/Med/High terciles of ITS OWN valid-pixel distribution in this scene
(2026-08-28, per Henry's review) -- this is a relative, within-scene
pattern display only, explicitly not a numerically validated product.
The qualitative pattern (e.g. agricultural/vineyard parcels reading
higher nitrogen than surrounding chaparral) is the thing being shown,
not the absolute values.

Veg-masked via step9's veg_mask (same fix as step11/12 -- apply the real
NDVI-derived mask, not each trait's own diagnostic range_mask, so masking
is consistent across all 5 panels).
"""
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
FIGURES_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/figures/"
CA_STEM = "20250407_192247_40_4001_basic_sr_hdf5"
VEG_MASK_TIF = TRAIT_OUTPUT_DIR + f"{CA_STEM}_ndvi_shadow_mask.tif"

# (label, stem, 3-color low->high palette per trait's original color family)
TRAITS = [
    ("Nitrogen", "nitrogen", ("#f7fcb9", "#78c679", "#005a32")),
    ("Calcium", "calcium", ("#f1eef6", "#74a9cf", "#023858")),
    ("Lignin", "lignin", ("#ffffd4", "#fe9929", "#8c2d04")),
    ("Cellulose", "cellulose", ("#fde725", "#21918c", "#440154")),
    ("LMA", "LMA", ("#fcfdbf", "#f1605d", "#280b53")),
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
    ncols = 3
    nrows = 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 5.2 * nrows))
    fig.subplots_adjust(hspace=0.25, wspace=0.35, top=0.86)
    axes = axes.flatten()
    for ax in axes[len(TRAITS):]:
        ax.axis("off")

    for ax, (label, stem, colors) in zip(axes, TRAITS):
        arr = load_masked(stem, veg_mask)
        valid = arr[~np.isnan(arr)]
        if valid.size == 0:
            print(f"{label}: no valid pixels")
            continue

        # Tercile cutoffs from this trait's own valid-pixel distribution in
        # this scene -- relative Low/Med/High, not an absolute/validated scale.
        lo_cut, hi_cut = np.percentile(valid, [33.33, 66.67])
        binned = np.digitize(arr, [lo_cut, hi_cut]).astype(float)
        binned[np.isnan(arr)] = np.nan

        cmap = ListedColormap(colors)
        cmap.set_bad("lightgray")
        norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N)
        im = ax.imshow(binned, cmap=cmap, norm=norm)
        ax.set_title(label, fontsize=16)
        ax.set_xticks([]); ax.set_yticks([])
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, ticks=[0, 1, 2])
        cbar.ax.set_yticklabels(["Low", "Med", "High"], fontsize=13)

        print(f"{label}: n_valid={valid.size}, tercile cuts at {lo_cut:.2f}/{hi_cut:.2f} "
              f"(scene-relative, not an absolute/validated scale)")

    fig.suptitle(
        "California (SHIFT models) predicted trait patterns, 2025-04-07\n"
        "Relative Low/Med/High within this scene only -- no field validation for California in this project;\n"
        "gray = non-vegetated. Not a numerically validated product.",
        fontsize=15,
    )
    out_path = FIGURES_DIR + "california_sidebyside_maps.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
