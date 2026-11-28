"""Normalized, inspectable grade schema for Shared two-actor episodes."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


GRADE_SCHEMA = "paragui.grade/v1"


def _score(checks: list[dict[str, Any]]) -> float:
    if not checks:
        return 0.0
    weight_total = sum(float(c.get("weight", 1.0)) for c in checks)
    if weight_total <= 0:
        raise ValueError("A non-empty subcheck group needs positive total weight")
    return round(sum(float(c["score"]) * float(c.get("weight", 1.0)) for c in checks) / weight_total, 4)


def _normalize_checks(checks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for check in checks:
        item = dict(check)
        check_id = str(item.get("id", "")).strip()
        if not check_id or check_id in seen:
            raise ValueError("Every subcheck requires a unique non-empty id")
        seen.add(check_id)
        score = float(item.get("score", 1.0 if item.get("passed") is True else 0.0))
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"Subcheck {check_id} score must be in [0, 1]")
        passed = item.get("passed")
        if not isinstance(passed, bool):
            raise ValueError(f"Subcheck {check_id} requires boolean passed")
        weight = float(item.get("weight", 1.0))
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError(f"Subcheck {check_id} weight must be positive")
        normalized.append({
            "id": check_id,
            "passed": passed,
            "score": round(score, 4),
            "weight": weight,
            "required": bool(item.get("required", True)),
            "evidence": item.get("evidence"),
        })
    return normalized


def _actor_passes(score: float, threshold: float, checks: list[dict[str, Any]]) -> bool:
    required_checks_pass = all(c["passed"] for c in checks if c["required"])
    return score >= threshold and required_checks_pass


def make_grade(
    *,
    case_id: str,
    run_id: str,
    actor_a_checks: Iterable[dict[str, Any]],
    actor_b_checks: Iterable[dict[str, Any]],
    joint_checks: Iterable[dict[str, Any]],
    pass_threshold_a: float = 0.8,
    pass_threshold_b: float = 0.8,
    failure_reasons: Iterable[str] = (),
    run_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    subchecks = {
        "actor_a": _normalize_checks(actor_a_checks),
        "actor_b": _normalize_checks(actor_b_checks),
        "joint": _normalize_checks(joint_checks),
    }
    for threshold in (pass_threshold_a, pass_threshold_b):
        if not math.isfinite(float(threshold)) or not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("Actor pass thresholds must be in [0, 1]")
    score_a = _score(subchecks["actor_a"])
    score_b = _score(subchecks["actor_b"])
    pass_a = _actor_passes(score_a, float(pass_threshold_a), subchecks["actor_a"])
    pass_b = _actor_passes(score_b, float(pass_threshold_b), subchecks["actor_b"])
    joint_pass = pass_a and pass_b and all(c["passed"] for c in subchecks["joint"])
    failures = [str(x) for x in failure_reasons if str(x).strip()]
    for group in ("actor_a", "actor_b", "joint"):
        for check in subchecks[group]:
            if not check["passed"]:
                failures.append(f"{group}:{check['id']} failed")
    if not pass_a:
        failures.append("Actor A did not meet the individual pass criteria")
    if not pass_b:
        failures.append("Actor B did not meet the individual pass criteria")
    return {
        "schema_version": GRADE_SCHEMA,
        "case_id": case_id,
        "run_id": run_id,
        "graded_at_utc": datetime.now(timezone.utc).isoformat(),
        "score_a": score_a,
        "score_b": score_b,
        "mean_score": round((score_a + score_b) / 2.0, 4),
        "pass_thresholds": {"actor_a": float(pass_threshold_a), "actor_b": float(pass_threshold_b)},
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": joint_pass,
        "subchecks": subchecks,
        "failure_reasons": list(dict.fromkeys(failures)),
        "run_metadata": dict(run_metadata or {}),
    }


def validate_grade(grade: dict[str, Any]) -> None:
    required = {
        "schema_version", "case_id", "run_id", "score_a", "score_b", "mean_score",
        "pass_thresholds", "pass_a", "pass_b", "joint_pass", "subchecks", "failure_reasons", "run_metadata",
    }
    missing = required - set(grade)
    if missing:
        raise ValueError(f"grade.json is missing fields: {sorted(missing)}")
    if grade["schema_version"] != GRADE_SCHEMA:
        raise ValueError("Unsupported grade schema")
    for key in ("score_a", "score_b", "mean_score"):
        value = float(grade[key])
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{key} must be in [0, 1]")
    expected_mean = round((float(grade["score_a"]) + float(grade["score_b"])) / 2.0, 4)
    if round(float(grade["mean_score"]), 4) != expected_mean:
        raise ValueError("mean_score does not equal the mean of the two actor scores")
    subchecks = grade["subchecks"]
    if not isinstance(subchecks, dict) or set(("actor_a", "actor_b", "joint")) - set(subchecks):
        raise ValueError("subchecks must contain actor_a, actor_b and joint arrays")
    for group in ("actor_a", "actor_b", "joint"):
        _normalize_checks(subchecks[group])
    thresholds = grade["pass_thresholds"]
    expected_a = _actor_passes(float(grade["score_a"]), float(thresholds["actor_a"]), subchecks["actor_a"])
    expected_b = _actor_passes(float(grade["score_b"]), float(thresholds["actor_b"]), subchecks["actor_b"])
    expected_joint = expected_a and expected_b and all(c["passed"] for c in subchecks["joint"])
    if grade["pass_a"] is not expected_a or grade["pass_b"] is not expected_b:
        raise ValueError("Actor pass flags conflict with actor scores/subchecks")
    if grade["joint_pass"] is not expected_joint:
        raise ValueError("joint_pass must require both actors to pass and all joint checks to pass")
    if not isinstance(grade["failure_reasons"], list) or not isinstance(grade["run_metadata"], dict):
        raise ValueError("failure_reasons and run_metadata have invalid types")


def write_grade(path: str | Path, grade: dict[str, Any]) -> None:
    validate_grade(grade)
    Path(path).write_text(json.dumps(grade, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
