"""Minimal Transformers runtime for the existing CodexHarness/Qwen bridge.

This module only loads Qwen and maps the bridge's text/image messages to the
checkpoint processor. Tool selection and GUI execution remain in the existing
CodexHarness and MCP servers.
"""
from __future__ import annotations

import base64
import re
from io import BytesIO
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor


_DATA_IMAGE = re.compile(r"^data:image/[^;]+;base64,(.*)$", re.DOTALL)


class LocalQwenRuntime:
    def __init__(self, model_path: Path, device: str = "auto") -> None:
        self.model_path = Path(model_path)
        self.processor = AutoProcessor.from_pretrained(
            self.model_path, local_files_only=True
        )
        device_map: str | dict[str, str] = "auto" if device == "auto" else {"": device}
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_path,
            torch_dtype=torch.bfloat16,
            device_map=device_map,
            local_files_only=True,
            low_cpu_mem_usage=True,
        ).eval()

    @staticmethod
    def _messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = message.get("content", "")
            if isinstance(content, str):
                converted.append({"role": role, "content": [{"type": "text", "text": content}]})
                continue
            parts: list[dict[str, Any]] = []
            for part in content if isinstance(content, list) else []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    parts.append({"type": "text", "text": str(part.get("text", ""))})
                elif part.get("type") == "image_url":
                    image_url = part.get("image_url")
                    url = image_url.get("url") if isinstance(image_url, dict) else image_url
                    match = _DATA_IMAGE.match(str(url or ""))
                    if not match:
                        raise ValueError("Qwen image input must be a base64 data URL")
                    raw = base64.b64decode(match.group(1), validate=True)
                    image = Image.open(BytesIO(raw)).convert("RGB")
                    parts.append({"type": "image", "image": image})
            converted.append({"role": role, "content": parts})
        return converted

    @torch.inference_mode()
    def infer(self, messages: list[dict[str, Any]], max_new_tokens: int) -> dict[str, str]:
        conversation = self._messages(messages)
        inputs = self.processor.apply_chat_template(
            conversation,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
        model_device = self.model.device
        inputs = {key: value.to(model_device) if hasattr(value, "to") else value
                  for key, value in inputs.items()}
        generated = self.model.generate(
            **inputs,
            max_new_tokens=int(max_new_tokens),
            do_sample=False,
        )
        prompt_length = inputs["input_ids"].shape[1]
        text = self.processor.batch_decode(
            generated[:, prompt_length:], skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return {"text": text}
