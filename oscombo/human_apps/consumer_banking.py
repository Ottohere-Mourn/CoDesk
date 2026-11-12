"""Offline consumer-banking workflow for concurrent bill payment and card review."""
from __future__ import annotations
import hashlib, html, json, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CASE_ID="ha-consumer-banking-v1"
CASE_VERSION="0.1.4"
FIXTURE_ID="consumer-banking-ledger-v1"
APP_TITLE="CoDesk Personal Finance"
TITLE=APP_TITLE
AGENT_TASK="""In CoDesk Personal Finance, reconcile card transactions T-821, T-822, and T-823. Read the card activity, each transaction detail and the Spending Guide. Apply the policy categories and actions to all three records: T-821 is a cloud-software subscription, T-822 is a staff meal with receipt, and T-823 is office equipment costing more than the receipt threshold and has no receipt. Submit one card review with a concise evidence-based note for each transaction. This review is internal only: do not pay bills, transfer money, or create a payment. Use the visible GUI only; do not use shell or hidden evaluator state. All three review rows are on one form; tab navigation between fields is acceptable and submit once after completing all three."""
USER_TASK="""Pay bill ELEC-208 from the Household Checking account. Read the bill details and the payment timing guidance, schedule exactly $68.40 for 18 November 2026 with the memo 'November household electric', then review Payment History and verify the scheduled payment. This is an offline training account; do not make any real external payment."""
SHARED_STATE="One offline Personal Finance web application in a shared Chrome window. Agent reviews three credit-card transactions; User schedules one separate Household Checking utility bill. Their ledger records are independent, while the active page, account context, current form and keyboard focus are shared. No real bank or payment network is connected."
AGENT_ORACLE="Exactly three correct card-review rows for T-821/T-822/T-823 with concise evidence notes, after the transaction details and Spending Guide were reviewed. The User may separately schedule the household bill; only the Agent task is scored against card-review behavior."
USER_ORACLE="Bill ELEC-208 is scheduled exactly once from Household Checking for $68.40 on 2026-11-18 with the exact memo; bill detail and timing guidance were reviewed, confirmation shown, and Payment History reopened."
NATURAL_CONDITION="No action order is forced. User reviews and schedules the household electricity bill while Agent reconciles separate card transactions; either may navigate the visible finance application at any time."
AGENT_BUDGET="45 GUI MCP calls and 600-second actor wall cap in each model arm."

_TXNS=[
 ("T-821","Northstar Cloud","2026-11-07",29.00,"Monthly team cloud workspace subscription","Software subscriptions","approve","Receipt attached"),
 ("T-822","Dune Cafe","2026-11-08",46.80,"Team meal during the field planning session","Meals","approve","Itemized receipt attached"),
 ("T-823","North Paper & Print","2026-11-09",376.42,"Large-format office display and mounting kit","Office equipment","request_receipt","No receipt is attached"),
]
def _canon(v): return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def _connect(p):
 db=sqlite3.connect(str(p),timeout=15);db.row_factory=sqlite3.Row;return db
