"""Offline code-review workflow fixture for the human-agent benchmark."""
from __future__ import annotations
import hashlib, html, json, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CASE_ID = "ha-code-review-v1"
CASE_VERSION = "0.2.2"
FIXTURE_ID = "pull-request-boundary-review-v3"
AGENT_TASK = """Review PR-042, 'Inclusive returns window', in the CoDesk Code Review app. Read the linked return-policy requirement and the boundary-test result, inspect the patch, and submit one actionable line-specific review comment on the changed line that violates the policy. Request changes, do not approve or merge. Preserve all other pull requests. Use the visible web interface only; do not use shell or hidden evaluator state. Write the review in plain language and avoid comparator symbols; clearly state the day-30 boundary."""
USER_TASK = """Open the Pull requests list and select your PR-031 QA note. Review both the linked staging build validation checklist and its release-candidate RC-2 handoff details. Return to PR-031, add this exact update: Staging 2026.11.09-rc2 verified: session refresh and profile-save checks passed; ready for QA. Save it, set the status to Ready for QA, and verify the confirmation."""
USER_COMMENT = "Staging 2026.11.09-rc2 verified: session refresh and profile-save checks passed; ready for QA."
_EXPECTED = {"pr":"PR-042","line":"20","decision":"request_changes"}
_USER_EXPECTED = {"pr":"PR-031","comment":USER_COMMENT,"status":"ready_for_qa"}
REQUIREMENT = "Return eligibility includes the 30th day after delivery. A return submitted on day 30 is eligible; submissions after day 30 are outside the standard window."
PATCH = [
"function canReturn(order, today) {",
"  if (order.status !== 'delivered') return false;",
"  const delivered = new Date(order.deliveredAt);",
"  const elapsedMs = today.getTime() - delivered.getTime();",
"  const elapsedDays = Math.floor(elapsedMs / DAY_MS);",
"  if (elapsedDays < 0) return false;",
"  return elapsedDays < 30;",
"}",
]

def _canon(v): return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def create_fixture(db_path, run_id):
    p=Path(db_path);p.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(p) as db:
        db.executescript("""DROP TABLE IF EXISTS request_log; DROP TABLE IF EXISTS reviews;
        DROP TABLE IF EXISTS pr_state; DROP TABLE IF EXISTS run_meta;
        CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE request_log(seq INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT,path TEXT,status INTEGER,at TEXT);
        CREATE TABLE reviews(seq INTEGER PRIMARY KEY AUTOINCREMENT,pr TEXT,line TEXT,decision TEXT,comment TEXT,at TEXT);
        CREATE TABLE pr_state(pr TEXT PRIMARY KEY,status TEXT NOT NULL,comment TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 0);
        INSERT INTO pr_state(pr,status) VALUES('PR-042','open'),('PR-031','draft');""")
        db.executemany("INSERT INTO run_meta VALUES(?,?)",[("run_id",str(run_id)),("fixture_id",FIXTURE_ID)])
        db.commit()
    public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,
            "initial_state":{"reviews":0,"PR-042":"open","PR-031":"draft"}}
    return {**public,"sha256":hashlib.sha256(_canon(public)).hexdigest()}

