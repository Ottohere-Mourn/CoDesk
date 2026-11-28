"""Versioned non-destructive minimizer for image/Base64 payloads in Codex JSONL."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REDACTOR_VERSION = "codex-image-minimizer/v2"
_DATA_IMAGE = re.compile(r"data:image/[^;,\s]+;base64,([A-Za-z0-9+/=\r\n]+)", re.I)
_LONG_BASE64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{256,}={0,2}(?![A-Za-z0-9+/=])")
_IMAGE_KEYS = {"image", "image_data", "image_base64", "screenshot", "screenshot_base64", "base64", "data"}


def redact_value(value: Any, *, key: str = "", image_context: bool = False, stats: dict[str, int] | None = None) -> Any:
    stats = stats if stats is not None else {"payloads_redacted": 0, "base64_chars_omitted": 0}
    if isinstance(value, dict):
        image_object = image_context or value.get("type") == "image" or str(value.get("mimeType", "")).startswith("image/")
        return {
            k: redact_value(v, key=str(k), image_context=image_object or str(k).lower() in _IMAGE_KEYS, stats=stats)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_value(v, key=key, image_context=image_context, stats=stats) for v in value]
    if not isinstance(value, str):
        return value

    def placeholder(char_count: int) -> str:
        stats["payloads_redacted"] += 1
        stats["base64_chars_omitted"] += char_count
        return f"<BASE64_OMITTED:{char_count}chars>"

    # Opaque encrypted reasoning is not readable model/tool text. Its
    # URL-safe Base64 may accidentally contain token-shaped substrings.
    if key == "encrypted_content":
        stats["encrypted_payloads_omitted"] = stats.get("encrypted_payloads_omitted", 0) + 1
        return f"<ENCRYPTED_CONTENT_OMITTED:{len(value)}chars>"
    text = value
    text = _DATA_IMAGE.sub(lambda m: placeholder(len(re.sub(r"\s+", "", m.group(1)))), text)
    if image_context:
        compact = re.sub(r"\s+", "", text)
        if len(compact) >= 128 and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", compact):
            return placeholder(len(compact))
    return _LONG_BASE64.sub(lambda m: placeholder(len(m.group(0))), text)


def redact_events_file(source: str | Path, destination: str | Path) -> dict[str, Any]:
    src = Path(source)
    dst = Path(destination)
    stats = {"payloads_redacted": 0, "base64_chars_omitted": 0, "events_processed": 0}
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8") as reader, dst.open("w", encoding="utf-8", newline="\n") as writer:
        for line_number, line in enumerate(reader, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {src}:{line_number}") from exc
            clean = redact_value(row, stats=stats)
            writer.write(json.dumps(clean, ensure_ascii=False, separators=(",", ":")) + "\n")
            stats["events_processed"] += 1
    return {"redactor_version": REDACTOR_VERSION, **stats, "output": str(dst)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, help="Write to a separate sanitized file")
    args = parser.parse_args()
    print(json.dumps(redact_events_file(args.source, args.destination), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
