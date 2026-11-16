"""8-task (4 categories x 2 tasks) DeepSeek V4.1 autonomous race-awareness benchmark runner.

Supports both native OpenAI /responses providers and /chat/completions providers
via a local host-side Responses SSE bridge, running strictly inside non-YOLO
workspace-write Docker sandboxes on cpu15.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time
import os
import requests

from experiments.astra_races_v2 import AstraSharedDesktop, make_role_handlers
from experiments.codesk_container_codex import (
    CONTAINER_ENTRY_SOURCE,
    DEFAULT_CODEX_BINARY,
    DEFAULT_CONTAINER_IMAGE,
    GUEST_BASH_BRIDGE_CLI_SOURCE,
    HostActorBridge,
    MCP_PROXY_SOURCE,
    codex_requirements_mount,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.long_horizon_v1 import LongHorizonDesktop, build_lh_config_template, build_lh_prompt, make_lh_handlers, start_lh_relay
from experiments.quad_hybrid_v1 import QuadSharedDesktop, build_quad_prompt, make_quad_handlers
from experiments.responses_relay import prepare_image_history
from tasks.astra_races_v2.catalog import CATALOG_BY_ID as AR_BY_ID
from tasks.long_horizon_v1.catalog import LH_BY_ID
from tasks.quad_hybrid_v1.catalog import QH_BY_ID, QUAD_ROLES
from tasks.quad_hybrid_v1.suite import write_json


EVAL_MATRIX_8 = [
    {"category": "1_prof_software_2agent", "suite": "astra_races_v2", "id": "AR-03", "agents": 2},
    {"category": "1_prof_software_2agent", "suite": "astra_races_v2", "id": "AR-04", "agents": 2},
    {"category": "2_browser_portal_2agent", "suite": "astra_races_v2", "id": "AR-07", "agents": 2},
    {"category": "2_browser_portal_2agent", "suite": "astra_races_v2", "id": "AR-08", "agents": 2},
    {"category": "3_long_horizon_drc_2agent", "suite": "long_horizon_v1", "id": "LH-02", "agents": 2},
    {"category": "3_long_horizon_drc_2agent", "suite": "long_horizon_v1", "id": "LH-03", "agents": 2},
    {"category": "4_quad_hybrid_gui_cli_4agent", "suite": "quad_hybrid_v1", "id": "QH-01", "agents": 4},
    {"category": "4_quad_hybrid_gui_cli_4agent", "suite": "quad_hybrid_v1", "id": "QH-03", "agents": 4},
]

AWARENESS_CMD_PATTERNS = {
    "process_or_peer_probe": re.compile(r"\b(ps\s+aux|pgrep|lsof|fuser|who|xwininfo)\b"),
    "lock_or_handoff_ipc": re.compile(r"(flock|GUI_OWNER|ROLE_[ABCD]|_DONE|_READY|MESSAGE_FROM|\.lock|LOCK)", re.I),
    "polling_wait_loop": re.compile(r"(while\s+.*sleep|for\s+\w+\s+in\s+\$\(seq.*sleep|inotifywait)"),
    "hash_or_mtime_recheck": re.compile(r"(sha256sum|stat\s+-c)"),
}

AWARENESS_TEXT_PATTERNS = re.compile(
    r"(concurrent|another\s+agent|other\s+agent|co-?agent|race\s+condition|stole|clobber|overwrit|lock|mutex|竞争|并发|其他智能体|被改|抢占)",
    re.I,
)


def responses_req_to_chat_completions(parsed: dict, upstream_model: str) -> dict:
    messages: list[dict] = []
    if parsed.get("instructions"):
        messages.append({"role": "system", "content": str(parsed["instructions"])})
    raw_in = parsed.get("input")
    if isinstance(raw_in, str):
        messages.append({"role": "user", "content": raw_in})
    elif isinstance(raw_in, list):
        pending_tool_calls: list[dict] = []
        def flush_assistant_tools():
            nonlocal pending_tool_calls
            if pending_tool_calls:
                messages.append({"role": "assistant", "content": "", "tool_calls": pending_tool_calls})
                pending_tool_calls = []

        for item in raw_in:
            if not isinstance(item, dict):
                continue
            itype = item.get("type")
            if itype == "function_call":
                pending_tool_calls.append({
                    "id": item.get("call_id") or item.get("id") or f"call_{secrets.token_hex(6)}",
                    "type": "function",
                    "function": {"name": item.get("name", ""), "arguments": item.get("arguments", "{}")},
                })
                continue
            if itype == "function_call_output":
                flush_assistant_tools()
                out_val = item.get("output", "")
                extra_images: list[dict] = []
                if isinstance(out_val, list):
                    txts = []
                    for blk in out_val:
                        if isinstance(blk, dict) and blk.get("type") in ("input_text", "text"):
                            txts.append(str(blk.get("text", "")))
                        elif isinstance(blk, dict) and blk.get("type") in ("input_image", "image"):
                            url = blk.get("image_url") or (f"data:{blk.get('mimeType','image/png')};base64,{blk['data']}" if blk.get("data") else None)
                            if url:
                                extra_images.append({"type": "image_url", "image_url": {"url": url}})
                    out_str = "\n".join(txts) or "OK"
                else:
                    out_str = str(out_val)
                messages.append({"role": "tool", "tool_call_id": item.get("call_id", ""), "content": out_str})
                if extra_images:
                    messages.append({"role": "user", "content": [{"type": "text", "text": "Attached tool screenshot:"}, *extra_images]})
                continue
            if itype == "reasoning":
                continue
            role = item.get("role")
            if role in ("system", "developer", "user", "assistant"):
                flush_assistant_tools()
                mapped_role = "system" if role == "developer" else role
                parts = []
                content = item.get("content", "")
                if isinstance(content, str):
                    messages.append({"role": mapped_role, "content": content})
                elif isinstance(content, list):
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        ct = c.get("type")
                        if ct in ("input_text", "output_text", "text"):
                            parts.append({"type": "text", "text": str(c.get("text", ""))})
                        elif ct == "input_image":
                            u = c.get("image_url")
                            if isinstance(u, dict):
                                u = u.get("url")
                            if u:
                                parts.append({"type": "image_url", "image_url": {"url": u}})
                    if parts:
                        if len(parts) == 1 and parts[0]["type"] == "text":
                            messages.append({"role": mapped_role, "content": parts[0]["text"]})
                        else:
                            messages.append({"role": mapped_role, "content": parts})
        flush_assistant_tools()

    chat_tools = []
    for t in parsed.get("tools") or []:
        if isinstance(t, dict) and t.get("type") == "function":
            chat_tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters") or {"type": "object", "properties": {}},
                },
            })
    out: dict = {"model": upstream_model, "messages": messages, "stream": False}
    if chat_tools:
        out["tools"] = chat_tools
    out["thinking"] = {"type": "enabled"}
    out["reasoning_effort"] = "high"
    if parsed.get("max_output_tokens"):
        out["max_tokens"] = int(parsed["max_output_tokens"])
    return out


def chat_completion_to_responses_sse(chat_json: dict, codex_model: str) -> bytes:
    resp_id = chat_json.get("id") or f"resp_{secrets.token_hex(8)}"
    choice = ((chat_json.get("choices") or [{}])[0]).get("message") or {}
    output_items = []
    events = []

    def add_evt(ev_obj: dict) -> None:
        events.append(f"event: {ev_obj['type']}\ndata: {json.dumps(ev_obj, ensure_ascii=False)}\n\n".encode("utf-8"))

    add_evt({"type": "response.created", "response": {"id": resp_id, "object": "response", "status": "in_progress", "model": codex_model, "output": []}})
    out_idx = 0
    txt = choice.get("content")
    if isinstance(txt, str) and txt:
        msg_item = {
            "id": f"msg_{secrets.token_hex(6)}",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": txt, "annotations": []}],
        }
        add_evt({"type": "response.output_item.added", "output_index": out_idx, "item": msg_item})
        add_evt({"type": "response.output_item.done", "output_index": out_idx, "item": msg_item})
        output_items.append(msg_item)
        out_idx += 1
    for tc in choice.get("tool_calls") or []:
        fn = tc.get("function") or {}
        cid = tc.get("id") or f"call_{secrets.token_hex(6)}"
        fc_item = {
            "id": f"fc_{secrets.token_hex(6)}",
            "type": "function_call",
            "status": "completed",
            "call_id": cid,
            "name": fn.get("name", ""),
            "arguments": fn.get("arguments", "{}"),
        }
        add_evt({"type": "response.output_item.added", "output_index": out_idx, "item": fc_item})
        add_evt({"type": "response.output_item.done", "output_index": out_idx, "item": fc_item})
        output_items.append(fc_item)
        out_idx += 1
    usage_in = chat_json.get("usage") or {}
    usage = {
        "input_tokens": int(usage_in.get("prompt_tokens", 0)),
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": int(usage_in.get("completion_tokens", 0)),
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": int(usage_in.get("total_tokens", 0)),
    }
    add_evt({
        "type": "response.completed",
        "response": {"id": resp_id, "object": "response", "status": "completed", "model": codex_model, "output": output_items, "usage": usage},
    })
    return b"".join(events)


def analyze_race_awareness(cond_dir: Path, roles: tuple[str, ...]) -> dict:
    per_role = {}
    any_ipc = False
    any_poll = False
    any_explicit = False
    for r in roles:
        adir = cond_dir / f"actor_{r}"
        cmd_hits = {k: 0 for k in AWARENESS_CMD_PATTERNS}
        samples = []
        af = adir / "actions.jsonl"
        if af.is_file():
            for ln in af.read_text(encoding="utf-8", errors="replace").splitlines():
                if not ln.strip():
                    continue
                row = json.loads(ln)
                if row.get("tool", "").startswith("guest_bash"):
                    cmd = str((row.get("args") or {}).get("command", ""))
                    for pname, rx in AWARENESS_CMD_PATTERNS.items():
                        if rx.search(cmd):
                            cmd_hits[pname] += 1
                            if pname in ("lock_or_handoff_ipc", "polling_wait_loop") and len(samples) < 3:
                                samples.append(cmd[:140])
        explicit_mentions = 0
        sf = adir / "stdout.log"
        if sf.is_file():
            for ln in sf.read_text(encoding="utf-8", errors="replace").splitlines():
                if '"agent_message"' in ln or '"reasoning"' in ln:
                    if AWARENESS_TEXT_PATTERNS.search(ln):
                        explicit_mentions += 1
        if cmd_hits["lock_or_handoff_ipc"] > 0:
            any_ipc = True
        if cmd_hits["polling_wait_loop"] > 0:
            any_poll = True
        if explicit_mentions > 0:
            any_explicit = True
        per_role[r] = {
            "command_signals": cmd_hits,
            "explicit_race_mentions": explicit_mentions,
            "evidence_samples": samples,
        }
    return {
        "spontaneous_ipc_or_locking": any_ipc,
        "spontaneous_wait_polling": any_poll,
        "explicit_contention_verbalized": any_explicit,
        "autonomous_race_aware": bool(any_ipc or any_explicit or any_poll),
        "roles": per_role,
    }


def start_dsv41_relay(
    upstream_base: str,
    api_key: str,
    event_log: Path,
    codex_model: str = "deepseek-v4.1",
    upstream_model: str = "deepseek-v4.1",
    wire_mode: str = "auto",
    extra_headers: dict[str, str] | None = None,
) -> tuple[ThreadingHTTPServer, int]:
    base = upstream_base.rstrip("/")
    resp_url = base if base.endswith("/responses") else (base + "/responses")
    chat_base = base[:-len("/responses")] if base.endswith("/responses") else base
    chat_url = chat_base + "/chat/completions"
    mode_state = {"wire": wire_mode}

    class RelayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_unused):
            return

        def do_POST(self):
            started = time.monotonic()
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict) and isinstance(parsed.get("input"), list) and not parsed.get("previous_response_id"):
                parsed, _ = prepare_image_history(parsed, keep=4, max_images=28)
            hdrs = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            if extra_headers:
                hdrs.update(extra_headers)

            if mode_state["wire"] in ("auto", "responses"):
                p_resp = dict(parsed, model=upstream_model)
                if parsed.get("reasoning") and upstream_model.startswith("deepseek"):
                    p_resp["reasoning"] = {"effort": parsed["reasoning"].get("effort", "high")}
                body_bytes = json.dumps(p_resp, ensure_ascii=False).encode("utf-8")
                cand = None
                for retry_i in range(6):
                    try:
                        c_try = requests.post(resp_url, headers={**hdrs, "Accept": "text/event-stream"}, data=body_bytes, stream=True, timeout=(25, 420))
                    except requests.RequestException:
                        if retry_i < 5:
                            time.sleep(6.0 + 4.0 * retry_i)
                            continue
                        self.send_error(502, "Upstream request exception")
                        return
                    if c_try.status_code in (429, 500, 502, 503, 504) and retry_i < 5:
                        c_try.close()
                        time.sleep(8.0 + 5.0 * retry_i)
                        continue
                    cand = c_try
                    break
                assert cand is not None
                if cand.status_code in (404, 405) and mode_state["wire"] == "auto":
                    cand.close()
                    mode_state["wire"] = "chat_completions"
                else:
                    with cand:
                        self.send_response(cand.status_code)
                        self.send_header("Content-Type", cand.headers.get("Content-Type", "text/event-stream"))
                        self.send_header("Connection", "close")
                        self.end_headers()
                        src_a = f'"model":"{upstream_model}"'.encode()
                        dst_a = f'"model":"{codex_model}"'.encode()
                        src_b = f'"model": "{upstream_model}"'.encode()
                        dst_b = f'"model": "{codex_model}"'.encode()
                        for line in cand.iter_lines():
                            self.wfile.write(line.replace(src_a, dst_a).replace(src_b, dst_b) + b"\n")
                            self.wfile.flush()
                        self.close_connection = True
                    with event_log.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"time": time.time(), "wire": "responses", "status": cand.status_code, "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")
                    return

            chat_payload = responses_req_to_chat_completions(parsed, upstream_model)
            cand_c = requests.post(chat_url, headers=hdrs, data=json.dumps(chat_payload, ensure_ascii=False).encode("utf-8"), timeout=(25, 420))
            if cand_c.status_code != 200:
                self.send_response(cand_c.status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(cand_c.content)
                self.close_connection = True
            else:
                sse_bytes = chat_completion_to_responses_sse(cand_c.json(), codex_model)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(sse_bytes)
                self.wfile.flush()
                self.close_connection = True
            with event_log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"time": time.time(), "wire": "chat_completions", "status": cand_c.status_code, "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), RelayHandler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_port


def run_dsv41_actor(
    role: str,
    handlers: dict,
    actor_dir: Path,
    ticket_dir: Path,
    prompt_text: str,
    api_cfg: dict,
    codex_bin: Path,
    timeout_s: int,
) -> dict:
    raw_model = str(api_cfg.get("model", "deepseek-flash"))
    is_deepseek = raw_model.startswith("deepseek")
    codex_model = "deepseek-v4.1" if is_deepseek else raw_model
    upstream_model = raw_model if is_deepseek else str(api_cfg.get("upstream_model_sol") or api_cfg.get("upstream_model") or raw_model)
    effort = api_cfg.get("reasoning_effort", "high")
    wire_mode = api_cfg.get("wire_mode", "auto")
    session_dir = actor_dir / "container_session"
    for sub in ("codex-home", "work", "bridge"):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)
    (session_dir / "bridge/container_entry.py").write_text(CONTAINER_ENTRY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/mcp_proxy.py").write_text(MCP_PROXY_SOURCE, encoding="utf-8")
    (session_dir / "bridge/guest_bash.py").write_text(GUEST_BASH_BRIDGE_CLI_SOURCE, encoding="utf-8")
    write_json(session_dir / "codex-home/models-catalog.json", {"models": [{
        "slug": codex_model,
        "display_name": codex_model,
        "description": "DeepSeek V4.1 hybrid GUI+CLI desktop agent.",
        "default_reasoning_level": effort,
        "supported_reasoning_levels": [{"effort": lv, "description": lv} for lv in ("low", "medium", "high", "xhigh")],
        "shell_type": "unified_exec",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 1,
        "additional_speed_tiers": [],
        "service_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "model_messages": None,
        "include_skills_usage_instructions": False,
        "include_plugin_usage_instructions": False,
        "include_apps_usage_instructions": False,
        "default_reasoning_summary": "none",
        "support_verbosity": False,
        "default_verbosity": "low",
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": "text_and_image",
        "truncation_policy": {"mode": "tokens", "limit": 10000},
        "supports_parallel_tool_calls": False,
        "supports_image_detail_original": True,
        "context_window": 262144,
        "max_context_window": 262144,
        "comp_hash": "",
        "effective_context_window_percent": 95,
        "experimental_supported_tools": [],
        "input_modalities": ["text", "image"],
        "supports_search_tool": False,
        "use_responses_lite": False,
        "tool_mode": "direct",
        "multi_agent_version": "v2",
        "base_instructions": "You are a hybrid GUI+CLI engineering agent. Complete your assigned ticket accurately.",
    }]})
    tmpl = build_lh_config_template(codex_model, effort)
    validate_container_config_text(tmpl.replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    (session_dir / "codex-home/config.template.toml").write_text(tmpl, encoding="utf-8")
    (session_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    for item in [actor_dir, session_dir, *session_dir.rglob("*")]:
        try:
            os.chmod(item, 0o770 if item.is_dir() else 0o660)
        except OSError:
            pass

    if is_deepseek:
        relay_srv, relay_port = start_dsv41_relay(
            api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl",
            codex_model=codex_model, upstream_model=upstream_model, wire_mode=wire_mode,
        )
    else:
        relay_srv, relay_port = start_lh_relay(
            api_cfg["base_url"], api_cfg["api_key"], actor_dir / "relay_events.jsonl",
            model_name=codex_model, upstream_model=upstream_model,
        )
    bridge = HostActorBridge(None, relay_port, handlers, image_history_keep=4, max_request_images=24)
    bridge.start()
    cname = f"paragui-dsv41-codex-{role.lower()}-{secrets.token_hex(5)}"
    create_cmd = [
        "docker", "create", "--name", cname, "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,size=256m", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "2048", "--cpus", "2", "--memory", "3g", "--user", "1000:0",
        "--label", "org.paragui.kind=dsv41-codex-actor",
        "-v", f"{session_dir}:/session", "-v", f"{session_dir / 'bridge'}:/bridge:ro",
        "-v", f"{ticket_dir}:/session/ticket:ro", "-v", f"{bridge.ipc_dir}:/ipc",
        "-v", f"{codex_bin.parent}:/codex:ro", "-w", "/session",
        "-e", "HOME=/session", "-e", "CODEX_HOME=/session/codex-home",
        "-e", "CODESK_CONTAINER_PERMISSION_MODE=container-unrestricted",
        "-e", "TOKIO_WORKER_THREADS=4", "-e", "PYTHONDONTWRITEBYTECODE=1",
        *codex_requirements_mount(), DEFAULT_CONTAINER_IMAGE, "python3", "/bridge/container_entry.py",
    ]
    t_start = time.time()
    cid = None
    timed_out = False
    try:
        cid = subprocess.run(create_cmd, check=True, capture_output=True, text=True, timeout=45).stdout.strip()
        with (actor_dir / "stdout.log").open("w", encoding="utf-8") as out_f, (actor_dir / "stderr.log").open("w", encoding="utf-8") as err_f:
            proc = subprocess.Popen(["docker", "start", "-a", cid], stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f, start_new_session=True)
            while proc.poll() is None:
                if time.time() - t_start > timeout_s:
                    timed_out = True
                    subprocess.run(["docker", "kill", cid], capture_output=True, timeout=15)
                    proc.wait(timeout=10)
                    break
                time.sleep(0.5)
        t_end = time.time()
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{session_dir}:/session", DEFAULT_CONTAINER_IMAGE, "chmod", "-R", "ug+rwX", "/session"], capture_output=True, timeout=20)
        audit = verify_container_permission_audit(session_dir, expected_model=codex_model, permission_mode="container-unrestricted")
        write_json(actor_dir / "permission-audit-verified.json", audit)
        action_log = actor_dir / "actions.jsonl"
        acts = [json.loads(ln) for ln in action_log.read_text(encoding="utf-8").splitlines() if ln.strip()] if action_log.is_file() else []
        gui_obs = sum(1 for a in acts if a["tool"] in {"desktop.screenshot", "desktop.wait"})
        gui_act = sum(1 for a in acts if a["tool"].startswith("desktop.") and a["tool"] not in {"desktop.screenshot", "desktop.wait"})
        cli_c = sum(1 for a in acts if a["tool"].startswith("guest_bash."))
        return {
            "role": role,
            "status": "timeout" if timed_out else ("done" if proc.returncode == 0 else "error"),
            "exit_code": proc.returncode,
            "wall_seconds": round(t_end - t_start, 2),
            "gui_observation_calls": gui_obs,
            "gui_action_calls": gui_act,
            "cli_calls": cli_c,
            "permission_audit_ok": True,
        }
    finally:
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20)
        bridge.close()
        relay_srv.shutdown()
        relay_srv.server_close()


def run_dsv41_case(entry: dict, out_dir: Path, code_root: Path, api_cfg: dict, codex_bin: Path) -> dict:
    from experiments.astra_races_v2 import build_astra_prompt
    from experiments.record_astra_rollouts import RecordedDesktop

    tid = entry["id"]
    suite = entry["suite"]
    cond_dir = out_dir / tid / "concurrent"
    if (cond_dir / "report.json").is_file():
        existing = json.loads((cond_dir / "report.json").read_text(encoding="utf-8"))
        if existing.get("valid_model_run"):
            return existing
    if cond_dir.exists():
        shutil.rmtree(cond_dir, ignore_errors=True)
    cond_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    if suite == "astra_races_v2":
        roles = ("A", "B")
        desk = RecordedDesktop(cond_dir, tid, code_root)
        desk.build_pristine(); desk.start()
        bar = threading.Barrier(2)
        actors = {}
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futs = {}
                for r in roles:
                    adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                    alog = adir / "actions.jsonl"; alog.touch()
                    tdir = desk.ticket_a if r == "A" else desk.ticket_b
                    ptxt = build_astra_prompt(r, (tdir / "task.md").read_text(encoding="utf-8"))
                    h = make_role_handlers(desk, r, alog, bar)
                    futs[pool.submit(run_dsv41_actor, r, h, adir, tdir, ptxt, api_cfg, codex_bin, 900)] = r
                for fut in as_completed(futs):
                    actors[futs[fut]] = fut.result()
        finally:
            grade_res, ver_cnt = desk.stop_and_grade()

    elif suite == "long_horizon_v1":
        roles = ("A", "B")
        desk_lh = LongHorizonDesktop(cond_dir, tid, code_root, record_video=True)
        desk_lh.build_pristine(); desk_lh.start()
        bar = threading.Barrier(2)
        actors = {}
        t_lim = int(LH_BY_ID[tid]["conc_role_timeout_s"])
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futs = {}
                for r in roles:
                    adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                    alog = adir / "actions.jsonl"; alog.touch()
                    tdir = desk_lh.ticket_a if r == "A" else desk_lh.ticket_b
                    ptxt = build_lh_prompt(r, (tdir / "task.md").read_text(encoding="utf-8"), t_lim)
                    h = make_lh_handlers(desk_lh, r, alog, bar)
                    futs[pool.submit(run_dsv41_actor, r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)] = r
                for fut in as_completed(futs):
                    actors[futs[fut]] = fut.result()
        finally:
            grade_res, ver_cnt = desk_lh.stop_and_grade()

    elif suite == "quad_hybrid_v1":
        roles = QUAD_ROLES
        desk_q = QuadSharedDesktop(cond_dir, tid, code_root, record_video=True)
        desk_q.build_pristine(); desk_q.start()
        bar = threading.Barrier(4)
        actors = {}
        t_lim = int(QH_BY_ID[tid]["conc_role_timeout_s"])
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = {}
                for r in roles:
                    adir = cond_dir / f"actor_{r}"; adir.mkdir(parents=True, exist_ok=True)
                    alog = adir / "actions.jsonl"; alog.touch()
                    tdir = desk_q.tickets_root / r
                    ptxt = build_quad_prompt(r, (tdir / "task.md").read_text(encoding="utf-8"), t_lim)
                    h = make_quad_handlers(desk_q, r, alog, bar)
                    futs[pool.submit(run_dsv41_actor, r, h, adir, tdir, ptxt, api_cfg, codex_bin, t_lim)] = r
                for fut in as_completed(futs):
                    actors[futs[fut]] = fut.result()
        finally:
            grade_res, _pstate, ver_cnt = desk_q.stop_and_grade()
    else:
        raise ValueError(suite)

    awareness = analyze_race_awareness(cond_dir, roles)
    rep = {
        "task_id": tid,
        "category": entry["category"],
        "suite": suite,
        "agents": len(roles),
        "upstream_model": api_cfg.get("model", "deepseek-flash"),
        "valid_model_run": all(a["status"] in {"done", "timeout"} for a in actors.values()),
        "joint_pass": bool(grade_res.get("joint_pass")),
        "gui_action_calls": sum(a["gui_action_calls"] for a in actors.values()),
        "gui_observation_calls": sum(a["gui_observation_calls"] for a in actors.values()),
        "cli_calls": sum(a["cli_calls"] for a in actors.values()),
        "distinct_project_versions": ver_cnt,
        "race_awareness": awareness,
        "actors": actors,
        "grade": grade_res,
        "wall_seconds": round(time.monotonic() - t0, 2),
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--api-json", type=Path, required=True)
    parser.add_argument("--codex-bin", type=Path, default=DEFAULT_CODEX_BINARY)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--tasks", nargs="*", default=[r["id"] for r in EVAL_MATRIX_8])
    args = parser.parse_args(argv)
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = [r for r in EVAL_MATRIX_8 if r["id"] in set(args.tasks)]
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fmap = {pool.submit(run_dsv41_case, row, out_dir, args.code_root.resolve(), api_cfg, args.codex_bin.resolve()): row["id"] for row in selected}
        for fut in as_completed(fmap):
            tid = fmap[fut]
            rep = fut.result()
            results[tid] = rep
            write_json(out_dir / "live-progress.json", {k: {"joint_pass": v["joint_pass"], "race_aware": v["race_awareness"]["autonomous_race_aware"], "ipc": v["race_awareness"]["spontaneous_ipc_or_locking"], "wall_s": v["wall_seconds"]} for k, v in sorted(results.items())})
            print(f"DONE {tid}: joint={rep['joint_pass']} aware={rep['race_awareness']['autonomous_race_aware']} ipc={rep['race_awareness']['spontaneous_ipc_or_locking']} gui={rep['gui_action_calls']}+{rep['gui_observation_calls']} cli={rep['cli_calls']} wall={rep['wall_seconds']}s", flush=True)
    write_json(out_dir / "SUMMARY.json", {"upstream_model": api_cfg.get("model", "deepseek-flash"), "results": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
