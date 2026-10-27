"""Small real-Guest Data-to-Deck pilot using the existing OSWorld step harness.

This is a scripted adapter smoke, not model evidence. It deliberately reuses
OSWorld DesktopEnv, oscombo.Guest, StepLoopHarness, ProtocolStore and the case
Oracle. It only starts Guest(s) when invoked explicitly.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import io
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import traceback
from pathlib import Path
from typing import Any

from . import spec
from .fixtures import build_fixture
from .oracle import _gold_reconciliation_rows, evaluate
from .protocol import ProtocolStore, make_server
from .provenance import RunLedger, collect_artifacts
from .collab_tools import CollaborationClient


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _desktop_frame_ready(png: bytes) -> bool:
    """Reject boot-time black frames even when the screenshot HTTP API is live."""
    from PIL import Image
    with Image.open(io.BytesIO(png)) as frame:
        if frame.size != (1920, 1080):
            return False
        histogram = frame.convert("L").histogram()
        # A cursor on a black X root is not a usable desktop. This is only a
        # startup gate, never a filter of observations during actor execution.
        return sum(histogram[24:]) / (frame.width * frame.height) > 0.02


def _wait_for_visible_desktop(guest, timeout: float = 300) -> bytes:
    deadline = time.monotonic() + timeout
    consecutive = 0
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        shot = guest.screenshot(patience=60)
        ready = _desktop_frame_ready(shot)
        path = guest.root / "screenshots" / f"{guest.guest_key}-readiness-{attempt:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(shot)
        _append(guest.root / "desktop_readiness.jsonl", {"time": time.time(), "guest_key": guest.guest_key,
                "ready_frame": ready, "screenshot": str(path.relative_to(guest.root))})
        consecutive = consecutive + 1 if ready else 0
        if consecutive >= 2:
            return shot
        time.sleep(5)
    raise RuntimeError("Guest HTTP is live but no stable visible 1920x1080 desktop became ready")


def _append(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _episode_result_status(score_success: bool, reset_success: bool,
                           actor_results: dict[str, dict[str, Any]], model_called: bool) -> str:
    """Keep a failed Codex/MCP launch out of the model task-failure count."""
    if model_called and any(
        result.get("status") == "error"
        or (result.get("status") == "timeout" and int(result.get("steps", 0)) == 0)
        for result in actor_results.values()
    ):
        return "INVALID_INFRA_OR_RUNNER_ERROR"
    return "PASS" if score_success and reset_success else "FAIL"


def _absolute_existing_command(command: str | None) -> str | None:
    """Anchor project-relative executables before Guest startup changes cwd.

    Keep the lexical path to venv/bin/python (often a symlink); resolving the
    symlink can bypass the virtual environment's site-packages.
    """
    if not command:
        return command
    path = Path(command)
    if not path.is_absolute() and len(path.parts) > 1 and path.exists():
        return os.path.abspath(path)
    return command


def _gold_tsv() -> bytes:
    return ("\n".join("\t".join(str(cell) for cell in row)
                      for row in _gold_reconciliation_rows()) + "\n").encode("utf-8")


def _calc_actions() -> list[str]:
    return [
        # Enter in the name box can retain its edit focus on this LO build.
        # Select the sheet, then focus the grid and navigate to A1 instead.
        "import pyautogui, time; pyautogui.click(625,1045); time.sleep(5)",
        "import pyautogui, time; pyautogui.click(500,500); time.sleep(2); pyautogui.hotkey('ctrl','home'); time.sleep(3)",
        "import pyautogui, time; pyautogui.hotkey('ctrl','v'); time.sleep(5)",
        "import pyautogui, time; pyautogui.press('enter'); time.sleep(5)",
        "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(5)",
        "DONE",
    ]


def _impress_replace_actions(find: str, replacement: str) -> list[str]:
    # Separate field edits into observable steps. Under TCG a compound fast
    # click/Ctrl+A/type sequence can outrun LO's dialog event processing.
    actions = []
    for y, text in ((446, find), (538, replacement)):
        actions.append("import pyautogui, time; pyautogui.click(1000," + str(y) +
                       "); time.sleep(1); pyautogui.hotkey('ctrl','a'); time.sleep(1); "
                       "pyautogui.write(" + repr(text) + ", interval=0.05); time.sleep(2)")
    actions.append("import pyautogui, time; pyautogui.click(1195,594); time.sleep(5)")
    return actions


def _impress_initial_actions() -> list[str]:
    actions = ["import pyautogui, time; pyautogui.hotkey('ctrl','h'); time.sleep(5)"]
    for find, replacement in (
        ('Q3 revenue: $310k', 'Q3 revenue: $300k'),
        ('Gross Margin: 31% (Q3)', 'Gross Margin: 45% (Q3)'),
        ('Q3 revenue is $310k.', 'Q3 revenue: $300k'),
    ):
        actions.extend(_impress_replace_actions(find, replacement))
    return actions + ["import pyautogui, time; pyautogui.click(1240,775); time.sleep(5)", "DONE"]


def _impress_final_actions(shared: bool) -> list[str]:
    actions = []
    if shared:
        actions.append("import pyautogui, time; pyautogui.hotkey('alt','tab'); time.sleep(5)")
    actions.append("import pyautogui, time; pyautogui.hotkey('ctrl','h'); time.sleep(5)")
    for find, replacement in (
        ('West discount campaign caused the Q3 profit decline.',
         'West: revenue +$15k, promotion expense +$14k, operating profit -$11k. The data do not establish causality.'),
        ('Complete the regional profit bridge and distinguish evidence from explanation.',
         'Q2-Q3 bridge: revenue +$30k; total cost +$35k; operating profit -$5k.'),
    ):
        actions.extend(_impress_replace_actions(find, replacement))
    return actions + ["import pyautogui, time; pyautogui.click(1240,775); time.sleep(5)",
                      "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(5)", "DONE"]


def _lite_calc_actions() -> list[str]:
    return [
        "import pyautogui, time; pyautogui.click(470,1045); time.sleep(5)",
        "import pyautogui, time; pyautogui.click(500,500); time.sleep(2); pyautogui.hotkey('ctrl','home'); time.sleep(3)",
        "import pyautogui, time; pyautogui.hotkey('ctrl','v'); time.sleep(5)",
        "import pyautogui, time; pyautogui.press('enter'); time.sleep(5)",
        "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(5)",
        "DONE",
    ]


def _lite_impress_actions(digest_prefix: str) -> list[str]:
    actions = ["import pyautogui, time; pyautogui.hotkey('ctrl','h'); time.sleep(5)"]
    changes = (
        ("Q3 gross margin: 31%", "Q3 gross margin: 45%."),
        ("West operating profit increased $11k from Q2 to Q3.",
         "West operating profit fell $11k from Q2 to Q3."),
        ("West promotion spending increased and caused the profit change.",
         "West promotion spending rose $14k; the figures do not establish causation."),
        ("Verified source: pending Agent A analysis.",
         f"Verified source: verified_analysis.ods SHA-256 {digest_prefix}"),
    )
    for old, new in changes:
        actions.extend(_impress_replace_actions(old, new))
    return actions + ["import pyautogui, time; pyautogui.click(1240,775); time.sleep(5)",
                      "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(5)", "DONE"]


def _lite_v2_calc_actions(negative: bool = False) -> list[str]:
    formula = "=-10" if negative else "=(B4-C4-D4-E4)-(B3-C3-D3-E3)"
    return [
        "import pyautogui, time; pyautogui.click(230,399); time.sleep(1)",
        f"import pyautogui, time; pyautogui.write({formula!r}, 0.08); time.sleep(1)",
        "import pyautogui, time; pyautogui.press('enter'); time.sleep(1)",
        "import pyautogui, time; pyautogui.click(395,399); time.sleep(1)",
        "import pyautogui, time; pyautogui.write('B3:E4', 0.12); time.sleep(1)",
        "import pyautogui, time; pyautogui.press('enter'); time.sleep(1)",
        "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(3)",
        "DONE",
    ]


def _lite_v2_impress_actions(change: float) -> list[str]:
    # The optional LibreOffice donation banners shift the slide canvas down
    # about 40 pixels on a fresh Guest. Search the unique draft sentence in
    # Impress instead of clicking a fixed canvas position. This is the same
    # scripted policy in Shared and Isolated; model Actors remain unrestricted.
    actions = ["import pyautogui, time; pyautogui.hotkey('ctrl','h'); time.sleep(3)"]
    actions.extend(_impress_replace_actions(
        "West Q3 vs Q2 profit: [await A result]. Source: [await A analysis].",
        f"West operating profit fell ${abs(change):g}k from Q2 to Q3. "
        "Source: verified_analysis.ods."))
    return actions + [
        "import pyautogui, time; pyautogui.click(1240,775); time.sleep(1)",
        "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(3)",
        "DONE",
    ]


class LoggedGuest:
    """Narrow logging facade consumed by the existing StepLoopHarness."""

    def __init__(self, env: Any, ledger: RunLedger, run_root: Path, guest_key: str):
        from oscombo.guest import Guest
        self.base = Guest(env)
        self.env = env
        self.ledger = ledger
        self.root = run_root
        self.guest_key = guest_key
        self.actor = "system"
        self.action_n = 0

    @property
    def url(self) -> str:
        return self.base.url

    def screenshot(self, patience: float | None = None) -> bytes:
        return self.base.screenshot(patience)

    def accessibility_tree(self) -> str | None:
        return self.base.accessibility_tree()

    def active_window(self) -> str | None:
        return self.base.active_window()

    def _window_sample(self, phase: str) -> dict[str, Any]:
        started = _stamp()
        try:
            result = self.base.execute(["bash", "-lc",
                "printf 'ACTIVE_WINDOW_ID='; xdotool getactivewindow 2>/dev/null || true; "
                "printf 'ACTIVE_WINDOW_TITLE='; xdotool getactivewindow getwindowname 2>/dev/null || true; "
                "printf 'WINDOWS_BEGIN\\n'; wmctrl -lpGx 2>/dev/null || true; printf 'WINDOWS_END\\n'"], 20)
            output = result.get("output", "")
        except Exception as exc:
            output = f"sample_error={type(exc).__name__}: {exc}"
        return {"phase": phase, "sample_start_utc": started, "sample_end_utc": _stamp(),
                "atomic": False, "output": output}

    def run_pyautogui(self, code: str) -> Any:
        self.action_n += 1
        action_id = f"{self.actor}-{self.action_n:03d}"
        before = self._window_sample("before")
        started = time.time()
        self.ledger.record(self.actor, "action_start", guest_id=self.guest_key,
                           details={"action_id": action_id, "code": code,
                                    "window_sample": before, "atomic_window_sample": False})
        result = self.base.run_pyautogui(code)
        ended = time.time()
        after = self._window_sample("after")
        shot = self.base.screenshot(patience=40)
        shot_path = self.root / "screenshots" / f"{action_id}.png"
        shot_path.parent.mkdir(parents=True, exist_ok=True)
        shot_path.write_bytes(shot)
        event = {"actor": self.actor, "guest_key": self.guest_key, "action_id": action_id,
                 "code": code, "started_at": started, "ended_at": ended,
                 "duration_s": round(ended - started, 3), "window_before": before,
                 "window_after": after, "window_samples_atomic": False,
                 "screenshot": str(shot_path.relative_to(self.root))}
        _append(self.root / "gui_actions.jsonl", event)
        self.ledger.record(self.actor, "action_end", guest_id=self.guest_key,
                           details={"action_id": action_id, "duration_s": event["duration_s"],
                                    "window_sample": after, "screenshot": event["screenshot"],
                                    "atomic_window_sample": False})
        return result

    def execute(self, argv: list[str], timeout: float = 60) -> dict:
        return self.base.execute(argv, timeout)


class GuestFiles:
    def __init__(self, guests: dict[str, Any]):
        self.guests = guests

    def copy_from_guest(self, guest_id: str, guest_path: str, local_path: Path) -> None:
        source = self.guests[guest_id]
        controller = getattr(source, "controller", source)
        payload = controller.get_file(guest_path)
        if payload is None:
            raise RuntimeError(f"Guest file endpoint returned no bytes for {guest_id}:{guest_path}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(payload)


def _owned_container(env: Any, run_id: str) -> tuple[Any, dict[str, str]]:
    import docker
    container = getattr(env.provider, "container", None)
    cid = getattr(container, "id", None)
    if not cid or len(cid) != 64:
        raise RuntimeError("Guest ownership check requires a full 64-character container ID")
    docker_client = docker.from_env()
    actual = docker_client.containers.get(cid)
    actual.reload()
    labels = actual.attrs.get("Config", {}).get("Labels") or {}
    if actual.id != cid or labels.get("oscombo") != "1" or labels.get("oscombo.run") != run_id:
        raise RuntimeError(f"refusing operation on non-owned Guest {cid}: labels={labels}")
    return actual, labels


def _write_ownership(run_root: Path, value: dict[str, Any]) -> None:
    path = run_root / "ownership.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record_resource(run_root: Path, entry: dict[str, Any]) -> None:
    path = run_root / "ownership.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("resources", []).append(entry)
    _write_ownership(run_root, data)


def _missing_container(cid: str) -> bool:
    import docker
    try:
        docker.from_env().containers.get(cid).reload()
        return False
    except docker.errors.NotFound:
        return True


def _boot_guest(run_root: Path, run_id: str, key: str, image: str, provider: Path,
                runtime: str, ledger: RunLedger) -> tuple[Any, LoggedGuest, str]:
    os.environ.update({
        "OSWORLD_DIR": str(provider), "OSCOMBO_GUEST_IMAGE": image,
        "OSCOMBO_RUNTIME_IMAGE": runtime,
        "OSCOMBO_OVERLAY_DIR": str(run_root / "overlay" / key),
        "SWCUB_VM_OVERLAY": str(run_root / "overlay" / key),
        "OSCOMBO_RUN_LABEL": run_id,
        "OSCOMBO_GUEST_RAM": os.environ.get("OSCOMBO_GUEST_RAM", "4G"),
        "OSCOMBO_GUEST_CPUS": os.environ.get("OSCOMBO_GUEST_CPUS", "4"),
        "OSCOMBO_VM_READY_TIMEOUT": os.environ.get("OSCOMBO_VM_READY_TIMEOUT", "1800"),
    })
    if str(provider) not in sys.path:
        sys.path.insert(0, str(provider))
    os.chdir(provider)
    from desktop_env.desktop_env import DesktopEnv
    started = time.monotonic()
    env = DesktopEnv(provider_name="docker", path_to_vm=image,
                     cache_dir=str(run_root / "cache" / key), os_type="Ubuntu",
                     action_space="pyautogui", headless=False, require_a11y_tree=False,
                     require_terminal=False, client_password="osworld-public-evaluation")
    try:
        container, labels = _owned_container(env, run_id)
        cid = container.id
        mounts = container.attrs.get("Mounts", [])
        base = next((m for m in mounts if m.get("Destination") == "/System.qcow2"), None)
        if not base or base.get("Source") != image or base.get("RW") is not False:
            raise RuntimeError(f"Guest base image is not verified read-only: {base}")
        overlay = getattr(env.provider, "_oscombo_overlay", None)
        if not overlay or not Path(overlay).resolve().is_relative_to((run_root / "overlay").resolve()):
            raise RuntimeError(f"Guest overlay is not owned by this run: {overlay}")
        resource = {"kind": "guest-container", "key": key, "container_id": cid,
                    "name": container.name, "image_id": container.attrs.get("Image"),
                    "labels": labels, "overlay_path": str(overlay), "base_mount": base,
                    "status": "active", "created_utc": _stamp()}
        _record_resource(run_root, resource)
        ledger.metadata.setdefault("guests", []).append({
            "key": key, "container_id": cid, "labels": labels, "overlay_path": str(overlay),
            "base_image": base, "created_utc": _stamp(),
            "readiness_latency_s": round(time.monotonic() - started, 2)})
        ledger.metadata_path.write_text(json.dumps(ledger.metadata, indent=2, sort_keys=True) + "\n")
    except Exception:
        # A constructor/validation failure must not leak a resource this run
        # just created. Close only when the exact full ID and run labels prove
        # ownership; otherwise preserve the resource and report the ambiguity.
        candidate = getattr(getattr(env, "provider", None), "container", None)
        candidate_id = getattr(candidate, "id", None)
        if candidate_id and len(candidate_id) == 64:
            try:
                owned, owned_labels = _owned_container(env, run_id)
            except Exception:
                raise RuntimeError(
                    f"Guest startup failed and ownership could not be verified for {candidate_id}; "
                    "resource preserved for manual inspection.\n" + traceback.format_exc())
            _append(run_root / "resource_actions.jsonl", {"action": "startup_failure_owned_guest_cleanup",
                "guest_key": key, "container_id": candidate_id, "labels": owned_labels,
                "ownership_verified": True, "time_utc": _stamp()})
            owned.stop(timeout=10)
            owned.remove(force=True)
            if not _missing_container(candidate_id):
                raise RuntimeError(f"owned Guest remains after startup-failure cleanup: {candidate_id}")
        raise
    lg = LoggedGuest(env, ledger, run_root, key)
    # DesktopEnv's Docker constructor already starts a clean Guest. Do not
    # call reset here: the first explicit reset is reserved for the end-of-run
    # cleanliness check and must correspond to the Guest we logged above.
    try:
        shot = _wait_for_visible_desktop(lg)
    except BaseException:
        _verify_container(cid, run_id)
        _append(run_root / "resource_actions.jsonl", {"action": "visible_readiness_failed_cleanup",
                "container_id": cid, "run_id": run_id, "ownership_verified": True, "time_utc": _stamp()})
        env.close()
        raise
    path = run_root / "screenshots" / f"{key}-initial.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(shot)
    _append(run_root / "observations.jsonl", {"actor": "system", "guest_key": key,
        "time_utc": _stamp(), "screenshot": str(path.relative_to(run_root)),
        "bytes": len(shot), "window": lg._window_sample("initial"), "atomic": False})
    return env, lg, cid


def _shell(guest: LoggedGuest, script: str, timeout: int = 45) -> dict[str, Any]:
    result = guest.env.controller.run_bash_script(script, timeout=timeout)
    if not isinstance(result, dict) or result.get("status") != "success" or result.get("returncode", 0):
        raise RuntimeError(f"Guest setup command failed: {result}")
    return result


def _install_fixture(guest: LoggedGuest, fixture_dir: Path, task_root: str) -> None:
    pieces = [f"test ! -e {shlex.quote(task_root)}",
              f"mkdir -p {shlex.quote(task_root + '/input')} {shlex.quote(task_root + '/outputs/agent_A')} "
              f"{shlex.quote(task_root + '/outputs/agent_B')}"]
    for name in (spec.FIXTURE_NAMES["authority"], spec.FIXTURE_NAMES["draft"], spec.FIXTURE_NAMES["brief"]):
        payload = base64.b64encode((fixture_dir / name).read_bytes()).decode("ascii")
        dest = f"{task_root}/input/{name}"
        pieces.append(f"printf %s {shlex.quote(payload)} | base64 -d > {shlex.quote(dest)}")
    pieces.extend([
        f"chmod -R a-w {shlex.quote(task_root + '/input')}",
        f"cp {shlex.quote(task_root + '/input/' + spec.FIXTURE_NAMES['authority'])} "
        f"{shlex.quote(task_root + '/outputs/agent_A/verified_analysis.ods')}",
        f"cp {shlex.quote(task_root + '/input/' + spec.FIXTURE_NAMES['draft'])} "
        f"{shlex.quote(task_root + '/outputs/agent_B/final_management_brief.odp')}",
        f"chmod u+w {shlex.quote(task_root + '/outputs/agent_A/verified_analysis.ods')} "
        f"{shlex.quote(task_root + '/outputs/agent_B/final_management_brief.odp')}",
    ])
    _shell(guest, "set -e\n" + "\n".join(pieces), timeout=60)


def _office_frame_ready(png: bytes) -> bool:
    """Reject unpainted or disabled LO toolbars during setup on the pinned Guest."""
    from PIL import Image
    with Image.open(io.BytesIO(png)) as frame:
        if frame.size != (1920, 1080):
            return False
        toolbar = frame.convert("L").crop((100, 85, 1800, 220))
        return sum(toolbar.histogram()[:128]) / (toolbar.width * toolbar.height) > 0.01


def _launch(guest: LoggedGuest, application: str, path: str, log: str, readonly: bool = False) -> None:
    title_hint = Path(path).name
    cmd = (f"mkdir -p {shlex.quote(str(Path(log).parent))}; "
           f"nohup soffice --{application} {'--view ' if readonly else ''}{shlex.quote(path)} >{shlex.quote(log)} 2>&1 </dev/null & ")
    _shell(guest, cmd, timeout=15)
    deadline = time.monotonic() + 300
    consecutive = 0
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        # Setup only: make the initial app geometry reproducible. This is never
        # called to arbitrate concurrent Actor input during a model episode.
        _shell(guest, f"wmctrl -r {shlex.quote(title_hint)} -b add,maximized_vert,maximized_horz; "
                     f"wmctrl -a {shlex.quote(title_hint)}; sleep 5; true", timeout=15)
        shot = guest.screenshot(patience=60)
        active = guest.active_window() or ""
        ready = title_hint.casefold() in active.casefold() and _office_frame_ready(shot)
        path_out = guest.root / "screenshots" / f"{application}-ready-{time.time_ns()}-{attempt}.png"
        path_out.write_bytes(shot)
        _append(guest.root / "observations.jsonl", {"actor": "system", "guest_key": guest.guest_key,
            "time_utc": _stamp(), "application": application, "ready_frame": ready,
            "screenshot": str(path_out.relative_to(guest.root)), "window": guest._window_sample("app_ready"),
            "atomic": False})
        consecutive = consecutive + 1 if ready else 0
        if consecutive >= 2:
            return
    raise RuntimeError(f"application did not render a usable foreground document: {title_hint!r}")


def _activate_ready_document(guest: LoggedGuest, path: str, phase: str) -> None:
    """Select an already-open task document and capture verified foreground state."""
    title_hint = Path(path).name
    _shell(guest, f"wmctrl -a {shlex.quote(title_hint)}; sleep 1", timeout=10)
    active = guest.active_window() or ""
    if title_hint.casefold() not in active.casefold():
        raise RuntimeError(f"could not activate {title_hint!r}; active window is {active!r}")
    shot = guest.screenshot(patience=45)
    path_out = guest.root / "screenshots" / f"{phase}.png"
    path_out.write_bytes(shot)
    _append(guest.root / "observations.jsonl", {
        "actor": "system", "guest_key": guest.guest_key, "time_utc": _stamp(),
        "phase": phase, "expected_document": title_hint, "active_window": active,
        "screenshot": str(path_out.relative_to(guest.root)),
        "window": guest._window_sample(phase), "atomic": False})


def _clipboard(guest: LoggedGuest, run_id: str, payload: bytes | None = None) -> None:
    payload = payload if payload is not None else _gold_tsv()
    payload_path = f"/tmp/{run_id}/analysis.tsv"
    encoded = base64.b64encode(payload).decode("ascii")
    script = (f"mkdir -p {shlex.quote('/tmp/' + run_id)}; "
              f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(payload_path)}; "
              f"xclip -selection clipboard -i -t UTF8_STRING {shlex.quote(payload_path)} >/tmp/{run_id}/xclip.log 2>&1 & "
              "sleep 1; xclip -selection clipboard -o -target TARGETS 2>/dev/null")
    result = _shell(guest, script, timeout=20)
    if "UTF8_STRING" not in result.get("output", ""):
        raise RuntimeError(f"X11 clipboard UTF8_STRING target unavailable: {result}")
    _append(guest.root / "agent_inputs.jsonl", {"actor": "A", "guest_key": guest.guest_key,
        "kind": "scripted_policy_clipboard_input", "bytes": len(payload),
        "sha256": __import__("hashlib").sha256(payload).hexdigest(), "time_utc": _stamp()})


def _run_actor(role: str, guest: LoggedGuest, instruction: str, actions: list[str],
               run_root: Path, max_steps: int = 30, case_id: str = spec.CASE_ID) -> dict[str, Any]:
    from oscombo.harness.base import AgentContext
    from oscombo.harness.step_loop import StepLoopHarness
    guest.actor = role
    role_root = run_root / "actor_runs" / role
    role_root.mkdir(parents=True, exist_ok=True)
    actor_root = role_root / f"stage-{len(list(role_root.glob('stage-*'))) + 1:02d}"
    actor_root.mkdir(exist_ok=False)
    actor_spec = {"harness": "step", "policy": "scripted", "options": {
        "actions": actions, "action_pause": 0.25, "step_pause": 0.2,
        "save_screenshots": True}}
    ctx = AgentContext(name=role, task_id=case_id, instruction=instruction,
                       guest=guest, out=actor_root, max_steps=max_steps,
                       spec=actor_spec, t0=time.time())
    harness = StepLoopHarness(actor_spec)
    harness.prepare(ctx)
    started = time.monotonic()
    result = harness.run(ctx)
    summary = {"actor": role, "guest_key": guest.guest_key, "status": result.status,
               "steps": result.steps, "actions": sum(len(x.get("actions", [])) for x in result.trace),
               "elapsed_s": round(time.monotonic() - started, 2),
               "trace_path": str((actor_root / "trace.json").relative_to(run_root))}
    (actor_root / "trace.json").write_text(json.dumps(result.trace, indent=2, ensure_ascii=False) + "\n")
    _append(run_root / "actors.jsonl", summary)
    return summary


def _run_model_actor(role: str, guest: LoggedGuest, instruction: str, run_root: Path,
                     model: str, base_url: str, api_key_env: str, mcp_python: str,
                     collab_url: str | None, token_env: str | None, max_steps: int = 60,
                     effort: str = "medium", timeout: float = 1200,
                     local_qwen: bool = False, request_retries: int = 5,
                     tool_cooldown_sec: float = 0.0,
                     relay_client_token_env: str | None = None,
                     workspace_bridge: bool = False,
                     case_id: str = spec.CASE_ID) -> dict[str, Any]:
    """Run the existing CodexHarness against a real Guest and the case message API."""
    from oscombo.harness.base import AgentContext
    from oscombo.harness.external import CodexHarness
    guest.actor = role
    actor_root = run_root / "actor_runs" / role
    actor_root.mkdir(parents=True, exist_ok=True)
    options = {"base_url": base_url, "api_key_env": relay_client_token_env or api_key_env,
               "mcp_python": mcp_python,
               "timeout": timeout, "auth_mode": "none" if local_qwen else "auto",
               "request_retries": request_retries, "stream_retries": request_retries,
               "desktop_tool_cooldown_sec": tool_cooldown_sec}
    if relay_client_token_env:
        options["redact_env_keys"] = [api_key_env]
    if collab_url and token_env:
        options["collaboration"] = {"actor": role, "url": collab_url, "token_env": token_env,
                                    "workspace_bridge": workspace_bridge}
    actor_spec = {"harness": "codex", "model": model, "effort": effort, "options": options}
    ctx = AgentContext(name=role, task_id=case_id, instruction=instruction,
                       guest=guest, out=actor_root, max_steps=max_steps,
                       spec=actor_spec, t0=time.time())
    harness = CodexHarness(actor_spec)
    harness.prepare(ctx)
    started_at = time.time()
    started = time.monotonic()
    result = harness.run(ctx)
    trace_path = actor_root / "trace.json"
    trace_path.write_text(json.dumps(result.trace, indent=2, ensure_ascii=False) + "\n")
    summary = {"actor": role, "guest_key": guest.guest_key, "status": result.status,
               "steps": result.steps, "elapsed_s": round(time.monotonic() - started, 2),
               "started_at": started_at, "ended_at": time.time(),
               "model": model, "endpoint": base_url, "effort": effort,
               "trace_path": str(trace_path.relative_to(run_root)), "error": result.error,
               "harness_version": harness.harness_version}
    _append(run_root / "actors.jsonl", summary)
    return summary


def _effective_role_steps(role: str, diagnostic_step_limit: int | None,
                          role_budget: dict | None = None) -> int:
    baseline = int((role_budget or spec.ROLE_BUDGET)[role]["steps"])
    if diagnostic_step_limit is None:
        return baseline
    if diagnostic_step_limit < 1:
        raise ValueError("diagnostic step limit must be positive")
    return min(baseline, int(diagnostic_step_limit))


def _model_collaboration_tokens(tokens: dict[str, str], roles: tuple[str, ...]) -> dict[str, str]:
    """Publish the credentials already registered with the running message server."""
    token_envs = {role: f"CODESK_CDD_COLLAB_TOKEN_{role}" for role in roles}
    for role, name in token_envs.items():
        os.environ[name] = tokens[role]
    return token_envs


def _sample_guest_resources(root: Path, container_ids: dict, stop: threading.Event) -> None:
    import docker
    client = docker.from_env(timeout=5)
    try:
        while not stop.wait(5):
            known = dict(container_ids)
            try:
                # Include boot/reset costs before DesktopEnv returns readiness.
                for container in client.containers.list(filters={"label": ["oscombo=1", f"oscombo.run={root.name}"]}):
                    if container.id not in known.values():
                        known[f"boot-or-reset-{container.short_id}"] = container.id
            except Exception as exc:
                _append(root / "guest_resources.jsonl", {"time": time.time(), "phase": "discover_owned",
                                                        "error_type": type(exc).__name__})
            for key, cid in list(known.items()):
                try:
                    stats = client.containers.get(cid).stats(stream=False)
                    _append(root / "guest_resources.jsonl", {
                        "time": time.time(), "guest_key": key, "container_id": cid,
                        "read": stats.get("read"), "cpu_stats": stats.get("cpu_stats"),
                        "precpu_stats": stats.get("precpu_stats"), "memory_stats": stats.get("memory_stats"),
                        "pids_stats": stats.get("pids_stats"),
                        "caveat": "rootless cgroup counters may be absent; missing is not zero",
                    })
                except Exception as exc:
                    _append(root / "guest_resources.jsonl", {"time": time.time(), "guest_key": key,
                        "container_id": cid, "error_type": type(exc).__name__})
    finally:
        client.close()


def _verify_container(cid: str, run_id: str) -> Any:
    import docker
    container = docker.from_env().containers.get(cid)
    container.reload()
    labels = container.attrs.get("Config", {}).get("Labels") or {}
    if container.id != cid or labels.get("oscombo") != "1" or labels.get("oscombo.run") != run_id:
        raise RuntimeError(f"refusing to reset/close non-owned Guest {cid}: {labels}")
    return container


def _start_local_qwen_gateway(run_root: Path, python: Path, worker: Path, model_path: Path,
                              visible_gpus: str, max_output_tokens: int = 12000,
                              max_new_tokens: int = 512) -> tuple[subprocess.Popen, str]:
    """Start one loopback Qwen process and return its actor-routed Responses endpoint."""
    import requests
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log_path = run_root / "qwen_gateway.log"
    log = log_path.open("w", encoding="utf-8")
    cmd = [str(python), "-u", "-m", "oscombo.local_qwen_responses",
           "--worker-script", str(worker), "--model-path", str(model_path), "--device", "auto",
           "--host", "127.0.0.1", "--port", str(port), "--run-dir", str(run_root),
           "--max-output-tokens-per-actor", str(max_output_tokens),
           "--max-new-tokens", str(max_new_tokens)]
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": visible_gpus, "HF_HUB_OFFLINE": "1",
           "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "PYTHONUNBUFFERED": "1"}
    process = subprocess.Popen(cmd, cwd=Path(__file__).resolve().parents[3], env=env,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    health = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log.close()
            raise RuntimeError(f"local Qwen gateway exited {process.returncode}; see {log_path}")
        try:
            response = requests.get(health, timeout=2)
            if response.ok and response.json().get("ready"):
                log.flush()
                return process, f"http://127.0.0.1:{port}"
        except requests.RequestException:
            pass
        time.sleep(2)
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
    log.close()
    raise TimeoutError(f"local Qwen gateway did not become ready within 900s; see {log_path}")


def _start_codex_compat_relay(run_root: Path, upstream: str, api_key_env: str,
                              client_token: str, client_token_env: str) -> tuple[subprocess.Popen, str]:
    """Start one run-owned loopback relay; keep the provider key out of Codex."""
    import requests
    ready = run_root / "codex_relay_ready.json"
    log_path = run_root / "codex_relay.log"
    cmd = [sys.executable, "-u", "-m", "oscombo.responses_tool_image_relay",
           "--upstream", upstream, "--api-key-env", api_key_env,
           "--client-token-env", client_token_env,
           "--ready-file", str(ready),
           "--event-log", str(run_root / "codex_relay_events.jsonl")]
    relay_env = {name: os.environ[name] for name in (
        "PATH", "HOME", "PYTHONPATH", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "no_proxy", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")
                 if name in os.environ}
    relay_env.update({api_key_env: os.environ[api_key_env],
                      client_token_env: client_token, "PYTHONUNBUFFERED": "1"})
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=Path(__file__).resolve().parents[3],
                                   env=relay_env,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Codex compatibility relay exited {process.returncode}; see {log_path}")
        if ready.exists():
            info = json.loads(ready.read_text())
            if info.get("pid") == process.pid:
                base = f"http://127.0.0.1:{info['port']}/v1"
                try:
                    response = requests.get(f"http://127.0.0.1:{info['port']}/health", timeout=2)
                    if response.ok and response.json().get("ready"):
                        return process, base
                except requests.RequestException:
                    pass
        time.sleep(0.2)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    raise TimeoutError(f"Codex compatibility relay not ready within 20s; see {log_path}")


def run_pilot(condition: str, run_root: Path, image: str, provider: Path,
              runtime: str, model: str | None = None,
              base_url: str = "https://api.openai.com/v1",
              api_key_env: str = "OPENAI_API_KEY", mcp_python: str | None = None,
              effort: str = "medium", model_timeout: float = 1200,
              model_request_retries: int = 5,
              model_tool_cooldown_sec: float = 0.0,
              local_qwen: bool = False, qwen_python: Path | None = None,
              qwen_worker: Path | None = None, qwen_model_path: Path | None = None,
              qwen_visible_gpus: str = "6,7", qwen_max_new_tokens: int = 512,
              diagnostic_step_limit: int | None = None,
              codex_compat_relay: bool = False,
              case_lite_v1: bool = False,
              case_lite_v2: bool = False,
              scripted_negative: bool = False) -> dict[str, Any]:
    if case_lite_v1 and case_lite_v2:
        raise ValueError("select only one case version")
    if scripted_negative and (not case_lite_v2 or model):
        raise ValueError("scripted_negative applies only to v2 scripted controls")
    if case_lite_v2:
        from oscombo.collab.data_to_deck_lite_v2 import spec as case_spec
        from oscombo.collab.data_to_deck_lite_v2.fixtures import build_fixture as case_build_fixture
        from oscombo.collab.data_to_deck_lite_v2.oracle import evaluate as case_evaluate
    elif case_lite_v1:
        from oscombo.collab.data_to_deck_lite_v1 import spec as case_spec
        from oscombo.collab.data_to_deck_lite_v1.fixtures import build_fixture as case_build_fixture
        from oscombo.collab.data_to_deck_lite_v1.oracle import evaluate as case_evaluate
    else:
        case_spec, case_build_fixture, case_evaluate = spec, build_fixture, evaluate
    if condition not in {"solo_A", "solo_B", "collaborative_shared", "collaborative_isolated"}:
        raise ValueError("unsupported condition")
    # `_boot_guest` changes cwd into the pinned OSWorld provider. Resolve an
    # existing project-relative MCP interpreter while still in the repo cwd.
    mcp_python = _absolute_existing_command(mcp_python)
    is_solo = condition in {"solo_A", "solo_B"}
    solo_role = condition[-1] if is_solo else None
    if is_solo and not model:
        raise ValueError("role Solo conditions require a real model")
    if local_qwen and not all((qwen_python, qwen_worker, qwen_model_path)):
        raise ValueError("local Qwen mode requires python, worker script, and model path")
    if codex_compat_relay and (not model or local_qwen):
        raise ValueError("Codex compatibility relay requires a remote model endpoint")
    # Remote provider credentials stay in the coordinator/relay process only.
    # Actors receive a disposable loopback capability, never the provider key.
    if model and not local_qwen:
        codex_compat_relay = True
    if local_qwen and qwen_max_new_tokens < 1:
        raise ValueError("local Qwen per-response output cap must be positive")
    if model_request_retries < 0 or model_request_retries > 5:
        raise ValueError("model request retries must be between 0 and 5")
    if model_tool_cooldown_sec < 0 or model_tool_cooldown_sec > 300:
        raise ValueError("model tool cooldown must be between 0 and 300 seconds")
    run_root.mkdir(parents=True, exist_ok=False)
    run_id = run_root.name
    fixture_dir = run_root / "fixtures"
    case_build_fixture(fixture_dir)
    guest_count = 1 if condition in {"solo_A", "solo_B", "collaborative_shared"} else 2
    metadata = {"run_id": run_id, "case_id": case_spec.CASE_ID, "case_version": case_spec.CASE_VERSION,
                "condition": condition,
                "actor_type": "codex_harness_local_qwen" if model and local_qwen else
                              "codex_cli_real_model" if model else "scripted_steps_on_real_osworld_guest",
                "model_called": bool(model), "model": model,
                "endpoint": "per-run-loopback" if local_qwen else (base_url if model else None),
                "effort": effort if model else None,
                "model_request_retries": model_request_retries if model else None,
                "model_tool_cooldown_sec": model_tool_cooldown_sec if model else None,
                "codex_compat_relay": codex_compat_relay,
                "codex_compat_relay_policy": "strip Codex metadata headers; forward request body unchanged"
                if codex_compat_relay else None,
                "mcp_python": mcp_python if model else None,
                "local_qwen": local_qwen,
                "qwen_python": str(qwen_python.resolve()) if local_qwen and qwen_python else None,
                "qwen_worker_script": str(qwen_worker.resolve()) if local_qwen and qwen_worker else None,
                "qwen_checkpoint": str(qwen_model_path) if local_qwen else None,
                "qwen_visible_gpus": qwen_visible_gpus if local_qwen else None,
                "qwen_dtype": "bfloat16" if local_qwen else None,
                "qwen_quantization": None,
                "qwen_history_policy": (
                    "all system messages + first user task + latest 12 non-pinned messages; latest image only"
                    if local_qwen else None),
                "qwen_output_token_cap_per_actor": 12000 if local_qwen else None,
                "qwen_max_new_tokens_per_response": qwen_max_new_tokens if local_qwen else None,
                "qwen_budget_basis": "generated-output-token cap; input usage unavailable from worker" if local_qwen else None,
                "total_model_token_budget": case_spec.TOTAL_MODEL_TOKEN_BUDGET,
                "role_budget_contract": case_spec.ROLE_BUDGET,
                "diagnostic_step_limit": diagnostic_step_limit,
                "effective_role_step_budget": {role: _effective_role_steps(role, diagnostic_step_limit, case_spec.ROLE_BUDGET)
                                                for role in ((solo_role,) if is_solo else ("A", "B"))},
                "message_api_enabled": True, "attachment_api_enabled": True,
                "lite_peer_documents_preopened": bool((case_lite_v1 or case_lite_v2) and model and
                                                      condition == "collaborative_isolated"),
                "scripted_negative_control": scripted_negative,
                "guest_count": guest_count, "provider_commit": "3d778a3c9a34a079316f70df023b166700445792",
                "provider_path": str(provider), "base_qcow2": image,
                "runtime_image": runtime, "started_at": time.time()}
    ledger = RunLedger(run_root, metadata)
    (run_root / "ownership.json").write_text(json.dumps({"project": "CoDesk Data-to-Deck",
        "run_id": run_id, "owner": os.environ.get("USER"), "created_utc": _stamp(),
        "resources": [], "cleanup": "only full-ID + exact oscombo.run label resources"},
        indent=2) + "\n")
    store = ProtocolStore(run_root / "collaboration", run_id)
    tokens = {role: secrets.token_urlsafe(32) for role in ("A", "B")}
    server = make_server(store, tokens)
    import threading
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    clients = {role: CollaborationClient(f"http://127.0.0.1:{server.server_port}", role, tokens[role])
               for role in ("A", "B")}
    envs: dict[str, Any] = {}
    guests: dict[str, LoggedGuest] = {}
    container_ids: dict[str, str] = {}
    resource_stop = threading.Event()
    resource_thread = threading.Thread(target=_sample_guest_resources,
                                      args=(run_root, container_ids, resource_stop), daemon=True)
    resource_thread.start()
    outcomes: dict[str, Any] = {}
    model_token_envs: list[str] = []
    qwen_process: subprocess.Popen | None = None
    qwen_base_url = base_url
    relay_process: subprocess.Popen | None = None
    workspace_bridge = None
    model_base_url = base_url
    relay_client_token_env: str | None = None
    # Guest overlays are episode-private; a fixed public path keeps the role
    # prompts identical across conditions without exposing the treatment name.
    task_root = ("/tmp/codesk-data-to-deck-lite-v2" if case_lite_v2 else
                 "/tmp/codesk-data-to-deck-lite-v1" if case_lite_v1 else
                 "/tmp/codesk-data-to-deck")
    try:
        if local_qwen:
            assert qwen_python and qwen_worker and qwen_model_path
            qwen_process, qwen_base_url = _start_local_qwen_gateway(
            run_root, qwen_python, qwen_worker, qwen_model_path, qwen_visible_gpus,
            max_new_tokens=qwen_max_new_tokens)
            ledger.metadata["local_qwen_gateway"] = {"pid": qwen_process.pid,
                "base_url": qwen_base_url, "loopback_only": True, "created_at": _stamp(),
                "process_command": [str(qwen_python), "-m", "oscombo.local_qwen_responses"]}
            ledger.metadata_path.write_text(json.dumps(ledger.metadata, indent=2, sort_keys=True) + "\n")
            _append(run_root / "resource_actions.jsonl", {"action": "local_qwen_gateway_started",
                "pid": qwen_process.pid, "loopback_only": True, "gpus": qwen_visible_gpus,
                "run_id": run_id, "time_utc": _stamp()})
        if codex_compat_relay:
            relay_client_token_env = "CODESK_RUN_RELAY_TOKEN"
            relay_token = secrets.token_urlsafe(32)
            os.environ[relay_client_token_env] = relay_token
            model_token_envs.append(relay_client_token_env)
            relay_process, model_base_url = _start_codex_compat_relay(
                run_root, base_url, api_key_env, relay_token, relay_client_token_env)
            ledger.metadata["codex_compat_relay_process"] = {
                "pid": relay_process.pid, "base_url": model_base_url,
                "loopback_only": True, "created_at": _stamp()}
            ledger.metadata_path.write_text(json.dumps(ledger.metadata, indent=2, sort_keys=True) + "\n")
            _append(run_root / "resource_actions.jsonl", {"action": "codex_compat_relay_started",
                "pid": relay_process.pid, "run_id": run_id, "time_utc": _stamp()})
        guest_keys = ("shared",) if condition == "collaborative_shared" else (("solo",) if is_solo else ("A", "B"))
        for key in guest_keys:
            env, guest, cid = _boot_guest(run_root, run_id, key, image, provider, runtime, ledger)
            envs[key], guests[key], container_ids[key] = env, guest, cid
            _append(run_root / "resource_actions.jsonl", {"action": "guest_created",
                "run_id": run_id, "guest_key": key, "container_id": cid,
                "labels": _owned_container(env, run_id)[1], "time_utc": _stamp()})
            _install_fixture(guest, fixture_dir, task_root)

        guest_a = guests["shared"] if condition == "collaborative_shared" else (
            guests["solo"] if is_solo else guests["A"])
        guest_b = guests["shared"] if condition == "collaborative_shared" else (
            guests["solo"] if is_solo else guests["B"])
        if not is_solo:
            from .workspace_bridge import SavedArtifactBridge
            workspace_bridge = SavedArtifactBridge(
                run_root / "workspace_versions", run_id, task_root,
                {"A": guest_a.env.controller, "B": guest_b.env.controller},
                {"A": guest_a.guest_key, "B": guest_b.guest_key},
                case_id=case_spec.CASE_ID, peer_read_only=case_lite_v1 or case_lite_v2)
            server.workspace_bridge = workspace_bridge
            workspace_bridge.start()
        _launch(guest_a, "calc", f"{task_root}/outputs/agent_A/verified_analysis.ods",
                f"/tmp/{run_id}/calc.log")
        if model:
            if (case_lite_v1 or case_lite_v2) and condition == "collaborative_isolated":
                # The Shared desktop already has both role documents open.
                # Give each Isolated desktop the same open-document choices;
                # restore the role's own application to the foreground before
                # either Actor starts. Peer copies are read-only on disk.
                _launch(guest_a, "impress", f"{task_root}/outputs/agent_B/final_management_brief.odp",
                        f"/tmp/{run_id}/peer-impress.log", readonly=True)
                _launch(guest_b, "calc", f"{task_root}/outputs/agent_A/verified_analysis.ods",
                        f"/tmp/{run_id}/peer-calc.log", readonly=True)
                _activate_ready_document(guest_a,
                    f"{task_root}/outputs/agent_A/verified_analysis.ods", "isolated-A-own-foreground")
            _launch(guest_b, "impress", f"{task_root}/outputs/agent_B/final_management_brief.odp",
                    f"/tmp/{run_id}/impress.log")
            # Solo A and Solo B share one Guest object. Opening Impress after Calc
            # otherwise leaves the role-only A calibration on the wrong app.
            # Shared/isolated collaborative conditions retain their existing setup.
            if condition == "solo_A":
                _activate_ready_document(
                    guest_a, f"{task_root}/outputs/agent_A/verified_analysis.ods",
                    "solo_A_calc_foreground")
            actor_roles = (solo_role,) if is_solo else ("A", "B")
            collaboration_roles = () if is_solo else actor_roles
            token_envs = _model_collaboration_tokens(tokens, collaboration_roles)
            model_token_envs.extend(token_envs.values())

            instructions = {
                "A": case_spec.AGENT_A_INSTRUCTION +
                    f"\nThe open editable output workbook is {task_root}/outputs/agent_A/verified_analysis.ods.",
                "B": case_spec.AGENT_B_INSTRUCTION +
                    f"\nThe open editable output presentation is {task_root}/outputs/agent_B/final_management_brief.odp.",
            }
            if is_solo:
                instructions[solo_role] += "\nThis is a role-only solvability run. Complete your assigned role goal without waiting for or messaging another Actor."
            else:
                for role in actor_roles:
                    instructions[role] += (
                        "\nSaved role outputs are versioned and copied to the same paths on both desktops. "
                        "Use publish_saved_artifact after saving to verify delivery, and list_saved_artifacts "
                        "to obtain revision/hash metadata. "
                        + ("You may open the other role's file read-only through the GUI if needed. "
                           if case_lite_v2 else
                           "Open the other role's file read-only through the GUI; reopen it to read a newly saved revision. ")
                        + "Do not write the other role's output. "
                        "Edit documents through Calc and Impress; do not use Terminal commands, scripts, "
                        "macros or evaluator files to generate document contents.")
            actor_barrier = threading.Barrier(len(actor_roles))
            def actor_task(role: str) -> dict[str, Any]:
                actor_guest = guest_a if role == "A" else guest_b
                actor_base_url = f"{qwen_base_url}/actor/{role}/v1" if local_qwen else model_base_url
                if relay_client_token_env:
                    actor_base_url = model_base_url.removesuffix("/v1") + f"/actor/{role}/v1"
                actor_barrier.wait(timeout=60)
                return _run_model_actor(
                    role, actor_guest, instructions[role], run_root, model, actor_base_url,
                    api_key_env, mcp_python or sys.executable,
                    None if is_solo else f"http://127.0.0.1:{server.server_port}",
                    None if is_solo else token_envs[role],
                    max_steps=_effective_role_steps(role, diagnostic_step_limit, case_spec.ROLE_BUDGET), effort=effort,
                    timeout=model_timeout, local_qwen=local_qwen,
                    request_retries=model_request_retries,
                    tool_cooldown_sec=model_tool_cooldown_sec,
                    relay_client_token_env=relay_client_token_env,
                    workspace_bridge=workspace_bridge is not None,
                    case_id=case_spec.CASE_ID)
            if is_solo:
                outcomes[solo_role] = actor_task(solo_role)
            else:
                with ThreadPoolExecutor(max_workers=2, thread_name_prefix="cdd-actor") as pool:
                    futures = {role: pool.submit(actor_task, role) for role in ("A", "B")}
                    for role, future in futures.items():
                        outcomes[role] = future.result()
        elif case_lite_v2:
            from oscombo.collab.data_to_deck_lite_v2.private.gold import expected_change
            from oscombo.collab.data_to_deck_lite_v2.fixtures import authority_sheets
            change = expected_change(authority_sheets())
            outcomes["A"] = _run_actor(
                "A", guest_a, case_spec.AGENT_A_INSTRUCTION,
                _lite_v2_calc_actions(scripted_negative), run_root,
                max_steps=case_spec.ROLE_BUDGET["A"]["steps"], case_id=case_spec.CASE_ID)
            if outcomes["A"]["status"] != "done":
                raise RuntimeError(f"Lite v2 A scripted GUI did not finish: {outcomes['A']}")
            a_revision = workspace_bridge.publish("A")
            a_path = f"{task_root}/outputs/agent_A/verified_analysis.ods"
            if guest_b.env.controller.get_file(a_path) != guest_a.env.controller.get_file(a_path):
                raise RuntimeError("Lite v2 B Guest cannot read saved A revision")
            message = clients["A"].send_message(
                "B", f"Saved West Q3 minus Q2 operating profit change: {change:+g} USD_k. "
                     "Evidence: West_Finance!B3:E4 in verified_analysis.ods; please use saved revision.")
            if not any(m["message_id"] == message["message_id"] for m in clients["B"].read_messages()):
                raise RuntimeError("Lite v2 B cannot read A's message")
            _launch(guest_b, "impress", f"{task_root}/outputs/agent_B/final_management_brief.odp",
                    f"/tmp/{run_id}/impress.log")
            outcomes["B"] = _run_actor(
                "B", guest_b, case_spec.AGENT_B_INSTRUCTION,
                _lite_v2_impress_actions(change), run_root,
                max_steps=case_spec.ROLE_BUDGET["B"]["steps"], case_id=case_spec.CASE_ID)
            if outcomes["B"]["status"] != "done":
                raise RuntimeError(f"Lite v2 B scripted GUI did not finish: {outcomes['B']}")
            workspace_bridge.publish("B")
        elif case_lite_v1:
            from oscombo.collab.data_to_deck_lite_v1.private.gold import gold_findings_rows
            payload = ("\n".join("\t".join(str(cell) for cell in row)
                                  for row in gold_findings_rows()) + "\n").encode("utf-8")
            _clipboard(guest_a, run_id, payload)
            outcomes["A"] = _run_actor(
                "A", guest_a, case_spec.AGENT_A_INSTRUCTION,
                _lite_calc_actions(), run_root,
                max_steps=case_spec.ROLE_BUDGET["A"]["steps"],
                case_id=case_spec.CASE_ID)
            if outcomes["A"]["status"] != "done":
                raise RuntimeError(f"Lite A scripted GUI did not finish: {outcomes['A']}")
            a_revision = workspace_bridge.publish("A")
            a_path = f"{task_root}/outputs/agent_A/verified_analysis.ods"
            if guest_b.env.controller.get_file(a_path) != guest_a.env.controller.get_file(a_path):
                raise RuntimeError("Lite B Guest cannot read saved A revision")
            attachment = clients["A"].send_attachment("verified-findings.tsv", payload)
            clients["A"].send_message("B", "Saved Findings with the verified margin and West profit change; see the attached source cells. The numbers do not prove causation.",
                                      [attachment["attachment_id"]])
            if not clients["B"].read_messages() or clients["B"].read_attachment(attachment["attachment_id"])["sha256"] != attachment["sha256"]:
                raise RuntimeError("Lite B cannot read A's message or attachment")
            _launch(guest_b, "calc", a_path, f"/tmp/{run_id}/peer-findings.log", readonly=True)
            _launch(guest_b, "impress", f"{task_root}/outputs/agent_B/final_management_brief.odp",
                    f"/tmp/{run_id}/impress.log")
            outcomes["B"] = _run_actor(
                "B", guest_b, case_spec.AGENT_B_INSTRUCTION,
                _lite_impress_actions(a_revision["sha256"][:12]), run_root,
                max_steps=case_spec.ROLE_BUDGET["B"]["steps"],
                case_id=case_spec.CASE_ID)
            if outcomes["B"]["status"] != "done":
                raise RuntimeError(f"Lite B scripted GUI did not finish: {outcomes['B']}")
            workspace_bridge.publish("B")
        else:
            _clipboard(guest_a, run_id)
            outcomes["A_initial"] = _run_actor(
                "A", guest_a, case_spec.AGENT_A_INSTRUCTION, _calc_actions(), run_root,
                max_steps=case_spec.ROLE_BUDGET["A"]["steps"])
            if outcomes["A_initial"]["status"] != "done":
                raise RuntimeError(f"Actor A GUI step loop did not finish: {outcomes['A_initial']}")

            attachment = clients["A"].send_attachment("verified-analysis.tsv", _gold_tsv())
            clients["A"].send_message("B", "I saved the reconciliation workbook. The attached rows contain the checked Q2-Q3 bridge and West deltas; I have not inferred causality.", [attachment["attachment_id"]])
            received_a = clients["B"].read_messages()
            if not received_a or clients["B"].read_attachment(attachment["attachment_id"])["sha256"] != attachment["sha256"]:
                raise RuntimeError("Actor B could not read Actor A's message/attachment")

            _launch(guest_b, "impress", f"{task_root}/outputs/agent_B/final_management_brief.odp",
                    f"/tmp/{run_id}/impress.log")
            outcomes["B_initial"] = _run_actor(
                "B", guest_b, case_spec.AGENT_B_INSTRUCTION, _impress_initial_actions(), run_root,
                max_steps=case_spec.ROLE_BUDGET["B"]["steps"])
            question = clients["B"].send_message("A", "Please confirm the West profit change and whether the workbook supports a causal claim.")
            received_b = clients["A"].read_messages()
            if not any(m["message_id"] == question["message_id"] for m in received_b):
                raise RuntimeError("Actor A could not read Actor B's follow-up")

            if condition == "collaborative_shared":
                resume_actions = ["import pyautogui, time; pyautogui.hotkey('alt','tab'); time.sleep(1)",
                                  "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(1)", "DONE"]
            else:
                resume_actions = ["import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(1)", "DONE"]
            outcomes["A_resume"] = _run_actor(
                "A", guest_a, "Reopen your saved Calc analysis, verify the West Q2-Q3 figures and save it.",
                resume_actions, run_root, max_steps=case_spec.ROLE_BUDGET["A"]["steps"])
            response_attachment = clients["A"].send_attachment(
                "west-evidence.txt", b"West operating profit changes from 24k to 13k (-11k). The workbook shows concurrent revenue and promotion changes but does not establish causality.")
            clients["A"].send_message("B", "Confirmed. The source supports a -11k West operating-profit change, not a causal explanation.", [response_attachment["attachment_id"]])
            received_reply = clients["B"].read_messages()
            if clients["B"].read_attachment(response_attachment["attachment_id"])["content"].find("does not establish causality") < 0:
                raise RuntimeError("Actor B could not read Actor A's follow-up attachment")

            outcomes["B_final"] = _run_actor(
                "B", guest_b, "Finish the three-slide report using the verified evidence from Actor A.",
                _impress_final_actions(condition == "collaborative_shared"), run_root,
                max_steps=case_spec.ROLE_BUDGET["B"]["steps"])
            if outcomes["B_final"]["status"] != "done":
                raise RuntimeError(f"Actor B GUI step loop did not finish: {outcomes['B_final']}")

        if workspace_bridge is not None:
            workspace_bridge.stop()
            (run_root / "workspace_sync_result.json").write_text(json.dumps({
                "final_versions": workspace_bridge.snapshot(), "verified": True,
                "transient_errors": workspace_bridge.errors,
                "scope": "saved output bytes verified in both Guests; does not prove GUI reopen",
            }, indent=2) + "\n")
            workspace_bridge = None

        # Verify each saved output is present and hash it in the Guest before
        # collection.  Do not SIGKILL LibreOffice to force a reopen check: that
        # creates a recovery dialog and turns an otherwise saved artifact into
        # an artificial infrastructure failure.  A separate historical Guest
        # smoke already covered close/reopen persistence; this pilot scores the
        # saved files actually produced by the GUI actions below.
        guest_save_evidence = {}
        artifact_roles = (solo_role,) if is_solo else ("A", "B")
        role_paths = {"A": (guest_a, f"{task_root}/outputs/agent_A/verified_analysis.ods"),
                      "B": (guest_b, f"{task_root}/outputs/agent_B/final_management_brief.odp")}
        for role in artifact_roles:
            guest, guest_path = role_paths[role]
            proof = _shell(guest,
                f"test -s {shlex.quote(guest_path)} && stat -c '%s %Y' {shlex.quote(guest_path)} "
                f"&& sha256sum {shlex.quote(guest_path)}", timeout=20)
            guest_save_evidence[role] = {"guest_key": guest.guest_key, "path": guest_path,
                                         "output": proof.get("output", "").strip(),
                                         "time_utc": _stamp()}

        artifact_items = [{"actor": role, "guest_id": role_paths[role][0].guest_key,
                           "guest_path": role_paths[role][1],
                           "local_path": f"{role}/{'verified_analysis.ods' if role == 'A' else 'final_management_brief.odp'}"}
                          for role in artifact_roles]
        guest_controllers = {key: envs[key].controller for key in envs}
        manifest = collect_artifacts(run_root, artifact_items, GuestFiles(guest_controllers))
        (run_root / "guest_save_evidence.json").write_text(
            json.dumps(guest_save_evidence, indent=2, sort_keys=True) + "\n")
        analysis_path = (run_root / "artifacts/A/verified_analysis.ods" if "A" in artifact_roles
                         else fixture_dir / case_spec.FIXTURE_NAMES["authority"])
        deck_path = (run_root / "artifacts/B/final_management_brief.odp" if "B" in artifact_roles
                     else fixture_dir / case_spec.FIXTURE_NAMES["draft"])
        oracle = case_evaluate(fixture_dir / case_spec.FIXTURE_NAMES["authority"], analysis_path,
                          fixture_dir / case_spec.FIXTURE_NAMES["draft"], deck_path)
        (run_root / "oracle.json").write_text(json.dumps(oracle, indent=2, sort_keys=True) + "\n")

        # Post-execution lifecycle check: close/reopen via real GUI, without
        # editing. Preserve the scored bytes and do not rely on historical runs.
        reopen_evidence = []
        reopen_complete = True
        for role in artifact_roles:
            guest, guest_path = role_paths[role]
            before_bytes = guest.env.controller.get_file(guest_path)
            try:
                _activate_ready_document(guest, guest_path, f"reopen-{role}-before")
            except RuntimeError:
                active = guest.active_window() or ""
                if not model or "Save Document?" not in active:
                    raise
                # A timed-out Actor may leave unsaved edits and LO's save
                # question. Scoring already used the saved bytes above. Do not
                # click Save or silently change that artifact for a lifecycle
                # check; preserve the modal screenshot and continue to reset.
                shot_path = run_root / "screenshots" / f"reopen-{role}-blocked-unsaved.png"
                shot_path.write_bytes(guest.screenshot(patience=45))
                reopen_complete = False
                reopen_evidence.append({"actor": role, "guest_key": guest.guest_key,
                    "same_bytes_after_gui_reopen": False, "blocked_by_unsaved_dialog": True,
                    "active_window": active,
                    "saved_sha256": __import__("hashlib").sha256(before_bytes).hexdigest(),
                    "screenshot": str(shot_path.relative_to(run_root)), "time": time.time()})
                continue
            try:
                guest.actor = "system"
                guest.run_pyautogui("import pyautogui, time; pyautogui.hotkey('ctrl','w'); time.sleep(2)")
                # A timed-out Actor may have left unsaved edits. Ctrl+W then
                # opens a modal instead of closing the document; polling for
                # its window title through the Guest shell can stall and hide
                # the already collected Oracle score. Keep the modal evidence
                # and proceed to the run-owned reset without answering it.
                active_after_close = guest.active_window() or ""
                if model and "Save Document?" in active_after_close:
                    raise RuntimeError("postscore reopen blocked by unsaved document dialog")
                _shell(guest, f"for i in $(seq 1 30); do "
                              f"wmctrl -l | grep -Fq {shlex.quote(Path(guest_path).name)} || exit 0; "
                              "sleep 1; done; exit 1", timeout=40)
                _launch(guest, "calc" if role == "A" else "impress", guest_path,
                        f"/tmp/{run_id}/reopen-{role}.log")
                after_bytes = guest.env.controller.get_file(guest_path)
                if not before_bytes or before_bytes != after_bytes:
                    raise RuntimeError(f"saved {role} artifact changed or disappeared during GUI reopen")
                reopen_evidence.append({"actor": role, "guest_key": guest.guest_key,
                                        "sha256": __import__("hashlib").sha256(after_bytes).hexdigest(),
                                        "same_bytes_after_gui_reopen": True, "time": time.time()})
                if condition == "collaborative_isolated":
                    peer_guest = guest_b if role == "A" else guest_a
                    _launch(peer_guest, "calc" if role == "A" else "impress", guest_path,
                            f"/tmp/{run_id}/peer-read-{role}.log", readonly=True)
                    peer_bytes = peer_guest.env.controller.get_file(guest_path)
                    if peer_bytes != after_bytes:
                        raise RuntimeError(f"peer Guest read a different {role} revision")
                    reopen_evidence.append({"actor": role, "guest_key": peer_guest.guest_key,
                        "sha256": __import__("hashlib").sha256(peer_bytes).hexdigest(),
                        "peer_gui_opened_readonly": True, "time": time.time()})
            except RuntimeError as exc:
                if not model:
                    raise
                # A timed-out model can leave LibreOffice in a state where
                # closing or reopening stalls. The saved bytes were collected
                # and scored above; record the lifecycle failure, then still
                # attempt the run-owned Guest reset.
                reopen_complete = False
                shot_path = run_root / "screenshots" / f"reopen-{role}-failed.png"
                try:
                    shot_path.write_bytes(guest.screenshot(patience=45))
                    shot = str(shot_path.relative_to(run_root))
                except Exception:
                    shot = None
                reopen_evidence.append({"actor": role, "guest_key": guest.guest_key,
                    "same_bytes_after_gui_reopen": False, "error": str(exc),
                    "saved_sha256": __import__("hashlib").sha256(before_bytes).hexdigest(),
                    "screenshot": shot, "time": time.time()})
        (run_root / "reopen_evidence.json").write_text(json.dumps(reopen_evidence, indent=2) + "\n")

        reset_results = []
        for key, env in envs.items():
            old_id = container_ids[key]
            _verify_container(old_id, run_id)
            ledger.record("system", "reset", guest_id=key, details={"phase": "begin", "container_id": old_id})
            # The upstream Docker provider reads these process environment
            # variables when it creates a replacement Guest. Re-select this
            # Guest's private overlay directory before each reset; otherwise
            # the last-started isolated Guest would capture both overlays.
            overlay_dir = str(run_root / "overlay" / key)
            os.environ["OSCOMBO_OVERLAY_DIR"] = overlay_dir
            os.environ["SWCUB_VM_OVERLAY"] = overlay_dir
            os.environ["OSCOMBO_RUN_LABEL"] = run_id
            # The existing Agent harness talks directly to the OSWorld
            # controller, so DesktopEnv does not see env.step() calls and
            # cannot infer that this Guest is dirty. Mark it used so its
            # official reset path replaces the run-owned container/overlay.
            env.is_environment_used = True
            obs = env.reset()
            new_container, labels = _owned_container(env, run_id)
            new_id = new_container.id
            if new_id == old_id or not _missing_container(old_id):
                raise RuntimeError(f"Guest reset did not replace the owned container for {key}")
            mounts = new_container.attrs.get("Mounts", [])
            base = next((m for m in mounts if m.get("Destination") == "/System.qcow2"), None)
            overlay = getattr(env.provider, "_oscombo_overlay", None)
            if not base or base.get("Source") != image or base.get("RW") is not False:
                raise RuntimeError(f"reset Guest base image is not verified read-only: {base}")
            if not overlay or not Path(overlay).resolve().is_relative_to((run_root / "overlay").resolve()):
                raise RuntimeError(f"reset Guest overlay is not owned by this run: {overlay}")
            probe = envs[key].controller.run_bash_script(
                f"test ! -e {shlex.quote(task_root)} && ! pgrep -x soffice.bin >/dev/null", timeout=30)
            reset_ok = (isinstance(probe, dict) and probe.get("status") == "success"
                        and probe.get("returncode", 0) == 0)
            if not reset_ok:
                raise RuntimeError(f"Guest reset verification failed for {key}: {probe}")
            reset_results.append({"guest_key": key, "old_container_id": old_id,
                                  "new_container_id": new_id, "labels": labels,
                                  "workspace_clean": True, "time_utc": _stamp()})
            container_ids[key] = new_id
            ownership_path = run_root / "ownership.json"
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
            for resource in ownership.get("resources", []):
                if resource.get("container_id") == old_id:
                    resource["status"] = "removed_by_verified_reset"
                    resource["removed_utc"] = _stamp()
            _write_ownership(run_root, ownership)
            _record_resource(run_root, {"kind": "guest-container", "key": key,
                "container_id": new_id, "labels": labels,
                "overlay_path": str(overlay), "base_mount": base,
                "status": "active_after_reset", "created_utc": _stamp()})
            ledger.record("system", "reset", guest_id=key,
                          details={"phase": "verified", "old_container_id": old_id,
                                   "new_container_id": new_id, "workspace_clean": True})
            _append(run_root / "resource_actions.jsonl", {"action": "reset_verified",
                "guest_key": key, "old_container_id": old_id, "new_container_id": new_id,
                "ownership_verified": True, "time_utc": _stamp()})

        score_success = oracle["actors"][solo_role]["success"] if is_solo else oracle["joint_success"]
        summary = {"run_id": run_id, "condition": condition, "guest_count": guest_count,
                   "actor_results": outcomes, "artifact_manifest": manifest,
                   "guest_save_evidence": guest_save_evidence,
                   "oracle": oracle, "reset": reset_results,
                   "reopen_complete": reopen_complete,
                   "score_mode": f"actor_{solo_role}_solvability" if is_solo else "joint_success",
                   "scored_success": bool(score_success),
                   "protocol_event_log": str(store.log_path),
                   "elapsed_s": round(time.time() - metadata["started_at"], 2),
                   "status": _episode_result_status(
                       bool(score_success), len(reset_results) == guest_count and reopen_complete,
                       outcomes, bool(model))}
        (run_root / "result.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return summary
    finally:
        resource_stop.set()
        resource_thread.join(timeout=10)
        if workspace_bridge is not None:
            try:
                workspace_bridge.stop()
            except Exception as exc:
                _append(run_root / "workspace_sync_errors.jsonl", {"error": str(exc), "time": time.time()})
        for name in model_token_envs:
            os.environ.pop(name, None)
        # Only close resources whose full container IDs still carry this run's
        # exact ownership labels. Never enumerate/remove unrelated containers.
        cleanup_errors: list[str] = []
        for key, env in list(envs.items()):
            cid = container_ids.get(key)
            if cid:
                try:
                    _verify_container(cid, run_id)
                except Exception as exc:
                    cleanup_errors.append(f"{key} {cid}: ownership check failed; resource preserved: {exc}")
                    continue
                _append(run_root / "resource_actions.jsonl", {"action": "close_begin",
                    "guest_key": key, "container_id": cid, "ownership_verified": True,
                    "time_utc": _stamp()})
            try:
                env.close()
            except Exception as exc:
                cleanup_errors.append(f"{key} {cid}: close raised {type(exc).__name__}: {exc}")
            if cid and not _missing_container(cid):
                cleanup_errors.append(f"{key} {cid}: owned Guest remains after close()")
                continue
            if cid:
                _append(run_root / "resource_actions.jsonl", {"action": "close_verified",
                    "guest_key": key, "container_id": cid, "time_utc": _stamp()})
                ownership_path = run_root / "ownership.json"
                ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
                for resource in ownership.get("resources", []):
                    if resource.get("container_id") == cid:
                        resource["status"] = "removed_after_exact_id_label_verification"
                        resource["removed_utc"] = _stamp()
                _write_ownership(run_root, ownership)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if qwen_process is not None:
            _append(run_root / "resource_actions.jsonl", {"action": "local_qwen_gateway_stop_requested",
                "pid": qwen_process.pid, "time_utc": _stamp()})
            qwen_process.terminate()
            try:
                qwen_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                qwen_process.kill()
                qwen_process.wait(timeout=10)
            _append(run_root / "resource_actions.jsonl", {"action": "local_qwen_gateway_stopped",
                "pid": qwen_process.pid, "returncode": qwen_process.returncode, "time_utc": _stamp()})
        if relay_process is not None:
            _append(run_root / "resource_actions.jsonl", {"action": "codex_compat_relay_stop_requested",
                "pid": relay_process.pid, "run_id": run_id, "time_utc": _stamp()})
            relay_process.terminate()
            try:
                relay_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                relay_process.kill()
                relay_process.wait(timeout=5)
            _append(run_root / "resource_actions.jsonl", {"action": "codex_compat_relay_stopped",
                "pid": relay_process.pid, "returncode": relay_process.returncode,
                "run_id": run_id, "time_utc": _stamp()})
        if cleanup_errors:
            raise RuntimeError("Guest cleanup verification incomplete: " + "; ".join(cleanup_errors))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True,
                        choices=("solo_A", "solo_B", "collaborative_shared", "collaborative_isolated"))
    parser.add_argument("--case-lite-v1", action="store_true",
                        help="run the independent Data-to-Deck Lite v1 profile")
    parser.add_argument("--case-lite-v2", action="store_true",
                        help="run the independent Data-to-Deck Lite v2 profile")
    parser.add_argument("--scripted-negative", action="store_true",
                        help="v2 scripted control deliberately saves an incorrect Calc result")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--model", help="use the existing CodexHarness with this model ID instead of scripted actors")
    parser.add_argument("--local-qwen", action="store_true",
                        help="start a run-owned loopback Responses bridge to the existing local Qwen runtime")
    parser.add_argument("--qwen-python", type=Path)
    parser.add_argument("--qwen-worker-script", type=Path)
    parser.add_argument("--qwen-model-path", type=Path)
    parser.add_argument("--qwen-visible-gpus", default="6,7")
    parser.add_argument("--qwen-max-new-tokens", type=int, default=512,
                        help="per-response cap for the local Qwen action JSON")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--codex-compat-relay", action="store_true",
                        help="run-owned loopback relay strips Codex metadata headers for compatible providers")
    parser.add_argument("--api-key-env", default="AIGCBEST_API_KEY")
    parser.add_argument("--mcp-python", help="Python executable with MCP, requests and Pillow installed")
    parser.add_argument("--effort", default="medium", choices=("low", "medium", "high", "xhigh"))
    parser.add_argument("--model-timeout", type=float, default=1200)
    parser.add_argument("--model-request-retries", type=int, default=5,
                        help="Codex transport retries for transient request errors; never replays GUI actions")
    parser.add_argument("--model-tool-cooldown-sec", type=float, default=0.0,
                        help="minimum seconds between desktop tool results and subsequent model turns")
    parser.add_argument("--diagnostic-step-limit", type=int,
                        help="temporary per-actor GUI-call cap for bounded calibration; does not change the 240-step task budget")
    args = parser.parse_args(argv)
    run_root = args.run_root.resolve()
    provider = args.provider.resolve()
    if not provider.is_dir() or not (provider / ".git").exists():
        raise SystemExit(f"isolated OSWorld Provider workview missing: {provider}")
    if args.local_qwen and not args.model:
        args.model = "Qwen3-VL-30B-A3B-Instruct"
    if args.model and not args.local_qwen and not os.environ.get(args.api_key_env):
        raise SystemExit(f"model requested but environment variable {args.api_key_env} is unset")
    if args.local_qwen and not all((args.qwen_python, args.qwen_worker_script, args.qwen_model_path)):
        raise SystemExit("--local-qwen requires --qwen-python, --qwen-worker-script, and --qwen-model-path")
    try:
        result = run_pilot(args.condition, run_root, args.image, provider, args.runtime,
                           model=args.model, base_url=args.base_url, api_key_env=args.api_key_env,
                           mcp_python=args.mcp_python, effort=args.effort,
                           model_timeout=args.model_timeout,
                           model_request_retries=args.model_request_retries,
                           model_tool_cooldown_sec=args.model_tool_cooldown_sec,
                           local_qwen=args.local_qwen,
                           qwen_python=args.qwen_python, qwen_worker=args.qwen_worker_script,
                           qwen_model_path=args.qwen_model_path,
                           qwen_visible_gpus=args.qwen_visible_gpus,
                           qwen_max_new_tokens=args.qwen_max_new_tokens,
                           diagnostic_step_limit=args.diagnostic_step_limit,
                           codex_compat_relay=args.codex_compat_relay,
                           case_lite_v1=args.case_lite_v1,
                           case_lite_v2=args.case_lite_v2,
                           scripted_negative=args.scripted_negative)
    except Exception as exc:
        failure = {"status": "INVALID_INFRA_OR_RUNNER_ERROR", "condition": args.condition,
                   "run_id": run_root.name, "error": f"{type(exc).__name__}: {exc}",
                   "traceback": traceback.format_exc(), "failed_at_utc": _stamp()}
        if run_root.exists():
            (run_root / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        print(json.dumps(failure, indent=2), file=sys.stderr)
        raise SystemExit(3)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
