"""Reusable manifest builders and private evaluators for Modal and Browser Context.

These are task prototypes. Their evaluators operate on authoritative state supplied by
the runner; no actor receives that callback. Guest setup/readiness is runner-owned.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


MODAL_FAMILY_ID = "CODESK-TC-MODAL"
MODAL_TEMPLATE_ID = "writer_calc_save_dialog_v1"
CONTEXT_FAMILY_ID = "CODESK-TE-APP-CONTEXT"
CONTEXT_TEMPLATE_ID = "chromium_two_tab_context_v1"


def generate_modal_instance(seed: int) -> dict[str, Any]:
    from ..task_factory import (_b64, canonical_json, render_calc_fods,
                               render_writer_fodt, sha256_bytes)
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    serial = seed + 1
    writer_text = f"Board minutes {serial:04d}: final"
    calc_cells = [["Attendee", "Status"], [f"Member-{serial:04d}", "Present"]]
    writer_path = f"/tmp/codesk_modal/source-{serial:04d}.fodt"
    calc_path = f"/tmp/codesk_modal/source-{serial:04d}.fods"
    output_writer = f"/tmp/codesk_modal/out/minutes-{serial:04d}.fodt"
    output_calc = f"/tmp/codesk_modal/out/roster-{serial:04d}.fods"
    initial = {"writer": {"text": writer_text, "source_path": writer_path,
                           "save_path": output_writer, "dialog": "closed"},
               "calc": {"cells": calc_cells, "source_path": calc_path,
                        "save_path": output_calc, "dialog": "closed"},
               "desktop": {"window_count": 2, "active_dialog": None}}
    expected = {"writer": {"text": writer_text, "saved_path": output_writer,
                            "format": "FODT"},
                "calc": {"cells": calc_cells, "saved_path": output_calc,
                         "format": "FODS"}}
    goals = {
        "writer_actor": {"operation": "Save As the open Writer document to its assigned FODT path",
                         "source": writer_path, "target": output_writer,
                         "expected": writer_text},
        "calc_actor": {"operation": "Save As the open Calc workbook to its assigned FODS path",
                       "source": calc_path, "target": output_calc,
                       "expected": calc_cells},
    }
    files = {writer_path: render_writer_fodt([writer_text]),
             calc_path: render_calc_fods(calc_cells)}
    task_id = f"{MODAL_FAMILY_ID}-{seed:08d}"
    instance_id = f"modal-v1-seed-{seed:08d}"
    semantic = {"template_id": MODAL_TEMPLATE_ID, "seed": seed,
                "initial_state": initial, "actor_goals": goals,
                "expected_state": expected}
    fingerprint = sha256_bytes(canonical_json(semantic))
    manifest = {
        "schema_version": 1, "family_id": MODAL_FAMILY_ID,
        "template_id": MODAL_TEMPLATE_ID, "template_version": "1.0.0-prototype",
        "task_id": task_id, "instance_id": instance_id, "seed": seed,
        "content_fingerprint": fingerprint,
        "environment": {"adapter": "OSWorldSharedEpisode", "release": "osworld-v2.1",
                        "guest_application": "LibreOffice Writer + Calc",
                        "setup_commands": [["mkdir", "-p", "/tmp/codesk_modal/out"],
                                           ["libreoffice", "--writer", writer_path],
                                           ["libreoffice", "--calc", calc_path]],
                        "readiness": {"writer_source_contains": writer_text,
                                      "calc_cells": calc_cells,
                                      "active_dialog": None},
                        "shared_resources": ["desktop focus", "modal dialog stack",
                                              "keyboard", "pointer"]},
        "actors": {"writer_actor": "gui", "calc_actor": "gui"},
        "actor_goals": goals, "initial_state": initial, "expected_state": expected,
        "initial_files": [{"guest_path": path, "relative_path": f"initial/{path.rsplit('/',1)[-1]}",
                           "sha256": sha256_bytes(data), "size_bytes": len(data),
                           "content_base64": _b64(data)} for path, data in sorted(files.items())],
        "schedule": [
            {"actor_id": "writer_actor", "trigger": "episode_started"},
            {"actor_id": "calc_actor", "trigger": {"after_actor_turn":
                {"actor_id": "writer_actor", "count": 1}}},
            {"actor_id": "writer_actor", "trigger": {"after_actor_turn":
                {"actor_id": "calc_actor", "count": 1}}}],
        "evaluator": {"type": "ModalSaveExactEvaluator",
                      "oracle": "saved ODF path, parsed content, format, and dialog event owner",
                      "checks": ["actor save path", "exact saved content", "format",
                                 "dialog confirmation ownership"]},
        "joint_feasibility": {"feasible": True,
                              "proof": "Actors save distinct source documents to distinct output paths."},
        "evidence_status": "offline_prototype_guest_unverified",
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json(manifest))
    return manifest


def generate_browser_context_instance(seed: int) -> dict[str, Any]:
    from ..task_factory import _b64, canonical_json, sha256_bytes
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    a = f"CTX-A-{seed + 4100:05d}"
    b = f"CTX-B-{seed + 8200:05d}"
    initial = {"window_id": None, "active_tab": "tab-a",
               "tabs": {"tab-a": {"url": "/actor-a", "goal": "", "revision": 0},
                        "tab-b": {"url": "/actor-b", "goal": "", "revision": 0}}}
    expected = {"actor_a_goal": a, "actor_b_goal": b,
                "one_top_level_window": True}
    goals = {"actor_a": {"operation": "submit the assigned review in Browser tab A",
                          "tab": "tab-a", "expected": a},
             "actor_b": {"operation": "submit the assigned approval in Browser tab B",
                          "tab": "tab-b", "expected": b}}
    state_bytes = (json.dumps(initial, sort_keys=True, separators=(",", ":")) + "\n").encode()
    guest_path = "/tmp/codesk_browser_context/state.json"
    server_path = "/tmp/codesk_browser_context/server.py"
    server_bytes = browser_context_server_source(a, b, guest_path)
    task_id = f"{CONTEXT_FAMILY_ID}-{seed:08d}"
    instance_id = f"browser-context-v1-seed-{seed:08d}"
    semantic = {"template_id": CONTEXT_TEMPLATE_ID, "seed": seed,
                "initial_state": initial, "actor_goals": goals,
                "expected_state": expected}
    fingerprint = sha256_bytes(canonical_json(semantic))
    manifest = {
        "schema_version": 1, "family_id": CONTEXT_FAMILY_ID,
        "template_id": CONTEXT_TEMPLATE_ID, "template_version": "1.0.0-prototype",
        "task_id": task_id, "instance_id": instance_id, "seed": seed,
        "content_fingerprint": fingerprint,
        "environment": {"adapter": "OSWorldSharedEpisode", "release": "osworld-v2.1",
                        "guest_application": "Chromium, one window with two local tabs",
                        "setup_commands": [["python3", server_path],
                                           ["chromium", "--new-window",
                                            "http://127.0.0.1:8766/actor-a",
                                            "http://127.0.0.1:8766/actor-b"]],
                        "readiness": {"route_a": "http://127.0.0.1:8766/actor-a",
                                      "route_b": "http://127.0.0.1:8766/actor-b",
                                      "expected_tabs_in_one_window": 2},
                        "shared_resources": ["browser window context", "active tab",
                                              "keyboard", "pointer", "local app backend"]},
        "actors": {"actor_a": "gui", "actor_b": "gui"},
        "actor_goals": goals, "initial_state": initial, "expected_state": expected,
        "initial_files": [
            {"guest_path": guest_path, "relative_path": "initial/state.json",
             "sha256": sha256_bytes(state_bytes), "size_bytes": len(state_bytes),
             "content_base64": _b64(state_bytes)},
            {"guest_path": server_path, "relative_path": "initial/server.py",
             "sha256": sha256_bytes(server_bytes), "size_bytes": len(server_bytes),
             "content_base64": _b64(server_bytes)}],
        "schedule": [
            {"actor_id": "actor_a", "trigger": "episode_started"},
            {"actor_id": "actor_b", "trigger": {"after_actor_turn":
                {"actor_id": "actor_a", "count": 1}}},
            {"actor_id": "actor_a", "trigger": {"after_actor_turn":
                {"actor_id": "actor_b", "count": 1}}}],
        "evaluator": {"type": "BrowserTabContextEvaluator",
                      "oracle": "private server state plus browser tab/window event stream",
                      "checks": ["both exact goal submissions", "one stable top-level window id",
                                 "active-tab transitions", "no cross-tab goal contamination"]},
        "joint_feasibility": {"feasible": True,
                              "proof": "Distinct tab-owned fields accept independent exact submissions."},
        "evidence_status": "offline_prototype_guest_unverified",
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json(manifest))
    return manifest


@dataclass(frozen=True)
class ModalSaveExactEvaluator:
    """Evaluate saved artifacts and independently report dialog-owner evidence."""
    expected: dict[str, Any]

    def evaluate(self, actual: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        actor_success = {
            "writer_actor": actual.get("writer") == self.expected["writer"],
            "calc_actor": actual.get("calc") == self.expected["calc"],
        }
        confirms = [e for e in events if e.get("kind") == "dialog_confirmed"]
        by_actor = {actor: [e for e in confirms if e.get("actor_id") == actor]
                    for actor in actor_success}
        owner = {actor: ("supported" if any(e.get("dialog_owner") == actor
                                             and e.get("target_path") == self.expected[actor.split("_")[0]]["saved_path"]
                                             for e in rows) else
                         "mismatch" if rows and any(e.get("dialog_owner") != actor for e in rows)
                         else "unknown") for actor, rows in by_actor.items()}
        return {"actor_success": actor_success,
                "joint_success": all(actor_success.values()),
                "dialog_owner_evidence": owner,
                "cross_owner_confirmation_count": sum(
                    e.get("actor_id") != e.get("dialog_owner") for e in confirms),
                "dialog_attribution_complete": all(v != "unknown" for v in owner.values())}


def evaluate_browser_context(actual: dict[str, Any], events: list[dict[str, Any]],
                             expected: dict[str, Any]) -> dict[str, Any]:
    """Separate task outcome from evidence that tab context changed in one window."""
    tabs = actual.get("tabs", {})
    actor_success = {"actor_a": tabs.get("tab-a", {}).get("goal") == expected["actor_a_goal"],
                     "actor_b": tabs.get("tab-b", {}).get("goal") == expected["actor_b_goal"]}
    window_ids = {e.get("window_id") for e in events
                  if e.get("kind") in {"window_observation", "tab_activated"}
                  and e.get("window_id") is not None}
    activations = [e for e in events if e.get("kind") == "tab_activated"]
    tab_changes = sum(e.get("before_tab") != e.get("after_tab") for e in activations)
    evidence = ("supported" if len(window_ids) == 1 and tab_changes > 0 else
                "contradicted" if len(window_ids) > 1 else "unknown")
    return {"actor_success": actor_success, "joint_success": all(actor_success.values()),
            "same_top_level_window": evidence == "supported",
            "application_context_evidence": evidence,
            "window_id_count": len(window_ids), "tab_change_count": tab_changes,
            "cross_tab_contention_exposure": tab_changes > 0}


def browser_context_server_source(goal_a: str, goal_b: str,
                                  state_path: str = "/tmp/codesk_browser_context/state.json") -> bytes:
    """Build a dependency-free local two-route app fixture for a Guest setup adapter.

    The UI has one form per URL, intended to be opened as two tabs in one Chromium
    window. Goal commits and page visibility are logged server-side. X11 window IDs
    still have to be joined by the desktop adapter before claiming same-window evidence.
    """
    import json as _json
    goals = _json.dumps({"actor_a": goal_a, "actor_b": goal_b})
    source = r"""from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
