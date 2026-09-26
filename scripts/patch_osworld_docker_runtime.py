#!/usr/bin/env python3
"""Add a local-runtime override while preserving OSWorld V2.1's pinned default."""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED = "happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9"
MARKER = "# SWCUB_LOCAL_RUNTIME_OVERRIDE"


def patch(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return False
    needle = f'''                self.container = self.client.containers.run(\n                    "{PINNED}",'''
    replacement = f'''                {MARKER}\n                runtime_image = os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", "{PINNED}")\n                self.container = self.client.containers.run(\n                    runtime_image,'''
    if source.count(needle) != 1:
        raise RuntimeError(f"Expected exactly one pinned provider image call in {path}")
    path.write_text(source.replace(needle, replacement), encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("osworld_v2_dir", type=Path)
    args = parser.parse_args()
    path = args.osworld_v2_dir / "desktop_env/providers/docker/provider.py"
    changed = patch(path)
    print(f"patched={changed} provider={path}")
    print(f"default_runtime_image={PINNED}")


if __name__ == "__main__":
    main()
