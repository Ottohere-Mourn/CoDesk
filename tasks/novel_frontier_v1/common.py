"""Authentic desktop helpers, multi-page PDF/scan generators, read-only UNO inspector & rubric engine for novel_frontier_v1.

Strictly adheres to the updated $paragui-case-design contract:
  - Zero inline synthetic PyQt/GTK/Tk toy GUI app mockups.
  - Zero hardcoded CUA driver binaries in task modules or graders.
  - Natural window-manager placement at boot (zero rigid split-screen coordinates).
  - Read-only post-episode grading (zero post-exit Ctrl+S injection).
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Any, Iterator
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from tasks.thematic_arenas_v1.xlsx_utils import (
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

FORBIDDEN_PROMPT_TOKENS: tuple[str, ...] = (
    "do not modify",
    "ctrl+z",
    "cmd+z",
    "command+z",
    "other agent",
    "another agent",
    "peer agent",
    "concurrent agent",
    "teammate",
    "colleague",
    "qwen_cua_driver",
    "desktop.click",
    "guest_bash",
    "click_and_type",
)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json_safe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@contextmanager
def file_atomic_lock(lock_name: str) -> Iterator[None]:
    """Fine-grained short-lived advisory file lock (<0.2s) for atomic shared-file commits."""
    lp = Path(f"/tmp/.nf_atomic_{lock_name}.lck")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def verify_prompt_hygiene(tickets_by_role: dict[str, str]) -> dict[str, Any]:
    joined = "\n".join(tickets_by_role.values()).lower()
    hits = [pat for pat in FORBIDDEN_PROMPT_TOKENS if pat in joined]
    return {"ok": len(hits) == 0, "forbidden_hits": hits}


def score_rubric(
    checks: list[tuple[str, bool, float, str]],
    pass_threshold: float = 0.88,
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
    passed = (score >= pass_threshold) and len(errs) == 0 if pass_threshold >= 0.999 else (score >= pass_threshold)
    return score, passed, errs, sub_map


def build_grade_payload(
    *,
    task_id: str,
    checks_a: list[tuple[str, bool, float, str]],
    checks_b: list[tuple[str, bool, float, str]],
    checks_joint: list[tuple[str, bool, float, str]] | None,
    tickets_by_role: dict[str, str],
    service_state: dict[str, Any],
    wall_seconds: float,
    pass_threshold: float = 0.88,
) -> dict[str, Any]:
    j_checks = checks_joint or []
    sc_a, ok_a_raw, errs_a, sub_a = score_rubric(checks_a + j_checks, pass_threshold=pass_threshold)
    sc_b, ok_b_raw, errs_b, sub_b = score_rubric(checks_b + j_checks, pass_threshold=pass_threshold)
    _, ok_j, errs_j, sub_j = score_rubric(j_checks, pass_threshold=0.999) if j_checks else (1.0, True, [], {})
    pass_a = bool(ok_a_raw and ok_j)
    pass_b = bool(ok_b_raw and ok_j)
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
        "errors_a": errs_a[:10],
        "errors_b": errs_b[:10],
        "errors_joint": errs_j[:10],
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_hygiene(tickets_by_role),
        "telemetry": service_state,
    }


def load_mono_font(size: int = 18) -> Any:
    from PIL import ImageFont
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ):
        if Path(cand).is_file():
            return ImageFont.truetype(cand, size=size)
    return ImageFont.load_default()


def render_scanned_exhibit_png(
    path: Path,
    header: str,
    body_lines: list[str],
    stamp_text: str = "CONTROLLED ENGINEERING EXHIBIT",
    tilt_deg: float = -0.35,
) -> None:
    from PIL import Image, ImageDraw
    path.parent.mkdir(parents=True, exist_ok=True)
    f_hdr = load_mono_font(21)
    f_body = load_mono_font(17)
    f_stamp = load_mono_font(16)
    max_w = max([int(f_hdr.getbbox(header)[2])] + [int(f_body.getbbox(ln)[2]) for ln in body_lines] + [820])
    w = max(1120, max_w + 96)
    h = max(460, 165 + 32 * len(body_lines))
    im = Image.new("RGB", (w, h), (251, 249, 244))
    dr = ImageDraw.Draw(im)
    dr.rectangle([(16, 16), (w - 16, h - 16)], outline=(71, 85, 105), width=2)
    dr.rectangle([(16, 16), (w - 16, 70)], fill=(15, 23, 42))
    dr.text((32, 29), header, fill=(248, 250, 252), font=f_hdr)
    y = 92
    for ln in body_lines:
        dr.text((34, y), ln, fill=(15, 23, 42), font=f_body)
        y += 31
    sw = max(290, int(f_stamp.getbbox(stamp_text)[2]) + 32)
    dr.rectangle([(w - sw - 32, h - 64), (w - 32, h - 26)], outline=(185, 28, 28), width=2)
    dr.text((w - sw - 16, h - 54), stamp_text, fill=(185, 28, 28), font=f_stamp)
    im.rotate(tilt_deg, resample=Image.BICUBIC, expand=False, fillcolor=(245, 243, 238)).save(path, format="PNG")


def write_multipage_sop_pdf(path: Path, doc_title: str, pages: list[tuple[str, list[str]]]) -> None:
    """Create a real searchable multi-page PDF SOP via LibreOffice headless HTML->PDF conversion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    blocks: list[str] = [
        "<!doctype html><html><head><meta charset='utf-8'/>",
        "<style>body{font-family:'DejaVu Sans',sans-serif;font-size:10.5pt;color:#0f172a;line-height:1.45;}",
        "h1{font-size:15pt;border-bottom:2px solid #1e293b;padding-bottom:4px;}",
        "h2{font-size:12pt;color:#1d4ed8;margin-top:12px;}",
        ".pg{page-break-after:always;} .last{page-break-after:auto;}",
        "pre{background:#f1f5f9;padding:8px;border:1px solid #cbd5e1;font-family:'DejaVu Sans Mono',monospace;font-size:9.5pt;}</style></head><body>",
    ]
    for idx, (sec_hdr, lines) in enumerate(pages):
        cls = "last" if idx == len(pages) - 1 else "pg"
        blocks.append(f"<div class='{cls}'><h1>{esc(doc_title)}</h1><h2>{esc(sec_hdr)}</h2>")
        for ln in lines:
            if ln.startswith("  ") or "|" in ln:
                blocks.append(f"<pre>{esc(ln)}</pre>")
            else:
                blocks.append(f"<p>{esc(ln)}</p>")
        blocks.append("</div>")
    blocks.append("</body></html>")

    if shutil.which("libreoffice"):
        with tempfile.TemporaryDirectory() as tmp:
            u_dir = Path(tmp) / "lo_pdf"
            hp = Path(tmp) / f"{path.stem}.html"
            hp.write_text("\n".join(blocks), encoding="utf-8")
            cp = subprocess.run(
                [
                    "libreoffice",
                    f"-env:UserInstallation=file://{u_dir}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp),
                    str(hp),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            gen = Path(tmp) / f"{path.stem}.pdf"
            if cp.returncode == 0 and gen.is_file() and gen.stat().st_size > 800:
                path.write_bytes(gen.read_bytes())
                return

    # Fallback raster PDF if LibreOffice is absent on host unit-test runner
    from PIL import Image, ImageDraw
    f1, f2 = load_mono_font(20), load_mono_font(15)
    imgs: list[Image.Image] = []
    for sec_hdr, lines in pages:
        im = Image.new("RGB", (1100, 1420), (255, 255, 255))
        dr = ImageDraw.Draw(im)
        dr.text((40, 36), f"{doc_title} — {sec_hdr}", fill=(15, 23, 42), font=f1)
        y = 88
        for ln in lines:
            dr.text((44, y), ln[:105], fill=(30, 41, 59), font=f2)
            y += 26
        imgs.append(im)
    imgs[0].save(path, format="PDF", save_all=True, append_images=imgs[1:])


def evaluate_xlsx_via_libreoffice(path: Path) -> dict[str, dict[str, dict[str, str | float | None]]]:
    """Isolated-profile headless LibreOffice formula evaluator (never collides with running UNO soffice.bin)."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            u_dir = tmp_dir / "lo_eval_prof"
            ods_p = tmp_dir / "eval.ods"
            cp1 = subprocess.run(
                [
                    "libreoffice", f"-env:UserInstallation=file://{u_dir}",
                    "--headless", "--norestore", "--convert-to", "ods", "--outdir", str(tmp_dir), str(path),
                ],
                capture_output=True, text=True, timeout=45,
            )
            cand_ods = tmp_dir / (path.stem + ".ods")
            if cp1.returncode == 0 and cand_ods.is_file():
                cand_ods.rename(ods_p)
                cp2 = subprocess.run(
                    [
                        "libreoffice", f"-env:UserInstallation=file://{u_dir}",
                        "--headless", "--norestore", "--convert-to", "xlsx", "--outdir", str(tmp_dir), str(ods_p),
                    ],
                    capture_output=True, text=True, timeout=45,
                )
                eval_xlsx = tmp_dir / "eval.xlsx"
                if cp2.returncode == 0 and eval_xlsx.is_file():
                    return read_multisheet_xlsx(eval_xlsx)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return read_multisheet_xlsx(path)


def write_simple_odt(path: Path, title: str, paragraphs: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    if shutil.which("libreoffice"):
        with tempfile.TemporaryDirectory() as tmp:
            u_dir = Path(tmp) / "lo_odt"
            hp = Path(tmp) / f"{path.stem}.html"
            lines = ["<!doctype html><html><head><meta charset='utf-8'/></head><body>", f"<h2>{esc(title)}</h2>"]
            for tag_id, txt in paragraphs:
                lines.append(f"<p>[{esc(tag_id)}] {esc(txt)}</p>")
            lines.append("</body></html>")
            hp.write_text("\n".join(lines), encoding="utf-8")
            cp = subprocess.run(
                [
                    "libreoffice",
                    f"-env:UserInstallation=file://{u_dir}",
                    "--headless",
                    "--convert-to",
                    "odt",
                    "--outdir",
                    str(tmp),
                    str(hp),
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )
            gen = Path(tmp) / f"{path.stem}.odt"
            if cp.returncode == 0 and gen.is_file() and gen.stat().st_size > 500:
                path.write_bytes(gen.read_bytes())
                return
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">\n'
        '  <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
        '  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
        '</manifest:manifest>\n'
    )
    body = [f"<text:p>{esc(title)}</text:p>"] + [f"<text:p>[{esc(k)}] {esc(v)}</text:p>" for k, v in paragraphs]
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">\n'
        '  <office:body><office:text>' + "".join(body) + "</office:text></office:body>\n</office:document-content>\n"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("META-INF/manifest.xml", manifest, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", content, compress_type=ZIP_DEFLATED)


def read_odt_plain_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        with ZipFile(path, "r") as zf:
            root = ET.fromstring(zf.read("content.xml"))
        chunks = ["".join(el.itertext()).strip() for el in root.iter() if el.tag.endswith("}h") or el.tag.endswith("}p")]
        return "\n".join(c for c in chunks if c)
    except Exception:
        return ""


def extract_pdf_text(path: Path) -> str:
    if not path.is_file() or not shutil.which("pdftotext"):
        return ""
    cp = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=20)
    return cp.stdout if cp.returncode == 0 else ""


def launch_chromium_natural(urls: list[str], width: int = 1340, height: int = 880) -> None:
    """Launch a single authenticated Chromium window using natural WM placement (no --window-position, no :9222)."""
    u_args = " ".join(shlex.quote(u) for u in urls)
    inner = (
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus AT_SPI_BUS_ADDRESS=\"$AT_ADDR\"; "
        "mkdir -p /home/user/.config/nf_chr_profile; "
        "nohup chromium --no-sandbox --test-type --no-first-run --disable-gpu --disable-dev-shm-usage "
        "--force-renderer-accessibility --user-data-dir=/home/user/.config/nf_chr_profile "
        f"--window-size={width},{height} {u_args} >/tmp/nf_chromium.log 2>&1 </dev/null &"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", inner], check=True, capture_output=True, timeout=25)
    time.sleep(2.2)


UNO_PIPE_NAME = "nf_uno_pipe"


def launch_libreoffice_uno_natural(doc_paths: list[Path], uno_port: int = 2002, pipe_name: str = UNO_PIPE_NAME) -> None:
    """Open real LibreOffice documents on :99 with natural WM placement and a desk-local UNIX pipe (isolated from guest_bash)."""
    del uno_port
    if not doc_paths:
        return
    q_docs = " ".join(shlex.quote(str(p)) for p in doc_paths)
    accept = f"pipe,name={pipe_name};urp;"
    inner = (
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user USER=user LOGNAME=user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus AT_SPI_BUS_ADDRESS=\"$AT_ADDR\" SAL_USE_VCLPLUGIN=gtk3; "
        f"nohup libreoffice --norestore --nologo --nofirststartwizard --accept={shlex.quote(accept)} {q_docs} >/tmp/nf_soffice.log 2>&1 </dev/null &"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", inner], check=True, capture_output=True, timeout=25)
    for _ in range(45):
        if list(Path("/tmp").glob(f"*{pipe_name}*")):
            break
        time.sleep(0.3)
    time.sleep(1.5)


def reload_uno_pipe_documents(paths: list[Path], pipe_name: str = UNO_PIPE_NAME) -> None:
    """Author-side desk-local helper (for deterministic 5-gate solve_role only) to reload disk-updated ODF/OOXML docs via UNIX pipe."""
    uris = [p.resolve().as_uri() for p in paths]
    fdirs = sorted({str(p.resolve().parent) for p in paths})
    code = (
        "import glob, os, uno\n"
        "local = uno.getComponentContext()\n"
        "res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)\n"
        f"ctx = res.resolve('uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext')\n"
        "desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)\n"
        "keeper = desk.loadComponentFromURL('private:factory/swriter', '_blank', 0, ())\n"
        f"targets = set({json.dumps(uris)})\n"
        "en = desk.getComponents().createEnumeration()\n"
        "to_close = []\n"
        "while en.hasMoreElements():\n"
        "    d = en.nextElement()\n"
        "    if hasattr(d, 'getURL') and d.getURL() in targets:\n"
        "        to_close.append(d)\n"
        "for d in to_close:\n"
        "    d.setModified(False); d.close(True)\n"
        f"for fd in {json.dumps(fdirs)}:\n"
        "    for lk in glob.glob(os.path.join(fd, '.~lock.*')):\n"
        "        try: os.unlink(lk)\n"
        "        except OSError: pass\n"
        "pv = uno.createUnoStruct('com.sun.star.beans.PropertyValue'); pv.Name = 'Silent'; pv.Value = True\n"
        "for u in sorted(targets):\n"
        "    desk.loadComponentFromURL(u, '_blank', 0, (pv,))\n"
        "keeper.setModified(False); keeper.close(True)\n"
    )
    inner = f"export HOME=/home/user USER=user LOGNAME=user; python3 -c {shlex.quote(code)}"
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", inner], check=True, capture_output=True, timeout=45)


def launch_blender_gui_natural(blend_path: Path) -> None:
    """Launch real Blender 3.4 GUI on :99 with natural Openbox placement and persistent read-only live scene telemetry."""
    hook_py = Path("/run/user/1000/blender_gui_hook.py")
    hook_py.parent.mkdir(parents=True, exist_ok=True)
    hook_py.write_text(
        "import bpy, json, os\n"
        "STATE_P = '/run/user/1000/blender_live_state.json'\n"
        "CMD_P = '/run/user/1000/blender_live_cmd.json'\n"
        "def _nf_poll_live_scene():\n"
        "    try:\n"
        "        if os.path.isfile(CMD_P):\n"
        "            with open(CMD_P, 'r', encoding='utf-8') as f:\n"
        "                cmd = json.load(f)\n"
        "            os.unlink(CMD_P)\n"
        "            fp = cmd.get('open_mainfile') or bpy.data.filepath\n"
        "            if fp and os.path.isfile(fp):\n"
        "                bpy.ops.wm.open_mainfile(filepath=fp)\n"
        "        rb = bpy.data.objects.get('RightBipolar_Arm')\n"
        "        lt = bpy.data.objects.get('Endoscope_Light')\n"
        "        lg = bpy.data.objects.get('LeftGrasper_Arm')\n"
        "        cm = bpy.data.objects.get('Endoscope_Camera')\n"
        "        st = {\n"
        "            'running': True,\n"
        "            'filepath': bpy.data.filepath,\n"
        "            'is_dirty': bool(bpy.data.is_dirty),\n"
        "            'bipolar_status': str(rb.get('status', '')) if rb else '',\n"
        "            'bipolar_w': round(float(rb.get('bipolar_duty_w', -1.0)), 3) if rb else -1.0,\n"
        "            'led_status': str(lt.get('status', '')) if lt else '',\n"
        "            'led_w': round(float(lt.get('led_illuminator_w', -1.0)), 3) if lt else -1.0,\n"
        "            'left_loc': [round(float(x), 2) for x in lg.location] if lg else [],\n"
        "            'cam_loc': [round(float(x), 2) for x in cm.location] if cm else [],\n"
        "        }\n"
        "        tmp_p = STATE_P + '.tmp'\n"
        "        with open(tmp_p, 'w', encoding='utf-8') as f:\n"
        "            json.dump(st, f)\n"
        "        os.replace(tmp_p, STATE_P)\n"
        "    except Exception:\n"
        "        pass\n"
        "    return 0.5\n"
        "bpy.app.timers.register(_nf_poll_live_scene, first_interval=0.4, persistent=True)\n",
        encoding="utf-8",
    )
    try:
        os.chmod(hook_py, 0o644)
        os.chown(hook_py, 1000, 0)
    except OSError:
        pass
    inner = (
        "AT_ADDR=$(cat /run/user/1000/atspi_addr 2>/dev/null || true); "
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus AT_SPI_BUS_ADDRESS=\"$AT_ADDR\"; "
        f"nohup blender {shlex.quote(str(blend_path))} --python /run/user/1000/blender_gui_hook.py >/tmp/nf_blender_gui.log 2>&1 </dev/null &"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", inner], check=True, capture_output=True, timeout=25)
    for _ in range(35):
        if Path("/run/user/1000/blender_live_state.json").is_file():
            break
        time.sleep(0.25)
    time.sleep(1.0)


def inspect_live_blender_readonly() -> dict[str, Any]:
    """Read-only inspection of the live open Blender 3.4 GUI scene on :99 (zero disk/UI mutations)."""
    st = read_json_safe(Path("/run/user/1000/blender_live_state.json"))
    return st if st else {"running": False, "is_dirty": False}


def inspect_live_uno_documents_readonly(uno_port: int = 2002, pipe_name: str = UNO_PIPE_NAME) -> dict[str, Any]:
    """Read-only inspection of open LibreOffice documents via desk-local UNIX pipe (zero Ctrl+S, zero disk writes)."""
    del uno_port
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
        "            names = list(d.getSheets().getElementNames())\n"
        "            for nm in names:\n"
        "                sh = d.getSheets().getByName(nm)\n"
        "                cells = {}\n"
        "                for r in range(18):\n"
        "                    for c in range(8):\n"
        "                        cl = sh.getCellByPosition(c, r)\n"
        "                        s = cl.getString().strip()\n"
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
        inner = f"export HOME=/home/user USER=user LOGNAME=user; python3 -c {shlex.quote(probe)}"
        cp = subprocess.run(["su", "-s", "/bin/bash", "user", "-c", inner], capture_output=True, text=True, timeout=25)
        if cp.returncode == 0 and cp.stdout.strip():
            return json.loads(cp.stdout.strip().splitlines()[-1])
    except Exception:
        pass
    return {"connected": False, "docs": {}}


__all__ = [
    "FORBIDDEN_PROMPT_TOKENS",
    "UNO_PIPE_NAME",
    "build_grade_payload",
    "evaluate_xlsx_via_libreoffice",
    "extract_pdf_text",
    "file_atomic_lock",
    "inspect_live_blender_readonly",
    "inspect_live_uno_documents_readonly",
    "launch_blender_gui_natural",
    "launch_chromium_natural",
    "launch_libreoffice_uno_natural",
    "load_mono_font",
    "read_json_safe",
    "read_multisheet_xlsx",
    "read_odt_plain_text",
    "reload_uno_pipe_documents",
    "render_scanned_exhibit_png",
    "score_rubric",
    "sha256_file",
    "update_single_sheet_xlsx",
    "verify_prompt_hygiene",
    "write_json",
    "write_multipage_sop_pdf",
    "write_multisheet_xlsx",
    "write_simple_odt",
]