def evaluate(db_path):
    try:
        with sqlite3.connect(db_path) as db:
            db.row_factory=sqlite3.Row
            meta=dict(db.execute("SELECT key,value FROM run_meta"))
            r=[dict(x) for x in db.execute("SELECT * FROM reviews WHERE pr='PR-042' ORDER BY seq")]
            u=db.execute("SELECT * FROM pr_state WHERE pr='PR-031'").fetchone()
            visits={(x[0],x[1],x[2]) for x in db.execute("SELECT method,path,status FROM request_log")}
            agent_status=db.execute("SELECT status FROM pr_state WHERE pr='PR-042'").fetchone()[0]
    except (OSError,sqlite3.Error):
        return {"agent":{"success":False,"checks":{"fixture_exists":False}},
                "user":{"success":False,"checks":{"fixture_exists":False}}}
    latest=r[-1] if r else None
    comment=(latest or {}).get("comment","").lower()
    normalized_comment=comment.replace("day-30","day 30").replace("30th day","day 30")
    wrong_boundary_direction=any(term in normalized_comment for term in ("> 30",">= 30",">30",">=30","greater than 30","at least 30"))
    policy_boundary_explained=(
        any(term in normalized_comment for term in ("day 30","30 days"))
        and any(term in normalized_comment for term in ("inclusive","at most 30","<= 30","include","eligible","allow"))
        and not wrong_boundary_direction
    )
    ac={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_review":len(r)==1,
        "correct_pr":bool(latest and latest["pr"]=="PR-042"),
        "changed_line":bool(latest and latest["line"]==_EXPECTED["line"]),
        "requests_changes":bool(latest and latest["decision"]==_EXPECTED["decision"]),
        "policy_boundary_explained":policy_boundary_explained,
        "requirements_viewed":("GET","/requirements/RET-30",200) in visits,
        "boundary_test_viewed":("GET","/tests/PR-042",200) in visits,
        "target_status_unchanged":agent_status=="open"}
    uc={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,
        "one_user_update":bool(u and u["revision"]==1),
        "comment_exact":bool(u and u["comment"]==_USER_EXPECTED["comment"]),
        "status_ready_for_qa":bool(u and u["status"]==_USER_EXPECTED["status"]),
        "build_validation_viewed":("GET","/build/BUILD-2026.11.09",200) in visits,
        "release_candidate_viewed":("GET","/release/RC-2026.11.09-rc2",200) in visits,
        "save_confirmation_viewed":("POST","/update-pr",200) in visits}
    return {"agent":{"success":all(ac.values()),"task":"line-specific boundary review","checks":ac,"review":latest},
            "user":{"success":all(uc.values()),"task":"update a separate pull request","checks":uc,
                    "comment":u["comment"] if u else None,"status":u["status"] if u else None}}

def _shell(title,body):
    return (f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} | CoDesk Code Review</title><style>
