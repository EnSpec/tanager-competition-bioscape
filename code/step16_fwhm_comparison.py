"""FWHM-vs-wavelength comparison, Tanager vs. AVIRIS-NG vs. EMIT -- the
figure mentioned in the outline (Section 2), kept after Henry's review
(2026-08-28) and extended to add EMIT alongside the original two.

All three arrays are real, not nominal spec-sheet values: Tanager's from
the example scene's own h5 attrs, AVIRIS-NG's from an actual corrected
BioSCape flightline (same source step2 uses for cross-sensor matching),
EMIT's from the same L2A granule used in the EMIT comparison (step6).
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
EMIT_NC = (
    "/Volumes/Enspec/projects/BioScape/tanager_competition/emit_comparison/"
    "EMIT_L2A_RFL_001_20260302T092128_2606106_004.nc"
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


def get_emit_fwhm():
    ds = nc.Dataset(EMIT_NC)
    sbp = ds.groups["sensor_band_parameters"]
    wl = np.array(sbp.variables["wavelengths"][:], dtype=float)
    fwhm = np.array(sbp.variables["fwhm"][:], dtype=float)
    ds.close()
    return wl, fwhm


def main():
    tan_wl, tan_fwhm = get_tanager_fwhm()
    av_wl, av_fwhm = get_aviris_fwhm()
    emit_wl, emit_fwhm = get_emit_fwhm()

    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.plot(tan_wl, tan_fwhm, label="Tanager (this scene)", color="#d55e00", linewidth=2)
    ax.plot(av_wl, av_fwhm, label="AVIRIS-NG (BioSCape flightline)", color="#0072b2", linewidth=2)
    ax.plot(emit_wl, emit_fwhm, label="EMIT (this scene)", color="#009e73", linewidth=2)
    ax.fill_between(tan_wl, tan_fwhm, np.interp(tan_wl, av_wl, av_fwhm),
                     where=(tan_fwhm > np.interp(tan_wl, av_wl, av_fwhm)),
                     color="#d55e00", alpha=0.15, label="Tanager wider than AVIRIS-NG (can't sharpen)")
    ax.set_xlabel("Wavelength (nm)", fontsize=18)
    ax.set_ylabel("FWHM (nm)", fontsize=18)
    ax.set_title(
        "Spectral response width by wavelength: Tanager vs. AVIRIS-NG vs. EMIT\n"
        "(real per-band values, not nominal spec-sheet FWHM)",
        fontsize=17,
    )
    ax.tick_params(axis="both", labelsize=15)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=15)
    ax.set_xlim(376, 2500)
    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT_PATH}")

    print(f"\nTanager FWHM range: {tan_fwhm.min():.2f}-{tan_fwhm.max():.2f} nm")
    print(f"AVIRIS-NG FWHM range: {av_fwhm.min():.2f}-{av_fwhm.max():.2f} nm")
    print(f"EMIT FWHM range: {emit_fwhm.min():.2f}-{emit_fwhm.max():.2f} nm")
    tan_wider_frac = (tan_fwhm > np.interp(tan_wl, av_wl, av_fwhm)).mean()
    print(f"Fraction of Tanager bands wider than AVIRIS-NG at that wavelength: {tan_wider_frac*100:.0f}%")


if __name__ == "__main__":
    main()