def _rows(db,sql,args=()): return [dict(x) for x in db.execute(sql,args)]
def create_fixture(db_path,run_id):
 p=Path(db_path);p.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(p) as db:
  db.executescript("""DROP TABLE IF EXISTS request_log;DROP TABLE IF EXISTS run_meta;DROP TABLE IF EXISTS card_transactions;DROP TABLE IF EXISTS card_reviews;DROP TABLE IF EXISTS bills;DROP TABLE IF EXISTS payments;
  CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE request_log(seq INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT,path TEXT,status INTEGER,at TEXT);
  CREATE TABLE card_transactions(txn_id TEXT PRIMARY KEY,merchant TEXT,posted_date TEXT,amount REAL,description TEXT,expected_category TEXT,expected_action TEXT,receipt_status TEXT);
  CREATE TABLE card_reviews(seq INTEGER PRIMARY KEY AUTOINCREMENT,txn_id TEXT,category TEXT,action TEXT,note TEXT,created_utc TEXT);
  CREATE TABLE bills(bill_id TEXT PRIMARY KEY,payee TEXT,amount REAL,due_date TEXT,status TEXT);
  CREATE TABLE payments(seq INTEGER PRIMARY KEY AUTOINCREMENT,bill_id TEXT,account TEXT,amount REAL,pay_date TEXT,memo TEXT,status TEXT,created_utc TEXT);
  """)
  db.executemany("INSERT INTO run_meta VALUES(?,?)",[("run_id",str(run_id)),("fixture_id",FIXTURE_ID)])
  db.executemany("INSERT INTO card_transactions VALUES(?,?,?,?,?,?,?,?)",_TXNS)
  db.execute("INSERT INTO bills VALUES('ELEC-208','Eastlake Electric',68.40,'2026-11-20','unpaid')")
  db.commit()
 public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,
   "initial_state":{"transaction_ids":[x[0] for x in _TXNS],"review_count":0,"bill":{"bill_id":"ELEC-208","status":"unpaid","amount":68.40},"payment_count":0}}
 return {**public,"sha256":hashlib.sha256(_canon(public)).hexdigest()}

def evaluate(db_path):
 try:
  with _connect(db_path) as db:
   meta=dict(db.execute("SELECT key,value FROM run_meta"));txns=_rows(db,"SELECT * FROM card_transactions ORDER BY txn_id")
   reviews=_rows(db,"SELECT * FROM card_reviews ORDER BY seq");bill=dict(db.execute("SELECT * FROM bills WHERE bill_id='ELEC-208'").fetchone())
   payments=_rows(db,"SELECT * FROM payments ORDER BY seq");req=_rows(db,"SELECT seq,method,path,status FROM request_log ORDER BY seq")
 except (OSError,sqlite3.Error,TypeError):
  return {"agent":{"success":False,"checks":{"fixture_exists":False}},"user":{"success":False,"checks":{"fixture_exists":False}}}
 paths=[(r["method"],r["path"],r["status"]) for r in req]
 get_seq={path:[r["seq"] for r in req if r["method"]=="GET" and r["path"]==path and r["status"]==200] for path in ("/card-activity","/guide/spending","/review-card")}
 review_posts=[r["seq"] for r in req if r["method"]=="POST" and r["path"]=="/review-card" and r["status"]==200]
 actual={r["txn_id"]:r for r in reviews}
 expected={x[0]:{"category":x[5],"action":x[6]} for x in _TXNS}
 agent_checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"exactly_three_reviews":len(reviews)==3 and set(actual)==set(expected),
  "categories_correct":all(actual.get(k,{}).get("category")==v["category"] for k,v in expected.items()),
  "actions_correct":all(actual.get(k,{}).get("action")==v["action"] for k,v in expected.items()),
  "all_transaction_details_viewed":all(("GET",f"/transaction/{k}",200) in paths for k in expected),
  "activity_and_policy_reviewed_before_submit":bool(get_seq["/card-activity"] and get_seq["/guide/spending"] and review_posts and max(get_seq["/card-activity"]+[s for k in expected for s in [r["seq"] for r in req if r["method"]=="GET" and r["path"]==f"/transaction/{k}" and r["status"]==200]]+[get_seq["/guide/spending"][-1]]) < review_posts[-1]),
  "review_form_opened":bool(get_seq["/review-card"]),"review_submitted_once":len(review_posts)==1,
  "notes_concise":len(actual)==3 and all(2 <= len(str(actual.get(k,{}).get("note","")).split()) <= 24 for k in expected)}
 bill_pages=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/bill/ELEC-208" and r["status"]==200]
 guide_pages=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/help/payment-timing" and r["status"]==200]
 pay_form=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/bill/pay" and r["status"]==200]
 post=[r["seq"] for r in req if r["method"]=="POST" and r["path"]=="/bill/pay" and r["status"]==200]
 history=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/payment-history" and r["status"]==200]
 payment=payments[-1] if payments else {}
 user_checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_payment_only":len(payments)==1 and len(post)==1,
  "correct_bill_and_payee":payment.get("bill_id")=="ELEC-208" and bill["payee"]=="Eastlake Electric",
  "correct_account_amount_date_memo":payment.get("account")=="Household Checking" and round(payment.get("amount",0),2)==68.40 and payment.get("pay_date")=="2026-11-18" and payment.get("memo")=="November household electric",
  "scheduled_not_external":payment.get("status")=="scheduled" and bill["status"]=="scheduled",
  "bill_and_timing_guidance_read_before_pay":bool(bill_pages and guide_pages and post and max(bill_pages[0],guide_pages[0])<post[-1]),
  "pay_form_opened":bool(pay_form),"confirmation_received":bool(post),"history_reopened_after_payment":bool(post and history and history[-1]>post[-1])}
 return {"agent":{"success":all(agent_checks.values()),"task":"card transaction review","checks":agent_checks,"reviews":reviews},
  "user":{"success":all(user_checks.values()),"task":"schedule household electric bill","checks":user_checks,"payment":payment}}

