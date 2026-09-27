"""Local visual-language model actor client with a strict GUI action schema.

The model is served by a separate host Python process so OSWorld's pinned
environment does not need a second Torch/Transformers installation. The worker
receives only task instructions and screenshot bytes; it has no evaluator API.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from typing import Any, Callable
from urllib.request import Request, urlopen

from .environment import ActorContext


class LocalQwenWorkerClient:
    def __init__(self, base_url: str, timeout: float = 180):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        with urlopen(self.base_url + "/health", timeout=5) as response:
            return json.loads(response.read())

    def infer(self, screenshot: bytes, prompt: str, max_new_tokens: int = 128) -> dict[str, Any]:
        payload = json.dumps({
            "image_base64": base64.b64encode(screenshot).decode("ascii"),
            "prompt": prompt,
            "max_new_tokens": max_new_tokens,
        }).encode("utf-8")
        request = Request(self.base_url + "/infer", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError(f"invalid local model response: {result!r}")
        return result


def parse_gui_action(raw: str) -> dict[str, Any]:
    """Parse a single JSON action, allowing a surrounding Markdown code fence."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    # Qwen2.5-VL can emit otherwise clear click coordinates with the y key's
    # quotes or colon omitted. Normalize only these two syntactic forms; never
    # rescale, clamp, or otherwise alter numeric coordinates.
    text = re.sub(r'(?<!["\w])y\s*:', '"y":', text)
    text = re.sub(r'("x"\s*:\s*\d+)\s*,\s*(\d+)(?=\s*[,}])', r'\1,"y":\2', text)
    start = text.find("{")
    if start < 0:
        raise ValueError("model output contains no JSON object")
    depth = 0
    in_string = False
    escaped = False
    end = -1
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end < 0:
        raise ValueError("model output contains an incomplete JSON object")
    action = json.loads(text[start:end])
    if not isinstance(action, dict) or not isinstance(action.get("op"), str):
        raise ValueError("model action must be a JSON object with string field 'op'")
    op = action["op"]
    if op == "click":
        if set(action) != {"op", "x", "y"} or type(action["x"]) is not int or type(action["y"]) is not int:
            raise ValueError("click action requires integer x and y")
    elif op == "type":
        if set(action) != {"op", "text"} or not isinstance(action["text"], str) or len(action["text"]) > 512:
            raise ValueError("type action requires text (maximum 512 characters)")
    elif op == "key":
        allowed = {"ctrl+a", "ctrl+s", "ctrl+z", "ctrl+f", "enter", "return", "tab", "esc", "escape"}
        if set(action) != {"op", "key"} or action["key"].lower() not in allowed:
            raise ValueError("key action is outside the allowlist")
    elif op == "done":
        if set(action) != {"op"}:
            raise ValueError("done action must contain only op")
    else:
        raise ValueError(f"unsupported model GUI operation: {op!r}")
    return action


