"""Loopback Responses-API bridge for the existing local Qwen3-VL worker.

This is deliberately a narrow CodexHarness compatibility layer: it forwards
the current multimodal conversation to the existing Qwen runtime and converts
one JSON tool decision into a Responses ``function_call`` item. It never
executes tools; Codex CLI/MCP remains responsible for tool execution.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import re
import struct
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable


TOOL_PROTOCOL = """You are the model behind a computer-use agent. The messages include the task, recent desktop screenshot(s), and the exact available tools. You MUST choose the next tool call when the task is not complete. Return exactly one JSON object and nothing else, using this schema: {\"tool_call\": {\"name\": \"EXACT_TOOL_NAME_FROM_LIST\", \"arguments\": {}}}. When the task is complete, return {\"message\": \"short completion status\"}. Never return bounding boxes, screen descriptions, markdown, or unstructured reasoning. Never invent a tool name or arguments. Example only: {\"tool_call\": {\"name\": \"mcp__desktop__screenshot\", \"arguments\": {}}}."""


def _input_messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions:
        messages.append({"role": "system", "content": instructions})
    content = body.get("input", "")
    if isinstance(content, str):
        messages.append({"role": "user", "content": content})
        return messages
    if isinstance(content, dict):
        content = [content]
    if not isinstance(content, list):
        raise ValueError("Responses input must be a string, object, or array")

    for item in content:
        if not isinstance(item, dict):
            continue
        typ = item.get("type")
        if typ in ("message", "input_message", "response_output_message"):
            role = item.get("role", "user")
            parts = item.get("content", "")
            if isinstance(parts, str):
                messages.append({"role": role, "content": parts})
                continue
            converted: list[dict[str, Any]] = []
            for part in parts if isinstance(parts, list) else []:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype in ("input_text", "output_text", "text"):
                    converted.append({"type": "text", "text": str(part.get("text", ""))})
                elif ptype in ("input_image", "image_url"):
                    url = part.get("image_url")
                    if isinstance(url, dict):
                        url = url.get("url")
                    if isinstance(url, str):
                        converted.append({"type": "image_url", "image_url": {"url": url}})
                elif ptype == "refusal":
                    converted.append({"type": "text", "text": str(part.get("refusal", ""))})
            messages.append({"role": role, "content": converted})
        elif typ == "function_call_output":
            output = item.get("output", "")
            if isinstance(output, list):
                # Codex serializes MCP output as a content array on
                # function_call_output. Never stringify this array: screenshot
                # PNG base64 would become hundreds of thousands of prompt
                # tokens and can trigger a huge KV-cache allocation.
                converted = _tool_result_content(output)
                messages.append({"role": "tool", "content": converted,
                                 "name": str(item.get("name", "tool"))})
            elif isinstance(output, dict) and isinstance(output.get("content"), list):
                converted = _tool_result_content(output["content"])
                messages.append({"role": "tool", "content": converted,
                                 "name": str(item.get("name", "tool"))})
            else:
                messages.append({"role": "tool", "content": str(output),
                                 "name": str(item.get("name", "tool"))})
        elif typ in ("mcp_call_output", "mcp_tool_call_output"):
            output = item.get("result", item.get("output", {}))
            content = output.get("content", []) if isinstance(output, dict) else []
            converted = _tool_result_content(content)
            tool_name = item.get("tool", item.get("name", "tool"))
            messages.append({"role": "tool", "content": converted,
                             "name": str(tool_name)})
        elif typ in ("function_call", "mcp_call", "mcp_tool_call"):
            args = item.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            name = item.get("name", item.get("tool", item.get("server_label", "tool")))
            namespace = item.get("namespace")
            if item.get("type") == "mcp_tool_call":
                name = f"mcp__{item.get('server', 'mcp')}__{item.get('tool', 'tool')}"
            elif isinstance(namespace, str) and namespace:
                prefix = namespace if namespace.endswith("__") else namespace + "__"
                name = name if str(name).startswith("mcp__") else prefix + str(name)
            elif isinstance(name, str) and not name.startswith("mcp__") and item.get("type") in ("mcp_call",):
                server = item.get("server_label", item.get("server", "mcp"))
                name = f"mcp__{server}__{name}"
            action = {"tool_call": {"name": str(name), "arguments": args if isinstance(args, dict) else {}}}
            # Keep the prior assistant action in the same JSON format used by
            # the local protocol. A prose paraphrase is echoed by Qwen as a
            # final answer instead of continuing from the tool screenshot.
            messages.append({"role": "assistant", "content": json.dumps(action, ensure_ascii=False)})
        elif typ == "reasoning":
            summary = item.get("summary") or []
            messages.append({"role": "assistant", "content": " ".join(
                str(x.get("text", "")) for x in summary if isinstance(x, dict))})
    return messages


def _tool_result_content(parts: Any) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for part in parts if isinstance(parts, list) else []:
        if not isinstance(part, dict):
            continue
        if part.get("type") in ("text", "input_text", "output_text"):
            converted.append({"type": "text", "text": str(part.get("text", ""))})
        elif part.get("type") in ("image", "input_image"):
            # Codex may pass MCP images in either the underlying MCP shape
            # (`image` + `data`) or its normalized Responses shape
            # (`input_image` + `image_url`). Dropping the latter leaves the
            # model with an empty screenshot result and causes repeated
            # screenshot calls, even though the request contains the PNG.
            if part.get("type") == "image" and isinstance(part.get("data"), str):
                mime = str(part.get("mimeType", part.get("mime_type", "image/png")))
                url = f"data:{mime};base64,{part['data']}"
            else:
                image_url = part.get("image_url")
                url = image_url.get("url") if isinstance(image_url, dict) else image_url
            if isinstance(url, str) and url.startswith("data:image/"):
                converted.append({"type": "image_url", "image_url": {"url": url}})
    return converted


def _tool_specs(body: dict[str, Any]) -> list[dict[str, Any]]:
    tools = body.get("tools") or []
    if not isinstance(tools, list):
        return []
    result: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") in ("function", "mcp"):
            result.append(tool)
            continue
        # Codex wraps custom MCP tools in a Responses `namespace` extension.
        # The local Qwen runtime only needs ordinary function schemas, so
        # flatten the wrapper while preserving Codex's exact dispatch name.
        if tool.get("type") == "namespace":
            namespace = str(tool.get("name", ""))
            for member in tool.get("tools") or []:
                if not isinstance(member, dict) or not member.get("name"):
                    continue
                member_name = str(member["name"])
                prefix = namespace if namespace.endswith("__") else namespace + "__"
                full_name = member_name if member_name.startswith("mcp__") else prefix + member_name
                parameters = member.get("parameters", member.get("input_schema", {}))
                result.append({"type": "function", "name": full_name,
                    "description": member.get("description", ""), "parameters": parameters,
                    # Preserve Codex's namespace/name pair while presenting a
                    # flat function name to a local model that lacks namespace
                    # tool support. The pair is restored on the response path.
                    "_codex_namespace": namespace,
                    "_codex_tool_name": member_name})
    # Codex also sends its own goal/resource/user-input functions. This agent
    # is authorized only for this run's desktop and optional collaboration MCP.
    return [tool for tool in result if str(tool.get("name", "")).startswith("mcp__")]


def _tool_prompt(tools: list[dict[str, Any]]) -> str:
    compact = []
    for tool in tools:
        if tool.get("type") == "function":
            compact.append({k: tool[k] for k in ("name", "description", "parameters") if k in tool})
        else:
            compact.append({k: tool[k] for k in ("server_label", "server_description", "allowed_tools") if k in tool})
    return TOOL_PROTOCOL + "\nAvailable tools JSON:\n" + json.dumps(compact, ensure_ascii=False)


def _allowed_tool_names(tools: list[dict[str, Any]]) -> set[str]:
    allowed: set[str] = set()
    for tool in tools:
        if tool.get("type") == "function" and tool.get("name"):
            allowed.add(str(tool["name"]))
        elif tool.get("type") == "mcp":
            server = str(tool.get("server_label", "mcp"))
            for name in tool.get("allowed_tools") or []:
                if isinstance(name, str):
                    allowed.add(f"mcp__{server}__{name}")
                    allowed.add(f"{server}__{name}")
    return allowed


def _text_only_input(messages: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            chunks.extend(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return "\n".join(chunks)


def _retain_latest_image(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep textual conversation history but only the newest visual observation.

    Codex includes each earlier MCP screenshot again on every Responses call.
    Re-encoding all of those frames into Qwen's multimodal KV cache caused
    memory growth and eventually OOM on long computer-use turns. The current
    screenshot is the operative observation; prior actions and tool text stay
    in history for continuity.
    """
    latest: tuple[int, int] | None = None
    for mi in range(len(messages) - 1, -1, -1):
        content = messages[mi].get("content")
        if not isinstance(content, list):
            continue
        for pi in range(len(content) - 1, -1, -1):
            part = content[pi]
            if isinstance(part, dict) and part.get("type") == "image_url":
                latest = (mi, pi)
                break
        if latest is not None:
            break
    if latest is None:
        return messages
    for mi, message in enumerate(messages):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        message["content"] = [
            part for pi, part in enumerate(content)
            if not (isinstance(part, dict) and part.get("type") == "image_url")
            or (mi, pi) == latest
        ]
    return messages


def _retain_recent_history(messages: list[dict[str, Any]], recent_messages: int = 12
                           ) -> list[dict[str, Any]]:
    """Bound per-turn context while preserving system/task instructions.

    Codex sends the full conversation again on every Responses request. Keeping
    every old tool result made Qwen's KV cache grow until long episodes OOMed.
    Keep all system messages, the first user task message, and the latest six
    tool/action turns (normally twelve alternating assistant/tool messages).
    """
    if recent_messages < 1:
        raise ValueError("recent_messages must be positive")
    pinned: set[int] = set()
    first_user = next((i for i, message in enumerate(messages)
                       if message.get("role") == "user"), None)
    for i, message in enumerate(messages):
        if message.get("role") == "system" or i == first_user:
            pinned.add(i)
    candidates = [i for i in range(len(messages)) if i not in pinned]
    keep = pinned | set(candidates[-recent_messages:])
    return [message for i, message in enumerate(messages) if i in keep]


def _input_image_sizes(messages: list[dict[str, Any]]) -> list[list[int]]:
    """Read sizes from image data URLs passed to the Qwen worker."""
    sizes: list[list[int]] = []
    for message in messages:
        content = message.get("content")
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            image_url = part.get("image_url")
            url = image_url.get("url") if isinstance(image_url, dict) else image_url
            match = re.match(r"^data:image/[^;]+;base64,(.+)$", str(url or ""), re.DOTALL)
            if not match:
                continue
            raw = base64.b64decode(match.group(1), validate=True)
            if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
                sizes.append(list(struct.unpack(">II", raw[16:24])))
    return sizes


def _extract_decision(text: str, allowed: set[str]) -> tuple[str, dict[str, Any] | str]:
    candidate = text.strip()
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    # Some Qwen generations concatenate multiple valid JSON tool objects
    # despite the one-action instruction. Parse the first complete object
    # instead of greedily merging the entire response and downgrading it to
    # an assistant message (which Codex cannot execute as an action).
    starts = [m.start() for m in re.finditer(r"\{", candidate)]
    for start in starts:
        try:
            value, _end = json.JSONDecoder().raw_decode(candidate[start:])
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(value, dict):
            try:
                call = value.get("tool_call", value if value.get("type") in ("function", "tool_call")
                                 or ("name" in value and "arguments" in value) else None)
                if isinstance(call, dict):
                    name = call.get("name") or call.get("tool")
                    args = call.get("arguments", {})
                    if isinstance(args, str):
                        args = json.loads(args)
                    if name not in allowed:
                        suffix_matches = [x for x in allowed if x.endswith("__" + str(name)) or x.endswith("." + str(name))]
                        if len(suffix_matches) == 1:
                            name = suffix_matches[0]
                    if name in allowed and isinstance(args, dict):
                        return "function_call", {"name": name, "arguments": args}
                if isinstance(value.get("message"), str):
                    return "message", value["message"]
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    return "message", candidate


class QwenResponsesAdapter:
    def __init__(self, infer: Callable[[list[dict[str, Any]], int], dict[str, Any]],
                 *, max_output_tokens_per_actor: int = 12000, max_new_tokens: int = 512,
                 log_path: Path | None = None, count_tokens: Callable[[str], int] | None = None):
        self.infer = infer
        self.max_output_tokens_per_actor = max_output_tokens_per_actor
        self.max_new_tokens = max_new_tokens
        self.log_path = log_path
        self.count_tokens = count_tokens
        self.lock = threading.Lock()  # single shared model; serialize inference requests
        self.used_tokens: dict[str, int] = {"A": 0, "B": 0, "S": 0}

    def respond(self, body: dict[str, Any], actor: str) -> dict[str, Any]:
        if actor not in self.used_tokens:
            raise ValueError(f"unknown actor route {actor!r}")
        remaining = self.max_output_tokens_per_actor - self.used_tokens[actor]
        if remaining <= 0:
            raise RuntimeError(f"actor {actor} exhausted local Qwen output-token budget")
        messages = _retain_latest_image(_retain_recent_history(_input_messages(body)))
        qwen_input_image_sizes = _input_image_sizes(messages)
        tools = _tool_specs(body)
        tool_instruction = _tool_prompt(tools)
        system_message = next((m for m in messages if m.get("role") == "system"), None)
        if system_message:
            system_message["content"] = str(system_message.get("content", "")) + "\n\n" + tool_instruction
        else:
            messages.insert(0, {"role": "system", "content": tool_instruction})
        requested = body.get("max_output_tokens")
        max_new = min(self.max_new_tokens, remaining, int(requested) if requested else self.max_new_tokens)
        started = time.monotonic()
        token_count = self.count_tokens or (lambda s: max(1, (len(s) + 3) // 4))
        input_text = _text_only_input(messages)
        # The runtime's tokenizer/processor is also shared. Keep token counting
        # inside the same critical section as generate(); otherwise another
        # thread can enter the Rust tokenizer while it is still borrowed by the
        # previous request and fail with `Already borrowed`.
        with self.lock:
            result = self.infer(messages, max_new)
            raw_model_output = str(result.get("text", ""))
            text = raw_model_output.strip()
            if not text:
                raise RuntimeError("local Qwen returned empty text")
            output_tokens = token_count(text)
            input_tokens_text_only = token_count(input_text) if input_text else 0
        allowed_tools = _allowed_tool_names(tools)
        kind, value = _extract_decision(text, allowed_tools)
        self.used_tokens[actor] += output_tokens
        rid = "resp_" + uuid.uuid4().hex
        created = int(time.time())
        if kind == "function_call":
            call_id = "call_" + uuid.uuid4().hex
            item = {"id": "fc_" + uuid.uuid4().hex, "type": "function_call", "status": "completed",
                    "call_id": call_id, "name": value["name"],
                    "arguments": json.dumps(value["arguments"], ensure_ascii=False, separators=(",", ":"))}
            # Codex routes MCP calls by the exact (namespace, name) pair.
            # Returning only `mcp__server__tool` is visible to the model but
            # fails at the router with `unsupported call`.
            for tool in tools:
                if tool.get("name") == value["name"] and tool.get("_codex_namespace"):
                    item["namespace"] = tool["_codex_namespace"]
                    item["name"] = tool["_codex_tool_name"]
                    break
        else:
            item = {"id": "msg_" + uuid.uuid4().hex, "type": "message", "status": "completed",
                    "role": "assistant", "content": [{"type": "output_text", "text": str(value), "annotations": []}]}
        response = {"id": rid, "object": "response", "created_at": created, "status": "completed",
                    "model": body.get("model", "Qwen3-VL-30B-A3B-Instruct"), "output": [item],
                    "parallel_tool_calls": False, "store": False,
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"time": time.time(), "actor": actor, "response_id": rid,
                    "kind": kind, "tool": value.get("name") if kind == "function_call" else None,
                    "raw_model_output": raw_model_output,
                    "parsed_arguments": value.get("arguments") if kind == "function_call" else None,
                    "qwen_input_image_sizes": qwen_input_image_sizes,
                    "latency_s": round(time.monotonic() - started, 3), "requested_output_cap": max_new,
                    "generated_output_tokens": output_tokens,
                    "input_tokens_text_only_estimate": input_tokens_text_only,
                    "actor_estimated_output_tokens_total": self.used_tokens[actor],
                    "available_tool_names": sorted(allowed_tools),
                    "tool_schema_types": [t.get("type") for t in tools],
                    "token_count_method": "model tokenizer for output; text-only input excludes image patches" if self.count_tokens else "4-char estimate"}, ensure_ascii=False) + "\n")
        response["usage"] = {"input_tokens": input_tokens_text_only, "output_tokens": output_tokens,
                             "total_tokens": input_tokens_text_only + output_tokens}
        return response


def _stream_events(response: dict[str, Any]):
    rid = response["id"]
    item = response["output"][0]
    yield {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}}
    yield {"type": "response.in_progress", "response": {**response, "status": "in_progress", "output": []}}
    yield {"type": "response.output_item.added", "output_index": 0, "item": {**item, "status": "in_progress"}}
    if item["type"] == "function_call":
        yield {"type": "response.function_call_arguments.delta", "item_id": item["id"],
               "output_index": 0, "delta": item["arguments"]}
        yield {"type": "response.function_call_arguments.done", "item_id": item["id"],
               "output_index": 0, "arguments": item["arguments"]}
    else:
        text = item["content"][0]["text"]
        yield {"type": "response.content_part.added", "item_id": item["id"], "output_index": 0,
               "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}
        yield {"type": "response.output_text.delta", "item_id": item["id"], "output_index": 0,
               "content_index": 0, "delta": text}
        yield {"type": "response.output_text.done", "item_id": item["id"], "output_index": 0,
               "content_index": 0, "text": text}
    yield {"type": "response.output_item.done", "output_index": 0, "item": item}
    yield {"type": "response.completed", "response": response}


def serve(adapter: QwenResponsesAdapter, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def send_json(self, status: int, value: dict[str, Any]) -> None:
            raw = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path.endswith("/models"):
                self.send_json(200, {"object": "list", "data": [{"id": "Qwen3-VL-30B-A3B-Instruct", "object": "model"}]})
            elif self.path == "/health":
                self.send_json(200, {"ready": True, "backend": "local-qwen", "auth": False})
            else:
                self.send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            match = re.fullmatch(r"/actor/([ABS])/v1/responses", self.path)
            if not match:
                self.send_json(404, {"error": "expected /actor/{A|B|S}/v1/responses"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 128_000_000:
                    raise ValueError("request size must be between 1 byte and 128 MB")
                body = json.loads(self.rfile.read(size))
                _append_event(adapter.log_path, {
                    "event": "request_received", "actor": match.group(1), "path": self.path,
                    "request_bytes": size, "input_item_types": [
                        x.get("type") for x in body.get("input", []) if isinstance(x, dict)
                    ] if isinstance(body.get("input"), list) else [],
                    "tool_spec_types": [x.get("type") for x in body.get("tools", []) if isinstance(x, dict)],
                    "time": time.time()})
                response = adapter.respond(body, match.group(1))
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    for event in _stream_events(response):
                        self.wfile.write(("event: " + event["type"] + "\ndata: " +
                                          json.dumps(event, ensure_ascii=False) + "\n\n").encode())
                        self.wfile.flush()
                    self.wfile.write(b"data: [DONE]\n\n")
                else:
                    self.send_json(200, response)
            except Exception as exc:
                _append_event(adapter.log_path, {"event": "request_error", "actor": match.group(1),
                    "path": self.path, "error_type": type(exc).__name__, "error": str(exc),
                    "time": time.time()})
                self.send_json(500, {"error": {"type": type(exc).__name__, "message": str(exc)}})

    server = ThreadingHTTPServer((host, port), Handler)
    return server


def _append_event(path: Path | None, value: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-script", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--max-output-tokens-per-actor", type=int, default=12000)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("local Qwen endpoint must bind loopback only")
    if not args.worker_script.is_file() or not args.model_path.is_dir():
        raise SystemExit("worker script or model path is missing")
    spec = importlib.util.spec_from_file_location("codesk_local_qwen_worker", args.worker_script)
    if not spec or not spec.loader:
        raise SystemExit("cannot import local Qwen worker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = module.LocalQwenRuntime(args.model_path, args.device)
    adapter = QwenResponsesAdapter(runtime.infer,
        max_output_tokens_per_actor=args.max_output_tokens_per_actor,
        max_new_tokens=args.max_new_tokens,
        log_path=args.run_dir / "qwen_gateway_events.jsonl",
        count_tokens=lambda text: len(runtime.processor.tokenizer.encode(text, add_special_tokens=False)))
    server = serve(adapter, args.host, args.port)
    print(json.dumps({"ready": True, "base_url": f"http://{args.host}:{server.server_port}",
                      "model": args.model_path.name, "device": args.device, "auth": False,
                      "loopback_only": True}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
