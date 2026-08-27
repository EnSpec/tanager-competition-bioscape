# step10_mosaic_aviris_aoi.R
#
# Mosaics BioSCape AVIRIS-NG L3 trait tiles (Nov 2023) over the same AOI
# as the Tanager scene, for a same-location, cross-platform comparison
# (airborne AVIRIS-NG vs. spaceborne Tanager) alongside the EMIT
# comparison already in step6/step7.
#
# None of the pre-built regional mosaics in Trait_Maps/Version_1.0/Mosaics
# (cape peninsula, baviaanskloof, west_coast, cederberg, afromontane_forest,
# kogelberg) cover this AOI (checked bounds directly) -- this area
# (Jonkershoek/Franschhoek) was never mosaicked before. Rather than adding
# a new region to the shared bioscape_regions_of_interest.gpkg (a team
# resource used by other projects), this calls mosaic_trait() directly
# with an explicit tile_ids list scoped to this project.
#
# Tile selection: the AVIRIS_coverage/ANG Coverage.geojson polygons (raw
# per-segment coverage) use a DIFFERENT, denser sub-tile numbering than
# what actually got processed into Trait_Maps/Version_1.0/PLSR (that
# geojson's segment numbers for our AOI's flightlines, e.g. "_047" to
# "_051", don't exist as processed PLSR tile folders -- only "_000" to
# "_020" or so were ever processed per flightline). So tile selection
# here was done by reading each ACTUALLY-PROCESSED tile's own GeoTransform
# from its netCDF and checking against the Tanager scene's EPSG:32734
# bounds directly (both already in the same CRS, no reprojection needed)
# -- see the Python snippet in CLAUDE.md "AVIRIS-NG AOI mosaic" for that
# check. Result: 24 processed tiles across 6 flightlines (2023-11-22 and
# 2023-11-25) actually overlap this AOI.

source("/Users/henryfrye/Dropbox/Intellectual_Endeavours/Wisconsin/BioSCapeTownsend/CapeTraits/Workflow11_Trait_Map_Assess/code/mosaic_trait_tiles.R")

tile_ids <- c(
  "ang20231122t115757_000_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t121456_018_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t121456_019_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t121456_020_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t123202_000_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t123202_001_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t123202_002_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t123202_003_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231122t123202_004_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t073454_004_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t082540_008_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t082540_009_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t082540_010_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t084600_004_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t084600_005_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t084600_006_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t084600_007_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t090120_007_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t090120_008_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t090120_009_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t090120_010_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t093445_007_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t093445_008_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1",
  "ang20231125t093445_009_L2A_OE_0b4f48b4_RFL_ORT_corr_topo_brdf_glint_v1"
)

trait_root <- "/Volumes/Enspec/projects/BioScape/Trait_Maps/Version_1.0/PLSR"
mask_root  <- "/Volumes/Enspec/projects/BioScape/Trait_Maps/Version_1.0/Masks"

# Kept in this project's own Enspec folder, NOT the shared Mosaics/ dir --
# this is a one-off AOI-scoped mosaic, not a new named region other
# projects should discover.
out_dir <- "/Volumes/Enspec/projects/BioScape/tanager_competition/aviris_aoi_mosaic"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

traits <- c("Nitrogen", "Lignin", "Calcium", "Cellulose")

message("Tiles: ", length(tile_ids))
message("Traits: ", paste(traits, collapse = ", "))

for (j in seq_along(traits)) {
  mosaic_trait(
    trait      = traits[[j]],
    tile_ids   = tile_ids,
    trait_root = trait_root,
    mask_root  = mask_root,
    out_dir    = out_dir,
    write_mask = (j == 1)
  )
}

message("\nDone. Output in: ", out_dir)
