"""Exercise native references, real GUI evidence and native-file negative controls."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import time

from experiments import professional_trajectories as collector
from experiments.professional_v3 import P10Desktop, SOURCE


def native_command(workspace, trusted, image, command, output=None, role=None, observations=None):
    arguments = ["docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "4g",
        "-v", str(SOURCE.parent.parent) + ":/code:ro", "-v", str(workspace) + ":/work",
        "-v", str(trusted) + ":/trusted:ro", "-e", "PYTHONPATH=/code", "-e", "PYTHONDONTWRITEBYTECODE=1"]
    if output:
        output.mkdir(parents=True)
        arguments += ["-v", str(output) + ":/evaluation"]
    if observations:
        arguments += ["-v", str(observations) + ":/observations.jsonl:ro"]
    arguments += [image, "python3", "-m", "tasks.professional_v3.p10_native", command,
        "--workspace", "/work", "--trusted", "/trusted"]
    if output:
        arguments += ["--out", "/evaluation"]
    if role:
        arguments += ["--role", role]
    if observations:
        arguments += ["--observations", "/observations.jsonl"]
    result = collector.command(arguments, timeout=240)
    if output:
        (output / "stderr.log").write_bytes(result.stderr)
    return json.loads(result.stdout) if command == "grade" else None


def gui_review(root, roles, expected, image):
    maximum = max((record for record in expected["exposure"] if record["affected"] is not None), key=lambda record: record["affected"])["parcel_id"]
    low = next(record["parcel_id"] for record in expected["exposure"] if record["coverage"] < .8)
    totals = Counter()
    for record in expected["access"]["allocations"]:
        totals[record["origin_id"]] += record["persons"]
    partial = next(record["origin_id"] for record in expected["network"]["origins"] if 0 < totals[record["origin_id"]] < record["demand"])
    unreachable = next(record["origin_id"] for record in expected["network"]["origins"] if record["origin_id"] not in expected["access"]["reachable_origins"])
    steps = []
    for role in roles:
        steps.extend([("p10a", "exposure_parcels", "parcel_id", maximum), ("p10a", "exposure_parcels", "parcel_id", low),
                      ("p10a", "layout", "", "Exposure_Review")] if role == "a" else [
            ("p10b", "access_routes", "origin_id", partial), ("p10b", "access_exceptions", "origin_id", unreachable), ("p10b", "layout", "", "Access_Review")])
    desktop = P10Desktop(root / "shared", "p10", image)
    try:
        desktop.start()
        code = """from qgis.core import QgsProject, QgsRectangle
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import QApplication
from qgis.utils import iface
def show_step(step):
    role, name, field, identifier = step
    for widget in QApplication.topLevelWidgets():
        if 'AttributeTable' in widget.metaObject().className(): widget.close()
    for designer in iface.openLayoutDesigners(): designer.window().close()
    if name == 'layout':
        iface.openLayoutDesigner(QgsProject.instance().layoutManager().layoutByName(identifier))
    else:
        layer = QgsProject.instance().mapLayersByName(name)[0]
        iface.setActiveLayer(layer)
        feature = next(feature for feature in layer.getFeatures() if str(feature[field]) == identifier)
        layer.selectByIds([feature.id()])
        extent = QgsRectangle(feature.geometry().boundingBox())
        if extent.width() < 1: extent.grow(60)
        extent.scale(1.5)
        iface.mapCanvas().setExtent(extent)
        iface.mapCanvas().refresh()
        table = iface.showAttributeTable(layer, '\"'+field+'\" = '+repr(identifier))
        table.resize(560, 300)
        table.move(1010, 490)
        table.show()
        table.raise_()
        table.activateWindow()
    QApplication.processEvents()
