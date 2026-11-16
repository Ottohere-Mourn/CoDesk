"""Summarize downloaded public trajectories without copying model reasoning."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


WEAVE_TASKS = (
    "SPA_task_0_blender_room_arrange",
    "DES_task_15_blender_bpy_lookdev_eyedrop",
    "SPA_task_1_qgis_flood_zone",
    "SPA_task_2_kicad_pcb_route",
    "SPA_task_13_meshlab_printability_audit",
    "SPA_task_14_cloudcompare_scan_vs_cad",
)
REFRESH_EXPORT = "https://api.trajectories.sh/api/public/trajectories/d701f96e-8132-485a-80f3-654dea6178ee/export"
REFRESH_ATIF = (
    "https://api.trajectories.sh/api/viewer/by-id/d701f96e-8132-485a-80f3-654dea6178ee"
    "/api/jobs/blenderbench-image-kitchen-rigging"
    "/trials/blender-image-kitchen-rigging__jYHU2au/trajectory"
)


def weave_counts(data):
    steps = data["steps"]
    kinds = Counter(step["kind"] for step in steps)
    channels = [step["kind"] for step in steps if step["kind"] in ("gui", "cli")]
    return {
        "raw_events": len(steps),
        "kind_counts": dict(sorted(kinds.items())),
        "numbered_events": sum(kind != "note" for kind in (step["kind"] for step in steps)),
        "events_with_shot": sum(bool(step.get("shot")) for step in steps),
        "gui_noop_events": sum(step["kind"] == "gui" and step.get("action") == "(no-op)" for step in steps),
        "gui_cli_switches_ignoring_notes": sum(left != right for left, right in zip(channels, channels[1:])),
    }


def atif_counts(data):
    steps = data["steps"]
    calls = [call for step in steps for call in step.get("tool_calls", [])]
    images = []
    for step in steps:
        for result in step.get("observation", {}).get("results", []):
            content = result.get("content")
            if isinstance(content, list):
                images.extend(block for block in content if isinstance(block, dict) and block.get("type") == "image")
    return {
        "schema_version": data["schema_version"],
        "raw_steps": len(steps),
        "source_counts": dict(sorted(Counter(step["source"] for step in steps).items())),
        "explicit_tool_calls": len(calls),
        "tool_counts": dict(sorted(Counter(call["function_name"] for call in calls).items())),
        "image_observation_blocks": len(images),
    }


def audit(raw_dir):
    raw_dir = Path(raw_dir)

    def read(filename):
        raw = (raw_dir / filename).read_bytes()
        return json.loads(raw), hashlib.sha256(raw).hexdigest()

    manifest, manifest_hash = read("weave-manifest.json")
    gallery = {entry["id"]: entry for entry in manifest}
    samples = []
    for task in WEAVE_TASKS:
        data, digest = read(f"weave-{task}.json")
        counts = weave_counts(data)
        samples.append({
            "task_id": task,
            "url": f"https://weavebench.github.io/trajectories/data/{task}.json",
            "sha256": digest,
            "published_model": data["model"],
            "published_harness": data["harness"],
            "published_score": data["score"],
            "gallery_steps": gallery[task]["steps"],
            "gallery_matches_numbered_events": gallery[task]["steps"] == counts["numbered_events"],
            **counts,
        })
    refresh, refresh_hash = read("refresh-rigging-atif.json")
    repositories = {}
    for name in ("weave", "cadworld"):
        tree, digest = read(f"{name}-tree.json")
        repositories[name] = {"commit": tree["sha"], "tree_sha256": digest}
    return {
        "schema_version": 1,
        "observed_date_utc": "2026-11-02",
        "selection": "Purposive professional-software sample; not random or representative.",
        "counting_caveat": "Publisher events, not primitive GUI actions. CLI events may contain GUI automation. Images are observations, not proof of GUI-only editing.",
        "weave_gallery_entries": len(manifest),
        "weave_gallery_sha256": manifest_hash,
        "weave_samples": samples,
        "refresh_sample": {"url": REFRESH_ATIF, "export_url": REFRESH_EXPORT,
                           "sha256": refresh_hash, **atif_counts(refresh)},
        "repositories": repositories,
        "cadworld_evidence_level": "Task examples, native evaluator contracts and action logging contract inspected; no full public rollout verified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = json.dumps(audit(args.raw_dir), ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