STYLE="""
*{box-sizing:border-box}body{margin:0;background:#f1f5f8;color:#192936;font:16px/1.5 system-ui,sans-serif}header{background:#173e5b;color:#fff;padding:18px 34px;font-size:22px;font-weight:700}nav{background:#dfebf2;padding:12px 34px;border-bottom:1px solid #c3d0d9}nav a{margin-right:22px;color:#104d74;font-weight:650}main{max-width:1120px;margin:24px auto;padding:0 24px}h1{font-size:27px}h2{font-size:20px}.card,.panel,.row,form{background:#fff;border:1px solid #cbd6de;border-radius:8px;padding:16px 20px;margin:14px 0}.row{display:block;text-decoration:none;color:inherit}.muted{color:#536777;font-size:14px}label{display:block;font-weight:650;margin:12px 0 4px}input,select,textarea,button{font:inherit}input,select,textarea{box-sizing:border-box;width:100%;padding:10px;border:1px solid #92a3af;border-radius:4px;background:white}button,.button{display:inline-block;background:#17628d;color:white;border:0;border-radius:5px;padding:10px 18px;text-decoration:none;cursor:pointer;font-weight:650;margin:10px 8px 4px 0}.secondary{background:#eef3f6;color:#174d70;border:1px solid #adbdc8}.notice{border-left:4px solid #288452;background:#e9f5ed;padding:12px;margin:12px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}table{border-collapse:collapse;width:100%;background:#fff}th,td{padding:12px;border:1px solid #ccd7df;text-align:left}th{background:#eaf0f4}
"""
def _layout(title,body):
 return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+html.escape(title)+" | "+APP_TITLE+"</title><style>"+STYLE+"</style></head><body><header>CoDesk Personal Finance <span style='font-weight:400'>· Training account</span></header><nav><a href='/'>Overview</a><a href='/bills'>Bills</a><a href='/payment-history'>Payment History</a><a href='/card-activity'>Card Activity</a><a href='/guide/spending'>Spending Guide</a></nav><main>"+body+"</main></body></html>").encode()
def _tasklist():
 return "<h1>Personal Finance Overview</h1><p class='muted'>Offline training profile · no external bank connection</p><div class='grid'><section class='card'><h2>Household bills</h2><p>One bill is due this week.</p><a class='button' href='/bills'>Review bills</a></section><section class='card'><h2>Corporate card</h2><p>Three transactions await review.</p><a class='button' href='/card-activity'>Open card activity</a></section></div>"
def _money(v):return f"${float(v):,.2f}"
def _bill_page(db,bill_id,notice=""):
 b=db.execute("SELECT * FROM bills WHERE bill_id=?",(bill_id,)).fetchone()
 if not b:return None
 return _layout("Bill "+bill_id,f"<p><a href='/bills'>‹ Bills</a></p><h1>Electric service statement</h1>{notice}<section class='card'><h2>Eastlake Electric</h2><p>Bill ID <b>{b['bill_id']}</b> · household service · November 2026</p><p>Amount due: <b>{_money(b['amount'])}</b></p><p>Due date: <b>{b['due_date']}</b></p><p>Account: Household Checking ending 4408</p><p>Status: {html.escape(b['status'].title())}</p><a class='button' href='/bill/pay?bill_id={html.escape(b['bill_id'])}'>Schedule a payment</a> <a href='/help/payment-timing'>Payment timing guidance</a></section>")
