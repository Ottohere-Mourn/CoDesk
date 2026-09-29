"""Deterministic family/template/instance/run construction for CoDesk V1.

This module is offline-only: it renders seed artifacts and evaluators but never
starts a desktop, Docker container, model, or application.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Any, Callable
import xml.etree.ElementTree as ET

from .evaluator import GuestLibreOfficeBindingEvaluator


FACTORY_SCHEMA_VERSION = 1
OFFICE_FAMILY_ID = "CODESK-TA-OFFICE"
OFFICE_TEMPLATE_ID = "writer_calc_independent_edits_v1"
CLIPBOARD_FAMILY_ID = "CODESK-TB-CLIPBOARD"
CLIPBOARD_TEMPLATE_ID = "clipboard_transfer_v1"
MODAL_FAMILY_ID = "CODESK-TC-MODAL"
MODAL_TEMPLATE_ID = "writer_calc_save_dialog_v1"
CONTEXT_FAMILY_ID = "CODESK-TE-APP-CONTEXT"
CONTEXT_TEMPLATE_ID = "chromium_two_tab_context_v1"
TEMPLATE_VERSION = "1.0.0"

_TEXT_NS = GuestLibreOfficeBindingEvaluator.TEXT_NS
_TABLE_NS = GuestLibreOfficeBindingEvaluator.TABLE_NS
_OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_SCENARIOS = (
    ("quarterly_report", "Quarterly forecast", "Approved"),
    ("supplier_review", "Supplier onboarding", "Reviewed"),
    ("inventory_audit", "Inventory audit", "Reconciled"),
    ("travel_request", "Travel request", "Authorized"),
    ("release_check", "Release readiness", "Complete"),
    ("incident_summary", "Incident summary", "Resolved"),
    ("budget_revision", "Budget revision", "Accepted"),
    ("meeting_minutes", "Meeting minutes", "Confirmed"),
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def render_writer_fodt(paragraphs: list[str]) -> bytes:
    root = ET.Element(f"{{{_OFFICE_NS}}}document", {
        f"{{{_OFFICE_NS}}}version": "1.2",
        f"{{{_OFFICE_NS}}}mimetype": "application/vnd.oasis.opendocument.text"})
    body = ET.SubElement(root, f"{{{_OFFICE_NS}}}body")
    text_body = ET.SubElement(body, f"{{{_OFFICE_NS}}}text")
    for value in paragraphs:
        para = ET.SubElement(text_body, f"{{{_TEXT_NS}}}p")
        para.text = value
    return _xml_bytes(root)


def render_calc_fods(rows: list[list[str]], sheet_name: str = "Sheet1") -> bytes:
    root = ET.Element(f"{{{_OFFICE_NS}}}document", {
        f"{{{_OFFICE_NS}}}version": "1.2",
        f"{{{_OFFICE_NS}}}mimetype": "application/vnd.oasis.opendocument.spreadsheet"})
    body = ET.SubElement(root, f"{{{_OFFICE_NS}}}body")
    spreadsheet = ET.SubElement(body, f"{{{_OFFICE_NS}}}spreadsheet")
    table = ET.SubElement(spreadsheet, f"{{{_TABLE_NS}}}table",
                          {f"{{{_TABLE_NS}}}name": sheet_name})
    for row_values in rows:
        row = ET.SubElement(table, f"{{{_TABLE_NS}}}table-row")
        for value in row_values:
            cell = ET.SubElement(row, f"{{{_TABLE_NS}}}table-cell",
                                 {f"{{{_OFFICE_NS}}}value-type": "string"})
            para = ET.SubElement(cell, f"{{{_TEXT_NS}}}p")
            para.text = value
    return _xml_bytes(root)


def _xml_bytes(root: ET.Element) -> bytes:
    ET.register_namespace("office", _OFFICE_NS)
    ET.register_namespace("text", _TEXT_NS)
    ET.register_namespace("table", _TABLE_NS)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="utf-8", short_empty_elements=True)


def office_file_bytes(initial_state: dict[str, Any]) -> dict[str, bytes]:
    """Shared setup renderer used by the family factory and legacy seed helpers."""
    writer_text = initial_state["writer_document"]["text"]
    cells = initial_state["calc_sheet"]["cells"]
    writer_path = initial_state["writer_document"]["path"]
    calc_path = initial_state["calc_sheet"]["path"]
    return {writer_path: render_writer_fodt([writer_text]),
            calc_path: render_calc_fods(cells)}


def generate_office_instance(seed: int) -> dict[str, Any]:
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    scenario = random.Random(seed).choice(_SCENARIOS)
    scenario_id, subject, final_status = scenario
    serial = seed + 1
    case = f"Case {serial:04d}: {subject}"
    initial_writer = f"{case} — Draft"
    final_writer = f"{case} — {final_status}"
    initial_calc = [["Case", "Status"], [case, "Draft"]]
    final_calc = [["Case", "Status"], [case, final_status]]
    initial = {"writer_document": {"path": "/tmp/swcub_office/document.fodt",
                                    "paragraphs": [initial_writer], "text": initial_writer},
               "calc_sheet": {"path": "/tmp/swcub_office/table.fods",
                              "sheet": "Sheet1", "cells": initial_calc}}
    expected = {"writer_text": final_writer, "calc_cells": final_calc}
    files = office_file_bytes(initial)
    task_id = f"{OFFICE_FAMILY_ID}-{seed:08d}"
    instance_id = f"office-wc-v1-seed-{seed:08d}"
    actor_goals = {
        "writer_actor": {"resource": "writer_document",
                         "operation": "replace the document body and save",
                         "initial": initial_writer, "expected": final_writer},
        "calc_actor": {"resource": "calc_sheet.B2",
                       "operation": "change the Status cell for this case and save",
                       "row_key": case, "initial": "Draft", "expected": final_status},
    }
    semantic = {"template_id": OFFICE_TEMPLATE_ID, "template_version": TEMPLATE_VERSION,
                "scenario_id": scenario_id, "initial_state": initial,
                "actor_goals": actor_goals, "expected_state": expected}
    content_hash = sha256_bytes(canonical_json(semantic))
    manifest: dict[str, Any] = {
        "schema_version": FACTORY_SCHEMA_VERSION,
        "family_id": OFFICE_FAMILY_ID,
        "template_id": OFFICE_TEMPLATE_ID,
        "template_version": TEMPLATE_VERSION,
        "task_id": task_id,
        "instance_id": instance_id,
        "seed": seed,
        "scenario_id": scenario_id,
        "content_fingerprint": content_hash,
        "environment": {"adapter": "OSWorldSharedEpisode",
                         "release": "osworld-v2.1",
                         "guest_application": "LibreOffice Writer + Calc",
                         "shared_resources": ["desktop focus", "keyboard", "pointer",
                                              "Writer document", "Calc spreadsheet"]},
        "actors": {"writer_actor": "gui", "calc_actor": "gui"},
        "actor_goals": actor_goals,
        "initial_state": initial,
        "expected_state": expected,
        "non_target_integrity": {
            "writer_actor": {"calc_sheet": initial_calc},
            "calc_actor": {"writer_document": initial_writer,
                            "calc_cells_except_B2": {"A1": "Case", "B1": "Status",
                                                     "A2": case}},
            "joint": {"writer_document_exact": final_writer,
                      "calc_sheet_exact": final_calc}},
        "initial_files": [{"guest_path": guest_path,
                           "relative_path": f"initial/{PathLike.name(guest_path)}",
                           "sha256": sha256_bytes(data), "size_bytes": len(data),
                           "content_base64": _b64(data)}
                          for guest_path, data in sorted(files.items())],
        "schedule": [
            {"actor_id": "writer_actor", "trigger": "episode_started"},
            {"actor_id": "calc_actor", "trigger": {"after_actor_turn": {
                "actor_id": "writer_actor", "count": 1}}},
            {"actor_id": "writer_actor", "trigger": {"after_actor_turn": {
                "actor_id": "calc_actor", "count": 1}}}],
        "evaluator": {"type": "GeneratedOfficeExactEvaluator",
                      "oracle": "exact saved FODT/FODS parse",
                      "checks": ["writer final document", "all Calc cells",
                                 "per-actor goals", "non-target integrity"]},
        "joint_feasibility": {"feasible": True,
                              "proof": "Actor write sets are disjoint: Writer document body and Calc B2; both preserve the Calc row key and all other cells."},
        "template_validation_status": "offline_candidate; real template evidence inherited only from seed-0 anchor",
        "run_configuration_fields_excluded": ["condition", "repeat", "window_geometry",
                                               "actor_budget", "schedule_policy"],
        "task_content_sha256": content_hash,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json(manifest))
    return manifest


@dataclass(frozen=True)
class GeneratedOfficeExactEvaluator:
    """Reusable objective evaluator for generated Writer/Calc instances."""
    manifest: dict[str, Any]
    read_file: Callable[[str], str]
    required_actors: tuple[str, ...] = ("writer_actor", "calc_actor")

    def evaluate(self, _environment: Any = None) -> dict[str, Any]:
        if (not self.required_actors
                or not set(self.required_actors) <= {"writer_actor", "calc_actor"}):
            raise ValueError("required_actors must be a nonempty subset of office actors")
        initial = self.manifest["initial_state"]
        expected = self.manifest["expected_state"]
        writer_path = initial["writer_document"]["path"]
        calc_path = initial["calc_sheet"]["path"]
        writer_actual = GuestLibreOfficeBindingEvaluator._parse_writer(
            self.read_file(writer_path))
        calc_actual = GuestLibreOfficeBindingEvaluator._parse_calc(
            self.read_file(calc_path))
        actual = {"writer_text": writer_actual, "calc_cells": calc_actual}
        actor_results = {
            "writer_actor": writer_actual == expected["writer_text"],
            "calc_actor": calc_actual == expected["calc_cells"],
        }
        non_target_mutations = []
        goal_state_errors = []
        if "writer_actor" not in self.required_actors and writer_actual != initial[
                "writer_document"]["text"]:
            non_target_mutations.append({"resource": "writer_document",
                                         "expected_unchanged": initial["writer_document"]["text"],
                                         "actual": writer_actual})
        elif ("writer_actor" in self.required_actors
              and writer_actual not in {initial["writer_document"]["text"],
                                        expected["writer_text"]}):
            goal_state_errors.append({"resource": "writer_document",
                                      "expected": expected["writer_text"],
                                      "actual": writer_actual})
        initial_cells = initial["calc_sheet"]["cells"]
        if "calc_actor" not in self.required_actors and calc_actual != initial_cells:
            non_target_mutations.append({"resource": "calc_sheet",
                                         "expected_unchanged": initial_cells,
                                         "actual": calc_actual})
        elif "calc_actor" in self.required_actors:
            for row_index, row in enumerate(expected["calc_cells"]):
                for col_index, value in enumerate(row):
                    got = calc_actual[row_index][col_index] if (
                        row_index < len(calc_actual) and col_index < len(calc_actual[row_index])) else None
                    initial_value = initial_cells[row_index][col_index]
                    if got != value and got != initial_value:
                        row = {"resource": "calc_sheet",
                               "cell": f"{chr(65 + col_index)}{row_index + 1}",
                               "expected": value, "initial": initial_value, "actual": got}
                        if row_index == 1 and col_index == 1:
                            goal_state_errors.append(row)
                        else:
                            non_target_mutations.append(row)
        return {"task_id": self.manifest["task_id"],
                "instance_id": self.manifest["instance_id"],
                "success": all(actor_results[actor] for actor in self.required_actors)
                           and not non_target_mutations,
                "required_actors": list(self.required_actors),
                "actor_goal_success": {actor: actor_results[actor]
                                       for actor in self.required_actors},
                "final_state": actual, "expected_state": expected,
                "goal_state_errors": goal_state_errors,
                "non_target_mutations": non_target_mutations,
                "no_non_target_contamination": not non_target_mutations}


def validate_office_candidate(manifest: dict[str, Any]) -> dict[str, Any]:
    """Offline test of initial state, Solo A/B, joint oracle, and contamination negative control."""
    import base64
    from .evaluator import GuestLibreOfficeBindingEvaluator as Parser
    initial_files = {item["guest_path"]: base64.b64decode(item["content_base64"], validate=True)
                     for item in manifest["initial_files"]}
    initial = manifest["initial_state"]
    expected = manifest["expected_state"]
    writer_path, calc_path = (initial["writer_document"]["path"],
                              initial["calc_sheet"]["path"])
    initial_parsed = {"writer_text": Parser._parse_writer(initial_files[writer_path].decode()),
                      "calc_cells": Parser._parse_calc(initial_files[calc_path].decode())}
    initial_matches = (initial_parsed["writer_text"] == initial["writer_document"]["text"]
                       and initial_parsed["calc_cells"] == initial["calc_sheet"]["cells"])

    def score(files: dict[str, bytes], actors: tuple[str, ...]) -> dict[str, Any]:
        return GeneratedOfficeExactEvaluator(
            manifest, lambda path: files[path].decode("utf-8"), actors).evaluate()

    writer_only = dict(initial_files)
    writer_only[writer_path] = render_writer_fodt([expected["writer_text"]])
    solo_writer = score(writer_only, ("writer_actor",))
    calc_only = dict(initial_files)
    calc_only[calc_path] = render_calc_fods(expected["calc_cells"])
    solo_calc = score(calc_only, ("calc_actor",))
    joint = {writer_path: render_writer_fodt([expected["writer_text"]]),
             calc_path: render_calc_fods(expected["calc_cells"])}
    joint_result = score(joint, ("writer_actor", "calc_actor"))
    contaminated = dict(writer_only)
    bad_cells = [list(row) for row in initial["calc_sheet"]["cells"]]
    bad_cells[1][1] = "UNAUTHORIZED"
    contaminated[calc_path] = render_calc_fods(bad_cells)
    contamination_result = score(contaminated, ("writer_actor",))
    checks = {"initial_files_parse_exactly": initial_matches,
              "solo_writer_oracle": solo_writer["success"],
              "solo_calc_oracle": solo_calc["success"],
              "joint_oracle": joint_result["success"],
              "non_target_contamination_detected": (
                  not contamination_result["success"]
                  and bool(contamination_result["non_target_mutations"])),
              "joint_feasible_disjoint_write_sets": bool(
                  manifest["joint_feasibility"]["feasible"])}
    return {"task_id": manifest["task_id"], "instance_id": manifest["instance_id"],
            "success": all(checks.values()), "checks": checks,
            "contamination_evidence": contamination_result["non_target_mutations"]}


def generate_clipboard_instance(seed: int) -> dict[str, Any]:
    """Generate through the same schema, retaining the task's unvalidated status."""
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    from .tasks.clipboard_v1 import (CALC_PATH, TASK_ID, TASK_VERSION,
                                     writer_seed_odf, calc_seed_odf)
    # Content is deterministic per seed but the desktop observer/clipboard task
    # remains unvalidated. This does not imply its X11 mechanism is observable.
    writer_token = f"REF-{seed + 7319:06d}"
    calc_token = f"BATCH-{seed + 204:06d}"
    task_id = f"{CLIPBOARD_FAMILY_ID}-{seed:08d}"
    initial = {"writer_source": writer_token, "writer_destination": "",
               "calc_source": calc_token, "calc_destination": ""}
    expected = {"writer_destination": writer_token, "calc_destination": calc_token}
    semantic = {"template_id": CLIPBOARD_TEMPLATE_ID, "template_version": TASK_VERSION,
                "initial_state": initial, "expected_state": expected}
    files = {"/tmp/swcub_clipboard/writer.fodt": writer_seed_odf(writer_token),
             CALC_PATH: calc_seed_odf(calc_token)}
    manifest: dict[str, Any] = {
        "schema_version": FACTORY_SCHEMA_VERSION,
        "family_id": CLIPBOARD_FAMILY_ID,
        "template_id": CLIPBOARD_TEMPLATE_ID,
        "template_version": TASK_VERSION,
        "task_id": task_id,
        "instance_id": f"clipboard-v1-seed-{seed:08d}", "seed": seed,
        "content_fingerprint": sha256_bytes(canonical_json(semantic)),
        "environment": {"adapter": "OSWorldSharedEpisode",
                         "release": "osworld-v2.1",
                         "guest_application": "LibreOffice Writer + Calc",
                         "shared_resources": ["workspace backend", "desktop focus",
                                              "X11 CLIPBOARD selection"]},
        "actors": {"writer_actor": "gui", "calc_actor": "gui"},
        "actor_goals": {"writer_actor": {"operation": "copy source into Writer destination",
                                             "source": writer_token,
                                             "destination": writer_token},
                        "calc_actor": {"operation": "copy source into Calc A2",
                                        "source": calc_token,
                                        "destination": calc_token}},
        "initial_state": initial, "expected_state": expected,
        "non_target_integrity": {"writer_source_preserved": writer_token,
                                 "calc_source_preserved": calc_token,
                                 "distinct_destinations": True},
        "initial_files": [{"guest_path": path,
                            "relative_path": f"initial/{PathLike.name(path)}",
                            "sha256": sha256_bytes(data), "size_bytes": len(data),
                            "content_base64": _b64(data)}
                           for path, data in sorted(files.items())],
        "evaluator": {"type": "ClipboardTaskEvaluator", "oracle": "saved ODF exact state",
                      "checks": ["both destination tokens", "source preservation",
                                 "cross-document contamination"]},
        "schedule": [
            {"actor_id": "writer_actor", "trigger": "episode_started"},
            {"actor_id": "calc_actor", "trigger": {"after_actor_turn": {
                "actor_id": "writer_actor", "count": 1}}},
            {"actor_id": "writer_actor", "trigger": {"after_actor_turn": {
                "actor_id": "calc_actor", "count": 1}}}],
        "joint_feasibility": {"feasible": True,
                              "proof": "Distinct source payloads and distinct saved destinations."},
        "validation_status": "design_only_until_observer_and_guest_gates_pass",
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json(manifest))
    return manifest


