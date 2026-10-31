from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

from oscombo.collab.ticket_to_resolution import spec
from oscombo.collab.ticket_to_resolution.lite_v1 import spec as lite_spec
from oscombo.collab.ticket_to_resolution.oracle import evaluate
from oscombo.collab.ticket_to_resolution.database import CaseStore
from oscombo.collab.ticket_to_resolution.runner import hidden_manifest_path, prepare_run
from oscombo.collab.ticket_to_resolution.webapp import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra"))
from run_ticket_to_resolution_lite_model import public_handoff_state


def _csrf(response: requests.Response) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def _login(base_url: str, actor: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.get(f"{base_url}/login?actor={actor}", timeout=10)
    assert response.status_code == 200
    response = session.post(
        f"{base_url}/login",
        data={"actor": actor, "password": password},
        allow_redirects=True,
        timeout=10,
    )
    assert response.status_code == 200
    assert response.url.endswith("/lite")
    return session


@pytest.mark.parametrize(("amount", "expected_success"), [("88.00", True), ("80.00", False)])
def test_lite_gui_flow_uses_original_business_oracle(tmp_path, amount, expected_success):
    root = tmp_path / "episode"
    prepare_run(root, "ttr-lite-ui-test")
    credentials = json.loads((root / "secrets" / "browser_credentials.json").read_text())
    server = make_server(root / "db" / spec.FIXTURE_DB, credentials, variant="lite-v1")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        verifier = _login(base_url, "A", credentials["A"])
        page = verifier.get(f"{base_url}/lite", timeout=10)
        assert "Delivery evidence" in page.text
        assert "POLICY-RET-4" in page.text
        # Radio choices avoid browser-native dropdown popups, which were not reliably inspectable in OSWorld screenshots.
        assert 'type="radio" name="decision" value="ELIGIBLE"' in page.text
        assert f'type="radio" name="line_id" value="{spec.TARGET_LINE_ID}"' in page.text
        assert f'type="radio" name="evidence_id" value="{spec.TARGET_EVIDENCE_ID}"' in page.text
        assert 'type="radio" name="shipping_amount" value="0.00"' in page.text
        assert 'select id="decision"' not in page.text
        response = verifier.post(
            f"{base_url}/lite/reviews/save",
            data={"csrf": _csrf(page), "decision": "ELIGIBLE", "line_id": spec.TARGET_LINE_ID,
                  "evidence_id": spec.TARGET_EVIDENCE_ID, "shipping_amount": "0.00",
                  "refund_amount": amount},
            allow_redirects=False,
            timeout=10,
        )
        assert response.status_code == 303
        review_url = response.headers["Location"]

        processor = _login(base_url, "B", credentials["B"])
        waiting = processor.get(f"{base_url}/lite", timeout=10)
        assert "saved case review" in waiting.text.lower()
        review_page = processor.get(f"{base_url}{review_url}", timeout=10)
        assert spec.TARGET_EVIDENCE_ID in review_page.text
        assert amount in review_page.text
        response = processor.post(
            f"{base_url}/lite/refunds/issue",
            data={"csrf": _csrf(review_page), "review_id": review_url.rsplit("/", 1)[1],
                  "line_id": spec.TARGET_LINE_ID, "shipping_amount": "0.00",
                  "refund_amount": amount, "idempotency_key": spec.IDEMPOTENCY_KEY},
            allow_redirects=False,
            timeout=10,
        )
        if not expected_success:
            assert response.status_code == 400
        else:
            assert response.status_code == 303
            refund_url = response.headers["Location"]
            refund_page = processor.get(f"{base_url}{refund_url}", timeout=10)
            response = processor.post(
                f"{base_url}/lite/tickets/resolve",
                data={"csrf": _csrf(refund_page), "ticket_id": spec.TICKET_ID,
                      "refund_id": refund_url.rsplit("/", 1)[1],
                      "resolution_code": spec.EXPECTED_RESOLUTION_CODE,
                      "notes": "Verified the case and completed the supported partial refund."},
                allow_redirects=False,
                timeout=10,
            )
            assert response.status_code == 303

        result = evaluate(root / "db" / spec.FIXTURE_DB, hidden_manifest_path(root))
        assert result["joint_business_success"] is expected_success
        assert result["process_evidence"]["review_opened_in_gui_by_B"]
        assert result["observed"]["refund_count"] == int(expected_success)
    finally:
        server.shutdown()
        server.server_close()
        server.access_log.close()
        thread.join(timeout=5)


def test_single_agent_task_card_requires_full_workflow_completion():
    from oscombo.collab.ticket_to_resolution.lite_v1 import spec as lite_spec
    instruction = lite_spec.SINGLE_AGENT_INSTRUCTION
    for required in ("open the saved review", "click “Issue Refund”",
                     "Partial refund — damaged item", "Customer resolution note",
                     "do not enter the refund amount", "ticket visibly shows RESOLVED"):
        assert required in instruction
    assert "Do not stop after saving the review or issuing the refund" in instruction


def test_resolution_form_requires_an_empty_customer_note(tmp_path):
    root = tmp_path / "resolution-form"
    prepare_run(root, "ttr-lite-resolution-form-copy")
    credentials = json.loads((root / "secrets" / "browser_credentials.json").read_text())
    server = make_server(root / "db" / spec.FIXTURE_DB, credentials, variant="lite-v1")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        actor = _login(base_url, "S", credentials["S"])
        page = actor.get(f"{base_url}/lite", timeout=10)
        saved = actor.post(
            f"{base_url}/lite/reviews/save",
            data={"csrf": _csrf(page), "decision": "ELIGIBLE",
                  "line_id": spec.TARGET_LINE_ID, "evidence_id": spec.TARGET_EVIDENCE_ID,
                  "shipping_amount": "0.00", "refund_amount": "88.00"},
            allow_redirects=False, timeout=10,
        )
        assert saved.status_code == 303
        review_page = actor.get(f"{base_url}{saved.headers['Location']}", timeout=10)
        refund = actor.post(
            f"{base_url}/lite/refunds/issue",
            data={"csrf": _csrf(review_page), "review_id": saved.headers["Location"].rsplit("/", 1)[1],
                  "line_id": spec.TARGET_LINE_ID, "shipping_amount": "0.00",
                  "refund_amount": "88.00", "idempotency_key": spec.IDEMPOTENCY_KEY},
            allow_redirects=False, timeout=10,
        )
        assert refund.status_code == 303
        resolution_page = actor.get(f"{base_url}{refund.headers['Location']}", timeout=10)
        assert "Customer resolution note (brief text, not the refund amount)" in resolution_page.text
        assert '<input id="notes" name="notes" required>' in resolution_page.text
        assert 'type="radio" name="resolution_code"' in resolution_page.text
        assert "Resolve Ticket" in resolution_page.text
    finally:
        server.shutdown()
        server.server_close()
        server.access_log.close()
        thread.join(timeout=5)

def test_handoff_lifecycle_wakes_when_review_follows_an_already_read_message(tmp_path):
    root = tmp_path / "episode"
    prepare_run(root, "ttr-lite-lifecycle-test")
    message_id = "review-handoff-1"
    message_time = time.time()
    (root / "collaboration" / "events.jsonl").write_text(json.dumps({
        "type": "message", "message_id": message_id, "actor": "A", "recipient": "B",
        "timestamp": message_time,
    }) + "\n")
    (root / "collaboration_reads.jsonl").write_text(json.dumps({
        "reader": "B", "time_unix": message_time + 0.001, "message_ids": [message_id],
    }) + "\n")

    time.sleep(0.02)
    order = CaseStore(root / "db" / spec.FIXTURE_DB).get_order()
    line = next(row for row in order["lines"] if row["id"] == spec.TARGET_LINE_ID)
    principal = int(line["quantity"]) * int(line["unit_price_cents"])
    tax = (principal * int(line["tax_rate_bps"]) + 5000) // 10000
    CaseStore(root / "db" / spec.FIXTURE_DB).save_review("A", {
        "ticket_id": spec.TICKET_ID, "order_id": spec.ORDER_ID,
        "order_revision": order["revision"], "decision": "ELIGIBLE",
        "line_id": line["id"], "evidence_id": spec.TARGET_EVIDENCE_ID,
        "policy_id": spec.POLICY_ID, "principal_cents": principal, "tax_cents": tax,
        "shipping_cents": 0, "refund_cents": principal + tax,
        "rationale": "Record the review facts for the lifecycle audit.",
    })

    state = public_handoff_state(root)
    assert state["review_saved_by_A"]
    assert state["A_message_sent_to_B"]
    assert state["latest_A_message_read_by_B"]
    assert state["review_saved_after_B_last_read"]
    assert state["ready_to_wake"]
    assert not state["handoff_seen_by_B"]

    with (root / "collaboration_reads.jsonl").open("a") as stream:
        stream.write(json.dumps({"reader": "B", "time_unix": time.time(),
                                 "message_ids": [message_id]}) + "\n")
    state = public_handoff_state(root)
    assert state["handoff_seen_by_B"]
    assert not state["ready_to_wake"]
