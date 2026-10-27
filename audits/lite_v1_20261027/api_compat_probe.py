"""Minimal provider image + forced tool-call probe; writes only sanitized metadata.

The provider key is read from a private local file. Never pass this script's
credential to an Actor or log response bodies, headers or request payloads.
"""
from __future__ import annotations
import argparse
import base64
import io
import json
from pathlib import Path
import time
import requests
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="https://api.haogpt.net/v1")
    parser.add_argument("--model", default="gpt-6-astra")
    args = parser.parse_args()
    key = args.key_file.read_text().strip()
    with Image.open(args.screenshot) as original:
        sample = original.convert("RGB")
        sample.thumbnail((640, 360))
        buffer = io.BytesIO()
        sample.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    payload = {
        "model": args.model,
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": "Call report_visible with a short description of the visible desktop."},
            {"type": "input_image", "image_url": "data:image/png;base64," + encoded},
        ]}],
        "tools": [{"type": "function", "name": "report_visible", "description": "Describe visible desktop",
                   "parameters": {"type": "object", "properties": {"description": {"type": "string"}},
                                  "required": ["description"], "additionalProperties": False}}],
        "tool_choice": {"type": "function", "name": "report_visible"},
        "max_output_tokens": 150,
    }
    started = time.monotonic()
    try:
        response = requests.post(args.base_url.rstrip("/") + "/responses", json=payload,
                                 headers={"Authorization": "Bearer " + key}, timeout=150)
        result = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        output = result.get("output", []) if isinstance(result, dict) else []
        safe = {"http_status": response.status_code, "elapsed_s": round(time.monotonic() - started, 3),
                "model": args.model, "output_types": [x.get("type") for x in output if isinstance(x, dict)],
                "tool_names": [x.get("name") for x in output if isinstance(x, dict) and x.get("type") == "function_call"],
                "usage": result.get("usage") if isinstance(result, dict) else None,
                "error_type": (result.get("error") or {}).get("type") if isinstance(result, dict) and isinstance(result.get("error"), dict) else None,
                "request_id_present": bool(response.headers.get("x-request-id")),
                "image_bytes": len(buffer.getvalue())}
    except requests.RequestException as exc:
        safe = {"http_status": None, "elapsed_s": round(time.monotonic() - started, 3),
                "model": args.model, "error_type": type(exc).__name__}
    args.output.write_text(json.dumps(safe, indent=2) + "\n")
    print(json.dumps(safe, sort_keys=True))


if __name__ == "__main__":
    main()
