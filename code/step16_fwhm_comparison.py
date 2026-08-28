"""FWHM-vs-wavelength comparison, Tanager vs. AVIRIS-NG -- the figure
mentioned in the outline (Section 2) but never built, per Henry's request
to generate it and decide whether it's worth including.

Both arrays are real, not nominal spec-sheet values: Tanager's from the
example scene's own h5 attrs, AVIRIS-NG's from an actual corrected
BioSCape flightline (same source step2 uses for cross-sensor matching).
"""
import h5py
import netCDF4 as nc
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TANAGER_H5 = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/raw_h5/"
    "20250504_092952_87_4001_basic_sr_hdf5.h5"
)
AVIRIS_REFERENCE_NC = (
    "/Volumes/Enspec/projects/BioScape/Lines_Corrected_Hyperspectral/"
    "ang20231022t092801_000_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1.nc"
)
OUT_PATH = "writeup/figures/fwhm_comparison.png"


def get_tanager_fwhm():
    with h5py.File(TANAGER_H5, "r") as hf:
        sr = hf["HDFEOS/SWATHS/HYP/Data Fields/surface_reflectance"]
        return np.array(sr.attrs["wavelengths"], dtype=float), np.array(sr.attrs["fwhm"], dtype=float)


def get_aviris_fwhm():
    ds = nc.Dataset(AVIRIS_REFERENCE_NC)
    refl = ds.groups["reflectance"]
    wl = np.array(refl.variables["wavelength"][:], dtype=float)
    fwhm = np.array(refl.variables["fwhm"][:], dtype=float)
    ds.close()
    return wl, fwhm


def main():
    tan_wl, tan_fwhm = get_tanager_fwhm()
    av_wl, av_fwhm = get_aviris_fwhm()

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(tan_wl, tan_fwhm, label="Tanager (this scene)", color="#d55e00", linewidth=1.5)
    ax.plot(av_wl, av_fwhm, label="AVIRIS-NG (BioSCape flightline)", color="#0072b2", linewidth=1.5)
    ax.fill_between(tan_wl, tan_fwhm, np.interp(tan_wl, av_wl, av_fwhm),
                     where=(tan_fwhm > np.interp(tan_wl, av_wl, av_fwhm)),
                     color="#d55e00", alpha=0.15, label="Tanager wider (can't sharpen)")
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("FWHM (nm)")
    ax.set_title("Spectral response width by wavelength: Tanager vs. AVIRIS-NG\n(real per-band values, not nominal spec-sheet FWHM)")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_xlim(376, 2500)
    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150)
    print(f"Wrote {OUT_PATH}")

    print(f"\nTanager FWHM range: {tan_fwhm.min():.2f}-{tan_fwhm.max():.2f} nm")
    print(f"AVIRIS-NG FWHM range: {av_fwhm.min():.2f}-{av_fwhm.max():.2f} nm")
    tan_wider_frac = (tan_fwhm > np.interp(tan_wl, av_wl, av_fwhm)).mean()
    print(f"Fraction of Tanager bands wider than AVIRIS-NG at that wavelength: {tan_wider_frac*100:.0f}%")


if __name__ == "__main__":
    main()
