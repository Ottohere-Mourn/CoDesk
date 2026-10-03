"""Offline task contracts and exact evaluators for the five MINIMAL matrix workflows.

Guest execution is provided by scripts/run_matrix_workflow_v1.py. Evaluator inputs
are collected runner-side and are never attached to ActorContext.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any
import xml.etree.ElementTree as ET

from ..task_factory import render_writer_fodt

TASKS = ("F-N1", "C-N1", "A-N1", "S-N1", "U-N1")

# Shared one-Writer-document fixture used by Selection and Undo.
S_TEXT_A = "ALPHA target"
S_TEXT_B = "BETA target"
U_A_INITIAL = "A-LINE: keep"
U_B_INITIAL = "B-LINE: keep"
U_A_TEMP = "A-LINE: temporary"
U_B_FINAL = "B-LINE: final"

C_TABLE = (("Item", "Count"), ("North", "17"), ("South", "29"))
C_BROWSER_URL = "https://example.org/codesk/n1/submit-b"
C_LABEL = "Copied review table"

A_ROUTE_GOALS = {"route-a": "A-READY-531", "route-b": "B-APPROVE-824"}
A_ROUTE_INITIAL = {"active_route": "route-a",
                   "routes": {key: {"value": "", "revision": 0}
                              for key in A_ROUTE_GOALS}}


def task_manifest(task_id: str) -> dict[str, Any]:
    rows = {
        "F-N1": {
            "family": "focus_input_routing", "apps": ["LibreOffice Writer"],
            "actor_goals": {"actor_a": "Replace doc-A paragraph with A-FINAL-731.",
                            "actor_b": "Replace doc-B paragraph with B-FINAL-204."},
            "shared_state": "OS foreground Writer top-level window",
            "evaluator": "exact content of doc-A and doc-B by path",
            "recovery": "A reactivates doc-A by window identity and repeats its edit"},
        "C-N1": {
            "family": "clipboard_ownership", "apps": ["Chromium", "LibreOffice Writer"],
            "actor_goals": {"actor_a": "Copy the structured Browser table into the Writer table target.",
                            "actor_b": "Copy and submit the assigned Browser URL in B's form."},
            "shared_state": "X11 clipboard payload, generation, and MIME targets",
            "evaluator": "Writer table rows/cells/text plus Browser exact URL/revision",
            "recovery": "A reacquires Browser table, recopies and replaces Writer target"},
        "A-N1": {
            "family": "application_context", "apps": ["Chromium"],
            "actor_goals": {"actor_a": "Submit A-READY-531 to route-a.",
                            "actor_b": "Submit B-APPROVE-824 to route-b."},
            "shared_state": "active SPA route in one Browser tab",
            "evaluator": "route-keyed exact values/revisions and route event stream",
            "recovery": "A navigates back to route-a, verifies route label, and submits"},
        "S-N1": {
            "family": "selection_active_object", "apps": ["LibreOffice Writer"],
            "actor_goals": {"actor_a": "Bold only the ALPHA target span.",
                            "actor_b": "Bold only the BETA target span."},
            "shared_state": "active text range in one Writer document/window",
            "evaluator": "ODF text spans/styles and both unformatted guard phrases",
            "recovery": "A reselects ALPHA target and applies bold"},
        "U-N1": {
            "family": "undo_redo_history", "apps": ["LibreOffice Writer"],
            "actor_goals": {"actor_a": "Make then Undo a temporary first-line edit, restoring its seed.",
                            "actor_b": "Change the second line to B-LINE: final."},
            "shared_state": "shared Writer document undo stack",
            "evaluator": "exact two paragraph strings and action/history event order",
            "recovery": "B reapplies its line if undone, then A undoes its own temporary line"},
    }
    if task_id not in rows:
        raise ValueError(f"unknown matrix workflow {task_id!r}")
    row = rows[task_id]
    return {"task_id": task_id, "version": "0.1.0-prototype",
            "family": row["family"], "applications": row["apps"],
            "actor_goals": row["actor_goals"], "shared_state": row["shared_state"],
            "evaluator": row["evaluator"], "recovery": row["recovery"],
            "condition_contract": {
                "solo": "one actor on a fresh Guest and task-relevant fixture",
                "ma_id": "independent Guest desktops cloned from equivalent fixture; same schedule",
                "ma_sd": "one Guest desktop and the task-specific shared GUI state",
                "schedule": ["actor_a", "actor_b", "actor_a"],
                "hidden_state_private": True}}


def fixture_files(task_id: str) -> dict[str, bytes]:
    if task_id == "F-N1":
        return {
            "/tmp/codesk_fn1/doc-a.fodt": render_writer_fodt(["A-DRAFT-731"]),
            "/tmp/codesk_fn1/doc-b.fodt": render_writer_fodt(["B-DRAFT-204"]),
        }
    if task_id == "C-N1":
        html = ("""<!doctype html><meta charset=utf-8><title>CoDesk rich clipboard</title>
