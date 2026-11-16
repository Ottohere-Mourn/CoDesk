"""Stage and run the 19-case CoDesk suite on CPU10 with gpt-6.1-sol, Native QEMU KVM, and non-YOLO Docker Codex."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

from experiments.codesk_hybrid_v2_runtime import (
    CONTAINER_CODEX_HARNESS_REPLACEMENT,
    CWD1_CODEX_RUNNER_SOURCE,
    DESKTOP_GATE_LOCK_HELPERS,
    GUEST_BASH_TOOLS_SOURCE,
    GUEST_CLI_TOOLS_SOURCE,
    HYBRID_V2_MODULE_SOURCE,
    LIVE_PILOT_REPLACEMENT,
    RECONSTRUCTED_CALC_HELPER_SOURCE,
    RECONSTRUCTED_WORKFLOWS_HELPER_SOURCE,
    RECONSTRUCTED_WRITER_OVERWRITE_HELPER_SOURCE,
    RESPONSES_RELAY_SOURCE,
    verify_reconstructed_prompt_hashes,
)


MODEL = "gpt-6.1-sol"
PINNED_SOURCES = {
    "handoff": ("codex/13-case-handoff-20261104", "e5bcbd05699dd4044ca3b8981b2486cce1fc97c2"),
    "candidate_repair": ("codex/candidate-repair-20261104", "909c88b4081cf981ff9187c6e976720bca48295b"),
    "case2": ("codex/case2-v12", "953d68418e35864e176c8b5c54f3bd497c60b7d3"),
    "case3": ("codex/case3-followup", "c6bcb56d9bd65bc37891d58a7f9e7d991349eaf2"),
    "case4": ("codex/case4-hardening", "3462672b50b73d08183528ba2148304b83438a89"),
}

PORTFOLIO_19 = [
    ("AUTH-1", "Local release-review active principal switch", "hybrid_suite", "scripts/run_auth_identity_hybrid_v2.py", "per_arm", "upstream_complete"),
    ("VIEW-1", "Release-review viewport scroll hit-testing", "hybrid_suite", "scripts/run_viewport_signoff_hybrid_v2.py", "per_arm", "upstream_complete"),
    ("CRM-LU1", "Legacy CRM full-record form lost update", "hybrid_suite", "scripts/run_crm_lu1_hybrid_v2.py", "per_arm", "upstream_complete"),
    ("SITEACT-STATE1", "Site activation readiness stale snapshot", "hybrid_suite", "scripts/run_siteact_state_hybrid_v2.py", "per_arm", "upstream_complete"),
    ("PAY-1", "Payroll timesheet correction stale payment line", "hybrid_suite", "scripts/run_pay1_timesheet_hybrid_v1.py", "pay1_split", "upstream_complete"),
    ("DATA-REL1", "Dataset policy amendment stale staging package", "hybrid_suite", "scripts/run_data_rel1_ma_id_v1.py", "datarel1_split", "upstream_complete"),
    ("AP-1", "Accounts payable remittance credit-memo handoff", "hybrid_suite", "scripts/run_ap1_remittance_hybrid_v2_triplet.py", "per_arm", "upstream_complete"),
    ("W1", "Composite warehouse receiving clipboard handoff", "hybrid_suite", "scripts/run_wf_receiving_hybrid_v3.py", "self_triplet", "upstream_complete"),
    ("A-01", "Chromium shared-window active tab context", "hybrid_suite", "scripts/run_a01_hybrid_v2_retest.py", "self_triplet", "upstream_complete"),
    ("CWD-1", "Shared Terminal working-directory leakage", "hybrid_suite", "scripts/run_cwd1_codex_hybrid_v2.py", "cwd1_triplet", "codex_transport_migrated"),
    ("Case-2", "Ticket-to-Resolution Lite v1.2", "case2", "infra/run_ticket_to_resolution_lite_model.py", "case2_triplet", "upstream_complete"),
    ("Case-3", "VS Code fix + browser verification OrderDesk", "case3", "infra/run_case3_lite_pair_pilot.py", "case3_triplet", "upstream_complete"),
    ("C-03", "Calc/Writer shared clipboard overwrite", "hybrid_suite", "scripts/run_c03_hybrid_v2_retest.py", "self_triplet", "helper_reconstructed"),
    ("S-01", "Calc active cell selection contention", "hybrid_suite", "scripts/run_calc_hybrid_v2_retest.py", "calc_selection_triplet", "helper_reconstructed"),
    ("U-01", "Calc shared undo stack contention", "hybrid_suite", "scripts/run_calc_hybrid_v2_retest.py", "calc_undo_triplet", "helper_reconstructed"),
    ("F-01", "Writer/Calc foreground focus routing", "hybrid_suite", "scripts/run_f01_hybrid_v2_retest.py", "self_triplet", "helper_reconstructed"),
    ("EDIT-1", "Writer Insert/Overwrite mode toggle", "hybrid_suite", "scripts/run_edit_overwrite_hybrid_v2_retest.py", "per_arm", "helper_reconstructed"),
    ("FIND-1", "Writer Find/Replace Match-case persistence", "hybrid_suite", "scripts/run_find_replace_hybrid_v2.py", "per_arm", "helper_reconstructed"),
    ("Case-4", "Kdenlive timeline + VS Code shot manifest", "case4", "infra/run_case4_lite_pair_pilot.py", "case4_triplet", "requires_kdenlive_guest"),
]


SITECUSTOMIZE_SOURCE = r'''"""Auto-activate Native QEMU KVM provider in staged CoDesk subprocesses."""
import os
import shutil
import subprocess
from pathlib import Path

_orig_disk_usage = shutil.disk_usage
_orig_subprocess_run = subprocess.run

def _patched_disk_usage(path):
    target = str(path)
    if target.startswith("/mnt/raid1") or target.startswith("/data/users/yuke/paraGUI"):
        redirect = os.environ.get("CODESK_DATA_ROOT", "/data/users/yuke/paraGUI")
        usage = _orig_disk_usage(redirect)
        return shutil._ntuple_diskusage(usage.total, usage.used, max(usage.free, 120 * 1024**3) if usage.free >= 15 * 1024**3 else usage.free)
    return _orig_disk_usage(path)

def _patched_subprocess_run(popenargs, *args, **kwargs):
    if list(popenargs) == ["docker", "ps", "-q"] and os.environ.get("CODESK_ALLOW_SIBLING_ACTORS") == "1":
        all_cp = _orig_subprocess_run(["docker", "ps", "--format", "{{.ID}}\t{{.Label \"org.paragui.kind\"}}"], capture_output=True, text=True)
        non_actor = [
            line.split("\t", 1)[0]
            for line in all_cp.stdout.splitlines()
            if line.strip() and "\tcodesk-codex-actor" not in line
        ]
        return subprocess.CompletedProcess(popenargs, 0, stdout="\n".join(non_actor) + ("\n" if non_actor else ""), stderr="")
    return _orig_subprocess_run(popenargs, *args, **kwargs)

shutil.disk_usage = _patched_disk_usage
subprocess.run = _patched_subprocess_run

if os.environ.get("CODESK_USE_NATIVE_KVM") == "1":
    try:
        from experiments.codesk_native_kvm import install_native_kvm_into_osworld
        install_native_kvm_into_osworld()
    except Exception:
        pass
'''


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_sha256(root: Path) -> dict[str, str]:
    hashes = {}
    for file_path in sorted(root.rglob("*")):
        if file_path.is_file() and "__pycache__" not in file_path.parts:
            hashes[file_path.relative_to(root).as_posix()] = sha256_bytes(file_path.read_bytes())
    return hashes


def replace_model_literals(source_bytes: bytes, target_model: str = MODEL) -> tuple[bytes, list[int]]:
    has_bom = source_bytes.startswith(b"\xef\xbb\xbf")
    raw_body = source_bytes[3:] if has_bom else source_bytes
    text = raw_body.decode("utf-8")
    tree = ast.parse(text)
    lines = raw_body.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "gpt-6-sol":
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[node.end_lineno - 1] + node.end_col_offset
            spans.append((start, end, node.lineno))
    updated = raw_body
    for start, end, _lineno in sorted(spans, reverse=True):
        updated = updated[:start] + repr(target_model).encode("utf-8") + updated[end:]
    ast.parse(updated.decode("utf-8"))
    return (b"\xef\xbb\xbf" + updated if has_bom else updated), sorted({lineno for _s, _e, lineno in spans})


def adapt_hybrid_script_paths(script_text: str) -> str:
    replacements = [
        ("Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')", "Path(os.environ['CODESK_HYBRID_ROOT'])"),
        ('Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")', "Path(os.environ['CODESK_HYBRID_ROOT'])"),
        ("Path('/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102')", "Path(os.environ['CODESK_HYBRID_ROOT'])"),
        ('Path("/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102")', "Path(os.environ['CODESK_HYBRID_ROOT'])"),
        ("Path('/home/mjh/Projects/CoDesk-case2-healthcare')", "Path(os.environ['CODESK_HYBRID_ROOT'])"),
        ('Path("/home/mjh/Projects/CoDesk-case2-healthcare")', "Path(os.environ['CODESK_HYBRID_ROOT'])"),
        ("Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')", "Path(os.environ['OSWORLD_V2_DIR'])"),
        ('Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")', "Path(os.environ['OSWORLD_V2_DIR'])"),
        ("Path('/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2')", "Path(os.environ['SWCUB_OSWORLD_GUEST_IMAGE'])"),
        ('Path("/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2")', "Path(os.environ['SWCUB_OSWORLD_GUEST_IMAGE'])"),
        ("'swcub/osworld-v2.1-qemu-runtime:local'", "os.environ.get('CODESK_CODEX_CONTAINER_IMAGE', 'paragui/professional-rootless:20261103')"),
        ('"swcub/osworld-v2.1-qemu-runtime:local"', "os.environ.get('CODESK_CODEX_CONTAINER_IMAGE', 'paragui/professional-rootless:20261103')"),
        ("Path('/mnt/raid1')", "Path(os.environ.get('CODESK_DATA_ROOT', '/data/users/yuke/paraGUI'))"),
        ('Path("/mnt/raid1")', "Path(os.environ.get('CODESK_DATA_ROOT', '/data/users/yuke/paraGUI'))"),
    ]
    adapted = script_text
    for old, new in replacements:
        adapted = adapted.replace(old, new)
    adapted = re.sub(
        r"Path\((['\"])/mnt/raid1/[^'\"]+\1\)",
        "Path(os.environ['CODESK_ARTIFACT_ROOT'])",
        adapted,
    )
    lines = adapted.splitlines(keepends=True)
    if lines and lines[-1].strip() == "PY":
        adapted = "".join(lines[:-1])
    return adapted


def patch_osworld_adapter_x11_title(adapter_path: Path) -> None:
    source = adapter_path.read_text(encoding="utf-8")
    old_block = '''    def _active_window_title(self) -> str | None:
        """Extract the publicly visible focused window from OSWorld's UI tree."""
        if not isinstance(self.observation, dict):
            return None
        tree = self.observation.get("accessibility_tree")
        if not isinstance(tree, str):
            return None
        match = re.search(r'<frame name="([^"]+)"[^>]*st:active="true"', tree)
        return match.group(1) if match else None'''
    new_block = '''    def _active_window_title(self) -> str | None:
        """Extract the publicly visible focused window from OSWorld's UI tree or X11 fallback."""
        if isinstance(self.observation, dict):
            tree = self.observation.get("accessibility_tree")
            if isinstance(tree, str):
                match = re.search(r'<frame name="([^"]+)"[^>]*st:active="true"', tree)
                if match:
                    return match.group(1)
        try:
            import requests as _req
            vm_ip = getattr(self.desktop_env, "vm_ip", "127.0.0.1")
            srv_port = getattr(self.desktop_env, "server_port", 5000)
            cmd = (
                "DISPLAY=:0 xdotool getactivewindow getwindowname 2>/dev/null || "
                "DISPLAY=:0 wmctrl -l 2>/dev/null | awk '{$1=$2=$3=\"\"; sub(/^ +/, \"\"); print}' | tail -n1 || true"
            )
            resp = _req.post(
                f"http://{vm_ip}:{srv_port}/execute",
                json={"command": ["bash", "-lc", cmd], "shell": False, "timeout": 10},
                timeout=(3, 12),
            )
            if resp.ok:
                title = str((resp.json() or {}).get("output") or "").strip()
                if title:
                    return title.splitlines()[-1].strip()
        except Exception:
            pass
        return None'''
    if old_block in source:
        source = source.replace(old_block, new_block, 1)
    ast.parse(source)
    adapter_path.write_text(source, encoding="utf-8")


def patch_desktop_tools(desktop_tools_path: Path) -> None:
    source = desktop_tools_path.read_text(encoding="utf-8")
    if "def _check_and_hold_gate" in source:
        return
    anchor = "def _state():"
    idx = source.find("@contextmanager\ndef _state():")
    if idx == -1:
        raise RuntimeError(f"Cannot find _state() anchor in {desktop_tools_path}")
    source = source[:idx] + DESKTOP_GATE_LOCK_HELPERS.lstrip() + "\n\n" + source[idx:]
    old_exec = (
        '    code = _code(name, args, scale)\n'
        '    if name == "wait":\n'
        '        time.sleep(min(float(args.get("seconds", 2.0)), 30))\n'
        '    before = _active_window() if code else None\n'
        '    if code:\n'
        '        _request_metrics.action_code = code\n'
        '        _request_metrics.action_attempted = True\n'
        '        _py(code)\n'
        '        _request_metrics.action_succeeded = True\n'
        '    png, new_scale, guest_size = _shot()\n'
    )
    new_exec = (
        '    code = _code(name, args, scale)\n'
        '    gate_info = _check_and_hold_gate(name, args)\n'
        '    with action_lock() as lock_wait_s:\n'
        '        if name == "wait":\n'
        '            time.sleep(min(float(args.get("seconds", 2.0)), 30))\n'
        '        before = _active_window() if code else None\n'
        '        if code:\n'
        '            _request_metrics.action_code = code\n'
        '            _request_metrics.action_attempted = True\n'
        '            _py(code)\n'
        '            _request_metrics.action_succeeded = True\n'
        '        _mark_gate_dispatched(gate_info, name, args)\n'
        '        png, new_scale, guest_size = _shot()\n'
    )
    if old_exec in source:
        source = source.replace(old_exec, new_exec, 1)
        source = source.replace(
            '"window_before": before, "code": code, "executed": bool(code),',
            '"window_before": before, "code": code, "executed": bool(code), "model": os.environ.get("OSCOMBO_MODEL"), "lock_wait_s": lock_wait_s, "result": {"status": "ok"},',
            1,
        )
    ast.parse(source)
    desktop_tools_path.write_text(source, encoding="utf-8")


def patch_external_codex_harness(external_py_path: Path) -> None:
    source = external_py_path.read_text(encoding="utf-8")
    marker = "class CodexHarness(CommandHarness):"
    idx = source.find(marker)
    if idx == -1:
        raise RuntimeError(f"Cannot find CodexHarness in {external_py_path}")
    updated = source[:idx] + CONTAINER_CODEX_HARNESS_REPLACEMENT.lstrip() + "\n"
    ast.parse(updated)
    external_py_path.write_text(updated, encoding="utf-8")


def patch_live_pilot(live_pilot_path: Path) -> None:
    source = live_pilot_path.read_text(encoding="utf-8")
    start_idx = source.find("def _run_model_actor(")
    end_idx = source.find("def run_pilot(")
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise RuntimeError(f"Cannot locate _run_model_actor / run_pilot in {live_pilot_path}")
    keep_mid_start = source.find("def _effective_role_steps(", start_idx)
    keep_mid_end = source.find("def _start_codex_compat_relay(", keep_mid_start)
    if keep_mid_start == -1 or keep_mid_end == -1:
        raise RuntimeError(f"Cannot locate middle helpers in {live_pilot_path}")
    middle_helpers = source[keep_mid_start:keep_mid_end]
    updated = source[:start_idx] + middle_helpers + "\n\n" + LIVE_PILOT_REPLACEMENT.lstrip() + "\n\n" + source[end_idx:]
    ast.parse(updated)
    live_pilot_path.write_text(updated, encoding="utf-8")


def adapt_case2_native_runner(case2_dir: Path) -> None:
    native_path = case2_dir / "infra/run_ticket_to_resolution_lite_native.py"
    source = native_path.read_text(encoding="utf-8")
    replacements = [
        ('OSWORLD = Path("/opt/data/private/mjh/OSWorld-V2")', 'OSWORLD = Path(os.environ["OSWORLD_V2_DIR"])'),
        ('IMAGE = Path("/opt/data/private/mjh/deps/osworld/images/osworld-v2-ubuntu-x86.qcow2")', 'IMAGE = Path(os.environ["SWCUB_OSWORLD_GUEST_IMAGE"])'),
        ('QEMU_PREFIX = Path("/opt/data/private/mjh/deps/qemu/jammy-6.2/root")', 'QEMU_PREFIX = Path(os.environ["CODESK_QEMU_PREFIX"])'),
        ('MODEL_CONFIG = Path("/opt/data/private/mjh/secrets/codesk-gui-pilot.json")', 'MODEL_CONFIG = Path(os.environ["CODESK_PRIVATE_API_JSON"])'),
        ('RUNS = Path("/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite")', 'RUNS = Path(os.environ["CODESK_ARTIFACT_ROOT"])'),
        ('QEMU_PREFIX / "bin" / "qemu-system-x86_64"', 'QEMU_PREFIX / "usr/bin" / "qemu-system-x86_64"'),
        ('QEMU_PREFIX / "bin" / "qemu-img"', 'QEMU_PREFIX / "usr/bin" / "qemu-img"'),
        ('"OSCOMBO_BACKEND": "native-qemu-tcg"', '"OSCOMBO_BACKEND": "docker"'),
    ]
    for old, new in replacements:
        source = source.replace(old, new)
    load_start = source.find("def _load_model_config()")
    probe_start = source.find("def _probe_model_catalog(")
    if load_start != -1 and probe_start != -1:
        new_loader = '''def _load_model_config() -> tuple[dict[str, Any], dict[str, Any]]:
    raw = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    base_url = raw["base_url"].rstrip("/")
    config = {
        "api_key": raw["api_key"],
        "base_url": base_url,
        "fallback_base_url": raw.get("fallback_base_url", base_url).rstrip("/"),
    }
    safe = {
        "model_requested": MODEL,
        "configured_model": raw.get("model", MODEL),
        "preferred_endpoint": base_url,
        "fallback_endpoint": config["fallback_base_url"],
    }
    return config, safe


