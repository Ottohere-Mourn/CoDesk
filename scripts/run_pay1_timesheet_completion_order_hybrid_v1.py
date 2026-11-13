#!/usr/bin/env python3
"""PAY-1 sequential completion-order Hybrid arm: test a late approved-hours correction."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, sys, time, uuid
from pathlib import Path
sys.path.insert(0, "/home/mjh/Projects/CoDesk-candidate-repair-20261104")
from scripts import run_pay1_timesheet_hybrid_v1 as h

ART=h.ART

def _json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def run_shared_completion_order(out,runid,condition,baseline):
    log=h.base.EventLog();store=h.ProtocolStore(out/'collaboration',runid)
    tokens={a:secrets.token_urlsafe(32) for a in ('A','B')}
    server=h.make_server(store,tokens)
    threading=__import__('threading'); threading.Thread(target=server.serve_forever,daemon=True).start()
    token_envs={}
    for actor in ('A','B'):
        envname='PAY1_COLLAB_'+actor+'_'+uuid.uuid4().hex[:8].upper()
        os.environ[envname]=tokens[actor];token_envs[actor]=envname
    ep=d=None;statuses={};setups={};states={};model_attempted={'A':False,'B':False}
    reset_ok=False;protocol_valid=False;errors=[]
    lock=out/'locks'/'guest-actions.lock'
    report={'run_id':runid,'task_id':h.fx.TASK_ID,'task_version':h.fx.TASK_VERSION,
        'fixture_sha256':h.fx.SOURCE_FIXTURE_SHA256,'condition':condition,
        'schedule':'A completes the payroll-clerk episode and handoff before B starts supervisor correction',
        'baseline_run_id':baseline['run_id'],'model':h.MODEL,
        'endpoint':os.environ.get('CODESK_SOL_ENDPOINT',h.ENDPOINT_DEFAULT),
        'runtime_profile':'gui-cli-mcp-v2','actor_implementation':'CodexHarness/Codex CLI 0.155.0',
        'tool_permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],
        'budget_per_actor':h.BUDGET,'output_token_budget_per_actor':h.TOKEN_BUDGET,
        'prompt_hashes':h.PROMPT_SHA,'prompts':h.PROMPTS,
        'protocol_gate':{'enabled':False,'reason':'registered actor-completion schedule; no pending action is intercepted'},
        'lock_file':str(lock) if condition=='ma_sd_lock' else None}
    try:
        ep,d=h.base.make_desktop('shared',log,out/'shared',require_a11y_tree=False);d.guest_key='shared'
        cli_a='/tmp/pay1_cli_'+runid+'_A';cli_b='/tmp/pay1_cli_'+runid+'_B'
        report['cli_roots']={'A':cli_a,'B':cli_b}
        ep.cli_action('pay1_setup','mkdir -p '+h.shlex.quote(cli_a)+' '+h.shlex.quote(cli_b))
        setups['shared']=h._setup(ep,d,out,runid,'A',condition,cli_a)
        evidence=json.dumps({'document_id':h.fx.CORRECTION_ID,'employee_id':h.fx.EMPLOYEE_ID,
            'week_id':h.fx.WEEK_ID,'corrected_hours_tenths':h.fx.CORRECTED_HOURS_TENTHS,
            'authorized_by':h.fx.SUPERVISOR_ID,'signed':True,
            'reason_code':h.fx.CORRECTION_SOURCE['reason_code']},indent=2)
        h._write_guest(ep,cli_b+'/correction.json',evidence,'pay1_actor_evidence_B')
        report['setups']=setups
        model_attempted['A']=True
        statuses['A']=h._run_actor('A',ep,d,out,runid,condition,server,token_envs['A'],cli_a,None)
        state_after_a=h._state(d);states['after_A_before_B']=state_after_a
        eval_after_a=h.fx.evaluate_actor(state_after_a,'A')
        messages_before_b,collab_before_b=h._messages(out)
        report['A_business_result_before_B']=eval_after_a
        report['collaboration_before_B']={'events':messages_before_b,'contract':collab_before_b}
        handoff_before_b=bool(collab_before_b.get('A_to_B_handoff'))
        if statuses['A'].get('status') not in {'done','max_steps','fail'}:
            raise RuntimeError('A did not terminate normally before the registered B schedule point')
        if not handoff_before_b:
            raise RuntimeError('A did not send the required handoff before B started')
        nav=h._mcp('key',{'keys':'ctrl+tab'},out,d,'coordinator_select_B',runid+'-select-B',condition,
                   lock=lock if condition=='ma_sd_lock' else None)
        role=h._green_center(nav['image']);report['B_tab_green_button']=role
        if not (300<=role['x']<=460):raise RuntimeError('B supervisor tab not active after coordinator handoff: '+str(role))
        model_attempted['B']=True
        statuses['B']=h._run_actor('B',ep,d,out,runid,condition,server,token_envs['B'],cli_b,None)
        state_after_b=h._state(d);states['after_B']=state_after_b
        eval_after_b=h.fx.evaluate_actor(state_after_b,'B')
        report['B_business_result_after_B']=eval_after_b
        messages,collab=h._messages(out)
        ev=h.fx.evaluate_shared(state_after_b)
        reset_response=h._post(d,'/api/reset',{});reset_state=h._state(d)
        reset_ok=bool(reset_response.get('ok') and reset_state['timecard']['approved_hours_tenths']==80 and not reset_state['payment_lines'] and not reset_state['audit_log'])
        statuses_ok=all(statuses.get(a,{}).get('status') in {'done','max_steps','fail'} for a in ('A','B'))
        protocol_valid=bool(handoff_before_b and collab.get('success') and statuses_ok)
        active=[r for r in state_after_b.get('payment_lines',[]) if r.get('actor')=='A' and r.get('status')=='submitted']
        mismatch=(len(active)==1 and active[0].get('hours_tenths')==80 and active[0].get('amount_cents')==h.fx.RATE_CENTS_PER_HOUR*80//10 and state_after_b.get('timecard',{}).get('approved_hours_tenths')==h.fx.CORRECTED_HOURS_TENTHS)
        mechanism_exposure_valid=bool(eval_after_a.get('success') and eval_after_b.get('success') and mismatch and not ev['A']['one_exact_current_payment'] and ev['B']['success'])
        report.update({'initial_workspace_bindings':{'A':'shared','B':'shared'},
            'actor_container_id':ep.snapshot().get('guest_container_id'),
            'actors':statuses,'actor_actions':{a:{'calls':len(h._actor_actions(out,a)),
                'log':str((out/'actor_runs'/a/a/'actions.jsonl').relative_to(out))} for a in ('A','B')},
            'final_states':{'shared':state_after_b},'collaboration_events':messages,
            'collaboration_contract':collab,'evaluation':ev,'protocol_valid':protocol_valid,
            'valid_model_run':bool(statuses_ok and protocol_valid and reset_ok),
            'mechanism_exposure_valid':mechanism_exposure_valid,
            'mechanism_exposure':{'A_passed_before_B':bool(eval_after_a.get('success')),
                'B_passed_after_correction':bool(eval_after_b.get('success')),
                'final_active_payment_hours':active[0].get('hours_tenths') if len(active)==1 else None,
                'final_approved_hours':state_after_b.get('timecard',{}).get('approved_hours_tenths'),
                'late_correction_made_A_stale':mismatch},
            'reset_check':{'reset_api_ok':bool(reset_response.get('ok')),
                'initial_hours_restored':reset_state['timecard']['approved_hours_tenths']==80,
                'payment_lines':len(reset_state['payment_lines']),'audit_log':len(reset_state['audit_log']),
                'success':reset_ok},'api_called':any(model_attempted.values()),
            'model_called':any(model_attempted.values())})
        if report['valid_model_run']:
            report['status']='completed';report['model_task_outcome']='PASS' if ev['success'] and collab['success'] else 'FAIL'
        else:
            report['status']='invalid_model_or_protocol';report['model_task_outcome']='environment_or_model_invalid'
    except Exception as exc:
        report.update({'status':'invalid_infrastructure_or_protocol','model_task_outcome':'environment_or_model_invalid',
            'valid_model_run':False,'error':{'type':type(exc).__name__,'message':str(exc)},
            'model_called':any(model_attempted.values()),'api_called':any(model_attempted.values()),
            'cleanup_errors':errors})
    finally:
        if ep is not None:
            try:ep.copy_artifacts(out/'guest-artifacts'/'shared')
            except Exception as exc:errors.append('artifact capture: '+str(exc))
            try:ep.close()
            except Exception as exc:errors.append('guest close: '+str(exc))
        try:server.shutdown();server.server_close()
        except Exception as exc:errors.append('server close: '+str(exc))
        if errors:report['cleanup_errors']=errors
    return report,log

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--condition',choices=('ma_sd','ma_sd_lock'),required=True)
    parser.add_argument('--baseline',required=True)
    args=parser.parse_args();baseline=json.loads(Path(args.baseline).read_text(encoding='utf-8'))
    if not baseline.get('valid_model_run') or baseline.get('model_task_outcome')!='PASS' or baseline.get('condition')!='ma_id' or baseline.get('task_version')!=h.fx.TASK_VERSION or baseline.get('fixture_sha256')!=h.fx.SOURCE_FIXTURE_SHA256 or baseline.get('prompt_hashes')!=h.PROMPT_SHA:
        raise SystemExit('MA-ID baseline mismatch or not a valid exact-task PASS; no Guest started.')
    h.preflight(require_key=True);ART.mkdir(parents=True,exist_ok=True)
    runid='pay1-sol-completion-order-'+args.condition+'-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    out=ART/runid;out.mkdir(parents=True,exist_ok=False)
    for sub in ('actor_runs','shared','collaboration','setup','locks','coordinator_mcp'):(out/sub).mkdir(parents=True,exist_ok=True)
    ledger,identity=h._env(out,runid);started=time.monotonic();_json(out/'prompts.json',h.PROMPTS)
    _json(out/'provenance-initial.json',{'source_commit':h.base.git_source_state(),'task_id':h.fx.TASK_ID,
        'task_version':h.fx.TASK_VERSION,'fixture_sha256':h.fx.SOURCE_FIXTURE_SHA256,'condition':args.condition,
        'schedule':'serial_actor_completion','baseline_run_id':baseline['run_id'],'model':h.MODEL,
        'permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],
        'budget_per_actor':h.BUDGET,'prompt_hashes':h.PROMPT_SHA,
        'app_sha256':hashlib.sha256(h.app.server_text(h.fx.SOURCE_FIXTURE_SHA256).encode()).hexdigest()})
    report,log=run_shared_completion_order(out,runid,args.condition,baseline)
    try:
        for proc in h.RELAY_PROCS:
            try:proc.terminate();proc.wait(timeout=10)
            except Exception:
                try:proc.kill()
                except Exception:pass
        for key in list(os.environ):
            if key.startswith('PAY1_RELAY_') or key.startswith('PAY1_COLLAB_'):os.environ.pop(key,None)
        try:log.write(out/'events.jsonl')
        except Exception as exc:report['event_log_error']=str(exc)
        report['wall_seconds']=round(time.monotonic()-started,2)
        report['resource_lifecycle']=h.base.verify_ledger(ledger) if ledger.exists() else None
        if not report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record') or not report.get('resource_lifecycle',{}).get('labels_consistent'):
            report['valid_model_run']=False;report['model_task_outcome']='environment_or_model_invalid';report['status']='invalid_resource_lifecycle'
        report['provenance']={'resource_run_id':identity.run_id,'source_commit':h.base.git_source_state(),
            'fixture_sha256':h.fx.SOURCE_FIXTURE_SHA256,'guest_image':str(h.IMAGE),
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'base_runner_sha256':hashlib.sha256(Path(h.__file__).read_bytes()).hexdigest(),
            'app_sha256':hashlib.sha256(h.app.server_text(h.fx.SOURCE_FIXTURE_SHA256).encode()).hexdigest()}
        _json(out/'report.json',report);_json(out/'provenance.json',report['provenance'])
    finally:
        pass
    print(json.dumps({'out':str(out),'status':report.get('status'),
        'model_task_outcome':report.get('model_task_outcome'),'wall_seconds':report.get('wall_seconds'),
        'valid_model_run':report.get('valid_model_run'),'mechanism_exposure_valid':report.get('mechanism_exposure_valid'),
        'condition':args.condition},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
