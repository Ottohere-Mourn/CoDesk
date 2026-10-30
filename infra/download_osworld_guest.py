#!/usr/bin/env python3
"""Resume, size-check and SHA256-check the pinned OSWorld Ubuntu Guest archive."""
from __future__ import annotations

import argparse
import fcntl
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SIZE = 14_891_811_084
SHA256 = "14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3"
URL = ("https://huggingface.co/datasets/xlangai/v2-image/resolve/"
       "6e16459a2feb5a8f1ed65babcfe7a2a6205d049d/osworld-v2-ubuntu-x86.qcow2.zip")
CHUNK_SIZE = 64 * 1024 * 1024
PRINT_LOCK = __import__("threading").Lock()


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _get_range(start: int, end: int, parts_dir: Path, retries: int, pause: float) -> Path:
    part = parts_dir / f"{start:012d}-{end:012d}.part"
    partial = part.with_suffix(".partial")
    expected = end - start + 1
    if part.exists():
        if part.stat().st_size == expected:
            return part
        raise RuntimeError(f"saved range has wrong length; preserving it: {part}")
    if partial.exists() and partial.stat().st_size > expected:
        quarantine = partial.with_name(partial.name + f".oversize-{time.time_ns()}")
        os.replace(partial, quarantine)
        with PRINT_LOCK:
            print(f"quarantined invalid oversized range {quarantine}; restarting only this range", file=sys.stderr,
                  flush=True)
    failures = 0
    while True:
        have = partial.stat().st_size if partial.exists() else 0
        if have == expected:
            os.replace(partial, part)
            return part
        request_start = start + have
        request = urllib.request.Request(URL, headers={"Range": f"bytes={request_start}-{end}"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                content_range = response.headers.get("Content-Range", "")
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                if response.status != 206 or not match or int(match.group(1)) != request_start \
                        or int(match.group(2)) != end or int(match.group(3)) != SIZE:
                    raise RuntimeError(f"unexpected range response: status={response.status}, "
                                       f"Content-Range={content_range!r}")
                with partial.open("ab", buffering=0) as target:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        target.write(block)
            failures = 0
        except (OSError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            failures += 1
            have = partial.stat().st_size if partial.exists() else 0
            with PRINT_LOCK:
                print(f"range {start}-{end}: interruption {failures}/{retries}: {type(exc).__name__}: {exc}; "
                      f"resume at {start + have}", file=sys.stderr, flush=True)
            if failures >= retries:
                raise
            time.sleep(min(pause * (2 ** min(failures - 1, 3)), 60))
        else:
            have = partial.stat().st_size
            if have > expected:
                raise RuntimeError(f"range has excess bytes; preserving it: {partial}")
            if have == expected:
                os.replace(partial, part)
                with PRINT_LOCK:
                    print(f"downloaded range {start}-{end}", flush=True)
                return part
            # EOF before this range ended; continue at the first missing byte.
            failures += 1
            if failures >= retries:
                raise RuntimeError(f"range {start}-{end} ended early at {start + have}")
            time.sleep(min(pause * (2 ** min(failures - 1, 3)), 60))


def download(path: Path, retries: int, pause: float, workers: int, parts_dir: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current = path.stat().st_size if path.exists() else 0
        if current > SIZE:
            raise RuntimeError(f"partial archive is larger than expected ({current} > {SIZE}); preserving it")
        if current == SIZE:
            actual = digest(path)
            if actual != SHA256:
                raise RuntimeError(f"archive size is complete but SHA256 differs: {actual}; file preserved")
            print(f"verified existing archive: {path} ({SIZE} bytes, SHA256 {actual})", flush=True)
            return

        parts_dir = (parts_dir.expanduser().resolve() if parts_dir else
                     path.parent / (path.name + ".parts"))
        parts_dir.mkdir(parents=True, exist_ok=True)
        parts = [(start, min(start + CHUNK_SIZE, SIZE) - 1)
                 for start in range(current, SIZE, CHUNK_SIZE)]
        print(f"resuming from {current}/{SIZE} bytes with {workers} range workers", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_get_range, start, end, parts_dir, retries, pause) for start, end in parts]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        assembling = path.with_name(path.name + ".assembling")
        with assembling.open("wb") as output, path.open("rb") as source:
            shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
            expected_start = current
            for start, end in parts:
                if start != expected_start:
                    raise RuntimeError(f"range gap in assemble plan at {expected_start}")
                part = parts_dir / f"{start:012d}-{end:012d}.part"
                if not part.is_file() or part.stat().st_size != end - start + 1:
                    raise RuntimeError(f"range missing/short before assemble: {part}")
                with part.open("rb") as source_part:
                    shutil.copyfileobj(source_part, output, length=8 * 1024 * 1024)
                expected_start = end + 1
        if expected_start != SIZE or assembling.stat().st_size != SIZE:
            raise RuntimeError(f"assembled archive length {assembling.stat().st_size}, expected {SIZE}")
        actual = digest(assembling)
        if actual != SHA256:
            raise RuntimeError(f"assembled archive SHA256 mismatch: {actual}; both source and assembly preserved")
        os.replace(assembling, path)
        print(f"verified archive: {path} ({SIZE} bytes, SHA256 {actual})", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--retries", type=int, default=100)
    parser.add_argument("--pause", type=float, default=15)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--parts-dir", type=Path,
                        help="store resumable range chunks here (use local scratch to reduce network-filesystem writes)")
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    download(args.archive.expanduser().resolve(), args.retries, args.pause, args.workers, args.parts_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
