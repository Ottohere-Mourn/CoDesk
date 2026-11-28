"""Safe host-side temporary roots for Shared BC runs.

Run outputs and Guest storage belong on RAID.  Codex HOME/config and transient
files must not use a filesystem where POSIX mode bits are ignored (the current
RAID export is mapped as world-writable).  These helpers fail closed if a
private host directory cannot be established.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


def ensure_private_directory(path: str | Path) -> Path:
    """Create a private directory and verify ownership/mode on POSIX hosts."""
    result = Path(path).expanduser().absolute()
    if result.exists() and result.is_symlink():
        raise ValueError(f"Refusing symlink for private runtime directory: {result}")
    result.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(result, 0o700)
        info = result.stat()
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise PermissionError(f"Private runtime directory is not owned by this user: {result}")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise PermissionError(f"Private runtime directory is accessible by group/other: {result}")
    return result


def require_not_under_tmp(path: str | Path) -> Path:
    """Reject accidental use of the exhausted 8-GiB /tmp mount."""
    candidate = Path(path).expanduser().absolute()
    if os.name == "posix":
        try:
            candidate.relative_to(Path("/tmp"))
        except ValueError:
            return candidate
        raise ValueError("BC TMPDIR must not use /tmp; select secure /dev/shm or a verified private volume")
    return candidate


def free_bytes(path: str | Path) -> int:
    return shutil.disk_usage(path).free


def remove_private_run_tree(path: str | Path, allowed_root: str | Path) -> None:
    """Remove one completed run-owned private tree, never a parent/root path."""
    target = Path(path).resolve(strict=True)
    root = Path(allowed_root).resolve(strict=True)
    if target == root or not target.is_relative_to(root):
        raise ValueError("Refusing to remove a temp root or path outside its configured parent")
    if os.name == "posix":
        info = target.stat()
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise PermissionError("Refusing to remove another user's private runtime tree")
    shutil.rmtree(target)
