"""Deterministic private oracle for CONC-04; never shipped as Guest input."""
from __future__ import annotations

import json
import math
from itertools import permutations
from pathlib import Path

from PIL import Image


NODES = ["API Gateway", "Auth Service", "Order Engine", "Inventory DB", "Event Bus", "Billing Worker"]
SLOTS = {"API Gateway": (105, 100), "Auth Service": (305, 100), "Order Engine": (505, 100),
         "Inventory DB": (805, 100), "Event Bus": (305, 560), "Billing Worker": (705, 560)}
EDGES = {("API Gateway", "Auth Service"), ("Auth Service", "Order Engine"),
         ("Order Engine", "Inventory DB"), ("Auth Service", "Event Bus"),
         ("Event Bus", "Billing Worker"), ("Billing Worker", "Inventory DB"),
         ("Order Engine", "Billing Worker")}
OBSTACLES = [(395, 220, 495, 365), (610, 365, 740, 490)]
STRIPES = {"#00897B", "#3949AB", "#00838F", "#6A1B9A", "#EF6C00"}
# Coordinates are private answer-key intervals in the 960x540 source chart space.
TRUTH = {
    "chart_1": [((265, 115, 315, 165), "SPIKE"), ((620, 250, 740, 280), "FLATLINE")],
    "chart_2": [((340, 400, 420, 448), "DROP"), ((675, 110, 735, 190), "SPIKE")],
    "chart_3": [((230, 220, 355, 252), "FLATLINE"), ((605, 360, 680, 455), "DROP")],
    "chart_4": [((435, 110, 500, 340), "SPIKE"), ((735, 370, 850, 430), "FLATLINE")],
}
MARKER_COLORS = {"chart_1": "#3949AB", "chart_2": "#00838F", "chart_3": "#6A1B9A", "chart_4": "#EF6C00"}
LABEL_COLORS = {"SPIKE": "#C62828", "DROP": "#1565C0", "FLATLINE": "#7B1FA2"}


def _parse(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _intersects(p, q, rect):
    # Liang–Barsky against a closed axis-aligned rectangle.
    x1, y1 = p; x2, y2 = q
    l, t, r, b = rect
    dx, dy = x2 - x1, y2 - y1
    lo, hi = 0.0, 1.0
    for den, num in ((-dx, x1-l), (dx, r-x1), (-dy, y1-t), (dy, b-y1)):
        if abs(den) < 1e-9:
            if num < 0:
                return False
            continue
        v = num / den
        if den < 0:
            lo = max(lo, v)
        else:
            hi = min(hi, v)
        if lo > hi:
            return False
    return True


def _edge_clear(edge):
    pts = edge.get("points")
    if not isinstance(pts, list) or len(pts) < 2:
        return False
    try:
        return all(not _intersects(tuple(a), tuple(b), o) for a, b in zip(pts, pts[1:]) for o in OBSTACLES)
    except (TypeError, ValueError):
        return False


def _iou(a, b):
    x1, y1, x2, y2 = a
    X1, Y1, X2, Y2 = b
    iw, ih = max(0, min(x2, X2)-max(x1, X1)), max(0, min(y2, Y2)-max(y1, Y1))
    inter = iw * ih
    area_a = max(0, x2-x1) * max(0, y2-y1)
    area_b = max(0, X2-X1) * max(0, Y2-Y1)
    return inter / (area_a + area_b - inter) if area_a + area_b > inter else 0.0


def _rgba(hex_color):
    s = hex_color.lstrip("#")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))


def _pixel_count(path, color, box=None):
    try:
        im = Image.open(path).convert("RGB")
    except (OSError, ValueError):
        return 0
    if box:
        im = im.crop(box)
    target = _rgba(color)
    return sum(1 for pixel in im.getdata() if pixel == target)


