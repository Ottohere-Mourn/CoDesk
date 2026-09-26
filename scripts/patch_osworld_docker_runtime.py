#!/usr/bin/env python3
"""Add a pinned-runtime override and RAID1-backed QEMU overlays to local OSWorld V2.1."""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED = "happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9"
RUNTIME_MARKER = "# SWCUB_LOCAL_RUNTIME_OVERRIDE"
OVERLAY_MARKER = "# SWCUB_RAID1_OVERLAY_MOUNT"


def patch(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    original = source
    if RUNTIME_MARKER not in source:
        old = f'''                self.container = self.client.containers.run(
                    "{PINNED}",'''
        new = f'''                {RUNTIME_MARKER}
                runtime_image = os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", "{PINNED}")
                self.container = self.client.containers.run(
                    runtime_image,'''
        if source.count(old) != 1:
            raise RuntimeError(f"Expected exactly one pinned provider image call in {path}")
        source = source.replace(old, new)

    if OVERLAY_MARKER not in source:
        runtime_line = f'''                runtime_image = os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", "{PINNED}")'''
        overlay_setup = '''
                # SWCUB_RAID1_OVERLAY_MOUNT
                overlay_host_dir = os.environ.get("SWCUB_OSWORLD_OVERLAY_HOST_DIR")
                volume_mounts = {
                    os.path.abspath(path_to_vm): {"bind": "/System.qcow2", "mode": "ro"}
                }
                if overlay_host_dir:
                    Path(overlay_host_dir).mkdir(parents=True, exist_ok=True)
                    self.environment["SWCUB_VM_OVERLAY"] = f"/vm-overlay/osworld-{uuid.uuid4().hex}.qcow2"
                    volume_mounts[overlay_host_dir] = {"bind": "/vm-overlay", "mode": "rw"}'''
        if source.count(runtime_line) != 1:
            raise RuntimeError(f"Expected exactly one runtime image assignment in {path}")
        source = source.replace(runtime_line, runtime_line + overlay_setup)
        old_volumes = '''                    volumes={
                        os.path.abspath(path_to_vm): {
                            "bind": "/System.qcow2",
                            "mode": "ro"
                        }
                    },'''
        if source.count(old_volumes) != 1:
            raise RuntimeError(f"Expected exactly one provider volume mapping in {path}")
        source = source.replace(old_volumes, "                    volumes=volume_mounts,")

    if "import uuid\n" not in source:
        source = source.replace("import time\n", "import time\nimport uuid\n")
    if source != original:
        path.write_text(source, encoding="utf-8")
    return source != original


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
