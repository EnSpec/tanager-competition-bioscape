"""NDVI + shadow/water mask for the California scene, same treatment
step4 gave the Cape scene -- reuses its compute_and_write_mask(), with
thresholds picked from THIS scene's own R800/NDVI histogram rather than
reusing the Cape numbers (surface reflectance levels aren't necessarily
comparable band-for-band across acquisitions).

This scene's histogram is more clearly bimodal than the Cape one: ~15%
of pixels (the coastal/ocean/urban strip visible in
figures/california_qa_preview.png) sit at R800<0.02 and NDVI<0, then
there's a clean gap before the vegetated bulk starts at R800>=0.16,
NDVI>=0.35 -- any threshold in that gap works equally well; picked 0.05
and 0.2 to stay consistent with the Cape scene's thresholds rather than
introduce a different convention without a reason to.
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from step4_ndvi_shadow_mask import compute_and_write_mask

CA_H5 = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/raw_h5/"
    "20250407_192247_40_4001_basic_sr_hdf5.h5"
)
OUTPUT_DIR = "/Volumes/Enspec/projects/BioScape/tanager_competition/trait_outputs/"

SHADOW_R800_THRESHOLD = 0.05
VEG_NDVI_THRESHOLD = 0.2


def main():
    out_path = OUTPUT_DIR + "20250407_192247_40_4001_basic_sr_hdf5_ndvi_shadow_mask.tif"
    compute_and_write_mask(CA_H5, out_path, SHADOW_R800_THRESHOLD, VEG_NDVI_THRESHOLD)


if __name__ == "__main__":
    main()
