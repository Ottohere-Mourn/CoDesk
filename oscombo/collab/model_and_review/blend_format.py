"""Lightweight .blend container signature checks.

Blender can save projects either as plain files (``BLENDER`` header) or as a
Zstandard-compressed .blend container (Zstandard frame magic). A compressed
container is only a candidate here; the real-file oracle must open it in
Blender and extract a valid scene before it is accepted as usable evidence.
"""
from __future__ import annotations

from pathlib import Path

BLENDER_MAGIC = b"BLENDER"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def has_blend_container_header(data: bytes) -> bool:
    return data.startswith(BLENDER_MAGIC) or data.startswith(ZSTD_MAGIC)


def has_blend_container_header_at(path: str | Path) -> bool:
    with Path(path).open("rb") as stream:
        return has_blend_container_header(stream.read(16))
