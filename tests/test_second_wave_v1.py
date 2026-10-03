import json,tempfile,unittest,ast
from pathlib import Path
from itertools import product
from swcub.production_v1 import (DOMAINS,LAYOUTS,_PROFILE_ROWS,build_instance,materialize,
    evaluate_oracle,_positive_state,_negative_state,canonical_bytes,sha256)
from swcub.second_wave_v1 import SECOND_WAVE
from swcub.runtime_v1 import build_runtime_registry
from swcub.runtime_bindings_v1 import build_runtime_binding_registry,concrete_binding_refs,OperationRuntimeObserver
from swcub.runtime_execution_v1 import DeterministicRuntimeScheduler,EventGate,RuntimeExecutor,Outcome
from swcub.fake_runtime_backend_v1 import FakeGuestBackend,fake_actor_factory
ROOT=Path(__file__).resolve().parents[1]
class SecondWaveWorkflowTests(unittest.TestCase):
 def test_all_second_wave_instances_are_deterministic_and_oracle_gated(self):
  with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
   ra,rb=Path(a),Path(b)
   for wid in SECOND_WAVE:
    before=len(list((ra/'instances').iterdir())) if (ra/'instances').exists() else 0
    for root in (ra,rb):
     (root/'instances').mkdir(exist_ok=True);(root/'fixtures').mkdir(exist_ok=True);(root/'evaluators').mkdir(exist_ok=True)
    for domain,profile in product(DOMAINS,_PROFILE_ROWS[wid]):
     x=materialize(build_instance(wid,domain,profile,LAYOUTS[0],20261003,ra),ra)
     y=materialize(build_instance(wid,domain,profile,LAYOUTS[0],20261003,rb),rb)
     for asset in x['fixture_files']:
      if asset['path'].endswith('browser-server.py'):ast.parse((ra/asset['path']).read_text())
     self.assertEqual(x['instance_id'],y['instance_id'])
     self.assertEqual(x['signatures'],y['signatures'])
     self.assertEqual(x['fixture_files'],y['fixture_files'])
     ev=json.loads((ra/x['evaluator_path']).read_text())
     self.assertTrue(evaluate_oracle({'evaluator':ev},_positive_state(build_instance(wid,domain,profile,LAYOUTS[0],20261003,ra)))['joint_success'],wid)
     self.assertFalse(evaluate_oracle({'evaluator':ev},_negative_state(build_instance(wid,domain,profile,LAYOUTS[0],20261003,ra)))['joint_success'],wid)
    self.assertEqual(len(list((ra/'instances').iterdir()))-before,20)
 def test_every_workflow_binding_and_topology_fake_lifecycle(self):
  registry=build_runtime_registry();bindings=build_runtime_binding_registry()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for wid,row in SECOND_WAVE.items():
    dirs={name:root/name for name in ('instances','fixtures','evaluators')}
    for d in dirs.values():d.mkdir(exist_ok=True)
    inst=materialize(build_instance(wid,DOMAINS[0],_PROFILE_ROWS[wid][0],LAYOUTS[0],20261003,root),root)
    self.assertEqual(set(concrete_binding_refs(wid)),{'setup','observer','evaluator','reset','cleanup'})
    binding=bindings[wid]
    self.assertTrue(all(callable(binding[x]) for x in ('setup','initial_verifier','evaluator','event_gate')))
    plan=registry.compile(inst,root)
    self.assertFalse(plan['runtime_execution_binding']['missing_components'],(wid,plan['runtime_execution_binding']['missing_components']))
    self.assertEqual(set(plan['topologies']),{'solo','ma_id','ma_sd'})
    for topology,actors in [('solo',['A']),('solo',['B']),('ma_id',['A','B']),('ma_sd',['A','B'])]:
     run={'run_id':f'fake-{wid}-{topology}-'+''.join(actors),'topology':topology,'active_actors':actors}
     gate=binding['event_gate'](plan,run)
     backend=FakeGuestBackend();sched=DeterministicRuntimeScheduler(fake_actor_factory,backend,step_budget=10,gate=gate)
     with tempfile.TemporaryDirectory() as output:
      result=RuntimeExecutor().execute(registry.get(wid),plan,run,backend,sched,Path(output))
     self.assertEqual(result['status'],Outcome.SUCCESS.value,(wid,topology,actors,result))
     self.assertTrue(result['reset'][0]['verified']);self.assertTrue(result['cleanup'][0]['ownership_verified'])

 def test_operation_observer_guard_integrity_detects_non_target_writer_changes(self):
  wid='F-05';domain=DOMAINS[0];profile=_PROFILE_ROWS[wid][0]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for name in ('instances','fixtures','evaluators'):(root/name).mkdir()
   record=materialize(build_instance(wid,domain,profile,LAYOUTS[0],20261003,root),root)
   plan=build_runtime_registry().compile(record,root)
   class Guest:
    fixtures={};files={}
   guest=Guest()
   for asset in plan['fixture_assets']:
    path=asset['guest_path'];data=Path(asset['host_path']).read_bytes();guest.fixtures[path]=data;guest.files[path]=data
   class Backend:
    def _command(self,g,args):return g.files[args[-1]].decode()
   observer=OperationRuntimeObserver(wid)
   self.assertTrue(observer._guards_intact([guest],plan,Backend()))
   writer=next(x['guest_path'] for x in plan['fixture_assets'] if x['guest_path'].endswith('document.fodt'))
   import xml.etree.ElementTree as ET
   raw=ET.fromstring(guest.files[writer]);ns='urn:oasis:names:tc:opendocument:xmlns:text:1.0'
   paras=list(raw.iter('{'+ns+'}p'));paras[-1].text='tampered guard'
   guest.files[writer]=ET.tostring(raw,encoding='utf-8')
   self.assertFalse(observer._guards_intact([guest],plan,Backend()))
