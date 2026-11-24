"""Shared helpers for rb_osw2_synth_v3 (including no-CDP studio_ui Chromium SSO launcher)."""
from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
from typing import Any

from tasks.rb_osw2_synth_v2.common import (
    FORBIDDEN_EXAM_V2_PATTERNS,
    advisory_lock,
    boot_isolated_studio_scripts,
    boot_singleton_cdp_chromium,
    build_grade_payload,
    cdp_call,
    cdp_eval_js,
    cdp_list_targets,
    convert_doc_to_pdf_isolated,
    evaluate_recreated_gui_app,
    extract_pdf_text,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    pdf_page_count,
    read_json_safe,
    read_odt_plain_text,
    reload_open_libreoffice_docs,
    render_scanned_document_png,
    run_cli_probe_json,
    semantic_doc_equal,
    set_x11_clipboard,
    stage_private_studio_script,
    verify_prompt_hygiene,
    write_json,
    write_simple_odt,
)

__all__ = [
    "FORBIDDEN_EXAM_V2_PATTERNS",
    "advisory_lock",
    "boot_isolated_studio_scripts",
    "boot_singleton_cdp_chromium",
    "boot_studio_sso_chromium",
    "build_grade_payload",
    "cdp_call",
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
    "render_scanned_document_png",
    "run_cli_probe_json",
    "semantic_doc_equal",
    "set_x11_clipboard",
    "stage_private_studio_script",
    "verify_prompt_hygiene",
    "write_json",
    "write_simple_odt",
]


def boot_studio_sso_chromium(
    state_dir: Path,
    window_pos: tuple[int, int] | None = None,
    window_size: tuple[int, int] = (1220, 860),
) -> None:
    """Launch authenticated HttpOnly SSO Chromium as `studio_ui` (no CDP port) on :99 + AT-SPI2.

    Prevents background WebSocket bypass of stateful portal VIEW toggles while keeping full
    AT-SPI2 + X11 + CLI accessibility intact.
    """
    boot_p = state_dir / "boot_url"
    if not boot_p.is_file():
        return
    cfg: dict[str, Any] = json.loads(boot_p.read_text(encoding="utf-8"))
    boot_p.unlink(missing_ok=True)
    urls = cfg.get("urls") or ([cfg["url"]] if cfg.get("url") else [])
    u_args = " ".join(shlex.quote(str(u)) for u in urls)
    pos_flag = f"--window-position={window_pos[0]},{window_pos[1]} " if window_pos is not None else ""
    cmd = (
        "id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; "
        "chmod 1777 /home/user/Downloads 2>/dev/null || true; "
        "chmod 755 /run/user/1000 /run/user/1000/at-spi 2>/dev/null || true; "
        "chmod 666 /run/user/1000/bus /run/user/1000/at-spi/bus* 2>/dev/null || true; "
        "mkdir -p /tmp/rt-studio-chr /home/studio_ui/.config/chromium && "
        "chown -R studio_ui:studio_ui /tmp/rt-studio-chr /home/studio_ui && chmod 700 /home/studio_ui/.config/chromium && "
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "su -s /bin/bash studio_ui -c '"
        "export DISPLAY=:99 HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/rt-studio-chr "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"'\"$AT_ADDR\"'\" AT_SPI_BUS=\"'\"$AT_ADDR\"'\"; "
        "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
        "--force-renderer-accessibility --user-data-dir=/home/studio_ui/.config/chromium "
        f"{pos_flag}--window-size={window_size[0]},{window_size[1]} "
        f"{u_args} >/tmp/studio_sso_chr.log 2>&1 </dev/null &'; "
        "for _i in $(seq 1 25); do DISPLAY=:99 wmctrl -lx 2>/dev/null | grep -qi chromium && break; sleep 0.3; done; sleep 0.6"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=30)
