# Studio Lamp: geometry review and product presentation

Complete the supplied real Blender scene as a compact product presentation. All dimensions are in meters. The scene contains a lamp base, stem, shade, bulb, floor, camera and three area lights. The scene catalog and this brief are available to every actor; no specification is hidden.

## Geometry target

Adjust `Lamp_Shade` to outside dimensions **1.50 × 1.50 × 0.80 m**, centered at **(0, 0, 2.50 m)**. Keep its existing open frustum shape and `Mat_Deep_Green` material. The bulb must remain inside the shade with at least **0.40 m radial clearance** from the inner shade wall at the bulb center, and at least **0.10 m vertical clearance** from the shade opening/rim. Preserve the base, stem, bulb and floor exactly.

## Presentation target

Use `Camera_Main` at **(4.20, -6.00, 3.20)**, aimed at the lamp center **(0, 0, 1.45)**, with **50 mm** focal length. Use area lights with these values:

| Object | Location (m) | Power | Size |
| --- | --- | ---: | ---: |
| `Key_Light` | (3, -4, 5) | 450 W | 4 m |
| `Fill_Light` | (-3, -1, 3) | 160 W | 3 m |
| `Rim_Light` | (0, 3, 4) | 320 W | 2 m |

Keep the supplied light colors and all lamp geometry/materials unchanged. Save the finished, reopenable Blender project as `deliverables/StudioLamp_Final.blend`.

## Work roles

A owns the shade geometry; B owns the camera and light setup and independently reviews the geometry. Both can inspect all specifications and scene objects. Their role split is an editing responsibility, not an information restriction. They may exchange findings or corrections when useful. No simultaneous editing, fixed message count, or forced conflict is required.
