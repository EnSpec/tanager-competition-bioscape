"""Check whether BioSCape CWM ground plots overlap the Tanager scene.

Reads the community-weighted-mean trait plot geojson (from
Workflow9_community_weighted_means), transforms plot coordinates into the
scene's ortho UTM grid (read straight off the h5's Planet_Ortho_Framing
attr, so this stays correct if a different scene is swapped in), and
either compares predicted vs. ground trait values at overlapping plots or
reports the nearest plots and their distance if nothing overlaps.

Not a formal validation (2-3 plots at most even in the best case) --
just a ballpark sanity check.
"""
import json
import os

import fsspec
import h5py
import numpy as np
import pyproj
import rasterio

TANAGER_H5 = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/raw_h5/"
    "20250504_092952_87_4001_basic_sr_hdf5.h5"
)
CWM_GEOJSON = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/ground_validation/"
    "cwm_bioscape_1.4_cover_uncert.geojson"
)
TRAIT_OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"

# ground-truth geojson property name -> trait GeoTIFF stem (from step2's
# TRAIT_MODELS list / os.path.basename(model_path) minus ".json")
TRAIT_MATCHUPS = {
    "sampled_Nitrogen_merged_cwm_iter_mean": "plsr__sampled_Nitrogen_merged_cwm_iter_mean__FULL-uvf__ideny__rep__boa",
    "sampled_Calcium_mg_per_g_cwm_iter_mean": "plsr__sampled_Calcium_mg_per_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa",
    "sampled_Lignin_recal_mg_g_cwm_iter_mean": "plsr__sampled_Lignin_recal_mg_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa",
    "sampled_Cellulose_mg_g_cwm_iter_mean": "plsr__sampled_Cellulose_mg_g_cwm_iter_mean__FULL-uvf__ideny__rep__boa",
}


def get_ortho_framing(h5_path):
    opener = fsspec.open(h5_path, mode="rb") if h5_path.startswith("http") else open(h5_path, "rb")
    with opener as f:
        hf = h5py.File(f, "r")
        geo = hf["HDFEOS/SWATHS/HYP/Geolocation Fields"]
        return json.loads(geo.attrs["Planet_Ortho_Framing"])


def main():
    framing = get_ortho_framing(TANAGER_H5)
    epsg, gt = framing["epsg_code"], framing["geotransform"]
    xmin, xmax = gt[0], gt[0] + framing["cols"] * gt[1]
    ymin, ymax = gt[3] + framing["rows"] * gt[5], gt[3]

    transformer = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)

    with open(CWM_GEOJSON, "r") as f:
        cwm = json.load(f)

    overlapping = []
    all_plots = []
    for feat in cwm["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        x, y = transformer.transform(lon, lat)
        dx = max(xmin - x, 0.0, x - xmax)
        dy = max(ymin - y, 0.0, y - ymax)
        edge_dist = (dx**2 + dy**2) ** 0.5
        all_plots.append((edge_dist, feat["properties"]["Plot"], lon, lat, x, y, feat["properties"]))
        if edge_dist == 0.0:
            overlapping.append((feat["properties"]["Plot"], x, y, feat["properties"]))

    print(f"Scene UTM{epsg} bounds: x[{xmin:.0f},{xmax:.0f}] y[{ymin:.0f},{ymax:.0f}]")
    print(f"{len(overlapping)} of {len(all_plots)} CWM plots fall within the scene footprint.")

    if not overlapping:
        all_plots.sort(key=lambda p: p[0])
        print("\nNo ground plots overlap this scene. Nearest plots:")
        for edge_dist, plot, lon, lat, x, y, props in all_plots[:5]:
            print(f"  {plot:12s} {edge_dist/1000:6.2f} km outside scene edge  (lon={lon:.4f}, lat={lat:.4f})")
        return

    print("\nComparing predicted vs. ground CWM at overlapping plots:")
    for plot, x, y, props in overlapping:
        col = int((x - gt[0]) / gt[1])
        row = int((y - gt[3]) / gt[5])
        print(f"\n{plot} (grid col={col}, row={row}):")
        for ground_key, tif_stem in TRAIT_MATCHUPS.items():
            ground_val = props.get(ground_key)
            tif_path = os.path.join(
                TRAIT_OUTPUT_DIR,
                os.path.splitext(os.path.basename(TANAGER_H5))[0] + f"_{tif_stem}.tif",
            )
            if not os.path.exists(tif_path):
                continue
            with rasterio.open(tif_path) as src:
                pred = src.read(1)[row, col]
                pred = None if pred == src.nodata else float(pred)
            print(f"  {ground_key:45s} ground={ground_val:8.2f}  predicted={pred}")


if __name__ == "__main__":
    main()