def verify_manifest(manifest: dict[str, Any]) -> bool:
    candidate = dict(manifest)
    recorded = candidate.pop("manifest_sha256", None)
    if not isinstance(recorded, str) or sha256_bytes(canonical_json(candidate)) != recorded:
        return False
    template = TEMPLATE_REGISTRY.get(manifest.get("template_id"))
    if template is None:
        return False
    regenerated = template.generate(manifest["seed"])
    return regenerated == manifest


def verify_initial_files(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in manifest.get("initial_files", []):
        try:
            import base64
            data = base64.b64decode(item["content_base64"], validate=True)
            valid = sha256_bytes(data) == item["sha256"] and len(data) == item["size_bytes"]
        except Exception:
            valid = False
        rows.append({"path": item.get("guest_path"), "valid": valid,
                     "sha256": item.get("sha256")})
    return {"success": bool(rows) and all(row["valid"] for row in rows), "files": rows}


def initialize_instance(manifest: dict[str, Any],
                        reset_environment: Callable[[str, int], Any],
                        write_guest_file: Callable[[Any, str, bytes], None],
                        read_guest_file: Callable[[Any, str], bytes]) -> Any:
    """Common reset-and-seed hook; it never starts an environment itself."""
    if not verify_manifest(manifest):
        raise ValueError("refusing to initialize an invalid or non-reproducible manifest")
    integrity = verify_initial_files(manifest)
    if not integrity["success"]:
        raise ValueError(f"initial file hash verification failed: {integrity}")
    import base64
    environment = reset_environment(manifest["instance_id"], manifest["seed"])
    for item in manifest["initial_files"]:
        expected = base64.b64decode(item["content_base64"], validate=True)
        write_guest_file(environment, item["guest_path"], expected)
        actual = read_guest_file(environment, item["guest_path"])
        if not isinstance(actual, bytes) or actual != expected:
            raise ValueError(f"Guest did not persist the declared initial bytes: {item['guest_path']}")
    return environment


def write_instance(manifest: dict[str, Any], root: Path) -> Path:
    """Write one immutable instance directory; refuses to overwrite any path."""
    import base64
    directory = root / manifest["instance_id"]
    directory.mkdir(parents=True, exist_ok=False)
    for item in manifest["initial_files"]:
        relative = Path(item["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("initial file path must be relative and traversal-free")
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = base64.b64decode(item["content_base64"], validate=True)
        if sha256_bytes(data) != item["sha256"]:
            raise ValueError(f"initial file digest mismatch: {relative}")
        target.write_bytes(data)
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return directory


def verify_instance_directory(directory: Path) -> dict[str, Any]:
    """Verify saved manifest regeneration and every on-disk initial artifact."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return {"success": False, "manifest_valid": False,
                "error": "manifest.json is missing", "files": []}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = []
    import base64
    for item in manifest.get("initial_files", []):
        relative = Path(item.get("relative_path", ""))
        if relative.is_absolute() or ".." in relative.parts:
            files.append({"path": str(relative), "valid": False,
                          "error": "unsafe relative path"})
            continue
        path = directory / relative
        try:
            actual = path.read_bytes()
            embedded = base64.b64decode(item["content_base64"], validate=True)
            valid = (sha256_bytes(actual) == item["sha256"]
                     and actual == embedded
                     and len(actual) == item["size_bytes"])
            files.append({"path": str(relative), "valid": valid,
                          "sha256": sha256_bytes(actual)})
        except (OSError, KeyError, ValueError) as exc:
            files.append({"path": str(relative), "valid": False,
                          "error": f"{type(exc).__name__}: {exc}"})
    manifest_valid = verify_manifest(manifest)
    return {"success": manifest_valid and bool(files) and all(row["valid"] for row in files),
            "manifest_valid": manifest_valid, "files": files}


@dataclass(frozen=True)
class RunConfig:
    """Execution repetition/layout belongs to a run, never an instance/task ID."""
    instance_id: str
    condition: str
    repeat: int
    window_geometry: dict[str, tuple[int, int, int, int]] | None = None
    actor_budget: int = 20
    solo_actor_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.instance_id):
            raise ValueError("invalid instance_id")
        if self.condition not in {"solo", "ma_id", "ma_sd"}:
            raise ValueError("invalid experiment condition")
        if type(self.repeat) is not int or self.repeat < 1:
            raise ValueError("repeat must be a positive integer")
        if type(self.actor_budget) is not int or self.actor_budget < 1:
            raise ValueError("actor_budget must be positive")
        if self.condition == "solo" and self.solo_actor_id not in {
                "writer_actor", "calc_actor"}:
            raise ValueError("Solo run must identify its one active actor")
        if self.condition != "solo" and self.solo_actor_id is not None:
            raise ValueError("solo_actor_id is only valid for Solo runs")
        geometry = self.window_geometry or {}
        for actor, rect in geometry.items():
            if not isinstance(actor, str) or len(rect) != 4 or any(type(x) is not int for x in rect):
                raise ValueError("window geometry must map actors to integer x/y/width/height")
        core = {"schema_version": 1, "instance_id": self.instance_id,
                "condition": self.condition, "repeat": self.repeat,
                "window_geometry": geometry, "actor_budget": self.actor_budget,
                "solo_actor_id": self.solo_actor_id}
        core["run_id"] = f"run-{sha256_bytes(canonical_json(core))[:16]}"
        return core


class PathLike:
    """Small POSIX path basename helper for Guest paths without pathlib semantics."""
    @staticmethod
    def name(path: str) -> str:
        return path.rstrip("/").rsplit("/", 1)[-1]


def _b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")


@dataclass(frozen=True)
class TaskTemplate:
    family_id: str
    template_id: str
    template_version: str
    evidence_status: str
    generate: Callable[[int], dict[str, Any]]


TEMPLATE_REGISTRY = {
    OFFICE_TEMPLATE_ID: TaskTemplate(OFFICE_FAMILY_ID, OFFICE_TEMPLATE_ID,
                                     TEMPLATE_VERSION,
                                     "anchored_on_existing_real_office_task",
                                     generate_office_instance),
    CLIPBOARD_TEMPLATE_ID: TaskTemplate(CLIPBOARD_FAMILY_ID, CLIPBOARD_TEMPLATE_ID,
                                        "1.0.0-proposed",
                                        "design_only_until_guest_observer_validation",
                                        generate_clipboard_instance),
}

# Keep application-specific manifests on the same deterministic Task Factory API.
# Their code-level evaluators and Guest execution gates are explicitly separate.
from .tasks.prototypes_v1 import (generate_browser_context_instance,
                                  generate_modal_instance)

TEMPLATE_REGISTRY.update({
    MODAL_TEMPLATE_ID: TaskTemplate(MODAL_FAMILY_ID, MODAL_TEMPLATE_ID,
                                    "1.0.0-prototype",
                                    "offline_prototype_guest_unverified",
                                    generate_modal_instance),
    CONTEXT_TEMPLATE_ID: TaskTemplate(CONTEXT_FAMILY_ID, CONTEXT_TEMPLATE_ID,
                                      "1.0.0-prototype",
                                      "offline_prototype_guest_unverified",
                                      generate_browser_context_instance),
})


def get_template(template_id: str) -> TaskTemplate:
    try:
        return TEMPLATE_REGISTRY[template_id]
    except KeyError as exc:
        raise ValueError(f"unknown registered task template: {template_id}") from exc
