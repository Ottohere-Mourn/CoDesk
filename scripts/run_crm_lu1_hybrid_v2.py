#!/usr/bin/env python3
"""CRM-LU1 legacy customer-record full-form update Hybrid v2 screen."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, secrets, shlex, subprocess, sys, threading, time, uuid
from pathlib import Path

ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
IMAGE=Path('/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2')
RUNTIME='swcub/osworld-v2.1-qemu-runtime:local'
APP=ROOT/'scripts'/'crm_lu1_app_v1.py'
FIXTURE=ROOT/'scripts'/'crm_lu1_fixture_v1.py'
ARTIFACT_ROOT=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/crm-lu1-hybrid-v2')
MODEL='gpt-6-sol'; TASK_ID='CRM-LU1'; TASK_VERSION='0.1.1-legacy-full-record-form-role-tabs'
BUDGET=20; TOKEN_BUDGET=12000; ARMS=('ma_id','ma_sd','ma_sd_lock')
PORT=8765
PROMPTS={
 'A':"""You are the renewal coordinator for synthetic customer C-014. Use the visible Northwind CRM page and the signed renewal addendum RN-014 shown there. Select the Renewal contact section, update only its field to Jordan Lee, then save and verify the value. Do not change the billing email or any other customer.  This is a local synthetic record only; no real CRM or customer data. GUI changes must be made through the visible page, not Guest CLI.""",
 'B':"""You are the billing coordinator for synthetic customer C-014. Use the visible Northwind CRM page and the verified billing-contact notice BN-014 shown there. Select the Billing email section, update only its field to ap@northwind.example, then save and verify the value. Do not change the renewal contact or any other customer.  This is a local synthetic record only; no real CRM or customer data. GUI changes must be made through the visible page, not Guest CLI."""
}
PROMPT_SHA={a:hashlib.sha256(t.encode()).hexdigest() for a,t in PROMPTS.items()}
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
for k,v in {'OSWORLD_V2_DIR':str(OSWORLD),'SWCUB_OSWORLD_GUEST_IMAGE':str(IMAGE),
            'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME,'OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME}.items():
    os.environ.setdefault(k,v)
from scripts import run_writer_calc_v1 as base
from scripts import crm_lu1_fixture_v1 as fx
from scripts import probe_calcmode1_menu_v1 as readiness_probe
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor,_start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore,make_server
from oscombo.harness.hybrid_v2 import MCP_PYTHON
from swcub.resource_safety import ensure_resource_identity

APP_SHA=hashlib.sha256(APP.read_bytes()).hexdigest()
FIXTURE_SHA=hashlib.sha256(FIXTURE.read_bytes()).hexdigest()

def _json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def _preflight(parent):
    import shutil
    if not APP.is_file() or not FIXTURE.is_file():raise RuntimeError('case app/fixture missing')
    if shutil.disk_usage('/').free<20*1024**3:raise RuntimeError('root free space below 20 GiB')
    if shutil.disk_usage('/mnt/raid1').free<100*1024**3:raise RuntimeError('RAID1 free space below 100 GiB')
    mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    if mem<20*1024**3:raise RuntimeError('MemAvailable below 20 GiB')
    if not parent.is_relative_to(Path('/mnt/raid1')):raise RuntimeError('artifacts must be on RAID1')
    if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,timeout=20,check=True).stdout.strip():
        raise RuntimeError('active Docker container; refusing Guest')
    if not IMAGE.is_file() or subprocess.run(['docker','image','inspect',RUNTIME],capture_output=True,timeout=20).returncode:
        raise RuntimeError('pinned Guest/runtime missing; no pull')
    if not os.environ.get('SWCUB_SOL_API_KEY'):raise RuntimeError('SWCUB_SOL_API_KEY absent; no model or Guest request started')

def _env(out,runid):
    (out/'overlays').mkdir(parents=True,exist_ok=True);ledger=out/'resource-events.jsonl'
    os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),
      'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),
      'OSWORLD_V2_DIR':str(OSWORLD)})
    os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
    return ledger,ensure_resource_identity(ledger)

def _read_state(d):
    code="import json,urllib.request;print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:%d/api/state',timeout=8))))"%PORT
    raw=base.guest_command(d,['python3','-c',code],timeout=15).strip().splitlines()[-1]
    return json.loads(raw)

def _setup_guest(binding,ep,d,out,runid,log):
    guest_root='/tmp/crm_lu1_'+runid
    files={guest_root+'/scripts/crm_lu1_app_v1.py':APP.read_bytes(),
           guest_root+'/scripts/crm_lu1_fixture_v1.py':FIXTURE.read_bytes()}
    for dest,raw in files.items():
        payload=base64.b64encode(raw).decode('ascii')
        py="from pathlib import Path;import base64;p=Path("+repr(dest)+");p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode("+repr(payload)+"))"
        ep.cli_action('task_setup_case_files', 'python3 -c '+shlex.quote(py))
    launch_server=("PYTHONPATH="+shlex.quote(guest_root)+
       " python3 "+shlex.quote(guest_root+'/scripts/crm_lu1_app_v1.py')+
       " --host 127.0.0.1 --port "+str(PORT)+" --state "+shlex.quote(guest_root+'/state.json')+
       " >/tmp/crm-lu1-app.log 2>&1 </dev/null &")
    ep.cli_action('task_setup_local_app_start','bash -lc '+shlex.quote(launch_server))
    browser=base.guest_command(d,['bash','-lc','command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE'],10).strip().splitlines()[-1]
    if browser=='NONE':raise RuntimeError('Chromium unavailable in pinned Guest')
    launch=("nohup "+shlex.quote(browser)+" --no-sandbox --start-maximized --no-first-run --no-default-browser-check "
       "--disable-dev-shm-usage --disable-extensions --disable-background-networking --no-proxy-server "
       "--user-data-dir="+shlex.quote(guest_root+'/chrome')+" --new-window http://127.0.0.1:"+str(PORT)+"/ "
       ">/tmp/crm-lu1-browser.log 2>&1 </dev/null &")
    ep.cli_action('task_setup_browser_start','bash -lc '+shlex.quote(launch))
    deadline=time.monotonic()+40;last=None
    while time.monotonic()<deadline:
        try:
            state=_read_state(d)
            if state.get('record')==fx.INITIAL and state.get('events')==[]:break
        except Exception as exc:last=f'{type(exc).__name__}: {exc}'
        time.sleep(1)
    else:raise RuntimeError('CRM-LU1 app health/state readiness failed: '+str(last))
    shot_dir=out/'readiness'/binding;shot_dir.mkdir(parents=True,exist_ok=True)
    d.guest_key=binding
    from PIL import Image,ImageStat
    # Chrome first-run startup can lag the app health check. Wait for an actual
    # browser-page screenshot instead of accepting the desktop wallpaper.
    time.sleep(8)
    obs=None;shot=None;page_light_fraction=0.0;im=None
    for attempt in range(12):
        obs=readiness_probe.mcp(ep,d,shot_dir,'screenshot',{},'crm-lu1-initial-'+binding,locked=False)
        shots=list(shot_dir.rglob('crm-lu1-initial-'+binding+'-screenshot.png'))
        if not shots:shots=list(shot_dir.rglob('*.png'))
        if shots:
            shot=shots[0];im=Image.open(shot).convert('RGB')
            px=im.load();stride=8
            samples=[px[x,y] for y in range(0,im.height,stride) for x in range(0,im.width,stride)]
            page_light_fraction=sum(1 for r,g,b in samples if min(r,g,b)>225)/max(1,len(samples))
            if page_light_fraction>0.10:break
        time.sleep(1)
    if shot is None or im is None:raise RuntimeError('visible browser screenshot missing')
    if im.width<1000 or im.height<600 or max(ImageStat.Stat(im).stddev)<8 or page_light_fraction<=0.10:
        raise RuntimeError('CRM page did not visibly load in the Guest browser')
    d.guest_key=binding
    cli_root='/tmp/crm_lu1_cli_'+runid
    ep.cli_action('task_setup_cli_root','mkdir -p '+shlex.quote(cli_root))
    return {'state':state,'screenshot':str(shot),'screenshot_size':[im.width,im.height],
            'screenshot_stddev':ImageStat.Stat(im).stddev,'page_light_fraction':page_light_fraction,'screenshot_observation':obs,
            'app_port':PORT,'app_root':guest_root,'cli_root':cli_root,
            'guest_id':ep.snapshot().get('guest_container_id'),
            'browser':browser,'state_file':guest_root+'/state.json'}

def _actor_actions(out,actor):
    rows=[]
    p=out/'actor_runs'/actor/actor/'actions.jsonl'
    try:
        for line in p.read_text(encoding='utf-8').splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:pass
    except FileNotFoundError:pass
    return rows

def _run(args):
    endpoint=(os.environ.get('CODESK_SOL_ENDPOINT') or 'https://docode.cc/v1').rstrip('/')
    if not endpoint.startswith('https://'):raise RuntimeError('Sol endpoint must use HTTPS')
    parent=args.artifact_parent.expanduser().resolve();_preflight(parent)
    out=parent/args.run_id
    if out.exists():raise FileExistsError(out)
    shared=args.condition!='ma_id';locked=args.condition=='ma_sd_lock';baseline=None
    if shared:
        if not args.baseline_report or not args.baseline_report.is_file():raise RuntimeError('shared arm requires MA-ID report')
        baseline=json.loads(args.baseline_report.read_text(encoding='utf-8'))
        if not (baseline.get('task_id')==TASK_ID and baseline.get('task_version')==TASK_VERSION
             and baseline.get('condition')=='ma_id' and baseline.get('valid_model_run') is True
             and baseline.get('task_success') is True and baseline.get('reset_success') is True
             and baseline.get('fixture_sha256')==FIXTURE_SHA and baseline.get('app_sha256')==APP_SHA
             and baseline.get('prompt_sha256')==PROMPT_SHA and baseline.get('model',{}).get('model')==MODEL):
            raise RuntimeError('matched successful MA-ID report rejected')
    out.mkdir(parents=True,exist_ok=False)
    for x in ('actor_runs','collaboration','guest-artifacts','readiness','locks'):(out/x).mkdir(parents=True,exist_ok=True)
    os.environ['SWCUB_OSWORLD_CACHE_DIR']=str(parent/'osworld-cache')
    ledger,ident=_env(out,args.run_id)
    log=base.EventLog();bindings={'A':'shared','B':'shared'} if shared else {'A':'actor_a','B':'actor_b'}
    guest_bindings=list(dict.fromkeys(bindings.values()))
    report={'run_id':args.run_id,'task_id':TASK_ID,'task_version':TASK_VERSION,
      'candidate':'CRM-LU1 synthetic customer master record: two role-owned fields saved from stale full-record forms',
      'condition':args.condition,'runtime_profile':'gui-cli-mcp-v2',
      'actor_implementation':'reused CodexHarness / Codex CLI 0.155.0',
      'model':{'model':MODEL,'endpoint':endpoint,'effort':'medium','request_retries':5,
               'steps_per_actor':BUDGET,'output_token_budget_per_actor':TOKEN_BUDGET},
      'tool_permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],
      'fixture_sha256':FIXTURE_SHA,'app_sha256':APP_SHA,'prompt_sha256':PROMPT_SHA,'task_prompts':PROMPTS,
      'schedule':'serial B then A in every arm. In Shared, both role forms are loaded from record version 1 before either save; B saves first and A later submits its still-open version-1 full form. In MA-ID the same two tasks run in independent Guest-local copies.',
      'topology':{'ma_id':'fresh independent Guest/app state per actor',
        'shared':'one Guest/app state; both full-record forms loaded from same initial record and remain open across saves','lock_scope':'production per-GUI/CLI tool-call mutex when enabled'},
      'lock_semantics':{'enabled':locked,'interpretation':'serialization protects individual GUI/CLI calls but does not merge fields submitted by a stale full-record form; no simultaneous MCP calls are required'},
      'bindings':bindings,'baseline_run_id':baseline.get('run_id') if baseline else None,
      'actor_results':{},'tool_usage':{},'guest_setup':{},'intermediate_states':{},
      'final_states':{},'evaluations':{},'valid_model_run':False,'task_success':False,'reset_success':False}
    eps={};desks={};setups={};relays=[];server=None;statuses={};started=time.monotonic()
    try:
        image_id=subprocess.run(['docker','image','inspect',RUNTIME,'--format','{{.Id}}'],capture_output=True,text=True,check=True,timeout=15).stdout.strip()
        report['runtime']={'runtime_image':RUNTIME,'runtime_image_id':image_id,'guest_image':str(IMAGE),'artifacts_on_raid1':True}
        store=ProtocolStore(out/'collaboration',args.run_id);tokens={a:secrets.token_urlsafe(32) for a in ('A','B')}
        server=make_server(store,tokens);threading.Thread(target=server.serve_forever,daemon=True).start();token_env={}
        for a in ('A','B'):
            name='CRMLU1_COLLAB_'+a+'_'+uuid.uuid4().hex[:8].upper();os.environ[name]=tokens[a];token_env[a]=name

        def start_guest(binding):
            ep,d=base.make_desktop(binding,log,out/'guest-artifacts'/binding,require_a11y_tree=False)
            eps[binding]=ep;desks[binding]=d;d.guest_key=binding
            setup=_setup_guest(binding,ep,d,out,args.run_id,log);setups[binding]=setup
            report['guest_setup'][binding]=setup
            return ep,d

        def close_guest(binding,ep):
            try:ep.copy_artifacts(out/'guest-artifacts'/binding)
            except Exception as exc:report.setdefault('artifact_errors',[]).append(f'{binding}: {type(exc).__name__}: {exc}')
            try:ep.close()
            except Exception as exc:report.setdefault('close_errors',[]).append(f'{binding}: {type(exc).__name__}: {exc}')
            eps.pop(binding,None);desks.pop(binding,None)

        def run_actor(actor,binding,ep,d):
            actor_dir=out/'actor_runs'/actor;actor_dir.mkdir(parents=True,exist_ok=True)
            relay_env='CRMLU1_RELAY_'+actor+'_'+uuid.uuid4().hex[:8].upper();os.environ[relay_env]=secrets.token_urlsafe(32)
            relay,url=_start_codex_compat_relay(actor_dir,endpoint,'SWCUB_SOL_API_KEY',os.environ[relay_env],relay_env,
                output_token_budget=TOKEN_BUDGET,response_token_cap=2048,reserve_on_missing_usage=True);relays.append(relay)
            from oscombo.guest import Guest
            guest=Guest(d);guest.guest_key=binding;guest.actor=actor
            root=setups[binding]['cli_root']+'_'+actor
            ep.cli_action('task_setup_actor_cli_root','mkdir -p '+shlex.quote(root))
            lock=str(out/'locks'/'gui-cli-actions.lock') if locked else None
            return _run_model_actor(actor,guest,PROMPTS[actor],out,MODEL,url,'SWCUB_SOL_API_KEY',MCP_PYTHON,
                f'http://127.0.0.1:{server.server_port}',token_env[actor],max_steps=BUDGET,effort='medium',
                timeout=3500,request_retries=5,tool_cooldown_sec=0.0,relay_client_token_env=relay_env,
                hybrid_v2=True,condition='collaborative_shared_lock' if locked else 'collaborative_shared' if shared else 'collaborative_isolated',
                episode_id=args.run_id+'-'+actor,cli_root=root,action_lock_file=lock,
                task_id=TASK_ID+'@'+TASK_VERSION,desktop_tool_timeout_sec=3600)

        states={};final={}
        if shared:
            ep,d=start_guest('shared')
            for actor in ('B','A'):
                statuses[actor]=run_actor(actor,'shared',ep,d)
                states[actor]=_read_state(d)
                report['intermediate_states'][actor]=states[actor]
            final={'shared':_read_state(d)}
            close_guest('shared',ep)
        else:
            for actor in ('B','A'):
                binding='actor_'+actor.lower()
                ep,d=start_guest(binding)
                statuses[actor]=run_actor(actor,binding,ep,d)
                states[actor]=_read_state(d)
                report['intermediate_states'][actor]=states[actor]
                final[binding]=states[actor]
                close_guest(binding,ep)

        report['actor_results']=statuses;report['final_states']=final
        if shared:
            final_state=final['shared']
            b_after_b=report['intermediate_states']['B']
            b_task=fx.actor_success(b_after_b,'B')
            a_task=fx.actor_success(final_state,'A')
            b_final=fx.actor_success(final_state,'B')
            signature=fx.lost_update_signature(final_state)
            report['evaluations']={'B_owner_field_after_B':b_task,'A_owner_field_after_A':a_task,
                'B_owner_field_after_A':b_final,'joint_final_record':fx.joint_success(final_state),
                'lost_update_signature':signature,'final_record':final_state.get('record'),
                'failure_attribution':'A stale full-record save overwrote B billing_email' if signature and b_task and a_task and not b_final else None}
            success=fx.joint_success(final_state)
        else:
            state_a=final['actor_a'];state_b=final['actor_b']
            ap=fx.actor_success(state_a,'A');bp=fx.actor_success(state_b,'B')
            success=ap and bp
            report['evaluations']={'A_isolated_owner_field':ap,'A_state':state_a,
                'B_isolated_owner_field':bp,'B_state':state_b,'joint_actor_tasks_pass':success}

        rows={a:_actor_actions(out,a) for a in ('A','B')}
        report['tool_usage']={a:{'calls':len(rows[a]),'by_tool':{t:sum(x.get('tool')==t for x in rows[a]) for t in sorted({x.get('tool','unknown') for x in rows[a]})},
             'tools':[x.get('tool') for x in rows[a]]} for a in ('A','B')}
        collab=out/'collaboration'/'events.jsonl';events=[]
        if collab.is_file():
            for line in collab.read_text(encoding='utf-8').splitlines():
                try:events.append(json.loads(line))
                except json.JSONDecodeError:pass
        report['collaboration_events']=events
        relay_calls={}
        for actor in ('A','B'):
            rp=out/'actor_runs'/actor/'codex_relay_events.jsonl';ev=[]
            if rp.is_file():
                for line in rp.read_text(encoding='utf-8').splitlines():
                    try:ev.append(json.loads(line))
                    except json.JSONDecodeError:pass
            relay_calls[actor]=sum(bool(x.get('request_json')) and x.get('upstream_status')==200 and x.get('model')==MODEL for x in ev)
        report['model_calls']=relay_calls;report['model_call_evidence']='codex_relay_events.jsonl: request_json=true, upstream_status=200, model=gpt-6-sol'
        actor_ok=all(statuses.get(a,{}).get('status') in {'done','max_steps','fail'} for a in ('A','B'))
        report['model_used']=all(relay_calls.get(a,0)>0 for a in ('A','B'))
        report['valid_model_run']=bool(actor_ok and report['model_used'])
        if args.condition=='ma_id':
            report['condition_classification']='MA-ID_PASS' if report['valid_model_run'] and success else 'MA-ID_FAIL' if report['valid_model_run'] else 'INVALID'
        elif report['valid_model_run'] and success:
            report['condition_classification']='Shared+Lock_PASS' if locked else 'Shared_PASS'
        elif report['valid_model_run'] and report['evaluations'].get('failure_attribution'):
            report['condition_classification']='Shared+Lock_FAIL' if locked else 'Shared_FAIL'
        elif report['valid_model_run']:
            report['condition_classification']='shared_fail_unattributed'
        else:report['condition_classification']='INVALID'
        report['task_success']=bool(success);report['status']='completed' if report['valid_model_run'] else 'invalid_model_or_protocol'
    except KeyboardInterrupt:
        report['status']='invalid_setup_or_runtime';report['error']={'type':'KeyboardInterrupt','message':'Interrupted; not counted as task failure.'};report['valid_model_run']=False
    except Exception as exc:
        report['status']='invalid_setup_or_runtime';report['error']={'type':type(exc).__name__,'message':str(exc)};report['valid_model_run']=False
    finally:
        for b,ep in list(eps.items()):
            try:ep.copy_artifacts(out/'guest-artifacts'/b)
            except Exception as exc:report.setdefault('artifact_errors',[]).append(f'{b}: {type(exc).__name__}: {exc}')
            try:ep.close()
            except Exception as exc:report.setdefault('close_errors',[]).append(f'{b}: {type(exc).__name__}: {exc}')
        for proc in relays:
            try:proc.terminate();proc.wait(timeout=8)
            except Exception:
                try:proc.kill()
                except Exception:pass
        if server is not None:
            try:server.shutdown();server.server_close()
            except Exception:pass
        try:
            from swcub.resource_safety import cleanup_docker_cli_container
            evs=[json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
            created={x.get('resource_id') for x in evs if x.get('event')=='created' and x.get('resource_type')=='container'}
            destroyed={x.get('resource_id') for x in evs if x.get('event')=='destroyed' and x.get('resource_type')=='container'}
            for cid in sorted(created-destroyed):
                try:cleanup_docker_cli_container(cid,ident,reason='runner_finally_owned_orphan_cleanup')
                except Exception as exc:report.setdefault('orphan_cleanup_errors',[]).append(f'{cid}: {type(exc).__name__}: {exc}')
        except Exception as exc:report.setdefault('orphan_cleanup_errors',[]).append(f'{type(exc).__name__}: {exc}')
        report['wall_seconds']=round(time.monotonic()-started,2)
        try:
            report['resource_lifecycle']=base.verify_ledger(ledger)
            report['reset_success']=bool(report['resource_lifecycle'].get('all_containers_have_destroy_record'))
        except Exception as exc:
            report['resource_lifecycle']={'error':str(exc)};report['reset_success']=False
        if not report['reset_success']:report['valid_model_run']=False
        if report.get('status')=='completed' and not report['reset_success']:report['status']='invalid_environment_reset'
        _json(out/'report.json',report)
        _json(out/'provenance.json',{'run_id':args.run_id,'source_commit':base.git_source_state(),
           'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'fixture_sha256':FIXTURE_SHA,'app_sha256':APP_SHA,'prompt_sha256':PROMPT_SHA,
           'task_version':TASK_VERSION,'model':MODEL,'endpoint':endpoint})
    print(json.dumps({'run_id':args.run_id,'condition':args.condition,'status':report['status'],
       'valid_model_run':report.get('valid_model_run'),'task_success':report.get('task_success'),
       'classification':report.get('condition_classification'),'evaluations':report.get('evaluations'),
       'wall_seconds':report['wall_seconds'],'error':report.get('error'),'out':str(out)},ensure_ascii=False,indent=2))
    return 0 if report.get('valid_model_run') else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=ARMS,required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--baseline-report',type=Path)
    p.add_argument('--artifact-parent',type=Path,default=ARTIFACT_ROOT)
    raise SystemExit(_run(p.parse_args()))
if __name__=='__main__':main()
