"""CoDesk Clipboard 001 immutable task data and exact saved-state oracle."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from ..evaluator import GuestLibreOfficeBindingEvaluator


TASK_ID = "CODESK-TB-CLIPBOARD-001"
TASK_VERSION = "1.0.0-proposed"
WRITER_SOURCE = "REF-7319"
CALC_SOURCE = "BATCH-204"
WRITER_PATH = "/tmp/swcub_clipboard/writer.fodt"
CALC_PATH = "/tmp/swcub_clipboard/calc.fods"

INITIAL_STATE = {
    "writer_text": f"{WRITER_SOURCE}\n",
    "calc_cells": [[CALC_SOURCE], [""]],
}
FINAL_STATE = {
    "writer_text": f"{WRITER_SOURCE}\n{WRITER_SOURCE}",
    "calc_cells": [[CALC_SOURCE], [CALC_SOURCE]],
}


def writer_seed_odf(source: str = WRITER_SOURCE) -> bytes:
    """Flat ODF with one source paragraph and one empty paste destination."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:body><office:text><text:p>{source}</text:p><text:p/></office:text></office:body>
</office:document>'''.encode("utf-8")


def calc_seed_odf(source: str = CALC_SOURCE) -> bytes:
    """Flat ODF with source A1 and empty destination A2."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:body><office:spreadsheet><table:table table:name="Sheet1">
 <table:table-row><table:table-cell office:value-type="string"><text:p>{source}</text:p></table:table-cell></table:table-row>
 <table:table-row><table:table-cell/></table:table-row>
 </table:table></office:spreadsheet></office:body>
</office:document>'''.encode("utf-8")


@dataclass(frozen=True)
class ClipboardTaskEvaluator:
    """Private reader over saved Guest files; actor contexts get no read handle."""
    read_file: Callable[[str], str]
    required_actors: tuple[str, ...] = ("writer_actor", "calc_actor")
    writer_source: str = WRITER_SOURCE
    calc_source: str = CALC_SOURCE
    task_id: str = TASK_ID
    task_version: str = TASK_VERSION

    def evaluate(self, _environment: Any = None) -> dict[str, Any]:
        writer_text = GuestLibreOfficeBindingEvaluator._parse_writer(
            self.read_file(WRITER_PATH))
        calc_cells = GuestLibreOfficeBindingEvaluator._parse_calc(
            self.read_file(CALC_PATH))
        actual = {"writer_text": writer_text, "calc_cells": calc_cells}
        if not self.required_actors or not set(self.required_actors) <= {
                "writer_actor", "calc_actor"}:
            raise ValueError("required_actors must be a nonempty subset of task actors")
        initial = {"writer_text": f"{self.writer_source}\n",
                   "calc_cells": [[self.calc_source], [""]]}
        final = {"writer_text": f"{self.writer_source}\n{self.writer_source}",
                 "calc_cells": [[self.calc_source], [self.calc_source]]}
        expected = dict(initial)
        if "writer_actor" in self.required_actors:
            expected["writer_text"] = final["writer_text"]
        if "calc_actor" in self.required_actors:
            expected["calc_cells"] = final["calc_cells"]
        writer_ok = writer_text == expected["writer_text"]
        calc_ok = calc_cells == expected["calc_cells"]
        contamination = []
        if not writer_ok and writer_text != initial["writer_text"]:
            contamination.append({"artifact": "writer", "initial": initial["writer_text"],
                                  "expected": final["writer_text"], "actual": writer_text})
        if not calc_ok and calc_cells != initial["calc_cells"]:
            contamination.append({"artifact": "calc", "initial": initial["calc_cells"],
                                  "expected": final["calc_cells"], "actual": calc_cells})
        goals = {"writer_actor": writer_ok, "calc_actor": calc_ok}
        return {"task_id": self.task_id, "task_version": self.task_version,
                "success": all(goals[actor] for actor in self.required_actors),
                "actor_goal_success": {actor: goals[actor]
                                       for actor in self.required_actors},
                "required_actors": list(self.required_actors),
                "initial_state": initial, "expected_final_state": expected,
                "final_state": actual,
                "missing": {"writer": None if writer_ok else {
                    "expected": expected["writer_text"], "actual": writer_text},
                    "calc": None if calc_ok else {
                    "expected": expected["calc_cells"], "actual": calc_cells}},
                "contamination_events": contamination,
                "no_non_goal_contamination": not contamination}


def clipboard_setup_commands() -> list[list[str]]:
    """Guest-side commands to install the immutable ODF seeds (no shell interpolation)."""
    import base64
    return [
        ["python3", "-c",
         "from pathlib import Path; import base64; p=Path('/tmp/swcub_clipboard'); "
         "p.mkdir(parents=True,exist_ok=True); "
         f"Path('{WRITER_PATH}').write_bytes(base64.b64decode('{base64.b64encode(writer_seed_odf()).decode()}')); "
         f"Path('{CALC_PATH}').write_bytes(base64.b64decode('{base64.b64encode(calc_seed_odf()).decode()}'))"],
    ]


