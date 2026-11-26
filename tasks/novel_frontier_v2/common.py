"""Shared authentic-software helpers for novel_frontier_v2 (zero inline synthetic GUI mockups, 100% read-only grading)."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Any, Iterator
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from tasks.thematic_arenas_v1.xlsx_utils import (
    CellSpec,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

FORBIDDEN_NF2_PROMPT_PATTERNS: tuple[str, ...] = (
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

UNO_PIPE_NAME = "nf2_uno_pipe"


def read_json_safe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@contextmanager
def file_atomic_lock(lock_name: str) -> Iterator[None]:
    lp = Path(f"/tmp/.nf2_lock_{lock_name}.lck")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def make_canary_code(prefix: str, salt: str) -> str:
    h = hashlib.sha256(f"nf2-20261124:{prefix}:{salt}".encode("utf-8")).hexdigest()[:8].upper()
    return f"{prefix}-{h}"


def verify_prompt_hygiene(tickets_by_role: dict[str, str]) -> dict[str, Any]:
    joined = "\n".join(tickets_by_role.values()).lower()
    hits = [pat for pat in FORBIDDEN_NF2_PROMPT_PATTERNS if pat in joined]
    return {"ok": len(hits) == 0, "forbidden_hits": hits}


def score_weighted_checks(
    checks: list[tuple[str, bool, float, str]],
    pass_threshold: float = 1.0,
) -> tuple[float, bool, list[str], dict[str, bool]]:
    tot_w = sum(max(0.0, float(w)) for _, _, w, _ in checks) or 1.0
    got_w = 0.0
    errs: list[str] = []
    sub: dict[str, bool] = {}
    for cid, ok, w, msg in checks:
        b_ok = bool(ok)
        sub[cid] = b_ok
        if b_ok:
            got_w += max(0.0, float(w))
        elif msg:
            errs.append(msg)
    sc = round(got_w / tot_w, 4)
    passed = (sc >= pass_threshold) and (len(errs) == 0 if pass_threshold >= 0.999 else True)
    return sc, passed, errs, sub


def build_grade_payload(
    *,
    task_id: str,
    checks_a: list[tuple[str, bool, float, str]],
    checks_b: list[tuple[str, bool, float, str]],
    checks_joint: list[tuple[str, bool, float, str]] | None,
    tickets_by_role: dict[str, str],
    service_state: dict[str, Any],
    wall_seconds: float,
    pass_threshold: float = 1.0,
) -> dict[str, Any]:
    j_list = list(checks_joint or [])
    full_a = list(checks_a) + j_list
    full_b = list(checks_b) + j_list
    sc_a, ok_a_own, errs_a, sub_a = score_weighted_checks(full_a, pass_threshold=pass_threshold)
    sc_b, ok_b_own, errs_b, sub_b = score_weighted_checks(full_b, pass_threshold=pass_threshold)
    _, ok_j, errs_j, sub_j = score_weighted_checks(j_list, pass_threshold=0.999) if j_list else (1.0, True, [], {})
    pass_a = bool(ok_a_own and ok_j)
    pass_b = bool(ok_b_own and ok_j)
    return {
        "task_id": task_id,
        "score_a": sc_a,
        "score_b": sc_b,
        "mean_score": round(0.5 * (sc_a + sc_b), 4),
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": bool(pass_a and pass_b),
        "subchecks_a": sub_a,
        "subchecks_b": sub_b,
        "subchecks_joint": sub_j,
        "errors_a": errs_a[:12],
        "errors_b": errs_b[:12],
        "errors_joint": errs_j[:8],
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_hygiene(tickets_by_role),
        "telemetry": service_state,
    }


def _xml_esc(val: str) -> str:
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_simple_odt(path: Path, title: str, tagged_paragraphs: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        u_dir = Path(tmp) / "lo_u"
        hp = Path(tmp) / "doc.html"
        html_lines = ["<!doctype html><html><head><meta charset='utf-8'/></head><body>", f"<h1>{_xml_esc(title)}</h1>"]
        for tag, body in tagged_paragraphs:
            prefix = f"[{_xml_esc(tag)}] " if tag else ""
            html_lines.append(f"<p>{prefix}{_xml_esc(body)}</p>")
        html_lines.append("</body></html>")
        hp.write_text("\n".join(html_lines) + "\n", encoding="utf-8")
        cp = subprocess.run(
            ["libreoffice", f"-env:UserInstallation=file://{u_dir}", "--headless", "--convert-to", "odt", "--outdir", str(tmp), str(hp)],
            capture_output=True, text=True, timeout=45,
        )
        gen = Path(tmp) / "doc.odt"
        if cp.returncode == 0 and gen.is_file() and gen.stat().st_size > 300:
            path.write_bytes(gen.read_bytes())
            return
    manifest_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">\n'
        '  <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
        '  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
        '</manifest:manifest>\n'
    )
    p_xml = [f"<text:p>{_xml_esc(title)}</text:p>"] + [
        f"<text:p>{('[' + _xml_esc(t) + '] ') if t else ''}{_xml_esc(b)}</text:p>" for t, b in tagged_paragraphs
    ]
    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">'
        "<office:body><office:text>" + "".join(p_xml) + "</office:text></office:body></office:document-content>\n"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("META-INF/manifest.xml", manifest_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", content_xml, compress_type=ZIP_DEFLATED)


def read_odt_plain_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        with ZipFile(path, "r") as zf:
            root = ET.fromstring(zf.read("content.xml"))
        lines = []
        for el in root.iter():
            if el.tag.endswith(("}h", "}p")):
                s = "".join(el.itertext()).strip()
                if s:
                    lines.append(s)
        return "\n".join(lines)
    except Exception:
        return ""


def write_multipage_sop_pdf(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        u_dir = Path(tmp) / "lo_pdf"
        hp = Path(tmp) / "sop.html"
        parts = [
            "<!doctype html><html><head><meta charset='utf-8'/>"
            "<style>body{font-family:Liberation Sans,sans-serif;font-size:11pt;line-height:1.38} "
            "h1{font-size:16pt;border-bottom:1px solid #333} h2{font-size:12.5pt;margin-top:14px}</style></head><body>",
            f"<h1>{_xml_esc(title)}</h1>",
        ]
        for shdr, paras in sections:
            parts.append(f"<h2>{_xml_esc(shdr)}</h2>")
            for p in paras:
                parts.append(f"<p>{_xml_esc(p)}</p>")
        parts.append("</body></html>")
        hp.write_text("\n".join(parts) + "\n", encoding="utf-8")
        cp = subprocess.run(
            ["libreoffice", f"-env:UserInstallation=file://{u_dir}", "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(hp)],
            capture_output=True, text=True, timeout=45,
        )
        gen = Path(tmp) / "sop.pdf"
        if cp.returncode == 0 and gen.is_file():
            path.write_bytes(gen.read_bytes())


def extract_pdf_text(path: Path) -> str:
    if not path.is_file():
        return ""
    cp = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=15)
    return cp.stdout if cp.returncode == 0 else ""


def render_scanned_exhibit_png(
    path: Path,
    header: str,
    lines: list[str],
    *,
    stamp_text: str = "CONTROLLED ENGINEERING EXHIBIT",
    tilt_deg: float = -0.20,
) -> None:
    from PIL import Image, ImageDraw, ImageFont
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1220, max(520, 155 + 38 * len(lines))
    img = Image.new("RGB", (w, h), (247, 245, 239))
    dr = ImageDraw.Draw(img)
    try:
        f_hdr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 21)
        f_bdy = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
        f_stp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        f_hdr = f_bdy = f_stp = ImageFont.load_default()
    dr.rectangle([24, 22, w - 24, h - 22], outline=(62, 68, 78), width=2)
    dr.rectangle([24, 22, w - 24, 72], fill=(32, 43, 62))
    dr.text((42, 35), header, fill=(244, 247, 252), font=f_hdr)
    y = 92
    for ln in lines:
        dr.text((44, y), ln, fill=(24, 28, 36), font=f_bdy)
        y += 35
    dr.rectangle([w - 370, h - 68, w - 42, h - 34], outline=(165, 38, 38), width=2)
    dr.text((w - 356, h - 59), stamp_text, fill=(165, 38, 38), font=f_stp)
    if abs(tilt_deg) > 0.01:
        img = img.rotate(tilt_deg, resample=Image.BICUBIC, expand=False, fillcolor=(247, 245, 239))
    img.save(path, format="PNG")


def evaluate_xlsx_via_libreoffice(path: Path) -> dict[str, dict[str, dict[str, str | float | None]]]:
    if not path.is_file():
        return {}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            u_dir = td / "lo_eval"
            cp1 = subprocess.run(
                ["libreoffice", f"-env:UserInstallation=file://{u_dir}", "--headless", "--norestore", "--convert-to", "ods", "--outdir", str(td), str(path)],
                capture_output=True, text=True, timeout=45,
            )
            c_ods = td / f"{path.stem}.ods"
            if cp1.returncode == 0 and c_ods.is_file():
                step_ods = td / "step.ods"
                c_ods.rename(step_ods)
                cp2 = subprocess.run(
                    ["libreoffice", f"-env:UserInstallation=file://{u_dir}", "--headless", "--norestore", "--convert-to", "xlsx", "--outdir", str(td), str(step_ods)],
                    capture_output=True, text=True, timeout=45,
                )
                ev_x = td / "step.xlsx"
                if cp2.returncode == 0 and ev_x.is_file():
                    return read_multisheet_xlsx(ev_x)
    except Exception:
        pass
    return read_multisheet_xlsx(path)


def _run_as_desktop_user(inner_cmd: str, timeout_s: int = 30) -> subprocess.CompletedProcess[str]:
    env_prefix = (
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 XAUTHORITY=/run/user/1000/x99.auth HOME=/home/user USER=user LOGNAME=user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
        "AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" AT_SPI_BUS=\"$AT_ADDR\" "
        "GTK_MODULES=gail:atk-bridge GNOME_ACCESSIBILITY=1 ACCESSIBILITY_ENABLED=1 "
        "QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 "
        "QTWEBENGINE_DISABLE_SANDBOX=1 LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1 SAL_USE_VCLPLUGIN=gtk3; "
    )
    return subprocess.run(
        ["su", "-s", "/bin/bash", "user", "-c", env_prefix + inner_cmd],
        check=True, capture_output=True, text=True, timeout=timeout_s,
    )


def launch_chromium_natural(urls: list[str], width: int = 1340, height: int = 880) -> None:
    """Launch authenticated Chromium with natural WM placement (no --window-position, no :9222 bypass)."""
    u_args = " ".join(shlex.quote(u) for u in urls)
    _run_as_desktop_user(
        "mkdir -p /home/user/.config/nf2_chr_profile; "
        "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
        "--force-renderer-accessibility --user-data-dir=/home/user/.config/nf2_chr_profile "
        f"--window-size={width},{height} {u_args} >/tmp/nf2_chromium.log 2>&1 </dev/null &"
    )
    time.sleep(2.3)


def launch_libreoffice_uno_natural(doc_paths: list[Path], pipe_name: str = UNO_PIPE_NAME) -> None:
    """Open LibreOffice documents on :99 via desk-local UNIX pipe (isolated from guest_bash)."""
    if not doc_paths:
        return
    q_docs = " ".join(shlex.quote(str(p)) for p in doc_paths)
    accept = f"pipe,name={pipe_name};urp;"
    _run_as_desktop_user(
        f"nohup libreoffice --norestore --nologo --nofirststartwizard --accept={shlex.quote(accept)} {q_docs} >/tmp/nf2_soffice.log 2>&1 </dev/null &"
    )
    for _ in range(45):
        if list(Path("/tmp").glob(f"*{pipe_name}*")):
            break
        time.sleep(0.3)
    time.sleep(1.4)


def reload_uno_pipe_documents(paths: list[Path], pipe_name: str = UNO_PIPE_NAME) -> None:
    """Author-side desk-local helper for deterministic 5-gate solve_role()."""
    uris = [p.resolve().as_uri() for p in paths]
    fdirs = sorted({str(p.resolve().parent) for p in paths})
    code = (
        "import glob, os, time, uno\n"
        "local = uno.getComponentContext()\n"
        "res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)\n"
        f"ctx = res.resolve('uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext')\n"
        "desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)\n"
        "pv = uno.createUnoStruct('com.sun.star.beans.PropertyValue'); pv.Name = 'Silent'; pv.Value = True\n"
        "keeper = desk.loadComponentFromURL('private:factory/swriter', '_blank', 0, (pv,))\n"
        f"targets = set({json.dumps(uris)})\n"
        "en = desk.getComponents().createEnumeration()\n"
        "to_close = []\n"
        "while en.hasMoreElements():\n"
        "    d = en.nextElement()\n"
        "    if hasattr(d, 'getURL') and d.getURL() in targets:\n"
        "        to_close.append(d)\n"
        "for d in to_close:\n"
        "    try: d.setModified(False); d.close(True)\n"
        "    except Exception: pass\n"
        "time.sleep(0.15)\n"
        f"for fd in {json.dumps(fdirs)}:\n"
        "    for lk in glob.glob(os.path.join(fd, '.~lock.*')):\n"
        "        try: os.unlink(lk)\n"
        "        except OSError: pass\n"
        "for u in sorted(targets):\n"
        "    desk.loadComponentFromURL(u, '_blank', 0, (pv,))\n"
        "try: keeper.setModified(False); keeper.close(True)\n"
        "except Exception: pass\n"
    )
    for attempt in range(2):
        cp = subprocess.run(
            ["su", "-s", "/bin/bash", "user", "-c", f"export HOME=/home/user USER=user LOGNAME=user; python3 -c {shlex.quote(code)}"],
            capture_output=True, text=True, timeout=25,
        )
        if cp.returncode == 0:
            return
        time.sleep(0.4)


def sync_uno_writer_text(odt_path: Path, full_text: str, pipe_name: str = UNO_PIPE_NAME) -> None:
    """Author-side helper to update an already-open Writer .odt document in-place via UNO without lock races."""
    uri = odt_path.resolve().as_uri()
    code = (
        "import uno\n"
        "local = uno.getComponentContext()\n"
        "res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)\n"
        f"ctx = res.resolve('uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext')\n"
        "desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)\n"
        f"want = {json.dumps(uri)}\n"
        f"txt = {json.dumps(full_text)}\n"
        "en = desk.getComponents().createEnumeration()\n"
        "while en.hasMoreElements():\n"
        "    d = en.nextElement()\n"
        "    if hasattr(d, 'getURL') and d.getURL() == want and hasattr(d, 'getText'):\n"
        "        d.getText().setString(txt); d.store(); break\n"
    )
    subprocess.run(
        ["su", "-s", "/bin/bash", "user", "-c", f"export HOME=/home/user USER=user LOGNAME=user; python3 -c {shlex.quote(code)}"],
        capture_output=True, text=True, timeout=20,
    )


def sync_uno_calc_cells(xlsx_path: Path, sheet_name: str, cell_updates: dict[str, int | float | str], pipe_name: str = UNO_PIPE_NAME) -> None:
    """Author-side helper to update an already-open Calc .xlsx sheet in-place via UNO without close/reopen races."""
    uri = xlsx_path.resolve().as_uri()
    code = (
        "import uno\n"
        "local = uno.getComponentContext()\n"
        "res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)\n"
        f"ctx = res.resolve('uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext')\n"
        "desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)\n"
        f"want = {json.dumps(uri)}\n"
        f"sh_nm = {json.dumps(sheet_name)}\n"
        f"upds = {json.dumps(cell_updates)}\n"
        "en = desk.getComponents().createEnumeration()\n"
        "while en.hasMoreElements():\n"
        "    d = en.nextElement()\n"
        "    if hasattr(d, 'getURL') and d.getURL() == want and hasattr(d, 'getSheets'):\n"
        "        sh = d.getSheets().getByName(sh_nm)\n"
        "        for ref, val in upds.items():\n"
        "            col = ord(ref[0].upper()) - 65; row = int(ref[1:]) - 1\n"
        "            cl = sh.getCellByPosition(col, row)\n"
        "            if isinstance(val, (int, float)):\n"
        "                cl.setValue(float(val))\n"
        "            elif isinstance(val, str) and val.startswith('='):\n"
        "                cl.setFormula(val)\n"
        "            else:\n"
        "                cl.setString(str(val))\n"
        "        d.store(); break\n"
    )
    subprocess.run(
        ["su", "-s", "/bin/bash", "user", "-c", f"export HOME=/home/user USER=user LOGNAME=user; python3 -c {shlex.quote(code)}"],
        capture_output=True, text=True, timeout=20,
    )


def inspect_live_uno_documents_readonly(pipe_name: str = UNO_PIPE_NAME) -> dict[str, Any]:
    """Read-only inspection of live open LibreOffice documents via desk-local UNIX pipe."""
    probe = (
        "import json, uno\n"
        "out = {'connected': False, 'docs': {}}\n"
        "try:\n"
        "    local = uno.getComponentContext()\n"
        "    res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)\n"
        f"    ctx = res.resolve('uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext')\n"
        "    desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)\n"
        "    out['connected'] = True\n"
        "    en = desk.getComponents().createEnumeration()\n"
        "    while en.hasMoreElements():\n"
        "        d = en.nextElement()\n"
        "        url = d.getURL() if hasattr(d, 'getURL') else ''\n"
        "        info = {'is_modified': bool(d.isModified()) if hasattr(d, 'isModified') else False}\n"
        "        if hasattr(d, 'getText'):\n"
        "            info['kind'] = 'writer'\n"
        "            info['text'] = d.getText().getString()\n"
        "            info['table_count'] = int(d.getTextTables().getCount()) if hasattr(d, 'getTextTables') else 0\n"
        "        elif hasattr(d, 'getSheets'):\n"
        "            info['kind'] = 'calc'\n"
        "            shs = {}\n"
        "            for nm in list(d.getSheets().getElementNames()):\n"
        "                sh = d.getSheets().getByName(nm)\n"
        "                cells = {}\n"
        "                for r in range(24):\n"
        "                    for c in range(10):\n"
        "                        s = sh.getCellByPosition(c, r).getString().strip()\n"
        "                        if s:\n"
        "                            cells[f'{chr(65+c)}{r+1}'] = s\n"
        "                shs[nm] = cells\n"
        "            info['sheets'] = shs\n"
        "        out['docs'][url] = info\n"
        "except Exception as e:\n"
        "    out['error'] = str(e)\n"
        "print(json.dumps(out))\n"
    )
    try:
        cp = subprocess.run(
            ["su", "-s", "/bin/bash", "user", "-c", f"export HOME=/home/user USER=user LOGNAME=user; python3 -c {shlex.quote(probe)}"],
            capture_output=True, text=True, timeout=25,
        )
        if cp.returncode == 0 and cp.stdout.strip():
            return json.loads(cp.stdout.strip().splitlines()[-1])
    except Exception:
        pass
    return {"connected": False, "docs": {}}


def launch_blender_gui_natural(blend_path: Path) -> None:
    """Launch real Blender 3.4 GUI on :99 with read-only live 3D & VSE strip telemetry."""
    hook_py = Path("/run/user/1000/blender_nf2_hook.py")
    hook_py.parent.mkdir(parents=True, exist_ok=True)
    hook_py.write_text(
        "import bpy, json, os\n"
        "STATE_P = '/run/user/1000/blender_nf2_live.json'\n"
        "CMD_P = '/run/user/1000/blender_nf2_cmd.json'\n"
        "def _poll():\n"
        "    try:\n"
        "        if os.path.isfile(CMD_P):\n"
        "            with open(CMD_P, 'r', encoding='utf-8') as f:\n"
        "                cmd = json.load(f)\n"
        "            os.unlink(CMD_P)\n"
        "            fp = cmd.get('open_mainfile') or bpy.data.filepath\n"
        "            if fp and os.path.isfile(fp):\n"
        "                bpy.ops.wm.open_mainfile(filepath=fp)\n"
        "        sc = bpy.context.scene\n"
        "        strips = []\n"
        "        if sc.sequence_editor:\n"
        "            for sq in sc.sequence_editor.sequences_all:\n"
        "                strips.append({'name': sq.name, 'type': sq.type, 'ch': int(sq.channel), 'start': int(sq.frame_final_start), 'end': int(sq.frame_final_end)})\n"
        "        props = {k: sc.get(k) for k in sc.keys() if not k.startswith('_') and isinstance(sc.get(k), (int, float, str, bool))}\n"
        "        st = {'running': True, 'filepath': bpy.data.filepath, 'is_dirty': bool(bpy.data.is_dirty), 'obj_count': len(bpy.data.objects), 'vse_strips': strips, 'scene_props': props}\n"
        "        tp = STATE_P + '.tmp'\n"
        "        with open(tp, 'w', encoding='utf-8') as f:\n"
        "            json.dump(st, f)\n"
        "        os.replace(tp, STATE_P)\n"
        "    except Exception:\n"
        "        pass\n"
        "    return 0.5\n"
        "bpy.app.timers.register(_poll, first_interval=0.4, persistent=True)\n",
        encoding="utf-8",
    )
    try:
        os.chmod(hook_py, 0o644)
        os.chown(hook_py, 1000, 0)
    except OSError:
        pass
    _run_as_desktop_user(
        f"nohup blender {shlex.quote(str(blend_path))} --python /run/user/1000/blender_nf2_hook.py >/tmp/nf2_blender.log 2>&1 </dev/null &"
    )
    for _ in range(35):
        if Path("/run/user/1000/blender_nf2_live.json").is_file():
            break
        time.sleep(0.25)
    time.sleep(1.0)


def reload_blender_gui_file(blend_path: Path) -> None:
    cmd_p = Path("/run/user/1000/blender_nf2_cmd.json")
    if cmd_p.parent.is_dir():
        write_json(cmd_p, {"open_mainfile": str(blend_path.resolve())})
        for _ in range(18):
            if not cmd_p.exists():
                break
            time.sleep(0.2)
        time.sleep(0.6)


def inspect_live_blender_readonly() -> dict[str, Any]:
    st = read_json_safe(Path("/run/user/1000/blender_nf2_live.json"))
    return st if st else {"running": False, "is_dirty": False}


def launch_qgis_gui_natural(project_path: Path | None = None) -> None:
    """Launch real QGIS 3.22 GUI on :99 with read-only live project/layer state telemetry."""
    hook_py = Path("/run/user/1000/qgis_nf2_hook.py")
    hook_py.parent.mkdir(parents=True, exist_ok=True)
    hook_py.write_text(
        "import json, os\n"
        "from qgis.core import QgsProject\n"
        "from qgis.PyQt.QtCore import QTimer\n"
        "STATE_P = '/run/user/1000/qgis_nf2_live.json'\n"
        "CMD_P = '/run/user/1000/qgis_nf2_cmd.json'\n"
        "def _qpoll():\n"
        "    try:\n"
        "        prj = QgsProject.instance()\n"
        "        if os.path.isfile(CMD_P):\n"
        "            with open(CMD_P, 'r', encoding='utf-8') as f:\n"
        "                cmd = json.load(f)\n"
        "            os.unlink(CMD_P)\n"
        "            rp = cmd.get('read_project')\n"
        "            if rp and os.path.isfile(rp):\n"
        "                prj.read(rp)\n"
        "        lyrs = {}\n"
        "        for lid, lyr in prj.mapLayers().items():\n"
        "            lyrs[lyr.name()] = {'crs': lyr.crs().authid(), 'subset': getattr(lyr, 'subsetString', lambda: '')(), 'count': int(lyr.featureCount()) if hasattr(lyr, 'featureCount') else -1}\n"
        "        st = {'running': True, 'file': prj.fileName(), 'crs': prj.crs().authid(), 'is_dirty': bool(prj.isDirty()), 'layers': lyrs}\n"
        "        tp = STATE_P + '.tmp'\n"
        "        with open(tp, 'w', encoding='utf-8') as f:\n"
        "            json.dump(st, f)\n"
        "        os.replace(tp, STATE_P)\n"
        "    except Exception:\n"
        "        pass\n"
        "_t = QTimer(); _t.timeout.connect(_qpoll); _t.start(500)\n"
        "QgsProject.instance()._nf2_timer = _t; _qpoll()\n",
        encoding="utf-8",
    )
    try:
        os.chmod(hook_py, 0o644)
        os.chown(hook_py, 1000, 0)
    except OSError:
        pass
    proj_arg = shlex.quote(str(project_path)) if project_path else ""
    _run_as_desktop_user(
        f"nohup qgis --nologo --code /run/user/1000/qgis_nf2_hook.py {proj_arg} >/tmp/nf2_qgis.log 2>&1 </dev/null &"
    )
    for _ in range(40):
        if Path("/run/user/1000/qgis_nf2_live.json").is_file():
            break
        time.sleep(0.3)
    time.sleep(1.2)


def reload_qgis_gui_project(project_path: Path) -> None:
    cmd_p = Path("/run/user/1000/qgis_nf2_cmd.json")
    if cmd_p.parent.is_dir():
        write_json(cmd_p, {"read_project": str(project_path.resolve())})
        for _ in range(18):
            if not cmd_p.exists():
                break
            time.sleep(0.25)
        time.sleep(0.6)


def inspect_live_qgis_readonly() -> dict[str, Any]:
    st = read_json_safe(Path("/run/user/1000/qgis_nf2_live.json"))
    return st if st else {"running": False, "is_dirty": False}


def launch_freecad_gui_natural(fcstd_path: Path) -> None:
    mod_dir = Path("/usr/share/freecad/Mod/Nf2Live")
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "InitGui.py").write_text(
        "from PySide2 import QtCore\n"
        "import FreeCAD\n"
        "def _nf2_fc_poll():\n"
        "    import json, os, FreeCAD, FreeCADGui\n"
        "    st_p = '/run/user/1000/freecad_nf2_live.json'\n"
        "    cmd_p = '/run/user/1000/freecad_nf2_cmd.json'\n"
        "    try:\n"
        "        if os.path.isfile(cmd_p):\n"
        "            with open(cmd_p, 'r', encoding='utf-8') as f:\n"
        "                cmd = json.load(f)\n"
        "            os.unlink(cmd_p)\n"
        "            rp = cmd.get('reopen')\n"
        "            if rp and os.path.isfile(rp):\n"
        "                for nm in list(FreeCAD.listDocuments().keys()):\n"
        "                    try: FreeCAD.closeDocument(nm)\n"
        "                    except Exception: pass\n"
        "                FreeCAD.openDocument(rp)\n"
        "        d = FreeCAD.ActiveDocument\n"
        "        if d:\n"
        "            gd = FreeCADGui.ActiveDocument\n"
        "            objs = {}\n"
        "            for o in d.Objects:\n"
        "                if hasattr(o, 'Shape') and o.Shape:\n"
        "                    objs[o.Name] = {\n"
        "                        'vol': round(float(o.Shape.Volume), 1),\n"
        "                        'z_cg': round(float(o.Shape.CenterOfGravity.z), 2),\n"
        "                        'mass': round(float(getattr(o, 'CommittedMassKg', -1.0)), 3),\n"
        "                        'status': str(getattr(o, 'Status', '')),\n"
        "                    }\n"
        "            st = {'running': True, 'file': d.FileName, 'is_dirty': bool(getattr(gd, 'Modified', False)), 'objects': objs}\n"
        "            tp = st_p + '.tmp'\n"
        "            with open(tp, 'w', encoding='utf-8') as f:\n"
        "                json.dump(st, f)\n"
        "            os.replace(tp, st_p)\n"
        "    except Exception:\n"
        "        pass\n"
        "_t = QtCore.QTimer(); _t.timeout.connect(_nf2_fc_poll); _t.start(500)\n"
        "FreeCAD._nf2_fc_timer = _t; _nf2_fc_poll()\n",
        encoding="utf-8",
    )
    _run_as_desktop_user(f"nohup freecad {shlex.quote(str(fcstd_path))} >/tmp/nf2_freecad.log 2>&1 </dev/null &")
    for _ in range(30):
        if Path("/run/user/1000/freecad_nf2_live.json").is_file():
            break
        time.sleep(0.3)
    time.sleep(1.0)


def reload_freecad_gui_file(fcstd_path: Path) -> None:
    cmd_p = Path("/run/user/1000/freecad_nf2_cmd.json")
    if cmd_p.parent.is_dir():
        write_json(cmd_p, {"reopen": str(fcstd_path.resolve())})
        for _ in range(20):
            if not cmd_p.exists():
                break
            time.sleep(0.25)
        time.sleep(0.8)


def inspect_live_freecad_readonly() -> dict[str, Any]:
    st = read_json_safe(Path("/run/user/1000/freecad_nf2_live.json"))
    return st if st else {"running": False, "is_dirty": False, "objects": {}}


def launch_gimp_gui_natural(xcf_paths: list[Path]) -> None:
    args = " ".join(shlex.quote(str(p)) for p in xcf_paths)
    _run_as_desktop_user(f"nohup gimp --no-splash {args} >/tmp/nf2_gimp.log 2>&1 </dev/null &")
    time.sleep(3.2)


def launch_inkscape_gui_natural(svg_paths: list[Path]) -> None:
    for idx, p in enumerate(svg_paths):
        _run_as_desktop_user(f"nohup inkscape {shlex.quote(str(p))} >/tmp/nf2_inkscape_{idx}.log 2>&1 </dev/null &")
        time.sleep(1.8)


def compile_qhc_collection(out_qhc: Path, custom_filters: dict[str, list[tuple[str, str, str]]]) -> None:
    """Build a native Qt5 Assistant .qhc help collection with filterable HTML engineering manuals."""
    out_qhc.parent.mkdir(parents=True, exist_ok=True)
    out_dir = out_qhc.parent.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        filt_defs = []
        filt_secs = []
        for fname, pages in custom_filters.items():
            fattr = fname.lower().replace(" ", "_")
            filt_defs.append(f'  <customFilter name="{_xml_esc(fname)}"><filterAttribute>{_xml_esc(fattr)}</filterAttribute></customFilter>')
            tocs = []
            flist = []
            for slug, title, html_body in pages:
                fn = f"{fattr}_{slug}.html"
                (td / fn).write_text(f"<!doctype html><html><head><meta charset='utf-8'/><title>{_xml_esc(title)}</title></head><body>{html_body}</body></html>\n", encoding="utf-8")
                tocs.append(f'      <section title="{_xml_esc(title)}" ref="{_xml_esc(fn)}"/>')
                flist.append(f'      <file>{_xml_esc(fn)}</file>')
            filt_secs.append(
                "  <filterSection>\n"
                f"    <filterAttribute>{_xml_esc(fattr)}</filterAttribute>\n"
                "    <toc>\n" + "\n".join(tocs) + "\n    </toc>\n"
                "    <files>\n" + "\n".join(flist) + "\n    </files>\n"
                "  </filterSection>"
            )
        (td / "manual.qhp").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<QtHelpProject version="1.0">\n'
            '  <namespace>org.paragui.nf2.manuals</namespace>\n'
            '  <virtualFolder>manuals</virtualFolder>\n'
            + "\n".join(filt_defs) + "\n"
            + "\n".join(filt_secs) + "\n"
            '</QtHelpProject>\n',
            encoding="utf-8",
        )
        (td / "collection.qhcp").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<QHelpCollectionProject version="1.0">\n'
            '  <assistant>\n'
            '    <title>Certified Engineering Documentation</title>\n'
            '    <enableFilterFunctionality visible="true">true</enableFilterFunctionality>\n'
            '    <enableDocumentationManager>true</enableDocumentationManager>\n'
            '    <enableAddressBar visible="true">true</enableAddressBar>\n'
            '  </assistant>\n'
            '  <docFiles>\n'
            '    <generate><file><input>manual.qhp</input><output>manual.qch</output></file></generate>\n'
            '    <register><file>manual.qch</file></register>\n'
            '  </docFiles>\n'
            '</QHelpCollectionProject>\n',
            encoding="utf-8",
        )
        # Run qhelpgenerator from out_dir after staging inputs so FileNameTable inside .qhc stores relative 'manual.qch' (never /tmp/tmpXXXX/manual.qch)!
        staged_files: list[Path] = []
        for f in td.iterdir():
            dst = out_dir / f.name
            dst.write_bytes(f.read_bytes())
            staged_files.append(dst)
        try:
            subprocess.run(
                ["qhelpgenerator", "collection.qhcp", "-o", out_qhc.name],
                cwd=str(out_dir),
                check=True,
                capture_output=True,
                timeout=30,
            )
        finally:
            for sf in staged_files:
                if sf.suffix in (".html", ".qhp", ".qhcp"):
                    sf.unlink(missing_ok=True)


def launch_qt_assistant_natural(qhc_path: Path) -> None:
    # Stage .qhc + .qch inside an unsearchable 0711 vault so find/glob cannot enumerate raw SQLite help files
    vault_root = Path("/opt/nf_qhc_vault")
    vault_dir = vault_root / secrets.token_hex(12)
    vault_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(vault_root, 0o711)
    for src_f in qhc_path.parent.iterdir():
        dst_f = vault_dir / src_f.name
        dst_f.write_bytes(src_f.read_bytes())
        os.chown(dst_f, 1000, 1000)
        os.chmod(dst_f, 0o600)
    os.chown(vault_dir, 1000, 1000)
    os.chmod(vault_dir, 0o700)
    shutil.rmtree(qhc_path.parent, ignore_errors=True)
    vault_qhc = vault_dir / qhc_path.name
    _run_as_desktop_user(
        f"nohup assistant -collectionFile {shlex.quote(str(vault_qhc))} >/tmp/nf2_assistant.log 2>&1 </dev/null &"
    )
    time.sleep(2.4)


def launch_qt_designer_natural(ui_path: Path) -> None:
    _run_as_desktop_user(f"nohup designer {shlex.quote(str(ui_path))} >/tmp/nf2_designer.log 2>&1 </dev/null &")
    time.sleep(2.4)


def launch_qt_linguist_natural(ts_path: Path) -> None:
    _run_as_desktop_user(f"nohup linguist {shlex.quote(str(ts_path))} >/tmp/nf2_linguist.log 2>&1 </dev/null &")
    time.sleep(2.4)


def inspect_live_x11_window_titles_readonly() -> list[str]:
    """Read-only snapshot of live X11 window titles on :99."""
    try:
        cp = subprocess.run(
            ["su", "-s", "/bin/bash", "user", "-c", "DISPLAY=:99 XAUTHORITY=/run/user/1000/x99.auth wmctrl -l 2>/dev/null || true"],
            capture_output=True, text=True, timeout=10,
        )
        titles = []
        for ln in cp.stdout.splitlines():
            parts = ln.split(None, 3)
            if len(parts) == 4:
                titles.append(parts[3].strip())
        return titles
    except Exception:
        return []


__all__ = [
    "CellSpec",
    "FORBIDDEN_NF2_PROMPT_PATTERNS",
    "UNO_PIPE_NAME",
    "build_grade_payload",
    "compile_qhc_collection",
    "evaluate_xlsx_via_libreoffice",
    "extract_pdf_text",
    "file_atomic_lock",
    "inspect_live_blender_readonly",
    "inspect_live_freecad_readonly",
    "inspect_live_qgis_readonly",
    "inspect_live_uno_documents_readonly",
    "inspect_live_x11_window_titles_readonly",
    "launch_blender_gui_natural",
    "launch_chromium_natural",
    "launch_freecad_gui_natural",
    "launch_gimp_gui_natural",
    "launch_inkscape_gui_natural",
    "launch_libreoffice_uno_natural",
    "launch_qgis_gui_natural",
    "launch_qt_assistant_natural",
    "launch_qt_designer_natural",
    "launch_qt_linguist_natural",
    "make_canary_code",
    "read_json_safe",
    "read_multisheet_xlsx",
    "read_odt_plain_text",
    "reload_blender_gui_file",
    "reload_freecad_gui_file",
    "reload_qgis_gui_project",
    "reload_uno_pipe_documents",
    "render_scanned_exhibit_png",
    "score_weighted_checks",
    "sync_uno_calc_cells",
    "sync_uno_writer_text",
    "update_single_sheet_xlsx",
    "verify_prompt_hygiene",
    "write_json",
    "write_multipage_sop_pdf",
    "write_multisheet_xlsx",
    "write_simple_odt",
]
