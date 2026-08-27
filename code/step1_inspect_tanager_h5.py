"""Dump the group/dataset structure of a Tanager basic_sr_hdf5 scene.

Reads via fsspec HTTP range requests by default, so it can inspect the
file directly from the Planet open-cogs bucket without downloading the
full ~1 GB scene. Pass a local path instead to inspect a downloaded copy.

Usage:
    python step1_inspect_tanager_h5.py [path_or_url]
"""
import sys

import fsspec
import h5py

DEFAULT_URL = (
    "https://storage.googleapis.com/open-cogs/planet-stac/"
    "tanager1-release2-core-imagery/basic_sr_hdf5/"
    "20250504_092952_87_4001_basic_sr_hdf5.h5"
)


def show(name, obj):
    if isinstance(obj, h5py.Dataset):
        print(f"DATASET {name}  shape={obj.shape} dtype={obj.dtype}")
    else:
        print(f"GROUP   {name}")
    for key, val in obj.attrs.items():
        print(f"    attr: {key} = {str(val)[:200]}")


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    opener = fsspec.open(source, mode="rb") if source.startswith("http") else open(source, "rb")
    with opener as f:
        hf = h5py.File(f, "r")
        hf.visititems(show)
        sr = hf["HDFEOS/SWATHS/HYP/Data Fields/surface_reflectance"]
        print("\n=== surface_reflectance summary ===")
        print("shape:", sr.shape)
        print("n wavelengths:", len(sr.attrs["wavelengths"]))
        print("wavelength range:", sr.attrs["wavelengths"].min(), "-", sr.attrs["wavelengths"].max())
        print("n good_wavelengths:", int(sr.attrs["good_wavelengths"].sum()), "/", len(sr.attrs["good_wavelengths"]))


if __name__ == "__main__":
    main()
