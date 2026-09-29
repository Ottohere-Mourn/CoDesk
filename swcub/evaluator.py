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


class GuestFocusEvaluator:
    """Check both terminal input streams using host-held Guest CLI reads."""
    def __init__(self, read_file: Callable[[str], str], expected: dict[str, str]):
        self._read_file = read_file
        self._expected = dict(expected)

    def evaluate(self, environment: Any) -> dict[str, object]:
        paths = {"Document": "/tmp/swcub_document.txt", "Chat": "/tmp/swcub_chat.txt"}
        actual = {window: self._read_file(path) for window, path in paths.items()}
        missing = {window: {"expected": value, "actual": actual[window]}
                   for window, value in self._expected.items() if actual.get(window) != value}
        return {"success": not missing, "expected": self._expected,
                "final_state": actual, "missing": missing,
                "no_cross_window_contamination": not missing}


class GuestLibreOfficeEvaluator:
    """Parse saved Flat ODF document/sheet state through a private Guest reader."""
    TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"

    def __init__(self, read_file: Callable[[str], str],
                 expected_writer_text: str, expected_calc: list[list[str]]):
        self._read_file = read_file
        self._expected_writer_text = expected_writer_text
        self._expected_calc = expected_calc

    def evaluate(self, environment: Any) -> dict[str, object]:
        import xml.etree.ElementTree as ET
        writer_xml = self._read_file("/tmp/swcub_office/document.fodt")
        calc_xml = self._read_file("/tmp/swcub_office/table.fods")
        writer_root = ET.fromstring(writer_xml)
        calc_root = ET.fromstring(calc_xml)
        writer_text = "\n".join(
            "".join(paragraph.itertext())
            for paragraph in writer_root.iter(f"{{{self.TEXT_NS}}}p")
        )
        calc_rows: list[list[str]] = []
        for row in calc_root.iter(f"{{{self.TABLE_NS}}}table-row"):
            cells: list[str] = []
            for cell in row.findall(f"{{{self.TABLE_NS}}}table-cell"):
                value = "\n".join(
                    "".join(paragraph.itertext())
                    for paragraph in cell.findall(f"{{{self.TEXT_NS}}}p")
                )
                repeat = int(cell.get(f"{{{self.TABLE_NS}}}number-columns-repeated", "1"))
                cells.extend([value] * min(repeat, 64))
            if cells:
                calc_rows.append(cells)
        missing: dict[str, object] = {}
        if writer_text != self._expected_writer_text:
            missing["writer_document"] = {"expected": self._expected_writer_text,
                                           "actual": writer_text}
        if calc_rows != self._expected_calc:
            missing["calc_sheet"] = {"expected": self._expected_calc,
                                     "actual": calc_rows}
        return {"success": not missing, "expected": {
                    "writer_text": self._expected_writer_text,
                    "calc_cells": self._expected_calc},
                "final_state": {"writer_text": writer_text, "calc_cells": calc_rows},
                "missing": missing,
                "no_cross_application_contamination": not missing}