<style>body{font:18px Arial}table{border-collapse:collapse}td,th{border:2px solid #176b54;padding:8px}
#table{position:absolute;left:50px;top:120px}#src{position:absolute;left:50px;top:300px}
#dst{position:absolute;left:50px;top:380px}button{position:absolute;left:50px;top:450px}</style>
<h1>Copy the review table into Writer</h1>
<table id=table><tr><th>Item</th><th>Count</th></tr><tr><td>North</td><td>17</td></tr>
<tr><td>South</td><td>29</td></tr></table>
<p id=src>__URL__</p><p>Copy source text into the URL field and submit.</p>
<input id=dst aria-label='URL destination'><button onclick='save()'>Submit URL</button>
<script>async function save(){let url=document.querySelector('#dst').value;
let r=await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({url})});document.body.dataset.saved=r.ok?'yes':'no';}</script>"""
                .replace("__URL__", C_BROWSER_URL)).encode()
        return {
            "/tmp/codesk_cn1/browser.html": html,
            "/tmp/codesk_cn1/state.json": (json.dumps({"submission": {}, "revision": 0},
                sort_keys=True) + "\n").encode(),
            "/tmp/codesk_cn1/server.py": c_server_source(),
            "/tmp/codesk_cn1/writer.fodt": render_writer_fodt([C_LABEL, "INSERT TABLE"]),
        }
    if task_id == "A-N1":
        return {
            "/tmp/codesk_an1/state.json": (json.dumps(A_ROUTE_INITIAL, sort_keys=True)+"\n").encode(),
            "/tmp/codesk_an1/server.py": a_server_source(),
        }
    if task_id in {"S-N1", "U-N1"}:
        paras = ([f"{S_TEXT_A} | {S_TEXT_B}", "KEEP GUARD"] if task_id == "S-N1"
                 else [U_A_INITIAL, U_B_INITIAL, "KEEP GUARD"])
        return {f"/tmp/codesk_{task_id.lower().replace('-', '')}/writer.fodt":
                render_writer_fodt(paras)}
    raise ValueError(task_id)


def fixture_hash(task_id: str) -> str:
    h = hashlib.sha256()
    for path, content in sorted(fixture_files(task_id).items()):
        h.update(path.encode() + b"\0" + content)
    return h.hexdigest()


def parse_writer(xml: str) -> dict[str, Any]:
    root = ET.fromstring(xml)
    office = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    text = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    fo = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    body = root.find(f".//{{{office}}}body/{{{office}}}text")
    if body is None:
        raise ValueError("Writer ODF has no text body")
    paras = body.findall(f"{{{text}}}p")
    auto = root.find(f".//{{{office}}}automatic-styles")
    styles: dict[str, dict[str, str]] = {}
    if auto is not None:
        for style in auto:
            name = style.get(f"{{{text}}}name")
            props = style.find(f"{{{text}}}text-properties")
            if name and props is not None:
                styles[name] = dict(props.attrib)
    def spans(paragraph: ET.Element) -> list[dict[str, Any]]:
        result = []
        for node in paragraph.iter():
            if node.tag == f"{{{text}}}span":
                name = node.get(f"{{{text}}}style-name", "")
                content = "".join(node.itertext())
                bold = styles.get(name, {}).get(f"{{{fo}}}font-weight") in {"bold", "700"}
                result.append({"text": content, "style": name, "bold": bold})
        return result
    return {"paragraphs": ["".join(p.itertext()) for p in paras],
            "spans": [spans(p) for p in paras], "paragraph_count": len(paras)}


def c_server_source() -> bytes:
    source = r'''from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
STATE=Path("/tmp/codesk_cn1/state.json")
HTML=Path("/tmp/codesk_cn1/browser.html").read_bytes()
class H(BaseHTTPRequestHandler):
 def reply(self,body,status=200):
  raw=json.dumps(body).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path!="/workspace":return self.reply({"error":"not found"},404)
  self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(HTML)));self.end_headers();self.wfile.write(HTML)
 def do_POST(self):
  if self.path!="/submit":return self.reply({"error":"not found"},404)
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
  s=json.loads(STATE.read_text());s["submission"]=p;s["revision"]+=1;STATE.write_text(json.dumps(s,sort_keys=True))
  return self.reply({"ok":True})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8769),H).serve_forever()
'''
    return source.encode()


def a_server_source() -> bytes:
    source = r'''from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
STATE=Path("/tmp/codesk_an1/state.json")
EVENTS=STATE.with_name("events.jsonl")
STATE.parent.mkdir(parents=True,exist_ok=True)
def log(row):
 row["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(row,sort_keys=True)+"\n")
class H(BaseHTTPRequestHandler):
 def reply(self,body,status=200):
  raw=json.dumps(body).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path not in ("/workspace","/route-a","/route-b"):return self.reply({"error":"not found"},404)
  html="""<!doctype html><meta charset=utf-8><title>CoDesk route context</title>
  <style>body{font:20px Arial;margin:24px}button,input{font:20px Arial;margin:12px;padding:8px}</style>
  <style>h1{position:absolute;left:50px;top:10px}#open-a{position:absolute;left:50px;top:90px}
  #open-b{position:absolute;left:190px;top:90px}#value{position:absolute;left:50px;top:210px}
  #submit{position:absolute;left:50px;top:280px}#result{position:absolute;left:250px;top:290px}</style>
  <h1 id=route>route-a</h1><button id=open-a onclick='go("route-a")'>Open A</button>
  <button id=open-b onclick='go("route-b")'>Open B</button>
  <p style='position:absolute;left:50px;top:170px'>Submit the route goal:</p>
  <input id=value><button id=submit onclick='submitGoal()'>Submit</button><output id=result></output>
  <script>
  let activeRoute=location.pathname==="/route-b"?"route-b":"route-a";
  const goals={"route-a":"A-READY-531","route-b":"B-APPROVE-824"};
  function render(){document.querySelector("#route").textContent=activeRoute;document.querySelector("#value").value="";history.pushState({route:activeRoute},"","/"+activeRoute);fetch("/event",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({kind:"route_changed",route:activeRoute})});}
  async function go(route){activeRoute=route;render()}
  async function submitGoal(){let value=document.querySelector("#value").value;await fetch("/submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({route:activeRoute,value})});document.querySelector("#result").textContent="Saved"}
  render();</script>"""
  raw=html.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw);log({"kind":"page_loaded","route":self.path.rsplit("/",1)[-1]});return
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
  s=json.loads(STATE.read_text())
  if self.path=="/event":log(p);return self.reply({"ok":True})
  if self.path!="/submit":return self.reply({"error":"not found"},404)
  route=p.get("route")
  if route not in s["routes"]:return self.reply({"error":"bad route"},400)
  s["active_route"]=route;s["routes"][route]["value"]=str(p.get("value",""));s["routes"][route]["revision"]+=1
  STATE.write_text(json.dumps(s,sort_keys=True));log({"kind":"route_submit","route":route,"revision":s["routes"][route]["revision"],"value":p.get("value")});return self.reply({"ok":True})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8770),H).serve_forever()
'''
    return source.encode()


def parse_writer_table(xml: str) -> dict[str, Any]:
    root=ET.fromstring(xml)
    table_ns="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    text_ns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    tables=[]
    for table in root.iter(f"{{{table_ns}}}table"):
        rows=[]
        for row in table.findall(f"{{{table_ns}}}table-row"):
            cells=[]
            for cell in row.findall(f"{{{table_ns}}}table-cell"):
                cells.append("".join(cell.itertext()))
            rows.append(cells)
        tables.append(rows)
    office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    body=root.find(f".//{{{office}}}body/{{{office}}}text")
    paras=[] if body is None else body.findall(f"{{{text_ns}}}p")
    return {"table": next((table for table in tables if table), None),
            "guard": "".join(paras[-1].itertext()) if paras else ""}


def evaluate(task_id: str, actual: dict[str, Any],
             active_actors: tuple[str, ...] = ("actor_a", "actor_b")) -> dict[str, Any]:
    """Score actors that ran in this binding and require all other goals untouched.

    For MA-ID, each Guest is evaluated with one active actor, so the peer's
    fixture state must remain exact. For MA-SD both actors are active in the
    same state and both target states are required.
    """
    if task_id == "F-N1":
        docs = actual.get("documents", {})
        a = docs.get("doc-a", "")
        b = docs.get("doc-b", "")
        goals = {"actor_a": a == "A-FINAL-731", "actor_b": b == "B-FINAL-204"}
        integrity = {"actor_a": b == ("B-FINAL-204" if "actor_b" in active_actors else "B-DRAFT-204"),
                     "actor_b": a == ("A-FINAL-731" if "actor_a" in active_actors else "A-DRAFT-731")}
    elif task_id == "C-N1":
        writer = actual.get("writer", {})
        browser = actual.get("browser", {})
        table = writer.get("table")
        expected_table = [list(row) for row in C_TABLE]
        goals = {"actor_a": table == expected_table,
                 "actor_b": browser.get("submission") == {"url": C_BROWSER_URL}
                    and browser.get("revision") == 1}
        integrity = {
            "actor_a": writer.get("guard") == "KEEP GUARD"
                and browser.get("submission", {}) == ({"url": C_BROWSER_URL}
                    if "actor_b" in active_actors else {})
                and browser.get("revision", 0) == (1 if "actor_b" in active_actors else 0),
            "actor_b": writer.get("table") == (expected_table if "actor_a" in active_actors else None)
                and writer.get("guard") == "KEEP GUARD",
        }
    elif task_id == "A-N1":
        state = actual.get("routes", {})
        goals = {actor: state.get(route, {}).get("value") == value
                 for actor, route, value in (
                     ("actor_a", "route-a", A_ROUTE_GOALS["route-a"]),
                     ("actor_b", "route-b", A_ROUTE_GOALS["route-b"]))}
        integrity = {
            "actor_a": (state.get("route-b", {}).get("value", "") ==
                        (A_ROUTE_GOALS["route-b"] if "actor_b" in active_actors else "")
                        and state.get("route-b", {}).get("revision", 0) ==
                        (1 if "actor_b" in active_actors else 0)),
            "actor_b": (state.get("route-a", {}).get("value", "") ==
                        (A_ROUTE_GOALS["route-a"] if "actor_a" in active_actors else "")
                        and state.get("route-a", {}).get("revision", 0) ==
                        (1 if "actor_a" in active_actors else 0)),
        }
    elif task_id == "S-N1":
        writer = actual.get("writer", {})
        bold = writer.get("bold_spans", [])
        actual_bold = {x.get("text") for x in bold if x.get("bold")}
        goals = {"actor_a": S_TEXT_A in actual_bold, "actor_b": S_TEXT_B in actual_bold}
        integrity = {"actor_a": writer.get("guard") == "KEEP GUARD"
                        and writer.get("document_text") == f"{S_TEXT_A} | {S_TEXT_B}"
                        and (S_TEXT_B in actual_bold) == ("actor_b" in active_actors),
                     "actor_b": writer.get("guard") == "KEEP GUARD"
                        and writer.get("document_text") == f"{S_TEXT_A} | {S_TEXT_B}"
                        and (S_TEXT_A in actual_bold) == ("actor_a" in active_actors)}
    elif task_id == "U-N1":
        lines = actual.get("writer", {}).get("paragraphs", [])
        goals = {"actor_a": len(lines) >= 2 and lines[0] == U_A_INITIAL,
                 "actor_b": len(lines) >= 2 and lines[1] == U_B_FINAL}
        integrity = {
            "actor_a": len(lines) == 3 and lines[2] == "KEEP GUARD"
                and lines[1] == (U_B_FINAL if "actor_b" in active_actors else U_B_INITIAL),
            "actor_b": len(lines) == 3 and lines[2] == "KEEP GUARD"
                and lines[0] == U_A_INITIAL,
        }
    else:
        raise ValueError(f"unknown matrix workflow {task_id!r}")
    if not active_actors or any(actor not in {"actor_a", "actor_b"} for actor in active_actors):
        raise ValueError("active_actors must be a nonempty subset of actor_a/actor_b")
    active_goals = {actor: goals[actor] for actor in active_actors}
    active_integrity = {actor: integrity[actor] for actor in active_actors}
    return {"task_id": task_id, "active_actors": list(active_actors),
            "actor_goal_success": active_goals,
            "non_target_integrity": active_integrity,
            "joint_success": all(active_goals.values()) and all(active_integrity.values()),
            "actual_state": actual}


@dataclass(frozen=True)
class WorkflowContract:
    task_id: str

    @property
    def manifest(self) -> dict[str, Any]:
        return task_manifest(self.task_id)

    @property
    def fixture_sha256(self) -> str:
        return fixture_hash(self.task_id)

    def evaluate(self, actual: dict[str, Any]) -> dict[str, Any]:
        return evaluate(self.task_id, actual)
