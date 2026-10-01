"""A-02: two independent records in one Browser tab and one URL.

The private record state and selection events are visible only to the runner.
Actors receive a screenshot and GUI controls; this module does not expose the
oracle through ActorContext.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from ..environment import ActorContext

TASK_VERSION = "0.1.0"
TASK_ID = "codesk-a02-record-context-000"
PORT = 8767
STATE_PATH = "/tmp/codesk_browser_record_context/state.json"
EVENTS_PATH = "/tmp/codesk_browser_record_context/events.jsonl"
SERVER_PATH = "/tmp/codesk_browser_record_context/server.py"
PROFILE_PATH = "/tmp/codesk_browser_record_context/profile"
URL = f"http://127.0.0.1:{PORT}/workspace"
SELECT_A_POINT = (170, 220)
SELECT_B_POINT = (350, 220)
INPUT_POINT = (300, 300)
SAVE_POINT = (260, 375)
VALUES = {"actor_a": "REC-A-4100", "actor_b": "REC-B-8200"}
INITIAL_STATE = {
    "selected_record": "record-a",
    "records": {"record-a": {"goal": "", "revision": 0},
                "record-b": {"goal": "", "revision": 0}},
}


def _server_source() -> bytes:
    source = r'''from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from datetime import datetime, timezone
import json
STATE=Path(__STATE_PATH__)
EVENTS=STATE.with_name("events.jsonl")
STATE.parent.mkdir(parents=True,exist_ok=True)
def record(event):
 event["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(event,sort_keys=True)+"\n")
class Handler(BaseHTTPRequestHandler):
 def response(self,data,status=200):
  raw=json.dumps(data).encode()
  self.send_response(status);self.send_header("Content-Type","application/json")
  self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=="/health":return self.response({"ok":True})
  if self.path!="/workspace":return self.response({"error":"not found"},404)
  html=r"""<!doctype html><meta charset="utf-8"><title>CoDesk record workspace</title>
  <style>body{font:20px Arial;margin:24px}button{font:20px Arial}
  #record-a{position:absolute;left:100px;top:80px;width:150px;height:48px}
  #record-b{position:absolute;left:280px;top:80px;width:150px;height:48px}
  #value{position:absolute;left:100px;top:160px;width:380px;height:48px;font:22px Arial}
  #save{position:absolute;left:100px;top:235px;width:150px;height:48px}</style>
  <h1>Record workspace</h1><p>Record A: REC-A-4100; Record B: REC-B-8200</p>
  <button id="record-a" onclick="selectRecord('record-a')">Record A</button>
  <button id="record-b" onclick="selectRecord('record-b')">Record B</button>
  <input id="value" autocomplete="off">
  <button id="save" onclick="saveGoal()">Save selected</button><output id="result"></output>
  <script>
  let selected='record-a';const drafts={'record-a':'','record-b':''};
  document.querySelector('#value').addEventListener('input',e=>{drafts[selected]=e.target.value});
  async function selectRecord(record){
    selected=record;document.querySelector('#value').value=drafts[record];
    await fetch('/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record})});
  }
  async function saveGoal(){
    let value=document.querySelector('#value').value;
    let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record:selected,value})});
    document.querySelector('#result').textContent=r.ok?'Saved':'Rejected';
  }
  </script>"""
  raw=html.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
  self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
  record({"kind":"page_loaded"});return
 def do_POST(self):
  try:p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
  except Exception:return self.response({"error":"invalid JSON"},400)
  rec=p.get("record")
  if rec not in ("record-a","record-b"):return self.response({"error":"bad record"},400)
  s=json.loads(STATE.read_text())
  if self.path=="/select":
    s["selected_record"]=rec;STATE.write_text(json.dumps(s,sort_keys=True))
    record({"kind":"record_selected","record":rec});return self.response({"ok":True})
  if self.path=="/save":
    if s["selected_record"]!=rec:return self.response({"error":"selection changed"},409)
    s["records"][rec]["goal"]=str(p.get("value",""))
    s["records"][rec]["revision"]+=1
    STATE.write_text(json.dumps(s,sort_keys=True))
    record({"kind":"record_saved","record":rec,"revision":s["records"][rec]["revision"]})
    return self.response({"ok":True})
  return self.response({"error":"not found"},404)
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8767),Handler).serve_forever()
'''
    return source.replace("__STATE_PATH__", repr(STATE_PATH)).encode()


SERVER_BYTES = _server_source()
STATE_BYTES = (json.dumps(INITIAL_STATE, sort_keys=True) + "\n").encode()
FIXTURE_SHA256 = hashlib.sha256(STATE_BYTES + b"\\0" + SERVER_BYTES).hexdigest()
MANIFEST = {
    "template_id": "A-02", "task_id": TASK_ID, "task_version": TASK_VERSION,
    "environment": "one Chromium top-level window, tab and URL; two in-page records",
    "actor_goals": {
        "actor_a": {"record": "record-a", "expected": VALUES["actor_a"]},
        "actor_b": {"record": "record-b", "expected": VALUES["actor_b"]}},
    "initial_state": INITIAL_STATE, "fixture_sha256": FIXTURE_SHA256,
    "schedule": ["actor_a", "actor_b", "actor_a"],
    "condition_contract": {
        "solo": "one actor on one clean Guest",
        "ma_id": "two clean independent desktops with identical fixture digest",
        "ma_sd": "two actors in one Chromium tab and one Guest",
        "backend_visibility_required": False,
        "recovery": "reselect own record, reobserve, then save"},
}


@dataclass(frozen=True)
class RecordContextTask:
    def evaluate(self, *, condition: str, states: dict[str, dict[str, Any]],
                 windows: dict[str, dict[str, Any]],
                 turn_events: dict[str, list[dict[str, Any]]],
                 recovery: bool) -> dict[str, Any]:
        if condition not in {"solo_a", "solo_b", "ma_id", "ma_sd"}:
            raise ValueError("unknown condition")
        active = ("actor_a", "actor_b") if condition in {"ma_id", "ma_sd"} else (
            ("actor_a",) if condition == "solo_a" else ("actor_b",))
        binding = lambda actor: "shared" if condition == "ma_sd" else actor
        goals, integrity = {}, {}
        for actor in active:
            records = states[binding(actor)]["records"]
            own = "record-a" if actor == "actor_a" else "record-b"
            other = "record-b" if actor == "actor_a" else "record-a"
            goals[actor] = records[own]["goal"] == VALUES[actor]
            integrity[actor] = (records[own]["revision"] == 1 and
                (condition == "ma_sd" or records[other] == INITIAL_STATE["records"][other]))
        a1, b1, a2 = (windows.get("actor_a_1", {}), windows.get("actor_b_1", {}),
                      windows.get("actor_a_2_before", {}))
        stable = bool(condition == "ma_sd" and all(row.get("window_id") and
            row.get("tab_id") and row.get("url") == URL for row in (a1,b1,a2)) and
            len({row["window_id"] for row in (a1,b1,a2)}) == 1 and
            len({row["tab_id"] for row in (a1,b1,a2)}) == 1)
        a_resume = turn_events.get("actor_a_2", [])
        wrong_record_action = bool(stable and
            any(row.get("kind") == "record_saved" and row.get("record") == "record-b"
                for row in a_resume) and not recovery)
        selection_changed = bool(stable and
            any(row.get("kind") == "record_selected" and row.get("record") == "record-b"
                for row in turn_events.get("actor_b_1", [])))
        success = all(goals.values()) and all(integrity.values())
        return {"actor_goal_success": goals, "non_target_integrity": integrity,
                "condition_success": success,
                "joint_success": success if len(active) == 2 else None,
                "same_window_tab_url": stable, "in_page_selection_changed": selection_changed,
                "wrong_record_action_supported": wrong_record_action,
                "recovery_supported": bool(recovery and condition == "ma_sd" and
                    stable and selection_changed and success and
                    any(row.get("kind") == "record_selected" and row.get("record") == "record-a"
                        for row in a_resume))}


TASK = RecordContextTask()


class ScriptedA02Actor:
    role = "gui"

    def __init__(self, actor_id: str, *, recovery: bool):
        if actor_id not in VALUES:
            raise ValueError("unknown actor")
        self.actor_id, self.recovery, self.turn = actor_id, recovery, 0

    @staticmethod
    def _observe(context: ActorContext) -> None:
        shot = context.observe().get("screenshot")
        if not isinstance(shot, bytes) or not shot:
            raise RuntimeError("A-02 actor received no real screenshot")

    def run_step(self, context: ActorContext) -> bool:
        if self.actor_id == "actor_a" and self.turn == 1:
            if self.recovery:
                context.click(*SELECT_A_POINT)
                self._observe(context)
            context.click(*SAVE_POINT)
            self.turn = 2
            return True
        if self.turn != 0:
            raise RuntimeError("unexpected A-02 turn")
        self._observe(context)
        context.click(*(SELECT_A_POINT if self.actor_id == "actor_a" else SELECT_B_POINT))
        context.click(*INPUT_POINT)
        context.press_key("ctrl+a")
        context.type_text(VALUES[self.actor_id])
        self.turn = 1
        if self.actor_id == "actor_a":
            return False
        context.click(*SAVE_POINT)
        return True
