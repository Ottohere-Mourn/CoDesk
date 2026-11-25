"""Deterministic reference-state checks for CONC-01; not model-run evidence."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image, ImageDraw
from grade import evaluate

TABS = [f"tab_{i}" for i in range(1, 7)]
COLORS = ["#1E88E5", "#8E24AA", "#FB8C00", "#43A047", "#00ACC1", "#F4511E"]
SAMPLE_STATE = {
    "a_controls": [{"name": n, "width": w, "height": 900} for w in (375, 768, 1440) for n in ("delivery", "promotion", "tax")],
    "a_checks": [{"band": b, "width": w, "height": h, "badge_code": c} for b, w, h, c in (("mobile", 375, 812, "123456"), ("tablet", 768, 1024, "123457"), ("desktop", 1440, 900, "123458"))],
    "b_hovers": [{"tab": t, "peak": p, "width": 1920, "height": 1080} for t in TABS for p in ("peak_a", "peak_b")],
    "peaks": {t: {"peak_a": i + 11.125, "peak_b": i + 22.875} for i, t in enumerate(TABS)},
}


def pristine():
    return {"actor_a": False, "actor_b": False, "state": {}}


def actor_write(state, actor):
    out = {"actor_a": state["actor_a"], "actor_b": state["actor_b"], "state": dict(state["state"])}
    out["actor_a" if actor == "A" else "actor_b"] = True
    out["state"][actor] = "complete"
    return out


def _image(path, size, color, warning=False):
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, min(119, size[0] - 1), 23), fill=color)
    if warning:
        draw.rectangle((0, 40, 200, 240), fill="#D32F2F")
    image.save(path)


def _write_a(workspace):
    out = workspace / "out_a"
    out.mkdir(parents=True, exist_ok=True)
    report = {"mobile": {"has_bug": True, "bug_element_id": "btn-express-pay", "badge_code": "123456"},
              "tablet": {"has_bug": True, "bug_element_id": "promo-banner", "badge_code": "123457"},
              "desktop": {"has_bug": False, "bug_element_id": "NONE", "badge_code": "123458"}}
    (out / "qa_viewport_report.json").write_text(json.dumps(report), encoding="utf-8")
    for name, size in (("qa_375.png", (375, 812)), ("qa_768.png", (768, 1024)), ("qa_1440.png", (1440, 900))):
        _image(out / name, size, "#00BFA5")


def _write_b(workspace):
    out = workspace / "out_b"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ops_telemetry.json").write_text(json.dumps(SAMPLE_STATE["peaks"]), encoding="utf-8")
    for i, (tab, color) in enumerate(zip(TABS, COLORS), 1):
        _image(out / f"ops_tab_{i}.png", (1920, 1080), color)


def reference_state():
    return json.loads(json.dumps(SAMPLE_STATE))


def grade_order(order):
    with tempfile_dir() as workspace:
        staged = pristine()
        for actor in order:
            staged = actor_write(staged, actor)
            if actor == "A": _write_a(workspace)
            else: _write_b(workspace)
        return evaluate(workspace, reference_state())


class tempfile_dir:
    def __enter__(self):
        import tempfile
        self._temp = tempfile.TemporaryDirectory()
        return Path(self._temp.name)
    def __exit__(self, *_): self._temp.cleanup()


def gates():
    start = time.perf_counter()
    with tempfile_dir() as empty:
        g1 = not evaluate(empty, reference_state())["joint_pass"]
    g2 = grade_order(("A", "B"))["joint_pass"]
    g3 = grade_order(("B", "A"))["joint_pass"]
    # A/B write the shared browser viewport without checking the current size;
    # B's narrow-window guard rejects the chart reads, so the joint hand-in is incomplete.
    naive = {"a_controls": SAMPLE_STATE["a_controls"], "a_checks": SAMPLE_STATE["a_checks"],
             "b_hovers": [], "peaks": SAMPLE_STATE["peaks"]}
    with tempfile_dir() as damaged:
        _write_a(damaged); _write_b(damaged)
        g4 = not evaluate(damaged, naive)["joint_pass"]
    # This is only a fixture-level merge check; the required real-tool Gate 5
    # observation is produced by a Guest reference replay, not inferred here.
    g5_fixture = grade_order(("A", "B"))["joint_pass"]
    elapsed = time.perf_counter() - start
    return {"gate1_pristine_fail": g1, "gate2_gt_seq_ab_exists": g2,
            "gate3_gt_seq_ba_exists": g3, "gate4_gt_naive_race_corrupts": g4,
            "gate5_fixture_feasible": g5_fixture, "fixture_elapsed_s": round(elapsed, 4),
            "gate5_real_tool_timing": False, "conc_role_timeout_s": 3600,
            "note": "Gate 5 must be confirmed by a real Guest GUI reference replay; offline fixture timing is not accepted."}
