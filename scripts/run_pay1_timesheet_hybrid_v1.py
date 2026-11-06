#!/usr/bin/env python3
"""PAY-1 GPT-6-Sol Hybrid v2 experimental runner. Starts with matched MA-ID baseline only."""
from __future__ import annotations
import argparse, base64, concurrent.futures, hashlib, json, os, secrets, shlex, shutil, subprocess, sys, threading, time, uuid
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
IMAGE=Path('/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2')
RUNTIME='swcub/osworld-v2.1-qemu-runtime:local'
ART=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/pay1-timesheet-hybrid-v1')
MODEL='gpt-6-sol';ENDPOINT_DEFAULT='https://docode.cc/v1';BUDGET=18;TOKEN_BUDGET=18000
ARMS=('ma_id','ma_sd','ma_sd_lock')
PROMPTS={
'A':"""You are the payroll clerk for weekly batch W19. Complete the payroll clerk task in the GUI for employee E-08: create exactly one correct payroll line using the currently approved hours. First use Guest CLI MCP to read batch_policy.txt. Inspect the visible approved timecard and the line form; do not assume hours without checking. The line form snapshots hours when you add it. After adding the line, inspect both the current approved timecard and the batch line; before finishing there must be exactly one active line for E-08/W19 with hours and amount matching the currently approved timecard. If the timecard changes while you work, use the ordinary Void line control and rebuild the line from the current approved record. Do not edit the timecard or B's source evidence. Send B a collaboration message reporting the hours/line you prepared, and read B's reply if available. Preserve all other records.""",
'B':"""You are the authorized payroll supervisor for weekly batch W19. Read A's collaboration message. Use Guest CLI MCP to read correction.json and verify the signed correction document ID, employee, week, corrected hours, and authorization. In the supervisor GUI, apply this authorized correction to E-08/W19; verify the timecard shows the correction ID and 6.0 approved hours. Do not edit or void a payment line. Send A a collaboration message confirming the correction ID and new approved hours. Preserve all other records."""
}
PROMPT_SHA={a:hashlib.sha256(v.encode()).hexdigest() for a,v in PROMPTS.items()}
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
for k,v in {'OSWORLD_V2_DIR':str(OSWORLD),'SWCUB_OSWORLD_GUEST_IMAGE':str(IMAGE),'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME,'OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME}.items():os.environ.setdefault(k,v)
from scripts import run_writer_calc_v1 as base
from scripts import pay1_timesheet_fixture_v1 as fx
from scripts import pay1_timesheet_app_v1 as app
from scripts.run_wf_receiving_hybrid_v3 import _start_receiving_codex_relay
from oscombo.harness.hybrid_v2 import MCP_PYTHON,MCP_SITE
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor
from oscombo.collab.data_to_deck.protocol import ProtocolStore,make_server
from swcub.resource_safety import ensure_resource_identity

def _json(p,data): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def preflight(require_key=True):
    if shutil.disk_usage('/').free<20*1024**3:raise RuntimeError('root free space below 20 GiB')
    if shutil.disk_usage('/mnt/raid1').free<100*1024**3:raise RuntimeError('RAID1 free space below 100 GiB')
    mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    if mem<20*1024**3:raise RuntimeError('MemAvailable below 20 GiB')
    if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True,timeout=20).stdout.strip():raise RuntimeError('active Docker container; refusing Guest start')
    if not IMAGE.is_file():raise RuntimeError('pinned Guest image missing')
    if subprocess.run(['docker','image','inspect',RUNTIME],capture_output=True,timeout=20).returncode:raise RuntimeError('pinned runtime missing locally; no pull/build')
    if require_key and not os.environ.get('SWCUB_SOL_API_KEY'):raise RuntimeError('GPT-6-Sol key absent; no Guest started')
def _env(out,runid):
    (out/'overlays').mkdir(parents=True,exist_ok=True);ledger=out/'resource-events.jsonl'
    os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),'OSWORLD_V2_DIR':str(OSWORLD)})
    os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
    return ledger,ensure_resource_identity(ledger)
def _guest(d,argv,timeout=30):return base.guest_command(d,argv,timeout=timeout)
def _state(d):return json.loads(_guest(d,['curl','--noproxy','*','-fsS',f'http://127.0.0.1:{app.PORT}/api/state'],10))
def _post(d,path,obj):
    payload=base64.b64encode(json.dumps(obj,separators=(',',':')).encode()).decode()
    code="import base64,urllib.request;u='http://127.0.0.1:"+str(app.PORT)+path+"';d=base64.b64decode("+repr(payload)+");r=urllib.request.urlopen(urllib.request.Request(u,data=d,headers={'Content-Type':'application/json'},method='POST'));print(r.read().decode())"
    return json.loads(_guest(d,['python3','-c',code],10))