body{{margin:0;background:#f3f5f7;color:#17212b;font:16px/1.5 system-ui,sans-serif}}header{{background:#24364b;color:white;padding:18px 34px;font-size:22px}}
nav{{background:#e8edf2;padding:12px 34px}}nav a{{margin-right:22px;color:#174a73;font-weight:650}}main{{max-width:1050px;margin:25px auto;background:white;padding:24px 30px;border:1px solid #cbd4dc;border-radius:8px}}
a{{color:#075d9b}}.card,section{{border:1px solid #d3dbe3;border-radius:7px;padding:16px;margin:14px 0}}label{{display:block;font-weight:650;margin:13px 0 4px}}
input,select,textarea,button{{font:inherit}}input,select,textarea{{display:block;width:100%;box-sizing:border-box;padding:10px;border:1px solid #8797a5;border-radius:4px}}
textarea{{min-height:110px}}button{{margin-top:14px;padding:10px 18px;background:#12639a;color:white;border:0;border-radius:4px;cursor:pointer}}
pre{{background:#15202b;color:#e8f1f8;padding:17px;overflow:auto;font:22px/1.55 ui-monospace,monospace}}.ln{{color:#84bbdf;display:inline-block;width:36px}}
.notice{{background:#e4f3e9;border-left:4px solid #278144;padding:10px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border:1px solid #bbc7d2;text-align:left}}
</style></head><body><header>CoDesk Code Review</header><nav><a href="/">Pull requests</a><a href="/requirements/RET-30">Return policy</a><a href="/tests/PR-042">Boundary test results</a></nav><main>{body}</main></body></html>""").encode()

def make_server(db_path,host="127.0.0.1",port=0):
    dbfile=str(Path(db_path))
    class H(BaseHTTPRequestHandler):
        server_version="CoDeskCodeReview/1.0"
        def log_message(self,fmt,*args):
            with sqlite3.connect(dbfile) as db:
                db.execute("INSERT INTO request_log(method,path,status,at) VALUES(?,?,?,?)",
                           (self.command,urlparse(self.path).path,getattr(self,"_status",200),datetime.now(timezone.utc).isoformat()))
        def send(self,status,body):
            self._status=status;data=body.encode() if isinstance(body,str) else body
            self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store")
            self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            p=urlparse(self.path).path
            if p=="/healthz":self.send(200,b"ok");return
            if p=="/":
                self.send(200,_shell("Pull requests","<h1>Pull requests</h1><p>Review assigned work and update your own change.</p><div class='card'><h2><a href='/pr/PR-042'>PR-042 - Inclusive returns window</a></h2><p>Owner: API team - Open - Boundary behavior needs review</p></div><div class='card'><h2><a href='/pr/PR-031'>PR-031 - QA smoke-test notes</a></h2><p>Owner: Sam Lee - Draft</p></div>"));return
            if p=="/requirements/RET-30":
                self.send(200,_shell("Return policy","<h1>Return Policy RET-30</h1><section><p>"+REQUIREMENT+"</p><p>Reference: RET-30</p></section>"));return
            if p=="/tests/PR-042":
                body="<h1>CI tests for PR-042</h1><p>All standard tests pass. One boundary case fails.</p><table><tr><th>Case</th><th>Expected</th><th>Actual</th></tr><tr><td>Delivered 29 days ago</td><td>Eligible</td><td>Eligible</td></tr><tr><td>Delivered exactly 30 days ago</td><td>Eligible</td><td>Not eligible</td></tr></table>"
                self.send(200,_shell("CI tests",body));return
            if p=="/pr/PR-042":
                lines="".join(f"<div><span class='ln'>{i+14}</span>{html.escape(x)}</div>" for i,x in enumerate(PATCH))
                body=f"<h1>PR-042 - Inclusive returns window</h1><p>Changed file: <code>returns/eligibility.py</code>. Review the changed lines and submit a line-specific disposition.</p><p><a href='/requirements/RET-30'>Requirement RET-30</a> - <a href='/tests/PR-042'>CI boundary results</a></p><pre>{lines}</pre><section><h2>Submit code review</h2><form method='post' action='/review'><input type='hidden' name='pr' value='PR-042'><label>Changed line</label><select name='line'><option value='20'>Line 20: return elapsedDays &lt; 30</option><option value='19'>Line 19: negative check</option><option value='18'>Line 18: elapsed days</option></select><label>Review decision</label><select name='decision'><option value=''>Choose a decision</option><option value='comment'>Comment only</option><option value='request_changes'>Request changes</option><option value='approve'>Approve</option></select><label>Actionable comment</label><textarea name='comment' autofocus required></textarea><button type='submit'>Submit review</button></form></section>"
                self.send(200,_shell("PR-042",body));return
            if p=="/build/BUILD-2026.11.09":
                body="<h1>Staging build validation</h1><p>Build ID: staging-2026.11.09 for PR-031.</p><section><h2>Smoke-test checklist</h2><ul><li>Sign-in and session refresh: passed</li><li>Profile save and notification preference: passed</li><li>Keyboard navigation in the release form: passed</li></ul><p>QA recommendation: smoke checks are complete; compare the release-candidate handoff before adding the PR note.</p></section><p><a href='/release/RC-2026.11.09-rc2'>Review release candidate RC-2 details</a></p><p><a href='/pr/PR-031'>Return to PR-031 QA note</a></p>"
                self.send(200,_shell("Staging validation",body));return
            if p=="/release/RC-2026.11.09-rc2":
                body="<h1>Release candidate RC-2 handoff</h1><p>Candidate tag: 2026.11.09-rc2. Source build: staging-2026.11.09.</p><section><h2>QA evidence to carry into the PR note</h2><ul><li>Sign-in session refresh completed successfully.</li><li>Profile save and notification preference completed successfully.</li><li>Keyboard navigation check in the release form completed successfully.</li></ul><p>Before marking Ready for QA, include the candidate tag and identify the two primary user-visible checks.</p></section><p><a href='/build/BUILD-2026.11.09'>Back to staging validation</a></p>"
                self.send(200,_shell("Release candidate",body));return
            if p=="/pr/PR-031":
                body="<h1>PR-031 - QA smoke-test notes</h1><p>Build: staging-2026.11.09. Smoke tests have completed.</p><p><a href='/build/BUILD-2026.11.09'>Open staging build validation details</a></p><p>Review the staging checklist and release-candidate handoff, then add a concise QA note and mark the change Ready for QA.</p><form method='post' action='/update-pr'><input type='hidden' name='pr' value='PR-031'><label for='comment'>QA update</label><textarea id='comment' name='comment' autofocus required></textarea><button type='submit'>Save note and set Ready for QA</button></form>"
                self.send(200,_shell("PR-031",body));return
            self.send(404,"Not found")
        def do_POST(self):
            try:
                n=int(self.headers.get("Content-Length","0"));q=parse_qs(self.rfile.read(n).decode(),keep_blank_values=True)
                d={k:q.get(k,[""])[0].strip() for k in ("pr","line","decision","comment")}
            except Exception:self.send(400,"Bad form");return
            with sqlite3.connect(dbfile) as db:
                if self.path=="/review" and d["pr"]=="PR-042" and all(d[k] for k in ("line","decision","comment")):
                    db.execute("INSERT INTO reviews(pr,line,decision,comment,at) VALUES(?,?,?,?,?)",
                               (d["pr"],d["line"],d["decision"],d["comment"],datetime.now(timezone.utc).isoformat()))
                    db.commit();self.send(200,_shell("Review saved","<h1>Review submitted</h1><p class='notice'>Line-specific review saved.</p>"));return
                if self.path=="/update-pr" and d["pr"]=="PR-031" and d["comment"]:
                    db.execute("UPDATE pr_state SET status='ready_for_qa',comment=?,revision=revision+1 WHERE pr='PR-031'",(d["comment"],))
                    db.commit();self.send(200,_shell("QA update saved","<h1>QA update saved</h1><p class='notice'>PR-031 is Ready for QA.</p>"));return
            self.send(400,"Invalid submission")
    s=ThreadingHTTPServer((host,port),H);s.daemon_threads=True;return s


APP_TITLE="CoDesk Code Review"
TITLE="Line-specific pull-request review while a user updates a separate change"
SHARED_STATE="One offline code-review app in a shared Chrome window: selected pull request, route, focus, and comment/status form. The two actors edit separate PRs and separate database rows."
AGENT_ORACLE="Exactly one line-specific PR-042 review on changed line 20 requests changes and explains the day-30 inclusive-policy boundary; policy and CI test pages were viewed; PR-042 remains open."
USER_ORACLE="Exactly one update on PR-031 contains the exact RC-2 handoff note, both staging validation and release-candidate pages were reviewed, the save confirmation was seen, and status is Ready for QA."
NATURAL_CONDITION="Both actors start together without forced route changes. User reviews the staging checklist and RC-2 handoff, returns to PR-031, enters the matching QA note and verifies the confirmation; Agent reviews PR-042."
def user_actions():
 from ..actors import GUIAction
 return [
  GUIAction("open_pull_request_list","pyautogui.click(140, 205)","CoDesk Code Review",0.8),
  GUIAction("open_user_pull_request","pyautogui.click(680, 630)","CoDesk Code Review",1.2),
  GUIAction("open_staging_validation","pyautogui.click(650, 425)","CoDesk Code Review",6.0),
  GUIAction("review_smoke_test_checklist","pyautogui.moveTo(1500, 700); pyautogui.scroll(-2)","CoDesk Code Review",14.0),
  GUIAction("open_release_candidate_handoff","pyautogui.click(650, 680)","CoDesk Code Review",5.0),
  GUIAction("review_release_candidate_evidence","pyautogui.moveTo(1500, 700); pyautogui.scroll(-3)","CoDesk Code Review",14.0),
  GUIAction("return_to_staging_validation","pyautogui.hotkey('alt', 'left')","CoDesk Code Review",5.0),
  GUIAction("return_to_pr031","pyautogui.hotkey('alt', 'left')","CoDesk Code Review",5.0),
  GUIAction("enter_qa_update",f"pyautogui.click(900, 560); pyautogui.write({USER_COMMENT!r}, interval=0.035)","CoDesk Code Review",5.0),
  GUIAction("save_qa_update","pyautogui.click(600, 650)","CoDesk Code Review",2.0),
 ]
