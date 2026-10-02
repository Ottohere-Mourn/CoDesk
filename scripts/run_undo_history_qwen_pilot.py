#!/usr/bin/env python3
from __future__ import annotations
import argparse,base64,hashlib,json,os,secrets,socket,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import run_writer_calc_v1 as base
from scripts import probe_selection_active_object_v1 as task
from scripts.run_writer_calc_v1 import LocalQwenInferenceClient
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.osworld_agent_actor import OSWorldAgentActor
from swcub.resource_safety import ensure_resource_identity
from mm_agents.qwen3vl_agent import Qwen3VLAgent
TASK_ID='CODESK-FAMILY-UNDO-HISTORY-001';VERSION='0.1.2-qwen-prompt-calibration';BUDGET=20

def prompt(actor):
 if actor=='actor_a': return ('In the open LibreOffice Calc document, enter the exact temporary text A-TEMP in cell B2, press Enter, and save. Then use Undo exactly once to remove your temporary edit and restore the original B2 value "B2 seed". Do not change C3 or any other cells. Save the final document and, when done, return DONE. In a shared run, continue this goal after the other actor has finished its C3 edit; do not undo before that edit.')
 return ('In the open LibreOffice Calc document, first press Ctrl+Home to select A1, then press Right twice and Down twice to select C3. Change C3 to the exact text B-2042, press Enter, and save. Preserve all other cells. When done, return DONE.')

