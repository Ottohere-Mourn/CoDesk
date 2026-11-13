#!/usr/bin/env python3
"""DATA-REL1 single MA-ID GPT-6-Sol screening; no other arm starts here."""
from __future__ import annotations
import base64, hashlib, json, os, secrets, shlex, sys, threading, time, uuid
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
ART=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/data-rel1-model-v1')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
from scripts import data_rel1_fixture_v1 as fx
from scripts import data_rel1_app_v1 as app
from scripts import run_pay1_timesheet_hybrid_v1 as pay1
from oscombo.collab.data_to_deck.protocol import ProtocolStore,make_server
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor
from oscombo.harness.hybrid_v2 import MCP_PYTHON,MCP_SITE
from swcub.resource_safety import ensure_resource_identity

MODEL='gpt-6-sol';ENDPOINT_DEFAULT='https://docode.cc/v1';BUDGET=18;TOKEN_BUDGET=18000
PROMPTS={
'A':"""You are the data analyst preparing the STUDY-SYN-88 export handoff. Use Guest CLI MCP to read export_policy.txt. Use the GUI exporter page to create exactly one READY package in local staging containing every and only currently allowed synthetic subject. Verify the subject list, policy version and manifest hash shown in the GUI before you finish. External release is disabled: do not publish, upload, or send data outside this Guest. Send B a collaboration message with the package ID, subject list and policy version, then stop; do not modify the protocol scope or use the coordinator controls. Preserve all other records.""",
'B':"""You are the protocol coordinator for STUDY-SYN-88. Read A's collaboration handoff. Use Guest CLI MCP to read PA-SYN-017.json and verify its source ID, approver, subject, signature and effective scope. In the GUI coordinator page, apply this amendment once, then verify policy version 2 and SUB-17 excluded for all unreleased packages. Do not use exporter controls or release any package; send A a collaboration message with the amendment ID and new policy version, then stop. Preserve all other records."""
}
PROMPT_SHA={a:hashlib.sha256(v.encode()).hexdigest() for a,v in PROMPTS.items()}
# Reuse CodexHarness/runtime actor loop and protocol plumbing from the existing PAY-1 runner.
pay1.PROMPTS=PROMPTS;pay1.PROMPT_SHA=PROMPT_SHA;pay1.fx=fx;pay1.RELAY_PROCS=[]

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def guest(d,argv,timeout=30):return pay1.base.guest_command(d,argv,timeout=timeout)
def api_get(d):return json.loads(guest(d,['curl','--noproxy','*','-fsS','--max-time','4',f'http://127.0.0.1:{app.PORT}/api/state'],8))
def install_text(ep,path,content,label):
    b64=base64.b64encode(content.encode('utf-8')).decode('ascii')
    code='from pathlib import Path;import base64;p=Path('+repr(path)+');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode('+repr(b64)+'))'
    ep.cli_action(label,'python3 -c '+shlex.quote(code))
