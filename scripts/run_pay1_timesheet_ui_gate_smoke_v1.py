#!/usr/bin/env python3
"""No-model production Desktop MCP submit-click gate and PAY-1 stale snapshot control."""
from __future__ import annotations
import base64, hashlib, json, os, secrets, shlex, shutil, subprocess, sys, threading, time, uuid
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
IMAGE=Path('/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2')
RUNTIME='swcub/osworld-v2.1-qemu-runtime:local'
ART=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/pay1-timesheet-ui-gate-v1')
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
for k,v in {'OSWORLD_V2_DIR':str(OSWORLD),'SWCUB_OSWORLD_GUEST_IMAGE':str(IMAGE),'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME,'OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME}.items(): os.environ.setdefault(k,v)
from scripts import run_writer_calc_v1 as base
from scripts import pay1_timesheet_fixture_v1 as fx
from scripts import pay1_timesheet_app_v1 as app
from scripts import run_pay1_timesheet_guest_smoke_v1 as smoke
from oscombo.harness.hybrid_v2 import MCP_PYTHON,MCP_SITE
from swcub.resource_safety import ensure_resource_identity

def preflight():
    if shutil.disk_usage('/').free<20*1024**3: raise RuntimeError('root free space below 20 GiB')
    if shutil.disk_usage('/mnt/raid1').free<100*1024**3: raise RuntimeError('RAID1 free space below 100 GiB')
    mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    if mem<20*1024**3: raise RuntimeError('MemAvailable below 20 GiB')
    if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True,timeout=20).stdout.strip(): raise RuntimeError('active Docker container; refusing Guest start')
    if not IMAGE.is_file(): raise RuntimeError('pinned Guest image missing')
    if subprocess.run(['docker','image','inspect',RUNTIME],capture_output=True,timeout=20).returncode: raise RuntimeError('pinned runtime missing locally; no pull/build')
def guest(d,argv,timeout=30): return base.guest_command(d,argv,timeout=timeout)
def state(d): return json.loads(guest(d,['curl','--noproxy','*','-fsS',f'http://127.0.0.1:{app.PORT}/api/state'],10))
def _env(out,runid,actor,episode,gate=None):
    env=os.environ.copy();log=out/'mcp'/actor/'actions.jsonl';log.parent.mkdir(parents=True,exist_ok=True)
    env.update({'OSCOMBO_GUEST_URL':f'http://{CURRENT_DESK.vm_ip}:{CURRENT_DESK.server_port}','OSCOMBO_ACTION_LOG':str(log),
      'OSCOMBO_MAX_STEPS':'20','OSCOMBO_MCP_SETTLE':'0.6','OSCOMBO_ACTOR_ID':actor,'OSCOMBO_EPISODE_ID':episode,
      'OSCOMBO_GUEST_KEY':'pay1-ui-gate','OSCOMBO_CONDITION':'collaborative_shared',
      'PYTHONPATH':os.pathsep.join(x for x in (MCP_SITE,str(HYBRID),str(ROOT),str(OSWORLD),os.environ.get('PYTHONPATH','')) if x)})
    if gate: env['OSCOMBO_MCP_GATE_CONFIG']=str(gate)
    else: env.pop('OSCOMBO_MCP_GATE_CONFIG',None)
    return env,log
def mcp_call(tool,args,out,runid,actor,episode,gate=None,timeout=90):
    env,log=_env(out,runid,actor,episode,gate)
    cp=subprocess.run([MCP_PYTHON,'-m','oscombo.desktop_tools',tool,json.dumps(args)],env=env,capture_output=True,text=True,timeout=timeout)
    if cp.returncode: raise RuntimeError(f'{tool} MCP exited {cp.returncode}: {cp.stderr[-1000:]}')
    obj=json.loads(cp.stdout)
    if obj.get('error'): raise RuntimeError(f'{tool} MCP failed: {obj["error"]}')
    png=base64.b64decode(obj['image']) if obj.get('image') else None
    return {'text':obj.get('text'),'png':png,'log':str(log.relative_to(out))}
def save_shot(out,name,png):
    p=out/'screenshots'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(png);return p
