#!/usr/bin/env python3
"""Bounded Writer hyperlink/comment GUI feasibility probe on a run-owned Guest."""
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
from swcub.task_factory import render_writer_fodt

PATH = "/tmp/codesk_semantic_probe/writer.fodt"
SEED = render_writer_fodt(["Link label", "Guard paragraph"])


def command(desktop, shell):
    return base.guest_command(desktop, ["bash", "-lc", shell])


def capture(episode, desktop, out, label):
    episode.refresh_observation(source="semantic_probe")
    obs = episode.observe("semantic_probe")
    screenshot = obs.get("screenshot")
    if isinstance(screenshot, bytes) and screenshot:
        (out / f"{label}.png").write_bytes(screenshot)
    tree = obs.get("accessibility_tree") or ""
    (out / f"{label}.accessibility.txt").write_text(tree)
    x11 = command(desktop, 'printf "ACTIVE="; xdotool getactivewindow; '
                           'printf "TITLE="; xdotool getactivewindow getwindowname; '
                           'wmctrl -lpG; xid=$(xdotool getactivewindow); '
                           'xprop -id "$xid" WM_TRANSIENT_FOR WM_CLASS WM_WINDOW_ROLE 2>&1')
    (out / f"{label}.x11.txt").write_text(x11)
    return {"screenshot": bool(screenshot), "tree_chars": len(tree),
            "x11": x11.splitlines()[:4]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    args = parser.parse_args()
    out = args.artifact_parent.expanduser().resolve() / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "overlays").mkdir()
    ledger = out / "resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID": args.run_id, "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
                       "SWCUB_RESOURCE_LEDGER": str(ledger),
                       "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger)
    log = base.EventLog()
    episode = replacement = None
    report = {"run_id": args.run_id, "status": "starting", "guest_host": os.uname().nodename,
              "model_used": False, "seed_sha256": hashlib.sha256(SEED).hexdigest()}
    start = time.monotonic()
    phase = "guest_startup"
    try:
        episode, desktop = base.make_desktop("semantic_probe", log, out)
        phase = "setup"
        statement = ("from pathlib import Path; import base64; "
                     f"p=Path({PATH!r}); p.parent.mkdir(parents=True,exist_ok=True); "
                     f"p.write_bytes(base64.b64decode({base64.b64encode(SEED).decode()!r}))")
        episode.cli_action("task_setup", "python3 -c " + shlex.quote(statement))
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(
            f"soffice --nologo --norestore --nofirststartwizard --writer {shlex.quote(PATH)} "
            f">/tmp/codesk-semantic-probe.log 2>&1 & sleep 6"))
        report["readiness"] = base.wait_for_app_document(
            episode, desktop, "writer", PATH, out / "readiness", timeout=120)
        actor = ActorContext("semantic_probe_actor", episode, "gui")
        report["initial"] = capture(episode, desktop, out, "initial")
        phase = "hyperlink_dialog"
        actor.press_key("ctrl+home")
        actor.press_key("shift+end")
        actor.press_key("ctrl+k")
        time.sleep(2)
        report["hyperlink_dialog"] = capture(episode, desktop, out, "hyperlink-dialog")
        actor.press_key("esc")
        time.sleep(1)
        phase = "comment"
        actor.press_key("ctrl+home")
        actor.press_key("shift+end")
        actor.press_key("ctrl+alt+c")
        time.sleep(2)
        report["comment_editor"] = capture(episode, desktop, out, "comment-editor")
        actor.type_text("Review note 482")
        actor.press_key("ctrl+s")
        time.sleep(2)
        report["after_comment_save"] = capture(episode, desktop, out, "after-comment-save")
        report["saved_fodt"] = command(desktop, f"cat {shlex.quote(PATH)}")
        (out / "saved-comment.fodt").write_text(report["saved_fodt"])
        del report["saved_fodt"]
        report["status"] = "completed"
        phase = "reset"
        episode.copy_artifacts(out / "guest-artifacts")
        episode.close(); episode = None
        replacement, replacement_desktop = base.make_desktop("semantic_probe_reset", log, out)
        report["reset_success"] = "clean" in command(
            replacement_desktop, f"test ! -e {shlex.quote(PATH)} && echo clean")
        replacement.close(); replacement = None
    except Exception as exc:
        report["status"] = "invalid_setup" if phase in {"guest_startup", "setup"} else "probe_error"
        report["error"] = {"phase": phase, "type": type(exc).__name__, "message": str(exc)}
    finally:
        for item in (replacement, episode):
            if item is not None:
                try: item.close()
                except Exception as exc: report.setdefault("close_errors", []).append(str(exc))
        report["wall_seconds"] = round(time.monotonic() - start, 3)
        log.write(out / "events.jsonl")
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        provenance = {"run_id": identity.run_id, "source": base.git_source_state(),
            "source_sha256": {"scripts/probe_writer_semantics.py":
                hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            "seed_sha256": hashlib.sha256(SEED).hexdigest(),
            "artifact_sha256": {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(out.rglob("*")) if p.is_file() and p.name != "provenance.json"
                and "overlays" not in p.parts}}
        (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"run_id": args.run_id, "status": report["status"],
                      "reset_success": report.get("reset_success"), "error": report.get("error"),
                      "artifact_dir": str(out)}))
    return 0 if report["status"] == "completed" and report.get("reset_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
