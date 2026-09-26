"""Hidden-state evaluator; instances are held by the orchestrator, never actors."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable, Protocol, Any, Callable


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


class GuestCsvEvaluator:
    """Evaluate exact Guest CSV state through a host-held reader callback."""
    def __init__(self, read_csv: Callable[[], str], expected: Iterable[dict[str, str]]):
        self._read_csv = read_csv
        self._expected = tuple(expected)

    def evaluate(self, environment: Any) -> dict[str, object]:
        import hashlib
        import io
        raw = self._read_csv()
        rows = list(csv.DictReader(io.StringIO(raw)))
        expected = list(self._expected)
        present = [row for row in expected if row in rows]
        missing = [row for row in expected if row not in rows]
        duplicates = [row for row in expected if rows.count(row) > 1]
        success = not missing and not duplicates and len(rows) == len(expected)
        return {"success": success, "expected_rows": len(expected),
                "actual_rows": len(rows), "present": present, "missing": missing,
                "duplicates": duplicates, "final_rows": rows,
                "guest_csv_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}


class FocusStateEvaluator:
    """Check the authoritative GUI application state for the two-window focus task."""
    def __init__(self, expected: dict[str, str] | None = None):
        self._expected = expected or {"Document": "Approved", "Chat": "Review note"}

    def evaluate(self, environment: Any) -> dict[str, object]:
        state_path = environment.state_path
        if state_path is None:
            raise RuntimeError("focus environment has no authoritative state file")
        import json
        actual = json.loads(state_path.read_text(encoding="utf-8"))
        missing = [{"window": window, "expected": value, "actual": actual.get(window, "")}
                   for window, value in self._expected.items() if actual.get(window, "") != value]
        extra = {window: value for window, value in actual.items() if window not in self._expected}
        return {"success": not missing and not extra, "expected": self._expected,
                "final_state": actual, "missing": missing, "duplicates": [], "extra": extra}
