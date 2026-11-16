# Enclosure finish, labels and optical review

Complete the specified FinishTargets in the existing live
`EnclosureReview.blend`, using the supplied calibrated finish references,
label atlas and view brief. GUI, CLI, Python and `bpy` are allowed. You own
FinishTargets' UVs, material assignments, owned shader graphs and
`exports/finish/`; preserve geometry, transforms, rig/animation, fixed cameras
and protected reference assets. Locks and safe incremental saves are allowed.
Do not overwrite current scene data with an older private snapshot.

Match the finish families and label placements from the visual brief, including
color-space conversion, roughness/metallic response and specified transparency.
Keep connected editable shader graphs. Some materials are initially linked to
protected objects: isolate edits where necessary instead of recoloring every
user of a shared datablock.

Produce usable UVs on the designated unchanged meshes. Meet the provided texel
density and bleed margins; avoid forbidden positive-area overlaps and mirrored
lettering. Account for inherited transforms and surface orientation. Labels
must remain upright and legible in all designated review views, not merely one
front-facing screenshot. Keep images packed or correctly relative and do not
use unrelated absolute-path textures.

Review the actual shader connections, UV placement and viewport appearance in
the running Blender instance using normal desktop observations. Do not use a
fabricated UI image as evidence. You may choose any effective tool workflow;
there is no minimum number of clicks or required editor-switch sequence.

Save the shared native file and provide
`exports/finish/finish_contact_sheet.png` and `finish_review.json`. The contact
sheet is a finish review using the provided review arrangement; it need not
contain another unfinished motion edit. Final appearance over the completed
motion is independently checked after all editing stops. Do not alter the rig,
mesh topology or camera definitions merely to make one view look correct.
