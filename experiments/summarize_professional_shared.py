"""Rebuild shared-desktop evidence reports without running models or applications."""
import argparse
import json
from pathlib import Path

from experiments.professional_shared import render_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads((args.root / "manifest.json").read_text())
    results = json.loads((args.root / "summary.json").read_text())
    integrity, metrics = render_report(args.root, manifest, results, args.dataset)
    print(json.dumps({"integrity_passed": integrity["integrity_passed"],
        "integrity_errors": integrity["integrity_errors"], "concurrency": metrics}, ensure_ascii=False))
    return int(not integrity["integrity_passed"])


if __name__ == "__main__":
    raise SystemExit(main())