def main():
 p=argparse.ArgumentParser();p.add_argument('--condition',choices=['solo_a','solo_b','ma_id','ma_sd'],required=True);p.add_argument('--run-id',required=True);p.add_argument('--artifact-parent',type=Path,required=True);p.add_argument('--qwen-endpoint',default=os.environ.get('SWCUB_QWEN_INFERENCE_URL','http://127.0.0.1:15485'));a=p.parse_args()
 out=a.artifact_parent.resolve()/a.run_id;out.mkdir(parents=True,exist_ok=False);(out/'overlays').mkdir();ledger=out/'resource-events.jsonl';os.environ.update({'SWCUB_RUN_ID':a.run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays')});os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None);identity=ensure_resource_identity(ledger)
 log=EventLog();envs={};desks={};actors={};bindings={};timeline=[];active=[];gate={'phase':'disabled','a_edit_confirmed':False,'b_edit_confirmed':False,'b_goal_confirmed':False,'events':[]};start=time.monotonic();phase='endpoint_check'
 report={'run_id':a.run_id,'task_id':TASK_ID,'task_version':VERSION,'condition':a.condition,'actor_implementation':'OSWorld V2.1 Qwen3VLAgent','model_used':True,'scripted_fallback':False,'guest_host':socket.gethostname(),'status':'starting','scheduled_exposure':a.condition in {'ma_id','ma_sd'},'actual_exposure':False,'observed_interference':'unknown','autonomous_recovery':False,'actor_goal_success':{},'actor_steps':{},'timeline':timeline,'gate':gate,'reset_success':False,'reset_checks':{},'agent_execution_errors':{}}
 def readcell(desk,cell):
  py="import json,uno; c=uno.getComponentContext(); r=c.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',c); x=r.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); d=x.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',x); s=d.getCurrentComponent().getSheets().getByIndex(0); q=s.getCellRangeByName(%r); print(json.dumps({'value':q.getString()}))"%cell
  return json.loads(task.cmd(desk,['python3','-c',py],timeout=15).strip().splitlines()[-1])['value']
 def mark(actor,event,details=None):
  who=actor if actor in bindings else 'actor_a';binding=bindings[who];desk=desks[binding];row={'event':event,'actor_id':actor,'binding':binding,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'active_window':task.active(desk),'clipboard_sha256':task.clipboard_digest(desk),'B2':readcell(desk,'B2'),'C3':readcell(desk,'C3'),**(details or {})};timeline.append(row);log.record(actor,'schedule' if actor=='coordinator' else 'instrumentation','undo.'+event,{},row,details={'hidden_observer':True});gate['events'].append(row);return row
 try:
  from urllib.request import urlopen
  with urlopen(a.qwen_endpoint.rstrip('/')+'/health',timeout=10) as r:health=json.loads(r.read())
  if not health.get('ready') or health.get('model')!='Qwen3-VL-30B-A3B-Instruct':raise RuntimeError(f'unexpected inference health {health}')
  def inf_event(row):
   with (out/'inference-events.jsonl').open('a') as f:f.write(json.dumps({'client_host':socket.gethostname(),**row})+'\n')
  client=LocalQwenInferenceClient(endpoint=a.qwen_endpoint,event_callback=inf_event);report['model']={**health,'inference_host':os.environ.get('SWCUB_QWEN_INFERENCE_HOST','4090'),'endpoint':a.qwen_endpoint,'transport':'existing SSH reverse tunnel','config':{'agent':'OSWorld V2.1 Qwen3VLAgent','model':'Qwen3-VL-30B-A3B-Instruct','agent_max_tokens':512,'temperature':0,'top_p':0.9,'action_budget_per_actor':BUDGET}}
  phase='guest_setup';active=['actor_a'] if a.condition=='solo_a' else ['actor_b'] if a.condition=='solo_b' else ['actor_a','actor_b']
  if a.condition=='ma_sd':bindings={x:'shared' for x in active};guest_bindings=['shared']
  elif a.condition=='ma_id':bindings={x:x for x in active};guest_bindings=active.copy()
  else:bindings={active[0]:active[0]};guest_bindings=active.copy()
  for binding in guest_bindings:
   ep,desk=base.make_desktop(binding,log,out);envs[binding]=(ep,desk);desks[binding]=desk;content=base64.b64encode(task.render_calc_fods(task.INITIAL)).decode();create=f"from pathlib import Path; import base64; p=Path({task.GUEST_PATH!r}); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(base64.b64decode({content!r}))";task.cmd(desk,['python3','-c',create],timeout=20);task.cmd(desk,['bash','-lc',f"soffice --nologo --norestore --nofirststartwizard --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' --calc {task.GUEST_PATH} >/tmp/codesk-undo-soffice.log 2>&1 & sleep 7"],timeout=15);ready=base.wait_for_app_document(ep,desk,'calc',task.GUEST_PATH,out/binding/'readiness',timeout=120);state={'B2':readcell(desk,'B2'),'C3':readcell(desk,'C3')};
   if state!={'B2':'B2 seed','C3':'C3 seed'}:raise RuntimeError(f'initial fixture mismatch: {state}')
   report.setdefault('readiness',{})[binding]={'app':ready,'initial_cells':state,'active_window':task.active(desk)}
  gate['phase']='await_a_edit' if a.condition in {'ma_id','ma_sd'} else 'disabled';phase='actor_setup'
  def actor_event(actor,row):
   ep=envs[bindings[actor]][0];snap=ep.snapshot();log.record(actor,'model_decision','osworld.qwen3vl.predict',snap,snap,details={'actor_event':row})
  def boundary(actor,obj,action):
   desk=desks[bindings[actor]]
   if gate['phase']=='await_a_edit' and actor=='actor_a' and readcell(desk,'B2')=='A-TEMP':gate['phase']='b_turn';gate['a_edit_confirmed']=True;mark(actor,'a_edit_committed_pause',{'complete_action_boundary':True,'action':str(action)});obj.pause()
   elif gate['phase']=='a_resume' and actor=='actor_a':
    row=mark(actor,'actor_a_post_resume_action',{'action':str(action)});report.setdefault('post_resume_actions',[]).append(row)
  def make_actor(actor):
   agent=Qwen3VLAgent(platform='ubuntu',model='qwen3-vl',max_tokens=512,action_space='pyautogui',observation_type='screenshot',coordinate_type='relative');agent.call_llm=lambda payload,model,c=client,aid=actor:c.complete(payload,model,actor_id=aid);return OSWorldAgentActor(agent,prompt(actor),actor_id=actor,max_steps=BUDGET,event_callback=lambda row,aid=actor:actor_event(aid,row),artifact_directory=out/'model-actors'/actor,action_boundary_callback=(lambda obj,action,aid=actor:boundary(aid,obj,action)) if actor=='actor_a' and a.condition in {'ma_id','ma_sd'} else None)
  actors={x:make_actor(x) for x in active};phase='model_execution'
  def run_actor(actor):
   obj=actors[actor];ctx=ActorContext(actor,envs[bindings[actor]][0],'gui');turns=0
   while not obj.terminated and not obj.paused and turns<BUDGET+5:
    try:obj.run_step(ctx);turns+=1
    except Exception as exc:report['agent_execution_errors'][actor]={'type':type(exc).__name__,'message':str(exc),'steps':obj.steps};log.record(actor,'agent_error','osworld.actor_step_failed',{}, {},outcome='failed',details=report['agent_execution_errors'][actor]);break
  if a.condition in {'solo_a','solo_b'}:who=active[0];timeline.append({'event':'solo_actor_start','actor_id':who});run_actor(who)
  else:
   timeline.append({'event':'actor_a_start','actor_id':'actor_a'});run_actor('actor_a');gate['b2_after_a']=readcell(desks[bindings['actor_a']],'B2')
   if gate['a_edit_confirmed']:
    gate['phase']='b_turn';mark('coordinator','actor_b_start',{'after':'a_edit_committed_pause'});run_actor('actor_b');gate['c3_after_b']=readcell(desks[bindings['actor_b']],'C3');gate['b_edit_confirmed']=gate['c3_after_b']=='B-2042';gate['b_goal_confirmed']=gate['b_edit_confirmed'];mark('coordinator','actor_a_resume',{'after':'actor_b_goal','b_goal_confirmed':gate['b_goal_confirmed']});gate['phase']='a_resume';actors['actor_a'].resume();run_actor('actor_a')
   else:gate['phase']='no_a_edit_gate';mark('coordinator','actor_a_finished_before_gate',{'terminated':actors['actor_a'].terminated});run_actor('actor_b')
   report['schedule_sequence_valid']=bool(gate['a_edit_confirmed'] and gate['b_edit_confirmed'] and gate['b_goal_confirmed']);report['actual_exposure']=bool(report['schedule_sequence_valid'] and a.condition=='ma_sd');
   if a.condition=='ma_id':report['control_sequence_valid']=report['schedule_sequence_valid']
  phase='evaluation'
  for who in active:report['actor_steps'][who]=actors[who].steps
  if a.condition=='ma_sd':
   d=desks['shared'];actual={'actor_a':readcell(d,'B2'),'actor_b':readcell(d,'C3')};report['evaluation']={'actual_cells':actual,'expected_cells':{'actor_a':'B2 seed','actor_b':'B-2042'}};report['actor_goal_success']={'actor_a':actual['actor_a']=='B2 seed','actor_b':actual['actor_b']=='B-2042'};windows={r['active_window']['xid'] for r in timeline if 'active_window'in r};clips={r['clipboard_sha256'] for r in timeline if 'clipboard_sha256'in r};report['same_top_level_window']=len(windows)==1;report['clipboard_unchanged']=len(clips)<=1;report['observed_interference']=bool(report['actual_exposure'] and actual=={'actor_a':'A-TEMP','actor_b':'C3 seed'} and report['same_top_level_window'] and report['clipboard_unchanged']);report['autonomous_recovery']=bool(report['actual_exposure'] and all(report['actor_goal_success'].values()) and bool(report.get('post_resume_actions')));report['interference_evidence']={'c3_after_b':gate.get('c3_after_b'),'final_cells':actual,'post_resume_actions':report.get('post_resume_actions',[])}
  else:
   report['evaluation']={}
   for who in active:
    d=desks[bindings[who]];actual={'B2':readcell(d,'B2'),'C3':readcell(d,'C3')};expected={'B2':'B2 seed','C3':'C3 seed'};cell='B2' if who=='actor_a' else 'C3';expected[cell]='B2 seed' if who=='actor_a' else 'B-2042';report['evaluation'][who]={'actual_cells':actual,'expected_cells':expected};report['actor_goal_success'][who]=actual==expected
   report['observed_interference']=False
  report['joint_success']=all(report['actor_goal_success'].values());report['status']='completed';phase='reset'
  for binding,(ep,_desk) in list(envs.items()):
   ep.copy_artifacts(out/f'guest-{ep.environment_id}-artifacts');ep.close();reset_ep,reset_desk=base.make_desktop(binding+'_reset',log,out);clean=task.cmd(reset_desk,['bash','-lc',f'test ! -e {task.GUEST_PATH} && echo reset_clean'],timeout=15);report['reset_checks'][binding]={'success':'reset_clean'in clean,'task_file_absent':'reset_clean'in clean,'guest_id':reset_ep.snapshot().get('guest_container_id')};reset_ep.close()
  envs.clear();report['reset_success']=all(v.get('success') for v in report['reset_checks'].values())
 except Exception as exc:
  report['status']='invalid_infra' if phase in {'endpoint_check','guest_setup','actor_setup'} else 'agent_or_runner_failure';report['error']={'phase':phase,'type':type(exc).__name__,'message':str(exc)}
  for ep,_d in envs.values():
   try:ep.copy_artifacts(out/'failure-artifacts');ep.close()
   except Exception:pass
  envs.clear()
 finally:
  report['wall_seconds']=round(time.monotonic()-start,2);report['timeline']=timeline;log.write(out/'events.jsonl');report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None;source=base.git_source_state();(out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');(out/'provenance.json').write_text(json.dumps({'run_id':identity.run_id,'source':source,'task_id':TASK_ID,'task_version':VERSION,'model_used':True,'artifact_sha256':{str(x.relative_to(out)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(out.rglob('*')) if x.is_file() and x.name!='provenance.json' and 'overlays' not in x.parts}},indent=2)+'\n')
  for actor,obj in actors.items():(out/f'{actor}-trace.json').write_text(json.dumps(obj.trace,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'run_id':a.run_id,'condition':a.condition,'status':report['status'],'joint_success':report.get('joint_success'),'actor_goal_success':report.get('actor_goal_success'),'scheduled_exposure':report.get('scheduled_exposure'),'actual_exposure':report.get('actual_exposure'),'interference':report.get('observed_interference'),'recovery':report.get('autonomous_recovery'),'reset':report.get('reset_success'),'error':report.get('error'),'artifacts':str(out)}));return 0 if report['status']=='completed' and report.get('reset_success') else 1
if __name__=='__main__':raise SystemExit(main())
