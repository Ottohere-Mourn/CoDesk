"""Shared AT-SPI2 candidate-app evaluator, isolated reference launcher, CDP helper & rubric engine for rb_osw2_synth_v1."""
from __future__ import annotations

import base64
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import struct
import subprocess
import tempfile
import time
from typing import Any, Iterator
import urllib.request

from tasks.exam_contention_v2.common import (
    FORBIDDEN_EXAM_V2_PATTERNS,
    build_grade_payload,
    convert_doc_to_pdf_isolated,
    extract_pdf_text,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    pdf_page_count,
    read_json_safe,
    read_odt_plain_text,
    reload_open_libreoffice_docs,
    semantic_doc_equal,
    set_x11_clipboard,
    verify_prompt_hygiene,
    write_json,
    write_simple_odt,
)

__all__ = [
    "FORBIDDEN_EXAM_V2_PATTERNS",
    "advisory_lock",
    "boot_isolated_studio_scripts",
    "boot_singleton_cdp_chromium",
    "build_grade_payload",
    "cdp_eval_js",
    "cdp_list_targets",
    "convert_doc_to_pdf_isolated",
    "evaluate_recreated_gui_app",
    "extract_pdf_text",
    "flush_open_libreoffice_to_disk",
    "get_x11_clipboard",
    "make_opaque_seal",
    "pdf_page_count",
    "read_json_safe",
    "read_odt_plain_text",
    "reload_open_libreoffice_docs",
    "semantic_doc_equal",
    "set_x11_clipboard",
    "stage_private_studio_script",
    "verify_prompt_hygiene",
    "write_json",
    "write_simple_odt",
]


@contextmanager
def advisory_lock(lock_name: str) -> Iterator[None]:
    lp = Path(f"/tmp/.rbs_careful_{lock_name}.lck")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def stage_private_studio_script(state_dir: Path, filename: str, source_code: str) -> Path:
    """Write reference GUI app code into a studio_ui-only directory unreadable by role containers."""
    priv = state_dir / "studio_only"
    priv.mkdir(parents=True, exist_ok=True)
    p = priv / filename
    p.write_text(source_code, encoding="utf-8")
    return p


def boot_isolated_studio_scripts(state_dir: Path, script_names: list[str], wait_s: float = 2.2) -> None:
    """Launch reference GUI apps as dedicated user `studio_ui` (UID != 1000, mode 0700 dir) on :99 + AT-SPI2."""
    priv = state_dir / "studio_only"
    run_dir = Path("/opt/rbs_studio_bin")
    run_dir.mkdir(parents=True, exist_ok=True)
    for fn in script_names:
        shutil.copy2(priv / fn, run_dir / fn)

    bg_cmds = " ".join(
        f"nohup python3 {shlex.quote(str(run_dir / fn))} >/tmp/rbs_ref_{idx}.log 2>&1 </dev/null &"
        for idx, fn in enumerate(script_names)
    )
    cmd = (
        "id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; "
        f"chown -R studio_ui:studio_ui {shlex.quote(str(run_dir))} && chmod 700 {shlex.quote(str(run_dir))}; "
        "chmod 1777 /home/user/Downloads 2>/dev/null || true; "
        # Grant studio_ui access to the shared X11 and AT-SPI2 bus sockets on desk_container
        "chmod 755 /run/user/1000 /run/user/1000/at-spi 2>/dev/null || true; "
        "chmod 666 /run/user/1000/bus /run/user/1000/at-spi/bus* 2>/dev/null || true; "
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "su -s /bin/bash studio_ui -c '"
        "export DISPLAY=:99 HOME=/home/studio_ui "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"'\"$AT_ADDR\"'\" AT_SPI_BUS=\"'\"$AT_ADDR\"'\" "
        "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
        "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1; "
        f"{bg_cmds}'"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=25)
    time.sleep(wait_s)


