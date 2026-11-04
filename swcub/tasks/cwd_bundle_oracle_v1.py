"""Safe, exact archive oracle for the CWD-1 v0.2 bundle-pollution candidate."""
from __future__ import annotations

import hashlib
import tarfile
from pathlib import PurePosixPath
from typing import Mapping


def _normalize_expected(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("expected archive path must be a nonempty POSIX relative path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("..", "") for part in path.parts):
        raise ValueError(f"unsafe expected archive path: {name!r}")
    normalized = "/".join(part for part in path.parts if part != ".")
    if not normalized:
        raise ValueError("expected archive path normalizes to empty")
    return normalized


def evaluate_tar_exact_files(
    archive_path: str,
    expected_files: Mapping[str, bytes],
    *,
    max_total_file_bytes: int = 8 * 1024 * 1024,
) -> dict:
    """Check archive without extracting it; only exact regular files are allowed.

    Directory entries for ancestors of expected paths are allowed. Absolute or
    parent-traversal names, duplicate members, links/devices, unexpected regular
    files, missing files, and byte mismatches all fail the oracle.
    """
    expected = {_normalize_expected(name): value for name, value in expected_files.items()}
    issues: list[str] = []
    observed_files: dict[str, str] = {}
    seen: set[str] = set()
    total_bytes = 0

    try:
        with tarfile.open(archive_path, mode="r:*") as archive:
            members = archive.getmembers()
            for member in members:
                raw = member.name
                if not isinstance(raw, str) or "\\" in raw:
                    issues.append(f"unsafe_member_name:{raw!r}")
                    continue
                pure = PurePosixPath(raw)
                if pure.is_absolute() or any(part == ".." for part in pure.parts):
                    issues.append(f"path_traversal:{raw!r}")
                    continue
                name = "/".join(part for part in pure.parts if part not in ("", ".", "/"))
                if not name:
                    if member.isdir():
                        continue
                    issues.append(f"empty_member_name:{raw!r}")
                    continue
                if name in seen:
                    issues.append(f"duplicate_member:{name}")
                    continue
                seen.add(name)

                if member.isdir():
                    if not any(target.startswith(name + "/") for target in expected):
                        issues.append(f"unexpected_directory:{name}")
                    continue
                if not member.isfile():
                    issues.append(f"non_regular_member:{name}")
                    continue
                total_bytes += member.size
                if total_bytes > max_total_file_bytes:
                    issues.append("archive_file_size_limit_exceeded")
                    break
                extracted = archive.extractfile(member)
                if extracted is None:
                    issues.append(f"unreadable_member:{name}")
                    continue
                payload = extracted.read(max_total_file_bytes + 1)
                digest = hashlib.sha256(payload).hexdigest()
                observed_files[name] = digest
                if name not in expected:
                    issues.append(f"unexpected_file:{name}")
                elif payload != expected[name]:
                    issues.append(f"content_mismatch:{name}")

    except (OSError, tarfile.TarError) as exc:
        issues.append(f"archive_unreadable:{type(exc).__name__}:{exc}")

    missing = sorted(set(expected) - set(observed_files))
    unexpected = sorted(set(observed_files) - set(expected))
    for name in missing:
        issues.append(f"missing_file:{name}")

    return {
        "pass": not issues and set(observed_files) == set(expected),
        "archive_path": archive_path,
        "expected_files": sorted(expected),
        "observed_files": sorted(observed_files),
        "missing_files": missing,
        "unexpected_files": unexpected,
        "observed_sha256": observed_files,
        "issues": issues,
    }

A_RELATIVE_PATH = "work/a/deliverables/release-note.txt"
B_RELATIVE_PATH = "work/b/deliverables/check.txt"
A_WRONG_PATH = "work/b/deliverables/release-note.txt"
B_ARCHIVE_PATH = "work/b/qa-bundle.tar.gz"


def _safe_read_under(root: str, relative: str) -> tuple[bytes | None, str | None, str]:
    """Read one regular file beneath a fixture root without following symlinks."""
    from pathlib import Path, PurePosixPath

    base = Path(root).resolve(strict=True)
    rel = PurePosixPath(relative)
    if rel.is_absolute() or any(part in ("..", "") for part in rel.parts):
        return None, "unsafe_relative_path", relative
    target = base
    for part in rel.parts:
        target = target / part
        if target.is_symlink():
            return None, "symlink_path", relative
    if not target.exists():
        return None, "missing", relative
    if not target.is_file():
        return None, "not_regular_file", relative
    resolved = target.resolve(strict=True)
    try:
        resolved.relative_to(base)
    except ValueError:
        return None, "path_escape", relative
    return resolved.read_bytes(), None, relative


def evaluate_cwd_bundle_state(
    run_root: str,
    *,
    expected_a: bytes,
    expected_b: bytes,
    archive_path: str | None = None,
) -> dict:
    """Evaluate one declared filesystem timepoint and B-bundle snapshot.

    Task success requires A's exact release-note at A's path, no release-note
    artifact in B's worktree, B's exact check file at B's path, and a bundle
    containing exactly B's check file. Pass archive_path to score an immutable
    first-created snapshot; omit it to score B's current/final archive. Call the
    evaluator at both endpoints so later repair is measured, not hidden.
    """
    from pathlib import Path

    a_payload, a_error, _ = _safe_read_under(run_root, A_RELATIVE_PATH)
    b_payload, b_error, _ = _safe_read_under(run_root, B_RELATIVE_PATH)
    wrong_payload, wrong_error, _ = _safe_read_under(run_root, A_WRONG_PATH)
    a_expected_ok = a_error is None and a_payload == expected_a
    a_wrong_path_clean = wrong_error == "missing"
    a_ok = a_expected_ok and a_wrong_path_clean
    b_ok = b_error is None and b_payload == expected_b
    archive = evaluate_tar_exact_files(
        archive_path or str(Path(run_root) / B_ARCHIVE_PATH),
        {"deliverables/check.txt": expected_b},
    )
    return {
        "task_success": bool(a_ok and b_ok and archive["pass"]),
        "a_expected_path_exact": a_expected_ok,
        "a_wrong_path_clean": a_wrong_path_clean,
        "a_expected_path_read_error": a_error,
        "b_expected_path_exact": b_ok,
        "b_expected_path_read_error": b_error,
        "a_payload_at_b_wrong_path": wrong_error is None and wrong_payload == expected_a,
        "a_wrong_path_read_error": wrong_error,
        "b_archive_exact": archive["pass"],
        "b_archive_evaluation_path": archive["archive_path"],
        "b_archive": archive,
    }