def readiness_state(read_file: Callable[[str], str], *,
                    writer_source: str = WRITER_SOURCE,
                    calc_source: str = CALC_SOURCE) -> dict[str, Any]:
    """Fail-closed initial-state gate before any actor receives control."""
    writer = GuestLibreOfficeBindingEvaluator._parse_writer(read_file(WRITER_PATH))
    calc = GuestLibreOfficeBindingEvaluator._parse_calc(read_file(CALC_PATH))
    actual = {"writer_text": writer, "calc_cells": calc}
    expected = {"writer_text": f"{writer_source}\n",
                "calc_cells": [[calc_source], [""]]}
    return {"ready": actual == expected, "expected": expected,
            "actual": actual, "identity": {"writer_path": WRITER_PATH,
                                           "calc_path": CALC_PATH,
                                           "calc_sheet": "Sheet1",
                                           "writer_destination": "second paragraph",
                                           "calc_destination": "A2"}}


def validate_topology(condition: str,
                      actor_bindings: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Fail closed unless backend/desktop/clipboard identity matches the condition."""
    required = {"writer_actor", "calc_actor"} if condition in {"ma_id", "ma_sd"} else None
    if condition in {"solo_writer", "solo_calc"}:
        actor = "writer_actor" if condition == "solo_writer" else "calc_actor"
        if set(actor_bindings) != {actor}:
            raise ValueError(f"{condition} must contain only {actor}")
        return {"valid": True, "condition": condition,
                "workspace_backend_shared": False,
                "desktop_shared": False, "clipboard_shared": False}
    if condition not in {"ma_id", "ma_sd"}:
        raise ValueError(f"unknown Clipboard 001 condition: {condition}")
    if set(actor_bindings) != required:
        raise ValueError(f"{condition} must bind both independent actors")
    fields = ("workspace_backend_id", "desktop_session_id", "clipboard_session_id")
    for actor, row in actor_bindings.items():
        if any(not isinstance(row.get(field), str) or not row[field] for field in fields):
            raise ValueError(f"{actor} needs explicit backend, desktop, and clipboard identities")
        digest = row.get("workspace_fixture_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"{actor} needs the digest of the initial task workspace fixture")
    same = {field: actor_bindings["writer_actor"][field]
            == actor_bindings["calc_actor"][field] for field in fields}
    fixture_matches = (actor_bindings["writer_actor"]["workspace_fixture_sha256"]
                       == actor_bindings["calc_actor"]["workspace_fixture_sha256"])
    valid = (fixture_matches and not same["desktop_session_id"]
             and not same["clipboard_session_id"] if condition == "ma_id"
             else fixture_matches and all(same.values()))
    if not valid:
        raise ValueError(f"{condition} topology violates task-state/control-plane contract: "
                         f"{same}, fixture_matches={fixture_matches}")
    return {"valid": True, "condition": condition,
            "workspace_backend_shared": same["workspace_backend_id"],
            "workspace_fixture_equivalent": fixture_matches,
            "desktop_shared": same["desktop_session_id"],
            "clipboard_shared": same["clipboard_session_id"]}


def task_specification() -> dict[str, Any]:
    """Machine-readable proposed task protocol; real Guest validation is separate."""
    return {"task_id": TASK_ID, "version": TASK_VERSION,
            "applications": ["LibreOffice Writer", "LibreOffice Calc"],
            "initial_state": INITIAL_STATE, "expected_final_state": FINAL_STATE,
            "actors": {
                "writer_actor": {"goal": "copy REF-7319 in Writer into the blank second paragraph",
                                 "source": "Writer paragraph 1", "destination": "Writer paragraph 2"},
                "calc_actor": {"goal": "copy BATCH-204 in Calc A1 into A2",
                               "source": "Calc Sheet1.A1", "destination": "Calc Sheet1.A2"}},
            "shared_resources": ["equivalent seeded task files", "desktop_control", "X11 CLIPBOARD selection"],
            "protocol": {"ma_sd_order": ["writer.copy", "calc.copy_paste_save",
                                          "writer.observe_or_recopy_paste_save"],
                         "forced_wrong_paste": False,
                         "recovery_control": "writer re-copies its stable source before paste"},
            "conditions": {"solo": "one actor; clean fixture and clipboard",
                           "ma_id": "same workspace fixture digest; independent local backends, desktops, and clipboards are allowed because goals do not require cross-Actor file visibility",
                           "ma_sd": "same backend, desktop, and clipboard identities"},
            "evaluation": "exact saved FODT/FODS state plus private event evidence",
            "status": "implementation_partial_real_guest_unvalidated"}
