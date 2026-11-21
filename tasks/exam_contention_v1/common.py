"""Shared deterministic utilities for exam_contention_v1 (EC-01..EC-05).

Follows the Exam-Style Self-Check + Blind Final Grading contract:
  - Zero artificial wall-clock sleep padding or hidden runtime regime samplers.
  - Zero online-judge oracle leakage endpoints.
  - GUI-driver-agnostic prompts with zero peer spoilers or puppet keystrokes.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from typing import Any, Iterator
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from tasks.thematic_arenas_v1.xlsx_utils import read_multisheet_xlsx



FORBIDDEN_EXAM_PATTERNS: tuple[str, ...] = (
    "do not modify",
    "ctrl+z",
    "cmd+z",
    "other agent",
    "another agent",
    "peer agent",
    "teammate",
    "colleague",
    "desktop.click",
    "guest_bash",
    "click_and_type",
)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_opaque_seal(domain_salt: str, state_key: str) -> str:
    """Generate a uniform-format cryptographic attestation token without English error spoilers."""
    digest = hashlib.sha256(f"paragui-ec-seal:{domain_salt}:{state_key}".encode("utf-8")).hexdigest()[:12].upper()
    return f"ATTEST-{digest}"


def find_unexpected_workspace_files(project_dir: Path, allowed_rel_paths: set[str]) -> list[str]:
    """Return relative paths of unexpected scratch/coordination files left in project_dir."""
    if not project_dir.is_dir():
        return []
    extras: list[str] = []
    for p in sorted(project_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(project_dir).as_posix()
        name = p.name
        if "/.git/" in f"/{rel}/" or name == ".git":
            continue
        if "/__pycache__/" in f"/{rel}" or name.endswith(".pyc"):
            continue
        if name.startswith(".~lock.") or name.endswith(("-wal", "-shm", "-journal")):
            continue
        if re.search(r"\.FCStd\d+$", name) or name.endswith(".qgs~"):
            continue
        if rel not in allowed_rel_paths:
            extras.append(rel)
    return extras


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_mono_font(size: int = 18) -> Any:
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
    stamp_text: str = "VERIFIED SCAN EXHIBIT",
    tilt_deg: float = -0.2,
) -> None:
    """Render a realistic slightly tilted scanned business/engineering exhibit PNG."""
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


def write_simple_odt(path: Path, title: str, paragraphs: list[tuple[str, str]]) -> None:
    """Write a valid OpenDocument Text (.odt) file with named paragraph markers for LibreOffice Writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">\n'
        '  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
        '  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
        '</manifest:manifest>\n'
    )
    body_xml = [f'<text:h text:outline-level="1">{_xml_esc(title)}</text:h>']
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
        zf.writestr("content.xml", content_xml, compress_type=ZIP_DEFLATED)


def read_odt_plain_text(path: Path) -> str:
    """Extract concatenated paragraph text from a .odt document (saved either by LibreOffice Writer or ODF tools)."""
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
    """Compare two .xlsx or .odt files semantically, ignoring ZIP mtime/view-state noise."""
    if not pre_path.is_file() or not post_path.is_file():
        return False
    suf = post_path.suffix.lower()
    if suf == ".odt":
        l1 = [ln.strip() for ln in read_odt_plain_text(pre_path).splitlines() if ln.strip()]
        l2 = [ln.strip() for ln in read_odt_plain_text(post_path).splitlines() if ln.strip()]
        return l1 == l2
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
    """Save any unsaved in-memory edits in the live X11 LibreOffice window to disk."""
    q_stem = shlex.quote(doc_path.stem)
    gui_sh = (
        "export DISPLAY=:99 HOME=/home/gui XDG_RUNTIME_DIR=/tmp/runtime-gui; "
        f"wid=$(xdotool search --onlyvisible --name {q_stem} | tail -n 1); "
        "if [ -n \"$wid\" ]; then "
        "  xdotool windowactivate --sync \"$wid\" 2>/dev/null || true; sleep 0.25; "
        "  xdotool key --clearmodifiers ctrl+s 2>/dev/null || true; sleep 0.9; "
        "  wmctrl -l | grep -qiE 'Confirm|Changed|Modified' && xdotool key --clearmodifiers Return && sleep 0.9 || true; "
        "fi"
    )
    subprocess.run(["su", "-s", "/bin/bash", "gui", "-c", gui_sh], capture_output=True, timeout=15)


def reload_open_libreoffice_window(doc_path: Path) -> None:
    """Reload doc_path cleanly into the right-half desktop LibreOffice window."""
    q_doc = shlex.quote(str(doc_path))
    q_lock = shlex.quote(str(doc_path.parent / f".~lock.{doc_path.name}#"))
    q_stem = shlex.quote(doc_path.stem)
    subprocess.run(["bash", "-lc", f"pkill -f 'soffice.bin' >/dev/null 2>&1 || true; sleep 0.6; rm -f {q_lock}"], capture_output=True, timeout=10)
    launch_sh = f"export DISPLAY=:99 HOME=/home/gui XDG_RUNTIME_DIR=/tmp/runtime-gui; nohup libreoffice --norestore --nologo --nofirststartwizard {q_doc} >/tmp/lo_reload.log 2>&1 &"
    subprocess.run(["su", "-s", "/bin/bash", "gui", "-c", launch_sh], capture_output=True, timeout=10)
    subprocess.run(["sleep", "3.2"], capture_output=True, timeout=10)
    tile_sh = (
        f"export DISPLAY=:99; wid=$(xdotool search --onlyvisible --name {q_stem} | tail -n 1); "
        "if [ -n \"$wid\" ]; then "
        "  wmctrl -i -r \"$wid\" -b remove,maximized_vert,maximized_horz 2>/dev/null || true; "
        "  wmctrl -i -r \"$wid\" -e 0,960,0,958,1050 2>/dev/null || true; "
        "fi"
    )
    subprocess.run(["su", "-s", "/bin/bash", "gui", "-c", tile_sh], capture_output=True, timeout=10)


def _xml_esc(val: str) -> str:
    return (
        str(val)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def convert_doc_to_pdf_isolated(src_doc: Path, dst_pdf: Path) -> bool:
    """Convert .xlsx/.odt to PDF using an isolated LibreOffice UserInstallation so a live GUI soffice.bin never blocks."""
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
            timeout=60,
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


@contextmanager
def advisory_lock(lock_name: str) -> Iterator[None]:
    """Used strictly inside Gate-5 deterministic careful-concurrency reference check."""
    lp = Path(f"/tmp/.gt_careful_{lock_name}.lck")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def verify_prompt_driver_and_ban_clean(tickets_by_role: dict[str, str]) -> dict[str, Any]:
    joined = "\n".join(tickets_by_role.values()).lower()
    hits = [pat for pat in FORBIDDEN_EXAM_PATTERNS if pat in joined]
    return {"ok": len(hits) == 0, "forbidden_hits": hits}


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