def boot_singleton_cdp_chromium(urls: list[str], window_pos: tuple[int, int] = (40, 30), window_size: tuple[int, int] = (1360, 920)) -> None:
    """Launch a single shared Chromium instance on :99 exposing --remote-debugging-port=9222."""
    u_args = " ".join(shlex.quote(u) for u in urls)
    cmd = (
        "su -s /bin/bash user -c '"
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus AT_SPI_BUS_ADDRESS=\"$AT_ADDR\"; "
        "mkdir -p /home/user/.config/rbs_chr_profile; "
        "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
        "--force-renderer-accessibility --remote-debugging-port=9222 --remote-allow-origins=* "
        "--user-data-dir=/home/user/.config/rbs_chr_profile "
        f"--window-position={window_pos[0]},{window_pos[1]} --window-size={window_size[0]},{window_size[1]} "
        f"{u_args} >/tmp/rbs_cdp_chr.log 2>&1 </dev/null &'; "
        "for _i in $(seq 1 30); do curl -fsS http://127.0.0.1:9222/json/version >/dev/null 2>&1 && break; sleep 0.3; done; sleep 0.6"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=30)


def cdp_list_targets(cdp_port: int = 9222) -> list[dict[str, Any]]:
    raw = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=5).read().decode("utf-8")
    return [t for t in json.loads(raw) if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]


def _ws_send_text(sock: socket.socket, payload: str) -> None:
    data = payload.encode("utf-8")
    mask = os.urandom(4)
    hdr = bytearray([0x81])
    n = len(data)
    if n < 126:
        hdr.append(0x80 | n)
    elif n < 65536:
        hdr.append(0x80 | 126)
        hdr.extend(struct.pack("!H", n))
    else:
        hdr.append(0x80 | 127)
        hdr.extend(struct.pack("!Q", n))
    hdr.extend(mask)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    sock.sendall(bytes(hdr) + masked)


def _ws_recv_text(sock: socket.socket) -> str:
    def _read_exact(k: int) -> bytes:
        buf = bytearray()
        while len(buf) < k:
            chunk = sock.recv(k - len(buf))
            if not chunk:
                raise EOFError("WebSocket closed")
            buf.extend(chunk)
        return bytes(buf)

    b1, b2 = _read_exact(2)
    del b1
    masked = bool(b2 & 0x80)
    ln = b2 & 0x7F
    if ln == 126:
        ln = struct.unpack("!H", _read_exact(2))[0]
    elif ln == 127:
        ln = struct.unpack("!Q", _read_exact(8))[0]
    mkey = _read_exact(4) if masked else b""
    body = _read_exact(ln)
    if masked:
        body = bytes(b ^ mkey[i % 4] for i, b in enumerate(body))
    return body.decode("utf-8", errors="replace")


def cdp_call(ws_url: str, method: str, params: dict[str, Any] | None = None, timeout_s: float = 8.0) -> dict[str, Any]:
    """Minimal dependency-free RFC-6455 CDP client for deterministic self-validation & tests."""
    rest = ws_url.split("ws://", 1)[1]
    host_port, path = rest.split("/", 1)
    host, port_s = host_port.split(":")
    path = "/" + path
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    with socket.create_connection((host, int(port_s)), timeout=timeout_s) as sock:
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(req.encode("ascii"))
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += sock.recv(4096)
        _ws_send_text(sock, json.dumps({"id": 1, "method": method, "params": params or {}}))
        for _ in range(40):
            msg = json.loads(_ws_recv_text(sock))
            if msg.get("id") == 1:
                return msg.get("result") or {}
    return {}


