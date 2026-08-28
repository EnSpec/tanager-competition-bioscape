"""Render step5's field-referenced ternary GeoTIFF to the report PNG,
with a north arrow (bottom-right) and scale bar (bottom-left, nudged
toward center) -- previously a manual QGIS export with neither
(2026-08-28, Henry's review). Builds it in Python instead of QGIS so
the figure is reproducible from this repo alone, same rationale as
step5's own raw_rgb port.

The GeoTIFF is UTM 34S (EPSG:32734), 30m pixels, north-up -- a plain
image plot preserves true north without needing an axes projection.
"""
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects
from matplotlib.patches import Polygon

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

    # Scale bar: bottom-left, nudged toward center, in data (pixel) coordinates.
    bar_px = SCALE_BAR_M / px_size_m
    margin_x = width * 0.10
    margin_y = height * 0.06
    bar_y = height - margin_y
    ax.plot([margin_x, margin_x + bar_px], [bar_y, bar_y], color="white",
             linewidth=3, solid_capstyle="butt")
    ax.plot([margin_x, margin_x + bar_px], [bar_y, bar_y], color="black",
             linewidth=1, solid_capstyle="butt")
    ax.text(margin_x + bar_px / 2, bar_y - height * 0.015, f"{SCALE_BAR_M // 1000} km",
            color="white", ha="center", va="bottom", fontsize=14, fontweight="bold",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=2.5, foreground="black")])

    # North arrow: simple solid triangle, bottom-right, with N below the base.
    arrow_x = width * 0.94
    text_y = height - margin_y
    arrow_base = text_y - height * 0.03
    arrow_top = arrow_base - height * 0.10
    arrow_half_width = width * 0.02
    triangle = Polygon(
        [(arrow_x, arrow_top), (arrow_x - arrow_half_width, arrow_base), (arrow_x + arrow_half_width, arrow_base)],
        closed=True, facecolor="white", edgecolor="black", linewidth=1.5,
    )
    ax.add_patch(triangle)
    ax.text(arrow_x, text_y, "N", color="white", ha="center",
            va="top", fontsize=16, fontweight="bold",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=2.5, foreground="black")])

    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight", pad_inches=0.05)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
