"""Render step5's field-referenced ternary GeoTIFF to the report PNG,
with a north arrow and scale bar -- previously a manual QGIS export with
neither (2026-08-28, Henry's review). Builds it in Python instead of
QGIS so the figure is reproducible from this repo alone, same rationale
as step5's own raw_rgb port.

The GeoTIFF is UTM 34S (EPSG:32734), 30m pixels, north-up -- a plain
image plot preserves true north without needing an axes projection.
"""
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects

TERNARY_TIF = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"
    "20250504_092952_87_4001_basic_sr_hdf5_Nitrogen_Lignin_Calcium_ternary.tif"
)
OUT_PATH = "writeup/figures/ternary_field_referenced.png"

SCALE_BAR_M = 5000  # 5 km


def main():
    with rasterio.open(TERNARY_TIF) as src:
        rgb = src.read([1, 2, 3])
        alpha = src.read(4)
        px_size_m = src.transform.a
        height, width = src.height, src.width

    img = np.moveaxis(rgb, 0, -1).astype(float) / 255.0
    img_rgba = np.dstack([img, alpha.astype(float) / 255.0])

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(img_rgba)
    ax.axis("off")

    # Scale bar: bottom-left, in data (pixel) coordinates.
    bar_px = SCALE_BAR_M / px_size_m
    margin_x = width * 0.05
    margin_y = height * 0.06
    bar_y = height - margin_y
    ax.plot([margin_x, margin_x + bar_px], [bar_y, bar_y], color="white",
             linewidth=3, solid_capstyle="butt")
    ax.plot([margin_x, margin_x + bar_px], [bar_y, bar_y], color="black",
             linewidth=1, solid_capstyle="butt")
    ax.text(margin_x + bar_px / 2, bar_y - height * 0.015, f"{SCALE_BAR_M // 1000} km",
            color="white", ha="center", va="bottom", fontsize=11, fontweight="bold",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=2.5, foreground="black")])

    # North arrow: top-right.
    arrow_x = width * 0.94
    arrow_y_tail = height * 0.16
    arrow_y_head = height * 0.04
    ax.annotate("", xy=(arrow_x, arrow_y_head), xytext=(arrow_x, arrow_y_tail),
                arrowprops=dict(facecolor="white", edgecolor="black", width=4, headwidth=12, headlength=10))
    ax.text(arrow_x, arrow_y_tail + height * 0.015, "N", color="white", ha="center",
            va="top", fontsize=13, fontweight="bold",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=2.5, foreground="black")])

    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight", pad_inches=0.05)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
