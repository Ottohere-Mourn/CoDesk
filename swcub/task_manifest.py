"""Structural validation for the small, versioned benchmark task catalog."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any


TASK_MANIFEST_SCHEMA_VERSION = 1


class TaskManifestError(ValueError):
    pass


def validate_task_manifest(manifest: Any) -> dict[str, int]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        raise TaskManifestError("manifest root must be an object")
    if manifest.get("manifest_schema_version") != TASK_MANIFEST_SCHEMA_VERSION:
        errors.append(f"manifest_schema_version must be {TASK_MANIFEST_SCHEMA_VERSION}")
    if not isinstance(manifest.get("benchmark_version"), str) or not manifest["benchmark_version"]:
        errors.append("benchmark_version must be a non-empty string")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty array")
        tasks = []

    task_ids: set[str] = set()
    interaction_count = 0
    for index, task in enumerate(tasks):
        prefix = f"tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} must be an object")
            continue
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"{prefix}.task_id must be a non-empty string")
            task_id = f"<invalid-{index}>"
        elif task_id in task_ids:
            errors.append(f"duplicate task_id: {task_id}")
        task_ids.add(task_id)
        if not isinstance(task.get("title"), str) or not task["title"]:
            errors.append(f"{prefix}.title must be a non-empty string")
        environment = task.get("environment")
        if not isinstance(environment, dict):
            errors.append(f"{prefix}.environment must be an object")
        else:
            for field in ("adapter", "task_mode", "application"):
                if not isinstance(environment.get(field), str) or not environment[field]:
                    errors.append(f"{prefix}.environment.{field} must be a non-empty string")
            if "initial_state" not in environment:
                errors.append(f"{prefix}.environment needs an initial_state")

        roles = task.get("actor_roles")
        if (not isinstance(roles, list) or len(roles) < 2
                or any(not isinstance(role, str) or not role for role in roles)
                or len(set(roles)) != len(roles)):
            errors.append(f"{prefix}.actor_roles must contain at least two unique role names")
            roles = []
        actor_ids = task.get("actor_ids")
        if not isinstance(actor_ids, dict) or set(actor_ids) != set(roles):
            errors.append(f"{prefix}.actor_ids must map every actor role to one actor id")
            actor_ids = {}
        raw_actor_ids = list(actor_ids.values())
        valid_actor_ids = [actor_id for actor_id in raw_actor_ids
                           if isinstance(actor_id, str) and actor_id]
        known_actor_ids = set(valid_actor_ids)
        if len(known_actor_ids) != len(raw_actor_ids):
            errors.append(f"{prefix}.actor_ids values must be unique non-empty strings")

        independent = task.get("independent_solutions")
        if not isinstance(independent, dict) or set(independent) != set(roles):
            errors.append(f"{prefix}.independent_solutions must provide one goal per actor role")
            independent = {}
        for role, solution in independent.items():
            if not isinstance(solution, dict):
                errors.append(f"{prefix}.independent_solutions.{role} must be an object")
                continue
            if not solution.get("actor_class"):
                errors.append(f"{prefix}.independent_solutions.{role} needs actor_class")
            schedule = solution.get("schedule")
            if not _valid_schedule(schedule, known_actor_ids):
                errors.append(f"{prefix}.independent_solutions.{role} has an invalid schedule")
            elif actor_ids.get(role) not in schedule:
                errors.append(f"{prefix}.independent_solutions.{role} schedule omits its actor")
            if not any(key in solution for key in ("required_row", "final_state")):
                errors.append(f"{prefix}.independent_solutions.{role} needs a final-state goal")

        joint = task.get("joint_goal")
        if not isinstance(joint, dict) or not joint.get("evaluator"):
            errors.append(f"{prefix}.joint_goal needs an evaluator")
        elif not any(key in joint for key in ("required_rows", "final_state")):
            errors.append(f"{prefix}.joint_goal needs an explicit final-state goal")

        interactions = task.get("interactions")
        if not isinstance(interactions, list) or len(interactions) < 2:
            errors.append(f"{prefix}.interactions needs passing and failing controls")
            interactions = []
        outcomes: set[bool] = set()
        case_ids: set[str] = set()
        for case_index, case in enumerate(interactions):
            case_prefix = f"{prefix}.interactions[{case_index}]"
            if not isinstance(case, dict):
                errors.append(f"{case_prefix} must be an object")
                continue
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or not case_id or case_id in case_ids:
                errors.append(f"{case_prefix}.case_id must be a unique non-empty string")
            else:
                case_ids.add(case_id)
            outcome = case.get("expected_evaluator_success")
            if type(outcome) is not bool:
                errors.append(f"{case_prefix}.expected_evaluator_success must be boolean")
            else:
                outcomes.add(outcome)
            if case.get("deterministic") is not True:
                errors.append(f"{case_prefix} must declare deterministic=true")
            if not _valid_schedule(case.get("schedule"), known_actor_ids):
                errors.append(f"{case_prefix}.schedule references unknown or no actors")
            elif set(case["schedule"]) != known_actor_ids:
                errors.append(f"{case_prefix}.schedule must include every actor")
            if not any(key in case for key in ("final_rows", "final_state")):
                errors.append(f"{case_prefix} needs an explicit final state")
            interaction_count += 1
        if outcomes != {False, True}:
            errors.append(f"{prefix}.interactions must include expected pass and fail controls")

        evidence = task.get("evidence")
        if (not isinstance(evidence, dict) or not isinstance(evidence.get("tests"), list)
                or not evidence["tests"] or not evidence.get("smoke_script")):
            errors.append(f"{prefix}.evidence needs test names and a smoke script")

    if errors:
        raise TaskManifestError("; ".join(errors))
    return {"tasks": len(tasks), "interactions": interaction_count}


def validate_task_manifest_references(manifest: dict[str, Any], repo_root: Path) -> dict[str, int]:
    """Check manifest evidence names and actor classes against repository source files."""
    root = repo_root.resolve()
    actor_file = root / "swcub" / "actors.py"
    if not actor_file.is_file():
        raise TaskManifestError("cannot find swcub/actors.py for actor reference checks")
    actor_classes = set(re.findall(r"^class\s+(\w+)\b", actor_file.read_text(encoding="utf-8"), re.M))
    test_names: set[str] = set()
    for test_file in (root / "tests").glob("test_*.py"):
        test_names.update(re.findall(r"^\s*def\s+(test_\w+)\s*\(",
                                     test_file.read_text(encoding="utf-8"), re.M))

    errors: list[str] = []
    referenced_tests: set[str] = set()
    referenced_actors: set[str] = set()
    referenced_scripts: set[str] = set()
    for task in manifest["tasks"]:
        task_id = task["task_id"]
        for role, solution in task["independent_solutions"].items():
            class_name = solution["actor_class"].split("(", 1)[0]
            referenced_actors.add(class_name)
            if class_name not in actor_classes:
                errors.append(f"{task_id}: actor class does not exist: {class_name}")
        evidence = task["evidence"]
        for name in evidence["tests"]:
            referenced_tests.add(name)
            if name not in test_names:
                errors.append(f"{task_id}: test function does not exist: {name}")
        script = evidence["smoke_script"]
        referenced_scripts.add(script)
        target = (root / script).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            errors.append(f"{task_id}: smoke script does not exist inside repository: {script}")
    if errors:
        raise TaskManifestError("; ".join(errors))
    return {"actor_classes": len(referenced_actors), "test_functions": len(referenced_tests),
            "smoke_scripts": len(referenced_scripts)}


def _valid_schedule(schedule: Any, actor_ids: set[Any]) -> bool:
    return (isinstance(schedule, list) and bool(schedule)
            and all(isinstance(actor_id, str) and actor_id in actor_ids for actor_id in schedule))
