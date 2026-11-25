"""Real-Guest reference schedule for CONC-01 Gate 5; no model is called."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

OUT_A = Path("/home/user/workspace/out_a")
OUT_B = Path("/home/user/workspace/out_b")
TIMING = Path("/tmp/conc01-runtime/gate5_timing.json")
TABS = [f"tab_{i}" for i in range(1, 7)]
WIDTHS = [("mobile", 375, 812, (355, 395)), ("tablet", 768, 1024, (748, 788)),
          ("desktop", 1440, 900, (1415, 1465))]
mobile_done, b_12_done, tablet_done, b_34_done, desktop_done = (threading.Event() for _ in range(5))
errors = []
role_times = {}


def gui():
    import pyautogui
    return pyautogui


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


class ChromePage:
    def __init__(self, target):
        self.ws = CDPWebSocket(target["webSocketDebuggerUrl"], timeout=10)
        self.seq = 0

    def call(self, method, params=None):
        self.seq += 1
        ident = self.seq
        self.ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == ident:
                if "error" in reply:
                    raise RuntimeError("Chrome DevTools request failed: " + str(reply["error"].get("message", "unknown error")))
                return reply.get("result", {})

    def js(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True,
                                                   "awaitPromise": True, "userGesture": True})
        value = result.get("result", {})
        if value.get("subtype") == "error":
            raise RuntimeError("browser evaluation failed: " + value.get("description", "unknown error"))
        return value.get("value")

    def screenshot(self, path):
        image = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
        Path(path).write_bytes(base64.b64decode(image))

    def close(self):
        self.ws.close()


class CDPWebSocket:
    """Minimal RFC 6455 client for Chrome DevTools, using only the Python standard library."""

    def __init__(self, url, timeout=10):
        parsed = urlsplit(url)
        if parsed.scheme != "ws" or not parsed.hostname or not parsed.port:
            raise RuntimeError("Chrome returned an unsupported DevTools WebSocket URL")
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buffer = bytearray()
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        path = parsed.path + ("?" + parsed.query if parsed.query else "")
        request = (f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
                   "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode("ascii"))
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("Chrome closed the DevTools handshake")
            response.extend(chunk)
        header, leftover = bytes(response).split(b"\r\n\r\n", 1)
        if b" 101 " not in header.splitlines()[0]:
            raise RuntimeError("Chrome rejected the DevTools WebSocket handshake")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        if b"sec-websocket-accept: " + expected.lower() not in header.lower():
            raise RuntimeError("Chrome DevTools returned an invalid WebSocket handshake")
        self.buffer.extend(leftover)

    def _read(self, count):
        while len(self.buffer) < count:
            chunk = self.sock.recv(max(4096, count - len(self.buffer)))
            if not chunk:
                raise RuntimeError("Chrome DevTools WebSocket closed unexpectedly")
            self.buffer.extend(chunk)
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def send(self, value):
        payload = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        head = bytearray([0x81])
        length = len(payload)
        if length < 126:
            head.append(0x80 | length)
        elif length < 65536:
            head.append(0x80 | 126)
            head.extend(struct.pack("!H", length))
        else:
            head.append(0x80 | 127)
            head.extend(struct.pack("!Q", length))
        mask = secrets.token_bytes(4)
        head.extend(mask)
        head.extend(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(head)

    def recv(self):
        while True:
            first, second = self._read(2)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if masked else b""
            payload = self._read(length)
            if masked:
                payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
            if opcode == 9:
                self._send_control(10, payload)
                continue
            if opcode == 8:
                raise RuntimeError("Chrome DevTools closed the WebSocket session")
            if opcode in (1, 2):
                return payload.decode("utf-8")

    def _send_control(self, opcode, payload):
        mask = secrets.token_bytes(4)
        frame = bytearray([0x80 | opcode, 0x80 | len(payload)])
        frame.extend(mask)
        frame.extend(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(frame)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def set_1920_mode():
    info = command("xrandr", "--query")
    output = re.search(r"^(\S+) connected", info, re.M)
    if not output:
        raise RuntimeError("no active X11 output was found")
    output_name = output.group(1)
    mode = next((x.split()[0] for x in info.splitlines() if re.match(r"^\s+1920x1080", x)), None)
    if mode is None:
        cvt = subprocess.run(["cvt", "1920", "1080", "60"], text=True, capture_output=True)
        line = next((x for x in cvt.stdout.splitlines() if x.startswith("Modeline ")), None)
        if not line:
            raise RuntimeError("1920x1080 is not offered and cvt could not generate a mode")
        parts = line.split()
        mode = parts[1].strip('"')
        values = parts[2:]
        subprocess.run(["xrandr", "--newmode", mode, *values], check=False, capture_output=True)
        subprocess.run(["xrandr", "--addmode", output_name, mode], check=False, capture_output=True)
    subprocess.run(["xrandr", "--output", output_name, "--mode", mode], check=True, capture_output=True)
    width, height = gui().size()
    if width < 1920 or height < 1080:
        raise RuntimeError(f"Guest desktop is {width}x{height}; requires 1920x1080")


def resize_window(page, width, height, maximize=False):
    target = page.call("Browser.getWindowForTarget")
    window_id = target.get("windowId")
    if window_id is None:
        raise RuntimeError("Chrome did not return the shared window ID")
    if maximize:
        page.call("Browser.setWindowBounds", {"windowId": window_id, "bounds": {"windowState": "maximized"}})
    else:
        # Restore first; Chrome ignores explicit dimensions while maximized.
        page.call("Browser.setWindowBounds", {"windowId": window_id, "bounds": {"windowState": "normal"}})
        page.call("Browser.setWindowBounds", {"windowId": window_id,
                                               "bounds": {"left": 8, "top": 8, "width": width, "height": height,
                                                          "windowState": "normal"}})
    time.sleep(0.25)


def targets():
    for _ in range(40):
        try:
            with urlopen("http://127.0.0.1:9222/json", timeout=2) as r:
                pages = json.loads(r.read())
            a = next(p for p in pages if p.get("type") == "page" and ":18081/" in p.get("url", ""))
            b = next(p for p in pages if p.get("type") == "page" and ":18082/" in p.get("url", ""))
            return ChromePage(a), ChromePage(b)
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("the two shared Chrome pages were not ready on the DevTools endpoint")


def a_stage(page, band, requested_width, requested_height, width_bounds):
    resize_window(page, requested_width, requested_height)
    measured = page.js("({width:window.outerWidth,height:window.outerHeight})")
    if not (width_bounds[0] <= measured["width"] <= width_bounds[1]):
        delta = requested_width - int(measured["width"])
        resize_window(page, requested_width + delta, requested_height)
        measured = page.js("({width:window.outerWidth,height:window.outerHeight})")
    if not (width_bounds[0] <= measured["width"] <= width_bounds[1]):
        bounds = page.call("Browser.getWindowForTarget").get("bounds", {})
        screen = page.js("({dpr:devicePixelRatio,screenWidth:screen.width,screenHeight:screen.height,innerWidth:innerWidth})")
        raise RuntimeError(f"could not reach {band} width; actual outerWidth={measured['width']}, bounds={bounds}, screen={screen}")
    result = page.js("""(async()=>{
      await control('delivery',document.querySelector('#shipping').value);
      await control('promotion',document.querySelector('#promo').value);
      await control('tax','recalculate');
      await recordCheck();
      let badge=(document.querySelector('#badge').textContent.match(/[0-9]{6}/)||[])[0]||'';
      return {width:window.outerWidth,height:window.outerHeight,ids:inspectLayout(),badge};
    })()""")
    if not result.get("badge"):
        raise RuntimeError(f"{band} viewport did not return a badge")
    OUT_A.mkdir(parents=True, exist_ok=True)
    page.screenshot(OUT_A / f"qa_{requested_width}.png")
    return band, {"has_bug": bool(result["ids"]),
                  "bug_element_id": ",".join(result["ids"]) if result["ids"] else "NONE",
                  "badge_code": result["badge"]}


def actor_a(page):
    start = time.monotonic()
    try:
        report = {}
        report[WIDTHS[0][0]] = a_stage(page, *WIDTHS[0][:3], WIDTHS[0][3])[1]
        mobile_done.set(); b_12_done.wait()
        report[WIDTHS[1][0]] = a_stage(page, *WIDTHS[1][:3], WIDTHS[1][3])[1]
        tablet_done.set(); b_34_done.wait()
        report[WIDTHS[2][0]] = a_stage(page, *WIDTHS[2][:3], WIDTHS[2][3])[1]
        desktop_done.set()
        (OUT_A / "qa_viewport_report.json").write_text(json.dumps(report), encoding="utf-8")
    except Exception as exc:
        errors.append(f"Actor A: {type(exc).__name__}: {exc}")
        mobile_done.set(); tablet_done.set(); desktop_done.set()
    role_times["A"] = {"start": start, "end": time.monotonic()}


def b_group(page, group):
    resize_window(page, 1920, 1080, maximize=True)
    dims = page.js("({width:window.outerWidth,height:window.outerHeight})")
    if dims["width"] < 1860 or dims["height"] < 950:
        raise RuntimeError(f"wide-window requirement failed at actual {dims['width']}x{dims['height']}")
    values = {}
    OUT_B.mkdir(parents=True, exist_ok=True)
    for tab in group:
        page.js(f"show('{tab}')")
        time.sleep(0.3)
        for index, peak in enumerate(("peak_a", "peak_b")):
            geometry = page.js(f"""(()=>{{let c=document.querySelector('#plot'),r=c.getBoundingClientRect(),p=points[{index}];
              return {{x:window.screenX+(window.outerWidth-window.innerWidth)/2+r.left+p.x*r.width/c.width*devicePixelRatio,
                      y:window.screenY+(window.outerHeight-window.innerHeight)+r.top+p.y*r.height/c.height*devicePixelRatio}}}})()""")
            gui().moveTo(round(geometry["x"]), round(geometry["y"]))
            time.sleep(0.35)
            tip = page.js("document.querySelector('#tip').textContent")
            match = re.search(r"([-+]?[0-9]+(?:\.[0-9]+)?)\s*$", str(tip))
            if not match:
                raise RuntimeError(f"{tab} {peak} hover did not return a tooltip value")
            values.setdefault(tab, {})[peak] = float(match.group(1))
        gui().screenshot().save(OUT_B / f"ops_{tab}.png")
    return values


def actor_b(page):
    start = time.monotonic()
    try:
        mobile_done.wait()
        report = b_group(page, TABS[:2]); b_12_done.set()
        tablet_done.wait()
        report.update(b_group(page, TABS[2:4])); b_34_done.set()
        desktop_done.wait()
        report.update(b_group(page, TABS[4:]))
        (OUT_B / "ops_telemetry.json").write_text(json.dumps(report), encoding="utf-8")
    except Exception as exc:
        errors.append(f"Actor B: {type(exc).__name__}: {exc}")
        b_12_done.set(); b_34_done.set()
    role_times["B"] = {"start": start, "end": time.monotonic()}


def main():
    start = time.monotonic()
    try:
        set_1920_mode()
        page_a, page_b = targets()
        worker_a = threading.Thread(target=actor_a, args=(page_a,), daemon=True)
        worker_b = threading.Thread(target=actor_b, args=(page_b,), daemon=True)
        worker_a.start(); worker_b.start()
        worker_a.join(1800); worker_b.join(1800)
        if worker_a.is_alive() or worker_b.is_alive(): errors.append("reference schedule exceeded 1800 seconds")
        page_a.close(); page_b.close()
    except Exception as exc:
        errors.append(f"setup: {type(exc).__name__}: {exc}")
    elapsed = time.monotonic() - start
    a_time, b_time = role_times.get("A"), role_times.get("B")
    overlap = max(0.0, min(a_time["end"], b_time["end"]) - max(a_time["start"], b_time["start"])) if a_time and b_time else 0.0
    result = {"reference_guest_replay": True, "careful_conc_elapsed_s": round(elapsed, 3),
              "conc_role_timeout_s": 3600, "overlap_s": round(overlap, 3),
              "schedule_complete": not errors, "errors": errors, "role_times": role_times}
    TIMING.parent.mkdir(parents=True, exist_ok=True)
    TIMING.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("reference_schedule=" + ("complete" if result["schedule_complete"] else "failed"))
    print("elapsed_s=" + str(result["careful_conc_elapsed_s"]))
    print("overlap_s=" + str(result["overlap_s"]))
    if errors:
        print("failure_count=" + str(len(errors)))
    raise SystemExit(0 if result["schedule_complete"] else 3)


if __name__ == "__main__":
    main()
