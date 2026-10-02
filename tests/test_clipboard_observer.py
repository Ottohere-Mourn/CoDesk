from __future__ import annotations

import hashlib

import pytest

from swcub.clipboard_observer import (ClipboardEventTracker, ClipboardSnapshot,
                                      classify_paste, payload_digest,
                                      validate_sampler_non_perturbation,
                                      has_intervening_clipboard_overwrite)
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.actors import ScriptedClipboardActor
from swcub.environment import ActorContext
from swcub.tasks.clipboard_v1 import (CALC_PATH, FINAL_STATE, INITIAL_STATE,
                                      WRITER_PATH, ClipboardTaskEvaluator,
                                      calc_seed_odf, readiness_state, writer_seed_odf,
                                      validate_topology)
from swcub.evaluator import GuestLibreOfficeBindingEvaluator


def snap(*, owner="0x10", digest=None, generation=0, focus="0x20"):
    return {"owner_xid": owner, "payload_sha256": digest, "payload_bytes": 8,
            "targets": ["TARGETS", "UTF8_STRING"], "generation": generation,
            "active_window_xid": focus, "active_window_title": "Writer",
            "focused_xid": focus, "focused_title": "Writer", "status": "ok"}


def test_logical_actor_requires_post_copy_digest_match_not_x_owner_alone():
    expected = payload_digest(b"REF-7319")
    tracker = ClipboardEventTracker()
    tracker.record(snap(digest=payload_digest(b"old")), phase="before_action")
    owner_only = tracker.record(snap(owner="0x99", digest=payload_digest(b"old")),
                                actor_id="writer_actor",
                                source_action={"op": "key", "key": "ctrl+c"},
                                expected_payload_sha256=expected,
                                phase="after_action")
    assert owner_only["selection_owner_changed"] is True
    assert owner_only["logical_actor"] is None

    tracker.record(snap(owner="0x99", digest=payload_digest(b"old")),
                   phase="before_action")
    copied = tracker.record(snap(owner="0xaa", digest=expected, generation=1),
                            actor_id="writer_actor",
                            source_action={"op": "key", "key": "ctrl+c"},
                            expected_payload_sha256=expected,
                            phase="after_action")
    assert copied["logical_actor"] == "writer_actor"
    assert copied["owner_xid"] == "0xaa"
    assert copied["logical_actor_attribution"] == "copy_action_bracket"


@pytest.mark.parametrize(("digest_ok", "target", "expected"), [
    (False, True, "clipboard_overwrite_supported"),
    (True, False, "focus_misroute_supported"),
    (False, False, "mixed"),
    (True, None, "unknown"),
    (True, True, "no_mechanism_evidence"),
])
def test_paste_attribution_separates_mechanism_and_final_outcome(digest_ok, target, expected):
    result = classify_paste(expected_payload_sha256="a" * 64,
                            observed_payload_sha256=("a" if digest_ok else "b") * 64,
                            target_matches=target, final_content_matches=False,
                            overwrite_between_copy_and_paste=(True if not digest_ok else None))
    assert result["mechanism_evidence"] == expected
    assert result["task_failure"] is True
    assert result["recovered_or_unaffected_final_state"] is False


def test_recopy_recovery_is_outcome_separate_from_exposure():
    failed = classify_paste(expected_payload_sha256="a" * 64,
                            observed_payload_sha256="b" * 64,
                            target_matches=True, final_content_matches=False,
                            overwrite_between_copy_and_paste=True)
    recovered = classify_paste(expected_payload_sha256="a" * 64,
                               observed_payload_sha256="a" * 64,
                               target_matches=True, final_content_matches=True)
    assert failed["mechanism_evidence"] == "clipboard_overwrite_supported"
    assert recovered["mechanism_evidence"] == "no_mechanism_evidence"
    assert recovered["task_failure"] is False
    assert recovered["recovered_or_unaffected_final_state"] is True


def test_overwrite_attribution_requires_other_actor_bracket_between_copy_and_paste():
    evidence = [{"seq": 4, "actor": "clipboard_observer", "details": {
        "phase": "after_action", "source_actor": "calc_actor", "logical_actor": "calc_actor",
        "payload_changed": True, "payload_sha256": "b" * 64}}]
    assert has_intervening_clipboard_overwrite(evidence, recipient_actor="writer_actor",
        copy_seq=2, paste_seq=6, expected_payload_sha256="a" * 64) is True
    assert has_intervening_clipboard_overwrite(evidence, recipient_actor="calc_actor",
        copy_seq=2, paste_seq=6, expected_payload_sha256="a" * 64) is False
    assert has_intervening_clipboard_overwrite(evidence, recipient_actor="writer_actor",
        copy_seq=5, paste_seq=6, expected_payload_sha256="a" * 64) is False