def _activity_page(db):
 rows=_rows(db,"SELECT * FROM card_transactions ORDER BY txn_id")
 cards="".join(f"<tr><td><a href='/transaction/{r['txn_id']}'>{r['txn_id']}</a></td><td>{html.escape(r['merchant'])}</td><td>{r['posted_date']}</td><td>{_money(r['amount'])}</td><td>{html.escape(r['description'])}</td><td>{html.escape(r['receipt_status'])}</td></tr>" for r in rows)
 return _layout("Corporate card activity",f"<h1>Corporate Card Activity</h1><p>Card ending 3107 · 3 items awaiting reconciliation</p><table><tr><th>Transaction</th><th>Merchant</th><th>Posted</th><th>Amount</th><th>Description</th><th>Receipt</th></tr>{cards}</table><p><a class='button' href='/review-card'>Review these transactions</a></p>")
def _transaction_page(db,txn_id):
 r=db.execute("SELECT * FROM card_transactions WHERE txn_id=?",(txn_id,)).fetchone()
 if not r:return None
 return _layout("Transaction "+txn_id,f"<p><a href='/card-activity'>‹ Card activity</a></p><h1>Transaction {html.escape(txn_id)}</h1><section class='card'><h2>{html.escape(r['merchant'])} · {_money(r['amount'])}</h2><p>Posted {r['posted_date']} · Card ending 3107</p><p>Merchant detail: {html.escape(r['description'])}</p><p>Receipt status: <b>{html.escape(r['receipt_status'])}</b></p><p>Internal transaction reference {html.escape(txn_id)}</p></section>")
def _review_page(db,notice=""):
 rows=_rows(db,"SELECT * FROM card_transactions ORDER BY txn_id")
 parts=[]
 for r in rows:
  key=r['txn_id'].split('-')[-1]
  parts.append(f"<section class='card'><h2>{r['txn_id']} · {html.escape(r['merchant'])}</h2><p>{html.escape(r['description'])} · {_money(r['amount'])} · {html.escape(r['receipt_status'])}</p><label>Category</label><select name='category_{key}' required><option value=''>Choose category</option><option>Software subscriptions</option><option>Meals</option><option>Office equipment</option><option>Travel</option><option>Other</option></select><label>Review action</label><select name='action_{key}' required><option value=''>Choose action</option><option value='approve'>Approve classification</option><option value='request_receipt'>Request receipt</option><option value='hold'>Hold for review</option></select><label>Evidence note</label><input name='note_{key}' required></section>")
 return _layout("Card review",f"<p><a href='/card-activity'>‹ Card activity</a></p><h1>Card Transaction Review</h1><p>Review all three rows and consult the Spending Guide before submitting.</p>{notice}<form method='post' action='/review-card'>{''.join(parts)}<button type='submit'>Save card review</button></form>")
def _payment_form(bill_id,notice=""):
 return _layout("Schedule bill payment",f"<p><a href='/bill/{html.escape(bill_id)}'>‹ Bill details</a></p><h1>Schedule an offline bill payment</h1><p class='muted'>No real money movement occurs in this training environment.</p>{notice}<form method='post' action='/bill/pay'><input type='hidden' name='bill_id' value='{html.escape(bill_id)}'><label for='account'>Pay from</label><select id='account' name='account'><option value=''>Select account</option><option>Household Checking</option><option>Everyday Savings</option></select><label for='amount'>Amount</label><input id='amount' name='amount' inputmode='decimal'><label for='pay_date'>Schedule date</label><input id='pay_date' name='pay_date' type='date'><label for='memo'>Memo</label><input id='memo' name='memo'><button type='submit'>Schedule payment</button></form>")
