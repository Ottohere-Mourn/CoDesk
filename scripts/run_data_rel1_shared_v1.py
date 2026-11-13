#!/usr/bin/env python3
"""Run exactly one DATA-REL1 Shared or Shared+Lock arm against a valid MA-ID PASS."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, shlex, sys, threading, time, uuid
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
ART=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/data-rel1-model-v1')
sys.path[:0]=[str(ROOT)]
from scripts import run_data_rel1_ma_id_v1 as common
from scripts import run_pay1_timesheet_hybrid_v1 as pay1
fx=common.fx;app=common.app;PROMPTS=common.PROMPTS;PROMPT_SHA=common.PROMPT_SHA
from oscombo.collab.data_to_deck.protocol import ProtocolStore,make_server


def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def activate_tab(d,route):
    tabs=json.loads(common.guest(d,['curl','--noproxy','*','-fsS','http://127.0.0.1:9222/json/list'],8))
    tab=next((x for x in tabs if x.get('type')=='page' and x.get('url')==route and x.get('title')=='Study Export Workbench'),None)
    if not tab:raise RuntimeError('Chrome tab unavailable for route '+route)
    raw=common.guest(d,['curl','--noproxy','*','-fsS',f"http://127.0.0.1:9222/json/activate/{tab['id']}"],8)
    return {'tab':tab,'activate_response':raw}
def screenshot(ep,out,name):
    obs=ep.refresh_observation(source='data_rel1_'+name);shot=obs.get('screenshot') if isinstance(obs,dict) else None
    if not isinstance(shot,bytes) or len(shot)<1000:raise RuntimeError('no Guest screenshot for '+name)
    p=out/'setup'/f'{name}.png';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(shot)
    return str(p.relative_to(out))
def collab_read(out):
    p=out/'collaboration'/'events.jsonl';rows=[]
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:pass
    m=[x for x in rows if x.get('type')=='message']
    ab=[x for x in m if x.get('actor')=='A' and x.get('recipient')=='B' and 'STUDY-SYN-88' in str(x.get('body',''))]
    ba=[x for x in m if x.get('actor')=='B' and x.get('recipient')=='A' and 'PA-SYN-017' in str(x.get('body',''))]
    return rows,{'A_to_B_handoff':bool(ab),'B_to_A_amendment_notice':bool(ba),'success':bool(ab and ba)}
def cli_args():
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=('ma_sd','ma_sd_lock'),required=True);p.add_argument('--baseline',required=True);return p.parse_args()
def main():
    args=cli_args();baseline_path=Path(args.baseline);baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
    if not (baseline.get('valid_model_run') is True and baseline.get('model_task_outcome')=='PASS' and baseline.get('condition')=='ma_id'
       and baseline.get('task_version')==fx.TASK_VERSION and baseline.get('fixture_sha256')==hashlib.sha256((ROOT/'scripts/data_rel1_fixture_v1.py').read_bytes()).hexdigest()
       and baseline.get('prompt_hashes')==PROMPT_SHA):
        raise SystemExit('MA-ID baseline mismatch or not a valid exact-task PASS; no Guest started.')
    pay1.preflight(require_key=True);ART.mkdir(parents=True,exist_ok=True)
    runid=f"data-rel1-sol-{args.condition}-"+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    out=ART/runid;out.mkdir(parents=True,exist_ok=False)
    for s in ('actor_runs','collaboration','setup','guest-artifacts','locks'):(out/s).mkdir(parents=True,exist_ok=True)
    ledger,identity=pay1._env(out,runid);started=time.monotonic();log=pay1.base.EventLog()
    store=ProtocolStore(out/'collaboration',runid);tokens={a:secrets.token_urlsafe(32) for a in ('A','B')};server=make_server(store,tokens);threading.Thread(target=server.serve_forever,daemon=True).start();token_env={}
    for a in ('A','B'):
        name='DATAREL_COLLAB_'+a+'_'+uuid.uuid4().hex[:8].upper();os.environ[name]=tokens[a];token_env[a]=name
    lock_enabled=args.condition=='ma_sd_lock'
    report={'run_id':runid,'task_id':fx.TASK_ID,'task_version':fx.TASK_VERSION,'fixture_sha256':hashlib.sha256((ROOT/'scripts/data_rel1_fixture_v1.py').read_bytes()).hexdigest(),
       'app_sha256':hashlib.sha256((ROOT/'scripts/data_rel1_app_v1.py').read_bytes()).hexdigest(),'condition':args.condition,
       'baseline_run_id':baseline.get('run_id'),'schedule':'serial_actor_completion','model':'gpt-6-sol',
       'endpoint':os.environ.get('CODESK_SOL_ENDPOINT','https://docode.cc/v1'),'runtime_profile':'gui-cli-mcp-v2',
       'actor_implementation':'reused CodexHarness / Codex CLI 0.155.0','tool_permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],
       'budget_per_actor':18,'output_token_budget_per_actor':18000,'prompt_hashes':PROMPT_SHA,'prompts':PROMPTS,
       'action_lock':{'enabled':lock_enabled,'path':str(out/'locks'/'guest-actions.lock') if lock_enabled else None,'scope':'existing PerActionLock via CodexHarness; one shared Guest'},
       'initial_workspace_bindings':{'A':'shared','B':'shared'},'model_called':False,'api_called':False,
       'external_release_enabled':False,'external_network_traffic_audited':False,'reset_check':{'shared_guest_started_from_exact_fixture':False,'guest_destroyed_after_capture':False}}
    ep=d=None;statuses={};model_attempted={'A':False,'B':False};states={};setups={};errors=[]
    try:
        ep,d=pay1.base.make_desktop('data_rel1_shared',log,out/'guest-artifacts'/'shared',require_a11y_tree=False);d.guest_key='data_rel1_shared'
        report['guest_container_id']=ep.snapshot().get('guest_container_id')
        setups['A']=common.setup_guest('A',ep,d,out,runid,'/tmp/data_rel1_cli_'+runid+'_A')
        b_root='/tmp/data_rel1_cli_'+runid+'_B';ep.cli_action('data_rel1_cli_root_B','mkdir -p '+shlex.quote(b_root))
        common.install_text(ep,b_root+'/PA-SYN-017.json',json.dumps(fx.RESTRICTION_EVIDENCE,ensure_ascii=False,indent=2)+'\n','data_rel1_amendment_evidence_B')
        # The app already has both role tabs; pin each actor to its own route without changing task state.
        setups['A']['active_route']=activate_tab(d,app.ROUTES['exporter']);setups['A']['ready_screenshot']=screenshot(ep,out,'shared-A-ready')
        initial=common.api_get(d);initial.pop('events',None);initial_ok=initial==fx.initial_workspace();report['initial_state_exact']=initial_ok;report['reset_check']['shared_guest_started_from_exact_fixture']=initial_ok
        if not initial_ok:raise RuntimeError('Shared workspace is not the exact initial fixture')
        model_attempted['A']=True
        statuses['A']=pay1._run_actor('A',ep,d,out,runid,args.condition,server,token_env['A'],'/tmp/data_rel1_cli_'+runid+'_A')
        state_a=common.api_get(d);states['after_A']=state_a;eval_a=fx.evaluate_actor(state_a,'A')
        setups['B']={'cli_evidence_path':b_root+'/PA-SYN-017.json','active_route':activate_tab(d,app.ROUTES['coordinator'])}
        setups['B']['ready_screenshot']=screenshot(ep,out,'shared-B-ready')
        model_attempted['B']=True
        statuses['B']=pay1._run_actor('B',ep,d,out,runid,args.condition,server,token_env['B'],b_root)
        state_b=common.api_get(d);states['after_B']=state_b;eval_b=fx.evaluate_actor(state_b,'B');evaluation=fx.evaluate_episode({'A':state_b,'B':state_b})
        messages,collab=collab_read(out)
        exposure=bool(eval_a.get('success') and eval_b.get('success') and not evaluation['actors']['A']['success'] and evaluation['actors']['B']['success']
          and not evaluation['actors']['A']['checks'].get('rows_match_current_eligible_subjects',True)
          and not evaluation['actors']['A']['checks'].get('package_versions_match_current_workspace',True))
        statuses_ok=all(statuses.get(a,{}).get('status') in {'done','max_steps','fail'} for a in ('A','B'))
        report.update({'setups':setups,'actors':statuses,'A_business_result_before_B':eval_a,'B_business_result_after_B':eval_b,
          'final_states':states,'evaluation':evaluation,'collaboration_events':messages,'collaboration_contract':collab,
          'mechanism_exposure_valid':exposure,'actor_actions':{a:{'calls':len(common.actor_actions(out,a)),'log':str((out/'actor_runs'/a/a/'actions.jsonl').relative_to(out))} for a in ('A','B')},
          'valid_model_run':bool(statuses_ok and initial_ok and set(states)=={'after_A','after_B'}),
          'model_called':any(model_attempted.values()),'api_called':any(model_attempted.values()),
          'model_task_outcome':'PASS' if evaluation['success'] and collab['success'] else 'FAIL' if statuses_ok else 'environment_or_model_invalid',
          'status':'completed' if statuses_ok and initial_ok else 'invalid_model_or_protocol',
          'reset_check':{'shared_guest_started_from_exact_fixture':initial_ok,'guest_destroyed_after_capture':False}})
    except Exception as exc:
        report.update({'status':'invalid_infrastructure_or_protocol','valid_model_run':False,'model_task_outcome':'environment_or_model_invalid',
          'model_called':any(model_attempted.values()),'api_called':any(model_attempted.values()),'error':{'type':type(exc).__name__,'message':str(exc)}})
    finally:
        for proc in pay1.RELAY_PROCS:
            try:proc.terminate();proc.wait(timeout=10)
            except Exception:
                try:proc.kill()
                except Exception:pass
        for key in list(os.environ):
            if key.startswith('PAY1_RELAY_') or key.startswith('DATAREL_COLLAB_'):os.environ.pop(key,None)
        if ep is not None:
            try:ep.copy_artifacts(out/'guest-artifacts'/'shared')
            except Exception as exc:errors.append('artifact capture: '+str(exc))
            try:ep.close()
            except Exception as exc:errors.append('guest close: '+str(exc))
        try:server.shutdown();server.server_close()
        except Exception as exc:errors.append('collaboration server: '+str(exc))
        try:log.write(out/'events.jsonl')
        except Exception as exc:errors.append('event log: '+str(exc))
        try:report['resource_lifecycle']=pay1.base.verify_ledger(ledger) if ledger.exists() else None
        except Exception as exc:errors.append('resource ledger: '+str(exc))
        report['wall_seconds']=round(time.monotonic()-started,2)
        report.setdefault('reset_check',{})['guest_destroyed_after_capture']=bool(report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record'))
        if errors:report['cleanup_errors']=errors
        if not report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record'):
            report['valid_model_run']=False;report['status']='invalid_resource_lifecycle';report['model_task_outcome']='environment_or_model_invalid'
        report['provenance']={'resource_run_id':identity.run_id,'source_commit':pay1.base.git_source_state(),'guest_image':str(pay1.IMAGE),
          'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'fixture_sha256':report['fixture_sha256'],'app_sha256':report['app_sha256']}
        write_json(out/'report.json',report)
    print(json.dumps({'out':str(out),'condition':args.condition,'status':report.get('status'),'model_task_outcome':report.get('model_task_outcome'),
      'valid_model_run':report.get('valid_model_run'),'mechanism_exposure_valid':report.get('mechanism_exposure_valid'),
      'wall_seconds':report.get('wall_seconds'),'evaluation_success':bool(report.get('evaluation',{}).get('success'))},ensure_ascii=False,indent=2))
    if not report.get('valid_model_run'):raise SystemExit(1)
if __name__=='__main__':main()