from datetime import datetime, timezone
STATE=Path(__STATE_PATH__)
GOALS=__GOALS__
EVENTS=STATE.with_name('events.jsonl')
DEFAULT={'window_id':None,'tabs':{'tab-a':{'goal':'','revision':0},'tab-b':{'goal':'','revision':0}}}
STATE.parent.mkdir(parents=True,exist_ok=True)
if not STATE.exists(): STATE.write_text(json.dumps(DEFAULT))
def append_event(event):
 event.update({'utc':datetime.now(timezone.utc).isoformat()})
 with EVENTS.open('a') as f: f.write(json.dumps(event,sort_keys=True)+'\n')
class Handler(BaseHTTPRequestHandler):
 def send_json(self,obj,status=200):
  data=json.dumps(obj).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
 def do_GET(self):
  if self.path=='/health': return self.send_json({'ok':True})
  if self.path in ('/actor-a','/actor-b'):
   actor='actor_a' if self.path.endswith('a') else 'actor_b'; tab='tab-a' if actor=='actor_a' else 'tab-b'
   target=GOALS[actor]
   html=f'''<!doctype html><meta charset="utf-8"><title>CoDesk {tab}</title>
   <style>body{{font:20px Arial;margin:24px}}#value{{position:absolute;left:100px;top:160px;width:380px;height:48px;font:22px Arial}}#submit{{position:absolute;left:100px;top:235px;width:150px;height:48px;font:20px Arial}}</style>
   <h1>{tab} review workspace</h1><p>Submit this exact value: <b id="target">{target}</b></p>
   <input id="value" autocomplete="off"><button id="submit" onclick="submitGoal()">Submit</button><output id="result"></output>
   <script>const actor={actor!r},tab={tab!r};
   document.addEventListener('visibilitychange',()=>fetch('/visibility',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{tab,visible:document.visibilityState==='visible'}})}}));
   async function submitGoal(){{let r=await fetch('/goal',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{actor,tab,value:document.querySelector('#value').value}})}});document.querySelector('#result').textContent=r.ok?'Saved':'Rejected';}}
   </script>'''.encode()
   self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(html))); self.end_headers(); self.wfile.write(html); append_event({'kind':'tab_page_loaded','actor_id':actor,'tab_id':tab}); return
  return self.send_json({'error':'not found'},404)
 def do_POST(self):
  try: p=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
  except Exception: return self.send_json({'error':'invalid JSON'},400)
  if self.path=='/visibility': append_event({'kind':'tab_visibility','tab_id':p.get('tab'),'visible':p.get('visible')}); return self.send_json({'ok':True})
  if self.path!='/goal': return self.send_json({'error':'not found'},404)
  actor=p.get('actor'); tab=p.get('tab'); expected_tab={'actor_a':'tab-a','actor_b':'tab-b'}.get(actor)
  if expected_tab!=tab: return self.send_json({'error':'actor/tab mismatch'},409)
  s=json.loads(STATE.read_text()); s['tabs'][tab]['goal']=str(p.get('value','')); s['tabs'][tab]['revision']+=1; STATE.write_text(json.dumps(s,sort_keys=True))
  append_event({'kind':'goal_committed','actor_id':actor,'tab_id':tab,'revision':s['tabs'][tab]['revision']})
  return self.send_json({'ok':True})
 def log_message(self,*args): pass
HTTPServer(('127.0.0.1',8766),Handler).serve_forever()
"""
    return (source.replace("__STATE_PATH__", repr(state_path))
            .replace("__GOALS__", goals).encode("utf-8"))