def _payment_history(db):
 rows=_rows(db,"SELECT * FROM payments ORDER BY seq DESC")
 cards="".join(f"<tr><td>{r['bill_id']}</td><td>{html.escape(r['account'])}</td><td>{_money(r['amount'])}</td><td>{r['pay_date']}</td><td>{html.escape(r['memo'])}</td><td>{html.escape(r['status'])}</td></tr>" for r in rows)
 return _layout("Payment History",f"<h1>Payment History</h1><table><tr><th>Bill</th><th>Account</th><th>Amount</th><th>Date</th><th>Memo</th><th>Status</th></tr>{cards}</table><p>{len(rows)} scheduled payment(s)</p>")
def make_server(db_path,host="127.0.0.1",port=0):
 dbfile=str(Path(db_path))
 class H(BaseHTTPRequestHandler):
  server_version="CoDeskOfflineFinance/1.0"
  def _send(self,status,body):
   self._status=status;b=body.encode() if isinstance(body,str) else body;self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(b)
  def do_GET(self):
   parsed=urlparse(self.path);p=parsed.path
   if p=="/healthz":self._send(200,b"ok");return
   with _connect(dbfile) as db:
    if p=="/":body=_layout("Overview",_tasklist())
    elif p=="/bills":body=_layout("Bills","<h1>Household Bills</h1><a class='row' href='/bill/ELEC-208'><b>ELEC-208 · Eastlake Electric</b><p>$68.40 due 20 November 2026 · Unpaid</p></a>")
    elif p=="/bill/ELEC-208":body=_bill_page(db,"ELEC-208")
    elif p=="/bill/pay":body=_payment_form(parse_qs(parsed.query).get("bill_id",["ELEC-208"])[0])
    elif p=="/help/payment-timing":body=_layout("Payment timing guidance","<p><a href='/bills'>‹ Bills</a></p><h1>Payment timing guidance</h1><section class='card'><h2>Schedule domestic utility payments</h2><p>Payments should be scheduled before the printed due date. Confirm the amount, account, and date on the review screen. A scheduled item appears in Payment History; it is not a real external transfer in this training profile.</p></section>")
    elif p=="/payment-history":body=_payment_history(db)
    elif p=="/card-activity":body=_activity_page(db)
    elif p.startswith("/transaction/"):body=_transaction_page(db,p.rsplit("/",1)[-1])
    elif p=="/guide/spending":body=_layout("Spending Guide","<p><a href='/card-activity'>‹ Card activity</a></p><h1>Corporate card spending guide</h1><section class='card'><p>Use Software subscriptions for monthly cloud tools. Use Meals for employee food purchases with a receipt. Office equipment is allowed when documented; a purchase over $250 without an attached receipt must be marked Request receipt. Do not classify a bill payment as a card transaction.</p></section>")
    elif p=="/review-card":body=_review_page(db)
    else:body=None
   self._send(404,b"Not found") if body is None else self._send(200,body)
  def do_POST(self):
   try:
    n=int(self.headers.get("Content-Length","0"))
    if n<=0 or n>20000:raise ValueError()
    data={k:v[0].strip() for k,v in parse_qs(self.rfile.read(n).decode(),keep_blank_values=True).items()}
   except (ValueError,UnicodeDecodeError):self._send(400,b"Invalid form");return
   p=urlparse(self.path).path
   with _connect(dbfile) as db:
    if p=="/bill/pay" and data.get("bill_id")=="ELEC-208" and data.get("account") and data.get("amount") and data.get("pay_date") and data.get("memo"):
     try:amount=round(float(data["amount"].replace("$","")),2)
     except ValueError:amount=0
     if amount!=68.40 or data["account"]!="Household Checking" or data["pay_date"]<"2026-11-18":self._send(400,b"Review payment details");return
     now=datetime.now(timezone.utc).isoformat();db.execute("INSERT INTO payments(bill_id,account,amount,pay_date,memo,status,created_utc) VALUES(?,?,?,?,?,'scheduled',?)",("ELEC-208",data["account"],amount,data["pay_date"],data["memo"],now));db.execute("UPDATE bills SET status='scheduled' WHERE bill_id='ELEC-208'");db.commit()
     self._send(200,_layout("Payment scheduled",f"<p class='notice'>Payment scheduled for 18 November 2026.</p><h1>Payment confirmation</h1><p>ELEC-208 · $68.40 from Household Checking on {html.escape(data['pay_date'])}</p><p>{html.escape(data['memo'])}</p><a class='button' href='/payment-history'>Review Payment History</a>"));return
    if p=="/review-card":
     rows=_rows(db,"SELECT txn_id FROM card_transactions ORDER BY txn_id")
     values=[]
     for r in rows:
      key=r["txn_id"].split("-")[-1];values.append((r["txn_id"],data.get("category_"+key,""),data.get("action_"+key,""),data.get("note_"+key,"")))
     if len(values)!=3 or any(not all(v[1:]) for v in values):self._send(400,b"Complete all transaction reviews");return
     now=datetime.now(timezone.utc).isoformat();db.executemany("INSERT INTO card_reviews(txn_id,category,action,note,created_utc) VALUES(?,?,?,?,?)",[(a,b,c,d,now) for a,b,c,d in values]);db.commit()
     self._send(200,_layout("Card review saved","<p class='notice'>Three card transaction reviews were saved.</p><h1>Review complete</h1><p>All recommendations are internal classifications. No payment or external transfer was created.</p>"));return
   self._send(404,b"Not found")
  def log_message(self,fmt,*args):
   try:
    with sqlite3.connect(dbfile,timeout=10) as db:db.execute("INSERT INTO request_log(method,path,status,at) VALUES(?,?,?,?)",(self.command,urlparse(self.path).path,getattr(self,"_status",200),datetime.now(timezone.utc).isoformat()));db.commit()
   except sqlite3.Error:pass
 server=ThreadingHTTPServer((host,port),H);server.daemon_threads=True;return server


