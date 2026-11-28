"""CLI for checking a batch archive before packaging."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:  # package import (tests / python -m)
    from .archive import validate_batch, write_manifest
except ImportError:  # direct script invocation documented in README
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pipeline.archive import validate_batch, write_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--ignore-incomplete-attempts", action="store_true", help="Ignore attempt folders without a report.json completion marker.")
    args = parser.parse_args()
    result = validate_batch(args.root, ignore_incomplete_attempts=args.ignore_incomplete_attempts)
    if result["ok"] and args.write_manifest:
        path = write_manifest(args.root, ignore_incomplete_attempts=args.ignore_incomplete_attempts)
        result["manifest_written"] = str(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
