#!/usr/bin/env python3
"""Patch the OSWorld-V2 docker provider (desktop_env/providers/docker/provider.py) for oscombo. Idempotent.

All changes are opt-in through environment variables; unset, the provider behaves as upstream except for the
longer readiness waits:

  OSCOMBO_RUNTIME_IMAGE     container image that runs QEMU (default: the pinned upstream image). Use
                            the image from infra/qemu-runtime on hosts without /dev/kvm (TCG fallback).
  OSCOMBO_OVERLAY_DIR       host directory for the per-Guest qcow2 overlays (default: inside the container)
  OSCOMBO_GUEST_RAM         Guest RAM (default 8G; upstream 4G)
  OSCOMBO_GUEST_CPUS        Guest vCPUs (default 8; upstream 4). Heavy apps under TCG want 12.
  OSCOMBO_TCG_CPU_MODEL     QEMU CPU model without KVM (default Haswell-noTSX; the default TCG model breaks the
                            Guest's llvmpipe and leaves a black screen)
  OSCOMBO_VM_READY_TIMEOUT  seconds to wait for the Guest server (default 1800; upstream 300 is too short for TCG)
  OSCOMBO_RUN_LABEL         value of the container label ``oscombo.run`` (``python -m oscombo cleanup NAME``)

  python infra/patch_osworld.py "$OSWORLD_DIR"
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "# OSCOMBO_PATCHED"
PINNED = "happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9"

EDITS = [
    ("import time\n", f"import time\nimport uuid  {MARKER}\n"),
    ('        self.environment = {"DISK_SIZE": "32G", "RAM_SIZE": "4G", "CPU_CORES": "4"}  # Modify if needed\n',
     '        self.environment = {"DISK_SIZE": "32G", "RAM_SIZE": os.environ.get("OSCOMBO_GUEST_RAM", "8G"),\n'
     '                            "CPU_CORES": os.environ.get("OSCOMBO_GUEST_CPUS", "8")}  # oscombo\n'),
    ("    def _wait_for_vm_ready(self, timeout: int = 300):\n",
     '    def _wait_for_vm_ready(self, timeout: int = int(os.environ.get("OSCOMBO_VM_READY_TIMEOUT", "1800"))):\n'),
    ("                    timeout=(10, 10)\n",
     "                    timeout=(10, 60)  # oscombo: a slow Guest needs seconds to encode a screenshot\n"),
    ('                    self.environment["KVM"] = "N"\n',
     '                    self.environment["KVM"] = "N"\n'
     '                    self.environment["TCG_CPU_MODEL"] = os.environ.get("OSCOMBO_TCG_CPU_MODEL",\n'
     '                                                                       "Haswell-noTSX")\n'),
    (f'''                self.container = self.client.containers.run(
                    "{PINNED}",
''', f'''                # oscombo: runtime image override, overlay directory, ownership labels
                runtime_image = os.environ.get("OSCOMBO_RUNTIME_IMAGE", "{PINNED}")
                volumes = {{os.path.abspath(path_to_vm): {{"bind": "/System.qcow2", "mode": "ro"}}}}
                overlay_dir = os.environ.get("OSCOMBO_OVERLAY_DIR")
                if overlay_dir:
                    Path(overlay_dir).mkdir(parents=True, exist_ok=True)
                    name = f"osworld-{{uuid.uuid4().hex}}.qcow2"
                    self.environment["OSWORLD_VM_OVERLAY"] = f"/vm-overlay/{{name}}"
                    self._oscombo_overlay = os.path.join(overlay_dir, name)
                    volumes[overlay_dir] = {{"bind": "/vm-overlay", "mode": "rw"}}
                self.container = self.client.containers.run(
                    runtime_image,
'''),
    ('''                    volumes={
                        os.path.abspath(path_to_vm): {
                            "bind": "/System.qcow2",
                            "mode": "ro"
                        }
                    },
''', "                    volumes=volumes,\n"),
    ("                    detach=True\n                )\n",
     '                    detach=True,\n'
     '                    labels={"oscombo": "1", "oscombo.run": os.environ.get("OSCOMBO_RUN_LABEL", "manual")},\n'
     "                )\n"),
    ("                self.container.remove()\n                time.sleep(WAIT_TIME)\n",
     "                self.container.remove()\n"
     "                if getattr(self, \"_oscombo_overlay\", None) and os.path.exists(self._oscombo_overlay):\n"
     "                    os.remove(self._oscombo_overlay)  # oscombo: overlays grow to GBs per run\n"
     "                time.sleep(WAIT_TIME)\n"),
]


def patch(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return False
    for old, new in EDITS:
        if source.count(old) != 1:
            raise RuntimeError(f"{path}: expected exactly one occurrence of:\n{old}")
        source = source.replace(old, new)
    path.write_text(source, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("osworld_dir", type=Path)
    a = ap.parse_args()
    path = a.osworld_dir / "desktop_env/providers/docker/provider.py"
    print(f"{'patched' if patch(path) else 'already patched'}: {path}")


if __name__ == "__main__":
    main()
