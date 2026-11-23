"""Shared helpers & interactive visual/AT-SPI candidate evaluator for rb_osw2_synth_v2 (RBS2-01..RBS2-06)."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from tasks.rb_osw2_synth_v1.common import (
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
    semantic_doc_equal,
    set_x11_clipboard,
    stage_private_studio_script,
    verify_prompt_hygiene,
    write_json,
    write_simple_odt,
)
from tasks.exam_contention_v2.common import render_scanned_document_png

__all__ = [
    "FORBIDDEN_EXAM_V2_PATTERNS",
    "advisory_lock",
    "boot_isolated_studio_scripts",
    "boot_singleton_cdp_chromium",
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


def run_cli_probe_json(script_path: Path, args: list[str], timeout_s: float = 15.0) -> dict[str, Any]:
    """Run a recreated app's `--self-test-json` or CLI query entrypoint as `user` for behavioral grading."""
    if not script_path.is_file():
        return {}
    import json
    import os
    import shlex

    for p in [script_path.parent, *script_path.parent.rglob("*")]:
        try:
            os.chmod(p, 0o777 if p.is_dir() else 0o755)
        except OSError:
            pass
    cmd_str = " ".join(["bash", shlex.quote(str(script_path)), *(shlex.quote(a) for a in args)])
    cp = subprocess.run(
        ["su", "-s", "/bin/bash", "user", "-c", cmd_str],
        cwd=str(script_path.parent),
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if cp.returncode != 0:
        return {}
    for ln in reversed(cp.stdout.strip().splitlines()):
        ln = ln.strip()
        if ln.startswith("{") and ln.endswith("}"):
            try:
                return json.loads(ln)
            except Exception:
                continue
    try:
        return json.loads(cp.stdout)
    except Exception:
        return {}
