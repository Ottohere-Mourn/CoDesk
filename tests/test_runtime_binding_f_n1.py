from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from swcub.production_v1 import evaluate_oracle, read_manifest
from swcub.runtime_bindings_v1 import (
    F_N1RuntimeObserver, _setup_f_n1, build_runtime_binding_registry,
)
from swcub.runtime_v1 import build_runtime_registry


class Guest:
    def __init__(self, slot, plan):
        self.slot = slot
        self.fixtures = {row["guest_path"]: Path(row["host_path"]).read_bytes()
                         for row in plan["fixture_assets"]}
        self.current = dict(self.fixtures)
        self.launched = [{"app": row["app"], "target": row["guest_path"]}
                         for row in plan["fixture_assets"]]
        self.episode = SimpleNamespace(
            _active_window_title=lambda: "Writer - CoDesk doc",
            refresh_observation=lambda _source: {"screenshot": b"offline-test-only"},
            log=SimpleNamespace(record=lambda *args, **kwargs: None))


class Backend:
    def __init__(self):
        self.events = []

    def _command(self, guest, argv):
        if argv[0] == "cat":
            return guest.current[argv[1]].decode("utf-8")
        if argv[0] == "bash":
            return "doc-a - LibreOffice Writer\ndoc-b - LibreOffice Writer"
        raise AssertionError(argv)

    def notify_observer_event(self, event):
        self.events.append(dict(event))


def _set_target_paragraph(raw: bytes, initial: str, expected: str) -> bytes:
    text_ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    root = ET.fromstring(raw)
    found = False
    for node in root.iter(f"{{{text_ns}}}p"):
        if "".join(node.itertext()) == initial and not found:
            node.text = expected
            found = True
    assert found
    return ET.tostring(root, encoding="utf-8")


def _case():
    suite = Path("benchmarks/codesk_v1")
    record = next(row for row in read_manifest(suite / "manifest.jsonl")
                  if row["workflow_id"] == "F-N1")
    plan = build_runtime_registry().compile(record, suite)
    return record, plan


def test_f_n1_generated_instance_is_concretely_bound_and_gates_setup():
    record, plan = _case()
    binding = plan["runtime_execution_binding"]
    assert binding["missing_components"] == []
    assert set(binding["required_observers"]) == {
        "foreground_window_document_identity_v1", "writer_document_content_v1"}
    registry = build_runtime_binding_registry()
    assert all(callable(registry["F-N1"][key]) for key in
               ("setup", "initial_verifier", "evaluator", "event_gate"))
    guest = Guest("shared", plan)
    backend = Backend()
    _setup_f_n1(plan, guest, backend)
    assert registry["F-N1"]["initial_verifier"]([guest], plan, backend) is True


def test_f_n1_observer_scores_shared_and_independent_guest_states_and_reset():
    record, plan = _case()
    observer = F_N1RuntimeObserver()
    backend = Backend()
    guests = [Guest("actor_A", plan), Guest("actor_B", plan)]

    # MA-ID: each actor changes only its own document on its equivalent Guest.
    for guest, actor in zip(guests, record["actor_goals"]):
        doc = "doc-a" if actor["actor_id"] == "A" else "doc-b"
        path = next(x["guest_path"] for x in plan["fixture_assets"]
                    if Path(x["guest_path"]).name == f"{doc}.fodt")
        guest.current[path] = _set_target_paragraph(
            guest.current[path], actor["initial_value"], actor["expected_value"])
    actual = observer(guests, plan, backend)
    assert evaluate_oracle(record, actual, ("A", "B"))["joint_success"] is True

    # Reset target restores the exact initial fixture bytes and observer gate.
    for guest in guests:
        guest.current = dict(guest.fixtures)
    assert observer.verify_initial(guests, plan, backend) is True

    # MA-SD: the two independent edits coexist in one Guest; contamination fails.
    shared = Guest("shared", plan)
    for actor in record["actor_goals"]:
        doc = "doc-a" if actor["actor_id"] == "A" else "doc-b"
        path = next(x["guest_path"] for x in plan["fixture_assets"]
                    if Path(x["guest_path"]).name == f"{doc}.fodt")
        shared.current[path] = _set_target_paragraph(
            shared.current[path], actor["initial_value"], actor["expected_value"])
    actual = observer([shared], plan, backend)
    assert evaluate_oracle(record, actual, ("A", "B"))["joint_success"] is True
    doc_a = next(x["guest_path"] for x in plan["fixture_assets"]
                 if Path(x["guest_path"]).name == "doc-a.fodt")
    shared.current[doc_a] = shared.current[doc_a].replace(
        record["actor_goals"][0]["expected_value"].encode(), b"UNINTENDED EDIT", 1)
    actual = observer([shared], plan, backend)
    assert evaluate_oracle(record, actual, ("A", "B"))["joint_success"] is False
