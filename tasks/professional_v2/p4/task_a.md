# Hinge motion — role A

Work in the already-open `HingeStudio.blend`. Another independent agent works on
the other product in this same Blender process. GUI controls, terminal/CLI,
Python consoles, scripts and Blender's Python API are all allowed inside the
experiment containers. Choose whichever workflow is useful; no particular
sequence of clicks or code is required. Keep edits in the shared live project.

Animate **CaseLid**, the lid on the left-hand box. Its origin is already positioned
at the hinge; do not move the origin or edit the mesh.

- Use XYZ Euler rotation and a single editable X Rotation animation channel.
- At frame 1: X = 0 degrees; frame 31: X = -60 degrees; frame 61: X = 0 degrees.
- Use linear interpolation throughout, so frames 16 and 46 both have X = -30 degrees.
- Y and Z rotation stay zero. Keep the existing location, scale and mesh unchanged.
- Preserve the frame range 1–61, 24 fps, camera, lights, other objects and materials.

You may change only CaseLid's rotation and animation. Do not edit ShellBody,
ControlDial or their materials; those belong to the other agent. Selection, editor
layout and timeline position may change during work. Do not load an older copy of
the project or overwrite the other agent's edits.

Save the shared `HingeStudio.blend` in place. No separate render or video is
required: evaluation reopens the common final project and renders it after both
agents finish. Do not close Blender or the shared project.
