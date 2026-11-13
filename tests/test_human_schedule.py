from __future__ import annotations
import threading
import time
from pathlib import Path
from oscombo.eventlog import EventLog, append_jsonl
from oscombo.human_schedule import is_agent_input_event, timeline_metrics, wait_for_first_agent_input


def test_only_real_agent_gui_input_triggers_user_start():
    base={"actor_id":"agent","event_type":"agent_gui_action","tool":"click","code":"pyautogui.click(1,2)","status":"ok"}
    assert is_agent_input_event(base)
    assert not is_agent_input_event({**base,"tool":"screenshot","code":None})
    assert not is_agent_input_event({**base,"tool":"wait"})
    assert not is_agent_input_event({**base,"focus_switch_action":True})
    assert not is_agent_input_event({**base,"status":"error"})


def test_user_actions_interleaved_during_agent_think_are_distinct_from_literal_overlap():
    rows=[
        {"actor_id":"agent","event_type":"actor_started","guest_id":"shared","monotonic_time":0},
        {"actor_id":"user","event_type":"actor_started","guest_id":"shared","monotonic_time":10},
        {"actor_id":"agent","event_type":"agent_gui_action","guest_id":"shared","tool":"screenshot","start_monotonic":1,"end_monotonic":2},
        {"actor_id":"user","event_type":"gui_action","guest_id":"shared","action_name":"read_and_scroll","start_monotonic":5,"end_monotonic":7,"scheduled_delay_before_s":12},
        {"actor_id":"agent","event_type":"agent_gui_action","guest_id":"shared","tool":"click","start_monotonic":14,"end_monotonic":15,"code":"pyautogui.click(1,2)"},
        {"actor_id":"user","event_type":"actor_finished","guest_id":"shared","monotonic_time":18},
        {"actor_id":"agent","event_type":"actor_finished","guest_id":"shared","monotonic_time":20},
    ]
    m=timeline_metrics(rows)
    assert m["literal_same_guest_gui_action_overlap_pair_count"]==0
    assert m["user_actions_between_agent_gui_calls_count"]==1
    assert m["user_scheduled_dwell_s"]==12
    assert m["same_guest_actor_active_overlap_s"]==8


def test_independent_guest_timing_is_not_counted_as_shared_desktop_interference():
    rows=[
        {"actor_id":"agent","event_type":"agent_gui_action","guest_id":"agent-guest","tool":"click","start_monotonic":1,"end_monotonic":4,"code":"click"},
        {"actor_id":"user","event_type":"gui_action","guest_id":"user-guest","action_name":"edit","start_monotonic":2,"end_monotonic":5},
    ]
    m=timeline_metrics(rows)
    assert m["literal_same_guest_gui_action_overlap_pair_count"]==0
    assert m["user_actions_between_agent_gui_calls_count"]==0


def test_live_waiter_releases_on_first_agent_input(tmp_path: Path):
    path=tmp_path/"events.jsonl";log=EventLog(path,"r",tmp_path,time.monotonic())
    def writer():
        time.sleep(.05)
        append_jsonl(path,{"event_type":"agent_gui_action","actor_id":"agent","event_id":"e1","tool":"click","status":"ok","code":"pyautogui.click(4,5)","input_action":True,"start_monotonic":2.0,"end_monotonic":2.1,"run_elapsed_s":4.1})
    t=threading.Thread(target=writer);t.start()
    info=wait_for_first_agent_input(path,log,timeout_s=1,poll_s=.005);t.join()
    assert info["outcome"]=="triggered"
    assert info["trigger_event_id"]=="e1"
    assert info["trigger_tool"]=="click"


def test_live_waiter_records_clean_no_input_agent_finish(tmp_path: Path):
    path=tmp_path/"events.jsonl";log=EventLog(path,"r",tmp_path,time.monotonic())
    append_jsonl(path,{"event_type":"actor_finished","actor_id":"agent","event_id":"finish"})
    info=wait_for_first_agent_input(path,log,timeout_s=.01,poll_s=.002)
    assert info["outcome"]=="agent_finished_without_input"
