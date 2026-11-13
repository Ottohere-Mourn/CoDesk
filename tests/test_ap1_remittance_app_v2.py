import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer

from scripts.ap1_remittance_app_v2 import AP1Store, make_handler
from scripts.ap1_remittance_eval_v2 import evaluate_store
from scripts import ap1_remittance_fixture_v2 as fx


def post(base, path, data):
    body=urlencode(data,doseq=True).encode()
    req=Request(base+path,data=body,headers={"Content-Type":"application/x-www-form-urlencoded"})
    try:
        with urlopen(req) as r: return r.status,r.read().decode()
    except HTTPError as e: return e.code,e.read().decode()


def get(base,path):
    try:
        with urlopen(base+path) as r: return r.status,r.read().decode()
    except HTTPError as e: return e.code,e.read().decode()


def review_data():
    return [("source_id", x) for x in fx.SOURCE_DOCS]


def draft_data(amount_071="120000", amount_072="30000", amount_073="64000"):
    return {"include_071":"on","amount_071":amount_071,
            "include_072":"on","amount_072":amount_072,
            "include_073":"on","amount_073":amount_073,
            "amount_074":"18000","exception_reason":"PRICE_MISMATCH",
            "exception_reference":"DISPUTE-33"}


class AP1RemittanceAppV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.state_path=Path(self.tmp.name)/"state.json"
        self.store=AP1Store(self.state_path)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(self.store))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        self.tmp.cleanup()

    def test_shared_stale_draft_fails_and_visible_rebuild_recovers(self):
        status,body=get(self.base,"/health")
        self.assertEqual((status,json.loads(body)),(200,{"ok":True}))
        status,page=get(self.base,"/preparer")
        self.assertEqual(status,200); self.assertIn("INV-AP-074",page)
        self.assertIn("do not release or export",page)
        self.assertEqual(post(self.base,"/preparer/review",review_data())[0],200)
        self.assertEqual(post(self.base,"/preparer/draft",draft_data())[0],200)
        self.assertTrue(evaluate_store(self.store.data, "preparer")["success"])
        self.assertEqual(post(self.base,"/credit/apply",{
            "credit_id":"CN-AP-019","invoice_id":"INV-AP-071","amount_cents":"25000"})[0],200)
        stale=evaluate_store(self.store.data, "shared")
        self.assertFalse(stale["actor_a"]["success"],stale)
        self.assertTrue(stale["actor_b"]["success"],stale)
        self.assertEqual(stale["actor_a"]["actual_total_cents"],214000)
        self.assertEqual(stale["actor_a"]["expected_total_cents"],189000)
        status,page=get(self.base,"/preparer")
        self.assertIn("STALE DRAFT",page)
        self.assertIn("value='120000'",page)
        self.assertEqual(post(self.base,"/preparer/draft",draft_data("95000"))[0],200)
        recovered=evaluate_store(self.store.data, "shared")
        self.assertTrue(recovered["success"],recovered)
        self.assertEqual(recovered["actor_a"]["actual_total_cents"],189000)
        self.assertTrue(any(e["action"]=="DRAFT_SAVED" for e in recovered["events"]))

    def test_invalid_credit_and_double_apply_are_rejected(self):
        wrong={"credit_id":"CN-AP-019","invoice_id":"INV-AP-071","amount_cents":"24000"}
        self.assertEqual(post(self.base,"/credit/apply",wrong)[0],400)
        right={**wrong,"amount_cents":"25000"}
        self.assertEqual(post(self.base,"/credit/apply",right)[0],200)
        self.assertEqual(post(self.base,"/credit/apply",right)[0],400)
        self.assertEqual(self.store.data["core"]["ledger_revision"],2)
        self.assertEqual(len(self.store.data["core"]["audit"]),1)

    def test_private_actor_workspaces_preserve_isolated_controls(self):
        a=AP1Store(Path(self.tmp.name)/"a.json")
        b=AP1Store(Path(self.tmp.name)/"b.json")
        a.mark_reviewed(list(fx.SOURCE_DOCS))
        a.save_draft(draft_data())
        b.apply_credit({"credit_id":"CN-AP-019","invoice_id":"INV-AP-071",
                        "amount_cents":"25000"})
        self.assertTrue(evaluate_store(a.data, "preparer")["success"])
        self.assertTrue(evaluate_store(b.data, "credit")["success"])
        self.assertIsNot(a.data,b.data)
        self.assertEqual(a.data["core"]["ledger_revision"],1)
        self.assertEqual(b.data["core"]["ledger_revision"],2)

    def test_state_survives_store_restart_and_result_endpoint_is_read_only(self):
        self.store.mark_reviewed(list(fx.SOURCE_DOCS))
        self.store.save_draft(draft_data())
        before=json.loads(self.state_path.read_text())
        status,body=get(self.base,"/result?role=preparer")
        self.assertEqual(status,404); self.assertEqual(body,"not found")
        self.assertTrue(evaluate_store(self.store.data, "preparer")["success"])
        self.assertEqual(json.loads(self.state_path.read_text()),before)
        reopened=AP1Store(self.state_path)
        self.assertTrue(evaluate_store(reopened.data, "preparer")["success"])
        self.assertIn("all_source_documents_reviewed",
                      evaluate_store(reopened.data, "preparer")["checks"])

if __name__=="__main__": unittest.main()
