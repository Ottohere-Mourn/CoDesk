"""Offline controls for C-02/F-02 fixed oracles and scripted GUI intent."""
from copy import deepcopy
import xml.etree.ElementTree as ET

from swcub.tasks.browser_writer_workflows_v1 import (
    A_URL, B_URL, CASE, COMMENT, DECISION, C02, F02,
    OFFICE_NS, TEXT_NS, XLINK_NS, ScriptedBrowserWriterActor,
)


def writer_with_link(href=A_URL, text="Reference link", guard="Guard paragraph"):
    root = ET.fromstring(C02.files()[C02.writer_path])
    body = root.find(f".//{{{OFFICE_NS}}}body/{{{OFFICE_NS}}}text")
    first, second = body.findall(f"{{{TEXT_NS}}}p")
    first.text = None
    link = ET.SubElement(first, f"{{{TEXT_NS}}}a", {f"{{{XLINK_NS}}}href": href})
    link.text = text
    second.text = guard
    return ET.tostring(root, encoding="unicode")


def writer_with_comment(comment=COMMENT, anchor="Review anchor"):
    root = ET.fromstring(F02.files()[F02.writer_path])
    body = root.find(f".//{{{OFFICE_NS}}}body/{{{OFFICE_NS}}}text")
    first = body.find(f"{{{TEXT_NS}}}p")
    first.text = None
    name = "annotation-1"
    annotation = ET.SubElement(first, f"{{{OFFICE_NS}}}annotation",
                               {f"{{{OFFICE_NS}}}name": name})
    text = ET.SubElement(annotation, f"{{{TEXT_NS}}}p")
    text.text = comment
    annotation.tail = anchor
    ET.SubElement(first, f"{{{OFFICE_NS}}}annotation-end",
                  {f"{{{OFFICE_NS}}}name": name})
    return ET.tostring(root, encoding="unicode")


def test_deterministic_fixtures_and_server_source():
    for workflow in (C02, F02):
        assert workflow.fixture_sha256() == workflow.fixture_sha256()
        assert workflow.writer_initial_ok(
            workflow.parse_writer(workflow.files()[workflow.writer_path].decode()))
        compile(workflow.server_source(), f"{workflow.key}-server.py", "exec")
        assert workflow.browser_initial() == {"submission": {}, "revision": 0}


def test_c02_checks_visible_label_href_and_guard_separately():
    good = C02.parse_writer(writer_with_link())
    assert C02.writer_goal_ok(good)
    assert not C02.writer_goal_ok(C02.parse_writer(writer_with_link(B_URL)))
    assert not C02.writer_goal_ok(C02.parse_writer(writer_with_link(text="wrong")))
    assert not C02.writer_goal_ok(C02.parse_writer(writer_with_link(guard="polluted")))


def test_f02_checks_comment_body_anchor_name_and_text_integrity():
    good = F02.parse_writer(writer_with_comment())
    assert F02.writer_goal_ok(good)
    assert not F02.writer_goal_ok(F02.parse_writer(writer_with_comment(comment="wrong")))
    assert not F02.writer_goal_ok(F02.parse_writer(writer_with_comment(anchor="wrong")))
    root = ET.fromstring(writer_with_comment())
    end = root.find(f".//{{{OFFICE_NS}}}annotation-end")
    end.set(f"{{{OFFICE_NS}}}name", "wrong-name")
    assert not F02.writer_goal_ok(F02.parse_writer(ET.tostring(root, encoding="unicode")))


def test_solo_ma_id_and_ma_sd_oracles():
    for workflow, final_writer in ((C02, writer_with_link()), (F02, writer_with_comment())):
        seed = workflow.files()[workflow.writer_path].decode()
        initial = workflow.browser_initial()
        done = {"submission": workflow.browser_expected(), "revision": 1}
        solo_a = workflow.evaluate(condition="solo_a", writer_xml={"actor_a": final_writer},
                                   browser_state={"actor_a": deepcopy(initial)})
        solo_b = workflow.evaluate(condition="solo_b", writer_xml={"actor_b": seed},
                                   browser_state={"actor_b": done})
        assert solo_a["condition_success"] and solo_b["condition_success"]
        assert solo_a["joint_success"] is None and solo_b["joint_success"] is None
        ma_id = workflow.evaluate(condition="ma_id",
                                  writer_xml={"actor_a": final_writer, "actor_b": seed},
                                  browser_state={"actor_a": deepcopy(initial), "actor_b": done})
        assert ma_id["joint_success"]
        ma_sd = workflow.evaluate(condition="ma_sd", writer_xml={"shared": final_writer},
                                  browser_state={"shared": done})
        assert ma_sd["joint_success"]


def test_wrong_href_or_missing_comment_fails_shared_but_keeps_b_goal():
    c = C02.evaluate(condition="ma_sd", writer_xml={"shared": writer_with_link(B_URL)},
                     browser_state={"shared": {"submission": {"url": B_URL}, "revision": 1}})
    assert c["actor_goal_success"] == {"actor_a": False, "actor_b": True}
    assert not c["condition_success"]
    f = F02.evaluate(condition="ma_sd",
                     writer_xml={"shared": F02.files()[F02.writer_path].decode()},
                     browser_state={"shared": {"submission": {"case": CASE, "decision": DECISION},
                                                "revision": 1}})
    assert f["actor_goal_success"] == {"actor_a": False, "actor_b": True}
    assert not f["condition_success"]


class Recorder:
    def __init__(self):
        self.actions = []
    def observe(self):
        self.actions.append(("observe",))
        return {"screenshot": b"offline-only"}
    def click(self, x, y):
        self.actions.append(("click", x, y))
    def press_key(self, key):
        self.actions.append(("key", key))
    def type_text(self, value):
        self.actions.append(("type", value))


def test_c02_clipboard_action_and_recopy_control():
    a = ScriptedBrowserWriterActor(C02, "actor_a", recovery=False)
    r = Recorder()
    assert a.run_step(r) is False and a.run_step(r) is True
    assert r.actions.count(("key", "ctrl+c")) == 1
    assert ("key", "ctrl+k") in r.actions and ("key", "ctrl+v") in r.actions
    recovery = ScriptedBrowserWriterActor(C02, "actor_a", recovery=True)
    rr = Recorder()
    recovery.run_step(rr); recovery.run_step(rr)
    assert rr.actions.count(("key", "ctrl+c")) == 2
    b = ScriptedBrowserWriterActor(C02, "actor_b", recovery=False)
    br = Recorder()
    assert b.run_step(br) is True
    assert ("key", "ctrl+c") in br.actions and ("key", "ctrl+v") in br.actions


def test_f02_comment_anchor_and_browser_form_intent():
    a = ScriptedBrowserWriterActor(F02, "actor_a", recovery=False)
    r = Recorder()
    a.run_step(r); a.run_step(r)
    assert ("key", "ctrl+alt+c") in r.actions
    assert ("type", COMMENT) in r.actions
    recovered = ScriptedBrowserWriterActor(F02, "actor_a", recovery=True)
    rr = Recorder()
    recovered.run_step(rr); recovered.run_step(rr)
    assert rr.actions.count(("click", 35, 335)) == 2
    b = ScriptedBrowserWriterActor(F02, "actor_b", recovery=False)
    br = Recorder()
    b.run_step(br)
    assert ("type", CASE) in br.actions and ("type", DECISION) in br.actions
