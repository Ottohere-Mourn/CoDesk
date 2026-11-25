"""Deterministic feasibility fixtures for the two independent CONC-04 actors."""
from __future__ import annotations

import importlib.util
import tempfile
import time
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("conc04_grade_private", CASE / "private/grade.py")
grade_mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(grade_mod)
grade = grade_mod.grade
asset_spec = importlib.util.spec_from_file_location("conc04_build_assets", CASE / "integration/build_assets.py")
asset_mod = importlib.util.module_from_spec(asset_spec)
assert asset_spec and asset_spec.loader
asset_spec.loader.exec_module(asset_mod)
build_assets = asset_mod.build


def _make_truth(root: Path):
    from PIL import Image, ImageDraw
    assets = root / "assets"
    build_assets(assets)
    workspace = root / "workspace"
    (workspace / "out_a").mkdir(parents=True)
    (workspace / "out_b").mkdir(parents=True)
    nodes = [{"name": name, "x": p[0], "y": p[1]} for name, p in grade_mod.SLOTS.items()]
    paths = [
        [[163,100],[247,100]], [[363,100],[447,100]], [[563,100],[747,100]],
        [[363,100],[363,340],[363,560]], [[363,560],[647,560]],
        [[763,560],[780,520],[760,350],[747,100]],
        [[563,100],[570,180],[570,520],[647,560]],
    ]
    edges = [{"from": a, "to": b, "points": p} for (a,b),p in zip(grade_mod.EDGES, paths)]
    # Use a deterministic edge ordering, independent of set iteration.
    edge_names = [("API Gateway","Auth Service"),("Auth Service","Order Engine"),
                  ("Order Engine","Inventory DB"),("Auth Service","Event Bus"),
                  ("Event Bus","Billing Worker"),("Billing Worker","Inventory DB"),
                  ("Order Engine","Billing Worker")]
    edges = [{"from": a, "to": b, "points": p} for (a,b),p in zip(edge_names, paths)]
    (workspace / "out_a/arch_flow.json").write_text(__import__("json").dumps({"nodes": nodes, "edges": edges}), encoding="utf-8")
    im = Image.new("RGB", (1000,680), "white"); d=ImageDraw.Draw(im)
    for name,(x,y) in grade_mod.SLOTS.items():
        d.rectangle((x-58,y-23,x+58,y+23), fill="#e7f0fb", outline="#2e5d7b", width=3)
    d.rectangle((860,8,980,32), fill="#00897B"); im.save(workspace / "out_a/arch_flow.png")
    labels={}; bevents=[]
    line_colors={"SPIKE":"#C62828","DROP":"#1565C0","FLATLINE":"#7B1FA2"}
    for chart,truth in grade_mod.TRUTH.items():
        im=Image.open(assets / "CONC-04/guest/in_b/charts" / f"{chart}.png").convert("RGB"); d=ImageDraw.Draw(im)
        d.rectangle((824,10,944,34), fill=grade_mod.MARKER_COLORS[chart])
        rows=[]
        for box,label in truth:
            x1,y1,x2,y2=box; d.rectangle(box, outline=line_colors[label], width=3)
            rows.append({"x1":x1,"y1":y1,"x2":x2,"y2":y2,"label":label})
            bevents.extend([{"type":"box_drag","chart":chart,"moves":4},
                            {"type":"classify","chart":chart,"key":{"SPIKE":"1","DROP":"2","FLATLINE":"3"}[label],"label":label}])
        labels[chart]=rows; im.save(workspace / f"out_b/{chart}.png")
    (workspace / "out_b/anomaly_labels.json").write_text(__import__("json").dumps(labels), encoding="utf-8")
    ae=[]
    for name in grade_mod.NODES: ae.append({"type":"node_drop","node":name,"moves":4})
    for a,b in edge_names: ae.append({"type":"edge_drag","from":a,"to":b,"moves":5})
    state={"a_events":ae,"b_events":bevents}
    return grade(workspace,state),state,workspace


def gates():
    start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="conc04-fixture-") as t:
        result, state, workspace=_make_truth(Path(t))
        pristine=grade(Path(t)/"empty",{})
        damaged={**state,"a_events":state["a_events"][:-1]}
        bad=grade(workspace,damaged)
    elapsed=time.monotonic()-start
    return {"gate1_pristine_fail":not pristine["joint_pass"],
            "gate2_gt_seq_ab_exists":result["joint_pass"],
            "gate3_gt_seq_ba_exists":result["joint_pass"],
            "gate4_gt_naive_race_corrupts":not bad["joint_pass"],
            "gate5_fixture_feasible":result["joint_pass"] and elapsed <= 180,
            "fixture_elapsed_s":round(elapsed,4),"conc_role_timeout_s":3600}
