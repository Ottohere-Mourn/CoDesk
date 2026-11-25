"""Finite deterministic schedule checks for CONC-03."""
from __future__ import annotations

import json
import importlib.util
import tempfile
import time
from pathlib import Path

import fitz
from pptx import Presentation
from pptx.util import Inches, Pt

_CASE_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


grade = _load("conc03_private_grade", _CASE_ROOT / "private" / "grade.py").grade
build_assets = _load("conc03_asset_builder", _CASE_ROOT / "integration" / "build_assets.py").build


TIMEOUT = 3600
TITLE = ["Personal Protective Equipment", "Recognize and Report Hazards", "Keep Emergency Exits Clear"]
BODY = [
    "Wear a fitted helmet, eye protection, and task-appropriate gloves before entering the work area.",
    "Stop work, isolate the area, and report spills, exposed wiring, or unstable loads to the shift lead.",
    "Keep exit routes and door swing areas clear; use the nearest marked exit during an alarm.",
]


def _truth(root: Path):
    assets = root / "assets" / "CONC-03" / "guest"
    build_assets(root / "assets" / "CONC-03")
    workspace = root / "workspace"
    (workspace / "out_a").mkdir(parents=True)
    (workspace / "out_b").mkdir(parents=True)
    csv_data = "claim_id,status,reason_code,uploaded_filename\nEXP-401,APPROVED,,receipt_EXP-401.png\nEXP-402,REJECTED,ERR_AMOUNT_MISMATCH,receipt_EXP-402.png\nEXP-403,APPROVED,,receipt_EXP-403.png\n"
    (workspace / "approval_summary.csv").write_text(csv_data, encoding="utf-8")
    prs = Presentation(str(assets / "out_b" / "Safety_Brief.pptx"))
    for i, slide in enumerate(prs.slides):
        for shape in list(slide.shapes):
            if shape.name in {f"IconPlaceholder_{i + 1}", f"IconHint_{i + 1}"}:
                shape._element.getparent().remove(shape._element)
            elif shape.name == f"Title_{i + 1}":
                shape.text_frame.text = TITLE[i]
            elif shape.name == f"Body_{i + 1}":
                shape.text_frame.text = BODY[i]
            elif shape.name == f"Footer_{i + 1}":
                shape.text_frame.text = f"SAF-0{i + 1}"
        slide.shapes.add_picture(str(assets / "in_b" / "icons" / ("icon_helmet.png", "icon_hazard.png", "icon_exit.png")[i]),
                                 Inches(9.2), Inches(2.0), width=Inches(2.45), height=Inches(2.45))
    deck = workspace / "Safety_Brief.pptx"
    prs.save(str(deck))
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=960, height=540)
        page.insert_text((55, 55), TITLE[i], fontsize=26)
        page.insert_textbox(fitz.Rect(55, 110, 600, 300), BODY[i], fontsize=18)
        page.insert_image(fitz.Rect(660, 145, 850, 335), filename=str(assets / "in_b" / "icons" / ("icon_helmet.png", "icon_hazard.png", "icon_exit.png")[i]))
        page.insert_text((55, 495), f"SAF-0{i + 1}", fontsize=16)
    doc.save(workspace / "Safety_Brief.pdf")
    a_records = []
    events = []
    for cid, status, reason in (("EXP-401", "APPROVED", ""), ("EXP-402", "REJECTED", "ERR_AMOUNT_MISMATCH"), ("EXP-403", "APPROVED", "")):
        filename = f"receipt_{cid}.png"
        import hashlib
        sha = hashlib.sha256((assets / "in_a" / "receipts" / filename).read_bytes()).hexdigest()
        a_records.append({"claim_id": cid, "status": status, "reason_code": reason,
                          "uploaded_filename": filename, "sha256": sha})
        events.extend([{"type": "menu_open", "claim_id": cid}, {"type": "upload", "claim_id": cid}, {"type": "decision", "claim_id": cid}])
    state = {"a_records": a_records, "events": events, "popover_dismiss_count": 0}
    result = grade(workspace, state, assets)
    empty = root / "empty"
    empty.mkdir()
    pristine = grade(empty, {}, assets)
    return result, pristine["joint_pass"] is False, assets


def _simulate(order, careful):
    done = {"a": 0, "b": 0}
    focus = "a"
    menu_open = True
    for actor in order:
        if careful:
            focus = actor
            if actor == "a":
                # A controlled attachment cycle includes menu reopen after the
                # native chooser changes focus and dismisses the menu.
                menu_open = True
                done["a"] += 1
                menu_open = False
            else:
                done["b"] += 1
            continue
        if actor != focus:
            focus = actor
            menu_open = False
        if actor == "a":
            done["a"] += int(menu_open)
            # The file chooser interrupts Chrome focus and dismisses the menu.
            focus, menu_open = "b", False
        else:
            done["b"] += int(focus == "b")
            focus, menu_open = "a", False
    return done


def gates():
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="conc03-fixture-") as temp:
        fixture, pristine_fail, _ = _truth(Path(temp))
    total_a, total_b = 3, 3
    seq_ab = _simulate(["a"] * total_a + ["b"] * total_b, True)
    seq_ba = _simulate(["b"] * total_b + ["a"] * total_a, True)
    race = _simulate(["a", "b", "a", "b", "a", "b"], False)
    elapsed = time.monotonic() - start
    return {
        "gate1_pristine_fail": pristine_fail,
        "gate2_gt_seq_ab_exists": seq_ab == {"a": 3, "b": 3},
        "gate3_gt_seq_ba_exists": seq_ba == {"a": 3, "b": 3},
        "gate4_gt_naive_race_corrupts": race["a"] < 3 or race["b"] < 3,
        "gate5_fixture_feasible": fixture["joint_pass"] and elapsed <= 180,
        "fixture_elapsed_s": round(elapsed, 4), "conc_role_timeout_s": TIMEOUT,
    }
