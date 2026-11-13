"""Create one deliberately incorrect genuine .blend for oracle validation.

This is validation tooling only. It is never exposed to Actors or used by a
benchmark episode.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def _args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--kind", choices=("dimensions", "collision", "material",
                                             "camera", "light", "protected"), required=True)
    return parser.parse_args(raw)


def main() -> None:
    args = _args()
    source_input = Path(args.source).expanduser()
    output_input = Path(args.output).expanduser()
    if source_input.is_symlink():
        raise PermissionError(f"refusing symlinked source .blend: {source_input}")
    if output_input.exists() or output_input.is_symlink():
        raise FileExistsError(f"preserving existing negative control: {output_input}")
    source = source_input.resolve()
    output = output_input.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"missing or symlinked source .blend: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))

    if args.kind == "dimensions":
        bpy.data.objects["Lamp_Shade"].scale.x *= 0.9
    elif args.kind == "collision":
        shade = bpy.data.objects["Lamp_Shade"]
        z_values = [float(vertex.co.z) for vertex in shade.data.vertices]
        z_min, z_max = min(z_values), max(z_values)
        for vertex in shade.data.vertices:
            radius = (vertex.co.x ** 2 + vertex.co.y ** 2) ** 0.5
            if ((abs(vertex.co.z - z_min) < 1e-5 and abs(radius - 0.56) < 1e-4)
                    or (abs(vertex.co.z - z_max) < 1e-5 and abs(radius - 0.70) < 1e-4)):
                factor = 0.08 / radius
                vertex.co.x *= factor
                vertex.co.y *= factor
        shade.data.update()
    elif args.kind == "material":
        bpy.data.objects["Lamp_Shade"].data.materials[0] = bpy.data.materials["Mat_Porcelain"]
    elif args.kind == "camera":
        bpy.data.objects["Camera_Main"].data.lens = 35.0
    elif args.kind == "light":
        bpy.data.objects["Key_Light"].data.energy = 500.0
    elif args.kind == "protected":
        bpy.data.objects["Lamp_Base"].location.z += 0.05

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    print(f"CREATED_REAL_BLEND_NEGATIVE kind={args.kind} path={output} bytes={output.stat().st_size}")


if __name__ == "__main__":
    main()
