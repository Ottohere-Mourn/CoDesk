# -*- coding: utf-8 -*-
"""CoDesk 精选 23 题双智能体基准与 184 角色轨迹中文展示看板后端服务。"""
from __future__ import annotations

import argparse
import gzip
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.data_loader import (
    get_actor_trajectory,
    get_case_detail,
    get_episode_context,
    get_episode_timeline,
    get_overview_payload,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CoDesk23Dashboard/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        sys.stderr.write(f"[dashboard] {self.address_string()} - {format % args}\n")

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        accept_enc = self.headers.get("Accept-Encoding", "")
        use_gzip = "gzip" in accept_enc and len(data) > 1024
        payload = gzip.compress(data, compresslevel=5) if use_gzip else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def do_HEAD(self) -> None:
        self.do_GET()

    def _send_json(self, obj: object, status: int = 200) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send_bytes(raw, "application/json; charset=utf-8", status=status)

    def _serve_static(self, rel_path: str) -> None:
        target = (STATIC_DIR / rel_path).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
            self._send_json({"error": "静态资源不存在"}, status=HTTPStatus.NOT_FOUND)
            return
        ctype, _ = mimetypes.guess_type(str(target))
        if not ctype:
            ctype = "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
            ctype = f"{ctype}; charset=utf-8"
        self._send_bytes(target.read_bytes(), ctype)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self._send_json({"ok": True, "service": "codesk-selected-23-dashboard"})
            return

        if path == "/api/overview":
            self._send_json(get_overview_payload())
            return

        parts = [p for p in path.split("/") if p]
        # /api/cases/<case_id>
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "cases":
            data = get_case_detail(parts[2])
            if data is None:
                self._send_json({"error": f"未找到任务 {parts[2]}"}, status=HTTPStatus.NOT_FOUND)
            else:
                self._send_json(data)
            return

        # /api/cases/<case_id>/episodes/<ep_name>/context
        if len(parts) == 6 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "episodes":
            case_id, ep_name, sub = parts[2], parts[4], parts[5]
            if sub == "context":
                data = get_episode_context(case_id, ep_name)
                if data is None:
                    self._send_json({"error": "未找到对应局次上下文"}, status=HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(data)
                return
            if sub == "timeline":
                data = get_episode_timeline(case_id, ep_name)
                if data is None:
                    self._send_json({"error": "未找到对应局次时间线"}, status=HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(data)
                return

        # /api/cases/<case_id>/episodes/<ep_name>/trajectory/<role>
        if (
            len(parts) == 7
            and parts[0] == "api"
            and parts[1] == "cases"
            and parts[3] == "episodes"
            and parts[5] == "trajectory"
        ):
            case_id, ep_name, role = parts[2], parts[4], parts[6]
            data = get_actor_trajectory(case_id, ep_name, role)
            if data is None:
                self._send_json({"error": "未找到对应角色轨迹"}, status=HTTPStatus.NOT_FOUND)
            else:
                self._send_json(data)
            return

        # 静态资源与 SPA 入口
        if path in ("/", "/index.html"):
            self._serve_static("index.html")
            return
        if path.startswith("/"):
            rel = path.lstrip("/")
            candidate = (STATIC_DIR / rel).resolve()
            if str(candidate).startswith(str(STATIC_DIR.resolve())) and candidate.is_file():
                self._serve_static(rel)
                return
        self._serve_static("index.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 CoDesk 精选 23 题中文展示看板服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8790, help="监听端口（默认 8790）")
    args = parser.parse_args()

    # 预热总览缓存
    ov = get_overview_payload()
    print(
        f"[dashboard] 已加载 {ov['total_cases']} 道精选基准 / {ov['total_episodes']} 局 / "
        f"{ov['total_agent_trajectories']} 角色轨迹，监听 http://{args.host}:{args.port}",
        flush=True,
    )
    httpd = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