def _mcp(tool,args,out,d,actor,episode,condition,gate=None,lock=None,timeout=180):
    log=out/'coordinator_mcp'/actor/'actions.jsonl';log.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update({'OSCOMBO_GUEST_URL':f'http://{d.vm_ip}:{d.server_port}','OSCOMBO_ACTION_LOG':str(log),'OSCOMBO_MAX_STEPS':'8','OSCOMBO_MCP_SETTLE':'0.3','OSCOMBO_ACTOR_ID':actor,'OSCOMBO_EPISODE_ID':episode,'OSCOMBO_GUEST_KEY':d.guest_key,'OSCOMBO_CONDITION':'collaborative_isolated' if condition=='ma_id' else 'collaborative_shared_lock' if condition=='ma_sd_lock' else 'collaborative_shared','PYTHONPATH':os.pathsep.join(x for x in (MCP_SITE,str(HYBRID),str(ROOT),str(OSWORLD),os.environ.get('PYTHONPATH','')) if x)})
    if gate:env['OSCOMBO_MCP_GATE_CONFIG']=str(gate)
    else:env.pop('OSCOMBO_MCP_GATE_CONFIG',None)
    if lock:env['OSCOMBO_ACTION_LOCK_FILE']=str(lock)
    else:env.pop('OSCOMBO_ACTION_LOCK_FILE',None)
    cp=subprocess.run([MCP_PYTHON,'-m','oscombo.desktop_tools',tool,json.dumps(args)],env=env,capture_output=True,text=True,timeout=timeout)
    if cp.returncode:raise RuntimeError(f'coordinator MCP {tool} exited {cp.returncode}: {cp.stderr[-1000:]}')
    obj=json.loads(cp.stdout)
    if obj.get('error'):raise RuntimeError(f'coordinator MCP {tool} failed: {obj["error"]}')
    png=base64.b64decode(obj['image']) if obj.get('image') else None
    return {'text':obj.get('text'),'image':png,'action_log':str(log.relative_to(out))}
