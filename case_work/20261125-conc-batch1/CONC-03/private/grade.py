"""Deterministic evidence grader for the CONC-03 paired task."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import fitz
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


CLAIMS = {
    "EXP-401": ("APPROVED", "", "receipt_EXP-401.png"),
    "EXP-402": ("REJECTED", "ERR_AMOUNT_MISMATCH", "receipt_EXP-402.png"),
    "EXP-403": ("APPROVED", "", "receipt_EXP-403.png"),
}
TITLES = ["Personal Protective Equipment", "Recognize and Report Hazards", "Keep Emergency Exits Clear"]
FOOTERS = ["SAF-01", "SAF-02", "SAF-03"]
GUIDANCE = [
    "Wear a fitted helmet, eye protection, and task-appropriate gloves before entering the work area.",
    "Stop work, isolate the area, and report spills, exposed wiring, or unstable loads to the shift lead.",
    "Keep exit routes and door swing areas clear; use the nearest marked exit during an alarm.",
]
ICONS = ["icon_helmet.png", "icon_hazard.png", "icon_exit.png"]
ACCENTS = [(249, 200, 70), (245, 190, 54), (46, 157, 111)]


def _read_csv(path: Path):
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return reader.fieldnames, list(reader)
    except (OSError, UnicodeError, csv.Error):
        return None, []


def _hash(path: Path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _box(shape):
    return (shape.left, shape.top, shape.left + shape.width, shape.top + shape.height)


def _overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _icon_sha(slide):
    return [_hash_blob(s.image.blob) for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]


def _hash_blob(blob):
    return hashlib.sha256(blob).hexdigest()


def _pptx_checks(path: Path, asset_root: Path):
    checks = [False] * 10
    try:
        prs = Presentation(str(path))
    except Exception:
        return checks
    if len(prs.slides) != 3:
        return checks
    checks[0] = True
    expected_hashes = [_hash(asset_root / "in_b" / "icons" / f) for f in ICONS]
    title_ok, footer_ok, icon_hash_ok = [], [], []
    bounds_ok, overlap_ok = [], []
    for i, slide in enumerate(prs.slides):
        texts = [(s, s.text_frame.text.strip()) for s in slide.shapes if getattr(s, "has_text_frame", False)]
        title_shape = next((s for s, t in texts if TITLES[i] in t), None)
        footer_shape = next((s for s, t in texts if FOOTERS[i] in t), None)
        body_shape = next((s for s, t in texts if GUIDANCE[i] in t), None)
        title_ok.append(title_shape is not None)
        footer_ok.append(footer_shape is not None)
        hashes = _icon_sha(slide)
        icon_hash_ok.append(expected_hashes[i] and expected_hashes[i] in hashes)
        pic = next((s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE
                    and _hash_blob(s.image.blob) == expected_hashes[i]), None)
        if pic is None:
            bounds_ok.append(False)
            overlap_ok.append(False)
        else:
            b = _box(pic)
            bounds_ok.append(b[0] >= 0 and b[1] >= 0 and b[2] <= prs.slide_width and b[3] <= prs.slide_height)
            overlap_ok.append(all(not _overlap(b, _box(x)) for x in (title_shape, body_shape, footer_shape) if x is not None)
                              and title_shape is not None and body_shape is not None and footer_shape is not None)
    checks[1] = all(title_ok)
    checks[2] = all(footer_ok)
    checks[3:6] = icon_hash_ok
    checks[6:8] = [all(bounds_ok), all(overlap_ok)]
    try:
        with fitz.open(str(path.with_suffix(".pdf"))) as doc:
            checks[8] = len(doc) == 3
            page_ok = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
                im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                color = ACCENTS[i]
                count = sum(1 for px in im.crop((int(im.width * .60), int(im.height * .15),
                                                 int(im.width * .98), int(im.height * .84))).getdata()
                            if all(abs(px[j] - color[j]) <= 15 for j in range(3)))
                page_ok.append(len(page.get_text().strip()) > 20 and count >= 20)
            checks[9] = len(doc) == 3 and all(page_ok)
    except Exception:
        pass
    return checks


def grade(workspace: Path, state: dict, asset_root: Path, rendered: Path | None = None):
    workspace, asset_root = Path(workspace), Path(asset_root)
    csv_path = workspace / "approval_summary.csv"
    headers, rows = _read_csv(csv_path)
    a = [headers == ["claim_id", "status", "reason_code", "uploaded_filename"]]
    by_id = {r.get("claim_id"): r for r in rows}
    records = {r.get("claim_id"): r for r in state.get("a_records", []) if isinstance(r, dict)}
    for claim_id, (status, reason, filename) in CLAIMS.items():
        a.append(records.get(claim_id, {}).get("status") == status)
    for claim_id, (_, _, filename) in CLAIMS.items():
        asset = asset_root / "in_a" / "receipts" / filename
        a.append(records.get(claim_id, {}).get("sha256") == _hash(asset))
    menu_claims = {e.get("claim_id") for e in state.get("events", []) if e.get("type") == "menu_open"}
    uploads = {e.get("claim_id") for e in state.get("events", []) if e.get("type") == "upload"}
    decisions = {e.get("claim_id") for e in state.get("events", []) if e.get("type") == "decision"}
    a.append(set(CLAIMS) <= menu_claims and set(CLAIMS) <= uploads and set(CLAIMS) <= decisions)
    a.append(set(by_id) == set(CLAIMS) and len(rows) == 3 and all(
        by_id.get(cid, {}).get("status") == expected[0]
        and by_id.get(cid, {}).get("reason_code", "") == expected[1]
        for cid, expected in CLAIMS.items()))
    a.append(all(by_id.get(cid, {}).get("uploaded_filename") == expected[2]
                 for cid, expected in CLAIMS.items()))

    b = _pptx_checks(workspace / "Safety_Brief.pptx", asset_root)
    flags = [f"A{i + 1}" for i, ok in enumerate(a) if not ok] + [f"B{i + 1}" for i, ok in enumerate(b) if not ok]
    return {"actor_a": sum(a) / 10, "actor_b": sum(b) / 10,
            "joint_pass": all(a) and all(b), "checks": {"actor_a": a, "actor_b": b},
            "flags": flags, "actor_a_check_count": len(a), "actor_b_check_count": len(b)}
