"""SQLite fixture and transactional business rules for Ticket-to-Resolution.

This module is the local application's state store, not an Agent execution
shortcut. Formal task actions enter through the browser forms in webapp.py.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import spec


class BusinessRuleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE customers(
 id TEXT PRIMARY KEY, display_name TEXT NOT NULL, email TEXT NOT NULL, account_status TEXT NOT NULL);
CREATE TABLE orders(
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), status TEXT NOT NULL,
 total_cents INTEGER NOT NULL, remaining_cents INTEGER NOT NULL, revision INTEGER NOT NULL,
 placed_at TEXT NOT NULL, delivered_at TEXT NOT NULL);
CREATE TABLE order_lines(
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id), sku TEXT NOT NULL,
 description TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price_cents INTEGER NOT NULL,
 tax_rate_bps INTEGER NOT NULL, condition TEXT NOT NULL, evidence_id TEXT);
CREATE TABLE tickets(
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), order_id TEXT NOT NULL REFERENCES orders(id),
 status TEXT NOT NULL, issue_code TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
 created_at TEXT NOT NULL, resolution_code TEXT, resolution_notes TEXT, refund_id TEXT, revision INTEGER NOT NULL);
CREATE TABLE policies(
 id TEXT PRIMARY KEY, version TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
 return_days INTEGER NOT NULL, partial_shipping_refund INTEGER NOT NULL);
CREATE TABLE evidence(
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id), line_id TEXT NOT NULL REFERENCES order_lines(id),
 kind TEXT NOT NULL, description TEXT NOT NULL, observed_at TEXT NOT NULL);
CREATE TABLE reviews(
 id TEXT PRIMARY KEY, version INTEGER NOT NULL, ticket_id TEXT NOT NULL REFERENCES tickets(id),
 order_id TEXT NOT NULL REFERENCES orders(id), order_revision INTEGER NOT NULL,
 decision TEXT NOT NULL, line_id TEXT NOT NULL, evidence_id TEXT NOT NULL, policy_id TEXT NOT NULL,
 principal_cents INTEGER NOT NULL, tax_cents INTEGER NOT NULL, shipping_cents INTEGER NOT NULL,
 refund_cents INTEGER NOT NULL, rationale TEXT NOT NULL, actor_id TEXT NOT NULL,
 created_at TEXT NOT NULL, content_sha256 TEXT NOT NULL);
CREATE TABLE refunds(
 id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, review_id TEXT NOT NULL REFERENCES reviews(id),
 ticket_id TEXT NOT NULL REFERENCES tickets(id), order_id TEXT NOT NULL REFERENCES orders(id),
 line_id TEXT NOT NULL REFERENCES order_lines(id), principal_cents INTEGER NOT NULL,
 tax_cents INTEGER NOT NULL, shipping_cents INTEGER NOT NULL, amount_cents INTEGER NOT NULL,
 status TEXT NOT NULL, actor_id TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX one_refund_per_order_line ON refunds(order_id, line_id) WHERE status='SUCCEEDED';
CREATE TABLE audit_events(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, timestamp TEXT NOT NULL,
 actor_id TEXT NOT NULL, event_type TEXT NOT NULL, target_type TEXT NOT NULL,
 target_id TEXT NOT NULL, request_id TEXT NOT NULL, details_json TEXT NOT NULL);
CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events
 BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
 BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""


def _seed(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO metadata VALUES (?,?)", ("schema_version", spec.CASE_VERSION))
    conn.execute("INSERT INTO metadata VALUES (?,?)", ("run_id", "fixture"))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?)", [
        ("C-551", "Morgan Ellis (synthetic)", "morgan.ellis@example.invalid", "ACTIVE"),
        ("C-552", "Jordan Kim (synthetic)", "jordan.kim@example.invalid", "ACTIVE"),
        ("C-553", "Riley Chen (synthetic)", "riley.chen@example.invalid", "ACTIVE"),
    ])
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", [
        ("O-2048", "C-551", "PAID", 23500, 23500, 1, "2025-01-10", "2025-01-15"),
        ("O-2049", "C-552", "PAID", 6600, 6600, 1, "2025-01-11", "2025-01-16"),
        ("O-2050", "C-553", "PAID", 13200, 13200, 1, "2025-01-12", "2025-01-17"),
    ])
    conn.executemany("INSERT INTO order_lines VALUES (?,?,?,?,?,?,?,?,?)", [
        ("O-2048-L1", "O-2048", "MON-24", "24-inch monitor", 1, 12000, 1000, "DELIVERED_OK", None),
        ("O-2048-L2", "O-2048", "DOCK-USBC", "USB-C dock", 1, 8000, 1000, "DELIVERED_DAMAGED", "DELIVERY-EV-77"),
        ("O-2049-L1", "O-2049", "KEY-USB", "USB keyboard", 1, 6000, 1000, "DELIVERED_OK", None),
        ("O-2050-L1", "O-2050", "MOUSE-WL", "Wireless mouse", 1, 12000, 1000, "DELIVERED_OK", None),
    ])
    conn.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
        ("T-1042", "C-551", "O-2048", "OPEN", "DAMAGED_ITEM", "USB-C dock arrived damaged",
         "USB-C dock arrived damaged and will not power on. The monitor is fine. Please refund the dock only.",
         "2025-01-16T10:00:00Z", None, None, None, 1),
        ("T-1043", "C-552", "O-2049", "OPEN", "DELIVERY_DELAY", "Keyboard delivery question",
         "Synthetic non-target ticket; make no changes.", "2025-01-17T10:00:00Z", None, None, None, 1),
        ("T-1044", "C-553", "O-2050", "OPEN", "GENERAL_QUESTION", "Mouse setup question",
         "Synthetic non-target ticket; make no changes.", "2025-01-18T10:00:00Z", None, None, None, 1),
    ])
    conn.execute("INSERT INTO policies VALUES (?,?,?,?,?,?)", (
        spec.POLICY_ID, "4.0", "Damaged item partial refund",
        "Within 30 days of delivery, a supported damaged item may be refunded at its line price plus that line's tax. "
        "For a partial-item refund, shipping is not refundable. Unaffected lines are not refunded. "
        "The processor must reference a saved Case Review and verify it against the current order revision.",
        30, 0))
    conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)", (
        spec.TARGET_EVIDENCE_ID, "O-2048", spec.TARGET_LINE_ID, "DELIVERY_DAMAGE_SCAN",
        "Carrier delivery photo records a crushed carton for this line; the customer reports the dock will not power on.",
        "2025-01-15T16:35:00Z"))


def _rows(conn: sqlite3.Connection, table: str, order_by: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]


def business_snapshot(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    conn = connect(path)
    try:
        return {
            "customers": _rows(conn, "customers", "id"),
            "orders": _rows(conn, "orders", "id"),
            "order_lines": _rows(conn, "order_lines", "id"),
            "tickets": _rows(conn, "tickets", "id"),
            "policies": _rows(conn, "policies", "id"),
            "evidence": _rows(conn, "evidence", "id"),
        }
    finally:
        conn.close()


def _digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def business_state_digest(value: object) -> str:
    return _digest(value)


def create_database(path: str | Path, run_id: str, *, overwrite: bool = False) -> dict[str, Any]:
    db = Path(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing case database: {db}")
    if overwrite:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(db) + suffix)
            if candidate.exists():
                candidate.unlink()
    conn = connect(db)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        _seed(conn)
        conn.execute("UPDATE metadata SET value=? WHERE key='run_id'", (run_id,))
    finally:
        conn.close()
    try:
        db.chmod(0o600)
    except OSError:
        pass
    snap = business_snapshot(db)
    return {
        "case_id": spec.CASE_ID,
        "case_version": spec.CASE_VERSION,
        "run_id": run_id,
        "fixture_seed": 0,
        "sqlite_version": sqlite3.sqlite_version,
        "business_state_sha256": _digest(snap),
        "business_state": snap,
        "gold_answers_hidden_from_actors": True,
    }


def _review_payload(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticket_id": str(fields["ticket_id"]),
        "order_id": str(fields["order_id"]),
        "order_revision": int(fields["order_revision"]),
        "decision": str(fields["decision"]).upper(),
        "line_id": str(fields["line_id"]),
        "evidence_id": str(fields["evidence_id"]),
        "policy_id": str(fields["policy_id"]),
        "principal_cents": int(fields["principal_cents"]),
        "tax_cents": int(fields["tax_cents"]),
        "shipping_cents": int(fields["shipping_cents"]),
        "refund_cents": int(fields["refund_cents"]),
        "rationale": str(fields["rationale"]).strip(),
        "actor_id": str(fields["actor_id"]),
    }


def review_digest(fields: dict[str, Any]) -> str:
    return _digest(_review_payload(fields))


class CaseStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.is_file():
            raise FileNotFoundError(self.db_path)

    def _audit(self, conn: sqlite3.Connection, actor: str, event_type: str,
               target_type: str, target_id: str, request_id: str,
               details: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO audit_events(event_id,timestamp,actor_id,event_type,target_type,target_id,request_id,details_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), _now(), actor, event_type, target_type, target_id,
             request_id, json.dumps(details, sort_keys=True, separators=(",", ":"))))

    def record_view(self, actor: str, route: str, context_id: str) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._audit(conn, actor, "page_view", "route", route, str(uuid.uuid4()), {"context_id": context_id})
            conn.commit()
        finally:
            conn.close()

    def save_review(self, actor: str, fields: dict[str, Any]) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        if actor not in {"A", "S"}:
            error = BusinessRuleError("ROLE_FORBIDDEN", "Only the verifier can save a Case Review.")
            self.record_rejection(actor, "case_review_rejected", "case_review_request", request_id,
                                  {"error_code": error.code, "message": error.message})
            raise error
        try:
            payload = _review_payload({**fields, "actor_id": actor})
        except (KeyError, TypeError, ValueError) as exc:
            error = BusinessRuleError("INVALID_REVIEW", f"Review fields are incomplete: {exc}")
            self.record_rejection(actor, "case_review_rejected", "case_review_request", request_id,
                                  {"error_code": error.code, "message": error.message})
            raise error from exc
        if not payload["rationale"]:
            error = BusinessRuleError("INVALID_REVIEW", "Add a short evidence-based rationale before saving.")
            self.record_rejection(actor, "case_review_rejected", "case_review_request", request_id,
                                  {"error_code": error.code, "message": error.message})
            raise error
        conn = connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (payload["ticket_id"],)).fetchone()
            order = conn.execute("SELECT * FROM orders WHERE id=?", (payload["order_id"],)).fetchone()
            if not ticket or not order or ticket["order_id"] != order["id"]:
                raise BusinessRuleError("CASE_MISMATCH", "Ticket and order do not belong to the same case.")
            if ticket["status"] not in {"OPEN", "REVIEWED"}:
                raise BusinessRuleError("CASE_NOT_REVIEWABLE", "This ticket is no longer open for review.")
            payload["order_revision"] = int(order["revision"])
            existing = conn.execute("SELECT COALESCE(MAX(version),0) AS v FROM reviews WHERE ticket_id=?",
                                    (ticket["id"],)).fetchone()["v"]
            review_id = f"RV-{uuid.uuid4().hex[:12].upper()}"
            content_hash = review_digest(payload)
            created = _now()
            conn.execute(
                "INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (review_id, int(existing) + 1, payload["ticket_id"], payload["order_id"],
                 payload["order_revision"], payload["decision"], payload["line_id"],
                 payload["evidence_id"], payload["policy_id"], payload["principal_cents"],
                 payload["tax_cents"], payload["shipping_cents"], payload["refund_cents"],
                 payload["rationale"], actor, created, content_hash))
            if ticket["status"] == "OPEN":
                conn.execute("UPDATE tickets SET status='REVIEWED', revision=revision+1 WHERE id=?", (ticket["id"],))
            self._audit(conn, actor, "case_review_saved", "review", review_id, request_id,
                        {"ticket_id": ticket["id"], "order_id": order["id"],
                         "order_revision": order["revision"], "version": int(existing) + 1,
                         "content_sha256": content_hash})
            conn.commit()
            return self.get_review(review_id)
        except BusinessRuleError as exc:
            if conn.in_transaction:
                conn.rollback()
            self.record_rejection(actor, "case_review_rejected", "case_review_request", request_id,
                                  {"ticket_id": payload.get("ticket_id"), "order_id": payload.get("order_id"),
                                   "error_code": exc.code, "message": exc.message})
            raise
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def get_review(self, review_id: str) -> dict[str, Any]:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
            if not row:
                raise FileNotFoundError(review_id)
            result = dict(row)
            result["is_valid_current_review"], result["validation_message"] = self.validate_review(review_id)
            return result
        finally:
            conn.close()

    def validate_review(self, review_id: str, conn: sqlite3.Connection | None = None) -> tuple[bool, str]:
        owned = conn is None
        if conn is None:
            conn = connect(self.db_path)
        try:
            review = conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
            if not review:
                return False, "No saved review with this ID."
            order = conn.execute("SELECT * FROM orders WHERE id=?", (review["order_id"],)).fetchone()
            line = conn.execute("SELECT * FROM order_lines WHERE id=?", (review["line_id"],)).fetchone()
            ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (review["ticket_id"],)).fetchone()
            evidence = conn.execute("SELECT * FROM evidence WHERE id=?", (review["evidence_id"],)).fetchone()
            policy = conn.execute("SELECT * FROM policies WHERE id=?", (review["policy_id"],)).fetchone()
            if not all((order, line, ticket, evidence, policy)):
                return False, "The review references a missing order, line, ticket, evidence, or policy."
            if line["order_id"] != order["id"] or ticket["order_id"] != order["id"]:
                return False, "The reviewed line and ticket do not belong to the referenced order."
            payload = _review_payload(dict(review))
            if review_digest(payload) != review["content_sha256"]:
                return False, "The saved review content failed its integrity check."
            latest = conn.execute("SELECT MAX(version) AS version FROM reviews WHERE ticket_id=?",
                                  (review["ticket_id"],)).fetchone()["version"]
            if int(review["version"]) != int(latest):
                return False, "A newer Case Review exists; use the latest saved revision."
            if int(review["order_revision"]) != int(order["revision"]):
                return False, "The order changed after this review; refresh and save a new review."
            try:
                delivered = datetime.strptime(order["delivered_at"], "%Y-%m-%d").date()
                filed = datetime.strptime(ticket["created_at"][:10], "%Y-%m-%d").date()
                within_policy_window = 0 <= (filed - delivered).days <= int(policy["return_days"])
            except (TypeError, ValueError):
                within_policy_window = False
            expected_principal = int(line["quantity"]) * int(line["unit_price_cents"])
            expected_tax = (expected_principal * int(line["tax_rate_bps"]) + 5000) // 10000
            expected = (ticket["id"] == spec.TICKET_ID and order["id"] == spec.ORDER_ID
                        and ticket["issue_code"] == "DAMAGED_ITEM"
                        and order["status"] == "PAID"
                        and line["id"] == spec.TARGET_LINE_ID
                        and line["condition"] == "DELIVERED_DAMAGED"
                        and evidence["id"] == spec.TARGET_EVIDENCE_ID
                        and evidence["line_id"] == line["id"]
                        and policy["id"] == spec.POLICY_ID
                        and int(policy["return_days"]) == 30
                        and int(policy["partial_shipping_refund"]) == 0
                        and within_policy_window
                        and review["decision"] == "ELIGIBLE"
                        and int(review["principal_cents"]) == expected_principal
                        and int(review["tax_cents"]) == expected_tax
                        and int(review["shipping_cents"]) == 0
                        and int(review["refund_cents"]) == 8800)
            if not expected:
                return False, "Review does not match the current item, evidence, policy, and refundable amount."
            return True, "Review is current and consistent with the linked case records."
        finally:
            if owned:
                conn.close()

    def issue_refund(self, actor: str, *, ticket_id: str, order_id: str, review_id: str,
                     line_id: str, principal_cents: int, tax_cents: int,
                     shipping_cents: int, amount_cents: int, idempotency_key: str) -> dict[str, Any]:
        if actor not in {"B", "S"}:
            error = BusinessRuleError("ROLE_FORBIDDEN", "Only the processor can issue a refund.")
            self.record_rejection(actor, "refund_rejected", "refund_request", str(uuid.uuid4()),
                                  {"error_code": error.code, "message": error.message})
            raise error
        request_id = str(uuid.uuid4())
        try:
            request = {"ticket_id": ticket_id, "order_id": order_id, "review_id": review_id,
                       "line_id": line_id, "principal_cents": int(principal_cents),
                       "tax_cents": int(tax_cents), "shipping_cents": int(shipping_cents),
                       "amount_cents": int(amount_cents)}
        except (TypeError, ValueError) as exc:
            error = BusinessRuleError("INVALID_AMOUNT", "Refund components must be integer cents.")
            self.record_rejection(actor, "refund_rejected", "refund_request", request_id,
                                  {"error_code": error.code, "message": error.message})
            raise error from exc
        if not idempotency_key.strip() or len(idempotency_key) > 100:
            error = BusinessRuleError("INVALID_IDEMPOTENCY_KEY", "Enter a non-empty request key of at most 100 characters.")
            self.record_rejection(actor, "refund_rejected", "refund_request", request_id,
                                  {**request, "error_code": error.code, "message": error.message})
            raise error
        conn = connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM refunds WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                same = (existing["ticket_id"] == ticket_id and existing["order_id"] == order_id
                        and existing["review_id"] == review_id and existing["line_id"] == line_id
                        and int(existing["principal_cents"]) == int(principal_cents)
                        and int(existing["tax_cents"]) == int(tax_cents)
                        and int(existing["shipping_cents"]) == int(shipping_cents)
                        and int(existing["amount_cents"]) == int(amount_cents))
                if not same:
                    raise BusinessRuleError("IDEMPOTENCY_MISMATCH", "This request key was already used with different refund details.")
                self._audit(conn, actor, "refund_idempotent_replay", "refund", existing["id"], request_id,
                            {"idempotency_key": idempotency_key, "outcome": "existing transaction returned"})
                conn.commit()
                return dict(existing)

            ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not ticket or not order or ticket["order_id"] != order_id:
                raise BusinessRuleError("CASE_MISMATCH", "Ticket and order do not match.")
            if ticket["status"] not in {"REVIEWED", "REFUND_PENDING"}:
                raise BusinessRuleError("CASE_NOT_READY", "Save a current Case Review before issuing the refund.")
            duplicate = conn.execute("SELECT id FROM refunds WHERE order_id=? AND line_id=? AND status='SUCCEEDED'",
                                     (order_id, line_id)).fetchone()
            if duplicate:
                raise BusinessRuleError("LINE_ALREADY_REFUNDED", "This order line has already been refunded.")
            valid_review, message = self.validate_review(review_id, conn)
            if not valid_review:
                raise BusinessRuleError("REVIEW_INVALID", message)
            review = conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
            if review["ticket_id"] != ticket_id or review["order_id"] != order_id:
                raise BusinessRuleError("REVIEW_CASE_MISMATCH", "The selected review belongs to a different case.")
            expected_payload = (int(review["principal_cents"]) == request["principal_cents"]
                                and int(review["tax_cents"]) == request["tax_cents"]
                                and int(review["shipping_cents"]) == request["shipping_cents"]
                                and int(review["refund_cents"]) == request["amount_cents"]
                                and review["line_id"] == line_id)
            if not expected_payload:
                raise BusinessRuleError("REFUND_REVIEW_MISMATCH", "Refund line and amounts do not match the selected review.")
            if int(order["revision"]) != int(review["order_revision"]):
                raise BusinessRuleError("STALE_ORDER_REVISION", "Order state changed after review; obtain a fresh review.")
            if int(amount_cents) != int(principal_cents) + int(tax_cents) + int(shipping_cents):
                raise BusinessRuleError("AMOUNT_MISMATCH", "Refund total must equal item, tax, and shipping components.")
            if int(order["remaining_cents"]) < int(amount_cents):
                raise BusinessRuleError("REFUND_EXCEEDS_BALANCE", "Refund exceeds the remaining order balance.")
            transaction_id = "RF-" + hashlib.sha256(
                f"{self._run_id(conn)}:{idempotency_key}".encode()).hexdigest()[:16].upper()
            created = _now()
            conn.execute(
                "INSERT INTO refunds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (transaction_id, idempotency_key, review_id, ticket_id, order_id, line_id,
                 int(principal_cents), int(tax_cents), int(shipping_cents), int(amount_cents),
                 "SUCCEEDED", actor, created))
            conn.execute("UPDATE orders SET status='PARTIALLY_REFUNDED', remaining_cents=?, revision=revision+1 WHERE id=?",
                         (int(order["remaining_cents"]) - int(amount_cents), order_id))
            conn.execute("UPDATE tickets SET status='REFUND_PENDING', refund_id=?, revision=revision+1 WHERE id=?",
                         (transaction_id, ticket_id))
            self._audit(conn, actor, "refund_issued", "refund", transaction_id, request_id,
                        {**request, "idempotency_key": idempotency_key,
                         "review_content_sha256": review["content_sha256"],
                         "review_order_revision": int(review["order_revision"]),
                         "result_order_revision": int(order["revision"]) + 1,
                         "ticket_status": "REFUND_PENDING"})
            conn.commit()
            return self.get_refund(transaction_id)
        except BusinessRuleError as exc:
            if conn.in_transaction:
                conn.rollback()
            self.record_rejection(actor, "refund_rejected", "refund_request", request_id,
                                  {**request, "idempotency_key": idempotency_key,
                                   "error_code": exc.code, "message": exc.message})
            raise
        finally:
            conn.close()

    @staticmethod
    def _run_id(conn: sqlite3.Connection) -> str:
        row = conn.execute("SELECT value FROM metadata WHERE key='run_id'").fetchone()
        return row["value"] if row else "unknown"

    def get_refund(self, transaction_id: str) -> dict[str, Any]:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM refunds WHERE id=?", (transaction_id,)).fetchone()
            if not row:
                raise FileNotFoundError(transaction_id)
            return dict(row)
        finally:
            conn.close()

    def resolve_ticket(self, actor: str, *, ticket_id: str, refund_id: str,
                       resolution_code: str, notes: str) -> dict[str, Any]:
        if actor not in {"B", "S"}:
            error = BusinessRuleError("ROLE_FORBIDDEN", "Only the processor can resolve the ticket.")
            self.record_rejection(actor, "ticket_resolution_rejected", "ticket", str(uuid.uuid4()),
                                  {"error_code": error.code, "message": error.message})
            raise error
        conn = connect(self.db_path)
        request_id = str(uuid.uuid4())
        try:
            conn.execute("BEGIN IMMEDIATE")
            ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            refund = conn.execute("SELECT * FROM refunds WHERE id=?", (refund_id,)).fetchone()
            if ticket and ticket["status"] == "RESOLVED" and ticket["refund_id"] == refund_id:
                self._audit(conn, actor, "ticket_resolution_idempotent_replay", "ticket", ticket_id,
                            request_id, {"refund_id": refund_id, "outcome": "already resolved"})
                conn.commit()
                return dict(ticket)
            if not ticket or not refund or refund["ticket_id"] != ticket_id or ticket["refund_id"] != refund_id:
                raise BusinessRuleError("REFUND_LINK_MISMATCH", "Ticket is not linked to this successful refund.")
            if ticket["status"] != "REFUND_PENDING" or refund["status"] != "SUCCEEDED":
                raise BusinessRuleError("RESOLUTION_NOT_READY", "A successful refund must be present before resolution.")
            if resolution_code != spec.EXPECTED_RESOLUTION_CODE:
                raise BusinessRuleError("RESOLUTION_CODE_INVALID", "Choose the supported damaged-item partial-refund resolution code.")
            note = notes.strip()
            if not note:
                raise BusinessRuleError("RESOLUTION_NOTE_REQUIRED", "Add a concise resolution note.")
            conn.execute("UPDATE tickets SET status='RESOLVED', resolution_code=?, resolution_notes=?, revision=revision+1 WHERE id=?",
                         (resolution_code, note, ticket_id))
            self._audit(conn, actor, "ticket_resolved", "ticket", ticket_id, request_id,
                        {"refund_id": refund_id, "resolution_code": resolution_code,
                         "ticket_status": "RESOLVED"})
            conn.commit()
            return self.get_ticket(ticket_id)
        except BusinessRuleError as exc:
            if conn.in_transaction:
                conn.rollback()
            self.record_rejection(actor, "ticket_resolution_rejected", "ticket", request_id,
                                  {"ticket_id": ticket_id, "refund_id": refund_id,
                                   "error_code": exc.code, "message": exc.message})
            raise
        finally:
            conn.close()

    def record_rejection(self, actor: str, event_type: str, target_type: str,
                         target_id: str, details: dict[str, Any]) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._audit(conn, actor, event_type, target_type, target_id, str(uuid.uuid4()), details)
            conn.commit()
        finally:
            conn.close()

    def get_ticket(self, ticket_id: str = spec.TICKET_ID) -> dict[str, Any]:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if not row:
                raise FileNotFoundError(ticket_id)
            return dict(row)
        finally:
            conn.close()

    def get_order(self, order_id: str = spec.ORDER_ID) -> dict[str, Any]:
        conn = connect(self.db_path)
        try:
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                raise FileNotFoundError(order_id)
            result = dict(order)
            result["lines"] = [dict(row) for row in conn.execute(
                "SELECT * FROM order_lines WHERE order_id=? ORDER BY id", (order_id,))]
            return result
        finally:
            conn.close()

    def get_policy(self, policy_id: str = spec.POLICY_ID) -> dict[str, Any]:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM policies WHERE id=?", (policy_id,)).fetchone()
            if not row:
                raise FileNotFoundError(policy_id)
            return dict(row)
        finally:
            conn.close()

    def list_reviews(self, ticket_id: str = spec.TICKET_ID) -> list[dict[str, Any]]:
        conn = connect(self.db_path)
        try:
            rows = conn.execute("SELECT id FROM reviews WHERE ticket_id=? ORDER BY version", (ticket_id,)).fetchall()
            return [self.get_review(row["id"]) for row in rows]
        finally:
            conn.close()

    def list_audit(self) -> list[dict[str, Any]]:
        conn = connect(self.db_path)
        try:
            return [dict(row) for row in conn.execute("SELECT * FROM audit_events ORDER BY sequence")]
        finally:
            conn.close()
