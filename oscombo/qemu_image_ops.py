"""Small qemu-img helpers isolated from the OSWorld provider dependency."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def inspect_base_image(qemu_img: str, base: Path, env: dict[str, str]) -> dict[str, Any]:
    """Read immutable base metadata even while a QEMU Guest uses the base.

    qemu-img's default write-lock probe conflicts with a live QEMU process
    holding the same read-only base. -U inspects without taking image locks;
    the pinned base is read-only, and each Guest writes only to its own overlay.
    """
    info = subprocess.run([qemu_img, "info", "-U", "--output=json", str(base)],
                          capture_output=True, text=True, timeout=120, env=env)
    if info.returncode:
        raise RuntimeError(f"qemu-img cannot read Guest base image: {info.stderr[-1000:]}")
    try:
        image_info = json.loads(info.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("qemu-img returned invalid Guest image metadata") from exc
    if image_info.get("format") != "qcow2":
        raise RuntimeError(f"expected a qcow2 Guest base image, got {image_info.get('format')!r}")
    return image_info


def create_guest_overlay(qemu_img: str, base: Path, overlay: Path,
                         virtual_size: int, env: dict[str, str]) -> None:
    """Create an overlay without reopening the base; -u requires explicit size."""
    if not isinstance(virtual_size, int) or virtual_size <= 0:
        raise ValueError("Guest base image must provide a positive virtual-size")
    created = subprocess.run([qemu_img, "create", "-u", "-q", "-f", "qcow2",
                              "-F", "qcow2", "-b", str(base), str(overlay),
                              str(virtual_size)],
                             capture_output=True, text=True, timeout=120, env=env)
    if created.returncode:
        raise RuntimeError(f"could not create run-owned qcow2 overlay: {created.stderr[-1000:]}")


def readonly_backed_disk_args(base: Path, overlay: Path) -> list[str]:
    """Build a QEMU block graph with a private writable overlay and shared read-only base.

    QEMU 6.2's legacy drive path still takes a conflicting image lock on a
    shared qcow2 backing file, even when locking=off is specified as a
    drive option. An explicit blockdev graph lets the shared base file node
    disable locking while keeping both its file and qcow2 nodes read-only.
    """
    base_path, overlay_path = str(base), str(overlay)
    nodes = (
        {"driver": "file", "filename": overlay_path, "node-name": "guest-overlay-file"},
        {"driver": "file", "filename": base_path, "node-name": "shared-base-file",
         "locking": "off", "read-only": True},
        {"driver": "qcow2", "file": "shared-base-file", "node-name": "shared-base-format",
         "read-only": True},
        {"driver": "qcow2", "file": "guest-overlay-file", "node-name": "guest-disk",
         "backing": "shared-base-format"},
    )
    args: list[str] = []
    for node in nodes:
        args.extend(["-blockdev", json.dumps(node, separators=(",", ":"))])
    args.extend(["-device", "ide-hd,drive=guest-disk,bus=ide.0,unit=0"])
    return args