def cdp_eval_js(ws_url: str, expression: str) -> Any:
    res = cdp_call(ws_url, "Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
    return ((res.get("result") or {}).get("value"))


def evaluate_recreated_gui_app(
    run_script: Path,
    *,
    disp_num: int = 115,
    expected_title_sub: str = "",
    key_sequences: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Launch a candidate GUI app in an isolated Xvfb + AT-SPI2 + qwen-cua-driver sandbox and inspect it.

    Returns rich programmatic AT-SPI text snapshots (initial + after each key sequence) and
    visual window metrics (size, unique colors, non-blank ratio) for fine-grained partial credit.
    """
    from PIL import Image

    out: dict[str, Any] = {
        "script_exists": run_script.is_file(),
        "window_mapped": False,
        "window_title": "",
        "win_w": 0,
        "win_h": 0,
        "visual_nonblank": False,
        "unique_colors_sampled": 0,
        "initial_ax_text": "",
        "state_json": {},
        "after_keys_ax": {},
    }
    if not run_script.is_file():
        return out

    with tempfile.TemporaryDirectory(prefix=f"rbs_eval_{disp_num}_") as tmp:
        rt = Path(tmp)
        os.chmod(rt, 0o777)
        sock_p = rt / "cua.sock"
        shot_p = rt / "win.png"
        mcp_probe_py = rt / "mcp_probe.py"
        mcp_probe_py.write_text(
            "import json, subprocess, sys, time\n"
            "from pathlib import Path\n"
            f"rt = Path({json.dumps(str(rt))})\n"
            f"sock = {json.dumps(str(sock_p))}\n"
            f"kseqs = {json.dumps(list(key_sequences or ()))}\n"
            "p = subprocess.Popen(['qwen-cua-driver', 'mcp', '--socket', sock], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)\n"
            "_id = 0\n"
            "def call_tool(name, args):\n"
            "    global _id; _id += 1; i = _id\n"
            "    p.stdin.write(json.dumps({'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':name,'arguments':args}})+'\\n'); p.stdin.flush()\n"
            "    while True:\n"
            "        ln = p.stdout.readline()\n"
            "        if not ln: return {}\n"
            "        msg = json.loads(ln)\n"
            "        if msg.get('id') == i: return msg.get('result') or {}\n"
            "p.stdin.write(json.dumps({'jsonrpc':'2.0','id':999,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'ev','version':'1'}}})+'\\n'); p.stdin.flush()\n"
            "p.stdout.readline()\n"
            "p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized','params':{}})+'\\n'); p.stdin.flush()\n"
            "def dump_ax(out_file):\n"
            "    st = call_tool('get_state', {})\n"
            "    sc = st.get('structuredContent') or {}\n"
            "    ws = sc.get('windows') or []\n"
            "    chunks = [json.dumps(sc)]\n"
            "    if ws:\n"
            "        app_id = ws[-1].get('app') or ''\n"
            "        ga = call_tool('get_app', {'app': app_id})\n"
            "        chunks.extend(c.get('text','') for c in (ga.get('content') or []) if isinstance(c, dict))\n"
            "    (rt / out_file).write_text('\\n'.join(chunks), encoding='utf-8')\n"
            "    return sc\n"
            "sc0 = dump_ax('ax_init.txt')\n"
            "(rt / 'state_init.json').write_text(json.dumps(sc0), encoding='utf-8')\n"
            "for tag, kseq in kseqs:\n"
            "    subprocess.run(['xdotool', 'key', '--clearmodifiers', kseq], capture_output=True)\n"
            "    time.sleep(0.6)\n"
            "    dump_ax(f'ax_{tag}.txt')\n"
            "p.terminate()\n",
            encoding="utf-8",
        )
        os.chmod(mcp_probe_py, 0o644)
        eval_sh = (
            f"export DISPLAY=:{disp_num} XDG_RUNTIME_DIR={shlex.quote(str(rt))} HOME={shlex.quote(str(rt))}; "
            f"Xvfb :{disp_num} -screen 0 1600x1000x24 -ac +extension GLX +render -noreset -nolisten tcp >{rt}/xvfb.log 2>&1 & "
            "XVFB_PID=$!; sleep 0.7; "
            f"dbus-daemon --session --fork --address=unix:path={rt}/bus; "
            f"export DBUS_SESSION_BUS_ADDRESS=unix:path={rt}/bus; "
            f"/usr/libexec/at-spi-bus-launcher --launch-immediately >{rt}/atspi.log 2>&1 & "
            "ATSPI_PID=$!; sleep 0.6; "
            "AT_ADDR=$(dbus-send --session --dest=org.a11y.Bus --print-reply /org/a11y/bus org.a11y.Bus.GetAddress 2>/dev/null | sed -n 's/.*string \"\\(.*\\)\"/\\1/p' || true); "
            "dbus-send --session --dest=org.a11y.Bus --type=method_call /org/a11y/bus org.freedesktop.DBus.Properties.Set string:org.a11y.Status string:IsEnabled variant:boolean:true >/dev/null 2>&1 || true; "
            "dbus-send --session --dest=org.a11y.Bus --type=method_call /org/a11y/bus org.freedesktop.DBus.Properties.Set string:org.a11y.Status string:ScreenReaderEnabled variant:boolean:true >/dev/null 2>&1 || true; "
            f"if [ -n \"$AT_ADDR\" ]; then DBUS_SESSION_BUS_ADDRESS=\"$AT_ADDR\" /usr/libexec/at-spi2-registryd --use-gnome-session >{rt}/reg.log 2>&1 & fi; "
            "export AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
            "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
            "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1; "
            f"openbox >{rt}/ob.log 2>&1 & OB_PID=$!; sleep 0.5; "
            f"bash {shlex.quote(str(run_script))} >{rt}/app.log 2>&1 </dev/null & APP_PID=$!; "
            "wid=''; for _i in $(seq 1 30); do wid=$(wmctrl -l 2>/dev/null | tail -n 1 | awk '{print $1}' || true); [ -n \"$wid\" ] && break; sleep 0.35; done; sleep 0.8; "
            f"qwen-cua-driver serve --no-overlay --permission-mode standard --socket {shlex.quote(str(sock_p))} >{rt}/cua.log 2>&1 </dev/null & CUA_PID=$!; "
            f"for _i in $(seq 1 25); do [ -S {shlex.quote(str(sock_p))} ] && break; sleep 0.2; done; "
            f"wmctrl -lG > {rt}/wm_init.txt 2>/dev/null || true; "
            "if [ -n \"$wid\" ]; then "
            "  wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.25; "
            f"  import -window \"$wid\" {shlex.quote(str(shot_p))} 2>/dev/null || import -window root {shlex.quote(str(shot_p))} 2>/dev/null || true; "
            f"  python3 {shlex.quote(str(mcp_probe_py))} >/dev/null 2>&1 || true; "
            "fi; "
            "kill $CUA_PID $APP_PID $OB_PID $ATSPI_PID $XVFB_PID >/dev/null 2>&1 || true"
        )
        for p_ch in [run_script.parent, *run_script.parent.rglob("*")]:
            try:
                os.chmod(p_ch, 0o777 if p_ch.is_dir() else 0o755)
            except OSError:
                pass
        subprocess.run(
            ["su", "-s", "/bin/bash", "user", "-c", eval_sh],
            cwd=str(run_script.parent),
            capture_output=True,
            timeout=65,
        )

        wm_lines = [ln.strip() for ln in (rt / "wm_init.txt").read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()] if (rt / "wm_init.txt").is_file() else []
        if wm_lines:
            out["window_mapped"] = True
            picked = wm_lines[-1]
            if expected_title_sub:
                for ln in wm_lines:
                    if expected_title_sub.lower() in ln.lower():
                        picked = ln
                        break
            parts = picked.split(None, 7)
            if len(parts) >= 7:
                out["win_w"] = int(parts[4])
                out["win_h"] = int(parts[5])
                out["window_title"] = parts[7] if len(parts) >= 8 else ""

        if (rt / "state_init.json").is_file():
            out["state_json"] = read_json_safe(rt / "state_init.json")
        if (rt / "ax_init.txt").is_file():
            out["initial_ax_text"] = (rt / "ax_init.txt").read_text(encoding="utf-8", errors="replace")
        for tag, _k in (key_sequences or ()):
            fp = rt / f"ax_{tag}.txt"
            out["after_keys_ax"][tag] = fp.read_text(encoding="utf-8", errors="replace") if fp.is_file() else ""

        if shot_p.is_file() and shot_p.stat().st_size > 800:
            try:
                with Image.open(shot_p) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    if out["win_w"] == 0:
                        out["win_w"], out["win_h"] = w, h
                    colors = set()
                    for sx in range(0, w, max(1, w // 24)):
                        for sy in range(0, h, max(1, h // 18)):
                            colors.add(rgb.getpixel((sx, sy)))
                    out["unique_colors_sampled"] = len(colors)
                    out["visual_nonblank"] = (w >= 380 and h >= 260 and len(colors) >= 4)
            except Exception:
                pass
    return out
