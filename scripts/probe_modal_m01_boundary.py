#!/usr/bin/env python3
"""Bounded M-01 diagnostic: can a native LO modal block another GUI actor beyond focus?"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_writer_calc_v1 as base
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.prototypes_v1 import generate_modal_instance


def command(desktop, shell):
    return base.guest_command(desktop, ["bash", "-lc", shell])


def x11_snapshot(desktop):
    return command(desktop,
        'printf "ACTIVE="; xdotool getactivewindow 2>/dev/null; '
        'printf "TITLE="; xdotool getactivewindow getwindowname 2>/dev/null; '
        'wmctrl -lpG 2>&1; '
        'xid=$(xdotool getactivewindow 2>/dev/null); '
        'test -n "$xid" && xprop -id "$xid" WM_TRANSIENT_FOR WM_CLASS WM_WINDOW_ROLE _NET_WM_STATE 2>&1')


def capture(episode, desktop, out, label):
    episode.refresh_observation(source="m01_probe")
    observed = episode.observe("m01_probe")
    shot = observed.get("screenshot")
    if isinstance(shot, bytes) and shot:
        (out / f"{label}.png").write_bytes(shot)
    tree = observed.get("accessibility_tree") or ""
    (out / f"{label}.accessibility.txt").write_text(tree)
    state = {"x11": x11_snapshot(desktop), "screenshot": bool(shot), "tree_chars": len(tree)}
    (out / f"{label}.json").write_text(json.dumps(state, indent=2) + "\n")
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    args = parser.parse_args()
    out = args.artifact_parent.resolve() / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "overlays").mkdir()
    ledger = out / "resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID": args.run_id, "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
                       "SWCUB_RESOURCE_LEDGER": str(ledger),
                       "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger)
    manifest = generate_modal_instance(0)
    log = base.EventLog()
    episode = desktop = replacement = None
    start = time.monotonic()
    report = {"run_id": args.run_id, "status": "starting", "model_used": False,
              "probe": "M-01 modal ownership versus focus routing",
              "manifest_sha256": manifest["manifest_sha256"], "guest_host": os.uname().nodename}
    phase = "guest_startup"
    try:
        episode, desktop = base.make_desktop("m01", log, out)
        phase = "setup"
        statements = ["from pathlib import Path", "import base64"]
        for item in manifest["initial_files"]:
            path = item["guest_path"]
            data = item["content_base64"]
            statements.extend((f"Path({path!r}).parent.mkdir(parents=True,exist_ok=True)",
                               f"Path({path!r}).write_bytes(base64.b64decode({data!r}))"))
        episode.cli_action("task_setup", "python3 -c " + shlex.quote("; ".join(statements)))
        calc_path = manifest["actor_goals"]["calc_actor"]["source"]
        writer_path = manifest["actor_goals"]["writer_actor"]["source"]
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(
            f"soffice --nologo --norestore --nofirststartwizard --calc {shlex.quote(calc_path)} >/tmp/codesk-m01-calc.log 2>&1 & sleep 5"))
        report["calc_readiness"] = base.wait_for_app_document(episode, desktop, "calc", calc_path, out / "calc-readiness", timeout=120)
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(
            f"soffice --nologo --norestore --nofirststartwizard --writer {shlex.quote(writer_path)} >/tmp/codesk-m01-writer.log 2>&1 & sleep 5"))
        report["writer_readiness"] = base.wait_for_app_document(episode, desktop, "writer", writer_path, out / "writer-readiness", timeout=120)
        phase = "probe"
        a = ActorContext("writer_actor", episode, "gui")
        b = ActorContext("calc_actor", episode, "gui")
        report["before"] = capture(episode, desktop, out, "before")
        a.press_key("ctrl+shift+s")
        time.sleep(2)
        report["dialog_open"] = capture(episode, desktop, out, "dialog-open")
        modal = (all(marker in report["dialog_open"]["x11"] for marker in (
                     "TITLE=Save", "GtkFileChooserDialog",
                     "_NET_WM_STATE_MODAL", "WM_TRANSIENT_FOR(WINDOW)")))
        if not modal:
            report["status"] = "modal_not_observed"
        else:
            b.press_key("alt+tab")
            time.sleep(1)
            report["b_switch_attempt"] = capture(episode, desktop, out, "b-switch-attempt")
            # B legitimately starts its independent Calc Save As goal.
            b.press_key("ctrl+shift+s")
            time.sleep(2)
            report["b_save_attempt"] = capture(episode, desktop, out, "b-save-attempt")
            b.press_key("alt+tab")
            time.sleep(1)
            report["b_second_switch"] = capture(episode, desktop, out, "b-second-switch")
            # Restore the verified dialog by exact X11 window title for cleanup only.
            command(desktop, "wmctrl -a Save || true")
            a.press_key("esc")
            a.press_key("esc")
            time.sleep(1)
            report["after_cancel"] = capture(episode, desktop, out, "after-cancel")
            report["modal_observed"] = True
            report["b_focus_changed"] = (report["b_switch_attempt"]["x11"].splitlines()[:2]
                                         != report["dialog_open"]["x11"].splitlines()[:2])
            report["status"] = "completed"
        phase = "reset"
        episode.copy_artifacts(out / "guest-artifacts")
        episode.close()
        episode = None
        replacement, replacement_desktop = base.make_desktop("m01_reset", log, out)
        report["reset_success"] = "clean" in command(replacement_desktop,
            "test ! -e /tmp/codesk_modal && echo clean")
        replacement.close()
        replacement = None
    except Exception as exc:
        report["status"] = "invalid_setup" if phase in {"guest_startup", "setup"} else "probe_error"
        report["error"] = {"phase": phase, "type": type(exc).__name__, "message": str(exc)}
    finally:
        if replacement is not None:
            try:
                replacement.close()
            except Exception as exc:
                report["replacement_close_error"] = str(exc)
        if episode is not None:
            try:
                episode.copy_artifacts(out / "failure-artifacts")
            except Exception as exc:
                report["artifact_error"] = str(exc)
            try:
                episode.close()
            except Exception as exc:
                report["close_error"] = str(exc)
        report["wall_seconds"] = round(time.monotonic() - start, 3)
        log.write(out / "events.jsonl")
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        provenance = {"run_id": identity.run_id, "model_used": False,
                      "source": base.git_source_state(),
                      "source_sha256": {"scripts/probe_modal_m01_boundary.py":
                          hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                      "manifest_sha256": manifest["manifest_sha256"],
                      "artifact_sha256": {str(p.relative_to(out)):
                          hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(out.rglob("*")) if p.is_file()
                          and p.name != "provenance.json" and "overlays" not in p.parts}}
        (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"run_id": args.run_id, "status": report["status"],
                      "modal_observed": report.get("modal_observed"),
                      "b_focus_changed": report.get("b_focus_changed"),
                      "reset_success": report.get("reset_success"),
                      "artifact_dir": str(out), "error": report.get("error")}))
    return 0 if report["status"] == "completed" and report.get("reset_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
