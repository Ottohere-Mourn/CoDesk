"""Hidden-state evaluator; instances are held by the orchestrator, never actors."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable, Protocol, Any


class Evaluator(Protocol):
    def evaluate(self, environment: Any) -> dict[str, object]: ...


class RequiredRowsEvaluator:
    def __init__(self, expected: Iterable[dict[str, str]] | None = None):
        self._expected = tuple(expected or (
            {"id": "G1", "actor": "gui", "value": "GUI_VALUE"},
            {"id": "C1", "actor": "cli", "value": "CLI_VALUE"},
        ))

    def evaluate(self, environment: Any) -> dict[str, object]:
        # `csv_path` is read only by this evaluator capability, never supplied to actors.
        csv_path = environment if isinstance(environment, Path) else environment.csv_path
        if csv_path is None:
            raise RuntimeError("environment has no CSV state path")
        with csv_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        expected = list(self._expected)
        present = [row for row in expected if row in rows]
        missing = [row for row in expected if row not in rows]
        duplicates = [row for row in expected if rows.count(row) > 1]
        success = not missing and not duplicates and len(rows) == len(expected)
        return {"success": success, "expected_rows": len(expected), "actual_rows": len(rows),
                "present": present, "missing": missing, "duplicates": duplicates,
                "final_rows": rows}


class OSWorldTaskEvaluator:
    """Adapter for OSWorld's isolated execution-based task evaluator."""
    def evaluate(self, environment: Any) -> dict[str, object]:
        score = float(environment.evaluate_osworld_task())
        return {"success": score >= 1.0, "osworld_score": score}