class LocalQwenGUIActor:
    """Observe–infer–act loop. Only ActorContext tools can affect the Guest."""

    role = "gui"

    def __init__(self, client: LocalQwenWorkerClient, task: str, max_steps: int = 12,
                 event_callback: Callable[[dict[str, Any]], None] | None = None,
                 actor_id: str = "gui_actor", reuse_first_observation: bool = False,
                 action_guard: Callable[[dict[str, Any], list[dict[str, Any]]], str | None] | None = None):
        self.client = client
        self.task = task
        self.max_steps = max_steps
        self.event_callback = event_callback
        self.actor_id = actor_id
        self.reuse_first_observation = reuse_first_observation
        self.action_guard = action_guard
        self.trace: list[dict[str, Any]] = []
        self.history: list[dict[str, Any]] = []
        self.first_screenshot: bytes | None = None
        self.first_observed_revision: int | None = None
        self.finished = False
        self.turn = 0

    def run_step(self, context: ActorContext) -> bool:
        self.turn += 1
        if self.turn > self.max_steps:
            raise RuntimeError(f"{self.actor_id} exceeded its {self.max_steps}-turn budget")
        if self.finished:
            return self.turn == self.max_steps
        if self.reuse_first_observation and self.first_screenshot is not None:
            screenshot = self.first_screenshot
            observed_revision = self.first_observed_revision
        else:
            observation = context.observe()
            screenshot = observation.get("screenshot")
            if not isinstance(screenshot, bytes) or not screenshot:
                raise RuntimeError("local VLM received no screenshot bytes")
            if self.first_screenshot is None:
                self.first_screenshot = screenshot
                revision = getattr(context, "_observed_revision", None)
                self.first_observed_revision = revision if type(revision) is int else None
            observed_revision = getattr(context, "_observed_revision", None)
        step = self.turn
        if not isinstance(screenshot, bytes) or not screenshot:
            raise RuntimeError("local VLM has no screenshot for this turn")
        from PIL import Image
        import io
        with Image.open(io.BytesIO(screenshot)) as image:
            width, height = image.size
        prompt = (
            "You are a GUI computer-use agent. Inspect the screenshot and perform the task. "
            "Return exactly one JSON object, no markdown, with one action from: "
            '{"op":"click","x":integer,"y":integer}, '
            '{"op":"type","text":"..."}, '
            '{"op":"key","key":"ctrl+a|ctrl+s|ctrl+z|ctrl+f|enter|tab|esc"}, '
            '{"op":"done"}. Coordinates are absolute pixels in this screenshot, '
            f"whose dimensions are {width}x{height}. Task: {self.task}\n"
            f"Actions already executed: {json.dumps(self.history, ensure_ascii=False)}\n"
            "Choose only the next action. Use done only when the visible task appears complete."
        )
        action = None
        result: dict[str, Any] = {}
        for attempt in range(1, 4):
            started = time.monotonic()
            result = self.client.infer(screenshot, prompt)
            elapsed_ms = round((time.monotonic() - started) * 1000, 2)
            raw = result["text"]
            try:
                action = parse_gui_action(raw)
                if action.get("op") == "click" and not (
                        0 <= action["x"] < width and 0 <= action["y"] < height):
                    raise ValueError(f"model click {action['x']},{action['y']} exceeds screenshot {width}x{height}")
                if self.action_guard is not None:
                    policy_error = self.action_guard(action, self.history)
                    if policy_error:
                        raise ValueError(f"task action precondition: {policy_error}")
            except Exception as exc:
                failure_record = {
                    "step": step, "attempt": attempt, "actor_id": self.actor_id,
                    "observed_revision": observed_revision,
                    "model": result.get("model", "local-qwen-vl"),
                    "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
                    "screen_size": [width, height], "prompt": prompt, "raw_output": raw,
                    "parsed_action": None, "inference_ms": elapsed_ms,
                    "stale_image": self.reuse_first_observation and step > 1,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                self.trace.append(failure_record)
                if self.event_callback:
                    self.event_callback(failure_record)
                if attempt == 3:
                    raise
                prompt += (
                    f"\nPrevious output rejected: {type(exc).__name__}: {exc}. "
                    f"Return exactly one valid JSON object. Click coordinates must be integers "
                    f"inside 0..{width - 1} and 0..{height - 1}. Do not include a second action.")
                continue
            record = {
                "step": step, "attempt": attempt, "actor_id": self.actor_id,
                "model": result.get("model", "local-qwen-vl"),
                "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
                "screen_size": [width, height], "observed_revision": observed_revision,
                "prompt": prompt, "raw_output": raw, "parsed_action": action,
                "inference_ms": elapsed_ms,
                "stale_image": self.reuse_first_observation and step > 1,
            }
            self.trace.append(record)
            if self.event_callback:
                self.event_callback(record)
            break
        self.history.append(action)
        if action["op"] == "done":
            self.finished = True
            return self.turn == self.max_steps
        if action["op"] == "click":
            context.click(action["x"], action["y"])
        elif action["op"] == "type":
            context.type_text(action["text"])
        elif action["op"] == "key":
            context.press_key(action["key"])
        return self.turn == self.max_steps

    def run(self, context: ActorContext) -> None:
        while self.turn < self.max_steps:
            if self.run_step(context):
                return
