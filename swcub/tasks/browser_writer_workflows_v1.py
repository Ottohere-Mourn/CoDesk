"""Fixed Browser+Writer workflow contracts for C-02 and F-02.

The hidden Browser state, clipboard observer and saved ODF oracle remain runner-side.
Actors see screenshots and execute GUI actions only.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any
import xml.etree.ElementTree as ET

from ..environment import ActorContext
from ..task_factory import render_writer_fodt

OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
XLINK_NS = "http://www.w3.org/1999/xlink"
A_URL = "https://example.org/codesk/reference-a"
B_URL = "https://example.org/codesk/reference-b"
COMMENT = "Review note 482"
CASE = "CASE-901"
DECISION = "APPROVE"
WRITER_DOCK = (35, 335)
BROWSER_DOCK = (35, 60)
C02_A_SOURCE = (300, 300)
C02_B_SOURCE = (300, 390)
C02_B_DEST = (300, 480)
C02_SUBMIT = (250, 565)
F02_CASE_INPUT = (300, 300)
F02_DECISION_INPUT = (300, 390)
F02_SUBMIT = (250, 480)
LINK_URL_INPUT = (1050, 480)
LINK_OK = (1275, 795)


@dataclass(frozen=True)
class BrowserWriterWorkflow:
    key: str
    family: str
    version: str
    port: int
    writer_initial: tuple[str, str]
    actor_a_goal: str
    actor_b_goal: str

    @property
    def root(self) -> str:
        return f"/tmp/codesk_browser_writer/{self.key.lower()}"

    @property
    def writer_path(self) -> str:
        return f"{self.root}/writer.fodt"

    @property
    def state_path(self) -> str:
        return f"{self.root}/state.json"

    @property
    def server_path(self) -> str:
        return f"{self.root}/server.py"

    @property
    def events_path(self) -> str:
        return f"{self.root}/events.jsonl"

    @property
    def profile_path(self) -> str:
        return f"{self.root}/profile"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/workspace"

    def browser_initial(self) -> dict[str, Any]:
        return {"submission": {}, "revision": 0}

    def browser_expected(self) -> dict[str, str]:
        return {"url": B_URL} if self.key == "C-02" else {"case": CASE, "decision": DECISION}

    def html(self) -> str:
        if self.key == "C-02":
            return ('''<!doctype html><meta charset="utf-8"><title>CoDesk C-02 transfer</title>
<style>body{font:20px Arial;margin:24px}label{display:block}
input{position:absolute;left:100px;width:520px;height:48px;font:20px Arial}
#source-a{top:160px}#source-b{top:250px}#dest-b{top:340px}
#submit{position:absolute;left:100px;top:425px;width:180px;height:48px;font:20px Arial}</style>
<h1>Link transfer workspace</h1><p>Copy Source A for Writer; copy Source B for this form.</p>
<input id="source-a" aria-label="Source A URL" readonly value="__A_URL__">
<input id="source-b" aria-label="Source B URL" readonly value="__B_URL__">
<input id="dest-b" aria-label="Destination B URL" autocomplete="off">
<button id="submit" onclick="submitGoal()">Save B URL</button><output id="result"></output>
<script>async function submitGoal(){let url=document.querySelector('#dest-b').value;
let r=await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
document.querySelector('#result').textContent=r.ok?'Saved':'Rejected';}</script>'''
                    .replace("__A_URL__", A_URL).replace("__B_URL__", B_URL))
        return '''<!doctype html><meta charset="utf-8"><title>CoDesk F-02 review</title>
<style>body{font:20px Arial;margin:24px}input{position:absolute;left:100px;width:480px;height:48px;font:20px Arial}
#case{top:160px}#decision{top:250px}
#submit{position:absolute;left:100px;top:340px;width:180px;height:48px;font:20px Arial}</style>
<h1>Review submission</h1><p>Case CASE-901; decision APPROVE.</p>
<input id="case" aria-label="Case ID" autocomplete="off">
<input id="decision" aria-label="Decision" autocomplete="off">
<button id="submit" onclick="submitGoal()">Submit review</button><output id="result"></output>
<script>async function submitGoal(){let p={case:document.querySelector('#case').value,
decision:document.querySelector('#decision').value};
let r=await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
document.querySelector('#result').textContent=r.ok?'Saved':'Rejected';}</script>'''

    def server_source(self) -> bytes:
        source = r'''from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone
from pathlib import Path
import json
STATE=Path(__STATE__)
EVENTS=STATE.with_name("events.jsonl")
HTML=__HTML__
STATE.parent.mkdir(parents=True,exist_ok=True)
def event(row):
 row["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(row,sort_keys=True)+"\n")
class Handler(BaseHTTPRequestHandler):
 def reply(self,data,status=200):
  raw=json.dumps(data).encode()
  self.send_response(status);self.send_header("Content-Type","application/json")
  self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path!="/workspace":return self.reply({"error":"not found"},404)
  raw=HTML.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
  self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
  event({"kind":"page_loaded"});return
 def do_POST(self):
  if self.path!="/submit":return self.reply({"error":"not found"},404)
  try:p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
  except Exception:return self.reply({"error":"bad JSON"},400)
  s=json.loads(STATE.read_text());s["submission"]=p;s["revision"]+=1
  STATE.write_text(json.dumps(s,sort_keys=True))
  event({"kind":"form_submitted","submission":p,"revision":s["revision"]})
  return self.reply({"ok":True})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",__PORT__),Handler).serve_forever()
'''
        return (source.replace("__STATE__", repr(self.state_path))
                .replace("__HTML__", repr(self.html()))
                .replace("__PORT__", str(self.port))).encode()

    def files(self) -> dict[str, bytes]:
        state = (json.dumps(self.browser_initial(), sort_keys=True) + "\n").encode()
        return {self.writer_path: render_writer_fodt(list(self.writer_initial)),
                self.state_path: state, self.server_path: self.server_source()}

    def fixture_sha256(self) -> str:
        digest = sha256()
        for path, data in sorted(self.files().items()):
            digest.update(path.encode() + b"\0" + data)
        return digest.hexdigest()

    def manifest(self) -> dict[str, Any]:
        return {"template_id": self.key, "version": self.version, "family": self.family,
                "actor_goals": {"actor_a": self.actor_a_goal, "actor_b": self.actor_b_goal},
                "applications": ["Chromium", "LibreOffice Writer"],
                "initial_state": {"writer_paragraphs": list(self.writer_initial),
                                  "browser": self.browser_initial()},
                "expected_browser": self.browser_expected(),
                "fixture_sha256": self.fixture_sha256(),
                "condition_contract": {
                    "solo": "one actor in one clean Guest",
                    "ma_id": "two Guests, equal fixture digest, separate desktops and clipboards",
                    "ma_sd": "one Guest, one desktop and clipboard",
                    "schedule": ["actor_a.copy_or_select", "actor_b.complete", "actor_a.resume"],
                    "recovery": "actor_a reacquires source/target through GUI",
                    "backend_visibility_required": False}}

    def parse_writer(self, xml: str) -> dict[str, Any]:
        root = ET.fromstring(xml)
        body = root.find(f".//{{{OFFICE_NS}}}body/{{{OFFICE_NS}}}text")
        if body is None:
            raise ValueError("Writer ODF has no text body")
        paras = body.findall(f"{{{TEXT_NS}}}p")
        if len(paras) != 2:
            return {"paragraph_count": len(paras), "valid_structure": False}
        first, guard = paras
        guard_text = "".join(guard.itertext())
        if self.key == "C-02":
            links = first.findall(f".//{{{TEXT_NS}}}a")
            return {"paragraph_count": 2, "visible_text": "".join(first.itertext()),
                    "guard_text": guard_text,
                    "links": [{"text": "".join(link.itertext()),
                               "href": link.get(f"{{{XLINK_NS}}}href")} for link in links],
                    "annotations": len(first.findall(f".//{{{OFFICE_NS}}}annotation")),
                    "valid_structure": True}
        annotations = first.findall(f"{{{OFFICE_NS}}}annotation")
        ends = first.findall(f"{{{OFFICE_NS}}}annotation-end")
        anchor = (first.text or "") + "".join(child.tail or "" for child in first)
        return {"paragraph_count": 2, "anchor_text": anchor,
                "guard_text": guard_text,
                "annotations": [{"name": row.get(f"{{{OFFICE_NS}}}name"),
                                 "body": "\n".join("".join(p.itertext())
                                     for p in row.findall(f".//{{{TEXT_NS}}}p"))}
                                for row in annotations],
                "annotation_end_names": [row.get(f"{{{OFFICE_NS}}}name") for row in ends],
                "links": len(first.findall(f".//{{{TEXT_NS}}}a")),
                "valid_structure": True}

    def writer_initial_ok(self, parsed: dict[str, Any]) -> bool:
        if self.key == "C-02":
            return (parsed.get("valid_structure") is True and
                parsed.get("visible_text") == self.writer_initial[0] and
                parsed.get("guard_text") == self.writer_initial[1] and
                parsed.get("links") == [] and parsed.get("annotations") == 0)
        return (parsed.get("valid_structure") is True and
            parsed.get("anchor_text") == self.writer_initial[0] and
            parsed.get("guard_text") == self.writer_initial[1] and
            parsed.get("annotations") == [] and
            parsed.get("annotation_end_names") == [] and parsed.get("links") == 0)

    def writer_goal_ok(self, parsed: dict[str, Any]) -> bool:
        if self.key == "C-02":
            return (parsed.get("valid_structure") is True and
                parsed.get("visible_text") == self.writer_initial[0] and
                parsed.get("guard_text") == self.writer_initial[1] and
                parsed.get("links") == [{"text": self.writer_initial[0], "href": A_URL}] and
                parsed.get("annotations") == 0)
        annotations = parsed.get("annotations")
        return (parsed.get("valid_structure") is True and
            parsed.get("anchor_text") == self.writer_initial[0] and
            parsed.get("guard_text") == self.writer_initial[1] and
            isinstance(annotations, list) and len(annotations) == 1 and
            annotations[0]["body"] == COMMENT and
            annotations[0]["name"] in parsed.get("annotation_end_names", []) and
            len(parsed.get("annotation_end_names", [])) == 1 and parsed.get("links") == 0)

    def evaluate(self, *, condition: str, writer_xml: dict[str, str],
                 browser_state: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if condition not in {"solo_a", "solo_b", "ma_id", "ma_sd"}:
            raise ValueError("unknown condition")
        active = ("actor_a", "actor_b") if condition in {"ma_id", "ma_sd"} else (
            ("actor_a",) if condition == "solo_a" else ("actor_b",))
        binding = lambda actor: "shared" if condition == "ma_sd" else actor
        actual_writer = {key: self.parse_writer(xml) for key, xml in writer_xml.items()}
        goal, integrity = {}, {}
        for actor in active:
            row = actual_writer[binding(actor)]
            browser = browser_state[binding(actor)]
            if actor == "actor_a":
                goal[actor] = self.writer_goal_ok(row)
                integrity[actor] = (condition == "ma_sd" or browser == self.browser_initial())
            else:
                goal[actor] = (browser.get("submission") == self.browser_expected() and
                               browser.get("revision") == 1)
                integrity[actor] = (condition == "ma_sd" or self.writer_initial_ok(row))
        success = all(goal.values()) and all(integrity.values())
        return {"template_id": self.key, "active_actors": list(active),
                "actor_goal_success": goal, "non_target_integrity": integrity,
                "condition_success": success, "joint_success": success if len(active) == 2 else None,
                "writer_state": actual_writer, "browser_state": browser_state,
                "writer_initial_ok": {k: self.writer_initial_ok(v) for k,v in actual_writer.items()},
                "writer_goal_ok": {k: self.writer_goal_ok(v) for k,v in actual_writer.items()}}


C02 = BrowserWriterWorkflow(
    "C-02", "clipboard_state", "0.1.0", 8768,
    ("Reference link", "Guard paragraph"),
    "Copy Source A URL from Browser, make the selected Writer label a hyperlink with that exact href, save; preserve the guard.",
    "Copy Source B URL into the Browser destination form and submit it exactly once.")
F02 = BrowserWriterWorkflow(
    "F-02", "focus_input_routing", "0.1.0", 8769,
    ("Review anchor", "Guard paragraph"),
    "Attach the exact review comment to the selected Writer anchor and save; preserve document text.",
    "Fill both Browser review fields and submit the exact case and decision once.")
WORKFLOWS = {"C-02": C02, "F-02": F02}


class ScriptedBrowserWriterActor:
    role = "gui"

    def __init__(self, workflow: BrowserWriterWorkflow, actor_id: str, *, recovery: bool):
        if actor_id not in {"actor_a", "actor_b"}:
            raise ValueError("unknown actor")
        self.workflow, self.actor_id, self.recovery, self.turn = workflow, actor_id, recovery, 0

    @staticmethod
    def _observe(context: ActorContext) -> None:
        shot = context.observe().get("screenshot")
        if not isinstance(shot, bytes) or not shot:
            raise RuntimeError("no real Guest screenshot")

    def _copy_a_source(self, context: ActorContext) -> None:
        context.click(*BROWSER_DOCK)
        self._observe(context)
        context.click(*C02_A_SOURCE)
        context.press_key("ctrl+a")
        context.press_key("ctrl+c")

    def run_step(self, context: ActorContext) -> bool:
        wf = self.workflow.key
        if self.actor_id == "actor_b":
            if self.turn:
                raise RuntimeError("extra B turn")
            context.click(*BROWSER_DOCK)
            self._observe(context)
            if wf == "C-02":
                context.click(*C02_B_SOURCE)
                context.press_key("ctrl+a")
                context.press_key("ctrl+c")
                context.click(*C02_B_DEST)
                context.press_key("ctrl+v")
                context.click(*C02_SUBMIT)
            else:
                context.click(*F02_CASE_INPUT)
                context.type_text(CASE)
                context.click(*F02_DECISION_INPUT)
                context.type_text(DECISION)
                context.click(*F02_SUBMIT)
            self.turn = 1
            return True
        if self.turn == 0:
            if wf == "C-02":
                self._copy_a_source(context)
            else:
                context.click(*WRITER_DOCK)
                self._observe(context)
                context.press_key("ctrl+home")
                context.press_key("shift+end")
            self.turn = 1
            return False
        if self.turn != 1:
            raise RuntimeError("extra A turn")
        if wf == "C-02":
            if self.recovery:
                self._copy_a_source(context)
            context.click(*WRITER_DOCK)
            self._observe(context)
            context.press_key("ctrl+home")
            context.press_key("shift+end")
            context.press_key("ctrl+k")
            context.click(*LINK_URL_INPUT)
            context.press_key("ctrl+v")
            context.click(*LINK_OK)
            context.press_key("ctrl+s")
        else:
            if self.recovery:
                context.click(*WRITER_DOCK)
                self._observe(context)
                context.press_key("ctrl+home")
                context.press_key("shift+end")
            context.press_key("ctrl+alt+c")
            context.type_text(COMMENT)
            context.press_key("ctrl+s")
        self.turn = 2
        return True