"""
        code += "\nsteps=" + repr(steps) + "\n"
        code += "for index, step in enumerate(steps): QTimer.singleShot(1500+index*7000, lambda step=step: show_step(step))\n"
        desktop.raw(["xdotool", "key", "ctrl+alt+p"])
        time.sleep(1)
        desktop.raw(["xdotool", "type", "--clearmodifiers", "--delay", "0", "exec(" + repr(code) + ", {})"])
        desktop.raw(["xdotool", "key", "Return"])
        captured = set()
        deadline = time.monotonic() + len(steps) * 7 + 15
        while time.monotonic() < deadline and len(captured) < len(steps):
            state = desktop.state()
            for index, (task, name, field, identifier) in enumerate(steps):
                if index in captured:
                    continue
                matched = identifier in state.get("layouts_visible", []) if name == "layout" else (
                    state.get("active_layer") == name and state.get("table_visible") and state.get("selection_in_canvas")
                    and any(str(row.get(field)) == identifier for row in state.get("selected", [])))
                if matched:
                    path = root / task / f"review-{index}.png"
                    path.parent.mkdir(exist_ok=True)
                    desktop.screenshot(path)
                    desktop.capture(path, task)
                    captured.add(index)
            time.sleep(.5)
        collector.save(root / "gui-review.json", {"captured": sorted(captured), "expected_steps": len(steps), "last_state": desktop.state()})
        if len(captured) != len(steps):
            path = root / "debug.png"
            desktop.screenshot(path)
            raise RuntimeError("GUI review missed checkpoints: " + str(set(range(len(steps))) - captured))
    finally:
        desktop.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image", default="paragui/professional-rootless:20261103")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    expected = json.loads((args.dataset / "private/expected.json").read_text())
    protected = list(SOURCE.glob("p10*.py")) + [Path(__file__), Path(__file__).with_name("professional_v3.py"), Path(__file__).with_name("professional_native.py")]
    source_hashes = {str(path.relative_to(SOURCE.parent.parent)): collector.hashes(path.parent)[path.name] for path in protected}
    report = {"passed": False, "agent_rollouts": 0, "cases": {}, "negative_controls": {},
              "source_hashes": source_hashes, "input_hashes": collector.hashes(args.dataset / "dataset/pairs/p10/inputs")}
    collector.save(args.out / "validation.json", report)
    for case, roles in (("pristine", ""), ("a_only", "a"), ("b_only", "b"), ("ab", "ab"), ("ba", "ba")):
        root = args.out / case
        workspace = root / "shared/workspace"
        shutil.copytree(args.dataset / "dataset/pairs/p10/inputs", workspace)
        for role in roles:
            native_command(workspace, args.dataset / "private", args.image, "reference", role=role)
        artifact = native_command(workspace, args.dataset / "private", args.image, "grade", root / "artifact-grade")
        report["cases"][case] = {"artifact_scores": {role: artifact[role]["artifact_score"] for role in "ab"}}
        collector.save(args.out / "validation.json", report)
        assert all(artifact[role]["artifact_score"] == (1 if role in roles else 0) for role in "ab"), (case, artifact)
        if roles:
            gui_review(root, roles, expected, args.image)
            result = native_command(workspace, args.dataset / "private", args.image, "grade", root / "full-grade", observations=root / "native-observations.jsonl")
            report["cases"][case]["scores"] = {role: result[role]["score"] for role in "ab"}
            assert all(result[role]["success"] == (role in roles) for role in "ab"), (case, result)
        collector.save(args.out / "validation.json", report)
    for name in ("stale_project", "wrong_depth", "wrong_allocation", "stale_pdf", "fake_live_report"):
        root = args.out / name
        workspace = root / "shared/workspace"
        shutil.copytree(args.out / "ab/shared/workspace", workspace)
        observations = args.out / "ab/native-observations.jsonl"
        if name == "stale_project":
            shutil.copy2(args.out / "a_only/shared/workspace/RivertonReview.qgz", workspace / "RivertonReview.qgz")
        elif name in ("wrong_depth", "wrong_allocation"):
            statement = "UPDATE exposure_parcels SET mean_depth=999" if name == "wrong_depth" else "UPDATE access_routes SET persons=9999"
            code = "from osgeo import ogr; source=ogr.Open('/work/review.gpkg',1); source.ExecuteSQL(" + repr(statement) + ")"
            collector.command(["docker", "run", "--rm", "--network", "none", "-v", str(workspace) + ":/work", args.image, "python3", "-c", code])
        elif name == "stale_pdf":
            shutil.copy2(workspace / "exports/access/access_review.pdf", workspace / "exports/exposure/exposure_review.pdf")
        else:
            observations = root / "untrusted.jsonl"
            observations.write_text(json.dumps({"task": "p10a", "claimed_success": True}) + "\n")
        result = native_command(workspace, args.dataset / "private", args.image, "grade", root / "grade", observations=observations)
        assert not (result["a"]["success"] and result["b"]["success"]), name
        report["negative_controls"][name] = {role: result[role]["score"] for role in "ab"}
        collector.save(args.out / "validation.json", report)
    report["passed"] = True
    assert source_hashes == {str(path.relative_to(SOURCE.parent.parent)): collector.hashes(path.parent)[path.name] for path in protected}
    report["finished_at"] = time.time()
    collector.save(args.out / "validation.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
