"""Standalone Responses SSE upstream relay helper."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import requests
from experiments.responses_relay import prepare_image_history

DEFAULT_MODEL_NAME = "gpt-6.1-sol"
DEFAULT_EFFORT = "high"


def start_lh_relay(
    upstream_base: str,
    api_key: str,
    event_log: Path,
    model_name: str = DEFAULT_MODEL_NAME,
    upstream_model: str | None = None,
) -> tuple[ThreadingHTTPServer, int]:
    target_url = upstream_base.rstrip("/") + "/responses"
    candidates = []
    for item in [upstream_model, f"substrate-{model_name}", f"copilot-{model_name}", model_name]:
        if item and item not in candidates:
            candidates.append(item)

    class RelayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_unused):
            return

        def do_POST(self):
            started = time.monotonic()
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            parsed_dict = None
            try:
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict) and isinstance(parsed.get("input"), list) and not parsed.get("previous_response_id"):
                    parsed, _audit = prepare_image_history(parsed, keep=4, max_images=32)
                if isinstance(parsed, dict):
                    parsed_dict = parsed
                raw_body = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            except Exception:
                pass
            resp = None
            prefetched_lines: list[bytes] = []
            attempts = []
            model_idx = 0
            used_model = candidates[0]
            for retry_idx in range(12):
                used_model = candidates[min(model_idx, len(candidates) - 1)]
                req_body = raw_body
                if parsed_dict is not None and parsed_dict.get("model") == model_name and used_model != model_name:
                    req_body = json.dumps(dict(parsed_dict, model=used_model), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                try:
                    cand = requests.post(
                        target_url,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "Accept": self.headers.get("Accept", "text/event-stream"),
                        },
                        data=req_body,
                        stream=True,
                        timeout=(25, 420),
                    )
                except requests.RequestException as exc:
                    attempts.append({"attempt": retry_idx + 1, "error": type(exc).__name__, "upstream_model": used_model})
                    if retry_idx < 11:
                        time.sleep(10.0 + 4.0 * retry_idx)
                        continue
                    self.send_error(502, "Upstream request exception")
                    return
                attempts.append({"attempt": retry_idx + 1, "status": cand.status_code, "upstream_model": used_model})
                if cand.status_code == 403 and model_idx + 1 < len(candidates) and retry_idx < 11:
                    model_idx += 1
                    cand.close()
                    continue
                if cand.status_code in (400, 429, 500, 502, 503, 504) and retry_idx < 11:
                    retry_hdr = cand.headers.get("Retry-After")
                    try:
                        wait_s = min(max(float(retry_hdr), 5.0), 35.0) if retry_hdr else (10.0 + 5.0 * retry_idx)
                    except ValueError:
                        wait_s = 15.0
                    cand.close()
                    time.sleep(wait_s)
                    continue
                if cand.status_code == 200:
                    # Peek initial SSE events to catch HTTP-200 SSE "Selected model is at capacity" errors before committing 200 headers!
                    peek_buf: list[bytes] = []
                    sse_cap_err = False
                    line_iter = cand.iter_lines()
                    for _ in range(12):
                        try:
                            ln = next(line_iter)
                        except StopIteration:
                            break
                        except requests.RequestException:
                            sse_cap_err = True
                            break
                        peek_buf.append(ln)
                        low = ln.lower()
                        if b"at capacity" in low or b"overloaded" in low or b"rate_limit" in low or b"too many requests" in low:
                            sse_cap_err = True
                            break
                        if b"response.output_item" in ln or b"response.completed" in ln:
                            break
                    if sse_cap_err and retry_idx < 11:
                        attempts[-1]["sse_capacity_retry"] = True
                        cand.close()
                        time.sleep(12.0 + 6.0 * retry_idx)
                        continue
                    prefetched_lines = peek_buf
                    resp = (cand, line_iter)
                    break
                resp = cand
                break
            if resp is None:
                self.send_error(502, "Upstream unavailable")
                return
            cand_resp, rem_iter = resp if isinstance(resp, tuple) else (resp, None)
            with cand_resp:
                self.send_response(cand_resp.status_code)
                self.send_header("Content-Type", cand_resp.headers.get("Content-Type", "text/event-stream"))
                self.send_header("Connection", "close")
                self.end_headers()
                src_a = f'"model":"{used_model}"'.encode("utf-8")
                dst_a = f'"model":"{model_name}"'.encode("utf-8")
                src_b = f'"model": "{used_model}"'.encode("utf-8")
                dst_b = f'"model": "{model_name}"'.encode("utf-8")
                def _emit_line(raw_ln: bytes) -> None:
                    out_ln = raw_ln.replace(src_a, dst_a).replace(src_b, dst_b) if used_model != model_name else raw_ln
                    self.wfile.write(out_ln + b"\n")
                    self.wfile.flush()
                if rem_iter is not None:
                    for b_ln in prefetched_lines:
                        _emit_line(b_ln)
                    for b_ln in rem_iter:
                        _emit_line(b_ln)
                if used_model != model_name:
                    if rem_iter is None:
                        for line in cand_resp.iter_lines():
                            _emit_line(line)
                else:
                    if rem_iter is None:
                        for chunk in cand_resp.iter_content(chunk_size=16384):
                            if chunk:
                                self.wfile.write(chunk)
                                self.wfile.flush()
                self.close_connection = True
                with event_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"time": time.time(), "status": cand_resp.status_code, "upstream_model": used_model, "attempts": attempts, "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), RelayHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_port