class GuestLibreOfficeBindingEvaluator:
    """Grade exact saved ODF state for one or more isolated Guest desktops.

    The evaluator receives a host-held reader callback keyed by desktop binding;
    actor contexts never receive file-reader capabilities or expected values.
    ``expected_by_binding`` includes the non-goal application state, so edits to
    the other office file are detected as contamination as well as goal failure.
    """

    TEXT_NS = GuestLibreOfficeEvaluator.TEXT_NS
    TABLE_NS = GuestLibreOfficeEvaluator.TABLE_NS

    def __init__(self, read_file: Callable[[str, str], str],
                 expected_by_binding: dict[str, dict[str, Any]],
                 actor_goals: dict[str, dict[str, str]],
                 initial_state_by_binding: dict[str, dict[str, Any]]):
        self._read_file = read_file
        self._expected_by_binding = {key: dict(value)
                                     for key, value in expected_by_binding.items()}
        self._actor_goals = {key: dict(value) for key, value in actor_goals.items()}
        self._initial_state_by_binding = {key: dict(value)
                                          for key, value in initial_state_by_binding.items()}
        if set(self._initial_state_by_binding) != set(self._expected_by_binding):
            raise ValueError("initial and expected state must cover the same desktop bindings")

    @staticmethod
    def _parse_writer(raw: str) -> str:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(raw)
        return "\n".join("".join(paragraph.itertext())
                         for paragraph in root.iter(
                             f"{{{GuestLibreOfficeBindingEvaluator.TEXT_NS}}}p"))

    @staticmethod
    def _parse_calc(raw: str) -> list[list[str]]:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(raw)
        rows: list[list[str]] = []
        for row in root.iter(f"{{{GuestLibreOfficeBindingEvaluator.TABLE_NS}}}table-row"):
            cells: list[str] = []
            for cell in row.findall(f"{{{GuestLibreOfficeBindingEvaluator.TABLE_NS}}}table-cell"):
                value = "\n".join("".join(paragraph.itertext()) for paragraph in
                                   cell.findall(f"{{{GuestLibreOfficeBindingEvaluator.TEXT_NS}}}p"))
                repeat = int(cell.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
                                      "number-columns-repeated", "1"))
                cells.extend([value] * min(repeat, 64))
            if cells:
                rows.append(cells)
        return rows

    def evaluate(self, _environment: Any = None) -> dict[str, object]:
        actual_by_binding: dict[str, dict[str, Any]] = {}
        contamination: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for binding, expected in self._expected_by_binding.items():
            writer_text = self._parse_writer(
                self._read_file(binding, "/tmp/swcub_office/document.fodt"))
            calc_cells = self._parse_calc(
                self._read_file(binding, "/tmp/swcub_office/table.fods"))
            actual = {"writer_text": writer_text, "calc_cells": calc_cells}
            actual_by_binding[binding] = actual
            initial = self._initial_state_by_binding[binding]
            for field, value in (("writer_text", writer_text), ("calc_cells", calc_cells)):
                if value != expected[field]:
                    mismatch = {"desktop_binding": binding, "field": field,
                                "expected": expected[field], "actual": value}
                    missing.append(mismatch)
                    # A missed goal that leaves the original state intact is an
                    # objective failure, not contamination. Count a mutation as
                    # contamination only when the observed value differs from
                    # both the intended final value and the task's initial value.
                    if value != initial[field]:
                        contamination.append({**mismatch,
                                              "initial": initial[field],
                                              "classification": "unexpected_state_mutation"})

        actor_goal_success: dict[str, dict[str, Any]] = {}
        for actor_id, goal in self._actor_goals.items():
            binding = goal["desktop_binding"]
            field = goal["field"]
            expected = goal["expected"]
            actual = actual_by_binding[binding][field]
            actor_goal_success[actor_id] = {
                "desktop_binding": binding, "field": field,
                "expected": expected, "actual": actual, "success": actual == expected}
        return {"success": not missing,
                "actor_goal_success": actor_goal_success,
                "final_state_by_binding": actual_by_binding,
                "expected_state_by_binding": self._expected_by_binding,
                "initial_state_by_binding": self._initial_state_by_binding,
                "missing": missing,
                "contamination_events": contamination,
                "no_non_goal_application_contamination": not contamination,
                "no_unexpected_state_mutation": not contamination}


class GuestWebStateEvaluator:
    """Compare exact local web-app backend state through a private Guest reader."""
    def __init__(self, read_state: Callable[[], str], expected: dict[str, Any]):
        self._read_state = read_state
        self._expected = dict(expected)

    def evaluate(self, environment: Any) -> dict[str, object]:
        import json
        actual = json.loads(self._read_state())
        missing = {key: {"expected": value, "actual": actual.get(key)}
                   for key, value in self._expected.items() if actual.get(key) != value}
        return {"success": not missing, "expected": self._expected,
                "final_state": actual, "missing": missing}


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
