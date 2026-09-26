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
