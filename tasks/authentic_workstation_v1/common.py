"""Shared helpers for authentic_workstation_v1 (real open-source desktop apps, PDF spec builder, read-only grading)."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
from typing import Any, Iterator
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

from tasks.thematic_arenas_v1.xlsx_utils import (
    CellSpec,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

FORBIDDEN_AW_PROMPT_PATTERNS: tuple[str, ...] = (
    "other agent",
    "another agent",
    "peer agent",
    "concurrent agent",
    "teammate",
    "colleague",
    "do not modify",
    "ctrl+z",
    "cmd+z",
    "qwen_cua_driver",
    "desktop.click",
    "click_and_type",
)


def read_json_safe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@contextmanager
def resource_lock(resource_key: str) -> Iterator[None]:
    """Fine-grained per-artifact advisory lock (used around individual shared file commits, never wrapping whole roles)."""
    lp = Path(f"/tmp/.aw_res_{resource_key}.lck")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def make_session_token(domain_salt: str, state_key: str) -> str:
    digest = hashlib.sha256(f"aw-v1:{domain_salt}:{state_key}".encode("utf-8")).hexdigest()[:12].upper()
    return f"CERT-{digest}"


def verify_prompt_hygiene(tickets_by_role: dict[str, str]) -> dict[str, Any]:
    joined = "\n".join(tickets_by_role.values()).lower()
    hits = [pat for pat in FORBIDDEN_AW_PROMPT_PATTERNS if pat in joined]
    return {"ok": len(hits) == 0, "forbidden_hits": hits}


def score_rubric(
    checks: list[tuple[str, bool, float, str]],
    pass_threshold: float = 0.85,
) -> tuple[float, bool, list[str], dict[str, bool]]:
    tot_w = sum(max(0.0, float(w)) for _, _, w, _ in checks) or 1.0
    earned = 0.0
    errs: list[str] = []
    sub_map: dict[str, bool] = {}
    for cid, ok, w, err_msg in checks:
        flag = bool(ok)
        sub_map[cid] = flag
        if flag:
            earned += max(0.0, float(w))
        elif err_msg:
            errs.append(err_msg)
    score = round(earned / tot_w, 4)
    passed = (score >= pass_threshold) and (len(errs) == 0 if pass_threshold >= 0.999 else True)
    return score, passed, errs, sub_map


def build_aw_grade_payload(
    *,
    task_id: str,
    checks_a: list[tuple[str, bool, float, str]],
    checks_b: list[tuple[str, bool, float, str]],
    checks_joint: list[tuple[str, bool, float, str]] | None,
    tickets_by_role: dict[str, str],
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
    pass_threshold: float = 0.85,
) -> dict[str, Any]:
    """Build continuous + binary grade with 100% identical un-multiplied per-role scores in `isolated` and `shared`."""
    sc_a_own, ok_a_raw, errs_a, sub_a = score_rubric(checks_a, pass_threshold=pass_threshold)
    sc_b_own, ok_b_raw, errs_b, sub_b = score_rubric(checks_b, pass_threshold=pass_threshold)
    j_checks = (checks_joint or []) if active_mode != "isolated" else []
    sc_j, ok_j, errs_j, sub_j = score_rubric(j_checks, pass_threshold=0.999) if j_checks else (1.0, True, [], {})
    sc_a = sc_a_own
    sc_b = sc_b_own
    pass_a = bool(ok_a_raw)
    pass_b = bool(ok_b_raw)
    return {
        "task_id": task_id,
        "active_mode": active_mode,
        "score_a": sc_a,
        "score_b": sc_b,
        "score_joint": sc_j,
        "mean_score": round(0.5 * (sc_a + sc_b), 4),
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": bool(pass_a and pass_b and ok_j),
        "subchecks_a": sub_a,
        "subchecks_b": sub_b,
        "subchecks_joint": sub_j,
        "errors_a": errs_a[:10],
        "errors_b": errs_b[:10],
        "errors_joint": errs_j[:8],
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_hygiene(tickets_by_role),
        "telemetry": service_state,
    }


def _xml_esc(val: str) -> str:
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_odt_document(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        u_dir = Path(tmp) / "lo_odt"
        h_p = Path(tmp) / f"{path.stem}.html"
        lines = [
            "<!doctype html><html><head><meta charset='utf-8'/></head><body>",
            f"<h1>{_xml_esc(title)}</h1>",
        ]
        for sec_hdr, paras in sections:
            lines.append(f"<h2>{_xml_esc(sec_hdr)}</h2>")
            for p in paras:
                lines.append(f"<p>{_xml_esc(p)}</p>")
        lines.append("</body></html>")
        h_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cp = subprocess.run(
            [
                "libreoffice",
                f"-env:UserInstallation=file://{u_dir}",
                "--headless",
                "--convert-to",
                "odt",
                "--outdir",
                str(tmp),
                str(h_p),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        gen = Path(tmp) / f"{path.stem}.odt"
        if cp.returncode == 0 and gen.is_file() and gen.stat().st_size > 400:
            path.write_bytes(gen.read_bytes())
            return
    manifest_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">\n'
        '  <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
        '  <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>\n'
        '  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
        '</manifest:manifest>\n'
    )
    styles_xml = '<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"/>\n'
    body = [f"<text:p>{_xml_esc(title)}</text:p>"]
    for sec_hdr, paras in sections:
        body.append(f"<text:p>{_xml_esc(sec_hdr)}</text:p>")
        for p in paras:
            body.append(f"<text:p>{_xml_esc(p)}</text:p>")
    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">'
        "<office:body><office:text>" + "".join(body) + "</office:text></office:body></office:document-content>\n"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("META-INF/manifest.xml", manifest_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("styles.xml", styles_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", content_xml, compress_type=ZIP_DEFLATED)


def write_pdf_manual(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> None:
    """Render a realistic multi-section PDF specification manual via headless LibreOffice."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        odt_tmp = Path(tmp) / "spec.odt"
        u_dir = Path(tmp) / "lo_pdf"
        write_odt_document(odt_tmp, title, sections)
        cp = subprocess.run(
            [
                "libreoffice",
                f"-env:UserInstallation=file://{u_dir}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(odt_tmp),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        gen = Path(tmp) / "spec.pdf"
        if cp.returncode == 0 and gen.is_file():
            path.write_bytes(gen.read_bytes())


def read_odt_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        with ZipFile(path, "r") as zf:
            root = ET.fromstring(zf.read("content.xml"))
        return "\n".join("".join(el.itertext()).strip() for el in root.iter() if el.tag.endswith(("}h", "}p")) and "".join(el.itertext()).strip())
    except Exception:
        return ""


def extract_pdf_text(path: Path) -> str:
    if not path.is_file():
        return ""
    cp = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=15)
    return cp.stdout if cp.returncode == 0 else ""


def convert_to_pdf_headless(src_doc: Path, dst_pdf: Path) -> bool:
    dst_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        u_dir = Path(tmp) / "lo_conv"
        cp = subprocess.run(
            [
                "libreoffice",
                f"-env:UserInstallation=file://{u_dir}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(src_doc),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        gen = Path(tmp) / f"{src_doc.stem}.pdf"
        if cp.returncode == 0 and gen.is_file():
            dst_pdf.write_bytes(gen.read_bytes())
            return True
    return False


def launch_desktop_app_as_user(cmd_inner: str, wait_s: float = 1.8) -> None:
    """Launch a real installed desktop app (GIMP, Inkscape, FreeCAD, QGIS, LibreOffice, Designer, Linguist) on :99."""
    sh = (
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 XAUTHORITY=/tmp/x99.auth HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
        "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
        "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 "
        "QTWEBENGINE_DISABLE_SANDBOX=1 LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1 "
        "SAL_USE_VCLPLUGIN=gtk3; "
        f"{cmd_inner}"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", sh], check=True, capture_output=True, timeout=30)
    if wait_s > 0:
        time.sleep(wait_s)


def launch_studio_app(cmd_inner: str, wait_s: float = 2.2) -> None:
    """Launch a real desktop GUI app (LibreOffice, GIMP, Inkscape, Designer, Linguist, QGIS) as `studio_ui` on :99."""
    prep = (
        "id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; "
        "mkdir -p /srv/studio_project /tmp/rt-studio-aw /home/studio_ui/.config && "
        "chown -R studio_ui:studio_ui /srv/studio_project /tmp/rt-studio-aw /home/studio_ui && "
        "chmod 755 /srv/studio_project && chmod -R a+rX /srv/studio_project && "
        "chmod 755 /run/user/1000 /run/user/1000/at-spi 2>/dev/null || true; "
        "chmod 666 /run/user/1000/bus /run/user/1000/at-spi/bus* 2>/dev/null || true"
    )
    subprocess.run(["bash", "-lc", prep], check=True, capture_output=True, timeout=20)
    sh = (
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 XAUTHORITY=/tmp/x99.auth HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/rt-studio-aw "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
        "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
        "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 "
        "QTWEBENGINE_DISABLE_SANDBOX=1 LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1 "
        "SAL_USE_VCLPLUGIN=gtk3; "
        "umask 0022; "
        f"{cmd_inner}"
    )
    subprocess.run(["su", "-s", "/bin/bash", "studio_ui", "-c", sh], check=True, capture_output=True, timeout=30)
    if wait_s > 0:
        time.sleep(wait_s)


def boot_studio_browser(state_dir: Path, window_size: tuple[int, int] = (1260, 860)) -> None:
    """Launch authenticated HttpOnly Chromium as `studio_ui` (0700 profile, no CDP port, natural WM placement)."""
    boot_p = state_dir / "boot_url"
    if not boot_p.is_file():
        return
    cfg = json.loads(boot_p.read_text(encoding="utf-8"))
    boot_p.unlink(missing_ok=True)
    urls = cfg.get("urls") or ([cfg["url"]] if cfg.get("url") else [])
    u_args = " ".join(shlex.quote(str(u)) for u in urls)
    cmd = (
        "id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; "
        "mkdir -p /home/user/Downloads && chown studio_ui:0 /home/user/Downloads && chmod 755 /home/user/Downloads; "
        "chmod 755 /run/user/1000 /run/user/1000/at-spi 2>/dev/null || true; "
        "chmod 666 /run/user/1000/bus /run/user/1000/at-spi/bus* 2>/dev/null || true; "
        "mkdir -p /tmp/rt-studio-aw /home/studio_ui/.config/chromium && "
        "chown -R studio_ui:studio_ui /tmp/rt-studio-aw /home/studio_ui && chmod 700 /home/studio_ui/.config/chromium && "
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "su -s /bin/bash studio_ui -c '"
        "export DISPLAY=:99 XAUTHORITY=/tmp/x99.auth HOME=/home/studio_ui XDG_RUNTIME_DIR=/tmp/rt-studio-aw "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"'\"$AT_ADDR\"'\" AT_SPI_BUS=\"'\"$AT_ADDR\"'\"; "
        "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
        "--force-renderer-accessibility --user-data-dir=/home/studio_ui/.config/chromium "
        f"--window-size={window_size[0]},{window_size[1]} "
        f"{u_args} >/tmp/aw_studio_chr.log 2>&1 </dev/null &'; "
        "for _i in $(seq 1 25); do DISPLAY=:99 XAUTHORITY=/tmp/x99.auth wmctrl -lx 2>/dev/null | grep -qi chromium && break; sleep 0.3; done; sleep 0.6"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=30)


def boot_cdp_browser(urls: list[str], window_size: tuple[int, int] = (1380, 900)) -> None:
    """Launch singleton Chromium with --remote-debugging-port=9222 (natural WM placement, for responsive Web QA tasks)."""
    u_args = " ".join(shlex.quote(u) for u in urls)
    cmd = (
        "su -s /bin/bash user -c '"
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 XAUTHORITY=/tmp/x99.auth HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus AT_SPI_BUS_ADDRESS=\"$AT_ADDR\"; "
        "mkdir -p /home/user/.config/aw_chr_profile; "
        "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
        "--force-renderer-accessibility --remote-debugging-port=9222 --remote-allow-origins=* "
        f"--user-data-dir=/home/user/.config/aw_chr_profile --window-size={window_size[0]},{window_size[1]} "
        f"{u_args} >/tmp/aw_cdp_chr.log 2>&1 </dev/null &'; "
        "for _i in $(seq 1 30); do curl -fsS http://127.0.0.1:9222/json/version >/dev/null 2>&1 && break; sleep 0.3; done; sleep 0.6"
    )
    subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, timeout=30)


def evaluate_xlsx_isolated(path: Path) -> dict[str, dict[str, dict[str, str | float | None]]]:
    """Evaluate .xlsx formulas via an isolated headless LibreOffice profile so open GUI soffice.bin never locks."""
    if not path.is_file():
        return {}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            u_dir = tmp_dir / "lo_eval_profile"
            cp1 = subprocess.run(
                [
                    "libreoffice",
                    f"-env:UserInstallation=file://{u_dir}",
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    "ods",
                    "--outdir",
                    str(tmp_dir),
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )
            cand_ods = tmp_dir / f"{path.stem}.ods"
            if cp1.returncode == 0 and cand_ods.is_file():
                ods_p = tmp_dir / "eval_step.ods"
                cand_ods.rename(ods_p)
                cp2 = subprocess.run(
                    [
                        "libreoffice",
                        f"-env:UserInstallation=file://{u_dir}",
                        "--headless",
                        "--norestore",
                        "--convert-to",
                        "xlsx",
                        "--outdir",
                        str(tmp_dir),
                        str(ods_p),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                eval_xlsx = tmp_dir / "eval_step.xlsx"
                if cp2.returncode == 0 and eval_xlsx.is_file():
                    return read_multisheet_xlsx(eval_xlsx)
    except Exception:
        pass
    try:
        return read_multisheet_xlsx(path)
    except Exception:
        return {}


def cell_float(book: dict[str, dict[str, dict[str, Any]]], sheet: str, ref: str) -> float | None:
    val = ((book.get(sheet) or {}).get(ref) or {}).get("value")
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace(",", "").replace("$", "").strip())
        except ValueError:
            return None
    return None


def cell_str(book: dict[str, dict[str, dict[str, Any]]], sheet: str, ref: str) -> str:
    val = ((book.get(sheet) or {}).get(ref) or {}).get("value")
    return "" if val is None else str(val).strip()


def cell_formula(book: dict[str, dict[str, dict[str, Any]]], sheet: str, ref: str) -> str:
    f_val = ((book.get(sheet) or {}).get(ref) or {}).get("formula")
    return "" if f_val is None else str(f_val).strip()


__all__ = [
    "CellSpec",
    "FORBIDDEN_AW_PROMPT_PATTERNS",
    "boot_cdp_browser",
    "boot_studio_browser",
    "build_aw_grade_payload",
    "cell_float",
    "cell_formula",
    "cell_str",
    "convert_to_pdf_headless",
    "evaluate_xlsx_isolated",
    "extract_pdf_text",
    "launch_desktop_app_as_user",
    "launch_studio_app",
    "make_session_token",
    "read_json_safe",
    "read_multisheet_xlsx",
    "read_odt_text",
    "resource_lock",
    "score_rubric",
    "update_single_sheet_xlsx",
    "verify_prompt_hygiene",
    "write_json",
    "write_multisheet_xlsx",
    "write_odt_document",
    "write_pdf_manual",
]
