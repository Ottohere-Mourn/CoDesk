from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swcub.environment import ActorContext
from swcub.osworld_adapter import OSWorldSharedEpisode

from scripts.wf_composite_receiving_v2 import (
    APP_SERVER, ASN_LOT, EXPECTED, FIXTURE_DOCUMENTS, QA_DISPOSITION,
    clipboard_failure_attribution, collaboration_contract, evaluate_state, initial_state, mechanism_evidence, parse_receipt_ledger,
)


class ReceivingTaskTests(unittest.TestCase):
    def test_exact_state_and_totals_pass(self):
        state = initial_state()
        state["documents"] = dict(FIXTURE_DOCUMENTS)
        state.update(EXPECTED)
        result = evaluate_state(state)
        self.assertTrue(result["condition_success"])
        self.assertEqual(result["receipt_totals"],
                         {"received": 59, "available": 56, "accepted": 56, "held": 3, "shortage": 1})
        self.assertTrue(result["initial_documents_unchanged"])

    def test_receipt_ledger_totals_are_parsed_and_balanced(self):
        parsed = parse_receipt_ledger(EXPECTED["receipt_ledger"])
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["totals"], {
            "received": 59, "available": 56, "accepted": 56, "held": 3, "shortage": 1})
        broken = EXPECTED["receipt_ledger"].replace("accepted=15", "accepted=16")
        self.assertFalse(parse_receipt_ledger(broken)["valid"])

    def test_collaboration_contract_requires_ordered_handoff_and_qa_reply(self):
        events = [
            {"type": "message", "actor": "A", "recipient": "B",
             "message_id": "a1", "timestamp": 10,
             "body": "BN-07 LOT-B07; 3 cartons held for QA."},
            {"type": "message", "actor": "B", "recipient": "A",
             "message_id": "b1", "timestamp": 20,
             "body": "Confirmed LOT-B07, 3 cartons; temperature excursion 2-8 C."},
        ]
        self.assertTrue(collaboration_contract(events)["success"])
        self.assertFalse(collaboration_contract(events[:1])["success"])

    def test_clipboard_mismatch_is_not_enough_without_trace(self):
        source = hashlib.sha256(ASN_LOT.encode()).hexdigest()
        overwritten = hashlib.sha256(QA_DISPOSITION.encode()).hexdigest()
        unsupported = mechanism_evidence(
            expected_copy_sha256=source, clipboard_at_paste_sha256=overwritten,
            paste_target_id="held-lot-ref", target_is_held_lot_ref=True,
            final_held_lot_ref=QA_DISPOSITION, actor_a_copy_seen=True,
            actor_b_copy_seen=True, intervening_overwrite=False)
        self.assertEqual(unsupported["mechanism"], "unsupported")
        self.assertFalse(unsupported["attributable_task_failure"])

    def test_supported_clipboard_failure_and_recovery_are_separate(self):
        source = hashlib.sha256(ASN_LOT.encode()).hexdigest()
        overwritten = hashlib.sha256(QA_DISPOSITION.encode()).hexdigest()
        failure = mechanism_evidence(
            expected_copy_sha256=source, clipboard_at_paste_sha256=overwritten,
            paste_target_id="held-lot-ref", target_is_held_lot_ref=True,
            final_held_lot_ref=QA_DISPOSITION, actor_a_copy_seen=True,
            actor_b_copy_seen=True, intervening_overwrite=True)
        recovered = mechanism_evidence(
            expected_copy_sha256=source, clipboard_at_paste_sha256=overwritten,
            paste_target_id="held-lot-ref", target_is_held_lot_ref=True,
            final_held_lot_ref=ASN_LOT, actor_a_copy_seen=True,
            actor_b_copy_seen=True, intervening_overwrite=True)
        self.assertTrue(failure["attributable_task_failure"])
        self.assertTrue(recovered["mechanism"] == "shared_clipboard_payload_overwrite")
        self.assertFalse(recovered["task_failed"])
        self.assertTrue(recovered["recovered_or_unaffected"])

    def test_clipboard_failure_requires_all_unaffected_business_outputs_exact(self):
        source = hashlib.sha256(ASN_LOT.encode()).hexdigest()
        overwritten = hashlib.sha256(QA_DISPOSITION.encode()).hexdigest()
        mechanism = mechanism_evidence(
            expected_copy_sha256=source, clipboard_at_paste_sha256=overwritten,
            paste_target_id="held-lot-ref", target_is_held_lot_ref=True,
            final_held_lot_ref=QA_DISPOSITION, actor_a_copy_seen=True,
            actor_b_copy_seen=True, intervening_overwrite=True)
        final = {**EXPECTED, "held_lot_ref": QA_DISPOSITION, "documents": dict(FIXTURE_DOCUMENTS)}
        audit = clipboard_failure_attribution(final, mechanism)
        self.assertTrue(audit["supported_isolated_failure"])
        final["receipt_ledger"] = "ordinary error"
        audit = clipboard_failure_attribution(final, mechanism)
        self.assertFalse(audit["supported_isolated_failure"])
        self.assertFalse(audit["checks"]["receipt_ledger_exact"])

    def test_smoke_gui_controls_use_actorcontext_native_guest_actions(self):
        class FakeDesktopEnv:
            provider = None

            def __init__(self):
                self.actions = []

            def step(self, action, pause=2):
                self.actions.append(action)
                return {"screenshot": b"fake-frame"}, 0, False, {}

        desktop = FakeDesktopEnv()
        episode = OSWorldSharedEpisode(desktop)
        episode.observation = {"screenshot": b"initial-frame"}
        actor = ActorContext("scripted_control", episode, "gui")
        actor.click(1000, 840)
        actor.press_key("ctrl+v")
        actor.press_key("ctrl+1")

        self.assertEqual(desktop.actions, [
            'pyautogui.click(1000, 840)',
            'pyautogui.hotkey("ctrl", "v")',
            'pyautogui.hotkey("ctrl", "1")',
        ])
        self.assertEqual(episode.actor_steps["scripted_control"], 3)

    def test_guest_app_local_http_contract_and_reset(self):
        with tempfile.TemporaryDirectory(prefix="codedesk-receiving-app-test-") as td:
            tmp = Path(td)
            app = tmp / "server.py"
            state = tmp / "state.json"
            app.write_text(APP_SERVER, encoding="utf-8")
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            proc = subprocess.Popen(
                [sys.executable, str(app), "--port", str(port), "--state", str(state)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            base = f"http://127.0.0.1:{port}"
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    try:
                        with urlopen(base + "/health", timeout=0.3) as response:
                            health = json.load(response)
                        if health.get("ok"):
                            break
                    except Exception:
                        time.sleep(0.05)
                else:
                    stderr = proc.stderr.read() if proc.poll() is not None else ""
                    self.fail("guest-local fixture server did not start: " + stderr[-500:])
                with urlopen(base + "/case/receiving", timeout=1) as response:
                    receiving = response.read().decode()
                with urlopen(base + "/case/asn", timeout=1) as response:
                    asn = response.read().decode()
                with urlopen(base + "/case/qa", timeout=1) as response:
                    qa = response.read().decode()
                self.assertIn('data-role="receiving"', receiving)
                self.assertIn('data-role="asn"', asn)
                self.assertIn('data-role="qa"', qa)
                self.assertIn("ASN-2407", asn)
                self.assertIn('id="asn-lot-copy"', asn)
                self.assertIn('value="LOT-B07"', asn)
                self.assertIn('readonly', asn)
                self.assertIn(QA_DISPOSITION, qa)
                self.assertIn('id="qa-disposition-copy"', qa)
                self.assertIn("receiving-panel", receiving)
                self.assertIn("receiving-summary", receiving)
                self.assertIn("available ", receiving)
                self.assertIn("asn-panel", asn)
                self.assertIn("qa-panel", qa)

                def post(path, obj):
                    request = Request(base + path, data=json.dumps(obj).encode(),
                                      headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(request, timeout=1) as response:
                        return json.load(response)

                post("/api/receipt", {"receipt_ledger": EXPECTED["receipt_ledger"],
                                      "held_lot_ref": EXPECTED["held_lot_ref"],
                                      "route": "/case/receiving",
                                      "active_id": "held-lot-ref"})
                post("/api/qa", {"qa_disposition": EXPECTED["qa_disposition"],
                                 "route": "/case/qa",
                                 "active_id": "qa-disposition"})
                with urlopen(base + "/api/state", timeout=1) as response:
                    final = json.load(response)
                self.assertEqual(final["receipt_ledger"], EXPECTED["receipt_ledger"])
                self.assertEqual(final["held_lot_ref"], EXPECTED["held_lot_ref"])
                self.assertEqual(final["qa_disposition"], EXPECTED["qa_disposition"])
                self.assertEqual(final["documents"]["asn"],
                                 FIXTURE_DOCUMENTS["asn"])
                reset = post("/api/reset", {})
                self.assertTrue(reset["ok"])
                with urlopen(base + "/api/state", timeout=1) as response:
                    clean = json.load(response)
                self.assertEqual(clean["receipt_ledger"], "")
                self.assertEqual(clean["held_lot_ref"], "")
                self.assertEqual(clean["qa_disposition"], "")
                self.assertEqual(clean["events"], [])
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
                if proc.stderr:
                    proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
