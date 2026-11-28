"""Scan an archive tree for key/token/private-key/proxy indicators without printing values."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCANNER_VERSION = "sensitive-scan/v1"
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("api_token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("cloud_access_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*")),
    ("credential_url", re.compile(r"\b(?:https?|socks5)://[^\s/:@]+:[^\s/@]+@[^\s]+", re.I)),
)
_PROXY_ASSIGNMENT = re.compile(r"(?i)\b(?:HTTP|HTTPS|ALL)_PROXY\s*[:=]\s*\S+")
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def _files(paths: Iterable[str | Path]) -> list[Path]:
    found: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.add(path)
        elif path.is_dir():
            for item in path.rglob("*"):
                if not item.is_file() or any(part in _SKIP_DIRS for part in item.parts):
                    continue
                found.add(item)
    return sorted(found)


def scan_paths(paths: Iterable[str | Path], *, max_file_bytes: int = 16 * 1024 * 1024) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    scanned = 0
    for path in _files(paths):
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            raw = path.read_bytes()
            if b"\x00" in raw[:4096]:
                continue
            text = raw.decode("utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        for line_no, line in enumerate(text.splitlines(), 1):
            categories = {name for name, pattern in _RULES if pattern.search(line)}
            if _PROXY_ASSIGNMENT.search(line):
                categories.add("proxy_address")
            for category in sorted(categories):
                findings.append({"path": str(path), "line": line_no, "category": category})
    counts = Counter(item["category"] for item in findings)
    return {
        "scanner_version": SCANNER_VERSION,
        "files_scanned": scanned,
        "finding_count": len(findings),
        "counts_by_category": dict(sorted(counts.items())),
        "findings": findings,
        "values_printed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--summary-out", type=Path)
    args = parser.parse_args()
    summary = scan_paths(args.paths)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if summary["finding_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
