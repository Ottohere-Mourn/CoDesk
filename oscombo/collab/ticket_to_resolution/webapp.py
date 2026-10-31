"""Small browser UI for the deterministic, synthetic support application."""
from __future__ import annotations

import hmac
import json
import secrets
import threading
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import spec
from .database import BusinessRuleError, CaseStore, connect


def money(cents: int | str) -> str:
    value = int(cents)
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), 100)
    return f"{sign}${whole}.{fraction:02d}"


def parse_money(value: str) -> int:
    try:
        parsed = Decimal(value.strip())
        amount = parsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount != parsed:
            raise BusinessRuleError("INVALID_AMOUNT", "Amounts must use whole cents (at most two decimal places).")
    except (InvalidOperation, AttributeError) as exc:
        raise BusinessRuleError("INVALID_AMOUNT", "Enter an amount such as 88.00.") from exc
    if amount < 0:
        raise BusinessRuleError("INVALID_AMOUNT", "Amount cannot be negative.")
    return int(amount * 100)


def _options(items, selected: str = "") -> str:
    return "".join(f'<option value="{escape(str(value))}" {"selected" if str(value)==selected else ""}>{escape(str(label))}</option>'
                   for value, label in items)


def _layout(title: str, body: str, actor: str | None = None, *, error: str | None = None,
            success: str | None = None, variant: str = "full") -> bytes:
    page_title = f"{actor} · {title}" if variant == "lite-v1" and actor else title
    lite_class = "lite" if variant == "lite-v1" else ""
    lite_style = """main.lite{max-width:1600px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;align-items:start;padding:12px}
      body.lite-page header{padding:6px 24px}
      body.lite-page header h1{font-size:22px;margin:0}
      body.lite-page header div{font-size:13px}
      body.lite-page nav{padding:6px 24px}
      body.lite-page main.lite{margin:8px auto}
      main.lite>h2{grid-column:1/-1;margin:0 0 2px}
      main.lite>section.card:first-of-type{grid-column:1;grid-row:2/span 4}
      main.lite>section.card:not(:first-of-type){grid-column:2}
      main.lite .card{padding:10px;min-width:0}
      main.lite h3,main.lite h4{margin:5px 0}
      main.lite p,main.lite ul,main.lite table{margin:5px 0}
      main.lite td,main.lite th{padding:4px}
      main.lite fieldset.choices{margin:5px 0}
      main.lite fieldset.choices label{margin:2px 0;padding:2px 5px;border-radius:4px}
      main.lite fieldset.choices label:has(input:checked){background:#d5f3df;outline:2px solid #167047}
      main.lite fieldset.choices label:has(input:checked)::after{content:"Selected";margin-left:auto;color:#125c39;font-size:14px;font-weight:700}
      main.lite label{margin:5px 0 2px}
      main.lite input,main.lite textarea{box-sizing:border-box;min-height:32px}
      main.lite button{margin-top:4px}
      @media(max-width:900px){main.lite{display:block}}
      """ if variant == "lite-v1" else ""
    if actor is None:
        nav = ""
    elif variant == "lite-v1":
        nav = f'''<nav>
          <span class="who">Signed in as {escape(actor)}</span>
          <a href="/lite">T-1042 case</a><a href="/logout">Sign out</a>
        </nav>'''
    else:
        nav = f'''<nav>
      <span class="who">Signed in as {escape(actor)}</span>
      <a href="/queue">Case queue</a><a href="/ticket/{spec.TICKET_ID}">Target ticket</a>
      <a href="/order/{spec.ORDER_ID}">Order</a><a href="/policy/{spec.POLICY_ID}">Policy</a>
      <a href="/reviews">Case reviews</a><a href="/audit">Audit history</a><a href="/logout">Sign out</a>
    </nav>'''
    banner = (f'<div role="alert" class="error">{escape(error)}</div>' if error else "")
    if success:
        banner += f'<div role="status" class="success">{escape(success)}</div>'
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(page_title)} — Case Desk</title>
      <style>
      body{{font:18px/1.5 sans-serif;margin:0;background:#f4f6f8;color:#17212b}} header{{background:#17324d;color:white;padding:18px 32px}}
      main{{max-width:1000px;margin:24px auto;padding:24px;background:white;border:1px solid #d4dde5;border-radius:8px}}
      nav{{display:flex;gap:14px;align-items:center;flex-wrap:wrap;background:#e7edf3;padding:12px 24px}}
      nav a,.button{{color:#064e79;font-weight:600}} .who{{font-weight:bold;margin-right:12px}}
      label{{display:block;font-weight:600;margin:16px 0 5px}} input,select,textarea{{font:inherit;min-height:42px;width:100%;max-width:720px;padding:7px;border:1px solid #718397;border-radius:4px}}
      fieldset.choices{{border:0;padding:0;margin:16px 0;max-width:720px}}
      fieldset.choices legend{{font-weight:600;margin:0 0 5px;padding:0}}
      fieldset.choices label{{display:flex;align-items:center;gap:10px;margin:7px 0;font-weight:400;cursor:pointer}}
      fieldset.choices input[type=radio]{{width:auto;min-height:0;margin:0;accent-color:#135e8a}}
      textarea{{min-height:90px}} button,.button{{display:inline-block;font:inherit;font-weight:700;padding:10px 18px;margin-top:18px;border:0;border-radius:5px;background:#135e8a;color:white;cursor:pointer;text-decoration:none}}
      table{{border-collapse:collapse;width:100%;margin:14px 0}} th,td{{padding:10px;border:1px solid #cbd5df;text-align:left;vertical-align:top}}
      th{{background:#e9f0f5}} .error,.success,.notice{{padding:12px;margin:12px 0;border-radius:4px}} .error{{background:#ffe9e7;color:#8b1d14}} .success{{background:#e5f7eb;color:#145b2b}} .notice{{background:#eef5ff}}
      .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}} .card{{border:1px solid #cbd5df;padding:16px;border-radius:6px}}
      .mono{{font-family:monospace}} .small{{font-size:15px;color:#425466}} .status{{font-weight:700}}
      {lite_style}</style></head><body class="{'lite-page' if variant == 'lite-v1' else ''}"><header><h1>Case Desk — Synthetic Support Environment</h1><div>Training fixture only; no real customer or payment data.</div></header>
      {nav}<main class="{lite_class}"><h2>{escape(title)}</h2>{banner}{body}</main></body></html>'''
    return html.encode("utf-8")


class CaseWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def make_server(db_path: str | Path, actor_passwords: dict[str, str],
                host: str = "127.0.0.1", port: int = 0, *,
                variant: str = "full") -> CaseWebServer:
    if variant not in {"full", "lite-v1"}:
        raise ValueError(f"unknown Ticket-to-Resolution UI variant: {variant}")
    store = CaseStore(db_path)
    sessions: dict[str, dict[str, str]] = {}
    session_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "CaseDesk/0.1"

        def log_message(self, fmt: str, *args) -> None:
            # Do not log POST bodies, session cookies, or passwords.
            self.server.access_log.write(json.dumps({"method": self.command,
                "path": urlparse(self.path).path, "status": getattr(self, "_status", 200)}) + "\n")
            self.server.access_log.flush()

        def _send(self, body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8",
                  headers: dict[str, str] | None = None) -> None:
            self._status = status
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location: str, cookie: str | None = None) -> None:
            headers = {"Location": location}
            if cookie:
                headers["Set-Cookie"] = cookie
            self._send(b"", HTTPStatus.SEE_OTHER, headers=headers)

        def _cookies(self) -> SimpleCookie:
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie", ""))
            except Exception:
                pass
            return c

        def _session(self) -> tuple[str | None, dict[str, str] | None]:
            cookie = self._cookies().get("ttr_session")
            if not cookie:
                return None, None
            token = cookie.value
            return token, sessions.get(token)

        def _actor(self, allowed: set[str] | None = None) -> tuple[str | None, str | None, str | None]:
            token, session = self._session()
            if not session:
                return None, token, None
            actor = session["actor"]
            if allowed and actor not in allowed:
                return None, token, "Your role cannot perform this operation."
            return actor, token, None

        def _form(self) -> dict[str, str]:
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 32_768)
            except ValueError:
                length = 0
            raw = self.rfile.read(length).decode("utf-8", "replace")
            return {k: v[-1] for k, v in parse_qs(raw, keep_blank_values=True).items()}

        def _csrf_ok(self, form: dict[str, str]) -> bool:
            _, session = self._session()
            return bool(session and hmac.compare_digest(form.get("csrf", ""), session["csrf"]))

        def _require(self, actor: str | None, token: str | None) -> bool:
            if actor:
                return True
            self._redirect("/login", "ttr_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict" if token else None)
            return False

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/health":
                self._send(b'{"ready":true}', 200, "application/json")
                return
            if path == "/login":
                requested_actor = parse_qs(parsed.query).get("actor", [""])[0]
                roles = _options(((actor, actor) for actor in sorted(actor_passwords)), requested_actor)
                body = f'''<p>Use the role credential supplied for this run.</p><form method="post" action="/login">
                  <label for="actor">Role</label><select id="actor" name="actor">{roles}</select>
                  <label for="password">Run password</label><input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
                  <button type="submit">Sign in</button></form>'''
                self._send(_layout("Sign in", body, variant=variant))
                return
            actor, token, error = self._actor()
            if not actor:
                self._require(actor, token)
                return
            if error:
                self._send(_layout("Role error", "", actor, error=error), 403)
                return
            if path == "/logout":
                if token:
                    with session_lock:
                        sessions.pop(token, None)
                self._redirect("/login", "ttr_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")
                return
            if variant == "lite-v1" and path == "/lite/review-ready":
                reviews = store.list_reviews()
                payload = {"ready": bool(reviews),
                           "url": f"/lite/review/{quote(reviews[-1]['id'], safe='')}" if reviews else None}
                self._send(json.dumps(payload).encode("utf-8"), 200, "application/json")
                return
            query = parse_qs(parsed.query)
            context_id = next((query[k][0] for k in ("ticket", "order", "review", "refund")
                               if query.get(k)), "")
            audit_path = path
            if path.startswith("/lite/review/"):
                context_id = path.rsplit("/", 1)[1]
                audit_path = "/reviews/" + context_id
            elif path.startswith("/lite/refund/"):
                context_id = path.rsplit("/", 1)[1]
                audit_path = "/refunds/" + context_id
            elif path.startswith("/reviews/"):
                context_id = path.rsplit("/", 1)[1]
            elif path.startswith("/refunds/") and path != "/refunds/new":
                context_id = path.rsplit("/", 1)[1]
            elif path == "/reviews/current":
                current_reviews = store.list_reviews()
                context_id = current_reviews[-1]["id"] if current_reviews else ""
            elif path == f"/ticket/{spec.TICKET_ID}":
                context_id = spec.TICKET_ID
            elif path == f"/order/{spec.ORDER_ID}":
                context_id = spec.ORDER_ID
            store.record_view(actor, audit_path, context_id)
            try:
                if variant == "lite-v1" and path == "/lite":
                    self._page_lite(actor)
                elif variant == "lite-v1" and path.startswith("/lite/review/"):
                    self._page_lite_review(actor, context_id)
                elif variant == "lite-v1" and path.startswith("/lite/refund/"):
                    self._page_lite_refund(actor, context_id)
                elif path.startswith("/lite/"):
                    self._send(_layout("Not found", "<p>This page does not exist.</p>", actor, variant=variant), 404)
                elif path in {"/", "/queue"} and variant == "full":
                    self._page_queue(actor)
                elif path == f"/ticket/{spec.TICKET_ID}" and variant == "full":
                    self._page_ticket(actor)
                elif path == f"/order/{spec.ORDER_ID}" and variant == "full":
                    self._page_order(actor)
                elif path == f"/policy/{spec.POLICY_ID}" and variant == "full":
                    self._page_policy(actor)
                elif path == "/reviews" and variant == "full":
                    self._page_reviews(actor)
                elif path == "/reviews/current" and variant == "full":
                    self._page_current_review(actor)
                elif path == "/reviews/new" and variant == "full":
                    self._page_review_form(actor)
                elif path.startswith("/reviews/") and variant == "full":
                    self._page_review(actor, path.rsplit("/", 1)[1])
                elif path == "/refunds/new" and variant == "full":
                    self._page_refund_form(actor)
                elif path.startswith("/refunds/") and variant == "full":
                    self._page_refund(actor, path.rsplit("/", 1)[1])
                elif path == "/resolve" and variant == "full":
                    self._page_resolution(actor)
                elif path == "/audit" and variant == "full":
                    self._page_audit(actor)
                else:
                    self._send(_layout("Not found", "<p>This page does not exist.</p>", actor, variant=variant), 404)
            except FileNotFoundError:
                self._send(_layout("Not found", "<p>The requested case record does not exist.</p>", actor, variant=variant), 404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            form = self._form()
            if path == "/login":
                actor = form.get("actor", "")
                supplied = form.get("password", "")
                expected = actor_passwords.get(actor, "")
                if not expected or not hmac.compare_digest(supplied, expected):
                    self._send(_layout("Sign in", "<p>Return to the sign-in page.</p>", error="Invalid run credential.", variant=variant), 401)
                    return
                token = secrets.token_urlsafe(32)
                csrf = secrets.token_urlsafe(24)
                with session_lock:
                    sessions[token] = {"actor": actor, "csrf": csrf}
                self._redirect("/lite" if variant == "lite-v1" else "/queue",
                               f"ttr_session={token}; Path=/; HttpOnly; SameSite=Strict")
                return
            actor, token, error = self._actor()
            if not actor:
                self._require(actor, token)
                return
            if not self._csrf_ok(form):
                self._send(_layout("Request rejected", "", actor, error="Session check failed. Reload the page and try again."), 403)
                return
            service_called = False
            try:
                if variant == "lite-v1" and path == "/lite/reviews/save":
                    order = store.get_order()
                    line = next((row for row in order["lines"] if row["id"] == form.get("line_id")), None)
                    if line is None:
                        raise BusinessRuleError("INVALID_REVIEW", "Choose an order line shown in the case.")
                    principal = int(line["quantity"]) * int(line["unit_price_cents"])
                    tax = (principal * int(line["tax_rate_bps"]) + 5000) // 10000
                    review_fields = {
                        "ticket_id": spec.TICKET_ID, "order_id": spec.ORDER_ID, "order_revision": order["revision"],
                        "decision": form.get("decision", ""), "line_id": line["id"],
                        "evidence_id": form.get("evidence_id", ""), "policy_id": spec.POLICY_ID,
                        "principal_cents": principal, "tax_cents": tax,
                        "shipping_cents": parse_money(form.get("shipping_amount", "")),
                        "refund_cents": parse_money(form.get("refund_amount", "")),
                        "rationale": "Structured review recorded from the linked ticket, order, evidence, and policy."}
                    service_called = True
                    review = store.save_review(actor, review_fields)
                    self._redirect("/lite/review/" + quote(review["id"], safe=""))
                elif variant == "lite-v1" and path == "/lite/refunds/issue":
                    review_id = form.get("review_id", "")
                    review = store.get_review(review_id)
                    order = store.get_order(review["order_id"])
                    line = next((row for row in order["lines"] if row["id"] == form.get("line_id")), None)
                    if line is None:
                        raise BusinessRuleError("INVALID_REFUND", "Choose an order line shown in the case.")
                    principal = int(line["quantity"]) * int(line["unit_price_cents"])
                    tax = (principal * int(line["tax_rate_bps"]) + 5000) // 10000
                    service_called = True
                    refund = store.issue_refund(actor, ticket_id=review["ticket_id"],
                        order_id=review["order_id"], review_id=review_id, line_id=line["id"],
                        principal_cents=principal, tax_cents=tax,
                        shipping_cents=parse_money(form.get("shipping_amount", "")),
                        amount_cents=parse_money(form.get("refund_amount", "")),
                        idempotency_key=form.get("idempotency_key", ""))
                    self._redirect("/lite/refund/" + quote(refund["id"], safe=""))
                elif variant == "lite-v1" and path == "/lite/tickets/resolve":
                    service_called = True
                    ticket = store.resolve_ticket(actor, ticket_id=form.get("ticket_id", ""),
                        refund_id=form.get("refund_id", ""),
                        resolution_code=form.get("resolution_code", ""), notes=form.get("notes", ""))
                    self._redirect("/lite/refund/" + quote(ticket["refund_id"], safe=""))
                elif path == "/reviews/save" and variant == "full":
                    review_fields = {
                        "ticket_id": form.get("ticket_id", ""), "order_id": form.get("order_id", ""),
                        "order_revision": 1, "decision": form.get("decision", ""),
                        "line_id": form.get("line_id", ""), "evidence_id": form.get("evidence_id", ""),
                        "policy_id": form.get("policy_id", ""),
                        "principal_cents": parse_money(form.get("principal_amount", "")),
                        "tax_cents": parse_money(form.get("tax_amount", "")),
                        "shipping_cents": parse_money(form.get("shipping_amount", "")),
                        "refund_cents": parse_money(form.get("refund_amount", "")),
                        "rationale": form.get("rationale", "")}
                    service_called = True
                    review = store.save_review(actor, review_fields)
                    self._redirect("/reviews/" + quote(review["id"], safe=""))
                elif path == "/refunds/issue" and variant == "full":
                    refund_fields = {
                        "ticket_id": form.get("ticket_id", ""), "order_id": form.get("order_id", ""),
                        "review_id": form.get("review_id", ""), "line_id": form.get("line_id", ""),
                        "principal_cents": parse_money(form.get("principal_amount", "")),
                        "tax_cents": parse_money(form.get("tax_amount", "")),
                        "shipping_cents": parse_money(form.get("shipping_amount", "")),
                        "amount_cents": parse_money(form.get("refund_amount", "")),
                        "idempotency_key": form.get("idempotency_key", "")}
                    service_called = True
                    refund = store.issue_refund(actor,
                        **refund_fields)
                    self._redirect("/refunds/" + quote(refund["id"], safe=""))
                elif path == "/tickets/resolve" and variant == "full":
                    service_called = True
                    ticket = store.resolve_ticket(actor, ticket_id=form.get("ticket_id", ""),
                        refund_id=form.get("refund_id", ""),
                        resolution_code=form.get("resolution_code", ""), notes=form.get("notes", ""))
                    self._send(_layout("Case resolved", self._ticket_html(ticket), actor,
                                       success="Ticket resolution saved. The transaction is unchanged.", variant=variant))
                else:
                    self._send(_layout("Not found", "<p>Unknown form.</p>", actor, variant=variant), 404)
            except (BusinessRuleError, InvalidOperation) as exc:
                message = exc.message if isinstance(exc, BusinessRuleError) else "Enter valid currency amounts."
                if not service_called:
                    code = exc.code if isinstance(exc, BusinessRuleError) else "INVALID_AMOUNT"
                    store.record_rejection(actor, path.lstrip("/").replace("/", "_") + "_rejected",
                                           "gui_request", path, {"error_code": code, "message": message})
                home = "/lite" if variant == "lite-v1" else "/queue"
                body = f"<p>Review the visible case record and correct the form before retrying.</p><a href='{home}'>Return to case</a>"
                self._send(_layout("Action not completed", body, actor, error=message, variant=variant), 400)

        def _page_queue(self, actor: str) -> None:
            ticket = store.get_ticket()
            body = f'''<div class="notice">Assigned workflow: verify or process the same case. Source facts remain visible to both roles.</div>
              <div class="cards"><section class="card"><h3>{escape(ticket['id'])}</h3>
              <p class="status">{escape(ticket['status'])} · {escape(ticket['issue_code'])}</p>
              <p>{escape(ticket['subject'])}</p><p>{escape(ticket['body'])}</p>
              <a class="button" href="/ticket/{spec.TICKET_ID}">Open case</a></section>
              <section class="card"><h3>Your workspace</h3><p>A saves a review. B processes a supported refund and resolves the ticket. Both roles can inspect the same order and policy.</p>
              <a href="/order/{spec.ORDER_ID}">Review order evidence</a></section></div>'''
            self._send(_layout("Case queue", body, actor))

        @staticmethod
        def _ticket_html(ticket: dict) -> str:
            return f'''<table><tr><th>Ticket</th><td>{escape(ticket['id'])}</td></tr>
              <tr><th>Status</th><td class="status">{escape(ticket['status'])}</td></tr>
              <tr><th>Issue</th><td>{escape(ticket['issue_code'])}</td></tr>
              <tr><th>Order</th><td><a href="/order/{escape(ticket['order_id'])}">{escape(ticket['order_id'])}</a></td></tr>
              <tr><th>Customer request</th><td>{escape(ticket['body'])}</td></tr>
              <tr><th>Resolution</th><td>{escape(ticket['resolution_code'] or 'Not resolved')}</td></tr>
              <tr><th>Refund transaction</th><td>{escape(ticket['refund_id'] or 'None')}</td></tr></table>'''

        def _page_ticket(self, actor: str) -> None:
            ticket = store.get_ticket()
            body = self._ticket_html(ticket) + '''<div class="cards">
              <section class="card"><h3>Evidence</h3><a href="/order/O-2048">Open order and delivery record</a><br><a href="/policy/POLICY-RET-4">Open refund policy</a></section>
              <section class="card"><h3>Next actions</h3><a href="/reviews">Inspect saved reviews</a><br><a href="/refunds/new">Open refund console</a></section></div>'''
            self._send(_layout("Ticket T-1042", body, actor))

        def _page_order(self, actor: str) -> None:
            order = store.get_order()
            ticket = store.get_ticket()
            rows = "".join(f"<tr><td>{escape(row['id'])}</td><td>{escape(row['description'])}</td>"
                f"<td>{escape(row['condition'])}</td><td>{money(row['unit_price_cents'])}</td>"
                f"<td>{int(row['tax_rate_bps'])/100:.2f}%</td><td>{escape(row['evidence_id'] or '—')}</td></tr>"
                for row in order["lines"])
            # Evidence records are visible facts; identifiers are not hidden or
            # marked as the answer. The Agent decides which record applies.
            db = connect(store.db_path)
            try:
                evrows = [dict(r) for r in db.execute("SELECT * FROM evidence WHERE order_id=? ORDER BY id", (order["id"],))]
            finally:
                db.close()
            evhtml = "".join(f"<li><strong>{escape(e['id'])}</strong> — line {escape(e['line_id'])}: {escape(e['description'])}</li>" for e in evrows)
            body = f'''<p>Ticket {escape(ticket['id'])}: {escape(ticket['body'])}</p>
              <p>Order status: <strong>{escape(order['status'])}</strong>; current revision: <strong>{order['revision']}</strong>.</p>
              <p>Order placed: {escape(order['placed_at'])}; delivered: {escape(order['delivered_at'])}; ticket opened: {escape(ticket['created_at'])}.</p>
              <table><thead><tr><th>Order line</th><th>Item</th><th>Recorded condition</th><th>Price</th><th>Tax rate</th><th>Linked evidence</th></tr></thead><tbody>{rows}</tbody></table>
              <p>Merchandise tax is calculated per line. Shipping: {money(1500)}. Order total: {money(order['total_cents'])}.</p>
              <h3>Delivery and customer evidence</h3><ul>{evhtml}<li>Customer statement: “{escape(ticket['body'])}”</li></ul>
              <p><a href="/policy/{spec.POLICY_ID}">Read the published policy</a></p>'''
            if actor in {"A", "S"}:
                body += f'<a class="button" href="/reviews/new?ticket={spec.TICKET_ID}">Create Case Review</a>'
            self._send(_layout("Order O-2048", body, actor))

        def _page_policy(self, actor: str) -> None:
            policy = store.get_policy()
            body = f'''<p><strong>{escape(policy['id'])} · version {escape(policy['version'])}</strong></p>
              <p>{escape(policy['body'])}</p><p>Return period: {policy['return_days']} days from delivery; eligibility is assessed using the ticket's opened date.</p>
              <p>Shipping refundable for a partial item refund: {'Yes' if policy['partial_shipping_refund'] else 'No'}.</p>'''
            self._send(_layout("Refund policy", body, actor))

        def _page_reviews(self, actor: str) -> None:
            reviews = store.list_reviews()
            if not reviews:
                rows = "<tr><td colspan='5'>No review has been saved for this case.</td></tr>"
            else:
                rows = "".join(f"<tr><td><a href='/reviews/{quote(r['id'], safe='')}'>{escape(r['id'])}</a></td>"
                    f"<td>{r['version']}</td><td>{escape(r['actor_id'])}</td>"
                    f"<td>{'Current and consistent' if r['is_valid_current_review'] else 'Needs review'}</td>"
                    f"<td>Order revision {r['order_revision']}</td></tr>" for r in reviews)
            body = f"<table><thead><tr><th>Review</th><th>Version</th><th>Author</th><th>Application check</th><th>State basis</th></tr></thead><tbody>{rows}</tbody></table>"
            self._send(_layout("Case Reviews", body, actor))

        def _page_current_review(self, actor: str) -> None:
            reviews = store.list_reviews()
            if not reviews:
                self._send(_layout("Current Case Review", "<p>No Case Review has been saved yet.</p>", actor), 404)
                return
            self._page_review(actor, reviews[-1]["id"])

        def _page_review_form(self, actor: str) -> None:
            if actor not in {"A", "S"}:
                self._send(_layout("Role error", "", actor, error="Only the verifier can create the review."), 403)
                return
            order = store.get_order()
            line_opts = [(r["id"], f"{r['description']} — {money(r['unit_price_cents'])}") for r in order["lines"]]
            db = connect(store.db_path)
            try:
                ev = [dict(r) for r in db.execute("SELECT id,description FROM evidence WHERE order_id=? ORDER BY id", (spec.ORDER_ID,))]
            finally:
                db.close()
            evidence_opts = [(r["id"], f"{r['id']} — {r['description']}") for r in ev]
            body = f'''<p>Review the case and order before saving. The order revision is recorded automatically.</p>
              <form method="post" action="/reviews/save"><input type="hidden" name="csrf" value="{escape(self._session()[1]['csrf'])}">
              <input type="hidden" name="ticket_id" value="{spec.TICKET_ID}"><input type="hidden" name="order_id" value="{spec.ORDER_ID}">
              <label for="decision">Eligibility decision</label><select id="decision" name="decision" autofocus><option value="">Choose</option><option>ELIGIBLE</option><option>NOT_ELIGIBLE</option></select>
              <label for="line_id">Affected order line</label><select id="line_id" name="line_id"><option value="">Choose a line</option>{_options(line_opts)}</select>
              <label for="evidence_id">Supporting evidence</label><select id="evidence_id" name="evidence_id"><option value="">Choose evidence</option>{_options(evidence_opts)}</select>
              <label for="policy_id">Policy applied</label><select id="policy_id" name="policy_id"><option value="">Choose policy</option>{_options([(spec.POLICY_ID, f"{spec.POLICY_ID} — Damaged item partial refund")])}</select>
              <label for="principal_amount">Item amount to refund (USD)</label><input id="principal_amount" name="principal_amount" inputmode="decimal" required>
              <label for="tax_amount">Associated tax to refund (USD)</label><input id="tax_amount" name="tax_amount" inputmode="decimal" required>
              <label for="shipping_amount">Shipping to refund (USD)</label><input id="shipping_amount" name="shipping_amount" inputmode="decimal" required>
              <label for="refund_amount">Total proposed refund (USD)</label><input id="refund_amount" name="refund_amount" inputmode="decimal" required>
              <label for="rationale">Evidence-based rationale</label><textarea id="rationale" name="rationale" required></textarea>
              <button type="submit">Save Case Review</button></form>'''
            self._send(_layout("New Case Review", body, actor))

        def _page_review(self, actor: str, review_id: str) -> None:
            r = store.get_review(review_id)
            body = f'''<p class="status">{escape('Current and consistent' if r['is_valid_current_review'] else 'Review needs rechecking')}</p>
              <table><tbody><tr><th>Review ID</th><td class="mono">{escape(r['id'])}</td></tr>
              <tr><th>Version</th><td>{r['version']}</td></tr><tr><th>Author</th><td>{escape(r['actor_id'])}</td></tr>
              <tr><th>Ticket / order</th><td>{escape(r['ticket_id'])} / {escape(r['order_id'])}</td></tr>
              <tr><th>Order revision</th><td>{r['order_revision']}</td></tr>
              <tr><th>Saved</th><td>{escape(r['created_at'])}</td></tr>
              <tr><th>Decision / line</th><td>{escape(r['decision'])} / {escape(r['line_id'])}</td></tr>
              <tr><th>Evidence / policy</th><td>{escape(r['evidence_id'])} / {escape(r['policy_id'])}</td></tr>
              <tr><th>Item / tax / shipping</th><td>{money(r['principal_cents'])} / {money(r['tax_cents'])} / {money(r['shipping_cents'])}</td></tr>
              <tr><th>Proposed refund</th><td>{money(r['refund_cents'])}</td></tr>
              <tr><th>Rationale</th><td>{escape(r['rationale'])}</td></tr>
              <tr><th>Content SHA-256</th><td class="mono">{escape(r['content_sha256'])}</td></tr></tbody></table>
              <p>{escape(r['validation_message'])}</p><a class="button" href="/refunds/new">Open Refund Console</a>'''
            self._send(_layout("Case Review", body, actor))

        def _page_refund_form(self, actor: str) -> None:
            if actor not in {"B", "S"}:
                self._send(_layout("Role error", "", actor, error="Only the processor can use the refund console."), 403)
                return
            reviews = store.list_reviews()
            review_opts = [(r["id"], f"{r['id']} · v{r['version']} · {r['decision']} · {money(r['refund_cents'])}") for r in reviews]
            order = store.get_order()
            line_opts = [(r["id"], f"{r['description']} · {money(r['unit_price_cents'])}") for r in order["lines"]]
            body = f'''<p>Review the order facts and saved Case Review. Enter the transaction components, then issue the refund.</p>
              <p>Current order revision: <strong>{order['revision']}</strong>; remaining paid balance: <strong>{money(order['remaining_cents'])}</strong>.</p>
              <form method="post" action="/refunds/issue"><input type="hidden" name="csrf" value="{escape(self._session()[1]['csrf'])}">
              <input type="hidden" name="ticket_id" value="{spec.TICKET_ID}"><input type="hidden" name="order_id" value="{spec.ORDER_ID}">
              <input type="hidden" name="idempotency_key" value="{spec.IDEMPOTENCY_KEY}">
              <label for="review_id">Case Review to reference</label><select id="review_id" name="review_id" autofocus><option value="">Choose a saved review</option>{_options(review_opts)}</select>
              <label for="line_id">Order line</label><select id="line_id" name="line_id"><option value="">Choose a line</option>{_options(line_opts)}</select>
              <label for="principal_amount">Item refund (USD)</label><input id="principal_amount" name="principal_amount" inputmode="decimal" required>
              <label for="tax_amount">Tax refund (USD)</label><input id="tax_amount" name="tax_amount" inputmode="decimal" required>
              <label for="shipping_amount">Shipping refund (USD)</label><input id="shipping_amount" name="shipping_amount" inputmode="decimal" required>
              <label for="refund_amount">Total refund (USD)</label><input id="refund_amount" name="refund_amount" inputmode="decimal" required>
              <button type="submit">Issue Refund</button></form>'''
            self._send(_layout("Refund Console", body, actor))

        def _page_refund(self, actor: str, transaction_id: str) -> None:
            refund = store.get_refund(transaction_id)
            body = f'''<div class="success">Refund transaction recorded.</div><table><tbody>
              <tr><th>Transaction</th><td class="mono">{escape(refund['id'])}</td></tr>
              <tr><th>Status</th><td>{escape(refund['status'])}</td></tr>
              <tr><th>Order line</th><td>{escape(refund['line_id'])}</td></tr>
              <tr><th>Review</th><td><a href="/reviews/{quote(refund['review_id'], safe='')}">{escape(refund['review_id'])}</a></td></tr>
              <tr><th>Item / tax / shipping</th><td>{money(refund['principal_cents'])} / {money(refund['tax_cents'])} / {money(refund['shipping_cents'])}</td></tr>
              <tr><th>Total</th><td>{money(refund['amount_cents'])}</td></tr></tbody></table>
              <a class="button" href="/resolve?ticket={spec.TICKET_ID}&refund={quote(refund['id'], safe='')}">Continue ticket resolution</a>'''
            self._send(_layout("Refund result", body, actor))

        def _page_resolution(self, actor: str) -> None:
            if actor not in {"B", "S"}:
                self._send(_layout("Role error", "", actor, error="Only the processor can resolve the ticket."), 403)
                return
            ticket = store.get_ticket()
            conn = connect(store.db_path)
            try:
                refunds = [dict(r) for r in conn.execute("SELECT * FROM refunds WHERE ticket_id=? ORDER BY created_at", (spec.TICKET_ID,))]
            finally:
                conn.close()
            opts = [(r["id"], f"{r['id']} · {money(r['amount_cents'])} · {r['status']}") for r in refunds]
            body = f'''<p>Resolve the target ticket after checking the saved refund result. Ticket is currently {escape(ticket['status'])}.</p>
              <form method="post" action="/tickets/resolve"><input type="hidden" name="csrf" value="{escape(self._session()[1]['csrf'])}">
              <input type="hidden" name="ticket_id" value="{spec.TICKET_ID}">
              <label for="refund_id">Successful refund transaction</label><select id="refund_id" name="refund_id" autofocus><option value="">Choose transaction</option>{_options(opts)}</select>
              <label for="resolution_code">Resolution code</label><select id="resolution_code" name="resolution_code"><option value="">Choose</option>{_options([(spec.EXPECTED_RESOLUTION_CODE, "Partial refund — damaged item")])}</select>
              <label for="notes">Resolution note</label><textarea id="notes" name="notes" required></textarea>
              <button type="submit">Resolve Ticket</button></form>'''
            self._send(_layout("Ticket Resolution", body, actor))

        def _page_audit(self, actor: str) -> None:
            events = store.list_audit()
            rows = "".join(f"<tr><td>{e['sequence']}</td><td>{escape(e['timestamp'])}</td><td>{escape(e['actor_id'])}</td>"
                f"<td>{escape(e['event_type'])}</td><td>{escape(e['target_type'])} {escape(e['target_id'])}</td>"
                f"<td><code>{escape(e['details_json'])}</code></td></tr>" for e in events)
            if not rows:
                rows = "<tr><td colspan='6'>No application actions recorded yet.</td></tr>"
            body = f"<table><thead><tr><th>#</th><th>Time</th><th>Actor</th><th>Event</th><th>Target</th><th>Details</th></tr></thead><tbody>{rows}</tbody></table>"
            self._send(_layout("Append-only Audit History", body, actor))

        def _lite_sources(self) -> tuple[dict, dict, dict, list[dict]]:
            ticket = store.get_ticket()
            order = store.get_order()
            policy = store.get_policy()
            conn = connect(store.db_path)
            try:
                evidence = [dict(row) for row in conn.execute(
                    "SELECT * FROM evidence WHERE order_id=? ORDER BY id", (order["id"],))]
            finally:
                conn.close()
            return ticket, order, policy, evidence

        def _lite_source_html(self) -> tuple[str, dict, dict]:
            ticket, order, policy, evidence = self._lite_sources()
            rows = "".join(
                f"<tr><td>{escape(line['id'])}</td><td>{escape(line['description'])}</td>"
                f"<td>{escape(line['condition'])}</td><td>{money(line['unit_price_cents'])}</td>"
                f"<td>{int(line['tax_rate_bps']) / 100:.2f}%</td></tr>" for line in order["lines"])
            evidence_rows = "".join(
                f"<li><strong>{escape(item['id'])}</strong>: line {escape(item['line_id'])} — "
                f"{escape(item['description'])}</li>" for item in evidence)
            source = f'''<section class="card"><h3>{escape(ticket['id'])} · {escape(ticket['subject'])}</h3>
              <p>{escape(ticket['body'])}</p>
              <p>Order {escape(order['id'])} · {escape(order['status'])} · {money(order['total_cents'])} total</p>
              <table><thead><tr><th>Order line</th><th>Item</th><th>Condition</th><th>Price</th><th>Tax rate</th></tr></thead>
              <tbody>{rows}</tbody></table>
              <p>Shipping: {money(1500)}. Delivered {escape(order['delivered_at'])}; ticket opened {escape(ticket['created_at'][:10])}.</p>
              <h4>Delivery evidence</h4><ul>{evidence_rows}</ul>
              <h4>{escape(policy['id'])} · version {escape(policy['version'])}</h4>
              <p>{escape(policy['body'])}</p></section>'''
            return source, order, policy

        @staticmethod
        def _lite_review_html(review: dict) -> str:
            validity = "Current and consistent" if review["is_valid_current_review"] else "Needs rechecking"
            return f'''<section class="card"><h3>Saved Case Review</h3>
              <p class="status">{escape(validity)} · {escape(review['id'])} · version {review['version']}</p>
              <table><tbody><tr><th>Eligibility</th><td>{escape(review['decision'])}</td></tr>
              <tr><th>Order line</th><td>{escape(review['line_id'])}</td></tr>
              <tr><th>Evidence / policy</th><td>{escape(review['evidence_id'])} / {escape(review['policy_id'])}</td></tr>
              <tr><th>Item / tax / shipping</th><td>{money(review['principal_cents'])} / {money(review['tax_cents'])} / {money(review['shipping_cents'])}</td></tr>
              <tr><th>Proposed total</th><td>{money(review['refund_cents'])}</td></tr>
              <tr><th>Order revision</th><td>{review['order_revision']}</td></tr></tbody></table>
              <p>{escape(review['validation_message'])}</p></section>'''

        def _lite_review_form(self, actor: str, order: dict) -> str:
            if actor not in {"A", "S"}:
                return ""
            lines = [(line["id"], f"{line['description']} — {money(line['unit_price_cents'])}")
                     for line in order["lines"]]
            conn = connect(store.db_path)
            try:
                evidence = [dict(row) for row in conn.execute(
                    "SELECT id,description FROM evidence WHERE order_id=? ORDER BY id", (spec.ORDER_ID,))]
            finally:
                conn.close()
            csrf = escape(self._session()[1]["csrf"])
            body = f'''<section class="card"><h3>Order verification</h3>
              <form method="post" action="/lite/reviews/save">
              <input type="hidden" name="csrf" value="{csrf}">
              <fieldset class="choices"><legend>Eligibility</legend>
                <label><input type="radio" name="decision" value="ELIGIBLE" required autofocus> Eligible</label>
                <label><input type="radio" name="decision" value="NOT_ELIGIBLE"> Not eligible</label></fieldset>
              <fieldset class="choices"><legend>Affected order line</legend>
                {''.join(f'<label><input type="radio" name="line_id" value="{escape(str(value))}" required> {escape(str(label))}</label>' for value, label in lines)}</fieldset>
              <fieldset class="choices"><legend>Supporting delivery evidence</legend>
                {''.join(f'<label><input type="radio" name="evidence_id" value="{escape(str(row["id"]))}" required> {escape(str(row["id"]))} — {escape(str(row["description"]))}</label>' for row in evidence)}</fieldset>
              <fieldset class="choices"><legend>Shipping treatment</legend>
                <label><input type="radio" name="shipping_amount" value="0.00" required> Exclude shipping</label>
                <label><input type="radio" name="shipping_amount" value="15.00"> Include shipping</label></fieldset>
              <label for="refund_amount">Total proposed refund (USD)</label>
              <input id="refund_amount" name="refund_amount" inputmode="decimal" required>
              <button type="submit">Save Case Review</button></form></section>'''
            return body

        def _lite_refund_form(self, actor: str, review: dict) -> str:
            if actor not in {"B", "S"}:
                return "<p>The saved review is ready for the Support Processor.</p>"
            order = store.get_order(review["order_id"])
            lines = [(line["id"], f"{line['description']} — {money(line['unit_price_cents'])}")
                     for line in order["lines"]]
            csrf = escape(self._session()[1]["csrf"])
            return f'''<section class="card"><h3>Refund processing</h3>
              <p>Recheck the source records and review before submitting the transaction.</p>
              <form method="post" action="/lite/refunds/issue">
              <input type="hidden" name="csrf" value="{csrf}">
              <input type="hidden" name="review_id" value="{escape(review['id'])}">
              <input type="hidden" name="idempotency_key" value="{spec.IDEMPOTENCY_KEY}">
              <fieldset class="choices"><legend>Order line to refund</legend>
                {''.join(f'<label><input type="radio" name="line_id" value="{escape(str(value))}" required autofocus> {escape(str(label))}</label>' for value, label in lines)}</fieldset>
              <fieldset class="choices"><legend>Shipping treatment</legend>
                <label><input type="radio" name="shipping_amount" value="0.00" required> Exclude shipping</label>
                <label><input type="radio" name="shipping_amount" value="15.00"> Include shipping</label></fieldset>
              <label for="refund_amount">Refund total (USD)</label>
              <input id="refund_amount" name="refund_amount" inputmode="decimal" required>
              <button type="submit">Issue Refund</button></form></section>'''

        def _lite_resolution_form(self, actor: str, refund: dict) -> str:
            if actor not in {"B", "S"}:
                return "<p>The Support Processor can now resolve the ticket.</p>"
            csrf = escape(self._session()[1]["csrf"])
            return f'''<section class="card"><h3>Ticket resolution</h3>
              <p>Refund confirmed: {escape(refund['id'])} · {escape(refund['line_id'])} · {money(refund['amount_cents'])}.</p>
              <form method="post" action="/lite/tickets/resolve">
              <input type="hidden" name="csrf" value="{csrf}">
              <input type="hidden" name="ticket_id" value="{spec.TICKET_ID}">
              <input type="hidden" name="refund_id" value="{escape(refund['id'])}">
              <fieldset class="choices"><legend>Resolution code</legend>
                <label><input type="radio" name="resolution_code" value="{escape(spec.EXPECTED_RESOLUTION_CODE)}" required autofocus> Partial refund — damaged item</label></fieldset>
              <label for="notes">Customer resolution note (brief text, not the refund amount)</label>
              <input id="notes" name="notes" required>
              <button type="submit">Resolve Ticket</button></form></section>'''

        def _page_lite(self, actor: str) -> None:
            source, order, _policy = self._lite_source_html()
            reviews = store.list_reviews()
            if actor == "B":
                if reviews:
                    review_url = "/lite/review/" + quote(reviews[-1]["id"], safe="")
                    body = f'''{source}<p>A saved Case Review is available.
                      <a class="button" href="{review_url}">Open the verifier's review</a></p>
                      <script>setTimeout(() => location.replace({json.dumps(review_url)}), 800);</script>'''
                else:
                    body = f'''{source}<p role="status">Waiting for the verifier's saved review. You may inspect the source records while A works.</p>
                      <script>
                      const reviewPoll = setInterval(async () => {{
                        try {{
                          const response = await fetch('/lite/review-ready', {{cache: 'no-store'}});
                          const state = await response.json();
                          if (state.ready) {{ clearInterval(reviewPoll); location.assign(state.url); }}
                        }} catch (_) {{}}
                      }}, 3000);
                      </script>'''
                self._send(_layout("T-1042 Support Case", body, actor, variant="lite-v1"))
                return
            if actor == "S" and reviews:
                refunds = self._lite_refunds()
                if refunds:
                    self._page_lite_refund(actor, refunds[-1]["id"])
                else:
                    self._page_lite_review(actor, reviews[-1]["id"])
                return
            if actor == "A" and reviews:
                body = f'''{source}<p class="success">Review saved. Send the Support Processor a short handoff message.</p>'''
            else:
                body = source + self._lite_review_form(actor, order)
            self._send(_layout("T-1042 Support Case", body, actor, variant="lite-v1"))

        def _lite_refunds(self) -> list[dict]:
            conn = connect(store.db_path)
            try:
                return [dict(row) for row in conn.execute(
                    "SELECT * FROM refunds WHERE ticket_id=? ORDER BY created_at,id", (spec.TICKET_ID,))]
            finally:
                conn.close()

        def _page_lite_review(self, actor: str, review_id: str) -> None:
            if actor not in {"A", "B", "S"}:
                self._send(_layout("Role error", "", actor, error="Unknown case role.", variant="lite-v1"), 403)
                return
            review = store.get_review(review_id)
            source, _order, _policy = self._lite_source_html()
            body = source + self._lite_review_html(review)
            refunds = self._lite_refunds()
            if refunds:
                self._page_lite_refund(actor, refunds[-1]["id"])
                return
            if actor in {"B", "S"}:
                body += self._lite_refund_form(actor, review)
            else:
                body += self._lite_refund_form(actor, review)
            self._send(_layout("Review and Process T-1042", body, actor, variant="lite-v1"))

        def _page_lite_refund(self, actor: str, refund_id: str) -> None:
            refund = store.get_refund(refund_id)
            review = store.get_review(refund["review_id"])
            ticket = store.get_ticket(refund["ticket_id"])
            source, _order, _policy = self._lite_source_html()
            transaction = f'''<section class="card"><h3>Refund transaction</h3>
              <p class="status">{escape(refund['status'])} · {escape(refund['id'])}</p>
              <p>{escape(refund['line_id'])} · {money(refund['amount_cents'])}</p></section>'''
            if ticket["status"] == "RESOLVED":
                body = source + self._lite_review_html(review) + transaction
                body += f'''<p class="success">Ticket resolved as {escape(ticket['resolution_code'])}.
                  The saved transaction is {escape(ticket['refund_id'])}.</p>'''
            else:
                body = source + self._lite_resolution_form(actor, refund)
                body += transaction + self._lite_review_html(review)
            self._send(_layout("Refund and Resolve T-1042", body, actor, variant="lite-v1"))

    server = CaseWebServer((host, port), Handler)
    server.store = store
    server.sessions = sessions
    server.session_lock = session_lock
    server.access_log = open(Path(db_path).with_suffix(".http.jsonl"), "a", encoding="utf-8")
    return server


def run_server(db_path: str | Path, actor_passwords: dict[str, str], host: str = "127.0.0.1",
               port: int = 0, variant: str = "full") -> None:
    server = make_server(db_path, actor_passwords, host, port, variant=variant)
    print(json.dumps({"ready": True, "host": host, "port": server.server_address[1],
                      "variant": variant}, flush=True))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        server.access_log.close()