def test_paired_observer_state_check_is_explicitly_only_state_equivalence():
    result = validate_sampler_non_perturbation(snap(digest="a" * 64),
                                               snap(digest="a" * 64))
    assert result["stable"] is True
    assert "still requires a real control" in result["note"]
    changed = validate_sampler_non_perturbation(snap(digest="a" * 64),
                                                snap(digest="b" * 64))
    assert changed["stable"] is False


class FakeSampler:
    def __init__(self):
        self.n = 0

    def sample(self):
        self.n += 1
        return snap(digest=hashlib.sha256(b"same").hexdigest())


class Desktop:
    is_environment_used = False

    def reset(self, task_config=None, seed=None):
        return {"screenshot": b"real-looking", "instruction": "type text"}

    def step(self, action, pause=2):
        return {"screenshot": b"after"}, 0.0, False, {}

    def close(self):
        pass


def test_private_observer_logs_actor_source_but_not_in_observation():
    episode = OSWorldSharedEpisode(Desktop(), clipboard_sampler=FakeSampler(),
                                   require_clipboard_observer=True)
    observed = episode.reset({"id": "offline-contract", "instruction": "type text"})
    assert "clipboard" not in str(observed).lower()
    episode.act("writer_actor", "gui", {"op": "key", "key": "ctrl+c"})
    assert "clipboard" not in str(observed).lower()
    samples = [event for event in episode.log.events
               if event.action == "clipboard.sample"]
    assert len(samples) == 2
    assert all(event.actor == "clipboard_observer" for event in samples)
    assert all(event.details["source_actor"] == "writer_actor" for event in samples)
    assert samples[-1].details["logical_actor"] is None  # no actor source digest was declared


def test_clipboard_task_odf_seeds_read_back_to_exact_initial_state():
    writer = writer_seed_odf().decode()
    calc = calc_seed_odf().decode()
    read = {WRITER_PATH: writer, CALC_PATH: calc}
    parsed = {"writer_text": GuestLibreOfficeBindingEvaluator._parse_writer(writer),
              "calc_cells": GuestLibreOfficeBindingEvaluator._parse_calc(calc)}
    assert parsed == INITIAL_STATE
    assert readiness_state(lambda path: read[path])["ready"] is True


def test_clipboard_task_evaluator_checks_both_saved_destinations_and_contamination():
    writer_final = writer_seed_odf().decode().replace(
        "<text:p>INSERT COPIED VALUE</text:p>", "<text:p>REF-7319</text:p>")
    calc_final = calc_seed_odf().decode().replace(
        "<table:table-cell/></table:table-row>",
        "<table:table-cell office:value-type=\"string\"><text:p>BATCH-204</text:p>"
        "</table:table-cell></table:table-row>")
    files = {WRITER_PATH: writer_final, CALC_PATH: calc_final}
    success = ClipboardTaskEvaluator(lambda path: files[path]).evaluate()
    assert success["success"] is True
    assert success["actor_goal_success"] == {"writer_actor": True, "calc_actor": True}
    assert success["no_non_goal_contamination"] is True

    files[CALC_PATH] = calc_final.replace("BATCH-204", "REF-7319")
    contaminated = ClipboardTaskEvaluator(lambda path: files[path]).evaluate()
    assert contaminated["success"] is False
    assert contaminated["actor_goal_success"]["calc_actor"] is False
    assert contaminated["contamination_events"][0]["artifact"] == "calc"


def test_clipboard_solo_evaluator_requires_only_assigned_goal_and_preserves_other_file():
    writer_final = writer_seed_odf().decode().replace(
        "<text:p>INSERT COPIED VALUE</text:p>", "<text:p>REF-7319</text:p>")
    files = {WRITER_PATH: writer_final, CALC_PATH: calc_seed_odf().decode()}
    writer_solo = ClipboardTaskEvaluator(lambda path: files[path],
                                         required_actors=("writer_actor",)).evaluate()
    assert writer_solo["success"] is True
    assert writer_solo["actor_goal_success"] == {"writer_actor": True}
    assert writer_solo["final_state"]["calc_cells"] == INITIAL_STATE["calc_cells"]

    files[WRITER_PATH] = writer_seed_odf().decode()
    calc_final = calc_seed_odf().decode().replace(
        "<table:table-cell/></table:table-row>",
        "<table:table-cell office:value-type=\"string\"><text:p>BATCH-204</text:p>"
        "</table:table-cell></table:table-row>")
    files[CALC_PATH] = calc_final
    calc_solo = ClipboardTaskEvaluator(lambda path: files[path],
                                       required_actors=("calc_actor",)).evaluate()
    assert calc_solo["success"] is True
    assert calc_solo["actor_goal_success"] == {"calc_actor": True}


