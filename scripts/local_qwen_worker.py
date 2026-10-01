#!/usr/bin/env python3
"""Loopback model-inference transport for the pinned OSWorld Qwen agent."""
from __future__ import annotations

import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import time
import uuid


def _log(event: str, **fields: object) -> None:
    """Emit timing metadata only; never log prompts, images, or model output."""
    print(json.dumps({"event": event, "monotonic_s": round(time.monotonic(), 3), **fields}), flush=True)


class LocalQwenRuntime:
    def __init__(self, model_path: Path, device: str, *, max_memory_gpu: str | None = None,
                 max_memory_cpu: str | None = None, attention_backend: str | None = None):
        load_started = time.perf_counter()
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        import torch
        from transformers import AutoConfig, AutoProcessor
        from transformers import Qwen3VLForConditionalGeneration
        from transformers import Qwen3VLMoeForConditionalGeneration
        from qwen_vl_utils import process_vision_info

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; local model inference is required")
        self.model_path = str(model_path)
        self.device = device
        _log("model.load_start", model=Path(self.model_path).name, device=device,
             dtype="bfloat16", quantization=None, max_memory_gpu=max_memory_gpu,
             max_memory_cpu=max_memory_cpu, attention_backend=attention_backend)
        config = AutoConfig.from_pretrained(self.model_path, local_files_only=True)
        if config.model_type == "qwen3_vl":
            model_class = Qwen3VLForConditionalGeneration
        elif config.model_type == "qwen3_vl_moe":
            model_class = Qwen3VLMoeForConditionalGeneration
        else:
            raise ValueError(f"unsupported Qwen3-VL architecture: {config.model_type}")
        self.processor = AutoProcessor.from_pretrained(self.model_path, local_files_only=True)
        extra = {}
        if attention_backend:
            extra["attn_implementation"] = attention_backend
        if max_memory_gpu:
            if device != "auto":
                raise ValueError("max_memory limits require --device auto")
            extra["max_memory"] = {0: max_memory_gpu, "cpu": max_memory_cpu or "80GiB"}
        if device == "auto":
            self.model = model_class.from_pretrained(
                self.model_path, torch_dtype=torch.bfloat16, device_map="auto",
                local_files_only=True, low_cpu_mem_usage=True, **extra)
        else:
            self.model = model_class.from_pretrained(
                self.model_path, torch_dtype=torch.bfloat16, device_map={"": device},
                local_files_only=True, low_cpu_mem_usage=True, **extra)
        self.model.eval()
        self.torch = torch
        self.process_vision_info = process_vision_info
        device_map = getattr(self.model, "hf_device_map", {})
        self.mapped_devices = sorted({str(value) for value in device_map.values()}) if device_map else []
        self.config_sha256 = hashlib.sha256(
            (Path(self.model_path) / "config.json").read_bytes()).hexdigest()
        self.max_memory = {str(k): str(v) for k, v in extra.get("max_memory", {}).items()}
        self.attention_backend = attention_backend or "transformers-default"
        self.dtype = "bfloat16"
        self.quantization = None
        self.module_device_map = {str(k): str(v) for k, v in device_map.items()}
        _log("model.load_ready", model=Path(self.model_path).name,
             elapsed_s=round(time.perf_counter() - load_started, 3),
             mapped_devices=self.mapped_devices,
             module_count_by_device={device: sum(1 for value in device_map.values() if str(value) == device)
                                     for device in sorted({str(value) for value in device_map.values()})},
             dtype=self.dtype, quantization=self.quantization,
             attention_backend=self.attention_backend, max_memory=self.max_memory,
             gpu_memory_allocated=[int(torch.cuda.memory_allocated(i)) for i in range(torch.cuda.device_count())],
             gpu_memory_reserved=[int(torch.cuda.memory_reserved(i)) for i in range(torch.cuda.device_count())])

    @staticmethod
    def _messages_with_images(messages: list[dict[str, object]]) -> list[dict[str, object]]:
        from PIL import Image
        converted: list[dict[str, object]] = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                converted.append({"role": message.get("role", "user"), "content": content})
                continue
            parts: list[dict[str, object]] = []
            if not isinstance(content, list):
                raise ValueError("message content must be text or an array")
            for part in content:
                if not isinstance(part, dict):
                    raise ValueError("message content item must be an object")
                if part.get("type") == "text":
                    parts.append({"type": "text", "text": str(part.get("text", ""))})
                elif part.get("type") == "image_url":
                    image_url = part.get("image_url")
                    url = image_url.get("url") if isinstance(image_url, dict) else None
                    if not isinstance(url, str) or not url.startswith("data:image/"):
                        raise ValueError("only inline image data URLs are accepted")
                    try:
                        encoded = url.split(",", 1)[1]
                        image_bytes = base64.b64decode(encoded, validate=True)
                    except (IndexError, ValueError) as exc:
                        raise ValueError("invalid inline image data URL") from exc
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        parts.append({"type": "image", "image": image.convert("RGB")})
            converted.append({"role": message.get("role", "user"), "content": parts})
        return converted

    def infer(self, messages: list[dict[str, object]], max_new_tokens: int,
              request_id: str) -> dict[str, object]:
        started = time.perf_counter()
        image_count = sum(
            1 for message in messages
            if isinstance(message.get("content"), list)
            for part in message["content"]
            if isinstance(part, dict) and part.get("type") == "image_url"
        )
        _log("infer.start", request_id=request_id, message_count=len(messages),
             image_count=image_count, max_new_tokens=max_new_tokens)
        stage = time.perf_counter()
        converted = self._messages_with_images(messages)
        _log("infer.images_decoded", request_id=request_id,
             elapsed_s=round(time.perf_counter() - stage, 3))
        stage = time.perf_counter()
        rendered = self.processor.apply_chat_template(
            converted, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = self.process_vision_info(converted)
        _log("infer.template_ready", request_id=request_id,
             elapsed_s=round(time.perf_counter() - stage, 3))
        stage = time.perf_counter()
        inputs = self.processor(text=[rendered], images=image_inputs, videos=video_inputs,
                                padding=True, return_tensors="pt").to(self.model.device)
        _log("infer.inputs_ready", request_id=request_id,
             elapsed_s=round(time.perf_counter() - stage, 3),
             input_tokens=int(inputs.input_ids.shape[1]))
        generation = {"max_new_tokens": max_new_tokens, "do_sample": False}
        stage = time.perf_counter()
        _log("infer.generate_start", request_id=request_id)
        with self.torch.inference_mode():
            generated = self.model.generate(**inputs, **generation)
        _log("infer.generate_done", request_id=request_id,
             elapsed_s=round(time.perf_counter() - stage, 3),
             output_tokens=int(generated.shape[1] - inputs.input_ids.shape[1]))
        stage = time.perf_counter()
        text = self.processor.batch_decode(
            generated[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
        _log("infer.done", request_id=request_id,
             decode_s=round(time.perf_counter() - stage, 3),
             total_s=round(time.perf_counter() - started, 3))
        return {"text": text, "model": Path(self.model_path).name, "device": self.device}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--max-memory-gpu", default=None,
                        help="optional per-visible-GPU max for auto device mapping, e.g. 40GiB")
    parser.add_argument("--max-memory-cpu", default=None,
                        help="optional CPU offload budget used with --max-memory-gpu")
    parser.add_argument("--attn-implementation", choices=("eager", "sdpa", "flash_attention_2"),
                        default=None, help="optional Transformers attention backend")
    args = parser.parse_args()
    runtime = LocalQwenRuntime(args.model, args.device, max_memory_gpu=args.max_memory_gpu,
                               max_memory_cpu=args.max_memory_cpu,
                               attention_backend=args.attn_implementation)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def send_json(self, status: int, value: dict[str, object]) -> None:
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
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
                                 "model_path": str(args.model.resolve()),
                                 "config_sha256": runtime.config_sha256,
                                 "device": runtime.device,
                                 "mapped_devices": runtime.mapped_devices,
                                 "dtype": runtime.dtype, "quantization": runtime.quantization,
                                 "attention_backend": runtime.attention_backend,
                                 "max_memory": runtime.max_memory,
                                 "module_count_by_device": {device: sum(1 for value in runtime.module_device_map.values() if value == device)
                                     for device in sorted(set(runtime.module_device_map.values()))},
                                 "host": socket.gethostname(),
                                 "pid": os.getpid(),
                                 "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                                 "local_files_only": True, "bind": "127.0.0.1"})

        def do_POST(self) -> None:
            if self.path != "/infer":
                self.send_json(404, {"error": "unknown endpoint"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 24_000_000:
                    raise ValueError("request size must be between 1 and 24 MB")
                payload = json.loads(self.rfile.read(size))
                messages = payload.get("messages")
                if not isinstance(messages, list) or len(messages) > 32:
                    raise ValueError("messages must be a list of at most 32 items")
                max_new_tokens = int(payload.get("max_new_tokens", 512))
                if not 1 <= max_new_tokens <= 1536:
                    raise ValueError("max_new_tokens must be between 1 and 1536")
                request_id = self.headers.get("X-CoDesk-Request-ID", "")
                if not request_id or len(request_id) > 64 or not all(
                        char.isalnum() or char in "_-" for char in request_id):
                    request_id = uuid.uuid4().hex[:12]
                _log("http.request_start", request_id=request_id, bytes=size)
                result = runtime.infer(messages, max_new_tokens, request_id)
                self.send_json(200, result)
                _log("http.request_done", request_id=request_id)
            except Exception as exc:
                _log("http.request_error", error_type=type(exc).__name__)
                self.send_json(400, {"error": f"{type(exc).__name__}: {exc}"})

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(json.dumps({"ready": True, "model": args.model.name,
                      "bind": "127.0.0.1", "port": args.port}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