def setup_guest(actor,ep,d,out,runid,cli_root):
    guest_dir='/tmp/codesk-data-rel1'
    payload={name:base64.b64encode((ROOT/'scripts'/name).read_bytes()).decode('ascii') for name in ('data_rel1_fixture_v1.py','data_rel1_app_v1.py')}
    code=('from pathlib import Path;import base64;d=Path('+repr(guest_dir)+');d.mkdir(parents=True,exist_ok=True);files='+repr(payload)+';'
          '[(d/k).write_bytes(base64.b64decode(v)) for k,v in files.items()]')
    ep.cli_action('data_rel1_app_install','python3 -c '+shlex.quote(code))
    ep.cli_action('data_rel1_cli_root','mkdir -p '+shlex.quote(cli_root))
    if actor=='A':
        install_text(ep,cli_root+'/export_policy.txt',"""SYNTHETIC-EXPORT-CONTROL-01
Dataset: STUDY-SYN-88, version 1. Initial policy version: 1.
Every unreleased staging package must match the current policy version and allowed synthetic subjects before release.
Currently allowed: SUB-17, SUB-22.
External release is disabled. Never publish or upload this synthetic data.
""",'data_rel1_policy_evidence')
    else:
        install_text(ep,cli_root+'/PA-SYN-017.json',json.dumps(fx.RESTRICTION_EVIDENCE,ensure_ascii=False,indent=2)+'\n','data_rel1_amendment_evidence')
    start='nohup env PYTHONPATH='+shlex.quote(guest_dir)+' /usr/bin/python3 '+shlex.quote(guest_dir+'/data_rel1_app_v1.py')+' --state /tmp/codesk-data-rel1/state.json --port '+str(app.PORT)+' >/tmp/codesk-data-rel1-server.log 2>&1 </dev/null & echo $! >/tmp/codesk-data-rel1-server.pid'
    ep.cli_action('data_rel1_app_start','bash -lc '+shlex.quote(start))
    health='';deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            health=guest(d,['curl','--noproxy','*','-fsS','--max-time','2',f'http://127.0.0.1:{app.PORT}/health'],5)
            if '"ok"' in health:break
        except Exception:time.sleep(.3)
    if '"ok"' not in health:raise RuntimeError('DATA-REL1 Guest app did not become healthy: '+health[:300])
    browser=guest(d,['bash','-lc','command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE'],8).strip().splitlines()[-1]
    if browser=='NONE':raise RuntimeError('Chromium/Chrome not available in pinned Guest')
    launch=('nohup '+shlex.quote(browser)+' --no-sandbox --start-maximized --no-first-run --no-default-browser-check '
       '--disable-extensions --disable-background-networking --disable-dev-shm-usage --no-proxy-server --remote-debugging-port=9222 '
       '--user-data-dir=/tmp/codesk-data-rel1/chrome-'+runid+'-'+actor+' --new-window '
       +shlex.quote(app.ROUTES['exporter'])+' '+shlex.quote(app.ROUTES['coordinator'])+
       ' >/tmp/codesk-data-rel1-chrome.log 2>&1 </dev/null & echo $! >/tmp/codesk-data-rel1-chrome.pid')
    ep.cli_action('data_rel1_browser_start','bash -lc '+shlex.quote(launch))
    tabs=[];deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        try:
            tabs=json.loads(guest(d,['curl','--noproxy','*','-fsS','--max-time','2','http://127.0.0.1:9222/json/list'],5))
            expected=app.ROUTES['exporter'] if actor=='A' else app.ROUTES['coordinator']
            if any(t.get('type')=='page' and t.get('url')==expected and t.get('title')=='Study Export Workbench' for t in tabs):break
        except Exception:time.sleep(.5);continue
        time.sleep(.5)
    if actor=='B':
        from swcub.environment import ActorContext
        gui=ActorContext('setup-B',ep,'gui');gui.press_key('ctrl+tab')
    time.sleep(2)
    obs=ep.refresh_observation(source='data_rel1_'+actor+'_page_ready');shot=obs.get('screenshot') if isinstance(obs,dict) else None
    if not isinstance(shot,bytes) or len(shot)<1000:raise RuntimeError('no Guest screenshot for '+actor)
    p=out/'setup'/f'{actor}-ready.png';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(shot)
    html=guest(d,['curl','--noproxy','*','-fsS',app.ROUTES['exporter' if actor=='A' else 'coordinator']],8)
    if 'Every unreleased package must match the current protocol scope' not in html:raise RuntimeError('visible policy not loaded for '+actor)
    return {'health':json.loads(health),'browser_binary':browser,'tabs':tabs,'screenshot':str(p.relative_to(out)),
       'workspace_before_actor':api_get(d),'cli_evidence_path':cli_root}