def _a(workspace: Path, state: dict):
    graph = _parse(workspace / "out_a" / "arch_flow.json") or {}
    image = workspace / "out_a" / "arch_flow.png"
    nodes = {n.get("name"): n for n in graph.get("nodes", []) if isinstance(n, dict)}
    edges = graph.get("edges", [])
    flags = []
    checks = []
    checks.append(isinstance(graph.get("nodes"), list) and isinstance(graph.get("edges"), list))
    for name, (x, y) in SLOTS.items():
        n = nodes.get(name, {})
        try:
            checks.append(math.hypot(float(n["x"])-x, float(n["y"])-y) <= 25)
        except (KeyError, TypeError, ValueError):
            checks.append(False)
    pairs = [(e.get("from"), e.get("to")) for e in edges if isinstance(e, dict)]
    checks.append(len(pairs) == 7 and set(pairs) == EDGES)
    checks.append(len(edges) == 7 and all(_edge_clear(e) for e in edges))
    ae = state.get("a_events", [])
    placed = [e for e in ae if e.get("type") == "node_drop" and e.get("moves", 0) >= 3]
    drawn = [e for e in ae if e.get("type") == "edge_drag" and e.get("moves", 0) >= 3]
    checks.append({e.get("node") for e in placed} == set(NODES) and len(placed) == 6
                  and {(e.get("from"), e.get("to")) for e in drawn} == EDGES and len(drawn) == 7)
    checks.append(_pixel_count(image, "#00897B") >= 120*24 and all(_pixel_count(image, c) == 0 for c in STRIPES-{"#00897B"}))
    visible = True
    for name, (x, y) in SLOTS.items():
        if _pixel_count(image, "#2E5D7B", (max(0,x-64),max(0,y-27),min(1000,x+65),min(680,y+29))) < 20:
            visible = False
    checks.append(visible)
    return checks


def _b(workspace: Path, state: dict):
    labels = _parse(workspace / "out_b" / "anomaly_labels.json") or {}
    checks = [isinstance(labels, dict) and set(TRUTH) <= set(labels)]
    box_ok = {}
    for chart, truth in TRUTH.items():
        actual = labels.get(chart, [])
        if not isinstance(actual, list) or len(actual) != 2:
            box_ok[chart] = False
            checks.extend([False, False])
            continue
        try:
            candidates = [((float(b["x1"]),float(b["y1"]),float(b["x2"]),float(b["y2"])),b.get("label")) for b in actual]
            best = max((sum(_iou(candidates[i][0], truth[p[i]][0]) >= .75 and candidates[i][1] == truth[p[i]][1]
                            for i in range(2)) for p in permutations(range(2))), default=0)
            ok = best == 2
        except (KeyError, TypeError, ValueError):
            ok = False
        box_ok[chart] = ok
        checks.extend([ok, ok])
    be = state.get("b_events", [])
    drags = [e for e in be if e.get("type") == "box_drag" and e.get("moves", 0) >= 3]
    keys = [e for e in be if e.get("type") == "classify" and e.get("key") in {"1", "2", "3"}]
    # Shared-GUI collisions can require legitimate retries and corrections;
    # count qualifying interactions rather than requiring an exact event total.
    checks.append(len(drags) + len(keys) >= 8)
    charts_ok = True
    for chart in ("chart_1", "chart_2"):
        p = workspace / "out_b" / f"{chart}.png"
        charts_ok &= _pixel_count(p, MARKER_COLORS[chart]) >= 120*20
        charts_ok &= any(_pixel_count(p, c) >= 50 for c in LABEL_COLORS.values())
        charts_ok &= _pixel_count(p, "#00897B") == 0
    checks.append(bool(charts_ok))
    charts_ok = True
    for chart in ("chart_3", "chart_4"):
        p = workspace / "out_b" / f"{chart}.png"
        charts_ok &= _pixel_count(p, MARKER_COLORS[chart]) >= 120*20
        charts_ok &= any(_pixel_count(p, c) >= 50 for c in LABEL_COLORS.values())
        charts_ok &= _pixel_count(p, "#00897B") == 0
    checks.append(bool(charts_ok))
    return checks


def grade(workspace: Path, state: dict):
    a, b = _a(Path(workspace), state or {}), _b(Path(workspace), state or {})
    return {"actor_a": sum(a)/12, "actor_b": sum(b)/12, "joint_pass": all(a) and all(b),
            "checks": {"actor_a": a, "actor_b": b},
            "flags": [*(f"A{i+1}" for i,v in enumerate(a) if not v), *(f"B{i+1}" for i,v in enumerate(b) if not v)]}
