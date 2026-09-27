#!/usr/bin/env python3
"""Loopback-only worker for existing local Qwen-VL weights (no network fetch)."""
from __future__ import annotations

import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import time


class InferenceRuntime:
    def __init__(self, model_path: Path, device: str):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        import torch
        from transformers import AutoConfig, AutoProcessor
        from qwen_vl_utils import process_vision_info

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; refusing to fall back to unverified mock inference")
        self.device = device
        self.model_path = str(model_path)
        config = AutoConfig.from_pretrained(self.model_path, local_files_only=True)
        if config.model_type == "qwen3_vl":
            from transformers import Qwen3VLForConditionalGeneration
            model_class = Qwen3VLForConditionalGeneration
        elif config.model_type == "qwen2_5_vl":
            from transformers import Qwen2_5_VLForConditionalGeneration
            model_class = Qwen2_5_VLForConditionalGeneration
        else:
            raise ValueError(f"unsupported local Qwen-VL model type: {config.model_type}")
        self.processor = AutoProcessor.from_pretrained(self.model_path, local_files_only=True)
        self.model = model_class.from_pretrained(
            self.model_path, torch_dtype=torch.bfloat16, device_map={"": device},
            local_files_only=True, low_cpu_mem_usage=True)
        self.model.eval()
        self.torch = torch
        self.process_vision_info = process_vision_info

    def infer(self, image_bytes: bytes, prompt: str, max_new_tokens: int) -> dict[str, object]:
        from PIL import Image
        started = time.monotonic()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        messages = [{"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": prompt},
        ]}]
        rendered = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = self.process_vision_info(messages)
        inputs = self.processor(text=[rendered], images=image_inputs, videos=video_inputs,
                                padding=True, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            generated = self.model.generate(**inputs, max_new_tokens=max_new_tokens,
                                            do_sample=False)
        text = self.processor.batch_decode(
            generated[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
        return {"text": text, "model": Path(self.model_path).name,
                "inference_ms": round((time.monotonic() - started) * 1000, 2),
                "device": self.device}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    runtime = InferenceRuntime(args.model, args.device)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_json(404, {"error": "unknown endpoint"})
                return
            self.send_json(200, {"ready": True, "model": args.model.name,
                                 "device": args.device, "local_files_only": True})

        def do_POST(self) -> None:
            if self.path != "/infer":
                self.send_json(404, {"error": "unknown endpoint"})
                return
            try:
                if int(self.headers.get("Content-Length", "0")) > 12_000_000:
                    raise ValueError("request exceeds 12 MB limit")
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                prompt = payload["prompt"]
                max_new_tokens = int(payload.get("max_new_tokens", 128))
                if not isinstance(prompt, str) or len(prompt) > 12_000:
                    raise ValueError("invalid or oversized prompt")
                if not 1 <= max_new_tokens <= 256:
                    raise ValueError("max_new_tokens must be between 1 and 256")
                image = base64.b64decode(payload["image_base64"], validate=True)
                self.send_json(200, runtime.infer(image, prompt, max_new_tokens))
            except Exception as exc:
                self.send_json(400, {"error": f"{type(exc).__name__}: {exc}"})

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(json.dumps({"ready": True, "model": args.model.name,
                      "device": args.device, "bind": "127.0.0.1", "port": args.port}),
          flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
