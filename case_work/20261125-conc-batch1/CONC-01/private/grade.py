from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageChops

TABS = [f"tab_{i}" for i in range(1, 7)]
COLORS = {"tab_1": "#1E88E5", "tab_2": "#8E24AA", "tab_3": "#FB8C00", "tab_4": "#43A047", "tab_5": "#00ACC1", "tab_6": "#F4511E"}
WIDTHS = {"mobile": (355, 395), "tablet": (748, 788), "desktop": (1415, 1465)}
BUGS = {"mobile": (True, "btn-express-pay"), "tablet": (True, "promo-banner"), "desktop": (False, "NONE")}
TEAL, RED = "#00BFA5", "#D32F2F"


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _image(path):
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _has_color(image, color, threshold=20):
    if image is None:
        return False
    target = _rgb(color)
    solid = Image.new("RGB", image.size, target)
    exact = ImageChops.difference(image, solid).convert("L").histogram()[0]
    return exact >= threshold


def evaluate(workspace, state):
    workspace = Path(workspace)
    a_report = _json(workspace / "out_a" / "qa_viewport_report.json")
    a_checks = [bool(a_report and all(isinstance(a_report.get(b), dict) and {"has_bug", "bug_element_id", "badge_code"} <= set(a_report[b]) for b in WIDTHS))]
    records = {row.get("band"): row for row in (state or {}).get("a_checks", [])}
    for band, (low, high) in WIDTHS.items():
        a_checks.append(any(row.get("band") == band and low <= int(row.get("width", 0)) <= high for row in (state or {}).get("a_checks", [])))
    for band, (has_bug, target) in BUGS.items():
        row = (a_report or {}).get(band, {})
        element = str(row.get("bug_element_id", "")).replace("#", "").strip()
        if band == "tablet":
            ids = {x.strip() for x in element.replace(",", " ").replace(";", " ").replace("/", " ").split()}
            ok_id = bool(ids & {"promo-banner", "cart-total"})
        else:
            ok_id = element == target
        a_checks.append(row.get("has_bug") is has_bug and ok_id)
    for band in WIDTHS:
        reported = str((a_report or {}).get(band, {}).get("badge_code", ""))
        a_checks.append(bool(records.get(band)) and reported == str(records.get(band, {}).get("badge_code", "")))
    for name, band in zip(("qa_375.png", "qa_768.png", "qa_1440.png"), WIDTHS):
        image = _image(workspace / "out_a" / name)
        low, high = WIDTHS[band]
        valid = bool(image and low <= image.width <= high and _has_color(image, TEAL) and not any(_has_color(image, c) for c in COLORS.values()))
        a_checks.append(valid)
    controls = (state or {}).get("a_controls", [])
    a_checks.append(all(any(r.get("name") == name and low <= int(r.get("width", 0)) <= high
                           for r in controls)
                        for low, high in WIDTHS.values()
                        for name in ("delivery", "promotion", "tax")))

    b_report = _json(workspace / "out_b" / "ops_telemetry.json")
    b_checks = [bool(b_report and all(t in b_report for t in TABS))]
    truth = (state or {}).get("peaks", {})
    for tab in TABS:
        given, actual = (b_report or {}).get(tab, {}), truth.get(tab, {})
        b_checks.append(all(isinstance(given.get(k), (int, float)) and abs(given[k] - actual.get(k, -999999)) < 1e-3 for k in ("peak_a", "peak_b")))
    for tab in TABS:
        image = _image(workspace / "out_b" / f"ops_{tab}.png")
        valid = bool(image and image.width >= 1860 and image.height >= 950 and _has_color(image, COLORS[tab]) and not _has_color(image, RED, 100) and not _has_color(image, TEAL))
        b_checks.append(valid)
    hovers = (state or {}).get("b_hovers", [])
    observed = {(x.get("tab"), x.get("peak")) for x in hovers
                if int(x.get("width", 0)) >= 1860 and int(x.get("height", 0)) >= 950}
    required = {(tab, peak) for tab in TABS for peak in ("peak_a", "peak_b")}
    b_checks.append(required <= observed)
    return {"actor_a": sum(a_checks) / 14, "actor_b": sum(b_checks) / 14,
            "joint_pass": all(a_checks) and all(b_checks),
            "checks": {"actor_a": a_checks, "actor_b": b_checks},
            "flags": [f"A{i + 1}" for i, ok in enumerate(a_checks) if not ok] + [f"B{i + 1}" for i, ok in enumerate(b_checks) if not ok]}
