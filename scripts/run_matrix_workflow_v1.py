#!/usr/bin/env python3
"""Single-worker scripted Guest runner for the five MINIMAL matrix workflows.

No model fallback is present. Every GUI action is submitted through ActorContext.
Hidden state collection and evaluator calls remain runner-side.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_writer_calc_v1 as base
from swcub.clipboard_observer import GuestCommandClipboardSampler, install_guest_probe
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks import matrix_workflows_v1 as tasks


WRITER_PATHS = {
    "F-N1": {"doc-a": "/tmp/codesk_fn1/doc-a.fodt",
             "doc-b": "/tmp/codesk_fn1/doc-b.fodt"},
    "C-N1": {"writer": "/tmp/codesk_cn1/writer.fodt"},
    "S-N1": {"writer": "/tmp/codesk_sn1/writer.fodt"},
    "U-N1": {"writer": "/tmp/codesk_un1/writer.fodt"},
}
BROWSER_URLS = {"C-N1": "http://127.0.0.1:8769/workspace",
                "A-N1": "http://127.0.0.1:8770/workspace"}
STATE_PATHS = {"C-N1": "/tmp/codesk_cn1/state.json",
               "A-N1": "/tmp/codesk_an1/state.json"}
EVENT_PATHS = {"A-N1": "/tmp/codesk_an1/events.jsonl"}


def guest(ep: Any, desk: Any, argv: list[str], timeout: int = 45) -> str:
    return base.guest_command(desk, argv, timeout=timeout)


def active_window(ep: Any, desk: Any) -> dict[str, str]:
    raw = guest(ep, desk, ["bash", "-lc",
        'x=$(xdotool getactivewindow); printf "%s\\n" "$x"; xdotool getwindowname "$x"'])
    rows = raw.splitlines()
    return {"xid": rows[0].strip() if rows else "",
            "title": rows[1].strip() if len(rows) > 1 else ""}


def visible_windows(ep: Any, desk: Any) -> list[dict[str, str]]:
    raw = guest(ep, desk, ["bash", "-lc", "wmctrl -lpG"])
    result = []
    for line in raw.splitlines():
        parts = line.split(None, 7)
        if len(parts) == 8:
            result.append({"xid": parts[0], "title": parts[7]})
    return result


def write_fixtures(ep: Any, desk: Any, task_id: str) -> None:
    pieces = ["from pathlib import Path", "import base64"]
    for path, payload in sorted(tasks.fixture_files(task_id).items()):
        pieces.append(f"p=Path({path!r}); p.parent.mkdir(parents=True,exist_ok=True); "
                      f"p.write_bytes(base64.b64decode({base64.b64encode(payload).decode()!r}))")
    ep.cli_action("task_setup", "python3 -c " + shlex.quote("; ".join(pieces)))


def launch_writer(ep: Any, desk: Any, task_id: str, doc_key: str, out: Path) -> dict[str, Any]:
    path = WRITER_PATHS[task_id][doc_key]
    ep.cli_action("task_setup", "bash -lc " + shlex.quote(
        f"soffice --nologo --norestore --nofirststartwizard --writer {shlex.quote(path)} "
        f">/tmp/codesk-matrix-writer.log 2>&1 & sleep 5"))
    ready = base.wait_for_app_document(ep, desk, "writer", path,
                                       out / f"readiness-{doc_key}", timeout=90)
    return {"path": path, "ready": ready}


def launch_browser(ep: Any, desk: Any, task_id: str, out: Path) -> dict[str, Any]:
    server = ("/tmp/codesk_cn1/server.py" if task_id == "C-N1"
              else "/tmp/codesk_an1/server.py")
    url = BROWSER_URLS[task_id]
    ep.cli_action("task_setup", "bash -lc " + shlex.quote(
        f"python3 {server} >/tmp/codesk-matrix-browser-server.log 2>&1 &"))
    health = ""
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        health = guest(ep, desk, ["bash", "-lc",
            f"curl -fsS {url.rsplit('/',1)[0]}/health || true"])
        # Local app serves health on its port root.
        if '"ok": true' in health or '"ok":true' in health:
            break
        time.sleep(.3)
    if '"ok"' not in health:
        raise RuntimeError(f"local Browser fixture health failed: {health!r}")
    ep.cli_action("task_setup", "bash -lc " + shlex.quote(
        f"chromium --no-sandbox --new-window {shlex.quote(url)} "
        ">/tmp/codesk-matrix-chromium.log 2>&1 & sleep 5"))
    ep.refresh_observation(source="task_setup")
    window = active_window(ep, desk)
    return {"url": url, "health": health, "active_window": window}


def read_json(ep: Any, desk: Any, path: str) -> dict[str, Any]:
    return json.loads(guest(ep, desk, ["cat", path]))


def read_text(ep: Any, desk: Any, path: str) -> str:
    return guest(ep, desk, ["cat", path])


def writer_snapshot(ep: Any, desk: Any, path: str) -> dict[str, Any]:
    return tasks.parse_writer(read_text(ep, desk, path))


def observe(ctx: ActorContext, out: Path, label: str) -> dict[str, Any]:
    obs = ctx.observe()
    shot = obs.get("screenshot")
    saved = None
    if isinstance(shot, bytes) and shot:
        target = out / "screenshots" / f"{label}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(shot)
        saved = str(target)
    return {"screenshot_saved": saved, "observation_keys": sorted(obs.keys())}


def log_state(log: EventLog, actor: str, task: str, event: str,
              before: Any, after: Any, details: dict[str, Any]) -> None:
    log.record(actor, "instrumentation", f"{task}.{event}", before, after,
               details={"hidden_from_actor": True, **details})


def clipboard_state(ep: Any, desk: Any) -> dict[str, Any]:
    targets = guest(ep, desk, ["bash", "-lc",
        "timeout 2 xclip -selection clipboard -o -t TARGETS 2>/dev/null || true"], timeout=8)
    payload = guest(ep, desk, ["bash", "-lc",
        "timeout 2 xclip -selection clipboard -o 2>/dev/null | sha256sum | cut -d' ' -f1 || true"], timeout=8)
    return {"targets": sorted(set(targets.split())), "payload_sha256": payload.strip().splitlines()[-1]
            if payload.strip() else "", "read_only": True}


def select_writer_line(ctx: ActorContext, *, line: int) -> None:
    ctx.press_key("ctrl+home")
    for _ in range(line):
        ctx.press_key("down")
    ctx.press_key("home")
    ctx.press_key("shift+end")


def writer_replace(ctx: ActorContext, text: str) -> None:
    ctx.press_key("ctrl+home")
    ctx.press_key("ctrl+a")
    ctx.type_text(text)
    ctx.press_key("ctrl+s")
    time.sleep(.5)


def actor_f(ctx: ActorContext, actor: str, *, turn: int, shared: bool,
            recover: bool, ep: Any, desk: Any, log: EventLog, out: Path) -> None:
    if actor == "actor_a" and turn == 0:
        before = active_window(ep, desk)
        screenshot = observe(ctx, out, "actor-a-observe-doc-a")
        log_state(log, actor, "F-N1", "a_observed_doc_a", before, before,
                  {"screenshot": screenshot, "expected_document": "doc-a.fodt",
                   "window_before": before})
        return
    if actor == "actor_b":
        if shared:
            ctx.press_key("alt+tab")
        before = active_window(ep, desk)
        observe(ctx, out, "actor-b-doc-b")
        if "doc-b.fodt" not in before["title"]:
            raise RuntimeError(f"F-N1 Actor B did not reach doc-B: {before}")
        writer_replace(ctx, "B-FINAL-204")
        after = active_window(ep, desk)
        log_state(log, actor, "F-N1", "b_edited_doc_b", before, after,
                  {"goal": "B-FINAL-204", "window_before": before,
                   "window_after": after})
        return
    if actor == "actor_a" and turn == 1:
        before = active_window(ep, desk)
        if shared and recover:
            ctx.press_key("alt+tab")
            observe(ctx, out, "actor-a-recovery-doc-a")
        writer_replace(ctx, "A-FINAL-731")
        after = active_window(ep, desk)
        log_state(log, actor, "F-N1", "a_resumed_edit", before, after,
                  {"recovery": recover, "expected_document": "doc-a.fodt",
                   "window_before": before, "window_after": after})
        return
    if actor == "actor_a" and not shared:
        writer_replace(ctx, "A-FINAL-731")
        return
    raise RuntimeError(f"unexpected F-N1 turn actor={actor}, turn={turn}")


def browser_copy_table(ctx: ActorContext) -> None:
    ctx.press_key("ctrl+home")
    # Select the rendered table with ordinary mouse input; the page layout is fixed.
    ctx.execute_gui_action("pyautogui.moveTo(58, 238); "
                           "pyautogui.dragTo(340, 385, duration=0.5)")
    ctx.press_key("ctrl+c")


def browser_copy_url(ctx: ActorContext) -> None:
    ctx.click(150, 400)
    ctx.press_key("home")
    ctx.press_key("shift+end")
    ctx.press_key("ctrl+c")
    ctx.click(190, 480)
    ctx.press_key("ctrl+v")
    ctx.click(120, 550)


def paste_table_writer(ctx: ActorContext) -> None:
    ctx.press_key("ctrl+home")
    ctx.press_key("down")
    ctx.press_key("home")
    ctx.press_key("shift+end")
    ctx.press_key("ctrl+v")
    ctx.press_key("ctrl+s")
    time.sleep(.6)


def actor_c(ctx: ActorContext, actor: str, *, turn: int, shared: bool,
            recover: bool, ep: Any, desk: Any, log: EventLog, out: Path,
            clipboard: list[dict[str, Any]]) -> None:
    if actor == "actor_a" and turn == 0:
        before = clipboard_state(ep, desk)
        obs = observe(ctx, out, "actor-a-before-rich-copy")
        browser_copy_table(ctx)
        after = clipboard_state(ep, desk)
        clipboard.append({"actor_id": actor, "operation": "copy_rich_table",
                          "before": before, "after": after,
                          "has_html_target": any("html" in t.lower() for t in after["targets"]),
                          "ts_utc": datetime.now(timezone.utc).isoformat()})
        log_state(log, actor, "C-N1", "a_copied_rich_table", before, after,
                  {"observation": obs, "mime_targets": after["targets"]})
        return
    if actor == "actor_b":
        before = clipboard_state(ep, desk)
        observe(ctx, out, "actor-b-copy-url")
        browser_copy_url(ctx)
        after = clipboard_state(ep, desk)
        clipboard.append({"actor_id": actor, "operation": "copy_url", "before": before, "after": after})
        clipboard[-1]["ts_utc"] = datetime.now(timezone.utc).isoformat()
        log_state(log, actor, "C-N1", "b_copied_and_submitted_url", before, after,
                  {"mime_targets": after["targets"]})
        return
    if actor == "actor_a" and turn == 1:
        before = clipboard_state(ep, desk)
        if shared and recover:
            observe(ctx, out, "actor-a-recopy-source")
            browser_copy_table(ctx)
            recopy = clipboard_state(ep, desk)
            clipboard.append({"actor_id": actor, "operation": "copy_rich_table_recovery",
                              "after": recopy,
                              "has_html_target": any("html" in t.lower()
                                                     for t in recopy["targets"]),
                              "ts_utc": datetime.now(timezone.utc).isoformat()})
        ctx.press_key("alt+tab")
        paste_table_writer(ctx)
        after = clipboard_state(ep, desk)
        clipboard.append({"actor_id": actor, "operation": "paste_table",
                          "before": before, "after": after})
        clipboard[-1]["ts_utc"] = datetime.now(timezone.utc).isoformat()
        log_state(log, actor, "C-N1", "a_pasted_table", before, after,
                  {"recovery": recover})
        return
    if actor == "actor_a" and not shared:
        # Solo A has no clipboard competition, but still follows Browser copy -> Writer paste.
        browser_copy_table(ctx)
        rich_state = clipboard_state(ep, desk)
        clipboard.append({"actor_id": actor, "operation": "copy_rich_table_solo",
                          "after": rich_state,
                          "has_html_target": any("html" in t.lower()
                                                 for t in rich_state["targets"])})
        ctx.press_key("alt+tab")
        paste_table_writer(ctx)
        return
    raise RuntimeError(f"unexpected C-N1 turn actor={actor}, turn={turn}")


def actor_a_route(ctx: ActorContext, route: str, value: str, *, submit: bool) -> None:
    ctx.click(90 if route == "route-a" else 230, 180)
    ctx.click(180, 300)
    ctx.type_text(value)
    if submit:
        ctx.click(150, 370)


def actor_an(ctx: ActorContext, actor: str, *, turn: int, shared: bool,
             recover: bool, ep: Any, desk: Any, log: EventLog, out: Path) -> None:
    if actor == "actor_a" and turn == 0:
        before = read_json(ep, desk, STATE_PATHS["A-N1"])["active_route"]
        window_before = active_window(ep, desk)
        obs = observe(ctx, out, "actor-a-route-a-observe")
        actor_a_route(ctx, "route-a", "A-READY-531", submit=False)
        after = read_json(ep, desk, STATE_PATHS["A-N1"])["active_route"]
        log_state(log, actor, "A-N1", "a_entered_draft", before, after,
                  {"screenshot": obs, "draft_not_committed": True,
                   "window_before": window_before, "window_after": active_window(ep, desk)})
        return
    if actor == "actor_b":
        before = read_json(ep, desk, STATE_PATHS["A-N1"])["active_route"]
        window_before = active_window(ep, desk)
        observe(ctx, out, "actor-b-route-b")
        actor_a_route(ctx, "route-b", "B-APPROVE-824", submit=True)
        after = read_json(ep, desk, STATE_PATHS["A-N1"])
        log_state(log, actor, "A-N1", "b_navigated_and_submitted", before, after,
                  {"expected_route": "route-b", "window_before": window_before,
                   "window_after": active_window(ep, desk)})
        return
    if actor == "actor_a" and turn == 1:
        before = read_json(ep, desk, STATE_PATHS["A-N1"])["active_route"]
        observe(ctx, out, "actor-a-route-resume")
        if recover:
            actor_a_route(ctx, "route-a", "A-READY-531", submit=True)
        else:
            ctx.click(220, 405)
        after = read_json(ep, desk, STATE_PATHS["A-N1"])
        log_state(log, actor, "A-N1", "a_resumed_submit", before, after,
                  {"recovery": recover, "observed_route_before": before,
                   "server_state_after": after,
                   "window_after_action": active_window(ep, desk)})
        return
    if actor == "actor_a" and not shared:
        actor_a_route(ctx, "route-a", "A-READY-531", submit=True)
        return
    if actor == "actor_b" and not shared:
        actor_a_route(ctx, "route-b", "B-APPROVE-824", submit=True)
        return
    raise RuntimeError(f"unexpected A-N1 turn actor={actor}, turn={turn}")


def uno_selection(ep: Any, desk: Any) -> str:
    script = ("import uno; c=uno.getComponentContext(); r=c.ServiceManager.createInstanceWithContext"
              "('com.sun.star.bridge.UnoUrlResolver',c); x=r.resolve("
              "'uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); "
              "d=x.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',x); "
              "print(d.getCurrentComponent().getCurrentSelection().getString())")
    return guest(ep, desk, ["python3", "-c", script], timeout=15).strip()


def select_a(ctx: ActorContext) -> None:
    ctx.press_key("ctrl+home")
    for _ in range(len("ALPHA")):
        ctx.press_key("shift+right")


def select_b(ctx: ActorContext) -> None:
    ctx.press_key("ctrl+home")
    for _ in range(len("ALPHA target | ")):
        ctx.press_key("right")
    for _ in range(len("BETA")):
        ctx.press_key("shift+right")


def actor_s(ctx: ActorContext, actor: str, *, turn: int, shared: bool,
            recover: bool, ep: Any, desk: Any, log: EventLog, out: Path) -> None:
    if actor == "actor_a" and turn == 0:
        observe(ctx, out, "actor-a-selected-alpha")
        before = uno_selection(ep, desk)
        select_a(ctx)
        after = uno_selection(ep, desk)
        log_state(log, actor, "S-N1", "a_selected_range", before, after,
                  {"x11": active_window(ep, desk),
                   "selection_before": before, "selection_after": after})
        return
    if actor == "actor_b":
        observe(ctx, out, "actor-b-selected-beta")
        before = uno_selection(ep, desk)
        select_b(ctx)
        ctx.press_key("ctrl+b")
        after = uno_selection(ep, desk)
        log_state(log, actor, "S-N1", "b_selected_and_bolded", before, after,
                  {"x11": active_window(ep, desk),
                   "selection_before": before, "selection_after": after})
        return
    if actor == "actor_a" and turn == 1:
        before = uno_selection(ep, desk)
        observe(ctx, out, "actor-a-selection-resume")
        if recover:
            select_a(ctx)
        ctx.press_key("ctrl+b")
        ctx.press_key("ctrl+s")
        after = uno_selection(ep, desk)
        log_state(log, actor, "S-N1", "a_applied_bold", before, after,
                  {"recovery": recover, "x11": active_window(ep, desk),
                   "selection_before": before, "selection_after": after})
        return
    if actor == "actor_a" and not shared:
        select_a(ctx); ctx.press_key("ctrl+b"); ctx.press_key("ctrl+s")
        return
    if actor == "actor_b" and not shared:
        select_b(ctx); ctx.press_key("ctrl+b"); ctx.press_key("ctrl+s")
        return
    raise RuntimeError(f"unexpected S-N1 turn actor={actor}, turn={turn}")


def actor_u(ctx: ActorContext, actor: str, *, turn: int, shared: bool,
            recover: bool, ep: Any, desk: Any, log: EventLog, out: Path) -> None:
    path = WRITER_PATHS["U-N1"]["writer"]
    if actor == "actor_a" and turn == 0:
        observe(ctx, out, "actor-a-before-temporary-edit")
        before = read_text(ep, desk, path)
        window_before = active_window(ep, desk)
        select_writer_line(ctx, line=0); ctx.type_text("A-LINE: temporary"); ctx.press_key("ctrl+s")
        after = read_text(ep, desk, path)
        log_state(log, actor, "U-N1", "a_temporary_edit", before, after,
                  {"history_order": 1,
                   "window_before": window_before, "window_after": active_window(ep, desk),
                   "before_paragraphs": tasks.parse_writer(before)["paragraphs"],
                   "after_paragraphs": tasks.parse_writer(after)["paragraphs"]})
        return
    if actor == "actor_b":
        before = read_text(ep, desk, path)
        window_before = active_window(ep, desk)
        observe(ctx, out, "actor-b-before-line-edit")
        select_writer_line(ctx, line=1); ctx.type_text("B-LINE: final"); ctx.press_key("ctrl+s")
        after = read_text(ep, desk, path)
        log_state(log, actor, "U-N1", "b_document_edit", before, after,
                  {"history_order": 2,
                   "window_before": window_before, "window_after": active_window(ep, desk),
                   "before_paragraphs": tasks.parse_writer(before)["paragraphs"],
                   "after_paragraphs": tasks.parse_writer(after)["paragraphs"]})
        return
    if actor == "actor_a" and turn == 1:
        before = read_text(ep, desk, path)
        window_before = active_window(ep, desk)
        observe(ctx, out, "actor-a-before-undo")
        ctx.press_key("ctrl+z"); ctx.press_key("ctrl+s"); time.sleep(.5)
        after = read_text(ep, desk, path)
        log_state(log, actor, "U-N1", "a_undo", before, after,
                  {"recovery": recover, "history_order": 3,
                   "window_before": window_before, "window_after": active_window(ep, desk),
                   "before_paragraphs": tasks.parse_writer(before)["paragraphs"],
                   "after_paragraphs": tasks.parse_writer(after)["paragraphs"]})
        return
    if actor == "actor_a" and turn == 2 and recover:
        before = read_text(ep, desk, path)
        select_writer_line(ctx, line=0)
        ctx.type_text("A-LINE: keep")
        ctx.press_key("ctrl+s")
        after = read_text(ep, desk, path)
        log_state(log, actor, "U-N1", "a_recovery_restore_seed", before, after,
                  {"history_order": 4,
                   "before_paragraphs": tasks.parse_writer(before)["paragraphs"],
                   "after_paragraphs": tasks.parse_writer(after)["paragraphs"]})
        return
    if actor == "actor_a" and not shared:
        select_writer_line(ctx, line=0); ctx.type_text("A-LINE: temporary")
        ctx.press_key("ctrl+s"); ctx.press_key("ctrl+z"); ctx.press_key("ctrl+s")
        return
    if actor == "actor_b" and not shared:
        select_writer_line(ctx, line=1); ctx.type_text("B-LINE: final")
        ctx.press_key("ctrl+s")
        return
    raise RuntimeError(f"unexpected U-N1 turn actor={actor}, turn={turn}")


def setup_binding(task_id: str, binding: str, actor_ids: tuple[str, ...],
                  ep: Any, desk: Any, out: Path) -> dict[str, Any]:
    write_fixtures(ep, desk, task_id)
    opened: dict[str, Any] = {}
    if task_id == "F-N1":
        docs = ("doc-a", "doc-b") if "actor_a" in actor_ids and "actor_b" in actor_ids else (
            "doc-a" if actor_ids == ("actor_a",) else "doc-b",)
        for key in docs:
            opened[key] = launch_writer(ep, desk, task_id, key, out)
        if len(docs) == 2:
            guest(ep, desk, ["bash", "-lc",
                "wmctrl -a doc-a.fodt || wmctrl -a doc-a"], timeout=10)
            opened["window_rows"] = visible_windows(ep, desk)
            titles = [row["title"] for row in opened["window_rows"]]
            xids = [row["xid"] for row in opened["window_rows"]
                    if "doc-a.fodt" in row["title"] or "doc-b.fodt" in row["title"]]
            if not any("doc-a.fodt" in title for title in titles) or not any(
                    "doc-b.fodt" in title for title in titles):
                raise RuntimeError(f"two Writer documents/windows not observed: {titles}")
            if len(xids) != 2 or len(set(xids)) != 2:
                raise RuntimeError(f"F-N1 requires two distinct top-level window IDs: {xids}")
    elif task_id == "C-N1":
        opened["writer"] = launch_writer(ep, desk, task_id, "writer", out)
        opened["browser"] = launch_browser(ep, desk, task_id, out)
        probe, state_path = install_guest_probe(
            lambda argv: guest(ep, desk, argv), ROOT / "scripts/guest_clipboard_probe.py",
            f"{os.environ['SWCUB_RUN_ID']}-{binding}")
        sampler = GuestCommandClipboardSampler(lambda argv: guest(ep, desk, argv),
                                                probe_path=probe, state_path=state_path)
        ep.attach_clipboard_sampler(sampler, required=True)
        ep.clipboard_sampler.sample()
    elif task_id == "A-N1":
        opened["browser"] = launch_browser(ep, desk, task_id, out)
    else:
        opened["writer"] = launch_writer(ep, desk, task_id, "writer", out)
        if task_id == "S-N1":
            script = ("soffice --nologo --norestore --nofirststartwizard "
                      "--accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' "
                      f"--writer {shlex.quote(WRITER_PATHS[task_id]['writer'])} "
                      ">/tmp/codesk-matrix-writer-uno.log 2>&1 & sleep 3")
            ep.cli_action("task_setup", "bash -lc " + shlex.quote(script))
            uno_selection(ep, desk)
    return {"fixture_sha256": tasks.fixture_hash(task_id), "opened": opened,
            "active_window": active_window(ep, desk)}


def state_for(task_id: str, binding: str, ep: Any, desk: Any) -> dict[str, Any]:
    if task_id == "F-N1":
        docs = {}
        for key, path in WRITER_PATHS[task_id].items():
            raw = guest(ep, desk, ["bash", "-lc",
                f"test -f {shlex.quote(path)} && cat {shlex.quote(path)} || true"])
            try:
                docs[key] = tasks.parse_writer(raw)["paragraphs"][0] if raw else ""
            except Exception:
                docs[key] = ""
        return {"documents": docs}
    if task_id == "C-N1":
        writer = tasks.parse_writer_table(read_text(ep, desk, WRITER_PATHS[task_id]["writer"]))
        browser = read_json(ep, desk, STATE_PATHS[task_id])
        return {"writer": writer, "browser": browser}
    if task_id == "A-N1":
        return {"routes": read_json(ep, desk, STATE_PATHS[task_id])["routes"],
                "active_route": read_json(ep, desk, STATE_PATHS[task_id])["active_route"],
                "route_events": read_text(ep, desk, EVENT_PATHS[task_id])}
    if task_id == "S-N1":
        path = WRITER_PATHS[task_id]["writer"]
        parsed = tasks.parse_writer(read_text(ep, desk, path))
        text = parsed["paragraphs"][0] if parsed["paragraphs"] else ""
        bold = [span for para in parsed["spans"] for span in para if span["bold"]]
        return {"writer": {"document_text": text, "bold_spans": bold,
                           "guard": parsed["paragraphs"][-1] if parsed["paragraphs"] else ""}}
    path = WRITER_PATHS["U-N1"]["writer"]
    return {"writer": tasks.parse_writer(read_text(ep, desk, path))}


def run_one(args: argparse.Namespace) -> int:
    task_id = args.task
    out = args.artifact_parent.expanduser().resolve() / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "overlays").mkdir()
    ledger = out / "resource-events.jsonl"
    owner = secrets.token_hex(32)
    os.environ.update({"SWCUB_RUN_ID": args.run_id, "SWCUB_OWNER_TOKEN": owner,
                       "SWCUB_RESOURCE_LEDGER": str(ledger),
                       "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger)
    log = EventLog()
    episodes: dict[str, Any] = {}
    desktops: dict[str, Any] = {}
    contexts: dict[str, dict[str, ActorContext]] = {}
    report: dict[str, Any] = {
        "run_id": args.run_id, "task_id": task_id,
        "task_version": "0.1.0-prototype", "condition": args.condition,
        "actor_implementation": "scripted_gui", "model_used": False,
        "evidence_level": "scripted_real_guest_episode",
        "guest_host": os.uname().nodename, "status": "starting",
        "manifest": tasks.task_manifest(task_id),
        "scheduled_exposure": args.condition == "ma_sd",
        "recovery_control": args.recovery, "setup": {}, "events": [],
        "actor_goal_success": {}, "reset_success": False}
    phase = "guest_startup"
    start = time.monotonic()
    try:
        if args.condition.startswith("solo"):
            actor = "actor_a" if args.condition == "solo_a" else "actor_b"
            plan = [(actor, (actor,))]
        elif args.condition == "ma_id":
            plan = [("actor_a", ("actor_a",)), ("actor_b", ("actor_b",))]
        else:
            plan = [("shared", ("actor_a", "actor_b"))]
        for binding, actor_ids in plan:
            ep, desk = base.make_desktop(binding, log, out)
            episodes[binding], desktops[binding] = ep, desk
            phase = "task_setup"
            report["setup"][binding] = setup_binding(task_id, binding, actor_ids,
                                                      ep, desk, out / binding)
            contexts[binding] = {actor: ActorContext(actor, ep, "gui") for actor in actor_ids}
        bindings = {actor: binding for binding, actors in plan for actor in actors}
        report["bindings"] = bindings
        exposure_events: list[dict[str, Any]] = []
        clipboard_events: list[dict[str, Any]] = []
        phase = "actor_execution"
        if args.condition.startswith("solo"):
            actor = plan[0][1][0]
            binding = bindings[actor]
            ctx = contexts[binding][actor]
            if task_id == "F-N1":
                actor_f(ctx, actor, turn=-1, shared=False, recover=False,
                        ep=episodes[binding], desk=desktops[binding], log=log, out=out)
            elif task_id == "C-N1":
                if actor == "actor_a":
                    actor_c(ctx, actor, turn=-1, shared=False, recover=False,
                            ep=episodes[binding], desk=desktops[binding], log=log,
                            out=out, clipboard=clipboard_events)
                else:
                    actor_c(ctx, actor, turn=0, shared=False, recover=False,
                            ep=episodes[binding], desk=desktops[binding], log=log,
                            out=out, clipboard=clipboard_events)
            elif task_id == "A-N1":
                actor_an(ctx, actor, turn=-1, shared=False, recover=False,
                         ep=episodes[binding], desk=desktops[binding], log=log, out=out)
            elif task_id == "S-N1":
                actor_s(ctx, actor, turn=-1, shared=False, recover=False,
                        ep=episodes[binding], desk=desktops[binding], log=log, out=out)
            else:
                actor_u(ctx, actor, turn=-1, shared=False, recover=False,
                        ep=episodes[binding], desk=desktops[binding], log=log, out=out)
        else:
            # Each action boundary completes before the next Actor is resumed.
            if task_id == "F-N1":
                actor_f(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out)
                actor_f(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_b"]], desk=desktops[bindings["actor_b"]],
                        log=log, out=out)
                actor_f(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=1,
                        shared=args.condition == "ma_sd", recover=args.recovery,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out)
                if args.condition == "ma_sd" and args.recovery:
                    actor_f(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=0,
                            shared=True, recover=True, ep=episodes["shared"], desk=desktops["shared"],
                            log=log, out=out)
            elif task_id == "C-N1":
                actor_c(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out, clipboard=clipboard_events)
                actor_c(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_b"]], desk=desktops[bindings["actor_b"]],
                        log=log, out=out, clipboard=clipboard_events)
                actor_c(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=1,
                        shared=args.condition == "ma_sd", recover=args.recovery,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out, clipboard=clipboard_events)
            elif task_id == "A-N1":
                actor_an(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=0,
                         shared=args.condition == "ma_sd", recover=False,
                         ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                         log=log, out=out)
                actor_an(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=0,
                         shared=args.condition == "ma_sd", recover=False,
                         ep=episodes[bindings["actor_b"]], desk=desktops[bindings["actor_b"]],
                         log=log, out=out)
                actor_an(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=1,
                         shared=args.condition == "ma_sd", recover=args.recovery,
                         ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                         log=log, out=out)
            elif task_id == "S-N1":
                actor_s(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out)
                actor_s(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_b"]], desk=desktops[bindings["actor_b"]],
                        log=log, out=out)
                actor_s(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=1,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out)
                if args.condition == "ma_sd" and args.recovery:
                    actor_s(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=1,
                            shared=True, recover=True, ep=episodes["shared"],
                            desk=desktops["shared"], log=log, out=out)
                    actor_s(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=0,
                            shared=True, recover=True, ep=episodes["shared"],
                            desk=desktops["shared"], log=log, out=out)
            else:
                actor_u(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out)
                actor_u(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=0,
                        shared=args.condition == "ma_sd", recover=False,
                        ep=episodes[bindings["actor_b"]], desk=desktops[bindings["actor_b"]],
                        log=log, out=out)
                actor_u(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=1,
                        shared=args.condition == "ma_sd", recover=args.recovery,
                        ep=episodes[bindings["actor_a"]], desk=desktops[bindings["actor_a"]],
                        log=log, out=out)
                if args.condition == "ma_sd" and args.recovery:
                    actor_u(contexts[bindings["actor_a"]]["actor_a"], "actor_a", turn=2,
                            shared=True, recover=True, ep=episodes["shared"],
                            desk=desktops["shared"], log=log, out=out)
                    actor_u(contexts[bindings["actor_b"]]["actor_b"], "actor_b", turn=2,
                            shared=True, recover=True, ep=episodes["shared"],
                            desk=desktops["shared"], log=log, out=out)
        phase = "evaluator"
        evaluations = {}
        binding_actors: dict[str, list[str]] = {}
        for actor, binding in bindings.items():
            binding_actors.setdefault(binding, []).append(actor)
        binding_evaluations = {}
        for binding, actors_in_binding in binding_actors.items():
            actual = state_for(task_id, binding, episodes[binding], desktops[binding])
            scored = tasks.evaluate(task_id, actual, tuple(actors_in_binding))
            binding_evaluations[binding] = scored
            for actor in actors_in_binding:
                evaluations[actor] = scored
            report.setdefault("final_state", {})[binding] = actual
        report["per_actor_evaluation"] = evaluations
        report["actor_goal_success"] = {
            actor: evaluations[actor]["actor_goal_success"][actor] for actor in bindings}
        report["actor_integrity"] = {
            actor: evaluations[actor]["non_target_integrity"][actor] for actor in bindings}
        report["joint_success"] = (all(report["actor_goal_success"].values())
                                   and all(report["actor_integrity"].values()))
        report["clipboard_events"] = clipboard_events
        event_rows = [asdict(event) for event in log.events]
        action_rows = [row for row in event_rows if row.get("kind") == "instrumentation"]
        by_action = {row["action"].split(".")[-1]: row for row in action_rows}
        all_actions: dict[str, list[dict[str, Any]]] = {}
        for row in action_rows:
            all_actions.setdefault(row["action"].split(".")[-1], []).append(row)
        actual_exposure = False
        exposure_evidence: dict[str, Any] = {}
        if task_id == "F-N1":
            observed = by_action.get("a_observed_doc_a", {}).get("details", {})
            b_edit = by_action.get("b_edited_doc_b", {}).get("details", {})
            resume = by_action.get("a_resumed_edit", {}).get("details", {})
            a_window = observed.get("window_before", {})
            before_resume = resume.get("window_before", {})
            actual_exposure = (args.condition == "ma_sd"
                and "doc-a.fodt" in a_window.get("title", "")
                and "doc-b.fodt" in str(b_edit.get("window_after", {}))
                and "doc-b.fodt" in str(before_resume))
            if args.recovery:
                actual_exposure = (actual_exposure and
                    "doc-a.fodt" in str(resume.get("window_after", {})))
            exposure_evidence = {"a_observation": observed, "b_edit": b_edit,
                                 "a_resume": resume}
        elif task_id == "C-N1":
            a_copy = next((r for r in clipboard_events if r.get("operation") in
                           {"copy_rich_table", "copy_rich_table_solo"}), {})
            b_copy = next((r for r in clipboard_events if r.get("operation") == "copy_url"), {})
            a_paste = next((r for r in clipboard_events if r.get("operation") == "paste_table"), {})
            a_digest = a_copy.get("after", {}).get("payload_sha256", "")
            b_digest = b_copy.get("after", {}).get("payload_sha256", "")
            resume_digest = a_paste.get("before", {}).get("payload_sha256", "")
            actual_exposure = (args.condition == "ma_sd" and bool(a_digest)
                and bool(b_digest) and a_digest != b_digest
                and bool(a_copy.get("has_html_target"))
                and resume_digest in {a_digest, b_digest})
            exposure_evidence = {"a_copy": a_copy, "b_copy": b_copy,
                                 "a_recopy": next((r for r in clipboard_events
                                     if r.get("operation") == "copy_rich_table_recovery"), None),
                                 "a_resume_paste": a_paste}
        elif task_id == "A-N1":
            routes = report.get("final_state", {}).get("shared", {}).get("route_events", "")
            route_rows = []
            for line in routes.splitlines():
                try:
                    route_rows.append(json.loads(line))
                except Exception:
                    continue
            route_b_event = any(row.get("kind") == "route_changed"
                                and row.get("route") == "route-b" for row in route_rows)
            a_resume = by_action.get("a_resumed_submit", {}).get("details", {})
            a_observe = by_action.get("a_entered_draft", {}).get("details", {})
            b_navigate = by_action.get("b_navigated_and_submitted", {}).get("details", {})
            window_ids = [a_observe.get("window_before", {}).get("xid"),
                          b_navigate.get("window_after", {}).get("xid"),
                          a_resume.get("window_after_action", {}).get("xid")]
            actual_exposure = args.condition == "ma_sd" and route_b_event and (
                a_resume.get("observed_route_before") == "route-b"
                and bool(window_ids[0]) and len(set(window_ids)) == 1)
            exposure_evidence = {"route_events": route_rows, "a_resume": a_resume,
                                 "window_ids_across_actors": window_ids,
                                 "top_level_window": report.get("setup", {}).get("shared", {})
                                     .get("active_window")}
        elif task_id == "S-N1":
            a_select = by_action.get("a_selected_range", {}).get("details", {})
            b_select = by_action.get("b_selected_and_bolded", {}).get("details", {})
            a_apply_rows = all_actions.get("a_applied_bold", [])
            a_apply = a_apply_rows[0].get("details", {}) if a_apply_rows else {}
            actual_exposure = (args.condition == "ma_sd"
                and a_select.get("selection_after") == "ALPHA"
                and b_select.get("selection_after") == "BETA"
                and a_apply.get("selection_before") == "BETA"
                and a_select.get("x11", {}).get("xid")
                    == b_select.get("x11", {}).get("xid")
                and b_select.get("x11", {}).get("xid")
                    == a_apply.get("x11", {}).get("xid"))
            exposure_evidence = {"a_select": a_select, "b_select": b_select,
                                 "a_resume_stale_action": a_apply,
                                 "a_recovery": [row.get("details", {})
                                     for row in a_apply_rows[1:]]}
        elif task_id == "U-N1":
            a_edit = by_action.get("a_temporary_edit", {}).get("details", {})
            b_edit = by_action.get("b_document_edit", {}).get("details", {})
            undo = by_action.get("a_undo", {}).get("details", {})
            actual_exposure = (args.condition == "ma_sd"
                and a_edit.get("after_paragraphs", [None])[0] == tasks.U_A_TEMP
                and b_edit.get("after_paragraphs", [None, None])[1] == tasks.U_B_FINAL
                and undo.get("after_paragraphs", [None, None])[1] == tasks.U_B_INITIAL
                and a_edit.get("window_after", {}).get("xid")
                    == b_edit.get("window_after", {}).get("xid")
                and b_edit.get("window_after", {}).get("xid")
                    == undo.get("window_before", {}).get("xid"))
            exposure_evidence = {"a_edit": a_edit, "b_edit": b_edit, "a_undo": undo}
        report["instrumentation"] = {
            "scheduled_exposure": args.condition == "ma_sd",
            "actual_exposure": actual_exposure,
            "exposure_evidence": exposure_evidence,
            "events": event_rows}
        report["status"] = "completed"
        phase = "reset"
        originals = list(episodes.items())
        for _, ep in originals:
            ep.copy_artifacts(out / "guest-artifacts" / ep.environment_id)
            ep.close()
        episodes.clear()
        report["reset_checks"] = {}
        for binding, _ in originals:
            ep, desk = base.make_desktop(binding + "_reset", log, out)
            absent = True
            for path in tasks.fixture_files(task_id):
                check = guest(ep, desk, ["bash", "-lc",
                    f"test ! -e {shlex.quote(path)} && echo absent || echo present"])
                absent = absent and "absent" in check
            report["reset_checks"][binding] = {
                "success": absent, "replacement_guest_id": ep.snapshot().get("guest_container_id")}
            ep.close()
        report["reset_success"] = all(row["success"] for row in report["reset_checks"].values())
        if not report["reset_success"]:
            report["status"] = "invalid_environment_reset"
    except Exception as exc:
        report["status"] = "invalid_infrastructure_or_setup" if phase in {
            "guest_startup", "task_setup"} else "execution_or_evaluator_error"
        report["error"] = {"phase": phase, "type": type(exc).__name__, "message": str(exc)}
    finally:
        for binding, ep in list(episodes.items()):
            try:
                ep.copy_artifacts(out / "failure-artifacts" / binding)
            except Exception:
                pass
            try:
                ep.close()
            except Exception:
                pass
        report["wall_seconds"] = round(time.monotonic() - start, 2)
        log.write(out / "events.jsonl")
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["provenance"] = {
            "source_commit": base.git_source_state(),
            "task_fixture_sha256": tasks.fixture_hash(task_id),
            "actor_implementation": "scripted_gui",
            "model_used": False}
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
        (out / "provenance.json").write_text(json.dumps({
            "run_id": identity.run_id, "owner_token_sha256": hashlib.sha256(
                owner.encode()).hexdigest(), "source": base.git_source_state(),
            "task_id": task_id, "task_version": "0.1.0-prototype",
            "fixture_sha256": tasks.fixture_hash(task_id)}, indent=2)+"\n")
    print(json.dumps({"run_id": args.run_id, "task": task_id,
                      "condition": args.condition, "status": report["status"],
                      "actor_goal_success": report.get("actor_goal_success"),
                      "joint_success": report.get("joint_success"),
                      "reset_success": report.get("reset_success"),
                      "error": report.get("error"), "artifacts": str(out)}))
    return 0 if report["status"] == "completed" and report.get("reset_success") else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=tasks.TASKS, required=True)
    parser.add_argument("--condition", choices=("solo_a", "solo_b", "ma_id", "ma_sd"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    parser.add_argument("--recovery", action="store_true")
    return run_one(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
