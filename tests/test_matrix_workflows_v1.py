from __future__ import annotations

import json

import pytest

from swcub.tasks.matrix_workflows_v1 import (
    A_ROUTE_GOALS, C_BROWSER_URL, C_TABLE, S_TEXT_A, S_TEXT_B, TASKS,
    U_A_INITIAL, U_B_FINAL, WorkflowContract, a_server_source, c_server_source,
    evaluate, fixture_files, fixture_hash, parse_writer_table, task_manifest,
)


def test_all_five_contracts_and_fixtures_are_deterministic():
    assert TASKS == ("F-N1", "C-N1", "A-N1", "S-N1", "U-N1")
    for task in TASKS:
        assert task_manifest(task)["condition_contract"]["hidden_state_private"]
        assert fixture_hash(task) == fixture_hash(task)
        assert fixture_files(task)


def test_server_sources_compile_and_route_goals_are_separate():
    compile(c_server_source(), "cn1_server.py", "exec")
    compile(a_server_source(), "an1_server.py", "exec")
    assert A_ROUTE_GOALS["route-a"] != A_ROUTE_GOALS["route-b"]


def test_focus_evaluator_is_path_bound_and_detects_wrong_window_contamination():
    good = evaluate("F-N1", {"documents": {
        "doc-a": "A-FINAL-731", "doc-b": "B-FINAL-204"}})
    assert good["joint_success"]
    wrong = evaluate("F-N1", {"documents": {
        "doc-a": "A-DRAFT-731", "doc-b": "A-FINAL-731"}})
    assert not wrong["joint_success"]
    solo = evaluate("F-N1", {"documents": {
        "doc-a": "A-FINAL-731", "doc-b": "B-DRAFT-204"}}, ("actor_a",))
    assert solo["joint_success"]
    contaminated_solo = evaluate("F-N1", {"documents": {
        "doc-a": "A-FINAL-731", "doc-b": "A-FINAL-731"}}, ("actor_a",))
    assert not contaminated_solo["non_target_integrity"]["actor_a"]


def test_rich_clipboard_oracle_requires_table_structure_and_browser_goal():
    good = evaluate("C-N1", {"writer": {"table": [list(r) for r in C_TABLE],
                                      "guard": "KEEP GUARD"},
                              "browser": {"submission": {"url": C_BROWSER_URL},
                                          "revision": 1}})
    assert good["joint_success"]
    flattened = evaluate("C-N1", {"writer": {"table": None, "guard": "KEEP GUARD"},
                                  "browser": {"submission": {"url": C_BROWSER_URL},
                                              "revision": 1}})
    assert not flattened["joint_success"]
    assert not parse_writer_table(
        '<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">'
        '<office:body><office:text><text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        'plain text</text:p></office:text></office:body></office:document>')["table"]


def test_route_context_oracle_distinguishes_route_and_revision():
    good = evaluate("A-N1", {"routes": {
        "route-a": {"value": "A-READY-531", "revision": 1},
        "route-b": {"value": "B-APPROVE-824", "revision": 1}}})
    assert good["joint_success"]
    stale = evaluate("A-N1", {"routes": {
        "route-a": {"value": "", "revision": 0},
        "route-b": {"value": "A-READY-531", "revision": 2}}})
    assert not stale["joint_success"]
    untouched_peer = evaluate("A-N1", {"routes": {
        "route-a": {"value": "A-READY-531", "revision": 1},
        "route-b": {"value": "B-APPROVE-824", "revision": 1}}}, ("actor_a",))
    assert not untouched_peer["non_target_integrity"]["actor_a"]


def test_writer_range_oracle_requires_both_spans_and_guard():
    actual = {"writer": {"document_text": f"{S_TEXT_A} | {S_TEXT_B}",
                         "bold_spans": [{"text": S_TEXT_A, "bold": True},
                                        {"text": S_TEXT_B, "bold": True}],
                         "guard": "KEEP GUARD"}}
    assert evaluate("S-N1", actual)["joint_success"]
    actual["writer"]["bold_spans"] = [
        {"text": S_TEXT_A, "bold": False}, {"text": S_TEXT_B, "bold": True}]
    assert not evaluate("S-N1", actual)["joint_success"]
    only_a = {"writer": {"document_text": f"{S_TEXT_A} | {S_TEXT_B}",
                          "bold_spans": [{"text": S_TEXT_A, "bold": True}],
                          "guard": "KEEP GUARD"}}
    assert evaluate("S-N1", only_a, ("actor_a",))["joint_success"]
    only_b_wrong = evaluate("S-N1", {"writer": {
        "document_text": f"{S_TEXT_A} | {S_TEXT_B}",
        "bold_spans": [{"text": S_TEXT_A, "bold": True}],
        "guard": "KEEP GUARD"}}, ("actor_b",))
    assert not only_b_wrong["joint_success"]


def test_writer_undo_oracle_checks_both_goals_and_guard():
    good = evaluate("U-N1", {"writer": {
        "paragraphs": [U_A_INITIAL, U_B_FINAL, "KEEP GUARD"]}})
    assert good["joint_success"]
    lost_peer_edit = evaluate("U-N1", {"writer": {
        "paragraphs": [U_A_INITIAL, "B-LINE: keep", "KEEP GUARD"]}})
    assert not lost_peer_edit["joint_success"]
    assert evaluate("U-N1", {"writer": {
        "paragraphs": [U_A_INITIAL, "B-LINE: keep", "KEEP GUARD"]}},
        ("actor_a",))["joint_success"]
    solo_b = evaluate("U-N1", {"writer": {
        "paragraphs": [U_A_INITIAL, U_B_FINAL, "KEEP GUARD"]}}, ("actor_b",))
    assert solo_b["joint_success"]
    assert not evaluate("U-N1", {"writer": {
        "paragraphs": ["A-LINE: temporary", U_B_FINAL, "KEEP GUARD"]}},
        ("actor_b",))["joint_success"]
