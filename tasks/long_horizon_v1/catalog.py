"""Catalog and UID-0 compliance portals for the 4 ultra-long-horizon (40+ min) multi-app tasks."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import urllib.parse


LONG_HORIZON_CATALOG = [
    {
        "id": "LH-01",
        "software": "Blender 3.4 Cycles + Inkscape 1.2 + Chromium LEED Daylighting Portal",
        "canonical_project": "atrium_hall.blend",
        "gui_launch": ["chromium", "--no-sandbox", "--no-first-run", "--disable-gpu", "--user-data-dir=/home/gui/.config/chromium", "http://127.0.0.1:18911/"],
        "portal_port": 18911,
        "seq_role_timeout_s": 1350,
        "conc_role_timeout_s": 2520,
        "title": "10-louver 3-sun Cycles global-illumination & thermal-glare Pareto co-design + SVG HUD & LEED Portal",
    },
    {
        "id": "LH-02",
        "software": "QGIS 3.22 + SpatiaLite + LibreOffice Calc 7.4 + Chromium Municipal Bond Portal",
        "canonical_project": "metro_drainage.qgz",
        "gui_launch": ["chromium", "--no-sandbox", "--no-first-run", "--disable-gpu", "--user-data-dir=/home/gui/.config/chromium", "http://127.0.0.1:18912/"],
        "portal_port": 18912,
        "seq_role_timeout_s": 1350,
        "conc_role_timeout_s": 2520,
        "title": "96-subbasin 6-tier river DAG kinematic-wave flood routing, 20-yr DSCR bond schedule & 4-sheet A3 Atlas",
    },
    {
        "id": "LH-03",
        "software": "FreeCAD 0.20 + Inkscape 1.2 + Graphviz + Chromium Aerospace PLM Portal",
        "canonical_project": "cam_indexer.FCStd",
        "gui_launch": ["chromium", "--no-sandbox", "--no-first-run", "--disable-gpu", "--user-data-dir=/home/gui/.config/chromium", "http://127.0.0.1:18913/"],
        "portal_port": 18913,
        "seq_role_timeout_s": 1350,
        "conc_role_timeout_s": 2520,
        "title": "6-part harmonic cam-indexer 72-angle BRep film-clearance [0.14, 0.24] mm, CG offset & mass-budget co-design",
    },
    {
        "id": "LH-04",
        "software": "Blender 3.4 + GIMP 2.10 + Inkscape 1.2 + MLT melt + FFmpeg + SoX + Chromium Broadcast MAM",
        "canonical_project": "program_master.mlt",
        "gui_launch": ["chromium", "--no-sandbox", "--no-first-run", "--disable-gpu", "--user-data-dir=/home/gui/.config/chromium", "http://127.0.0.1:18914/"],
        "portal_port": 18914,
        "seq_role_timeout_s": 1350,
        "conc_role_timeout_s": 2520,
        "title": "6-app 24s broadcast master: EBU-R128 (-23.0±0.20 LUFS, LRA, dBTP), ducking SNR, BT.709 [16,235] & CBR window",
    },
]

LH_BY_ID = {entry["id"]: entry for entry in LONG_HORIZON_CATALOG}


def run_lh_portal(task_id: str, port: int, state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "portal_state.json"
    lock = threading.Lock()
    state = {
        "task_id": task_id,
        "submissions": {},
        "submission_history": [],
        "concurrent_overwrites": 0,
        "active_draft_owner": None,
        "active_draft_started": 0.0,
    }
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_unused):
            return

        def _reply(self, code: int, body_obj: dict) -> None:
            raw = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/health":
                self._reply(200, {"ready": True, "task_id": task_id})
                return
            if parsed.path == "/api/status":
                with lock:
                    self._reply(200, {"task_id": task_id, "submitted_roles": sorted(state["submissions"].keys()), "concurrent_overwrites": state["concurrent_overwrites"]})
                return
            html = (
                f"<!doctype html><html><head><title>{task_id} Compliance Signoff Portal</title></head><body>"
                f"<h1>{task_id} Engineering & Compliance Signoff Portal</h1>"
                "<p>POST JSON to <code>/api/submit</code> with <code>{\"role\": \"A|B\", \"project_sha256\": \"...\", \"metrics\": {...}}</code> after all workstation DRC gates pass.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
            body = json.loads(raw) if raw.strip() else {}
            now = time.time()
            if parsed.path == "/api/submit":
                role = str(body.get("role", ""))
                if role not in {"A", "B"}:
                    self._reply(400, {"ok": False, "error": "role must be A or B"})
                    return
                with lock:
                    if state["active_draft_owner"] and state["active_draft_owner"] != role and (now - state["active_draft_started"]) < 30.0:
                        state["concurrent_overwrites"] += 1
                    state["active_draft_owner"] = role
                    state["active_draft_started"] = now
                    rec = {"role": role, "project_sha256": str(body.get("project_sha256", "")), "metrics": body.get("metrics") or {}, "timestamp": now}
                    state["submissions"][role] = rec
                    state["submission_history"].append(rec)
                    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
                self._reply(200, {"ok": True, "recorded": rec})
                return
            self._reply(404, {"ok": False, "error": "not_found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    srv.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    run_lh_portal(args.task, args.port, args.state_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