def _green_center(png):
    from PIL import Image
    import io
    im=Image.open(io.BytesIO(png)).convert('RGB');pts=[]
    for y in range(100,min(im.height,650)):
        for x in range(200,min(im.width,1180)):
            r,g,b=im.getpixel((x,y))
            if 14<=r<=32 and 94<=g<=120 and 58<=b<=88:pts.append((x,y))
    rows={}
    for x,y in pts:rows.setdefault(y,[]).append(x)
    bands=[];band=[]
    for y in sorted(rows):
        if not band or y<=band[-1][0]+2:band.append((y,rows[y]))
        else:bands.append(band);band=[(y,rows[y])]
    if band:bands.append(band)
    hits=[]
    for b in bands:
        xs=[x for _,v in b for x in v];ys=[y for y,v in b for x in v]
        x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys)
        if x1-x0>=35 and y1-y0>=12:hits.append({'x':(x0+x1)//2,'y':(y0+y1)//2,'bbox':[x0,y0,x1,y1],'pixels':len(xs)})
    if len(hits)!=1:raise RuntimeError(f'expected exactly one visible green action button, found {hits}')
    return hits[0]
def _write_guest(ep,path,content,label):
    encoded=base64.b64encode(content.encode()).decode();py='from pathlib import Path;import base64;p=Path('+repr(path)+');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode('+repr(encoded)+'));p.chmod(0o444)'
    ep.cli_action(label,'python3 -c '+shlex.quote(py))
def _setup(ep,d,out,runid,actor,condition,cli_root):
    _write_guest(ep,app.SERVER_PATH,app.server_text(fx.SOURCE_FIXTURE_SHA256),'pay1_app_install')
    if actor=='A':
        policy='PAYROLL DRAFT-BATCH POLICY\nLines snapshot the hours entered when added. Compare current approved timecard with active batch line before batch release. An active draft line can be voided and rebuilt before release.\n'
        _write_guest(ep,cli_root+'/batch_policy.txt',policy,'pay1_actor_evidence')
    else:
        evidence=json.dumps({'document_id':fx.CORRECTION_ID,'employee_id':fx.EMPLOYEE_ID,'week_id':fx.WEEK_ID,'corrected_hours_tenths':fx.CORRECTED_HOURS_TENTHS,'authorized_by':fx.SUPERVISOR_ID,'signed':True,'reason_code':fx.CORRECTION_SOURCE['reason_code']},indent=2)
        _write_guest(ep,cli_root+'/correction.json',evidence,'pay1_actor_evidence')
    start='nohup /usr/bin/python3 '+shlex.quote(app.SERVER_PATH)+' --state '+shlex.quote(app.STATE_PATH)+' --port '+str(app.PORT)+' >/tmp/codesk-pay1-hybrid.log 2>&1 </dev/null & echo $! >/tmp/codesk-pay1-hybrid.pid'
    ep.cli_action('pay1_app_start','bash -lc '+shlex.quote(start))
    health='';deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:health=_guest(d,['curl','--noproxy','*','-fsS','--max-time','2',f'http://127.0.0.1:{app.PORT}/health'],5)
        except Exception:time.sleep(.25);continue
        if '"ok"' in health:break
        time.sleep(.25)
    if '"ok"' not in health:raise RuntimeError('Guest app health failed: '+health[:300])
    browser=_guest(d,['bash','-lc','command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE'],10).strip().splitlines()[-1]
    if browser=='NONE':raise RuntimeError('Chromium unavailable in pinned Guest')
    profile='/tmp/codesk-pay1-hybrid/chrome-'+runid+'-'+actor
    urls=shlex.quote(app.ROUTES['clerk'])+' '+shlex.quote(app.ROUTES['supervisor'])
    launch='nohup '+shlex.quote(browser)+' --no-sandbox --start-maximized --no-first-run --no-default-browser-check --disable-dev-shm-usage --disable-extensions --disable-background-networking --no-proxy-server --remote-debugging-port=9222 --user-data-dir='+shlex.quote(profile)+' --new-window '+urls+' >/tmp/codesk-pay1-hybrid-browser.log 2>&1 </dev/null & echo $! >/tmp/codesk-pay1-hybrid-browser.pid'
    ep.cli_action('pay1_browser_start','bash -lc '+shlex.quote(launch))
    tabs=[];deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:tabs=json.loads(_guest(d,['curl','--noproxy','*','-fsS','http://127.0.0.1:9222/json/list'],5))
        except Exception:time.sleep(.25);continue
        routes={x.get('url','') for x in tabs if x.get('type')=='page'}
        if app.ROUTES['clerk'] in routes and app.ROUTES['supervisor'] in routes:break
        time.sleep(.25)
    else:raise RuntimeError('both clerk/supervisor tabs did not load')
    from swcub.environment import ActorContext
    gui=ActorContext('setup-'+actor,ep,'gui')
    if actor=='B':gui.press_key('ctrl+tab') # tab order: clerk first, supervisor second
    obs=ep.refresh_observation(source='pay1_'+actor+'_browser_ready');shot=obs.get('screenshot') if isinstance(obs,dict) else None
    if not isinstance(shot,bytes) or len(shot)<1000:raise RuntimeError('no browser screenshot during setup')
    p=out/'setup'/f'{actor}-ready.png';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(shot)
    # Desktop MCP observation is saved and passed to the actor through its first call.
    sm=_mcp('screenshot',{},out,d,'setup_'+actor,runid+'-setup-'+actor,condition,lock=(out/'locks'/'guest-actions.lock') if condition=='ma_sd_lock' else None)
    role_button=_green_center(sm['image'])
    expected_role='clerk' if actor=='A' else 'supervisor'
    if actor=='A' and not (680<=role_button['x']<=811):raise RuntimeError('A is not on the clerk tab: '+str(role_button))
    if actor=='B' and not (300<=role_button['x']<=460):raise RuntimeError('B is not on supervisor tab: '+str(role_button))
    from PIL import Image
    import io
    Image.open(io.BytesIO(sm['image'])).save(out/'setup'/f'{actor}-mcp-ready.png')
    return {'health':health,'browser':browser,'loaded_routes':sorted(x.get('url','') for x in tabs if x.get('type')=='page'),'role':expected_role,'green_button':role_button,'screenshot':str(p.relative_to(out)),'mcp_log':sm['action_log'],'initial_business_state':_state(d)}
def _messages(out):
    p=out/'collaboration'/'events.jsonl';rows=[]
    if p.is_file():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:pass
    messages=[x for x in rows if x.get('type')=='message']
    ab=[x for x in messages if x.get('actor')=='A' and x.get('recipient')=='B' and ('e-08' in str(x.get('body','')).casefold() or 'w19' in str(x.get('body','')).casefold())]
    ba=[x for x in messages if x.get('actor')=='B' and x.get('recipient')=='A' and 'cor-w19-e08' in str(x.get('body','')).casefold() and ('6.0' in str(x.get('body','')) or '60' in str(x.get('body','')))]
    ordered=any(float(b.get('timestamp',0))>float(a.get('timestamp',0)) for a in ab for b in ba)
    return rows,{'A_to_B_handoff':bool(ab),'B_to_A_correction_reply':bool(ordered),'success':bool(ab and ordered)}
def _actor_actions(out,actor):
    p=out/'actor_runs'/actor/actor/'actions.jsonl';rows=[]
    if p.is_file():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:pass
    return rows
def _run_actor(actor,ep,d,out,runid,condition,server,token_env,cli_root,gatefile=None):
    actor_out=out/'actor_runs'/actor;actor_out.mkdir(parents=True,exist_ok=True)
    relay_env='PAY1_RELAY_'+actor+'_'+uuid.uuid4().hex[:8].upper();os.environ[relay_env]=secrets.token_urlsafe(32)
    relay,url=_start_receiving_codex_relay(actor_out,os.environ.get('CODESK_SOL_ENDPOINT',ENDPOINT_DEFAULT),'SWCUB_SOL_API_KEY',os.environ[relay_env],relay_env,output_token_budget=TOKEN_BUDGET,response_token_cap=2048);RELAY_PROCS.append(relay)
    from oscombo.guest import Guest
    g=Guest(d);g.guest_key=d.guest_key;g.actor=actor
    overrides={'OSCOMBO_MCP_GATE_CONFIG':str(gatefile)} if gatefile else None
    lock=str(out/'locks'/'guest-actions.lock') if condition=='ma_sd_lock' else None
    return _run_model_actor(actor,g,PROMPTS[actor],out,MODEL,url,'SWCUB_SOL_API_KEY',MCP_PYTHON,f'http://127.0.0.1:{server.server_port}',token_env,max_steps=BUDGET,effort='medium',timeout=3600,request_retries=1,tool_cooldown_sec=0.0,relay_client_token_env=relay_env,hybrid_v2=True,condition='collaborative_shared_lock' if condition=='ma_sd_lock' else 'collaborative_shared' if condition!='ma_id' else 'collaborative_isolated',episode_id=runid+'-'+actor,cli_root=cli_root,action_lock_file=lock,mcp_env_overrides=overrides,task_id=fx.TASK_ID+'@'+fx.TASK_VERSION,desktop_tool_timeout_sec=3600)
RELAY_PROCS=[]
def run_ma_id(out,runid,ledger,identity):
    log=base.EventLog();store=ProtocolStore(out/'collaboration',runid);tokens={a:secrets.token_urlsafe(32) for a in ('A','B')};server=make_server(store,tokens);threading.Thread(target=server.serve_forever,daemon=True).start();token_envs={}
    for a in ('A','B'):
        n='PAY1_COLLAB_'+a+'_'+uuid.uuid4().hex[:8].upper();os.environ[n]=tokens[a];token_envs[a]=n
    statuses={};states={};setups={};bindings={};roots={};guest_ids={};model_attempted={a:False for a in ('A','B')}
    try:
        for actor in ('A','B'):
            binding='actor_'+actor.lower();bindings[actor]=binding
            ep=d=None
            try:
                ep,d=base.make_desktop(binding,log,out/binding,require_a11y_tree=False);guest_ids[actor]=ep.snapshot().get('guest_container_id');d.guest_key=binding
                cli_root='/tmp/pay1_cli_'+runid+'_'+actor;roots[actor]=cli_root;ep.cli_action('pay1_setup','mkdir -p '+shlex.quote(cli_root))
                setups[actor]=_setup(ep,d,out,runid,actor,'ma_id',cli_root)
                model_attempted[actor]=True
                statuses[actor]=_run_actor(actor,ep,d,out,runid,'ma_id',server,token_envs[actor],cli_root)
                states[actor]=_state(d)
            except Exception as exc:
                statuses.setdefault(actor,{'status':'error','error':f'{type(exc).__name__}: {exc}'})
                setups.setdefault(actor,{'status':'error','error':f'{type(exc).__name__}: {exc}'})
                if ep is not None:
                    try:ep.copy_artifacts(out/'setup-failure-artifacts'/binding)
                    except Exception:pass
            finally:
                if ep is not None:
                    try:ep.copy_artifacts(out/'guest-artifacts'/binding)
                    except Exception:pass
                    try:ep.close()
                    except Exception:pass
        messages,collab=_messages(out)
        if set(states)=={'A','B'}: evaluation=fx.evaluate_isolated(states['A'],states['B'])
        else:evaluation=None
        valid_actor_status=all(statuses.get(a,{}).get('status') in {'done','max_steps','fail'} for a in ('A','B'))
        report={'run_id':runid,'task_id':fx.TASK_ID,'task_version':fx.TASK_VERSION,'fixture_sha256':fx.SOURCE_FIXTURE_SHA256,'condition':'ma_id','model':MODEL,'endpoint':os.environ.get('CODESK_SOL_ENDPOINT',ENDPOINT_DEFAULT),'runtime_profile':'gui-cli-mcp-v2','actor_implementation':'CodexHarness/Codex CLI 0.155.0','tool_permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],'budget_per_actor':BUDGET,'output_token_budget_per_actor':TOKEN_BUDGET,'prompt_hashes':PROMPT_SHA,'prompts':PROMPTS,'setups':setups,'initial_workspace_bindings':bindings,'guest_container_ids':guest_ids,'actors':statuses,'actor_actions':{a:{'calls':len(_actor_actions(out,a)),'log':str((out/'actor_runs'/a/a/'actions.jsonl').relative_to(out))} for a in ('A','B')},'final_states':states,'collaboration_events':messages,'collaboration_contract':collab,'evaluation':evaluation,'reset_check':{'both_private_guest_workspaces_destroyed_after_capture':len(states)==2 and bindings.get('A')!=bindings.get('B')},'valid_model_run':bool(valid_actor_status and len(states)==2 and collab['success']),'model_called':any(model_attempted.values()),'api_called':any(model_attempted.values())}
        if report['valid_model_run']:
            report['model_task_outcome']='PASS' if evaluation['success'] and collab['success'] else 'FAIL';report['status']='completed'
        else:report['model_task_outcome']='environment_or_model_invalid';report['status']='invalid_model_or_protocol'
        return report,log,server
    except Exception:
        try:server.shutdown();server.server_close()
        except Exception:pass
        raise
def run_shared(out,runid,condition,baseline):
    log=base.EventLog();store=ProtocolStore(out/'collaboration',runid);tokens={a:secrets.token_urlsafe(32) for a in ('A','B')};server=make_server(store,tokens);threading.Thread(target=server.serve_forever,daemon=True).start();token_envs={}
    for a in ('A','B'):
        n='PAY1_COLLAB_'+a+'_'+uuid.uuid4().hex[:8].upper();os.environ[n]=tokens[a];token_envs[a]=n
    ep=d=None;pool=None;fa=None;signal=None;statuses={};states={};lock=out/'locks'/'guest-actions.lock';setups={};model_attempted={'A':False,'B':False}
    report={'run_id':runid,'task_id':fx.TASK_ID,'task_version':fx.TASK_VERSION,'fixture_sha256':fx.SOURCE_FIXTURE_SHA256,'condition':condition,'baseline_run_id':baseline.get('run_id'),'model':MODEL,'endpoint':os.environ.get('CODESK_SOL_ENDPOINT',ENDPOINT_DEFAULT),'runtime_profile':'gui-cli-mcp-v2','actor_implementation':'CodexHarness/Codex CLI 0.155.0','tool_permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],'budget_per_actor':BUDGET,'output_token_budget_per_actor':TOKEN_BUDGET,'prompt_hashes':PROMPT_SHA,'prompts':PROMPTS,'protocol_gate':{'phase':'not_started','enabled':True},'lock_file':str(lock) if condition=='ma_sd_lock' else None}
    gate=None;release_path=None;statuses_valid=False
    try:
        ep,d=base.make_desktop('shared',log,out/'shared',require_a11y_tree=False);d.guest_key='shared'
        cli_a='/tmp/pay1_cli_'+runid+'_A';cli_b='/tmp/pay1_cli_'+runid+'_B';report['cli_roots']={'A':cli_a,'B':cli_b}
        ep.cli_action('pay1_setup','mkdir -p '+shlex.quote(cli_a)+' '+shlex.quote(cli_b))
        setups['shared']=_setup(ep,d,out,runid,'A',condition,cli_a)
        evidence=json.dumps({'document_id':fx.CORRECTION_ID,'employee_id':fx.EMPLOYEE_ID,'week_id':fx.WEEK_ID,'corrected_hours_tenths':fx.CORRECTED_HOURS_TENTHS,'authorized_by':fx.SUPERVISOR_ID,'signed':True,'reason_code':fx.CORRECTION_SOURCE['reason_code']},indent=2)
        _write_guest(ep,cli_b+'/correction.json',evidence,'pay1_actor_evidence_B')
        bbox=setups['shared']['green_button']['bbox'];y0,y1=bbox[1],bbox[3]
        gate={'gate_id':runid+'-submit-click','actor_id':'A','tool':'click','argument':'y','contains_any':[str(y) for y in range(y0,y1+1)],'signal_dir':str(out/'protocol_gate'/'actor_A'),'timeout_seconds':3500}
        gatefile=out/'protocol_gate'/'gate-config.json';_json(gatefile,gate);signal=Path(gate['signal_dir']);signal.mkdir(parents=True,exist_ok=True);release_path=signal/'release.json'
        report['setups']=setups;report['protocol_gate']={'enabled':True,'gate_id':gate['gate_id'],'tool':'click','argument':'y','expected_button_bbox':bbox,'phase':'waiting_for_A_submit'}
        # MA-SD starts A's normal task and waits for the exact pending submit action.
        pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        model_attempted['A']=True
        fa=pool.submit(_run_actor,'A',ep,d,out,runid,condition,server,token_envs['A'],cli_a,gatefile if condition!='ma_id' else None)
        pending=None;deadline=time.monotonic()+3300;pending_path=signal/'pending.json'
        while time.monotonic()<deadline and pending is None and not fa.done():
            try:pending=json.loads(pending_path.read_text(encoding='utf-8'))
            except (FileNotFoundError,json.JSONDecodeError):time.sleep(.5)
        report['protocol_gate']['pending']=pending
        if pending is None:
            report['protocol_gate']['phase']='A_submit_gate_not_reached'
            try:statuses['A']=fa.result(timeout=3700)
            except Exception as exc:statuses['A']={'status':'error','error':f'{type(exc).__name__}: {exc}'}
        else:
            x=pending.get('args',{}).get('x');y=pending.get('args',{}).get('y')
            gate_match=(pending.get('actor_id')=='A' and pending.get('episode_id')==runid+'-A' and pending.get('guest_key')=='shared' and pending.get('condition')==('collaborative_shared_lock' if condition=='ma_sd_lock' else 'collaborative_shared') and pending.get('tool')=='click' and isinstance(x,int) and bbox[0]<=x<=bbox[2] and isinstance(y,int) and bbox[1]<=y<=bbox[3])
            at_gate=_state(d);report['state_at_pending_submit']=at_gate;report['protocol_gate']['click_matches_exact_submit_region']=bool(gate_match);report['protocol_gate']['phase']='A_submit_pending'
            try:
                nav=_mcp('key',{'keys':'ctrl+tab'},out,d,'coordinator_select_B',runid+'-select-B',condition,lock=lock if condition=='ma_sd_lock' else None)
                role=_green_center(nav['image']);report['protocol_gate']['B_tab_green_button']=role
                if not (300<=role['x']<=460):raise RuntimeError('B supervisor tab not active after coordinator handoff: '+str(role))
                model_attempted['B']=True
                statuses['B']=_run_actor('B',ep,d,out,runid,condition,server,token_envs['B'],cli_b,None)
            except Exception as exc:statuses['B']={'status':'error','error':f'{type(exc).__name__}: {exc}'}
            after_b=_state(d);report['state_after_B_before_A_resume']=after_b
            b_eval=fx.evaluate_actor(after_b,'B');report['B_business_result_before_A_resume']=b_eval
            report['protocol_gate']['B_terminated_before_A_resume']=statuses.get('B',{}).get('status') in {'done','max_steps','fail'}
            try:
                restore=_mcp('key',{'keys':'ctrl+shift+tab'},out,d,'coordinator_restore_A',runid+'-restore-A',condition,lock=lock if condition=='ma_sd_lock' else None)
                role_a=_green_center(restore['image']);report['protocol_gate']['restored_A_green_button']=role_a
                report['protocol_gate']['A_clerk_tab_restored']=bool(680<=role_a['x']<=811)
                from PIL import Image
                import io
                Image.open(io.BytesIO(restore['image'])).save(out/'setup'/'A-restored-before-release.png')
            except Exception as exc:
                report['protocol_gate']['restore_error']=f'{type(exc).__name__}: {exc}'
            release_path.write_text(json.dumps({'gate_id':gate['gate_id'],'reason':'B completed signed correction; restore A payroll clerk tab; release exact pending click'})+'\n',encoding='utf-8')
            report['protocol_gate']['released']=True;report['protocol_gate']['phase']='A_submit_dispatched_after_B'
            try:statuses['A']=fa.result(timeout=3700)
            except Exception as exc:statuses['A']={'status':'error','error':f'{type(exc).__name__}: {exc}'}
        if 'B' not in statuses:
            try:
                # If A never reached the gate, still finish B so the arm is auditable; it will remain protocol-invalid.
                nav=_mcp('key',{'keys':'ctrl+tab'},out,d,'coordinator_select_B',runid+'-select-B-no-gate',condition,lock=lock if condition=='ma_sd_lock' else None)
                _=nav
                model_attempted['B']=True;statuses['B']=_run_actor('B',ep,d,out,runid,condition,server,token_envs['B'],cli_b,None)
            except Exception as exc:statuses['B']={'status':'error','error':f'{type(exc).__name__}: {exc}'}
        states['shared']=_state(d);messages,collab=_messages(out)
        ev=fx.evaluate_shared(states['shared']);all_status=all(statuses.get(a,{}).get('status') in {'done','max_steps','fail'} for a in ('A','B'))
        pending_ok=bool(report['protocol_gate'].get('click_matches_exact_submit_region') and report['protocol_gate'].get('B_terminated_before_A_resume') and report['protocol_gate'].get('released') and report['protocol_gate'].get('A_clerk_tab_restored'))
        protocol_valid=bool(pending_ok and b_eval.get('success') and collab.get('success')) if pending is not None else False
        mechanism_exposure_valid=bool(pending is not None and gate_match and at_gate['timecard']['approved_hours_tenths']==80 and not at_gate['payment_lines'] and after_b['timecard']['approved_hours_tenths']==60)
        reset_before=_post(d,'/api/reset',{});reset_state=_state(d);reset_ok=(reset_state['timecard']['approved_hours_tenths']==80 and not reset_state['payment_lines'] and not reset_state['audit_log'])
        report.update({'setups':setups,'initial_workspace_bindings':{'A':'shared','B':'shared'},'actors':statuses,'actor_actions':{a:{'calls':len(_actor_actions(out,a)),'log':str((out/'actor_runs'/a/a/'actions.jsonl').relative_to(out))} for a in ('A','B')},'final_states':states,'collaboration_events':messages,'collaboration_contract':collab,'evaluation':ev,'protocol_valid':protocol_valid,'valid_model_run':bool(all_status and protocol_valid and mechanism_exposure_valid and reset_ok),'reset_check':{'reset_api_ok':bool(reset_before.get('ok')),'initial_hours_restored':reset_state['timecard']['approved_hours_tenths']==80,'payment_lines':len(reset_state['payment_lines']),'audit_log':len(reset_state['audit_log']),'success':reset_ok},'mechanism_exposure_valid':mechanism_exposure_valid,'api_called':any(model_attempted.values()),'model_called':any(model_attempted.values())})
        if report['valid_model_run']:
            report['status']='completed';report['model_task_outcome']='PASS' if ev['success'] and collab['success'] else 'FAIL'
        else:
            report['status']='invalid_model_or_protocol';report['model_task_outcome']='environment_or_model_invalid'
    except Exception as exc:
        report.update({'status':'invalid_infrastructure_or_protocol','model_task_outcome':'environment_or_model_invalid','valid_model_run':False,'error':{'type':type(exc).__name__,'message':str(exc)},'model_called':any(model_attempted.values()),'api_called':any(model_attempted.values())})
    finally:
        if fa is not None and not fa.done() and release_path is not None and not release_path.exists():
            try:release_path.write_text(json.dumps({'gate_id':gate.get('gate_id') if gate else None,'reason':'emergency cleanup release after coordinator error'})+'\n')
            except Exception:pass
        if fa is not None:
            try:fa.result(timeout=3700)
            except Exception:pass
        if pool is not None:pool.shutdown(wait=True)
        if ep is not None:
            try:ep.copy_artifacts(out/'guest-artifacts'/'shared')
            except Exception as exc:report.setdefault('artifact_errors',[]).append(str(exc))
            try:ep.close()
            except Exception as exc:report.setdefault('close_errors',[]).append(str(exc))
        try:server.shutdown();server.server_close()
        except Exception:pass
    return report,log

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--condition',choices=ARMS,default='ma_id');parser.add_argument('--baseline',default=None);args=parser.parse_args()
    baseline=None
    if args.condition!='ma_id':
        if not args.baseline:raise SystemExit('Shared arms require --baseline pointing to a valid exact MA-ID PASS report.')
        baseline=json.loads(Path(args.baseline).read_text(encoding='utf-8'))
        if not baseline.get('valid_model_run') or baseline.get('model_task_outcome')!='PASS' or baseline.get('condition')!='ma_id' or baseline.get('task_version')!=fx.TASK_VERSION or baseline.get('fixture_sha256')!=fx.SOURCE_FIXTURE_SHA256 or baseline.get('prompt_hashes')!=PROMPT_SHA:
            raise SystemExit('MA-ID baseline mismatch or not a valid PASS; no Guest started.')
    preflight(require_key=True);ART.mkdir(parents=True,exist_ok=True);runid='pay1-sol-'+args.condition+'-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6];out=ART/runid;out.mkdir(parents=True,exist_ok=False)
    for sub in ('actor_runs','actor_a','actor_b','shared','collaboration','setup','locks','protocol_gate','coordinator_mcp'):(out/sub).mkdir(parents=True,exist_ok=True)
    ledger,identity=_env(out,runid);started=time.monotonic();report={'run_id':runid,'status':'starting','model':'gpt-6-sol','endpoint':os.environ.get('CODESK_SOL_ENDPOINT',ENDPOINT_DEFAULT),'api_key_persisted':False,'condition':args.condition}
    _json(out/'prompts.json',PROMPTS)
    _json(out/'provenance-initial.json',{'source_commit':base.git_source_state(),'task_id':fx.TASK_ID,'task_version':fx.TASK_VERSION,'fixture_sha256':fx.SOURCE_FIXTURE_SHA256,'condition':args.condition,'baseline_run_id':baseline.get('run_id') if baseline else None,'model':MODEL,'permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],'budget_per_actor':BUDGET,'prompt_hashes':PROMPT_SHA,'app_sha256':hashlib.sha256(app.server_text(fx.SOURCE_FIXTURE_SHA256).encode()).hexdigest()})
    log=None
    try:
        if args.condition=='ma_id':report,log,server=run_ma_id(out,runid,ledger,identity)
        else:report,log=run_shared(out,runid,args.condition,baseline)
    except Exception as exc:
        report.update({'status':'invalid_infrastructure_or_protocol','model_task_outcome':'environment_or_model_invalid','valid_model_run':False,'error':{'type':type(exc).__name__,'message':str(exc)}})
    finally:
        for p in RELAY_PROCS:
            try:p.terminate();p.wait(timeout=10)
            except Exception:
                try:p.kill()
                except Exception:pass
        for k in list(os.environ):
            if k.startswith('PAY1_RELAY_') or k.startswith('PAY1_COLLAB_'):os.environ.pop(k,None)
        if log:
            try:log.write(out/'events.jsonl')
            except Exception as exc:report['event_log_error']=str(exc)
        report['wall_seconds']=round(time.monotonic()-started,2);report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
        if not report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record') or not report.get('resource_lifecycle',{}).get('labels_consistent'):
            report['valid_model_run']=False;report['model_task_outcome']='environment_or_model_invalid';report['status']='invalid_resource_lifecycle'
        report['provenance']={'resource_run_id':identity.run_id,'source_commit':base.git_source_state(),'fixture_sha256':fx.SOURCE_FIXTURE_SHA256,'guest_image':str(IMAGE),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'app_sha256':hashlib.sha256(app.server_text(fx.SOURCE_FIXTURE_SHA256).encode()).hexdigest()}
        _json(out/'report.json',report);_json(out/'provenance.json',report['provenance'])
    print(json.dumps({'out':str(out),'status':report.get('status'),'model_task_outcome':report.get('model_task_outcome'),'wall_seconds':report.get('wall_seconds'),'valid_model_run':report.get('valid_model_run'),'condition':args.condition},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
