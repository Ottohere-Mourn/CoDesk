import json, tempfile, threading, unittest, urllib.request
from pathlib import Path
from scripts import crm_lu1_fixture_v1 as fx
from scripts import crm_lu1_app_v1 as app

class ContractTest(unittest.TestCase):
    def test_isolated_owner_updates_are_correct(self):
        a=fx.new_state(); b=fx.new_state()
        va={"renewal_contact":"Jordan Lee","billing_email":fx.INITIAL["billing_email"]}
        vb={"renewal_contact":fx.INITIAL["renewal_contact"],"billing_email":"ap@northwind.example"}
        fx.save_full_record(a,"A",fx.CUSTOMER,va,1)
        fx.save_full_record(b,"B",fx.CUSTOMER,vb,1)
        self.assertTrue(fx.actor_success(a,"A"))
        self.assertTrue(fx.actor_success(b,"B"))
        self.assertFalse(fx.joint_success(a)); self.assertFalse(fx.joint_success(b))
    def test_shared_completion_order_has_exact_lost_field_signature(self):
        s=fx.new_state()
        b={"renewal_contact":fx.INITIAL["renewal_contact"],"billing_email":"ap@northwind.example"}
        a={"renewal_contact":"Jordan Lee","billing_email":fx.INITIAL["billing_email"]}
        fx.save_full_record(s,"B",fx.CUSTOMER,b,1)
        self.assertTrue(fx.actor_success(s,"B"))
        fx.save_full_record(s,"A",fx.CUSTOMER,a,1)
        self.assertTrue(fx.actor_success(s,"A"))
        self.assertFalse(fx.actor_success(s,"B"))
        self.assertFalse(fx.joint_success(s))
        self.assertTrue(fx.lost_update_signature(s))
    def test_normal_reload_merge_recovers_without_erasing_source_history(self):
        s=fx.new_state()
        fx.save_full_record(s,"B",fx.CUSTOMER,{"renewal_contact":"Riley Park","billing_email":"ap@northwind.example"},1)
        fx.save_full_record(s,"A",fx.CUSTOMER,{"renewal_contact":"Jordan Lee","billing_email":"billing-old@northwind.example"},1)
        fx.recovery_save_after_reload(s)
        self.assertTrue(fx.joint_success(s))
        self.assertEqual(len(s["events"]),3)
        self.assertTrue(fx.lost_update_signature({"events":s["events"][:2]}))
    def test_wrong_customer_and_wrong_owner_value_rejected(self):
        s=fx.new_state()
        with self.assertRaises(ValueError):
            fx.save_full_record(s,"A","C-999",{"renewal_contact":"Jordan Lee","billing_email":"billing-old@northwind.example"},1)
        with self.assertRaises(ValueError):
            fx.save_full_record(s,"A",fx.CUSTOMER,{"renewal_contact":"Wrong","billing_email":"billing-old@northwind.example"},1)
    def test_http_ui_contract_and_reload(self):
        with tempfile.TemporaryDirectory() as td:
            store=app.Store(Path(td)/"state.json")
            server=app.ThreadingHTTPServer(("127.0.0.1",0),app.make_handler(store))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                url=f"http://127.0.0.1:{server.server_port}"
                page=urllib.request.urlopen(url+"/").read().decode()
                self.assertIn("Refresh record",page)
                self.assertIn("loaded_version",page)
                self.assertNotIn("version conflict",page.lower())
                b={"customer_id":"C-014","loaded_version":"1","renewal_contact":"Riley Park","billing_email":"ap@northwind.example"}
                req=urllib.request.Request(url+"/save/B",data=json.dumps(b).encode(),headers={"Content-Type":"application/json"})
                self.assertEqual(json.load(urllib.request.urlopen(req))["committed_version"],2)
                a={"customer_id":"C-014","loaded_version":"1","renewal_contact":"Jordan Lee","billing_email":"billing-old@northwind.example"}
                req=urllib.request.Request(url+"/save/A",data=json.dumps(a).encode(),headers={"Content-Type":"application/json"})
                json.load(urllib.request.urlopen(req))
                self.assertTrue(fx.lost_update_signature(store.data))
                reloaded=urllib.request.urlopen(url+"/").read().decode()
                self.assertIn("Jordan Lee",reloaded)
                self.assertIn("ap@northwind.example",reloaded)
            finally:
                server.shutdown();server.server_close()
if __name__=="__main__": unittest.main()