def collab_events(out):
    p=out/'collaboration'/'events.jsonl';rows=[]
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:pass
    messages=[x for x in rows if x.get('type')=='message']
    ab=[x for x in messages if x.get('actor')=='A' and x.get('recipient')=='B' and 'STUDY-SYN-88' in str(x.get('body',''))]
    ba=[x for x in messages if x.get('actor')=='B' and x.get('recipient')=='A' and 'PA-SYN-017' in str(x.get('body',''))]
    return rows,{'A_to_B_handoff':bool(ab),'B_to_A_amendment_notice':bool(ba),'success':bool(ab and ba)}
def actor_actions(out,actor):
    p=out/'actor_runs'/actor/actor/'actions.jsonl';rows=[]
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:pass
    return rows

def main():
    pay1.preflight(require_key=True)
    ART.mkdir(parents=True,exist_ok=True)
    runid='data-rel1-sol-ma-id-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    out=ART/runid;out.mkdir(parents=True,exist_ok=False)
    for s in ('actor_runs','collaboration','setup','guest-artifacts','locks'):(out/s).mkdir(parents=True,exist_ok=True)
    ledger,identity=pay1._env(out,runid);started=time.monotonic()
    log=pay1.base.EventLog();store=ProtocolStore(out/'collaboration',runid)
    tokens={a:secrets.token_urlsafe(32) for a in ('A','B')};server=make_server(store,tokens);threading.Thread(target=server.serve_forever,daemon=True).start()
    token_env={}
    for a in ('A','B'):
        n='DATAREL_COLLAB_'+a+'_'+uuid.uuid4().hex[:8].upper();os.environ[n]=tokens[a];token_env[a]=n
    report={'run_id':runid,'task_id':fx.TASK_ID,'task_version':fx.TASK_VERSION,'fixture_sha256':hashlib.sha256((ROOT/'scripts/data_rel1_fixture_v1.py').read_bytes()).hexdigest(),
       'app_sha256':hashlib.sha256((ROOT/'scripts/data_rel1_app_v1.py').read_bytes()).hexdigest(),'condition':'ma_id',
       'schedule':'serial_actor_completion','model':MODEL,'endpoint':os.environ.get('CODESK_SOL_ENDPOINT',ENDPOINT_DEFAULT),
       'runtime_profile':'gui-cli-mcp-v2','actor_implementation':'reused CodexHarness / Codex CLI 0.155.0',
       'tool_permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],
       'budget_per_actor':BUDGET,'output_token_budget_per_actor':TOKEN_BUDGET,
       'prompt_hashes':PROMPT_SHA,'prompts':PROMPTS,'initial_workspace_bindings':{},'actors':{},'setups':{},'final_states':{},
       'model_called':False,'api_called':False,'external_release_enabled':False,'external_network_traffic_audited':False}
    states={};eps=[];model_attempted=False
    write_json(out/'prompts.json',PROMPTS)
    write_json(out/'provenance-initial.json',{'source_commit':pay1.base.git_source_state(),'model':MODEL,'endpoint':report['endpoint'],
       'condition':'ma_id','schedule':'serial_actor_completion','tool_permissions':report['tool_permissions'],'budget_per_actor':BUDGET,
       'prompt_hashes':PROMPT_SHA,'fixture_sha256':report['fixture_sha256'],'app_sha256':report['app_sha256']})
    try:
        for actor in ('A','B'):
            binding='data_rel1_actor_'+actor.lower();cli_root='/tmp/data_rel1_cli_'+runid+'_'+actor;ep=d=None
            try:
                ep,d=pay1.base.make_desktop(binding,log,out/'guest-artifacts'/binding,require_a11y_tree=False);eps.append(ep)
                d.guest_key=binding;report['initial_workspace_bindings'][actor]=binding
                report['setups'][actor]=setup_guest(actor,ep,d,out,runid,cli_root)
                model_attempted=True
                status=pay1._run_actor(actor,ep,d,out,runid,'ma_id',server,token_env[actor],cli_root)
                report['actors'][actor]=status
                states[actor]=api_get(d)
                report['guest_container_ids']=report.get('guest_container_ids',{})|{actor:ep.snapshot().get('guest_container_id')}
                report['actor_states_captured'][actor]=True
            except Exception as exc:
                report['actors'].setdefault(actor,{'status':'error','error':f'{type(exc).__name__}: {exc}'})
                report['setups'].setdefault(actor,{'status':'error','error':f'{type(exc).__name__}: {exc}'})
                if ep is not None:
                    try:ep.copy_artifacts(out/'guest-artifacts'/('failure-'+binding))
                    except Exception:pass
            finally:
                if ep is not None:
                    try:ep.copy_artifacts(out/'guest-artifacts'/binding)
                    except Exception:pass
                    try:ep.close()
                    except Exception:pass
        messages,collab=collab_events(out)
        evaluation=fx.evaluate_episode(states) if set(states)=={'A','B'} else None
        task_pass=bool(evaluation and evaluation['success'] and collab['success'])
        terminal_status=all(report['actors'].get(a,{}).get('status') in {'done','max_steps','fail'} for a in ('A','B'))
        report.update({'final_states':states,'evaluation':evaluation,'collaboration_events':messages,'collaboration_contract':collab,
          'actor_actions':{a:{'calls':len(actor_actions(out,a)),'log':str((out/'actor_runs'/a/a/'actions.jsonl').relative_to(out))} for a in ('A','B')},
          'valid_model_run':bool(terminal_status and set(states)=={'A','B'}),'model_task_outcome':'PASS' if task_pass else 'FAIL' if terminal_status and set(states)=={'A','B'} else 'environment_or_model_invalid',
          'status':'completed' if terminal_status and set(states)=={'A','B'} else 'invalid_model_or_protocol',
          'model_called':model_attempted,'api_called':model_attempted,
          'reset_check':{'two_private_guest_workspaces_used':len(set(report['initial_workspace_bindings'].values()))==2,
             'resource_cleanup_checked_after_capture':True}})
    except Exception as exc:
        report.update({'status':'invalid_infrastructure_or_protocol','model_task_outcome':'environment_or_model_invalid','valid_model_run':False,
          'error':{'type':type(exc).__name__,'message':str(exc)},'model_called':model_attempted,'api_called':model_attempted})
    finally:
        for proc in pay1.RELAY_PROCS:
            try:proc.terminate();proc.wait(timeout=10)
            except Exception:
                try:proc.kill()
                except Exception:pass
        for key in list(os.environ):
            if key.startswith('PAY1_RELAY_') or key.startswith('DATAREL_COLLAB_'):os.environ.pop(key,None)
        try:server.shutdown();server.server_close()
        except Exception as exc:report.setdefault('cleanup_errors',[]).append('collaboration server: '+str(exc))
        try:log.write(out/'events.jsonl')
        except Exception as exc:report.setdefault('cleanup_errors',[]).append('event log: '+str(exc))
        try:report['resource_lifecycle']=pay1.base.verify_ledger(ledger) if ledger.exists() else None
        except Exception as exc:report.setdefault('cleanup_errors',[]).append('resource ledger: '+str(exc))
        if not report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record'):
            report['valid_model_run']=False;report['status']='invalid_resource_lifecycle';report['model_task_outcome']='environment_or_model_invalid'
        report['wall_seconds']=round(time.monotonic()-started,2)
        report['provenance']={'resource_run_id':identity.run_id,'source_commit':pay1.base.git_source_state(),
          'guest_image':str(pay1.IMAGE),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'fixture_sha256':report['fixture_sha256'],'app_sha256':report['app_sha256']}
        write_json(out/'report.json',report)
    print(json.dumps({'out':str(out),'status':report.get('status'),'model_task_outcome':report.get('model_task_outcome'),
       'valid_model_run':report.get('valid_model_run'),'condition':'ma_id','wall_seconds':report.get('wall_seconds'),
       'collaboration_contract':report.get('collaboration_contract'),'evaluation_success':bool(report.get('evaluation',{}).get('success'))},ensure_ascii=False,indent=2))
    if report.get('model_task_outcome')!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
