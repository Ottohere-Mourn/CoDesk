# Instrument finish — role B

Work in the already-open `HingeStudio.blend`. Another independent agent works on
the box lid in this same Blender process. GUI controls, terminal/CLI, Python
consoles, scripts and Blender's Python API are all allowed inside the experiment
containers. Choose whichever workflow is useful; no particular sequence of
clicks or code is required. Keep edits in the shared live project.

Finish the right-hand instrument using its existing, connected Principled BSDF
materials. Base Colors below use **sRGB RGBA hex**. You can enter them in the
color picker's sRGB Hex field or convert sRGB channels to linear values when
setting shader inputs programmatically:

| Object / material | Base Color (RGBA hex) | Roughness | Metallic |
| --- | --- | ---: | ---: |
| ShellBody / ShellFinish | `185B7AFF` | 0.32 | 0.15 |
| ControlDial / DialFinish | `E6B74AFF` | 0.22 | 0.80 |

Change only these three shader inputs for each of the two existing materials.
Keep their existing material slots, shader connections and other shader values.
Do not edit mesh geometry, transforms, lights, camera, world, render settings,
frame range or the box materials.

CaseLid's animation belongs to the other agent: do not modify it or reset the
project. Selection, editor layout and timeline position may change during work.

Save the shared `HingeStudio.blend` in place without replacing the other agent's
edits. No separate render is required: evaluation reopens the common final project
and renders it after both agents finish. Do not close Blender or the project.
