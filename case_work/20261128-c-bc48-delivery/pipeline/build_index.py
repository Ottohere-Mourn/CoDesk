"""Build a machine-readable Case/run/grade index from a batch archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


INDEX_SCHEMA = "paragui.case-index/v1"


def build_index(root: str | Path) -> dict[str, Any]:
    batch = Path(root)
    cases: list[dict[str, Any]] = []
    cases_root = batch / "cases"
    trajectories_root = batch / "trajectories"
    for case_dir in sorted(p for p in cases_root.iterdir() if p.is_dir()) if cases_root.is_dir() else []:
        config_path = case_dir / "case.json"
        if not config_path.is_file():
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        runs: list[dict[str, Any]] = []
        trajectory_case = trajectories_root / case_dir.name
        if trajectory_case.is_dir():
            for run_dir in sorted(p for p in trajectory_case.iterdir() if p.is_dir()):
                grade_path = run_dir / "grade.json"
                grade = json.loads(grade_path.read_text(encoding="utf-8")) if grade_path.is_file() else None
                runs.append({
                    "run_id": run_dir.name,
                    "trajectory_path": run_dir.relative_to(batch).as_posix(),
                    "grade_path": grade_path.relative_to(batch).as_posix() if grade_path.is_file() else None,
                    "score_a": grade.get("score_a") if grade else None,
                    "score_b": grade.get("score_b") if grade else None,
                    "mean_score": grade.get("mean_score") if grade else None,
                    "pass_a": grade.get("pass_a") if grade else None,
                    "pass_b": grade.get("pass_b") if grade else None,
                    "joint_pass": grade.get("joint_pass") if grade else None,
                })
        cases.append({
            "case_id": config.get("case_id", case_dir.name),
            "title": config.get("title"),
            "track": config.get("track"),
            "case_config": config_path.relative_to(batch).as_posix(),
            "source_paths": config.get("source_paths", []),
            "prompt_paths": config.get("prompt_paths", []),
            "oracle_path": config.get("oracle_path"),
            "runs": runs,
        })
    return {
        "schema_version": INDEX_SCHEMA,
        "batch_id": batch.name,
        "case_count": len(cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    index = build_index(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "case_count": index["case_count"], "run_count": sum(len(c["runs"]) for c in index["cases"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
