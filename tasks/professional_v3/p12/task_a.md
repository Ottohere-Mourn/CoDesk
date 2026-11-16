# Clamp base: parametric design and drawing release

Finish BaseBody in the existing live `ClampRelease.FCStd` from the supplied
dimensioned base drawing and design-change brief. GUI, CLI, Python and FreeCAD
APIs are allowed. You own BaseBody, the reserved `Base_*` spreadsheet aliases,
BasePage and `exports/base/`. Preserve other Bodies, parameter aliases, pages,
purchased components and the immutable mounting-interface datums. Short locks
and safe retries are allowed; never overwrite newer shared document state with
an older private copy.

Interpret the linked dimensions, tolerances, symmetry and datum references.
Keep a native editable feature history with valid solids and fully constrained
sketches representing the intended relationships. A fixed imported shape or
locking every coordinate independently is not a substitute for the specified
parameter dependencies. Avoid changing the source drawing or the global units.

The supplied admissible parameter ranges are part of the requirement. Vary each
named base control, recompute, and verify that relevant dependent dimensions,
holes, clearances and attachment references remain correct. Restore the nominal
release values. A model that works only at its original dimensions is incomplete.
The pickup interface is defined entirely by the immutable supplied datums, not
by another role's unfinished geometry or parameters.

Create the required native TechDraw projection, section and detail views on
BasePage, with geometry-linked dimensions and the stated tolerances. Inspect
readability and associations in the real application. Plain text that merely
resembles a dimension is not equivalent to a dimension linked to the model.

During review, change one public control in the live parameter interface,
recompute, and inspect the affected solid and drawing before restoring nominal
values. Capture normal desktop observations of these actual states. The page,
Body and workbench need not remain active after this time-local review.

Save the shared native document. Export `exports/base/base.step`,
`base_drawing.pdf` and `base_parameter_check.csv`. Reimport the STEP for a
geometry comparison and ensure the PDF matches the current saved page. These
are synthetic review artifacts, not certified manufacturing instructions.
