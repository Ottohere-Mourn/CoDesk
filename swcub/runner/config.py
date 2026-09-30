"""Validated, bounded configuration for the CoDesk Runner V1 pilot."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,29}$")
CONDITIONS = {"solo_document", "solo_chat", "ma_id", "ma_sd", "solo"}
FAMILIES = {"track_a_v1", "writer_calc_v1"}


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_config(data)
    if "task_family" not in data:
        data["task_family"] = data["task"]
    return data


def validate_config(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("experiment config must be a JSON object")
    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    experiment_id = data.get("experiment_id")
    if not isinstance(experiment_id, str) or not EXPERIMENT_ID_RE.fullmatch(experiment_id):
        raise ValueError("experiment_id must be 8-30 safe ASCII characters")
    family = data.get("task", data.get("task_family"))
    if data.get("task_family", family) != family:
        raise ValueError("task and task_family must identify the same registered family")
    if family not in FAMILIES:
        raise ValueError(f"task_family must be one of {sorted(FAMILIES)}")
    if data.get("task_version") != "1.0.0":
        raise ValueError(f"{family} requires frozen task_version 1.0.0")
    backend_topology = data.get("backend_topology", "legacy_per_actor_clone")
    if backend_topology not in {"legacy_per_actor_clone", "same_workspace"}:
        raise ValueError("backend_topology must be legacy_per_actor_clone or same_workspace")
    if backend_topology == "same_workspace" and family != "writer_calc_v1":
        raise ValueError("same_workspace topology is currently supported only for writer_calc_v1")
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("episodes must be a nonempty list")
    seen: set[tuple[str, int]] = set()
    for index, episode in enumerate(episodes):
        if not isinstance(episode, dict):
            raise ValueError(f"episodes[{index}] must be an object")
        condition = episode.get("condition")
        repeat = episode.get("repeat")
        allowed = ({"solo_document", "solo_chat", "ma_id", "ma_sd"}
                   if family == "track_a_v1" else {"solo", "ma_id", "ma_sd"})
        if condition not in allowed:
            raise ValueError(f"episodes[{index}].condition must be one of {sorted(allowed)}")
        if type(repeat) is not int or not 1 <= repeat <= 5:
            raise ValueError(f"episodes[{index}].repeat must be an integer from 1 to 5")
        key = (condition, repeat)
        if key in seen:
            raise ValueError(f"duplicate episode condition/repeat: {key}")
        seen.add(key)
    workers = data.get("max_workers", 1)
    if type(workers) is not int or workers not in (1, 2):
        raise ValueError("max_workers must be 1 or 2")
    guest_slots = data.get("max_concurrent_guests", 2)
    if type(guest_slots) is not int or not 1 <= guest_slots <= 4:
        raise ValueError("max_concurrent_guests must be between 1 and 4")
    if guest_slots < 2 and any(item["condition"] == "ma_id" for item in episodes):
        raise ValueError("MA-ID episodes require max_concurrent_guests of at least 2")
    if guest_slots < 2 and family == "writer_calc_v1" and any(
            item["condition"] == "solo" for item in episodes):
        raise ValueError("paired solo episodes require max_concurrent_guests of at least 2")
    if data.get("max_workers", 1) > data.get("max_concurrent_guests", 2):
        raise ValueError("max_workers cannot exceed max_concurrent_guests")
    stagger = data.get("startup_stagger_seconds", 15)
    if type(stagger) not in (int, float) or not 0 <= stagger <= 120:
        raise ValueError("startup_stagger_seconds must be between 0 and 120")
    root = data.get("artifact_root")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("artifact_root must be a nonempty path")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
