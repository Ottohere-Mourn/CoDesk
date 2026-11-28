"""Host-side deterministic BC-04 SVG structure and PNG artifact Oracle."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from pipeline.grade import make_grade

SVG_NS = "http://www.w3.org/2000/svg"
TARGET_IDS = {
    "hero-banner", "hero-background", "hero-accent", "hero-title", "hero-subtitle", "brand-mark",
    "pricing-section", "card-starter", "card-growth", "card-scale", "starter-price", "growth-price",
    "scale-price", "growth-highlight", "growth-badge",
}


def _id_map(root: ET.Element) -> dict[str, ET.Element]:
    return {node.attrib["id"]: node for node in root.iter() if "id" in node.attrib}


def _text(ids: dict[str, ET.Element], key: str) -> str:
    return " ".join("".join(ids[key].itertext()).split()) if key in ids else ""


def _attrs(ids: dict[str, ET.Element], key: str) -> dict[str, str]:
    return ids[key].attrib if key in ids else {}


def _png_info(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if len(raw) < 45 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
            return {"valid": False, "exists": path.is_file(), "size_bytes": len(raw), "width": 0, "height": 0}
        width, height = struct.unpack(">II", raw[16:24])
        has_idat = b"IDAT" in raw and raw.endswith(b"IEND\xaeB`\x82")
        return {"valid": width > 0 and height > 0 and has_idat, "exists": True,
                "size_bytes": len(raw), "width": width, "height": height}
    except OSError:
        return {"valid": False, "exists": False, "size_bytes": 0, "width": 0, "height": 0}


def _check(check_id: str, weight: float, passed: bool, evidence: Any, *, score: float | None = None) -> dict:
    return {"id": check_id, "weight": weight, "passed": bool(passed),
            "score": float(bool(passed)) if score is None else max(0.0, min(1.0, float(score))),
            "required": True, "evidence": evidence}


def grade_case(workspace: str | Path, preview_receipt: dict | None, run_id: str = "offline") -> dict:
    root = Path(workspace)
    source = root / "brand/launch_board.svg"
    hero = root / "out/hero_banner.png"
    pricing = root / "out/pricing_card.png"
    try:
        parsed = ET.parse(source)
        svg_root = parsed.getroot()
        ids = _id_map(svg_root)
        svg_ok = svg_root.tag == f"{{{SVG_NS}}}svg" and svg_root.attrib.get("viewBox") == "0 0 1600 1000"
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    except (OSError, ET.ParseError):
        ids, svg_ok, source_hash = {}, False, ""

    hero_info, pricing_info = _png_info(hero), _png_info(pricing)
    a = [
        _check("A01", .18, _text(ids, "hero-title") == "NORTHSTAR LAUNCH DAY", {"text": _text(ids, "hero-title")}),
        _check("A02", .12, _text(ids, "hero-subtitle") == "Clarity for every move.", {"text": _text(ids, "hero-subtitle")}),
        _check("A03", .18, _attrs(ids, "hero-background").get("fill") == "#143D59" and _attrs(ids, "hero-accent").get("fill") == "#F2B84B", {
            "background": _attrs(ids, "hero-background").get("fill"), "accent": _attrs(ids, "hero-accent").get("fill")}),
        _check("A04", .15, _attrs(ids, "brand-mark").get("transform", "").replace(" ", "") == "translate(112,72)", {"transform": _attrs(ids, "brand-mark").get("transform")}),
        _check("A05", .12, svg_ok and TARGET_IDS.issubset(ids), {"valid_svg": svg_ok, "required_ids_missing": sorted(TARGET_IDS - set(ids))}),
        _check("A06", .10, hero_info["valid"] and (hero_info["width"], hero_info["height"]) == (1600, 560), hero_info),
        _check("A07", .10, hero_info["valid"] and hero_info["size_bytes"] > 500, {"png": hero_info, "crop_endpoint_expected": "/hero.svg"}),
        _check("A08", .05, _attrs(ids, "hero-title").get("x") is not None and _attrs(ids, "brand-mark").get("transform") == "translate(112,72)", {"title_x": _attrs(ids, "hero-title").get("x"), "brand_transform": _attrs(ids, "brand-mark").get("transform")}),
    ]
    prices = {key: _text(ids, key) for key in ("starter-price", "growth-price", "scale-price")}
    highlight = _attrs(ids, "growth-highlight")
    badge = _text(ids, "growth-badge")
    b = [
        _check("B01", .15, prices["starter-price"] == "$19 / month", {"text": prices["starter-price"]}),
        _check("B02", .15, prices["growth-price"] == "$59 / month", {"text": prices["growth-price"]}),
        _check("B03", .15, prices["scale-price"] == "$149 / month", {"text": prices["scale-price"]}),
        _check("B04", .15, highlight.get("stroke", "").upper() == "#F2B84B" and highlight.get("stroke-width") == "6", {"stroke": highlight.get("stroke"), "stroke_width": highlight.get("stroke-width")}),
        _check("B05", .10, badge == "MOST POPULAR", {"text": badge}),
        _check("B06", .10, svg_ok and all(key in ids for key in ("pricing-section", "card-starter", "card-growth", "card-scale")), {"valid_svg": svg_ok, "card_ids": [key for key in ("card-starter", "card-growth", "card-scale") if key in ids]}),
        _check("B07", .10, pricing_info["valid"] and (pricing_info["width"], pricing_info["height"]) == (1400, 360), pricing_info),
        _check("B08", .05, pricing_info["valid"] and pricing_info["size_bytes"] > 500, {"png": pricing_info, "crop_endpoint_expected": "/pricing.svg"}),
        _check("B09", .05, all(_attrs(ids, key).get("x") for key in ("starter-price", "growth-price", "scale-price")), {"price_text_ids_have_positions": all(_attrs(ids, key).get("x") for key in ("starter-price", "growth-price", "scale-price"))}),
    ]
    receipt = preview_receipt if isinstance(preview_receipt, dict) else {}
    preview_ok = receipt.get("http_status") == 200 and receipt.get("svg_sha256") == source_hash and receipt.get("rendered") is True
    joint = [
        _check("J01", .30, all(row["passed"] for row in a[:5] + b[:6]), {"hero_and_pricing_source_checks": all(row["passed"] for row in a[:5] + b[:6])}),
        _check("J02", .25, hero_info["valid"] and pricing_info["valid"] and (hero_info["width"], hero_info["height"]) == (1600, 560) and (pricing_info["width"], pricing_info["height"]) == (1400, 360), {"hero_png": hero_info, "pricing_png": pricing_info}),
        _check("J03", .25, preview_ok, {"preview_status": receipt.get("http_status"), "preview_sha256_matches_final_svg": receipt.get("svg_sha256") == source_hash, "rendered": receipt.get("rendered") is True}),
        _check("J04", .20, svg_ok and TARGET_IDS.issubset(ids), {"valid_svg": svg_ok, "required_ids_missing": sorted(TARGET_IDS - set(ids))}),
    ]
    reasons = [] if preview_receipt else ["Host-collected final preview receipt is missing."]
    return make_grade(
        case_id="BC-04", run_id=run_id, actor_a_checks=a, actor_b_checks=b, joint_checks=joint,
        pass_threshold_a=.80, pass_threshold_b=.80, failure_reasons=reasons,
        run_metadata={"oracle": "BC-04 deterministic SVG/PNG Oracle", "workspace": str(root), "preview_receipt_host_collected": True},
    )


def grade_episode(snapshot_root: Path, receipt: dict, run_id: str) -> dict:
    """Grade recovered SVG/PNGs against host-fetched live preview responses."""
    workspace = snapshot_root.parent / "guest-output"
    source = workspace / "brand/launch_board.svg"
    try:
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    except OSError:
        source_hash = ""
    endpoints = receipt.get("http_endpoints", {}) if isinstance(receipt, dict) else {}
    preview = endpoints.get("preview", {}) if isinstance(endpoints, dict) else {}
    hero = endpoints.get("hero_crop", {}) if isinstance(endpoints, dict) else {}
    pricing = endpoints.get("pricing_crop", {}) if isinstance(endpoints, dict) else {}
    preview_receipt = {
        "http_status": preview.get("status_code") if isinstance(preview, dict) else None,
        "svg_sha256": source_hash,
        "rendered": all(isinstance(row, dict) and row.get("status_code") == 200 for row in (preview, hero, pricing))
                    and bool(source_hash),
    }
    return grade_case(workspace, preview_receipt, run_id)
