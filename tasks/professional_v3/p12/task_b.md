# Pickup module: parametric assembly and drawing release

Finish PickupBody in the existing live `ClampRelease.FCStd` using the supplied
pickup drawing, component schedule and parameter brief. GUI, CLI, Python and
FreeCAD APIs are allowed. You own PickupBody, `Pickup_*` spreadsheet aliases,
PickupPage and `exports/pickup/`. Preserve BaseBody, unowned aliases and pages,
purchased components and immutable assembly datums. Safe locks and retries are
allowed; do not save a stale whole-document snapshot over current shared work.

Build the specified native parametric features and fully constrained sketches.
Use the intended expression relationships instead of a nominal-only imported
solid. Preserve independent control of the declared pickup dimensions. Across
the supplied admissible ranges, recompute to valid geometry with the specified
clearances and datum attachment; then restore nominal values.

Your interface is fixed by the input datums and envelope. No formula may depend
on a mutable parameter owned by the base-design role. Do not adjust another
Body to conceal an incorrect pickup interface.

Create the specified native TechDraw views and geometry-linked dimensions on
PickupPage. Reconcile the BOM's quantities, dimensions and materials with the
actual pickup-module objects and its supplied purchased-component schedule,
not the other role's unfinished base release. Review
occlusion, unit formatting and tolerances in the real drawing window.

Demonstrate a parameter change and recompute in the live application, inspect
the changed geometry and associated drawing, then restore nominal values.
Use normal desktop observations rather than composited UI images or a report
claiming that recompute succeeded. These observations are time-local; the final
active Body, workbench and page are not required to remain yours.

Save the common native document and export `exports/pickup/pickup.step`,
`pickup_drawing.pdf` and `pickup_bom.csv`. Check the reimported STEP and exported
PDF against your committed nominal state. This is a synthetic design-review
exercise, not a real manufacturing certification.
