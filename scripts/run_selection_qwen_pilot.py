#!/usr/bin/env python3
"""Real Qwen3VLAgent pilot for the bounded Calc selection-state candidate.

Uses the repository's pinned agent and Actor adapter. Scheduler only pauses/resumes
at OSWorld action boundaries; it never submits actions or changes agent history.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, secrets, socket, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from scripts import run_writer_calc_v1 as base
from scripts.run_writer_calc_v1 import LocalQwenInferenceClient
from scripts import probe_selection_active_object_v1 as task
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.osworld_agent_actor import OSWorldAgentActor, OSWorldAgentActorError
from swcub.resource_safety import ensure_resource_identity
from mm_agents.qwen3vl_agent import Qwen3VLAgent
BUDGET=20

def prompt(actor):
    s=task.TARGETS[actor]
    col=ord(s['cell'][0])-ord('A'); row=int(s['cell'][1:])-1
    moves=[]
    if col: moves.append(f"press Right {col} time(s)")
    if row: moves.append(f"press Down {row} time(s)")
    navigation=" then ".join(["press Ctrl+Home"]+moves)
    return (f"In the open LibreOffice Calc sheet, change cell {s['cell']} to the exact text {s['value']}. "
            f"Use this keyboard navigation from A1: {navigation}. "
            "Type the value, press Enter, then press Ctrl+S once. Preserve all other cells. "
            "After saving, make no more GUI changes and return DONE; do not use the File menu or repeat the save.")

def main():
    p=argparse.ArgumentParser(); p.add_argument('--condition',choices=['solo_a','solo_b','ma_id','ma_sd'],required=True); p.add_argument('--run-id',required=True); p.add_argument('--artifact-parent',type=Path,required=True); p.add_argument('--qwen-endpoint',default=os.environ.get('SWCUB_QWEN_INFERENCE_URL','http://127.0.0.1:15485')); a=p.parse_args()
    out=a.artifact_parent.resolve()/a.run_id; out.mkdir(parents=True,exist_ok=False); (out/'overlays').mkdir(); ledger=out/'resource-events.jsonl'
    os.environ.update({'SWCUB_RUN_ID':a.run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays')}); os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None); identity=ensure_resource_identity(ledger)
    log=EventLog(); envs={}; desktops={}; actors={}; bindings={}; timeline=[]; start=time.monotonic(); phase='endpoint_check'
    report={'run_id':a.run_id,'task_id':task.TASK_ID,'task_version':'0.1.1-prompt-calibration','condition':a.condition,'actor_implementation':'OSWorld V2.1 Qwen3VLAgent','model_used':True,'scripted_fallback':False,'guest_host':socket.gethostname(),'status':'starting','scheduled_exposure':a.condition in {'ma_id','ma_sd'},'actual_exposure':False,'observed_interference':'unknown','autonomous_recovery':False,'recovery':{},'actor_goal_success':{},'actor_steps':{},'actions_after_resume':[],'timeline':timeline,'reset_success':False,'agent_execution_errors':{},'reset_checks':{}}
    phase='endpoint_check'
    try:
        from urllib.request import urlopen
        with urlopen(a.qwen_endpoint.rstrip('/')+'/health',timeout=10) as r: health=json.loads(r.read())
        if not health.get('ready') or health.get('model')!='Qwen3-VL-30B-A3B-Instruct': raise RuntimeError(f'unexpected inference service health: {health}')
        def inf_event(row):
            with (out/'inference-events.jsonl').open('a') as f: f.write(json.dumps({'client_host':socket.gethostname(),**row})+'\n')
        client=LocalQwenInferenceClient(endpoint=a.qwen_endpoint,event_callback=inf_event)
        report['model']={**health,'inference_host':os.environ.get('SWCUB_QWEN_INFERENCE_HOST','4090'),'endpoint':a.qwen_endpoint,'transport':'existing SSH reverse tunnel','config':{'agent':'OSWorld V2.1 Qwen3VLAgent','model':'Qwen3-VL-30B-A3B-Instruct','agent_max_tokens':512,'temperature':0,'top_p':0.9,'action_budget_per_actor':BUDGET}}
        phase='guest_setup'
        active=['actor_a'] if a.condition=='solo_a' else ['actor_b'] if a.condition=='solo_b' else ['actor_a','actor_b']
        if a.condition=='ma_sd': bindings={x:'shared' for x in active}; guest_bindings=['shared']
        elif a.condition=='ma_id': bindings={x:x for x in active}; guest_bindings=active.copy()
        else: bindings={active[0]:active[0]}; guest_bindings=active.copy()
        for binding in guest_bindings:
            ep,desk=base.make_desktop(binding,log,out); envs[binding]=(ep,desk); desktops[binding]=desk
            b64=base64.b64encode(task.render_calc_fods(task.INITIAL)).decode(); create=f"from pathlib import Path; import base64; p=Path({task.GUEST_PATH!r}); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(base64.b64decode({b64!r}))"
            task.cmd(desk,['python3','-c',create],timeout=20)
            task.cmd(desk,['bash','-lc',f"soffice --nologo --norestore --nofirststartwizard --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' --calc {task.GUEST_PATH} >/tmp/codesk-selection-soffice.log 2>&1 & sleep 7"],timeout=15)
            ready=base.wait_for_app_document(ep,desk,'calc',task.GUEST_PATH,out/binding/'readiness',timeout=120)
            task.cmd(desk,['python3','-c','import uno; print("UNO_READY")'],timeout=10)
            report.setdefault('readiness',{})[binding]={'app':ready,'initial_selection':task.selection(desk),'active_window':task.active(desk)}
        phase='actor_setup'
        gate={'phase':'await_a_target' if a.condition in {'ma_id','ma_sd'} else 'disabled','a_selection_confirmed':False,'b_selection_confirmed':False,'b_goal_completed':False,'events':[]}; report['selection_gate']=gate
        def event(kind,actor,details):
            binding=bindings.get(actor,bindings[active[0]]); ep,desk=envs[binding]; row={'event':kind,'actor_id':actor,'binding':binding,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selection':task.selection(desk),'active_window':task.active(desk),'clipboard_sha256':task.clipboard_digest(desk),**details}; timeline.append(row); log.record('coordinator','schedule' if actor=='coordinator' else 'instrumentation','selection.'+kind,{},row,details={'hidden_observer':True}); gate['events'].append(row); return row
        def mk_actor(actor):
            agent=Qwen3VLAgent(platform='ubuntu',model='qwen3-vl',max_tokens=512,action_space='pyautogui',observation_type='screenshot',coordinate_type='relative')
            agent.call_llm=lambda payload,model,c=client,aid=actor: c.complete(payload,model,actor_id=aid)
            actor_dir=out/'model-actors'/actor
            def record(row):
                ep=envs[bindings[actor]][0]; snap=ep.snapshot(); log.record(actor,'model_decision','osworld.qwen3vl.predict',snap,snap,observed_revision=row.get('observed_revision'),details=row); row['event_seq']=log.events[-1].seq; row['ts_utc']=log.events[-1].ts_utc
            def boundary(obj,action):
                binding=bindings[actor]; desk=desktops[binding]; sel=task.selection(desk)
                if gate['phase']=='await_a_target' and actor=='actor_a' and sel['start_column']==1 and sel['start_row']==1:
                    gate['phase']='b_turn'; gate['a_selection_confirmed']=True; event('actor_a_target_selected_pause','actor_a',{'expected':'B2','action':str(action),'complete_action_boundary':True}); obj.pause()
                elif gate['phase']=='b_turn' and actor=='actor_b' and not gate['b_selection_confirmed'] and sel['start_column']==2 and sel['start_row']==2:
                    gate['b_selection_confirmed']=True; event('actor_b_target_selected','actor_b',{'expected':'C3','action':str(action),'complete_action_boundary':True})
                elif gate['phase']=='a_resume' and actor=='actor_a':
                    row=event('actor_a_action_after_resume','actor_a',{'action':str(action),'expected_selection':'B2'}); report['actions_after_resume'].append(row)
            return OSWorldAgentActor(agent,prompt(actor),actor_id=actor,max_steps=BUDGET,event_callback=record,artifact_directory=actor_dir,action_boundary_callback=boundary if actor in {'actor_a','actor_b'} and a.condition in {'ma_id','ma_sd'} else None)
        actors={x:mk_actor(x) for x in active}
        phase='model_execution'
        def run_actor(actor,full=False):
            binding=bindings[actor]; ep,desk=envs[binding]; obj=actors[actor]; ctx=ActorContext(actor,ep,'gui'); turns=0
            while not obj.terminated and turns<BUDGET+5:
                if obj.paused: break
                try:
                    obj.run_step(ctx); turns+=1
                except Exception as exc:
                    report['agent_execution_errors'][actor]={'type':type(exc).__name__,'message':str(exc),'stage':'model_or_agent','steps':obj.steps}
                    log.record(actor,'agent_error','osworld.actor_step_failed',{}, {},outcome='failed',details=report['agent_execution_errors'][actor])
                    break
            return obj.terminated
        if a.condition in {'solo_a','solo_b'}:
            who=active[0]; timeline.append({'event':'solo_actor_start','actor_id':who}); run_actor(who)
        else:
            timeline.append({'event':'actor_a_start','actor_id':'actor_a'}); run_actor('actor_a')
            if gate['a_selection_confirmed']:
                gate['phase']='b_turn'; event('actor_b_start','coordinator',{'after':'actor_a_target_selected_pause'}); run_actor('actor_b'); gate['b_goal_completed']=actors['actor_b'].terminated
                event('actor_a_resume','actor_a',{'after':'actor_b_goal','selection_gate_met':gate['a_selection_confirmed']}); gate['phase']='a_resume'; actors['actor_a'].resume(); run_actor('actor_a')
            else:
                gate['phase']='no_selection_gate'; event('actor_a_turn_finished_before_gate','coordinator',{'terminated':actors['actor_a'].terminated}); run_actor('actor_b')
            report['schedule_sequence_valid']=bool(gate['a_selection_confirmed'] and gate['b_selection_confirmed'] and gate['b_goal_completed'])
            report['actual_exposure']=bool(report['schedule_sequence_valid'] and a.condition=='ma_sd')
            if a.condition=='ma_id': report['control_sequence_valid']=report['schedule_sequence_valid']
        phase='evaluation'
        for who in active:
            binding=bindings[who]; desk=desktops[binding]; report['actor_steps'][who]=actors[who].steps
            if a.condition=='ma_sd': pass
            else: report['actor_goal_success'][who]=task.evaluate(desk,[who])['success']
        if a.condition=='ma_sd':
            ev=task.evaluate(desktops['shared'],['actor_a','actor_b']); report['evaluation']=ev; actual=ev['actual_grid']; report['actor_goal_success']={'actor_a':actual[1][1]=='A-7319','actor_b':actual[2][2]=='B-2042'}
            contaminated=actual[2][2]=='A-7319' or actual[2][2] not in ('B-2042','C3 seed')
            report['observed_interference']=bool(report['actual_exposure'] and (not all(report['actor_goal_success'].values()) or contaminated))
            report['interference_evidence']={'selection_before_a_resume':next((e['selection'] for e in reversed(timeline) if e['event']=='actor_a_resume'),None),'first_a_post_resume_actions':report['actions_after_resume'][:3],'final_cells':{'B2':actual[1][1],'C3':actual[2][2]}}
            report['autonomous_recovery']=bool(report['actual_exposure'] and report['actor_goal_success'].get('actor_a') and report['actor_goal_success'].get('actor_b') and report['actions_after_resume'])
        else:
            report['evaluation']={who:task.evaluate(desktops[bindings[who]],[who]) for who in active}
            if a.condition in {'ma_id'}: report['observed_interference']=False
        report['joint_success']=all(report['actor_goal_success'].values()); report['status']='completed'; phase='reset'
        for binding,(ep,_desk) in list(envs.items()):
            ep.copy_artifacts(out/f'guest-{ep.environment_id}-artifacts'); ep.close()
            reset_ep,reset_desk=base.make_desktop(binding+'_reset',log,out)
            clean=task.cmd(reset_desk,['bash','-lc',f'test ! -e {task.GUEST_PATH} && echo reset_clean'],timeout=15)
            row={'success':'reset_clean' in clean,'task_file_absent':'reset_clean' in clean,'guest_id':reset_ep.snapshot().get('guest_container_id')}
            report['reset_checks'][binding]=row; reset_ep.close()
        envs.clear(); report['reset_success']=all(v.get('success') for v in report['reset_checks'].values())
    except Exception as exc:
        report['status']='invalid_infra' if phase in {'endpoint_check','guest_setup','actor_setup'} else 'agent_or_runner_failure'; report['error']={'phase':phase,'type':type(exc).__name__,'message':str(exc)}
        for ep,_desk in envs.values():
            try: ep.copy_artifacts(out/'failure-artifacts')
            except Exception: pass
            try: ep.close()
            except Exception: pass
        envs.clear()
    finally:
        report['wall_seconds']=round(time.monotonic()-start,2); report['timeline']=timeline; log.write(out/'events.jsonl'); report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
        source=base.git_source_state(); (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n'); (out/'provenance.json').write_text(json.dumps({'run_id':identity.run_id,'source':source,'task_id':task.TASK_ID,'task_version':'0.1.1-prompt-calibration','model_used':True,'artifact_sha256':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='provenance.json' and 'overlays' not in p.parts}},indent=2)+'\n')
        for actor,obj in actors.items():
            (out/f'{actor}-trace.json').write_text(json.dumps(obj.trace,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'run_id':a.run_id,'status':report['status'],'condition':a.condition,'joint_success':report.get('joint_success'),'actor_goal_success':report.get('actor_goal_success'),'scheduled_exposure':report.get('scheduled_exposure'),'actual_exposure':report.get('actual_exposure'),'interference':report.get('observed_interference'),'recovery':report.get('autonomous_recovery'),'reset':report.get('reset_success'),'error':report.get('error'),'artifacts':str(out)})); return 0 if report['status']=='completed' and report.get('reset_success') else 1
if __name__=='__main__': raise SystemExit(main())
