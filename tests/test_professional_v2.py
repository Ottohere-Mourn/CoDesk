import copy
import json
import math
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tasks.professional_v2.grade_blender import close, grade, target_color
from tasks.professional_v2.validate_blender import gui_pixels_ready


ROOT = Path(__file__).resolve().parents[1] / "tasks/professional_v2"


@pytest.fixture
def states():
    invariant = {
        "objects": {"CaseLid": {"location": [-1.5, 0.65, 0.76]},
                    "CaseBase": {}, "ShellBody": {"materials": ["ShellFinish"]},
                    "ControlDial": {"materials": ["DialFinish"]}},
        "scene": {"frames": [1, 61]}, "materials": {},
    }
    baseline = {"native_reopened": True, "external_dependencies": [], "invariants": invariant,
                "motion": {"curves": [], "samples": {}}, "materials": {}}
    solved = copy.deepcopy(baseline)
    solved["motion"] = {
        "curves": [{"path": "rotation_euler", "index": 0, "modifiers": 0, "muted": False,
                    "keys": [{"frame": frame, "value": math.radians(angle), "interpolation": "LINEAR"}
                             for frame, angle in ((1, 0), (31, -60), (61, 0))]}],
        "samples": {str(frame): [math.radians(angle), 0, 0]
                    for frame, angle in ((1, 0), (16, -30), (31, -60), (46, -30), (61, 0))},
    }
    solved["materials"] = {
        "ShellFinish": {"connected": True, "values": {"Base Color": target_color((24, 91, 122)), "Roughness": 0.32, "Metallic": 0.15}},
        "DialFinish": {"connected": True, "values": {"Base Color": target_color((230, 183, 74)), "Roughness": 0.22, "Metallic": 0.80}},
    }
    return baseline, solved


def test_six_checks_per_role_and_seed_not_solved(states):
    baseline, solved = states
    result = grade(solved, baseline)
    assert result["gate_passed"]
    assert all(role["total"] == 6 and role["score"] == 1 for role in result["roles"].values())
    assert all(role["score"] < 1 for role in grade(baseline, baseline)["roles"].values())


def test_missing_animation_cannot_pass_by_matching_static_pose(states):
    baseline, solved = states
    solved["motion"]["curves"] = []
    result = grade(solved, baseline)
    assert result["roles"]["a"]["score"] < 1
    assert not result["roles"]["a"]["checks"]["linear_midpoint_motion"]
    assert result["roles"]["b"]["score"] == 1


def test_wrong_interpolation_is_detected(states):
    baseline, solved = states
    solved["motion"]["curves"][0]["keys"][0]["interpolation"] = "BEZIER"
    assert not grade(solved, baseline)["roles"]["a"]["checks"]["linear_midpoint_motion"]


def test_material_failure_does_not_change_role_a_score(states):
    baseline, solved = states
    solved["materials"]["ShellFinish"]["values"]["Base Color"] = [1, 0, 0, 1]
    result = grade(solved, baseline)
    assert result["roles"]["a"]["score"] == 1
    assert result["roles"]["b"]["score"] == pytest.approx(5 / 6)


@pytest.mark.parametrize("mutation", ["asset", "external", "not_reopened"])
def test_preservation_failures_gate_both_scores(states, mutation):
    baseline, solved = states
    if mutation == "asset":
        solved["invariants"]["objects"].pop("CaseBase")
    elif mutation == "external":
        solved["external_dependencies"] = ["outside.blend"]
    else:
        solved["native_reopened"] = False
    result = grade(solved, baseline)
    assert not result["gate_passed"]
    assert all(role["score"] == 0 for role in result["roles"].values())


def test_color_space_and_nonfinite_values():
    assert target_color((0, 128, 255)) == pytest.approx([0, 0.2158605001, 1, 1])
    assert not close(float("nan"), 0)
    assert not close(float("inf"), 1)
    assert not close(None, 0)


def test_gui_readiness_rejects_blank_window_even_with_titlebar():
    image = Image.new("RGB", (1280, 800), "#888888")
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((0, 0, 1279, 24), fill="blue")
    assert not gui_pixels_ready(image)
    drawing.rectangle((100, 100, 700, 600), fill="#222222")
    assert gui_pixels_ready(image)
    assert not gui_pixels_ready(Image.new("RGB", (128, 80), "white"))


def test_catalog_is_original_and_does_not_claim_rollouts_or_registration():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    assert len(catalog["pairs"]) == 6
    assert catalog["agent_trajectories"] == 0
    assert catalog["track"] == "hybrid_gui_cli"
    assert "Python console" in catalog["policy"]["allowed"]
    assert "Python console" not in catalog["policy"]["forbidden"]
    assert catalog["policy"]["host_unrestricted_codex"] is False
    assert not catalog["official_benchmark_subset"]
    identifiers = [pair["id"] for pair in catalog["pairs"]]
    assert len(set(identifiers)) == len(identifiers)
    for pair in catalog["pairs"]:
        assert pair["provenance"]["type"] == "original_synthetic_benchmark_inspired"
        assert not pair["provenance"]["copied_assets"]
        assert not pair["provenance"]["copied_prompts"]
        assert pair["provenance"]["sources"]
        assert set(pair["agents"]) == {"a", "b"}
        assert set(pair["agents"]["a"]["writes"]).isdisjoint(pair["agents"]["b"]["writes"])
        for agent in pair["agents"].values():
            assert len(agent["checks"]) == 6
            assert agent["planned_hybrid_phases"]
            if "instruction_file" in agent:
                assert (ROOT / agent["instruction_file"]).is_file()
            else:
                assert agent["instruction"]
    assert catalog["pairs"][0]["status"] == "authoring_implemented_not_harness_registered"
    assert all(pair["status"].startswith("spec_only") for pair in catalog["pairs"][1:])


def test_p4_instructions_allow_code_without_exposing_references():
    pair = json.loads((ROOT / "p4/pair.json").read_text())
    assert pair["track"] == "hybrid_gui_cli"
    for role in ("a", "b"):
        prompt = (ROOT / f"p4/task_{role}.md").read_text()
        assert "Python" in prompt and "allowed" in prompt
        assert "Use only the GUI" not in prompt
        assert "grade_blender" not in prompt and "blender_hinge" not in prompt
