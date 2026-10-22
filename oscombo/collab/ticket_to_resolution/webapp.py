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
            success: str | None = None) -> bytes:
    nav = "" if actor is None else f'''<nav>
      <span class="who">Signed in as {escape(actor)}</span>
      <a href="/queue">Case queue</a><a href="/ticket/{spec.TICKET_ID}">Target ticket</a>
      <a href="/order/{spec.ORDER_ID}">Order</a><a href="/policy/{spec.POLICY_ID}">Policy</a>
      <a href="/reviews">Case reviews</a><a href="/audit">Audit history</a><a href="/logout">Sign out</a>
    </nav>'''
    banner = (f'<div role="alert" class="error">{escape(error)}</div>' if error else "")
    if success:
        banner += f'<div role="status" class="success">{escape(success)}</div>'
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} — Case Desk</title>
      <style>
      body{{font:18px/1.5 sans-serif;margin:0;background:#f4f6f8;color:#17212b}} header{{background:#17324d;color:white;padding:18px 32px}}
      main{{max-width:1000px;margin:24px auto;padding:24px;background:white;border:1px solid #d4dde5;border-radius:8px}}
      nav{{display:flex;gap:14px;align-items:center;flex-wrap:wrap;background:#e7edf3;padding:12px 24px}}
      nav a,.button{{color:#064e79;font-weight:600}} .who{{font-weight:bold;margin-right:12px}}
      label{{display:block;font-weight:600;margin:16px 0 5px}} input,select,textarea{{font:inherit;min-height:42px;width:100%;max-width:720px;padding:7px;border:1px solid #718397;border-radius:4px}}
      textarea{{min-height:90px}} button,.button{{display:inline-block;font:inherit;font-weight:700;padding:10px 18px;margin-top:18px;border:0;border-radius:5px;background:#135e8a;color:white;cursor:pointer;text-decoration:none}}
      table{{border-collapse:collapse;width:100%;margin:14px 0}} th,td{{padding:10px;border:1px solid #cbd5df;text-align:left;vertical-align:top}}
      th{{background:#e9f0f5}} .error,.success,.notice{{padding:12px;margin:12px 0;border-radius:4px}} .error{{background:#ffe9e7;color:#8b1d14}} .success{{background:#e5f7eb;color:#145b2b}} .notice{{background:#eef5ff}}
      .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}} .card{{border:1px solid #cbd5df;padding:16px;border-radius:6px}}
      .mono{{font-family:monospace}} .small{{font-size:15px;color:#425466}} .status{{font-weight:700}}
      </style></head><body><header><h1>Case Desk — Synthetic Support Environment</h1><div>Training fixture only; no real customer or payment data.</div></header>
      {nav}<main><h2>{escape(title)}</h2>{banner}{body}</main></body></html>'''
    return html.encode("utf-8")


class CaseWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def make_server(db_path: str | Path, actor_passwords: dict[str, str],
                host: str = "127.0.0.1", port: int = 0) -> CaseWebServer:
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
                self._send(_layout("Sign in", body))
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
            query = parse_qs(parsed.query)
            context_id = next((query[k][0] for k in ("ticket", "order", "review", "refund")
                               if query.get(k)), "")
            if path.startswith("/reviews/"):
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
            store.record_view(actor, path, context_id)
            try:
                if path in {"/", "/queue"}:
                    self._page_queue(actor)
                elif path == f"/ticket/{spec.TICKET_ID}":
                    self._page_ticket(actor)
                elif path == f"/order/{spec.ORDER_ID}":
                    self._page_order(actor)
                elif path == f"/policy/{spec.POLICY_ID}":
                    self._page_policy(actor)
                elif path == "/reviews":
                    self._page_reviews(actor)
                elif path == "/reviews/current":
                    self._page_current_review(actor)
                elif path == "/reviews/new":
                    self._page_review_form(actor)
                elif path.startswith("/reviews/"):
                    self._page_review(actor, path.rsplit("/", 1)[1])
                elif path == "/refunds/new":
                    self._page_refund_form(actor)
                elif path.startswith("/refunds/"):
                    self._page_refund(actor, path.rsplit("/", 1)[1])
                elif path == "/resolve":
                    self._page_resolution(actor)
                elif path == "/audit":
                    self._page_audit(actor)
                else:
                    self._send(_layout("Not found", "<p>This page does not exist.</p>", actor), 404)
            except FileNotFoundError:
                self._send(_layout("Not found", "<p>The requested case record does not exist.</p>", actor), 404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            form = self._form()
            if path == "/login":
                actor = form.get("actor", "")
                supplied = form.get("password", "")
                expected = actor_passwords.get(actor, "")
                if not expected or not hmac.compare_digest(supplied, expected):
                    self._send(_layout("Sign in", "<p>Return to the sign-in page.</p>", error="Invalid run credential."), 401)
                    return
                token = secrets.token_urlsafe(32)
                csrf = secrets.token_urlsafe(24)
                with session_lock:
                    sessions[token] = {"actor": actor, "csrf": csrf}
                self._redirect("/queue", f"ttr_session={token}; Path=/; HttpOnly; SameSite=Strict")
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
                if path == "/reviews/save":
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
                elif path == "/refunds/issue":
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
                elif path == "/tickets/resolve":
                    service_called = True
                    ticket = store.resolve_ticket(actor, ticket_id=form.get("ticket_id", ""),
                        refund_id=form.get("refund_id", ""),
                        resolution_code=form.get("resolution_code", ""), notes=form.get("notes", ""))
                    self._send(_layout("Case resolved", self._ticket_html(ticket), actor,
                                       success="Ticket resolution saved. The transaction is unchanged."))
                else:
                    self._send(_layout("Not found", "<p>Unknown form.</p>", actor), 404)
            except (BusinessRuleError, InvalidOperation) as exc:
                message = exc.message if isinstance(exc, BusinessRuleError) else "Enter valid currency amounts."
                if not service_called:
                    code = exc.code if isinstance(exc, BusinessRuleError) else "INVALID_AMOUNT"
                    store.record_rejection(actor, path.lstrip("/").replace("/", "_") + "_rejected",
                                           "gui_request", path, {"error_code": code, "message": message})
                body = "<p>Review the visible case record and correct the form before retrying.</p><a href='/queue'>Return to queue</a>"
                self._send(_layout("Action not completed", body, actor, error=message), 400)

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

    server = CaseWebServer((host, port), Handler)
    server.store = store
    server.sessions = sessions
    server.session_lock = session_lock
    server.access_log = open(Path(db_path).with_suffix(".http.jsonl"), "a", encoding="utf-8")
    return server


def run_server(db_path: str | Path, actor_passwords: dict[str, str], host: str = "127.0.0.1", port: int = 0) -> None:
    server = make_server(db_path, actor_passwords, host, port)
    print(json.dumps({"ready": True, "host": host, "port": server.server_address[1]}, flush=True))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        server.access_log.close()
