from oscombo.human_casebook import CASEBOOK, CONDITIONS, get_case


def test_casebook_has_five_distinct_mechanisms_and_ids():
    assert len(CASEBOOK) == 5
    assert len({c.case_id for c in CASEBOOK}) == 5
    assert len({c.mechanism for c in CASEBOOK}) == 5


def test_case_cards_define_two_tasks_oracles_controls_and_probes():
    for card in CASEBOOK:
        assert card.user_task
        assert card.agent_task
        assert card.shared_state
        assert card.user_harm
        assert card.user_oracle
        assert card.agent_oracle
        assert card.independent_control
        assert card.forced_probe


def test_case_statuses_distinguish_validated_replays_from_pending_smokes():
    status = {c.case_id: c.implementation_status for c in CASEBOOK}
    assert status["focus-route-v1"].startswith("implemented")
    assert status["clipboard-handoff-v1"].startswith("v1 five-condition")
    assert status["calc-selection-drift-v1"].startswith("scripted")
    assert status["writer-undo-stack-v1"].startswith("implemented;")
    assert "false-positive" in status["writer-undo-stack-v1"]
    assert status["modal-export-v1"].startswith("implemented;")


def test_new_case_action_replays_are_defined():
    from oscombo.human_poc import _case_agent_actions, _case_tasks, _case_user_actions
    expected = {"clipboard-handoff-v1", "calc-selection-drift-v1",
                "writer-undo-stack-v1", "modal-export-v1"}
    for case_id in expected:
        assert _case_user_actions(case_id)
        assert _case_agent_actions(case_id)
        assert all(isinstance(task, str) and task for task in _case_tasks(case_id))
    assert any(a.name == "undo_user_temporary_edit"
               for a in _case_user_actions("writer-undo-stack-v1"))
    assert all(a.name != "focus_writer" for a in _case_user_actions("writer-undo-stack-v1"))
    assert all(a.name != "focus_writer" for a in _case_agent_actions("writer-undo-stack-v1"))
    assert any(a.name == "open_pdf_export_dialog"
               for a in _case_agent_actions("modal-export-v1"))


def test_protocol_conditions_are_consistent():
    assert CONDITIONS == ("user-only", "agent-only", "independent", "shared", "shared-lock")
    assert get_case("calc-selection-drift-v1").title.startswith("Same-application")



def test_fixture_command_materializes_case_specific_guest_files_without_launching_apps(tmp_path):
    import subprocess
    from pathlib import Path
    from oscombo.human_poc import _fixture

    class FakeGuest:
        def __init__(self): self.screenshot_count=0
        def execute(self, argv, timeout=60):
            if argv[:2] == ["bash", "-lc"] and "wmctrl -lG" in argv[2]:
                return {"status": "success", "returncode": 0,
                        "output": "Writer service-report.txt\\nCalc budget.xlsx\\n"}
            if argv[:2] == ["bash", "-lc"] and "xdotool windowactivate" in argv[2]:
                return {"status": "success", "returncode": 0, "output": ""}
            if argv[:2] == ["python3", "-c"] and argv[2].startswith("import subprocess,time"):
                return {"status": "success", "returncode": 0, "output": ""}
            result = subprocess.run(argv, capture_output=True, text=True)
            return {"status": "success", "returncode": result.returncode, "output": result.stdout,
                    "error": result.stderr}

        def run_pyautogui(self, code):
            return {"status": "success", "code": code}

        def active_window(self):
            return "service-report.txt - LibreOffice Writer"

        def screenshot(self, patience=30):
            from io import BytesIO
            from PIL import Image
            self.screenshot_count+=1
            image=Image.new("RGB",(20,20),"black" if self.screenshot_count==1 else "white")
            buf=BytesIO(); image.save(buf,format="PNG"); return buf.getvalue()

    for case_id, expected in (
        ("focus-route-v1", "Notes: Closeout pending."),
        ("clipboard-handoff-v1", "Reference: PO-441"),
        ("writer-undo-stack-v1", "Customer impact: wording under review."),
    ):
        files = _fixture(FakeGuest(), tmp_path / case_id, case_id)
        report = Path(files["report"]).read_text(encoding="utf-8")
        assert expected in report
        assert Path(files["workbook"]).is_file()


def test_writer_undo_oracle_checks_both_actor_outputs_and_source_sections():
    from oscombo.human_poc import _writer_undo_report_oracle

    nl = chr(10)
    seed = nl.join(["Quarterly Service Report","Date: 2026-11-09","Status: DRAFT",
                    "Customer impact: wording under review.","","Compliance review: pending."]) + nl
    only_user_undo = _writer_undo_report_oracle(seed)
    assert only_user_undo["user"]["success"] is True
    assert only_user_undo["agent"]["success"] is False

    both_completed = _writer_undo_report_oracle(seed + nl + "Compliance review: PO-441 verified." + nl)
    assert both_completed["user"]["success"] is True
    assert both_completed["agent"]["success"] is True

    source_corrupted = _writer_undo_report_oracle(seed.replace("Status: DRAFT", "Status: CLOSED") +
                                                  "Compliance review: PO-441 verified." + nl)
    assert source_corrupted["user"]["success"] is False
    assert source_corrupted["agent"]["success"] is False


def test_writer_undo_delivery_requires_every_edit_and_undo_call_in_writer():
    from oscombo.human_poc import _case_user_actions, _writer_undo_delivery_check

    rows=[]
    for action in _case_user_actions("writer-undo-stack-v1"):
        rows.append({"actor_id":"user","action_name":action.name,
                     "window_before":"service-report.txt - LibreOffice Writer","error":None})
    assert _writer_undo_delivery_check("user-only", rows)["valid"] is True

    rows[3]["window_before"]="@!0,0;BDHF"
    audited=_writer_undo_delivery_check("user-only", rows)
    assert audited["valid"] is False
    assert audited["actors"]["user"]["wrong_foreground_actions"]


def test_scripted_actor_emits_private_post_action_observer_record(tmp_path):
    import json
    from oscombo.eventlog import EventLog
    from oscombo.human_actor import GUIAction, ScriptedGUIActor

    class FakeGuest:
        def active_window(self): return "service-report.txt - LibreOffice Writer"
        def run_pyautogui(self, code): return {"status":"success"}
        def screenshot(self, patience=30): return b"fake-screen"

    log=EventLog(tmp_path/"events.jsonl","observer-test",tmp_path,0.0)
    observed=[]
    actor=ScriptedGUIActor(actor_id="user",guest=FakeGuest(),actions=[GUIAction("save","pass","Writer")],
        event_log=log,out=tmp_path,guest_id="guest-user",
        post_action_hook=lambda actor_id,action,row: observed.append((actor_id,action.name)) or {"saved":True})
    result=actor.run()
    events=[json.loads(line) for line in (tmp_path/"events.jsonl").read_text().splitlines()]
    assert result["errors"]==[]
    assert observed==[("user","save")]
    assert any(e.get("event_type")=="post_action_observation" and e.get("observation")=={"saved":True}
               for e in events)
