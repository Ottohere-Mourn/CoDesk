#!/usr/bin/env python3
"""Bounded real-Guest probe for shared Calc undo-history contention."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import run_writer_calc_v1 as base
from scripts import probe_selection_active_object_v1 as task
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
TASK_ID='CODESK-FAMILY-UNDO-HISTORY-001'; VERSION='0.1.0-probe'
GOALS={'actor_a':{'cell':'B2','value':'A-TEMP','final':'B2 seed'},'actor_b':{'cell':'C3','value':'B-2042','final':'B-2042'}}
def main():
 p=argparse.ArgumentParser(); p.add_argument('--condition',choices=['solo_a','solo_b','ma_id','ma_sd','ma_sd_recovery'],required=True); p.add_argument('--run-id',required=True); p.add_argument('--artifact-parent',type=Path,required=True); a=p.parse_args()
 out=a.artifact_parent.resolve()/a.run_id; out.mkdir(parents=True,exist_ok=False); (out/'overlays').mkdir(); ledger=out/'resource-events.jsonl'
 os.environ.update({'SWCUB_RUN_ID':a.run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays')}); os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None); ident=ensure_resource_identity(ledger)
 log=EventLog(); envs={}; desks={}; events=[]; report={'run_id':a.run_id,'task_id':TASK_ID,'task_version':VERSION,'condition':a.condition,'actor_implementation':'scripted','scheduled_exposure':a.condition in {'ma_id','ma_sd','ma_sd_recovery'},'actual_exposure':False,'observed_interference':'unknown','autonomous_recovery':False,'actor_goal_success':{},'status':'starting'}; start=time.monotonic(); phase='guest_startup'
 def open_guest(binding):
  ep,d=base.make_desktop(binding,log,out); envs[binding]=ep; desks[binding]=d
  create='from pathlib import Path; import base64; p=Path(%r); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(base64.b64decode(%r))'%(task.GUEST_PATH,__import__('base64').b64encode(task.render_calc_fods(task.INITIAL)).decode())
  task.cmd(d,['python3','-c',create],timeout=20)
  task.cmd(d,['bash','-lc',"soffice --nologo --norestore --nofirststartwizard --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' --calc %s >/tmp/codesk-undo-soffice.log 2>&1 & sleep 7"%task.GUEST_PATH],timeout=15)
  ready=base.wait_for_app_document(ep,d,'calc',task.GUEST_PATH,out/binding/'readiness',timeout=120)
  report.setdefault('readiness',{})[binding]={'app':ready,'initial_selection':task.selection(d),'active_window':task.active(d)}
 def mark(actor,binding,event,**extra):
  row={'actor_id':actor,'event':event,'selection':task.selection(desks[binding]),'active_window':task.active(desks[binding]),'clipboard_sha256':task.clipboard_digest(desks[binding]),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**extra}; events.append(row); log.record(actor,'instrumentation','undo.'+event,{},row,details={'hidden_observer':True}); return row
 def do_value(actor,binding,value):
  ctx=ActorContext(actor,envs[binding],'gui'); cell=GOALS[actor]['cell']; task.select_cell(ctx,cell); ctx.type_text(value); ctx.press_key('Enter'); mark(actor,binding,'edit_committed',cell=cell,value=value); ctx.press_key('ctrl+s'); time.sleep(1)
 try:
  phase='setup'
  if a.condition in ('solo_a','solo_b'):
   who='actor_a' if a.condition=='solo_a' else 'actor_b'; open_guest(who); do_value(who,who,GOALS[who]['value'])
   if who=='actor_a': ActorContext(who,envs[who],'gui').press_key('ctrl+z'); mark(who,who,'undo_committed',expected='remove A-TEMP'); ActorContext(who,envs[who],'gui').press_key('ctrl+s'); time.sleep(1)
   ev=task.evaluate(desks[who],[who]); expected=GOALS[who]['final']; actual=ev['actual_grid'][int(GOALS[who]['cell'][1:])-1][ord(GOALS[who]['cell'][0])-65]; report['actor_goal_success'][who]=actual==expected; report['evaluation']={'expected_final':expected,'actual_final':actual,'grid':ev['actual_grid'],'success':report['actor_goal_success'][who]}
  else:
   shared=a.condition in {'ma_sd','ma_sd_recovery'}; bindings={'actor_a':'shared' if shared else 'actor_a','actor_b':'shared' if shared else 'actor_b'}
   for binding in dict.fromkeys(bindings.values()): open_guest(binding)
   report['bindings']=bindings
   # A performs a temporary edit. The scheduler pauses only at this completed-action boundary.
   do_value('actor_a',bindings['actor_a'],GOALS['actor_a']['value']); mark('coordinator',bindings['actor_a'],'pause_after_A_edit',shared=shared)
   # B independently commits its target. MA-ID uses the same order on an equal fixture.
   do_value('actor_b',bindings['actor_b'],GOALS['actor_b']['value'])
   # Resume A's planned Undo. No action is injected beyond the task's explicit undo goal.
   mark('coordinator',bindings['actor_a'],'resume_A_after_B_commit',shared=shared)
   ActorContext('actor_a',envs[bindings['actor_a']],'gui').press_key('ctrl+z'); mark('actor_a',bindings['actor_a'],'undo_committed',expected='remove A-TEMP')
   ActorContext('actor_a',envs[bindings['actor_a']],'gui').press_key('ctrl+s'); time.sleep(1)
   if shared:
    mid=task.evaluate(desks['shared'],['actor_a','actor_b'])['actual_grid']; mid_cells={'B2':mid[1][1],'C3':mid[2][2]}; report['interference_snapshot_after_undo']=mid_cells; report['same_top_level_window']=len({r['active_window']['xid'] for r in events})==1; report['clipboard_unchanged']=len({r['clipboard_sha256'] for r in events})<=1; report['observed_interference']=bool(mid_cells=={'B2':'A-TEMP','C3':'C3 seed'} and report['same_top_level_window'] and report['clipboard_unchanged'])
   if a.condition=='ma_sd_recovery':
    do_value('actor_b',bindings['actor_b'],GOALS['actor_b']['value']); mark('actor_b',bindings['actor_b'],'recovery_reapplied_B_goal',cell='C3',value=GOALS['actor_b']['value']); ctx=ActorContext('actor_a',envs[bindings['actor_a']],'gui'); task.select_cell(ctx,'B2'); ctx.type_text('B2 seed'); ctx.press_key('Enter'); ctx.press_key('ctrl+s'); time.sleep(1); mark('actor_a',bindings['actor_a'],'recovery_restored_A_goal',cell='B2',value='B2 seed')
   if shared:
    ev=task.evaluate(desks['shared'],['actor_a','actor_b']); grid=ev['actual_grid']; actual={'actor_a':grid[1][1],'actor_b':grid[2][2]}; report['evaluation']={'actual_grid':grid,'actual_cells':actual,'expected_cells':{'actor_a':'B2 seed','actor_b':'B-2042'}}; report['actor_goal_success']={'actor_a':actual['actor_a']=='B2 seed','actor_b':actual['actor_b']=='B-2042'}
    report['actual_exposure']=True
   else:
    report['evaluation']={};
    for who,binding in bindings.items():
     ev=task.evaluate(desks[binding],[who]); cell=GOALS[who]['cell']; val=ev['actual_grid'][int(cell[1:])-1][ord(cell[0])-65]; report['evaluation'][who]=ev; report['actor_goal_success'][who]=val==GOALS[who]['final']
    report['actual_exposure']=False; report['observed_interference']=False
  report['joint_success']=all(report['actor_goal_success'].values());
  if a.condition=='ma_sd_recovery': report['recovery']={'attempted':True,'success':report['joint_success']};
  report['status']='completed'; phase='reset'
  for binding,ep in list(envs.items()): ep.copy_artifacts(out/f'guest-{ep.environment_id}-artifacts'); ep.close()
  envs.clear(); report['reset_success']=True; report['reset_semantics']='owned guest closed; fixture recreated on next run'
 except Exception as exc:
  report['status']='invalid_setup' if phase in {'guest_startup','setup'} else 'probe_error'; report['error']={'phase':phase,'type':type(exc).__name__,'message':str(exc)}
  for ep in envs.values():
   try: ep.copy_artifacts(out/'failure-artifacts'); ep.close()
   except Exception: pass
  envs.clear()
 finally:
  report['wall_seconds']=round(time.monotonic()-start,2); report['events']=events; log.write(out/'events.jsonl'); report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
  (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n'); (out/'provenance.json').write_text(json.dumps({'run_id':ident.run_id,'source':base.git_source_state(),'task_id':TASK_ID,'task_version':VERSION,'goals':GOALS,'event_sha256':hashlib.sha256(json.dumps(events,sort_keys=True).encode()).hexdigest()},indent=2)+'\n')
 print(json.dumps({'run_id':a.run_id,'status':report['status'],'success':report.get('joint_success'),'goals':report.get('actor_goal_success'),'exposure':report.get('actual_exposure'),'interference':report.get('observed_interference'),'reset':report.get('reset_success'),'artifacts':str(out),'error':report.get('error')})); return 0 if report['status']=='completed' else 1
if __name__=='__main__': raise SystemExit(main())
