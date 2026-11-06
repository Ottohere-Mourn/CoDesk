"""Guest-app HTTP smoke tests; no Guest, model endpoint, or external network."""
import json, tempfile, threading, unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from scripts import data_rel1_app_v1 as app
from scripts import data_rel1_fixture_v1 as fx

class DataRel1AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='data-rel1-test-')
        self.state=app.State(self.temp.name+'/state.json')
        self.server=app.create_server(self.state,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.temp.cleanup()
    def get(self,path):
        try:
            with urlopen(self.base+path,timeout=3) as r:return r.status,r.headers.get('Content-Type'),r.read()
        except HTTPError as e:return e.code,e.headers.get('Content-Type'),e.read()
    def post(self,path,obj):
        req=Request(self.base+path,data=json.dumps(obj).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urlopen(req,timeout=3) as r:return r.status,json.loads(r.read())
        except HTTPError as e:return e.code,json.loads(e.read())
    def test_server_is_guest_loopback_only_and_has_no_external_publish_route(self):
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
        status,ctype,body=self.get('/health');self.assertEqual(status,200);self.assertIn('loopback_only',body.decode())
        self.assertEqual(self.get('/api/publish')[0],404)
        self.assertEqual(self.get('/case/exporter')[0],200)
    def test_shared_order_creates_exact_stale_package_failure(self):
        self.assertEqual(self.post('/api/build',{'actor':'A'})[0],200)
        before=fx.evaluate_actor(self.state.data,'A');self.assertTrue(before['success'],before)
        self.assertEqual(self.post('/api/amendment',{'actor':'B'})[0],200)
        a=fx.evaluate_actor(self.state.data,'A');b=fx.evaluate_actor(self.state.data,'B')
        self.assertFalse(a['success'],a);self.assertTrue(b['success'],b)
        self.assertFalse(a['checks']['rows_match_current_eligible_subjects'])
    def test_private_clones_both_pass_same_actor_oracle(self):
        wa=fx.initial_workspace();fx.build_ready_package(wa)
        wb=fx.initial_workspace();fx.register_exclusion(wb,fx.RESTRICTION_EVIDENCE)
        self.assertTrue(fx.evaluate_episode({'A':wa,'B':wb})['success'])
    def test_natural_recovery_restores_both_actor_goals(self):
        self.post('/api/build',{'actor':'A'});self.post('/api/amendment',{'actor':'B'})
        old=self.state.data['packages'][0]['package_id']
        self.assertEqual(self.post('/api/revoke',{'actor':'A','package_id':old})[0],200)
        self.assertEqual(self.post('/api/build',{'actor':'A'})[0],200)
        result=fx.evaluate_episode({'A':self.state.data,'B':self.state.data})
        self.assertTrue(result['success'],result)
    def test_role_boundaries_and_duplicate_actions_are_checked(self):
        self.assertEqual(self.post('/api/build',{'actor':'B'})[0],403)
        self.assertEqual(self.post('/api/amendment',{'actor':'A'})[0],403)
        self.assertEqual(self.post('/api/build',{'actor':'A'})[0],200)
        self.assertEqual(self.post('/api/build',{'actor':'A'})[0],409)
        self.assertEqual(self.post('/api/amendment',{'actor':'B'})[0],200)
        self.assertEqual(self.post('/api/amendment',{'actor':'B'})[0],409)
    def test_reset_returns_exact_initial_fixture(self):
        self.post('/api/build',{'actor':'A'});self.post('/api/amendment',{'actor':'B'})
        self.assertEqual(self.post('/api/reset',{})[0],200)
        _,_,raw=self.get('/api/state');state=json.loads(raw)
        self.assertEqual(state['policy_version'],1);self.assertEqual(state['packages'],[]);self.assertEqual(state['exclusions'],[])

if __name__=='__main__':unittest.main()