def green_button_center(png):
    from PIL import Image
    import io
    im=Image.open(io.BytesIO(png)).convert('RGB')
    pts=[]
    for y in range(100,min(im.height,650)):
        for x in range(200,min(im.width,1180)):
            r,g,b=im.getpixel((x,y))
            if 14<=r<=32 and 94<=g<=120 and 58<=b<=88: pts.append((x,y))
    if len(pts)<20: raise RuntimeError(f'cannot locate visible green action button; matching pixels={len(pts)}')
    # Cluster the same green CSS fill by row bands; choose the widest compact run.
    rows={}
    for x,y in pts: rows.setdefault(y,[]).append(x)
    bands=[];active=[]
    for y in sorted(rows):
        if not active or y<=active[-1][0]+2: active.append((y,rows[y]))
        else: bands.append(active);active=[(y,rows[y])]
    if active: bands.append(active)
    candidates=[]
    for band in bands:
        xs=[x for _,v in band for x in v];ys=[y for y,v in band for _ in v]
        x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys)
        if x1-x0>=35 and y1-y0>=12: candidates.append((len(xs),x0,x1,y0,y1))
    if len(candidates)!=1: raise RuntimeError(f'expected exactly one in-page green button, found {candidates}')
    _,x0,x1,y0,y1=candidates[0]
    return {'x':(x0+x1)//2,'y':(y0+y1)//2,'bbox':[x0,y0,x1,y1],'pixels':candidates[0][0]}
def main():
    global CURRENT_DESK
    preflight();runid='pay1-ui-gate-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    out=ART/runid;out.mkdir(parents=True,exist_ok=False);(out/'overlays').mkdir()
    ledger=out/'resource-events.jsonl';os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),'OSWORLD_V2_DIR':str(OSWORLD)})
    os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None);identity=ensure_resource_identity(ledger)
    log=base.EventLog();ep=d=None;started=time.monotonic();report={'run_id':runid,'model_called':False,'api_called':False,'purpose':'real Desktop MCP UI control and submit action-gate validation only','task_id':fx.TASK_ID,'task_version':fx.TASK_VERSION}
    try:
        ep,d=base.make_desktop('pay1-ui-gate-smoke',log,out/'shared',require_a11y_tree=False);CURRENT_DESK=d
        server=app.server_text(fx.SOURCE_FIXTURE_SHA256)
        smoke.write_guest(ep,app.SERVER_PATH,server,'pay1_app_install')
        start='nohup /usr/bin/python3 '+shlex.quote(app.SERVER_PATH)+' --state '+shlex.quote(app.STATE_PATH)+' --port '+str(app.PORT)+' >/tmp/codesk-pay1-ui-gate.log 2>&1 </dev/null & echo $! >/tmp/codesk-pay1-ui-gate.pid'
        ep.cli_action('pay1_app_start','bash -lc '+shlex.quote(start))
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                health=guest(d,['curl','--noproxy','*','-fsS','--max-time','2',f'http://127.0.0.1:{app.PORT}/health'],5)
                if '"ok"' in health: break
            except Exception: time.sleep(.25)
        else: raise RuntimeError('Guest app health timeout')
        browser=guest(d,['bash','-lc','command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE'],10).strip().splitlines()[-1]
        if browser=='NONE': raise RuntimeError('Chromium unavailable')
        profile='/tmp/codesk-pay1-ui-gate/chrome-'+runid
        # Last URL is active: clerk; the previous tab remains a real supervisor page.
        urls=shlex.quote(app.ROUTES['supervisor'])+' '+shlex.quote(app.ROUTES['clerk'])
        launch='nohup '+shlex.quote(browser)+' --no-sandbox --start-maximized --no-first-run --no-default-browser-check --disable-dev-shm-usage --disable-extensions --disable-background-networking --no-proxy-server --remote-debugging-port=9222 --user-data-dir='+shlex.quote(profile)+' --new-window '+urls+' >/tmp/codesk-pay1-ui-browser.log 2>&1 </dev/null & echo $! >/tmp/codesk-pay1-ui-browser.pid'
        ep.cli_action('pay1_browser_start','bash -lc '+shlex.quote(launch))
        tabs=[];title='';deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try: tabs=json.loads(guest(d,['curl','--noproxy','*','-fsS','http://127.0.0.1:9222/json/list'],5));title=guest(d,['bash','-lc','wid=$(xdotool getactivewindow 2>/dev/null||true);xdotool getwindowname "$wid" 2>/dev/null||true'],5).strip()
            except Exception: time.sleep(.25);continue
            urls_now={x.get('url') for x in tabs if x.get('type')=='page'}
            if all(app.ROUTES[x] in urls_now for x in ('clerk','supervisor')) and 'Payroll Close Desk' in title: break
            time.sleep(.25)
        else: raise RuntimeError('both intended payroll role tabs did not load')
        report.update({'health':health,'browser':browser,'window_title':title,'loaded_page_urls':sorted(x.get('url','') for x in tabs if x.get('type')=='page')})
        # Chromium activates the first URL from this command line; switch to the second (clerk) tab for A.
        a_switch=mcp_call('key',{'keys':'ctrl+tab'},out,runid,'A',runid+'-A-select-clerk');save_shot(out,'A-select-clerk.png',a_switch['png'])
        a_shot=mcp_call('screenshot',{},out,runid,'A',runid+'-A-initial');save_shot(out,'A-clerk-initial.png',a_shot['png'])
        a_button=green_button_center(a_shot['png']);report['submit_button']=a_button
        # B switches to the already loaded supervisor tab and uses the visible action button.
        b_obs=mcp_call('key',{'keys':'ctrl+shift+tab'},out,runid,'B',runid+'-B-open-supervisor');save_shot(out,'B-supervisor.png',b_obs['png'])
        b_button=green_button_center(b_obs['png']);report['correction_button']=b_button
        b_click=mcp_call('click',{'x':b_button['x'],'y':b_button['y']},out,runid,'B',runid+'-B-correction-click');save_shot(out,'B-after-correction.png',b_click['png'])
        after_b=state(d);report['state_after_B_click']=after_b
        if after_b['timecard']['approved_hours_tenths']!=60 or len(after_b['payment_lines']): raise RuntimeError('visible B correction click did not produce expected state: '+json.dumps({'approved_hours':after_b['timecard']['approved_hours_tenths'],'payment_lines':len(after_b['payment_lines'])}))
        # Return A to its tab; a live register refreshes to 6h while the already initialized batch input remains 8h.
        a_resume=mcp_call('key',{'keys':'ctrl+tab'},out,runid,'A',runid+'-A-resume');save_shot(out,'A-after-B-before-submit.png',a_resume['png'])
        stale_button=green_button_center(a_resume['png']);report['submit_button_after_B']=stale_button
        cfg=out/'protocol_gate'/'gate-config.json';signal=out/'protocol_gate'/'submit';signal.mkdir(parents=True,exist_ok=True)
        cfg.parent.mkdir(parents=True,exist_ok=True)
        cfg.write_text(json.dumps({'gate_id':runid+'-submit','actor_id':'A','tool':'click','argument':'x','contains':str(stale_button['x']),'signal_dir':str(signal),'timeout_seconds':120},indent=2)+'\n')
        env,action_log=_env(out,runid,'A',runid+'-A-submit-pending',cfg)
        proc=subprocess.Popen([MCP_PYTHON,'-m','oscombo.desktop_tools','click',json.dumps({'x':stale_button['x'],'y':stale_button['y']})],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        pending_path=signal/'pending.json';deadline=time.monotonic()+30
        while time.monotonic()<deadline and not pending_path.exists() and proc.poll() is None: time.sleep(.1)
        if not pending_path.exists():
            stdout,stderr=proc.communicate(timeout=5);raise RuntimeError('submit MCP click did not reach configured gate: '+stderr[-500:]+' '+stdout[-500:])
        pending=json.loads(pending_path.read_text());before_release=state(d)
        report['pending_click']=pending;report['state_at_gate']=before_release
        (signal/'release.json').write_text(json.dumps({'gate_id':runid+'-submit','reason':'scripted UI control releases exact visible Add line click after B correction'})+'\n')
        stdout,stderr=proc.communicate(timeout=90)
        if proc.returncode: raise RuntimeError('gated submit MCP failed: '+stderr[-800:])
        result=json.loads(stdout)
        if result.get('error'): raise RuntimeError('gated submit MCP returned error: '+str(result['error']))
        shot=base64.b64decode(result['image']) if result.get('image') else None
        if shot: save_shot(out,'A-after-submit.png',shot)
        final=state(d);shared=fx.evaluate_shared(final)
        rows=final.get('payment_lines',[])
        proof={'B_correction_happened_before_A_submit':before_release['timecard']['approved_hours_tenths']==60 and not before_release['payment_lines'],
          'gate_actor_episode_and_button_exact':pending.get('actor_id')=='A' and pending.get('episode_id')==runid+'-A-submit-pending' and pending.get('tool')=='click' and pending.get('args')=={'x':stale_button['x'],'y':stale_button['y']},
          'submitted_payment_preserved_form_snapshot':len(rows)==1 and rows[0]['hours_tenths']==80 and rows[0]['approved_hours_at_submit']==60 and rows[0]['ui_observed_hours_tenths']==60,
          'shared_oracle_A_fails_B_passes':not shared['A']['success'] and shared['B']['success']}
        report.update({'state_after_submit':final,'shared_oracle':shared,'scripted_ui_mechanism_control':proof,'mcp_action_log':str(action_log.relative_to(out)),'status':'ui_control_pass' if all(proof.values()) else 'ui_control_failed'})
        smoke.post(d,'/api/reset',{})
        reset=state(d);report['reset']={'approved_hours_tenths':reset['timecard']['approved_hours_tenths'],'payment_lines':len(reset['payment_lines']),'audit_log':len(reset['audit_log'])}
        if report['reset']!={'approved_hours_tenths':80,'payment_lines':0,'audit_log':0}: report['status']='ui_control_failed'
    except Exception as exc:
        report.update({'status':'invalid','error':{'type':type(exc).__name__,'message':str(exc)}})
        raise
    finally:
        if ep:
            try:ep.copy_artifacts(out/'guest-artifacts')
            except Exception as exc:report['artifact_error']=str(exc)
            try:ep.close()
            except Exception as exc:report['close_error']=str(exc)
        try:log.write(out/'events.jsonl')
        except Exception as exc:report['event_log_error']=str(exc)
        report['wall_seconds']=round(time.monotonic()-started,2)
        report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
        report['provenance']={'resource_run_id':identity.run_id,'source_commit':base.git_source_state(),'app_sha256':hashlib.sha256(app.server_text(fx.SOURCE_FIXTURE_SHA256).encode()).hexdigest(),'guest_image':str(IMAGE)}
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'out':str(out),'status':report.get('status'),'wall_seconds':report['wall_seconds'],'proof':report.get('scripted_ui_mechanism_control'),'reset':report.get('reset'),'lifecycle':report.get('resource_lifecycle')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
