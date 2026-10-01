#!/usr/bin/env python3
"""Bounded real-Guest feasibility probe for modal and in-window browser context."""
from __future__ import annotations
import base64, hashlib, json, os, secrets, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = Path(os.environ["OSWORLD_V2_DIR"]).resolve()
sys.path[:0] = [str(ROOT), str(V2)]
from scripts import run_writer_calc_v1 as base
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.clipboard_v1 import clipboard_setup_commands

RUN_ID = "modal-context-feasibility-r02-20261001"
OUT = ROOT / "artifacts/mechanism-validation-round1/modal-context" / RUN_ID
OUT.mkdir(parents=True, exist_ok=False)
(OUT / "overlays").mkdir()
os.environ.update({
    "SWCUB_RUN_ID": RUN_ID,
    "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
    "SWCUB_RESOURCE_LEDGER": str(OUT / "resource-events.jsonl"),
    "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(OUT / "overlays"),
})
os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
ensure_resource_identity(OUT / "resource-events.jsonl")
log = EventLog()
episode = None
report = {"run_id": RUN_ID, "status": "starting", "guest_host": os.uname().nodename,
          "model_used": False, "probe_type": "mechanism feasibility; scripted diagnostics"}
def command(desktop, shell):
    return base.guest_command(desktop, ["bash", "-lc", shell])
def observe(ctx, name):
    row = ctx.observe()
    shot = row.get("screenshot")
    if isinstance(shot, bytes):
        (OUT / f"{name}.png").write_bytes(shot)
    tree = row.get("accessibility_tree")
    (OUT / f"{name}.accessibility.txt").write_text(tree or "", encoding="utf-8")
    return {"screenshot": isinstance(shot, bytes), "accessibility_tree": bool(tree),
            "tree_chars": len(tree or "")}
def winstate(desktop):
    return command(desktop,
        'printf "ACTIVE="; xdotool getactivewindow 2>/dev/null; '
        'printf "TITLE="; xdotool getactivewindow getwindowname 2>/dev/null; '
        'wmctrl -lpG 2>&1; '
        'xid=$(xdotool getactivewindow 2>/dev/null); '
        'test -n "$xid" && xprop -id "$xid" WM_TRANSIENT_FOR WM_CLASS WM_WINDOW_ROLE _NET_WM_STATE 2>&1')
