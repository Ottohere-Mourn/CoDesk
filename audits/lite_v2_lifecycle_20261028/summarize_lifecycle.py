"""Summarize a v2 lifecycle episode, excluding suspended time from active overlap."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from audits.lite_v1_20261027.summarize_model import main as base_main, overlap, records


def main(root: Path) -> None:
    base_main(root)
    path = root / "model_metrics.json"
    metrics = json.loads(path.read_text())
    actors = {x["actor"]: x for x in records(root / "actors.jsonl")}
    events = records(root / "actor_lifecycle.jsonl")
    active = {role: [(actor["started_at"], actor["ended_at"])]
              for role, actor in actors.items()}
    waits = {}
    wait_intervals = []
    for suspended in [x for x in events if x.get("event") == "suspended_for_peer_handoff"]:
        role = suspended["actor"]
        terminal = next((x for x in events if x.get("actor") == role and x.get("time", 0) > suspended["time"]
                         and x.get("event") in {"woken_by_peer_handoff", "peer_handoff_wait_expired"}), None)
        if terminal and role in actors:
            active[role] = [(actors[role]["started_at"], suspended["time"])]
            if terminal["event"] == "woken_by_peer_handoff":
                active[role].append((terminal["time"], actors[role]["ended_at"]))
            waits[role] = round(terminal["time"] - suspended["time"], 3)
            wait_intervals.append((role, suspended["time"], terminal["time"]))
    metrics["actor_handoff_wait_s"] = waits
    metrics["actor_active_overlap_excluding_handoff_wait_s"] = overlap(
        active.get("A", []), active.get("B", []))
    metrics["actor_lifecycle_events"] = [{k: event.get(k) for k in ("event", "actor", "peer", "time")}
                                          for event in events]
    relay = records(root / "codex_relay_events.jsonl")
    metrics["model_requests_during_handoff_wait"] = sum(
        request.get("actor") == role and start <= request.get("started_at", 0) < end
        for role, start, end in wait_intervals for request in relay)
    metrics["desktop_calls_during_handoff_wait"] = sum(
        start <= action.get("t", 0) < end
        for role, start, end in wait_intervals
        for action in records(root / "actor_runs" / role / role / "actions.jsonl"))
    path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"run_id": root.name, "actor_handoff_wait_s": waits,
                      "actor_active_overlap_excluding_handoff_wait_s":
                      metrics["actor_active_overlap_excluding_handoff_wait_s"]}, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
