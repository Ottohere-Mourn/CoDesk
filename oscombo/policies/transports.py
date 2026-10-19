"""HTTP transports that replace an OSWorld agent's ``call_llm`` while keeping its prompt, history and parser.

``ChatCompletionsTransport``  any OpenAI-compatible ``/chat/completions`` server (vLLM, SGLang, OpenAI, ...)
``ResponsesTransport``        ``/responses``-only endpoints (Chat-Completions payload converted on the fly)

Both are callable as ``call_llm(payload)`` and ``call_llm(payload, model)`` and return the output text.
Endpoint and key come from the arguments or from ``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


def chat_to_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        text_type = "output_text" if role == "assistant" else "input_text"
        content = message.get("content", "")
        if isinstance(content, str):
            parts = [{"type": text_type, "text": content}]
        else:
            parts = []
            for part in content:
                if part.get("type") == "text":
                    parts.append({"type": text_type, "text": str(part.get("text", ""))})
                elif part.get("type") == "image_url":
                    image = part.get("image_url")
                    url = image.get("url") if isinstance(image, dict) else image
                    detail = image.get("detail", "auto") if isinstance(image, dict) else "auto"
                    parts.append({"type": "input_image", "image_url": url, "detail": detail})
                else:
                    raise ValueError(f"unsupported chat content part: {part.get('type')!r}")
        converted.append({"role": role, "content": parts})
    return converted


class _Transport:
    path = ""

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None, *,
                 extra_body: dict[str, Any] | None = None, max_retries: int = 8, timeout: float = 300):
        self.model = model
        base = base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self.url = base.rstrip("/") + self.path
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.extra_body = extra_body or {}
        self.max_retries = max_retries
        self.rate_limit_retries = int(os.environ.get("OSCOMBO_RATE_LIMIT_RETRIES", "60"))
        self.timeout = timeout
        self.calls: list[dict[str, Any]] = []  # per-request timing and token usage

    def body(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def text(self, result: dict[str, Any]) -> str:
        raise NotImplementedError

    def __call__(self, payload: dict[str, Any], _model: str | None = None) -> str:
        data = json.dumps({**self.body(payload), **self.extra_body}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        delay, errors, limited = 10.0, 0, 0
        while True:
            started = time.monotonic()
            try:
                with urlopen(Request(self.url, data=data, headers=headers, method="POST"),
                             timeout=self.timeout) as response:
                    result = json.loads(response.read())
                text = self.text(result)
                self.calls.append({"seconds": round(time.monotonic() - started, 2), "usage": result.get("usage")})
                if not text:
                    raise ValueError("empty model output")
                return text
            except HTTPError as exc:
                # shared deployments answer 429 with a short Retry-After: many short randomized retries
                if exc.code == 429 and limited < self.rate_limit_retries:
                    limited += 1
                    print(f"RATE_LIMIT_RETRY {limited}", file=sys.stderr, flush=True)
                    time.sleep(random.uniform(2.0, 10.0))
                    continue
                if exc.code not in RETRY_STATUS or errors == self.max_retries:
                    raise RuntimeError(f"{self.url} HTTP {exc.code}: {exc.read()[:300]!r}") from exc
            except (URLError, TimeoutError, ValueError) as exc:
                if errors == self.max_retries:
                    raise RuntimeError(f"{self.url} failed after {errors + 1} attempts: {exc}") from exc
            errors += 1
            time.sleep(delay)
            delay = min(delay * 2, 120.0)

    complete = __call__


class ChatCompletionsTransport(_Transport):
    path = "/chat/completions"

    def body(self, payload: dict[str, Any]) -> dict[str, Any]:
        keep = ("messages", "max_tokens", "max_completion_tokens", "temperature", "top_p", "stop")
        return {"model": self.model, **{k: payload[k] for k in keep if k in payload}}

    def text(self, result: dict[str, Any]) -> str:
        return (result.get("choices") or [{}])[0].get("message", {}).get("content") or ""


class ResponsesTransport(_Transport):
    path = "/responses"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None, *,
                 reasoning_effort: str | None = None, **kw: Any):
        super().__init__(model, base_url, api_key, **kw)
        self.reasoning_effort = reasoning_effort

    def body(self, payload: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "input": chat_to_responses_input(payload["messages"]),
                                "store": False}
        max_tokens = payload.get("max_completion_tokens") or payload.get("max_tokens")
        if max_tokens:
            body["max_output_tokens"] = int(max_tokens)
        if self.reasoning_effort:
            body["reasoning"] = {"effort": self.reasoning_effort}
        return body

    def text(self, result: dict[str, Any]) -> str:
        return "".join(c.get("text", "") for item in result.get("output", []) if item.get("type") == "message"
                       for c in item.get("content", []) if c.get("type") == "output_text")
