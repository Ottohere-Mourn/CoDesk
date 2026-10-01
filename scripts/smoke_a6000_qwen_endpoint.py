#!/usr/bin/env python3
"""Send one archived real OSWorld screenshot request to a live Qwen worker."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from urllib.request import Request, urlopen

DEFAULT_MESSAGES = Path(
    "/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/"
    "a6000-qwen-writer-calc-solo-20260930-r04-stage-timing/"
    "model-actors/writer_actor/draft/message_cache/messages_step_0.json"
)
EXPECTED_MODEL = "Qwen3-VL-30B-A3B-Instruct"
EXPECTED_CONFIG = "6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=os.environ.get(
        "SWCUB_QWEN_INFERENCE_URL", "http://127.0.0.1:15485"))
    parser.add_argument("--messages", type=Path, default=DEFAULT_MESSAGES)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    request_id = uuid.uuid4().hex[:16]
    result: dict[str, object] = {
        "request_id": request_id, "endpoint": args.endpoint,
        "messages_file": str(args.messages), "max_new_tokens": args.max_new_tokens,
        "status": "starting", "action_executed": False,
    }
    started = time.monotonic()
    try:
        with urlopen(args.endpoint.rstrip("/") + "/health", timeout=5) as response:
            health = json.loads(response.read())
        if (health.get("ready") is not True or health.get("model") != EXPECTED_MODEL
                or health.get("config_sha256") != EXPECTED_CONFIG
                or health.get("dtype") != "bfloat16" or health.get("quantization") is not None
                or health.get("cuda_device_ids") != [0, 1]
                or health.get("non_gpu_devices") or health.get("attention_backend") != "eager") :
            raise RuntimeError(f"worker health does not match pinned baseline: {health}")
        messages = json.loads(args.messages.read_text())
        image_bytes = []
        dimensions = []
        from PIL import Image
        from io import BytesIO
        for message in messages:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if item.get("type") != "image_url":
                    continue
                data_url = item["image_url"]["url"]
                raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
                image_bytes.append(raw)
                with Image.open(BytesIO(raw)) as image:
                    dimensions.append(list(image.size))
        if len(image_bytes) != 1:
            raise ValueError(f"expected exactly one archived screenshot, got {len(image_bytes)}")
        body = json.dumps({"messages": messages,
                           "max_new_tokens": args.max_new_tokens}).encode()
        request = Request(args.endpoint.rstrip("/") + "/infer", data=body,
                          headers={"Content-Type": "application/json",
                                   "X-CoDesk-Request-ID": request_id}, method="POST")
        with urlopen(request, timeout=args.timeout) as response:
            payload = json.loads(response.read())
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"worker returned no text: {payload}")
        osworld_root = os.environ.get("OSWORLD_V2_DIR")
        if not osworld_root:
            raise RuntimeError("OSWORLD_V2_DIR must point to the pinned OSWorld V2.1 checkout")
        import sys
        sys.path.insert(0, osworld_root)
        from mm_agents.qwen3vl_agent import Qwen3VLAgent
        agent = Qwen3VLAgent(platform="ubuntu", model="qwen3-vl", coordinate_type="relative")
        width, height = dimensions[0]
        instruction, actions = agent.parse_response(text, width, height, width, height)
        result.update({"status": "pass" if len(actions) == 1 else "invalid_action_count",
            "health": health, "response_text": text, "low_level_instruction": instruction,
            "parsed_actions": actions, "action_count": len(actions),
            "screenshot_sha256": hashlib.sha256(image_bytes[0]).hexdigest(),
            "screenshot_dimensions": dimensions[0], "action_executed": False})
    except Exception as exc:
        result.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)})
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: result.get(k) for k in
                          ("status", "request_id", "elapsed_seconds", "parsed_actions", "error")},
                         ensure_ascii=False))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