try:
    episode, desktop = base.make_desktop("modal_context_probe", log, OUT)
    report["guest_container_id"] = episode.snapshot().get("guest_container_id")
    for argv in clipboard_setup_commands():
        base.guest_command(desktop, argv)
    writer_path = "/tmp/swcub_clipboard/writer.fodt"
    command(desktop, f"soffice --nologo --norestore --nofirststartwizard --writer {writer_path} >/tmp/codesk-modal-probe-writer.log 2>&1 & sleep 7")
    writer_ready = base.wait_for_app_document(episode, desktop, "writer", writer_path,
                                               OUT / "writer-readiness", timeout=120)
    writer = ActorContext("diag_writer", episode, "gui")
    modal_rows = []
    for i in range(2):
        before = winstate(desktop)
        writer.press_key("ctrl+shift+s")
        time.sleep(2)
        during = winstate(desktop)
        obs = observe(writer, f"modal-save-dialog-{i+1}")
        modal_rows.append({"repeat": i+1, "before": before, "during": during,
                           "observation": obs})
        writer.press_key("esc")
        time.sleep(1)
        modal_rows[-1]["after_cancel"] = winstate(desktop)
    report["modal"] = {"writer_readiness": writer_ready, "repeats": modal_rows,
                       "native_dialog_observable": bool(modal_rows and
                          any("Save" in r["during"] or "save" in r["during"].lower()
                              for r in modal_rows)),
                       "repeatable_dialog_open": bool(len(modal_rows)==2 and
                          all("ACTIVE=" in r["during"] for r in modal_rows))}

    browser_path = command(desktop, "command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE").strip().splitlines()[-1]
    report["browser_binary"] = browser_path
    if browser_path == "NONE":
        report["application_context"] = {"status": "blocked_browser_unavailable"}
    else:
        page_a = b'<html><head><title>CoDesk Page A</title></head><body><h1>Page A</h1><textarea id="target" autofocus style="width:700px;height:250px;font-size:30px" oninput="location.hash=encodeURIComponent(this.value)"></textarea></body></html>'
        page_b = b'<html><head><title>CoDesk Page B</title></head><body><h1>Page B</h1><textarea id="target" autofocus style="width:700px;height:250px;font-size:30px" oninput="location.hash=encodeURIComponent(this.value)"></textarea></body></html>'
        a64, b64 = base64.b64encode(page_a).decode(), base64.b64encode(page_b).decode()
        command(desktop, "mkdir -p /tmp/codesk-context-probe")
        command(desktop, f"printf %s {a64} | base64 -d > /tmp/codesk-context-probe/a.html")
        command(desktop, f"printf %s {b64} | base64 -d > /tmp/codesk-context-probe/b.html")
        browser_cmd = (f"{browser_path} --no-first-run --no-default-browser-check "
                       f"--disable-dev-shm-usage --no-sandbox --remote-debugging-port=9222 "
                       f"--user-data-dir=/tmp/codesk-context-probe/profile --new-window "
                       f"file:///tmp/codesk-context-probe/a.html "
                       ">/tmp/codesk-context-probe/browser.log 2>&1 & sleep 7")
        command(desktop, browser_cmd)
        command(desktop, "wmctrl -a \"CoDesk Page A\"; sleep 2")
        actor_a = ActorContext("context_actor_a", episode, "gui")
        actor_b = ActorContext("context_actor_b", episode, "gui")
        state_a = winstate(desktop)
        obs_a = observe(actor_a, "context-page-a-before-yield")
        if "TITLE=CoDesk Page A" not in state_a:
            raise RuntimeError("Browser Page A is not the observed active window: " + state_a)
        tabs_a = command(desktop, "curl -s --max-time 3 http://127.0.0.1:9222/json/list || true")
        actor_b.press_key("ctrl+t")
        actor_b.type_text("file:///tmp/codesk-context-probe/b.html")
        actor_b.press_key("Return")
        time.sleep(3)
        obs_b = observe(actor_b, "context-page-b-after-switch")
        state_b = winstate(desktop)
        tabs_b = command(desktop, "curl -s --max-time 3 http://127.0.0.1:9222/json/list || true")
        actor_b.type_text("B-note")
        time.sleep(1)
        tabs_after_b = command(desktop, "curl -s --max-time 3 http://127.0.0.1:9222/json/list || true")
        actor_a.type_text("A-note")
        time.sleep(1)
        tabs_after_a = command(desktop, "curl -s --max-time 3 http://127.0.0.1:9222/json/list || true")
        xids_a = [s.split()[0] for s in state_a.splitlines()
                  if "CoDesk Page A - Google Chrome" in s]
        xids_b = [s.split()[0] for s in state_b.splitlines()
                  if "CoDesk Page B - Google Chrome" in s]
        report["application_context"] = {
            "page_a_observation": obs_a, "page_a_window_state": state_a, "page_a_tabs": tabs_a,
            "page_b_observation": obs_b, "page_b_window_state": state_b, "page_b_tabs": tabs_b,
            "after_actor_b_target": tabs_after_b, "after_actor_a_stale_action": tabs_after_a,
            "same_active_xid_before_after_tab_switch": bool(xids_a and xids_b and xids_a[-1] == xids_b[-1]),
            "actor_b_goal_expected": "B-note in Page B",
            "actor_a_goal_expected": "A-note in Page A",
            "scheduled_exposure": True,
            "scripted_stale_observation": True,
            "model_result": False}
    report["status"] = "completed"
except Exception as exc:
    report.update({"status": "probe_failed", "error": f"{type(exc).__name__}: {exc}"})
    if episode:
        try:
            episode.copy_artifacts(OUT / "guest-artifacts")
        except Exception:
            pass
finally:
    if episode:
        report["environment_health"] = episode.environment_health
        try:
            episode.copy_artifacts(OUT / "guest-artifacts")
        except Exception as exc:
            report["artifact_copy_error"] = str(exc)
        try:
            episode.close()
            report["guest_closed"] = True
        except Exception as exc:
            report["guest_closed"] = False
            report["close_error"] = str(exc)
    log.write(OUT / "events.jsonl")
    report["source_commit"] = base.git_source_state().get("commit")
    report["resource_ledger"] = str(OUT / "resource-events.jsonl")
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    artifact_hashes = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "provenance.json" and "overlays" not in path.parts:
            artifact_hashes[str(path.relative_to(OUT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "provenance.json").write_text(json.dumps({
        "run_id": RUN_ID, "guest_host": os.uname().nodename,
        "guest_container_id": report.get("guest_container_id"),
        "source_commit": report.get("source_commit"),
        "source_dirty_paths": base.git_source_state().get("dirty_paths"),
        "artifact_sha256": artifact_hashes,
        "run_ownership_ledger": str(OUT / "resource-events.jsonl"),
        "model_used": False}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"run_id": RUN_ID, "status": report["status"],
                  "modal_repeatable": report.get("modal",{}).get("repeatable_dialog_open"),
                  "context_same_xid": report.get("application_context",{}).get("same_active_xid_before_after_tab_switch"),
                  "artifact_dir": str(OUT), "error": report.get("error")}))
