from __future__ import annotations
import json, tempfile, unittest
import base64,threading,urllib.request
import importlib.util, sys, types
from pathlib import Path
from integration.build_assets import build
from private.wellposedness import gates
from private.grade import grade
from integration.service import _server

CASE=Path(__file__).resolve().parents[1]

class Conc08Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="conc08-tests-");cls.root=Path(cls.temp.name);build(cls.root)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_01_assets_formula_template_and_checkpoints(self):
        b=self.root/"CONC-08";truth=json.loads((b/"private/expected.json").read_text(encoding="utf-8"))
        self.assertEqual(len(truth["rev_rows"]),36);self.assertEqual(len(truth["hr_rows"]),36)
        self.assertEqual(len(truth["memos"]),4);self.assertEqual(len(truth["allowances"]),4)
        self.assertTrue(all((b/f"guest/in_a/credit_memos/CM-{i:02d}.png").is_file() for i in range(1,5)))
        self.assertTrue(all((b/f"guest/in_b/allowances/ALW-{i:02d}.png").is_file() for i in range(1,5)))
        self.assertTrue((b/"guest/out_a/Finance_Close.pptx").is_file())
        self.assertFalse((b/"guest/in_a/Finance_Close.pptx").exists())
        self.assertTrue((b/"guest/out_b/HR_Close.pptx").is_file())
        self.assertFalse((b/"guest/in_b/HR_Close.pptx").exists())
    def test_02_finance_deck_upload_source_matches_generated_asset_and_workspace_destination(self):
        package=types.ModuleType("evaluation_examples");package.__path__=[]
        task_class=types.ModuleType("evaluation_examples.task_class");task_class.__path__=[]
        common=types.ModuleType("evaluation_examples.task_class.pg_common");common.HOME="/home/user"
        grade=types.ModuleType("evaluation_examples.task_class.conc08_grade");grade.grade=lambda *a,**k:{}
        sys.modules.update({"evaluation_examples":package,"evaluation_examples.task_class":task_class,
                            "evaluation_examples.task_class.pg_common":common,
                            "evaluation_examples.task_class.conc08_grade":grade})
        task_class.pg_common=common;task_class.conc08_grade=grade
        bridge_path=CASE/"integration/pg_conc08.py"
        spec=importlib.util.spec_from_file_location("conc08_path_test_bridge",bridge_path)
        bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
        pair=next(x for x in bridge.FILES if x[1]=="/home/user/workspace/out_a/Finance_Close.pptx")
        self.assertEqual(pair[0],"CONC-08/guest/out_a/Finance_Close.pptx")
        self.assertTrue((self.root/"CONC-08/guest/out_a/Finance_Close.pptx").is_file())
        pair=next(x for x in bridge.FILES if x[1]=="/home/user/workspace/out_b/HR_Close.pptx")
        self.assertEqual(pair[0],"CONC-08/guest/out_b/HR_Close.pptx")
        self.assertTrue((self.root/"CONC-08/guest/out_b/HR_Close.pptx").is_file())
    def test_03_preflight_gates_pass_and_real_guest_is_pending(self):
        r=gates();self.assertTrue(all(r[k] for k in ("gate1_pristine_fail","gate2_gt_seq_ab_exists","gate3_gt_seq_ba_exists","gate4_gt_naive_race_corrupts","gate5_fixture_feasible")))
    def test_04_runtime_text_is_english(self):
        b=self.root/"CONC-08"
        texts=[p.read_text(encoding="utf-8") for p in (CASE/"integration/task_conc08a.py",CASE/"integration/task_conc08b.py",CASE/"integration/service.py",b/"guest/in_a/close_spec_a.txt",b/"guest/in_b/close_spec_b.txt")]
        self.assertFalse(any(any("\u4e00"<=c<="\u9fff" for c in t) for t in texts))
    def test_05_grade_has_46_named_boolean_checkpoints(self):
        b=self.root/"CONC-08";missing=self.root/"missing";missing.mkdir(exist_ok=True)
        r=grade(missing,{},b/"private/expected.json",self.root/"render")
        expected={f"A{i:02d}" for i in range(1,24)}|{f"B{i:02d}" for i in range(1,24)}
        self.assertEqual(set(r["checks"]["actor_a"])|set(r["checks"]["actor_b"]),expected)
    def test_06_finance_and_people_sessions_do_not_cross_route(self):
        state=self.root/"service-state.json";assets=self.root/"site"
        a=_server("127.0.0.1",0,"a",str(assets),str(state));b=_server("127.0.0.1",0,"b",str(assets),str(state))
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (a,b)]
        for t in threads:t.start()
        try:
            def get(server):
                with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/",timeout=2) as r:return r.read().decode(),r.headers.get("Set-Cookie","").split(";",1)[0]
            apage,ac=get(a);bpage,bc=get(b);self.assertIn("FinAudit",apage);self.assertIn("HRDesk",bpage);self.assertTrue(ac.startswith("fin_session="));self.assertTrue(bc.startswith("hr_session="))
            png=base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()
            def post(server,actor,cookie):
                body=json.dumps({"actor":actor,"id":1,"code":"TEST-ABCD-1234-XYZZ","amount":"12.50","category":"VAT" if actor=="a" else "Engineering","file_name":"proof.png","file_b64":png}).encode()
                req=urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/submit",data=body,headers={"Content-Type":"application/json","Cookie":f"{ac}; {bc}; {cookie}"})
                with urllib.request.urlopen(req,timeout=2) as r:return json.loads(r.read())
            post(a,"a",ac);post(b,"b",bc)
            final=json.loads(state.read_text(encoding="utf-8"));self.assertEqual(len(final["records"]["a"]),1);self.assertEqual(len(final["records"]["b"]),1)
        finally:
            for s in (a,b):s.shutdown();s.server_close()

if __name__=="__main__":unittest.main()