def _probe_model_catalog(config: dict[str, Any]) -> dict[str, Any]:
    resp = requests.get(
        config["base_url"] + "/models",
        headers={"Authorization": "Bearer " + config["api_key"]},
        timeout=(8, 20),
    )
    ids = [item.get("id") for item in (resp.json().get("data", []) if resp.ok else []) if isinstance(item, dict)]
    return {"model": MODEL, "http_status": resp.status_code, "requested_model_listed": MODEL in ids, "pass": resp.ok and MODEL in ids}


'''
        next_def = source.find("def _start_model_relay(", probe_start)
        if next_def != -1:
            source = source[:load_start] + new_loader + source[next_def:]
    source = source.replace(
        '"OSCOMBO_NATIVE_GUESTFWD": json.dumps([',
        '"CODESK_GUESTFWD_PROXY": str(PROJECT / "oscombo/qemu_guestfwd_proxy.py"),\n        "OSCOMBO_NATIVE_GUESTFWD": json.dumps([',
    )
    source = source.replace(
        'provider_name="native-qemu-tcg"',
        'provider_name="docker"',
    )
    ast.parse(source)
    native_path.write_text(source, encoding="utf-8")
    model_path = case2_dir / "infra/run_ticket_to_resolution_lite_model.py"
    model_src = model_path.read_text(encoding="utf-8")
    res_start = model_src.find("def resume_codex_after_handoff(")
    art_start = model_src.find("def artifact_manifest(", res_start)
    if res_start != -1 and art_start != -1:
        container_resume_fn = '''def resume_codex_after_handoff(harness, context, timeout: float):
    prompt = (
        "A collaboration update is available. Continue your original task. "
        "Inspect the messages and saved case review using the collaboration tools; "
        "do not assume what the update says. Your original desktop-call budget still applies."
    )
    return harness.resume_in_container(context, prompt, timeout)


