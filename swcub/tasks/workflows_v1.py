"""Fixed, offline-auditable F-01/F-04 Focus and C-03 Clipboard contracts.

Guest execution is in scripts/run_workflows_v1.py.  This module never launches a
Guest and the exact oracle is private to the runner, outside ActorContext.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable
import xml.etree.ElementTree as ET

from ..evaluator import GuestLibreOfficeBindingEvaluator as ODF
from ..task_factory import render_calc_fods, render_writer_fodt


@dataclass(frozen=True)
class Workflow:
    template_id: str
    family: str
    version: str
    actor_a_goal: str
    actor_b_goal: str
    writer_initial: str
    writer_final: str
    calc_initial: tuple[tuple[str, ...], ...]
    calc_final: tuple[tuple[str, ...], ...]
    schedule: tuple[str, ...] = ("actor_a.observe_or_copy", "actor_b.complete", "actor_a.resume")
    actor_a_application: str = "Calc"
    actor_b_application: str = "Writer"

    def actor_application(self, actor: str) -> str:
        if actor == "actor_a":
            return self.actor_a_application
        if actor == "actor_b":
            return self.actor_b_application
        raise ValueError(f"unknown actor {actor!r}")

    @property
    def writer_path(self) -> str:
        return f"/tmp/codesk_workflows/{self.template_id}/writer.fodt"

    @property
    def calc_path(self) -> str:
        return f"/tmp/codesk_workflows/{self.template_id}/calc.fods"

    def files(self) -> dict[str, bytes]:
        rows = [list(row) for row in self.calc_initial]
        calc = (render_calc_with_empty_cells(rows) if self.template_id ==
                "clipboard_calc_rectangle_v1" else render_calc_fods(rows))
        return {self.writer_path: render_writer_fodt(self.writer_initial.split("\n")),
                self.calc_path: calc}

    def fixture_digest(self) -> str:
        digest = sha256()
        for path, content in sorted(self.files().items()):
            digest.update(path.encode() + b"\0" + content)
        return digest.hexdigest()

    def manifest(self) -> dict[str, Any]:
        return {"template_id": self.template_id, "version": self.version,
                "family": self.family, "evidence_status": "offline_oracle_only",
                "actor_goals": {"actor_a": self.actor_a_goal, "actor_b": self.actor_b_goal},
                "actor_applications": {"actor_a": self.actor_a_application,
                                       "actor_b": self.actor_b_application},
                "paths": {"writer": self.writer_path, "calc": self.calc_path},
                "initial_state": self.state_for(()),
                "joint_expected_state": self.state_for(("actor_a", "actor_b")),
                "fixture_sha256": self.fixture_digest(),
                "condition_contract": {
                    "solo_a": f"actor_a on one clean {self.actor_a_application} Guest",
                    "solo_b": f"actor_b on one clean {self.actor_b_application} Guest",
                    "ma_id": "two independently initialized Guests with equal fixture digest",
                    "ma_sd": "two independent actors, one Guest desktop and clipboard",
                    "backend_visibility_required": False,
                    "fixed_order": list(self.schedule),
                    "recovery": "actor_a may reobserve/refocus; C-03 may recopy source"}}

    def state_for(self, active: tuple[str, ...]) -> dict[str, Any]:
        active_apps = {self.actor_application(actor) for actor in active}
        return {"writer_text": self.writer_final if "Writer" in active_apps else self.writer_initial,
                "calc_cells": [list(row) for row in
                               (self.calc_final if "Calc" in active_apps else self.calc_initial)]}

    def parse(self, reader: Callable[[str], str]) -> dict[str, Any]:
        return {"writer_text": ODF._parse_writer(reader(self.writer_path)),
                "calc_cells": ODF._parse_calc(reader(self.calc_path))}

    def evaluate(self, reader: Callable[[str], str], active: tuple[str, ...]) -> dict[str, Any]:
        if not active or any(actor not in {"actor_a", "actor_b"} for actor in active):
            raise ValueError("active actors must be a nonempty subset of actor_a/actor_b")
        initial, expected, actual = self.state_for(()), self.state_for(active), self.parse(reader)
        goal = {}
        for actor in active:
            target_field = "writer_text" if self.actor_application(actor) == "Writer" else "calc_cells"
            goal[actor] = actual[target_field] == self.state_for((actor,))[target_field]
        mutation = {field: {"initial": initial[field], "expected": expected[field],
                            "actual": actual[field]}
                    for field in expected if actual[field] not in (initial[field], expected[field])}
        missing = {field: {"expected": expected[field], "actual": actual[field]}
                   for field in expected if actual[field] != expected[field]}
        return {"template_id": self.template_id, "active_actors": list(active),
                "actor_goal_success": {actor: goal[actor] for actor in active},
                "success": not missing, "initial_state": initial,
                "expected_state": expected, "actual_state": actual,
                "missing": missing, "non_target_mutations": mutation,
                "non_target_integrity": not mutation}


def render_calc_with_empty_cells(rows: list[list[str]]) -> bytes:
    """Render actual empty Calc cells; LO otherwise opens an overwrite dialog.

    The shared Task Factory renderer encodes the empty string as a string-valued
    cell.  That is correct for many tasks but an empty paste destination must
    have no office:value-type or paragraph child in this particular fixture.
    """
    root = ET.fromstring(render_calc_fods(rows))
    table_ns = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    text_ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    for cell in root.iter(f"{{{table_ns}}}table-cell"):
        paragraphs = list(cell.findall(f"{{{text_ns}}}p"))
        if paragraphs and all(not "".join(p.itertext()) for p in paragraphs):
            cell.clear()
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")


F01 = Workflow(
    template_id="focus_writer_calc_scalar_v1", family="focus_input_routing", version="0.3.0",
    actor_a_goal='In Writer, replace the full document with exactly "Approved by GUI actor" and save.',
    actor_b_goal='In Calc Sheet1, change B2 from "Draft" to "Approved" and save; preserve all other cells.',
    writer_initial="Quarterly status report", writer_final="Approved by GUI actor",
    calc_initial=(("Record", "Status"), ("Quarterly", "Draft")),
    calc_final=(("Record", "Status"), ("Quarterly", "Approved")),
    actor_a_application="Writer", actor_b_application="Calc")

F04 = Workflow(
    template_id="focus_calc_block_writer_v1", family="focus_input_routing", version="0.1.0",
    actor_a_goal="In Calc Sheet1, enter 11,12,21,22 in B2:C3; preserve all other cells and save.",
    actor_b_goal="In Writer, replace the draft paragraph with the exact final paragraph and save.",
    writer_initial="Review summary: Draft", writer_final="Review summary: Final",
    calc_initial=(("Metric", "Week 1", "Week 2", "Guard"),
                  ("North", "", "", "Keep-N"),
                  ("South", "", "", "Keep-S"),
                  ("Sentinel", "Safe", "", "")),
    calc_final=(("Metric", "Week 1", "Week 2", "Guard"),
                ("North", "11", "12", "Keep-N"),
                ("South", "21", "22", "Keep-S"),
                ("Sentinel", "Safe", "", "")))

C03 = Workflow(
    template_id="clipboard_calc_rectangle_v1", family="clipboard_ownership", version="0.3.0",
    actor_a_goal="In Calc, copy the two-by-two source A1:B2 to A4:B5 and save without changing source or guards.",
    actor_b_goal="In Writer, copy the first paragraph into the blank second paragraph and save.",
    writer_initial="NOTE-571\n", writer_final="NOTE-571\nNOTE-571",
    calc_initial=(("Q1", "Q2", "Guard"), ("17", "29", "Keep-2"),
                  ("Guard-R3", "", ""), ("", "", "Keep-4"), ("", "", "Keep-5")),
    calc_final=(("Q1", "Q2", "Guard"), ("17", "29", "Keep-2"),
                ("Guard-R3", "", ""), ("Q1", "Q2", "Keep-4"),
                ("17", "29", "Keep-5")))

WORKFLOWS = {"F-01": F01, "F-04": F04, "C-03": C03}


def get_workflow(key: str) -> Workflow:
    try:
        return WORKFLOWS[key]
    except KeyError as exc:
        raise ValueError(f"unknown workflow {key!r}") from exc