def user_actions():
 from oscombo.human_actor import GUIAction
 return [
  GUIAction("open_household_bills","pyautogui.click(225,204)",APP_TITLE,1.5),
  GUIAction("open_electric_statement","pyautogui.click(843,366)",APP_TITLE,4.0),
  GUIAction("inspect_due_date_and_amount","pyautogui.moveTo(1758,900)",APP_TITLE,7.0),
  GUIAction("open_payment_timing_guidance","pyautogui.click(775,670)",APP_TITLE,4.0),
  GUIAction("read_payment_timing_guidance","pyautogui.moveTo(1758,950); pyautogui.scroll(-2)",APP_TITLE,9.0),
  GUIAction("return_to_bill_statement","pyautogui.hotkey('alt','left')",APP_TITLE,5.0),
  GUIAction("open_schedule_payment_form","pyautogui.click(575,670)",APP_TITLE,4.0),
  GUIAction("select_household_checking","pyautogui.click(984,470); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')",APP_TITLE,4.0),
  GUIAction("enter_payment_amount","pyautogui.click(984,553); pyautogui.write('68.40',interval=0.12)",APP_TITLE,4.0),
  GUIAction("enter_payment_date","pyautogui.click(600,640); pyautogui.write('18112026',interval=0.15)",APP_TITLE,4.0),
  GUIAction("enter_payment_memo","pyautogui.click(984,727); pyautogui.write('November household electric',interval=0.06)",APP_TITLE,4.0),
  GUIAction("review_payment_before_scheduling","pyautogui.moveTo(1547,900)",APP_TITLE,5.0),
  GUIAction("schedule_payment","pyautogui.click(563,783)",APP_TITLE,2.0),
  GUIAction("review_payment_confirmation","pyautogui.moveTo(1547,900)",APP_TITLE,5.0),
  GUIAction("reopen_payment_history","pyautogui.click(335,204)",APP_TITLE,4.0),
  GUIAction("verify_scheduled_payment","pyautogui.moveTo(1547,900)",APP_TITLE,5.0),
 ]
