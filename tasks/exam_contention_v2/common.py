"""Shared utilities, partial-credit rubric engine, and desktop helpers for exam_contention_v2.

Strictly adheres to the updated $paragui-case-design contract:
  - Full GUI + CLI concurrency enabled (zero stripped CLI utilities).
  - Supports both Track 1 (Isolated-Workspace Shared-Screen Contention) and Track 2 (Shared-State/Artifact Contention).
  - Continuous partial-credit scoring in [0.0, 1.0] alongside binary pass_a / pass_b / joint_pass.
  - Zero online-judge oracle leakage, zero hidden runtime regime samplers, zero busy-wait padding.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import Any, Iterator
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from tasks.thematic_arenas_v1.xlsx_utils import read_multisheet_xlsx


FORBIDDEN_EXAM_V2_PATTERNS: tuple[str, ...] = (
    "do not modify",
    "ctrl+z",
    "cmd+z",
    "command+z",
    "other agent",
    "another agent",
    "peer agent",
    "concurrent agent",
    "qwen_cua_driver",
    "desktop.click",
    "guest_bash",
    "dev_bash",
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


def make_opaque_seal(domain_salt: str, state_key: str) -> str:
    digest = hashlib.sha256(f"paragui-ec2-seal:{domain_salt}:{state_key}".encode("utf-8")).hexdigest()[:12].upper()
    return f"ATTEST-{digest}"


def score_rubric(
    checks: list[tuple[str, bool, float, str]],
    pass_threshold: float = 0.88,
) -> tuple[float, bool, list[str], dict[str, bool]]:
    """Compute weighted continuous partial-credit score in [0.0, 1.0], pass flag, and error list."""
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
    pass_threshold: float = 0.90,
) -> dict[str, Any]:
    """Assemble standardized partial-credit + binary grade dictionary."""
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
        "errors_a": errs_a[:8],
        "errors_b": errs_b[:8],
        "errors_joint": errs_j[:8],
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_hygiene(tickets_by_role),
        "telemetry": service_state,
    }


def verify_prompt_hygiene(tickets_by_role: dict[str, str]) -> dict[str, Any]:
    joined = "\n".join(tickets_by_role.values()).lower()
    hits = [pat for pat in FORBIDDEN_EXAM_V2_PATTERNS if pat in joined]
    return {"ok": len(hits) == 0, "forbidden_hits": hits}


def load_mono_font(size: int = 20) -> Any:
    from PIL import ImageFont
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ):
        if Path(cand).is_file():
            return ImageFont.truetype(cand, size=size)
    return ImageFont.load_default()


def render_scanned_document_png(
    path: Path,
    header: str,
    body_lines: list[str],
    stamp_text: str = "VERIFIED EXHIBIT",
    tilt_deg: float = -0.2,
) -> None:
    from PIL import Image, ImageDraw
    path.parent.mkdir(parents=True, exist_ok=True)
    f_hdr = load_mono_font(23)
    f_body = load_mono_font(21)
    f_stamp = load_mono_font(17)
    line_widths = [int(f_hdr.getbbox(header)[2])] + [int(f_body.getbbox(ln)[2]) for ln in body_lines]
    w = max(1180, max(line_widths, default=800) + 108)
    h = max(500, 175 + 38 * len(body_lines))
    im = Image.new("RGB", (w, h), (253, 252, 249))
    dr = ImageDraw.Draw(im)

    dr.rectangle([(18, 18), (w - 18, h - 18)], outline=(90, 95, 108), width=2)
    dr.rectangle([(18, 18), (w - 18, 76)], fill=(15, 23, 42))
    dr.text((34, 33), header, fill=(248, 250, 252), font=f_hdr)

    y = 98
    for ln in body_lines:
        dr.text((36, y), ln, fill=(8, 12, 20), font=f_body)
        y += 37

    stamp_w = max(310, int(f_stamp.getbbox(stamp_text)[2]) + 36)
    dr.rectangle([(w - stamp_w - 34, h - 68), (w - 34, h - 28)], outline=(185, 28, 28), width=2)
    dr.text((w - stamp_w - 18, h - 58), stamp_text, fill=(185, 28, 28), font=f_stamp)

    gentle_tilt = max(-0.25, min(0.25, float(tilt_deg)))
    rotated = im.rotate(gentle_tilt, resample=Image.BICUBIC, expand=False, fillcolor=(247, 245, 240))
    rotated.save(path, format="PNG")


def _xml_esc(val: str) -> str:
    return (
        str(val)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_simple_odt(path: Path, title: str, paragraphs: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("libreoffice"):
        with tempfile.TemporaryDirectory() as tmp:
            u_dir = Path(tmp) / "lo_odt"
            h_p = Path(tmp) / f"{path.stem}.html"
            lines = [
                "<!doctype html><html><head><meta charset='utf-8'/></head><body>",
                f"<p><strong>{_xml_esc(title)}</strong></p>",
            ]
            for tag_id, text_val in paragraphs:
                lines.append(f"<p>[{_xml_esc(tag_id)}] {_xml_esc(text_val)}</p>")
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
            if cp.returncode == 0 and gen.is_file() and gen.stat().st_size > 500:
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
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"/>\n'
    )
    body_xml = [f'<text:p>{_xml_esc(title)}</text:p>']
    for tag_id, text_val in paragraphs:
        body_xml.append(f'<text:p>[{_xml_esc(tag_id)}] {_xml_esc(text_val)}</text:p>')
    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'office:version="1.2">\n'
        '  <office:body><office:text>\n    ' + "\n    ".join(body_xml) + '\n  </office:text></office:body>\n'
        '</office:document-content>\n'
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("META-INF/manifest.xml", manifest_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("styles.xml", styles_xml, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", content_xml, compress_type=ZIP_DEFLATED)


def read_odt_plain_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        with ZipFile(path, "r") as zf:
            xml_bytes = zf.read("content.xml")
        root = ET.fromstring(xml_bytes)
        chunks: list[str] = []
        for elem in root.iter():
            if elem.tag.endswith("}h") or elem.tag.endswith("}p"):
                txt = "".join(elem.itertext()).strip()
                if txt:
                    chunks.append(txt)
        return "\n".join(chunks)
    except Exception:
        return ""


def _norm_formula(formula: Any) -> str:
    if not formula:
        return ""
    s = str(formula).strip().lstrip("=").replace(" ", "").upper()
    return re.sub(r"(\d+)\.0+(?!\d)", r"\1", s)


def semantic_doc_equal(pre_path: Path, post_path: Path) -> bool:
    if not pre_path.is_file() or not post_path.is_file():
        return False
    suf = post_path.suffix.lower()
    if suf == ".odt":
        l1 = [ln.strip() for ln in read_odt_plain_text(pre_path).splitlines() if ln.strip()]
        l2 = [ln.strip() for ln in read_odt_plain_text(post_path).splitlines() if ln.strip()]
        return l1 == l2
    if suf == ".odp":
        try:
            with ZipFile(pre_path) as z1, ZipFile(post_path) as z2:
                return z1.read("content.xml") == z2.read("content.xml")
        except Exception:
            return False
    if suf == ".xlsx":
        try:
            s1 = read_multisheet_xlsx(pre_path)
            s2 = read_multisheet_xlsx(post_path)
        except Exception:
            return False
        if set(s1.keys()) != set(s2.keys()):
            return False
        for sh_name in s1:
            c1 = {k: v for k, v in s1[sh_name].items() if v.get("formula") or v.get("value") not in (None, "")}
            c2 = {k: v for k, v in s2[sh_name].items() if v.get("formula") or v.get("value") not in (None, "")}
            if set(c1.keys()) != set(c2.keys()):
                return False
            for ref in c1:
                f1 = _norm_formula(c1[ref].get("formula"))
                f2 = _norm_formula(c2[ref].get("formula"))
                if f1 or f2:
                    if f1 != f2:
                        return False
                    continue
                v1 = c1[ref].get("value")
                v2 = c2[ref].get("value")
                try:
                    if abs(float(v1) - float(v2)) > 1e-3:  # type: ignore[arg-type]
                        return False
                except (TypeError, ValueError):
                    if str(v1 or "").strip() != str(v2 or "").strip():
                        return False
        return True
    return sha256_file(pre_path) == sha256_file(post_path)


def flush_open_libreoffice_to_disk(doc_path: Path) -> None:
    q_stem = shlex.quote(doc_path.stem)
    gui_sh = (
        "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000; "
        f"wid=$(xdotool search --onlyvisible --name {q_stem} | tail -n 1); "
        "if [ -n \"$wid\" ]; then "
        "  wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\" 2>/dev/null || true; sleep 0.3; "
        "  xdotool key --clearmodifiers ctrl+s 2>/dev/null || true; sleep 0.9; "
        "  wmctrl -l | grep -qiE 'Confirm|Changed|Modified' && xdotool key --clearmodifiers Return && sleep 0.8 || true; "
        "fi"
    )
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], capture_output=True, timeout=15)


def reload_open_libreoffice_docs(doc_paths: list[Path]) -> None:
    locks = " ".join(shlex.quote(str(p.parent / f".~lock.{p.name}#")) for p in doc_paths)
    subprocess.run(["bash", "-lc", f"pkill -f 'soffice.bin' >/dev/null 2>&1 || true; sleep 0.6; rm -f {locks}"], capture_output=True, timeout=10)
    for idx, doc_path in enumerate(doc_paths):
        q_doc = shlex.quote(str(doc_path))
        q_stem = shlex.quote(doc_path.stem)
        launch_sh = (
            "export DISPLAY=:99 HOME=/home/user XDG_RUNTIME_DIR=/run/user/1000 SAL_USE_VCLPLUGIN=gtk3; "
            f"nohup libreoffice --norestore --nologo --nofirststartwizard {q_doc} >/tmp/lo_reload_{idx}.log 2>&1 &"
        )
        subprocess.run(["su", "-s", "/bin/bash", "user", "-c", launch_sh], capture_output=True, timeout=10)
        subprocess.run(["sleep", "3.0"], capture_output=True, timeout=10)
        x_pos = 960 if idx == 0 else 480
        w_sz = 955 if idx == 0 else 960
        tile_sh = (
            f"export DISPLAY=:99; wid=$(xdotool search --onlyvisible --name {q_stem} | tail -n 1); "
            "if [ -n \"$wid\" ]; then "
            "  wmctrl -i -r \"$wid\" -b remove,maximized_vert,maximized_horz 2>/dev/null || true; "
            f"  wmctrl -i -r \"$wid\" -e 0,{x_pos},20,{w_sz},1020 2>/dev/null || true; "
            "fi"
        )
        subprocess.run(["su", "-s", "/bin/bash", "user", "-c", tile_sh], capture_output=True, timeout=10)


def convert_doc_to_pdf_isolated(src_doc: Path, dst_pdf: Path) -> bool:
    dst_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        u_dir = Path(tmp) / "lo_prof"
        out_d = Path(tmp) / "out"
        out_d.mkdir(parents=True, exist_ok=True)
        cp = subprocess.run(
            [
                "libreoffice",
                f"-env:UserInstallation=file://{u_dir}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_d),
                str(src_doc),
            ],
            capture_output=True,
            text=True,
            timeout=75,
        )
        gen = out_d / f"{src_doc.stem}.pdf"
        if cp.returncode == 0 and gen.is_file() and gen.stat().st_size > 500:
            dst_pdf.write_bytes(gen.read_bytes())
            return True
    return False


def extract_pdf_text(pdf_path: Path) -> str:
    if not pdf_path.is_file():
        return ""
    cp = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True, timeout=20)
    return cp.stdout if cp.returncode == 0 else ""


def pdf_page_count(pdf_path: Path) -> int:
    if not pdf_path.is_file():
        return 0
    cp = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=15)
    m = re.search(r"Pages:\s+(\d+)", cp.stdout or "")
    return int(m.group(1)) if m else 0


@contextmanager
def advisory_lock(lock_name: str) -> Iterator[None]:
    """Used strictly inside Gate-5 deterministic careful-concurrency reference verification."""
    lp = Path(f"/tmp/.gt_careful_{lock_name}.lck")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def set_x11_clipboard(val: str) -> None:
    p = subprocess.Popen(
        ["xclip", "-i", "-selection", "clipboard"],
        env={"DISPLAY": ":99", "PATH": "/usr/local/bin:/usr/bin:/bin"},
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    p.communicate(val.encode("utf-8"), timeout=5)


def get_x11_clipboard() -> str:
    cp = subprocess.run(
        ["xclip", "-o", "-selection", "clipboard"],
        env={"DISPLAY": ":99", "PATH": "/usr/local/bin:/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=5,
    )
    return cp.stdout.strip() if cp.returncode == 0 else ""
