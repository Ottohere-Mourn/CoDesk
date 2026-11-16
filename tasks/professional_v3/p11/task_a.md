# Enclosure motion and service-clearance review

Complete the motion system in the existing live `EnclosureReview.blend` using
the supplied motion brief, datum drawing and reference pose sequence. GUI,
CLI, Python and `bpy` are allowed. Preserve source meshes, UVs, material slots,
protected assets, camera definitions and all unowned data. You own only the
specified MotionRig constraints, drivers, animation and `exports/motion/`.
Short locks and safe incremental saves are allowed; do not save an old private
scene over newer changes in the shared file.

The enclosure has inherited transforms and an incomplete multi-part mechanism.
Recover the intended pivots from its datums rather than assuming object origins
are correct. Preserve the supplied geometry and scale. Build an editable rig
with named controls, coupled linkage and explicit motion dependencies; do not
replace the mechanism with a static mesh or a sequence of unrelated poses.

Implement the service cycle in `motion_brief.json`: release the latch before
opening, hold the inspection pose, close the lid, then engage the latch. Match
the supplied pose landmarks and timing tolerances. Respect the published motion
envelope and minimum 0.8 mm service clearance for the non-contact surface pairs
listed in the brief; declared mating/contact pairs are exempt. Check every integer and half frame,
not just the supplied reference frames. Avoid discontinuities and unintended
overshoot. The opening-angle control must remain functional across its stated
admissible range without moving the fixed mounting datums.

Inspect the actual running Blender timeline at a release transition, a mid-motion
frame and the hold pose. Show the active rig controls and corresponding viewport
state using normal desktop observations. A separately rendered image does not
demonstrate that the live rig is editable. Current frame, editor and selection
are temporary review state and need not remain yours after the review.

Save the common native project and export `exports/motion/motion_samples.csv`
with sampled transforms and clearance diagnostics plus `motion_review.json`
describing the controls and checks performed. These reports do not replace
native correctness. The combined final animation is rendered after all editing
has stopped; you do not need an unfinished material-review output to finish.