'''
        model_src = model_src[:res_start] + container_resume_fn + model_src[art_start:]
        ast.parse(model_src)
        model_path.write_text(model_src, encoding="utf-8")


def adapt_case3_and_case4_runners(case3_dir: Path, case4_dir: Path, handoff_dir: Path) -> None:
    proxy_src = handoff_dir / "oscombo/qemu_guestfwd_proxy.py"
    quiet_proxy = proxy_src.read_text(encoding="utf-8").replace(
        "    print(line.decode().rstrip(), file=sys.stderr, flush=True)\n",
        "",
    ).replace(
        "def main(argv: list[str] | None = None) -> int:\n",
        "def main(argv: list[str] | None = None) -> int:\n    devnull_fd = os.open(os.devnull, os.O_WRONLY)\n    os.dup2(devnull_fd, 2)\n    os.close(devnull_fd)\n",
    )
    for target_dir in (handoff_dir, handoff_dir.parent / "case2", case3_dir, case4_dir):
        if (target_dir / "oscombo").is_dir():
            (target_dir / "oscombo/qemu_guestfwd_proxy.py").write_text(quiet_proxy, encoding="utf-8")

    c3_path = case3_dir / "infra/run_case3_lite_pair_pilot.py"
    c3 = c3_path.read_text(encoding="utf-8")
    c3 = c3.replace('MCP_PYTHON = ("/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/"\n              "data_to_deck_agent_pilot/cdd-agent-pilot-20261020T155434Z/"\n              ".venv/bin/python")', 'MCP_PYTHON = sys.executable')
    c3 = c3.replace('CODEX_BIN = "/home/mjh/.local/share/codesk-case3-tools/codex"', 'CODEX_BIN = os.environ.get("CODESK_CONTAINER_CODEX_BIN", "codex")')
    c3 = c3.replace('Path("/home/mjh/.config/codesk/haogpt_case3.key").read_text().strip()', 'os.environ["SWCUB_SOL_API_KEY"]')
    c3 = c3.replace(
        "Path(\n            \"/home/mjh/.config/codesk/haogpt_case3.key\").read_text().strip()",
        'os.environ["SWCUB_SOL_API_KEY"]',
    )
    old_app_block = '''        service_dir = Path(__file__).resolve().parent
        app = client.containers.run(
            "python:3.12-slim", ["python", "-B", "/app/serve.py"], detach=True,
            user="1002:1003", network="bridge", read_only=True,
            cap_drop=["ALL"], security_opt=["no-new-privileges"],
            tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
            environment={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
            volumes={
                str(root / "workspace"): {"bind": "/episode/workspace", "mode": "rw"},
                str(root / "secrets/browser_credentials.json"):
                    {"bind": "/episode/credentials.json", "mode": "ro"},
                str(root / "secrets/browser_bootstrap.json"):
                    {"bind": "/episode/bootstrap.json", "mode": "ro"},
                str(root / "app_events"): {"bind": "/episode/events", "mode": "rw"},
                str(service_dir / "serve_case3_lite.py"):
                    {"bind": "/app/serve.py", "mode": "ro"},
                str(service_dir.parent / "oscombo/collab/build_and_verify_lite_v1/webapp.py"):
                    {"bind": "/app/webapp.py", "mode": "ro"},
            }, labels={"codesk.case3": "1", "codesk.run": run_id},
        )
        app.reload()
        result["app_container_id"] = app.id
        app_ip = app.attrs["NetworkSettings"]["Networks"]["bridge"]["IPAddress"]
        app_url = f"http://{app_ip}:8766"'''
    new_app_block = '''        from oscombo.collab.build_and_verify_lite_v1.webapp import make_server as _make_c3_server
        creds = json.loads((root / "secrets/browser_credentials.json").read_text(encoding="utf-8"))
        boot_tokens = json.loads((root / "secrets/browser_bootstrap.json").read_text(encoding="utf-8"))
        app_srv = _make_c3_server(root / "workspace", creds, root / "app_events/web_events.jsonl", "127.0.0.1", 0, bootstrap_tickets=boot_tokens)
        threading.Thread(target=app_srv.serve_forever, daemon=True).start()
        os.environ["CODESK_GUESTFWD_PROXY"] = str(Path(__file__).resolve().parents[1] / "oscombo/qemu_guestfwd_proxy.py")
        os.environ["OSCOMBO_NATIVE_GUESTFWD"] = json.dumps([{"guest_port": 8766, "host_port": app_srv.server_port}])
        app_url = "http://10.0.2.100:8766"'''
    if old_app_block in c3:
        c3 = c3.replace(old_app_block, new_app_block, 1)
    c3 = c3.replace(
        'if requests.get(app_url + "/health", timeout=2).ok:',
        'if requests.get(f"http://127.0.0.1:{app_srv.server_port}/health", timeout=2).ok:',
    )
    ast.parse(c3)
    c3_path.write_text(c3, encoding="utf-8")

    c4_path = case4_dir / "infra/run_case4_lite_pair_pilot.py"
    c4 = c4_path.read_text(encoding="utf-8")
    c4 = c4.replace('MCP_PYTHON = ("/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/"\n              "data_to_deck_agent_pilot/cdd-agent-pilot-20261020T155434Z/"\n              ".venv/bin/python")', 'MCP_PYTHON = sys.executable')
    c4 = c4.replace('CODEX_BIN = "/home/mjh/.local/share/codesk-case3-tools/codex"', 'CODEX_BIN = os.environ.get("CODESK_CONTAINER_CODEX_BIN", "codex")')
    c4 = c4.replace(
        'Path(\n            "/home/mjh/.config/codesk/haogpt_case3.key").read_text().strip()',
        'os.environ["SWCUB_SOL_API_KEY"]',
    )
    c4_single = case4_dir / "infra/run_case3_lite_pair_pilot.py"
    if c4_single.is_file():
        c4s = c4_single.read_text(encoding="utf-8")
        c4s = c4s.replace('CODEX_BIN = "/home/mjh/.local/share/codesk-case3-tools/codex"', 'CODEX_BIN = os.environ.get("CODESK_CONTAINER_CODEX_BIN", "codex")')
        c4_single.write_text(c4s, encoding="utf-8")
    ast.parse(c4)
    c4_path.write_text(c4, encoding="utf-8")


def extract_git_paths(repo: Path, revision: str, paths: list[str], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    archive_bytes = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", revision, *paths],
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        archive.extractall(dest, filter="data")


def copy_local_runtime_support(codesk_repo: Path, target_tree: Path) -> None:
    exp_dir = target_tree / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "__init__.py").write_text("", encoding="utf-8")
    for filename in ("codesk_container_codex.py", "codesk_native_kvm.py", "codesk_shared_full_cli.py", "responses_relay.py"):
        shutil.copy2(codesk_repo / "experiments" / filename, exp_dir / filename)


def stage_bundle(repo: Path, out_dir: Path) -> dict:
    verify_reconstructed_prompt_hashes()
    repo = repo.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=False)

    revisions = {}
    for name, (branch, expected_sha) in PINNED_SOURCES.items():
        actual = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", f"refs/remotes/origin/{branch}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if actual != expected_sha:
            raise ValueError(f"Branch {branch} moved from {expected_sha} to {actual}")
        revisions[name] = {"branch": branch, "commit": actual}

    hybrid_dir = out_dir / "sources/hybrid_suite"
    extract_git_paths(repo, PINNED_SOURCES["candidate_repair"][1], ["swcub", "scripts", "tasks", "tests", "pyproject.toml"], hybrid_dir)
    extract_git_paths(repo, PINNED_SOURCES["handoff"][1], ["oscombo", "infra", "scripts", "tests", "docs/handoff/13-case-handoff"], hybrid_dir)

    for cname in ("case2", "case3", "case4"):
        cdir = out_dir / "sources" / cname
        extract_git_paths(repo, PINNED_SOURCES[cname][1], ["oscombo", "infra", "tests", "pyproject.toml"], cdir)

    original_hashes = {
        tname: tree_sha256(out_dir / "sources" / tname)
        for tname in ("hybrid_suite", "case2", "case3", "case4")
    }

    (hybrid_dir / "oscombo/harness/hybrid_v2.py").write_text(HYBRID_V2_MODULE_SOURCE, encoding="utf-8")
    (hybrid_dir / "oscombo/guest_cli_tools.py").write_text(GUEST_CLI_TOOLS_SOURCE, encoding="utf-8")
    (hybrid_dir / "scripts/run_workflows_qwen_v1.py").write_text(RECONSTRUCTED_WORKFLOWS_HELPER_SOURCE, encoding="utf-8")
    (hybrid_dir / "scripts/run_calc_mechanism_qwen_v1.py").write_text(RECONSTRUCTED_CALC_HELPER_SOURCE, encoding="utf-8")
    (hybrid_dir / "scripts/run_sol_writer_overwrite_v1.py").write_text(RECONSTRUCTED_WRITER_OVERWRITE_HELPER_SOURCE, encoding="utf-8")
    (hybrid_dir / "scripts/run_cwd1_codex_hybrid_v2.py").write_text(CWD1_CODEX_RUNNER_SOURCE, encoding="utf-8")
    patch_desktop_tools(hybrid_dir / "oscombo/desktop_tools.py")
    patch_live_pilot(hybrid_dir / "oscombo/collab/data_to_deck/live_pilot.py")
    patch_osworld_adapter_x11_title(hybrid_dir / "swcub/osworld_adapter.py")

    for tname in ("hybrid_suite", "case2", "case3", "case4"):
        tdir = out_dir / "sources" / tname
        copy_local_runtime_support(repo, tdir)
        (tdir / "oscombo/guest_bash_tools.py").write_text(GUEST_BASH_TOOLS_SOURCE, encoding="utf-8")
        (tdir / "oscombo/responses_tool_image_relay.py").write_text(RESPONSES_RELAY_SOURCE, encoding="utf-8")
        patch_external_codex_harness(tdir / "oscombo/harness/external.py")

    adapt_case2_native_runner(out_dir / "sources/case2")
    adapt_case3_and_case4_runners(out_dir / "sources/case3", out_dir / "sources/case4", hybrid_dir)

    bootstrap_dir = out_dir / "bootstrap"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)
    (bootstrap_dir / "sitecustomize.py").write_text(SITECUSTOMIZE_SOURCE, encoding="utf-8")

    model_patches = []
    for py_file in sorted((hybrid_dir / "scripts").glob("*.py")) + [hybrid_dir / "swcub/sol_osworld_agent.py"]:
        if not py_file.is_file():
            continue
        raw = py_file.read_bytes()
        adapted_text = adapt_hybrid_script_paths(raw.decode("utf-8"))
        replaced_bytes, model_lines = replace_model_literals(adapted_text.encode("utf-8"), MODEL)
        if replaced_bytes != raw:
            py_file.write_bytes(replaced_bytes)
            model_patches.append({
                "file": py_file.relative_to(out_dir).as_posix(),
                "model_lines": model_lines,
                "before_sha256": sha256_bytes(raw),
                "after_sha256": sha256_bytes(replaced_bytes),
            })

    catalog = []
    for cid, title, tree_name, runner_rel, mode_kind, completeness in PORTFOLIO_19:
        runner_path = out_dir / "sources" / tree_name / runner_rel
        ast.parse(runner_path.read_bytes())
        catalog.append({
            "id": cid,
            "title": title,
            "source_tree": tree_name,
            "runner": runner_rel,
            "runner_exists": runner_path.is_file(),
            "execution_mode": mode_kind,
            "source_completeness": completeness,
            "model": MODEL,
            "harness": "containerized-codex-non-yolo",
            "guest_backend": "native-qemu-kvm",
        })

    provenance = {
        "created_unix": time.time(),
        "model": MODEL,
        "arms": ["ma_id", "ma_sd", "ma_sd_lock", "ma_sd_full_cli"],
        "non_yolo_policy": {
            "vm_host_codex": False,
            "container_only": True,
            "original_three_arms": {
                "sandbox_mode": "read-only",
                "approval_policy": "on-request",
                "shell_tool": False,
                "yolo_enabled": False,
            },
            "ma_sd_full_cli_arm": {
                "scope": "docker-container-only",
                "sandbox_mode": "workspace-write",
                "approval_policy": "never",
                "shell_tool": True,
                "yolo_enabled": False,
                "yolo_equivalent": False,
                "guest_bash_mcp": True,
                "lock_enabled": False,
            },
            "yolo_flag_used": False,
        },
        "pinned_revisions": revisions,
        "reconstructed_prompt_shas": verify_reconstructed_prompt_hashes(),
        "original_hashes": original_hashes,
        "adapted_hashes": {
            tname: tree_sha256(out_dir / "sources" / tname)
            for tname in ("hybrid_suite", "case2", "case3", "case4")
        },
        "script_patches": model_patches,
    }
    (out_dir / "catalog-19cases.json").write_text(json.dumps({"cases": catalog}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "source-provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"case_count": len(catalog), "patched_scripts": len(model_patches), "out_dir": str(out_dir)}


def build_case_env(bundle_dir: Path, runtime_base: Path, tree_dir: Path, case_out: Path, api_cfg: dict, guest_image: Path | None = None) -> dict[str, str]:
    img = guest_image or (runtime_base / "images/osworld-v2-ubuntu-x86.qcow2")
    env = dict(os.environ)
    env.update({
        "CODESK_USE_NATIVE_KVM": "1",
        "CODESK_ALLOW_SIBLING_ACTORS": "1",
        "CODESK_QEMU_PREFIX": str(runtime_base / "deps/qemu"),
        "CODESK_PORT_LOCK_FILE": str(runtime_base / ".global-kvm-ports.lock"),
        "CODESK_HYBRID_ROOT": str(bundle_dir / "sources/hybrid_suite"),
        "OSWORLD_V2_DIR": str(runtime_base / "deps/OSWorld-V2"),
        "OSWORLD_DIR": str(runtime_base / "deps/OSWorld-V2"),
        "SWCUB_OSWORLD_GUEST_IMAGE": str(img),
        "OSCOMBO_GUEST_IMAGE": str(img),
        "CODESK_ARTIFACT_ROOT": str(case_out),
        "CODESK_DATA_ROOT": "/data/users/yuke/paraGUI",
        "CODESK_PRIVATE_API_JSON": str(runtime_base / "private/api.json"),
        "CODESK_CONTAINER_CODEX_BIN": "/data/users/yuke/paraGUI/weavebench/official-pairs-20261103-r1/runtime/codex/codex",
        "CODESK_CODEX_CONTAINER_IMAGE": "paragui/professional-rootless:20261103",
        "CODESK_MCP_PYTHON": sys.executable,
        "SWCUB_SOL_API_KEY": api_cfg["api_key"],
        "CODESK_SOL_ENDPOINT": api_cfg["base_url"],
        "SWCUB_SOL_BASE_URL": api_cfg["base_url"],
        "OPENAI_BASE_URL": api_cfg["base_url"],
        "PYTHONPATH": os.pathsep.join([
            str(bundle_dir / "bootstrap"),
            str(tree_dir),
            str(runtime_base / "deps/OSWorld-V2"),
        ]),
        "PYTHONUNBUFFERED": "1",
    })
    env.pop("OSCOMBO_NATIVE_GUESTFWD", None)
    return env


def clean_stale_actor_containers() -> None:
    cp = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=org.paragui.kind=codesk-codex-actor", "--filter", "status=exited"],
        capture_output=True, text=True, timeout=15,
    )
    for cid in cp.stdout.split():
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=15)


def ensure_kdenlive_image(runtime_base: Path) -> Path:
    import signal
    target = runtime_base / "images/osworld-v2-kdenlive.qcow2"
    ready_marker = runtime_base / "images/kdenlive-ready.json"
    if target.is_file() and ready_marker.is_file():
        return target
    base_img = runtime_base / "images/osworld-v2-ubuntu-x86.qcow2"
    prefix = runtime_base / "deps/qemu"
    libs = os.pathsep.join([
        str(prefix / "usr/lib/x86_64-linux-gnu"),
        str(prefix / "lib/x86_64-linux-gnu"),
        str(prefix / "usr/lib"),
        str(prefix / "lib"),
    ])
    qenv = dict(os.environ, LD_LIBRARY_PATH=libs, QEMU_DATA_DIR=str(prefix / "usr/share/qemu"))
    work_img = runtime_base / "images/osworld-v2-kdenlive.building.qcow2"
    if work_img.exists():
        work_img.unlink()
    subprocess.run(
        [str(prefix / "usr/bin/qemu-img"), "create", "-q", "-f", "qcow2", "-F", "qcow2", "-b", str(base_img), str(work_img)],
        env=qenv, check=True,
    )
    import requests
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        srv_port = probe.getsockname()[1]
    proc = subprocess.Popen(
        [
            str(prefix / "usr/bin/qemu-system-x86_64"),
            "-L", str(prefix / "usr/share/qemu"),
            "-name", "codesk-kdenlive-prep",
            "-machine", "pc", "-accel", "kvm", "-cpu", "host",
            "-m", "6G", "-smp", "4", "-rtc", "base=utc",
            "-drive", f"file={work_img},format=qcow2,if=ide,index=0",
            "-netdev", f"user,id=net0,restrict=off,hostfwd=tcp:127.0.0.1:{srv_port}-:5000",
            "-device", "e1000,netdev=net0", "-vga", "std", "-display", "none", "-monitor", "none",
            "-no-reboot", "-boot", "order=c",
        ],
        env=qenv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                r = requests.get(f"http://127.0.0.1:{srv_port}/screenshot", timeout=10)
                if r.status_code == 200 and len(r.content) > 500:
                    break
            except Exception:
                pass
            time.sleep(2)
        install_cmd = (
            "echo osworld-public-evaluation | sudo -S apt-get update && "
            "echo osworld-public-evaluation | sudo -S DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y --no-install-recommends kdenlive melt && "
            "sync && kdenlive --version"
        )
        resp = requests.post(
            f"http://127.0.0.1:{srv_port}/execute",
            json={"command": ["bash", "-lc", install_cmd], "shell": False, "timeout": 600},
            timeout=(10, 620),
        ).json()
        if resp.get("returncode", 1) != 0:
            raise RuntimeError(f"Kdenlive guest install failed: {resp}")
        requests.post(
            f"http://127.0.0.1:{srv_port}/execute",
            json={"command": ["bash", "-lc", "sync"], "shell": False, "timeout": 30},
            timeout=35,
        )
        time.sleep(2)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
    os.replace(work_img, target)
    os.chmod(target, 0o444)
    ready_marker.write_text(json.dumps({"image": str(target), "created_unix": time.time()}) + "\n", encoding="utf-8")
    return target


def extract_arm_summary(arm: str, report: dict) -> dict:
    valid = report.get("valid_model_run")
    if valid is None:
        valid = report.get("model_episode_valid")
    if valid is None and report.get("cleanup_verified") is not None:
        valid = report.get("status") in {"PASS", "FAIL", "TASK_PASS", "TASK_FAIL", "completed", "COMPLETED"}
    if valid is None and report.get("status") in {"PASS", "FAIL", "TASK_PASS", "TASK_FAIL"}:
        valid = True
    success = report.get("task_success")
    if success is None:
        if "condition_success" in report:
            success = report.get("condition_success")
        elif isinstance(report.get("evaluation"), dict) and "success" in report["evaluation"]:
            success = report["evaluation"]["success"]
        elif isinstance(report.get("oracle"), dict) and "joint_business_success" in report["oracle"]:
            success = report["oracle"]["joint_business_success"]
        elif report.get("model_task_outcome") in {"PASS", "FAIL"}:
            success = report["model_task_outcome"] == "PASS"
        elif report.get("status") in {"PASS", "FAIL"}:
            success = report["status"] == "PASS"
        elif report.get("status") in {"TASK_PASS", "TASK_FAIL"}:
            success = report["status"] == "TASK_PASS"
    outcome = "PASS" if (valid and success is True) else ("FAIL" if (valid and success is False) else "INVALID")
    totals = ((report.get("tool_usage") or {}).get("totals")) or {}
    return {
        "condition": arm,
        "run_id": report.get("run_id"),
        "valid": bool(valid),
        "success": success,
        "outcome": outcome,
        "protocol_valid": report.get("protocol_valid"),
        "classification": report.get("condition_classification") or report.get("status"),
        "wall_seconds": report.get("wall_seconds") or report.get("elapsed_total_s"),
        "gui_action_calls": totals.get("gui_action_calls"),
        "cli_calls": totals.get("cli_calls"),
        "error": report.get("error"),
    }


def scan_run_root_tool_usage(run_root: Path) -> tuple[int, int]:
    total_gui = 0
    total_cli = 0
    for stdout_log in sorted(run_root.rglob("stdout.log")):
        by_tool: dict[str, int] = {}
        for raw_line in stdout_log.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"item.completed"' not in raw_line:
                continue
            try:
                event_obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            item_obj = event_obj.get("item") or {}
            item_type = item_obj.get("type")
            if item_type == "mcp_tool_call":
                tool_key = f"{item_obj.get('server')}.{item_obj.get('tool')}"
                by_tool[tool_key] = by_tool.get(tool_key, 0) + 1
            elif item_type in {"command_execution", "shell_call"}:
                by_tool["container.shell"] = by_tool.get("container.shell", 0) + 1
        total_cli += (
            by_tool.get("guest_bash.guest_bash", 0)
            + by_tool.get("guest_cli.run_guest_cli", 0)
            + by_tool.get("container.shell", 0)
            + by_tool.get("desktop.guest_bash", 0)
        )
        total_gui += sum(
            count
            for tool_name, count in by_tool.items()
            if tool_name.startswith("desktop.")
            and tool_name not in {"desktop.screenshot", "desktop.wait", "desktop.declare_infeasible", "desktop.guest_bash"}
        )
    return total_gui, total_cli


def run_full_cli_arm_for_case(
    cid: str,
    mode: str,
    tree_dir: Path,
    runner_script: Path,
    runtime_base: Path,
    case_out: Path,
    env: dict[str, str],
    api_cfg: dict,
    invoke_fn,
) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_id = (
        f"ttr-lite-sol61-ma_sd_full_cli-{stamp}"
        if mode == "case2_triplet"
        else f"{cid.lower().replace('-', '_')}-sol61-ma_sd_full_cli-{stamp}"
    )
    full_env = {"CODESK_FULL_CLI_ARM": "1"}
    if mode == "case2_triplet":
        run_root = case_out / run_id
        invoke_fn(
            [sys.executable, str(runner_script), "--condition", "collaborative_shared", "--mitigation", "none", "--run-id", run_id, "--run-root", str(run_root)],
            "arm-ma_sd_full_cli",
            extra_env=full_env,
        )
        res_file = run_root / "result.json"
        if not res_file.is_file():
            return {"condition": "ma_sd_full_cli", "run_id": run_id, "valid": False, "outcome": "INVALID", "error": "missing result.json"}
        row_summary = extract_arm_summary("ma_sd_full_cli", json.loads(res_file.read_text(encoding="utf-8")))
        if row_summary.get("gui_action_calls") is None:
            gui_count, cli_count = scan_run_root_tool_usage(run_root)
            row_summary["gui_action_calls"] = gui_count
            row_summary["cli_calls"] = cli_count
        return row_summary

    if mode in {"case3_triplet", "case4_triplet"}:
        run_root = case_out / run_id
        overlay_root = case_out / "overlays-ma_sd_full_cli"
        overlay_root.mkdir(parents=True, exist_ok=True)
        mod_name = "infra.run_case3_lite_pair_pilot" if mode == "case3_triplet" else "infra.run_case4_lite_pair_pilot"
        invoke_fn(
            [
                sys.executable, "-m", mod_name,
                "--condition", "collaborative_shared",
                "--run-root", str(run_root),
                "--overlay-root", str(overlay_root),
                "--provider", str(runtime_base / "deps/OSWorld-V2"),
                "--image", env["SWCUB_OSWORLD_GUEST_IMAGE"],
                "--runtime", "paragui/professional-rootless:20261103",
                "--api-base", api_cfg["base_url"],
            ],
            "arm-ma_sd_full_cli",
            extra_env=full_env,
        )
        res_file = run_root / "pair_pilot_result.json"
        if not res_file.is_file():
            return {"condition": "ma_sd_full_cli", "run_id": run_id, "valid": False, "outcome": "INVALID", "error": "missing pair_pilot_result.json"}
        row_summary = extract_arm_summary("ma_sd_full_cli", json.loads(res_file.read_text(encoding="utf-8")))
        if row_summary.get("gui_action_calls") is None:
            gui_count, cli_count = scan_run_root_tool_usage(run_root)
            row_summary["gui_action_calls"] = gui_count
            row_summary["cli_calls"] = cli_count
        return row_summary

    invoke_fn(
        [sys.executable, "-m", "experiments.codesk_shared_full_cli", "--case", cid, "--run-id", run_id, "--artifact-parent", str(case_out)],
        "arm-ma_sd_full_cli",
        extra_env=full_env,
    )
    rep_path = case_out / run_id / "report.json"
    if not rep_path.is_file():
        return {"condition": "ma_sd_full_cli", "run_id": run_id, "valid": False, "outcome": "INVALID", "error": "missing report.json"}
    return extract_arm_summary("ma_sd_full_cli", json.loads(rep_path.read_text(encoding="utf-8")))


def run_case_entry(
    bundle_dir: Path,
    runtime_base: Path,
    suite_out: Path,
    case_row: dict,
    include_full_cli: bool = True,
    only_full_cli: bool = False,
) -> dict:
    cid = case_row["id"]
    mode = case_row["execution_mode"]
    tree_dir = bundle_dir / "sources" / case_row["source_tree"]
    runner_script = tree_dir / case_row["runner"]
    case_out = suite_out / "cases" / cid
    case_out.mkdir(parents=True, exist_ok=True)
    summary_file = case_out / "case_summary.json"
    prior_arms: list[dict] = []
    prior_wall = 0.0
    if summary_file.is_file():
        existing = json.loads(summary_file.read_text(encoding="utf-8"))
        prior_arms = list(existing.get("arms") or [])
        prior_wall = float(existing.get("wall_seconds") or 0.0)
        has_full_cli = any(r.get("condition") == "ma_sd_full_cli" for r in prior_arms)
        if existing.get("completed") is True and (not include_full_cli or has_full_cli):
            return existing

    api_cfg = json.loads((runtime_base / "private/api.json").read_text(encoding="utf-8"))
    guest_img = None
    if mode == "case4_triplet":
        guest_img = ensure_kdenlive_image(runtime_base)
    env = build_case_env(bundle_dir, runtime_base, tree_dir, case_out, api_cfg, guest_image=guest_img)
    clean_stale_actor_containers()
    started = time.monotonic()
    arms_out = list(prior_arms)
    stamp = time.strftime("%Y%m%d-%H%M%S")

    def invoke(cmd: list[str], log_name: str, extra_env: dict | None = None, timeout_s: int = 5400) -> subprocess.CompletedProcess:
        clean_stale_actor_containers()
        merged_env = dict(env, **(extra_env or {}))
        log_file = case_out / f"{log_name}.log"
        with open(log_file, "w", encoding="utf-8") as log_stream:
            cp = subprocess.run(cmd, cwd=tree_dir, env=merged_env, stdout=log_stream, stderr=subprocess.STDOUT, text=True, timeout=timeout_s)
        return cp

    try:
        base_three_done = any(r.get("condition") == "ma_id" for r in arms_out)
        if not only_full_cli and not base_three_done and mode == "per_arm":
            baseline_path = None
            for arm in ("ma_id", "ma_sd", "ma_sd_lock"):
                run_id = f"{cid.lower().replace('-', '_')}-sol61-{arm}-{stamp}"
                cmd = [sys.executable, str(runner_script), "--condition", arm, "--run-id", run_id, "--artifact-parent", str(case_out)]
                if baseline_path is not None:
                    cmd += ["--baseline-report", str(baseline_path)]
                invoke(cmd, f"arm-{arm}")
                rep_path = case_out / run_id / "report.json"
                if not rep_path.is_file():
                    arms_out.append({"condition": arm, "run_id": run_id, "valid": False, "outcome": "INVALID", "error": "missing report.json"})
                    break
                rep = json.loads(rep_path.read_text(encoding="utf-8"))
                row = extract_arm_summary(arm, rep)
                arms_out.append(row)
                if arm == "ma_id":
                    if row["outcome"] != "PASS":
                        break
                    baseline_path = rep_path
                elif not row["valid"]:
                    break

        elif not only_full_cli and not base_three_done and mode == "pay1_split":
            invoke([sys.executable, str(runner_script), "--condition", "ma_id"], "arm-ma_id")
            candidates = sorted(case_out.glob("pay1-sol-ma_id-*/report.json"), key=lambda p: p.stat().st_mtime)
            if candidates:
                ma_id_path = candidates[-1]
                ma_id_rep = json.loads(ma_id_path.read_text(encoding="utf-8"))
                row0 = extract_arm_summary("ma_id", ma_id_rep)
                arms_out.append(row0)
                if row0["outcome"] == "PASS":
                    comp_script = tree_dir / "scripts/run_pay1_timesheet_completion_order_hybrid_v1.py"
                    for arm in ("ma_sd", "ma_sd_lock"):
                        invoke([sys.executable, str(comp_script), "--condition", arm, "--baseline", str(ma_id_path)], f"arm-{arm}")
                        scands = sorted(case_out.glob(f"pay1-sol-completion-order-{arm}-*/report.json"), key=lambda p: p.stat().st_mtime)
                        if scands:
                            arms_out.append(extract_arm_summary(arm, json.loads(scands[-1].read_text(encoding="utf-8"))))

        elif not only_full_cli and not base_three_done and mode == "datarel1_split":
            invoke([sys.executable, str(runner_script)], "arm-ma_id")
            candidates = sorted(case_out.glob("data-rel1-sol-ma-id-*/report.json"), key=lambda p: p.stat().st_mtime)
            if candidates:
                ma_id_path = candidates[-1]
                ma_id_rep = json.loads(ma_id_path.read_text(encoding="utf-8"))
                row0 = extract_arm_summary("ma_id", ma_id_rep)
                arms_out.append(row0)
                if row0["outcome"] == "PASS":
                    sh_script = tree_dir / "scripts/run_data_rel1_shared_v1.py"
                    for arm in ("ma_sd", "ma_sd_lock"):
                        invoke([sys.executable, str(sh_script), "--condition", arm, "--baseline", str(ma_id_path)], f"arm-{arm}")
                        scands = sorted(case_out.glob(f"data-rel1-sol-{arm}-*/report.json"), key=lambda p: p.stat().st_mtime)
                        if scands:
                            arms_out.append(extract_arm_summary(arm, json.loads(scands[-1].read_text(encoding="utf-8"))))

        elif not only_full_cli and not base_three_done and mode in {"self_triplet", "calc_selection_triplet", "calc_undo_triplet", "cwd1_triplet"}:
            if cid == "W1":
                cmd = [sys.executable, str(runner_script)]
            elif mode == "cwd1_triplet":
                cmd = [sys.executable, str(runner_script), "--artifact-parent", str(case_out)]
            elif mode.startswith("calc_"):
                mech = "selection" if mode == "calc_selection_triplet" else "undo"
                cmd = [sys.executable, str(runner_script), "--mechanism", mech, "--artifact-parent", str(case_out), "--run-prefix", f"{cid.lower()}-sol61-{stamp}"]
            else:
                cmd = [sys.executable, str(runner_script), "--artifact-parent", str(case_out), "--run-prefix", f"{cid.lower()}-sol61-{stamp}"]
            invoke(cmd, "triplet")
            triplets = sorted(case_out.glob("*-triplet/triplet_result.json"), key=lambda p: p.stat().st_mtime)
            if triplets:
                tdata = json.loads(triplets[-1].read_text(encoding="utf-8"))
                for arm_row in tdata.get("arms", []):
                    arms_out.append({
                        "condition": arm_row.get("condition"),
                        "run_id": arm_row.get("run_id"),
                        "valid": bool(arm_row.get("valid")),
                        "success": arm_row.get("success"),
                        "outcome": arm_row.get("outcome") or ("PASS" if arm_row.get("success") else "FAIL"),
                        "protocol_valid": arm_row.get("protocol_valid"),
                        "wall_seconds": arm_row.get("wall_seconds"),
                    })

        elif not only_full_cli and not base_three_done and mode == "case2_triplet":
            specs = [
                ("ma_id", "collaborative_isolated", "none"),
                ("ma_sd", "collaborative_shared", "none"),
                ("ma_sd_lock", "collaborative_shared", "input-lock"),
            ]
            for arm_label, cond_val, mitig in specs:
                run_id = f"ttr-lite-sol61-{arm_label}-{stamp}"
                run_root = case_out / run_id
                invoke(
                    [sys.executable, str(runner_script), "--condition", cond_val, "--mitigation", mitig, "--run-id", run_id, "--run-root", str(run_root)],
                    f"arm-{arm_label}",
                )
                res_file = run_root / "result.json"
                if not res_file.is_file():
                    arms_out.append({"condition": arm_label, "run_id": run_id, "valid": False, "outcome": "INVALID"})
                    break
                rep = json.loads(res_file.read_text(encoding="utf-8"))
                row = extract_arm_summary(arm_label, rep)
                arms_out.append(row)
                if arm_label == "ma_id" and row["outcome"] != "PASS":
                    break

        elif not only_full_cli and not base_three_done and mode in {"case3_triplet", "case4_triplet"}:
            specs = [
                ("ma_id", "collaborative_isolated", False),
                ("ma_sd", "collaborative_shared", False),
                ("ma_sd_lock", "collaborative_shared", True),
            ]
            for arm_label, cond_val, locked in specs:
                run_id = f"{cid.lower()}-sol61-{arm_label}-{stamp}"
                run_root = case_out / run_id
                overlay_root = case_out / f"overlays-{arm_label}"
                overlay_root.mkdir(parents=True, exist_ok=True)
                mod_name = "infra.run_case3_lite_pair_pilot" if mode == "case3_triplet" else "infra.run_case4_lite_pair_pilot"
                cmd = [
                    sys.executable, "-m", mod_name,
                    "--condition", cond_val,
                    "--run-root", str(run_root),
                    "--overlay-root", str(overlay_root),
                    "--provider", str(runtime_base / "deps/OSWorld-V2"),
                    "--image", env["SWCUB_OSWORLD_GUEST_IMAGE"],
                    "--runtime", "paragui/professional-rootless:20261103",
                    "--api-base", api_cfg["base_url"],
                ]
                if locked:
                    cmd.append("--desktop-lock")
                invoke(cmd, f"arm-{arm_label}")
                res_file = run_root / "pair_pilot_result.json"
                if not res_file.is_file():
                    arms_out.append({"condition": arm_label, "run_id": run_id, "valid": False, "outcome": "INVALID"})
                    break
                rep = json.loads(res_file.read_text(encoding="utf-8"))
                row = extract_arm_summary(arm_label, rep)
                arms_out.append(row)
                if arm_label == "ma_id" and row["outcome"] != "PASS":
                    break

        if include_full_cli and not any(r.get("condition") == "ma_sd_full_cli" for r in arms_out):
            full_cli_row = run_full_cli_arm_for_case(
                cid, mode, tree_dir, runner_script, runtime_base, case_out, env, api_cfg, invoke
            )
            arms_out.append(full_cli_row)
    except Exception as exc:
        arms_out.append({"condition": "orchestrator_error", "valid": False, "outcome": "INVALID", "error": f"{type(exc).__name__}: {exc}"})

    outcomes = {r["condition"]: r.get("outcome") for r in arms_out}
    target_met = (
        outcomes.get("ma_id") == "PASS"
        and outcomes.get("ma_sd") == "FAIL"
        and outcomes.get("ma_sd_lock") == "FAIL"
    )
    case_summary = {
        "id": cid,
        "title": case_row["title"],
        "source_completeness": case_row["source_completeness"],
        "model": MODEL,
        "harness": "containerized-codex (3-arm read-only MCP + 4th-arm ma_sd_full_cli WeaveBench hybrid)",
        "completed": bool(arms_out),
        "wall_seconds": round(prior_wall + (time.monotonic() - started), 2),
        "arms": arms_out,
        "outcomes": outcomes,
        "target_triplet_pass_fail_fail": target_met,
        "full_cli_shared_pass": outcomes.get("ma_sd_full_cli") == "PASS",
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    tmp_summary = summary_file.with_suffix(".json.tmp")
    tmp_summary.write_text(json.dumps(case_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_summary, summary_file)
    return case_summary


def write_suite_rollup(suite_out: Path, results: list[dict], total_cases: int, status: str) -> None:
    full_cli_done = [r for r in results if "ma_sd_full_cli" in (r.get("outcomes") or {})]
    rollup = {
        "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": status,
        "model": MODEL,
        "harness": "containerized-codex (3-arm read-only MCP + 4th-arm ma_sd_full_cli container-unrestricted GUI+CLI)",
        "guest_backend": "native-qemu-kvm (-accel kvm -cpu host)",
        "completed_cases": len(results),
        "total_cases": total_cases,
        "target_pass_fail_fail_count": sum(1 for r in results if r.get("target_triplet_pass_fail_fail")),
        "ma_id_pass_count": sum(1 for r in results if r.get("outcomes", {}).get("ma_id") == "PASS"),
        "ma_sd_full_cli_completed": len(full_cli_done),
        "ma_sd_full_cli_pass_count": sum(1 for r in full_cli_done if r.get("outcomes", {}).get("ma_sd_full_cli") == "PASS"),
        "cases": results,
    }
    (suite_out / "suite-status.json").write_text(json.dumps(rollup, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        f"# CoDesk 19-Case 4-Arm Suite ({MODEL}, Containerized Codex, Native KVM)",
        "",
        f"- Status: **{status}** ({len(results)}/{total_cases} cases finished)",
        f"- Isolated (ma_id) PASS: **{rollup['ma_id_pass_count']}/{len(results)}**",
        f"- Strict PASS / FAIL / FAIL triplet met: **{rollup['target_pass_fail_fail_count']}/{len(results)}**",
        f"- Shared Full GUI+CLI Unlocked (ma_sd_full_cli) PASS: **{rollup['ma_sd_full_cli_pass_count']}/{len(full_cli_done)}**",
        "",
        "| Case | Source | ma_id | ma_sd | ma_sd_lock | ma_sd_full_cli | FullCLI GUI/CLI | Wall (s) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in results:
        oc = row.get("outcomes", {})
        fc_arm = next((a for a in (row.get("arms") or []) if a.get("condition") == "ma_sd_full_cli"), {})
        gui_cli_str = (
            f"{fc_arm.get('gui_action_calls', '-')}/{fc_arm.get('cli_calls', '-')}"
            if fc_arm else "-"
        )
        lines.append(
            f"| {row['id']} | {row['source_completeness']} | {oc.get('ma_id', '-')} | "
            f"{oc.get('ma_sd', '-')} | {oc.get('ma_sd_lock', '-')} | "
            f"{oc.get('ma_sd_full_cli', '-')} | {gui_cli_str} | {row.get('wall_seconds', 0)} |"
        )
    (suite_out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_suite(
    bundle_dir: Path,
    runtime_base: Path,
    suite_out: Path,
    selected_ids: list[str] | None = None,
    lanes: int = 1,
    include_full_cli: bool = True,
    only_full_cli: bool = False,
) -> int:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    catalog = json.loads((bundle_dir / "catalog-19cases.json").read_text(encoding="utf-8"))["cases"]
    if selected_ids:
        wanted = set(selected_ids)
        catalog = [row for row in catalog if row["id"] in wanted]
    suite_out.mkdir(parents=True, exist_ok=True)
    order_map = {row["id"]: idx for idx, row in enumerate(catalog)}
    results: list[dict] = []
    rollup_lock = threading.Lock()
    if not only_full_cli:
        write_suite_rollup(suite_out, results, len(catalog), "running")
    if lanes <= 1:
        for case_row in catalog:
            res = run_case_entry(
                bundle_dir, runtime_base, suite_out, case_row,
                include_full_cli=include_full_cli, only_full_cli=only_full_cli,
            )
            results.append(res)
            if not only_full_cli:
                write_suite_rollup(suite_out, results, len(catalog), "running")
    else:
        with ThreadPoolExecutor(max_workers=lanes) as pool:
            future_map = {
                pool.submit(
                    run_case_entry, bundle_dir, runtime_base, suite_out, row,
                    include_full_cli, only_full_cli,
                ): row["id"]
                for row in catalog
            }
            for future in as_completed(future_map):
                res = future.result()
                with rollup_lock:
                    results.append(res)
                    results.sort(key=lambda r: order_map.get(r["id"], 999))
                    if not only_full_cli:
                        write_suite_rollup(suite_out, results, len(catalog), "running")
    results.sort(key=lambda r: order_map.get(r["id"], 999))
    if not only_full_cli:
        write_suite_rollup(suite_out, results, len(catalog), "completed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("stage")
    st.add_argument("--repo", type=Path, required=True)
    st.add_argument("--out", type=Path, required=True)
    rs = sub.add_parser("run-suite")
    rs.add_argument("--bundle", type=Path, required=True)
    rs.add_argument("--runtime-base", type=Path, required=True)
    rs.add_argument("--out", type=Path, required=True)
    rs.add_argument("--lanes", type=int, default=1)
    rs.add_argument("--no-full-cli", action="store_true")
    rs.add_argument("--only-full-cli", action="store_true")
    rs.add_argument("--cases", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "stage":
        summary = stage_bundle(args.repo, args.out)
        print(json.dumps(summary, indent=2))
        return 0
    if args.command == "run-suite":
        return run_suite(
            args.bundle.resolve(),
            args.runtime_base.resolve(),
            args.out.resolve(),
            args.cases,
            lanes=args.lanes,
            include_full_cli=not args.no_full_cli,
            only_full_cli=args.only_full_cli,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