def test_scripted_joint_schedule_uses_normal_copy_paste_and_has_recopy_control():
    episode = OSWorldSharedEpisode(Desktop())
    episode.reset({"id": "clipboard-script-contract", "instruction": "copy values"})
    writer = ScriptedClipboardActor("writer_actor", shared_desktop=True,
                                    recopy_on_resume=True)
    calc = ScriptedClipboardActor("calc_actor", shared_desktop=True)
    a_ctx, b_ctx = ActorContext("writer_actor", episode, "gui"), ActorContext(
        "calc_actor", episode, "gui")
    assert writer.run_step(a_ctx) is False  # A copies, then yields normally.
    assert calc.run_step(b_ctx) is True  # B copies/pastes its own Calc value.
    assert writer.run_step(a_ctx) is True  # A re-copies and pastes to Writer.
    actions = [e.details["source_action"] for e in episode.log.events
               if e.kind == "gui" and e.action == "osworld.step"]
    assert actions.count({"op": "key", "key": "ctrl+c"}) == 3
    assert actions.count({"op": "key", "key": "shift+end"}) == 2
    assert actions.count({"op": "key", "key": "ctrl+shift+right"}) == 0
    assert actions.count({"op": "key", "key": "ctrl+v"}) == 2
    assert {"op": "key", "key": "alt+tab"} in actions


def test_clipboard_topology_allows_equivalent_local_workspace_in_ma_id():
    digest = hashlib.sha256(b"identical initial Writer+Calc fixture").hexdigest()
    distinct = {"writer_actor": {"workspace_backend_id": "backend-A",
                                 "desktop_session_id": "desktop-A",
                                 "clipboard_session_id": "clipboard-A",
                                 "workspace_fixture_sha256": digest},
                "calc_actor": {"workspace_backend_id": "backend-B",
                               "desktop_session_id": "desktop-B",
                               "clipboard_session_id": "clipboard-B",
                               "workspace_fixture_sha256": digest}}
    result = validate_topology("ma_id", distinct)
    assert result["valid"] is True
    assert result["workspace_backend_shared"] is False
    assert result["workspace_fixture_equivalent"] is True
    distinct["calc_actor"]["workspace_fixture_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="fixture_matches=False"):
        validate_topology("ma_id", distinct)


def test_clipboard_topology_ma_sd_shares_backend_desktop_clipboard_and_fixture():
    digest = hashlib.sha256(b"identical initial Writer+Calc fixture").hexdigest()
    shared = {"writer_actor": {"workspace_backend_id": "backend",
                               "desktop_session_id": "desktop",
                               "clipboard_session_id": "clipboard",
                               "workspace_fixture_sha256": digest},
              "calc_actor": {"workspace_backend_id": "backend",
                             "desktop_session_id": "desktop",
                             "clipboard_session_id": "clipboard",
                             "workspace_fixture_sha256": digest}}
    assert validate_topology("ma_sd", shared)["valid"] is True


def test_guest_probe_treats_ownerless_clipboard_as_valid_empty_state(monkeypatch, tmp_path):
    from scripts import guest_clipboard_probe
    owners = iter((None, None))
    monkeypatch.setattr(guest_clipboard_probe, "x11_owner", lambda: next(owners))
    def no_selection_commands(argv, timeout=1.5):
        if argv[0] == "xdotool":
            raise FileNotFoundError("xdotool is not installed in this unit-test host")
        raise AssertionError(f"empty clipboard should not invoke {argv!r}")
    monkeypatch.setattr(guest_clipboard_probe, "run", no_selection_commands)
    result = guest_clipboard_probe.sample(tmp_path / "clipboard-state.json")
    assert result["status"] == "ok"
    assert result["owner_xid"] is None
    assert result["payload_sha256"] is None
    assert result["targets"] == []
    assert result["payload_read"] is False
    assert result["generation"] == 0
