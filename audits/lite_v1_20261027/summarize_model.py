"""Summarize one real Lite run without using hidden Gold or model transcript text."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import sys


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def document(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def overlap(first: list[tuple[float, float]], second: list[tuple[float, float]]) -> float:
    a, b = sorted(first), sorted(second)
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        total += max(0.0, min(a[i][1], b[j][1]) - max(a[i][0], b[j][0]))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return round(total, 3)


def main(root: Path) -> None:
    provenance = document(root / "provenance.json")
    result = document(root / "result.json")
    failure = document(root / "failure.json")
    oracle = result.get("oracle") or document(root / "oracle.json")
    actors = {r["actor"]: r for r in records(root / "actors.jsonl")}
    relay = records(root / "codex_relay_events.jsonl")
    per_actor = {}
    request_intervals = {}
    action_intervals = {}
    for role in "AB":
        requests = [x for x in relay if x.get("actor") == role]
        actions = records(root / "actor_runs" / role / role / "actions.jsonl")
        usages = [x.get("usage") or {} for x in requests if x.get("upstream_status") == 200]
        request_intervals[role] = [(x["started_at"], x["time"]) for x in requests
                                   if x.get("started_at") and x.get("time")]
        action_intervals[role] = [(x["action_started_at"], x["action_ended_at"]) for x in actions
                                  if x.get("executed") and x.get("action_started_at") and x.get("action_ended_at")]
        per_actor[role] = {
            "actor_status": actors.get(role, {}).get("status"),
            "actor_elapsed_s": actors.get(role, {}).get("elapsed_s"),
            "desktop_tool_calls": len(actions),
            "executed_gui_actions": sum(bool(x.get("executed")) for x in actions),
            "gui_action_s": round(sum(x.get("action_ended_at", 0) - x.get("action_started_at", 0)
                                      for x in actions if x.get("executed")), 3),
            "screenshot_s": round(sum(x.get("screenshot_s", 0) for x in actions), 3),
            "model_requests": len(requests),
            "model_request_s": round(sum(x.get("elapsed_s", 0) for x in requests), 3),
            "model_http_statuses": {str(status): sum(x.get("upstream_status") == status for x in requests)
                                    for status in sorted({x.get("upstream_status") for x in requests}, key=str)},
            "input_tokens": sum(x.get("input_tokens", 0) for x in usages),
            "output_tokens": sum(x.get("output_tokens", 0) for x in usages),
            "cached_input_tokens": sum((x.get("input_tokens_details") or {}).get("cached_tokens", 0)
                                       for x in usages),
            "total_tokens": sum(x.get("total_tokens", 0) for x in usages),
        }
    actor_intervals = {role: [(actors[role]["started_at"], actors[role]["ended_at"])]
                       for role in "AB" if role in actors}
    qemu = [x for x in records(root / "qemu_process_resources.jsonl") if "rss_bytes" in x]
    qemu_by_process = defaultdict(list)
    memory_by_bucket = defaultdict(dict)
    for x in qemu:
        identity = (x["container_id"], x["pid"], x["process_created"])
        qemu_by_process[identity].append(x)
        memory_by_bucket[math.floor(x["time"] / 5)][identity] = x["rss_bytes"]
    qemu_cpu = sum(max(s["cpu_seconds"] for s in group) - min(s["cpu_seconds"] for s in group)
                   for group in qemu_by_process.values())
    start = provenance.get("started_at")
    failure_end = (datetime.fromisoformat(failure["failed_at_utc"]).timestamp()
                   if failure.get("failed_at_utc") else None)
    first_actor = min((x["started_at"] for x in actors.values()), default=None)
    last_actor = max((x["ended_at"] for x in actors.values()), default=None)
    output = {
        "run_id": root.name, "condition": provenance.get("condition"),
        "case_id": provenance.get("case_id"), "model": provenance.get("model"),
        "role_step_budget": provenance.get("effective_role_step_budget"),
        "result_status": result.get("status") or failure.get("status"),
        "oracle_actor_success": {r: oracle.get("actors", {}).get(r, {}).get("success") for r in "AB"},
        "oracle_joint_success": oracle.get("joint_success"),
        "total_elapsed_s": (result.get("elapsed_s") if result else
                            round(failure_end - start, 3) if failure_end and start else None),
        "setup_until_actor_s": round(first_actor - start, 3) if first_actor and start else None,
        "actor_phase_s": round(last_actor - first_actor, 3) if first_actor and last_actor else None,
        "actor_execution_overlap_s": overlap(actor_intervals.get("A", []), actor_intervals.get("B", [])),
        "model_request_overlap_s": overlap(request_intervals["A"], request_intervals["B"]),
        "gui_action_overlap_s": overlap(action_intervals["A"], action_intervals["B"]),
        "actors": per_actor,
        "qemu_process_count": len(qemu_by_process),
        "qemu_cpu_seconds_sampled": round(qemu_cpu, 3),
        "qemu_peak_single_rss_gib": round(max((x["rss_bytes"] for x in qemu), default=0) / 2**30, 3),
        "qemu_peak_sampled_sum_rss_gib": round(max((sum(b.values()) for b in memory_by_bucket.values()), default=0) / 2**30, 3),
        "workspace_transfers": sum(x.get("event") == "transfer_verified" for x in records(root / "workspace_versions" / "events.jsonl")),
        "workspace_sync_errors": document(root / "workspace_sync_result.json").get("transient_errors"),
        "reset_guests": len(result.get("reset", [])),
        "scope": "Actor/API/GUI overlap is measured from timestamps; it does not by itself prove focus interference.",
    }
    (root / "model_metrics.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
