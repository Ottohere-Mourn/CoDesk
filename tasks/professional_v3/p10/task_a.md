# Riverton exposure-analysis release

Prepare the exposure-analysis portion of the supplied synthetic municipal review.
Work in the existing live `RivertonReview.qgz` and shared `review.gpkg`.
GUI controls, CLI, Python and application APIs are all allowed. Preserve every
unowned layer, table, layout and source file. Only `exposure_*` derived tables,
the `Exposure_Review` group/layout and your `exports/exposure/` files are yours.
You may use short project/database locks or retry conflicting writes; do not
replace the current shared project with a stale or unmerged private copy.

## Analysis

- Reconcile parcel geometry and stable IDs with the supplied population records.
  Select the latest quality-approved observation no later than the published
  review cutoff. Report missing, invalid and superseded observations separately;
  do not turn missing population into zero or double-count repaired multipart parcels.
- Follow `analysis_policy.json`: working CRS EPSG:32630, a 10 m analysis grid,
  declared interpolation, per-source elevation units and the common vertical datum.
  Convert feet/metres before combining the two DEM sources. Preserve NoData and
  the supplied overlap-priority rule; do not invent elevations outside coverage.
- Calculate nonnegative depth from supplied water-surface levels and elevation.
  Use parcel/cell intersection areas for valid coverage, mean depth and area
  deeper than 0.25 m. Estimate affected population using that area fraction of
  valid parcel area, retaining the prescribed rounding only at final export.
- Classify as Unknown when valid coverage is below 80% or no eligible population
  exists. Otherwise High means mean depth at least 1.0 m or affected population
  at least 100; Medium means mean depth at least 0.25 m or affected population
  at least 20; all remaining parcels are Low. Include explicit Unknown reasons.
- Keep a reproducible quality summary with input versions, exclusions, coverage,
  class totals and independent checks that parcel counts and areas reconcile.

## Native review and release

Add your derived layers to the existing project using portable relative sources.
Create an editable A4 `Exposure_Review` layout with readable classes, an explicit
Unknown treatment, scale, units, source dates and a quality inset. Preserve the
other groups and layouts when saving. Publish the derived layers to
`exports/exposure/exposure_release.gpkg`, the summary to `exposure_summary.csv`
and the layout to `exposure_review.pdf` in that same directory.

During review, show the largest affected-population parcel and a coverage-limited
parcel in the real QGIS attribute table and linked map selection. Inspect the
actual current layout, including its quality inset, after saving. Request normal
desktop observations for this review; screenshots must show the real application,
not a reconstructed table or composite. Selection/focus are temporary review
states, not a demand that your window remain active after you finish.

Reopen your release and check that its data, native layer sources and PDF agree.
Do not treat a self-written validation report as a substitute for correct native
data. This exercise is synthetic and is not an operational flood forecast.
