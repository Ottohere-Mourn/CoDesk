#!/usr/bin/env python3
"""No-model DATA-REL1 Guest GUI/CLI control smoke; never calls a model endpoint."""
from __future__ import annotations
import base64, hashlib, json, os, secrets, shlex, subprocess, sys, time, uuid
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
ART=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/data-rel1-guest-smoke-v1')
sys.path.insert(0,str(ROOT))
from scripts import data_rel1_fixture_v1 as fx
from scripts import data_rel1_app_v1 as app
from scripts import run_pay1_timesheet_hybrid_v1 as pay1
from scripts import run_writer_calc_v1 as harness

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def api_get(d,path):
    return json.loads(harness.guest_command(d,['curl','--noproxy','*','-fsS','--max-time','4',f'http://127.0.0.1:{app.PORT}{path}'],timeout=8))
def api_post(d,path,obj):
    body=json.dumps(obj,separators=(',',':'))
    cmd=f"curl --noproxy '*' -fsS --max-time 4 -X POST -H 'Content-Type: application/json' --data {shlex.quote(body)} http://127.0.0.1:{app.PORT}{path}"
    return json.loads(harness.guest_command(d,['bash','-lc',cmd],timeout=8))
def main():
    pay1.preflight(require_key=False)
    ART.mkdir(parents=True,exist_ok=True)
    runid='data-rel1-guest-smoke-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    out=ART/runid;out.mkdir(parents=True,exist_ok=False)
    for name in ('setup','guest-artifacts'): (out/name).mkdir(parents=True,exist_ok=True)
    ledger,identity=pay1._env(out,runid)
    log=harness.EventLog();ep=d=None;report={'run_id':runid,'task_id':fx.TASK_ID,'task_version':fx.TASK_VERSION,
        'mode':'no-model Guest GUI/CLI control smoke','model_called':False,'api_called':False,
        'model_endpoint':None,'condition':'single_guest_scripted_controls',
        'external_release_enabled':False,'external_network_used':'not instrumented; app routes are loopback-only and contain no external service calls'}
    error=None
    try:
        ep,d=harness.make_desktop('data_rel1_smoke',log,out/'guest',require_a11y_tree=False);d.guest_key='data_rel1_smoke'
        report['guest_container_id']=ep.snapshot().get('guest_container_id')
        guest_dir='/tmp/codesk-data-rel1'
        files={'data_rel1_fixture_v1.py':(ROOT/'scripts/data_rel1_fixture_v1.py').read_bytes(),
               'data_rel1_app_v1.py':(ROOT/'scripts/data_rel1_app_v1.py').read_bytes()}
        payload={name:base64.b64encode(content).decode('ascii') for name,content in files.items()}
        code=('from pathlib import Path;import base64;d=Path('+repr(guest_dir)+');d.mkdir(parents=True,exist_ok=True);'
              'files='+repr(payload)+';[(d/k).write_bytes(base64.b64decode(v)) for k,v in files.items()]')
        ep.cli_action('data_rel1_guest_install','python3 -c '+shlex.quote(code))
        cmd='nohup env PYTHONPATH='+shlex.quote(guest_dir)+' /usr/bin/python3 '+shlex.quote(guest_dir+'/data_rel1_app_v1.py')+' --state /tmp/codesk-data-rel1/state.json --port '+str(app.PORT)+' >/tmp/codesk-data-rel1-server.log 2>&1 </dev/null & echo $! >/tmp/codesk-data-rel1-server.pid'
        ep.cli_action('data_rel1_guest_start','bash -lc '+shlex.quote(cmd))
        deadline=time.monotonic()+20;health=''
        while time.monotonic()<deadline:
            try:
                health=harness.guest_command(d,['curl','--noproxy','*','-fsS','--max-time','2',f'http://127.0.0.1:{app.PORT}/health'],timeout=5)
                if '"ok": true' in health or '"ok":true' in health:break
            except Exception:time.sleep(.3)
        if '"ok"' not in health:raise RuntimeError('Guest-local DATA-REL1 app did not become healthy: '+health[:300])
        browser=harness.guest_command(d,['bash','-lc','command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE'],timeout=8).strip().splitlines()[-1]
        if browser=='NONE':raise RuntimeError('Chromium not found in pinned Guest')
        launch=('nohup '+shlex.quote(browser)+' --no-sandbox --start-maximized --no-first-run --no-default-browser-check '
                '--disable-extensions --disable-background-networking --disable-dev-shm-usage --no-proxy-server '
                '--remote-debugging-port=9222 --user-data-dir=/tmp/codesk-data-rel1/chrome --new-window '+shlex.quote(app.ROUTES['exporter'])+
                ' >/tmp/codesk-data-rel1-chrome.log 2>&1 </dev/null & echo $! >/tmp/codesk-data-rel1-chrome.pid')
        ep.cli_action('data_rel1_browser_start','bash -lc '+shlex.quote(launch))
        tabs=[];deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            try:
                tabs=json.loads(harness.guest_command(d,['curl','--noproxy','*','-fsS','--max-time','2','http://127.0.0.1:9222/json/list'],timeout=5))
                if any(t.get('type')=='page' and t.get('url')==app.ROUTES['exporter'] and t.get('title')=='Study Export Workbench' for t in tabs):break
            except Exception:time.sleep(.5);continue
            time.sleep(.5)
        page=next((t for t in tabs if t.get('type')=='page' and t.get('url')==app.ROUTES['exporter']),None)
        if not page or page.get('title')!='Study Export Workbench':
            diag=harness.guest_command(d,['bash','-lc',"ps -ef | grep -E '[c]hrome|[g]oogle-chrome'; tail -30 /tmp/codesk-data-rel1-chrome.log 2>/dev/null"],timeout=8)
            raise RuntimeError('Chrome did not render exporter title; tabs='+json.dumps(tabs)+' diagnostics='+diag[-1200:])
        time.sleep(3)
        obs=ep.refresh_observation(source='data_rel1_exporter_page_ready')
        shot=obs.get('screenshot') if isinstance(obs,dict) else None
        if not isinstance(shot,bytes) or len(shot)<1000:raise RuntimeError('Guest screenshot unavailable or too small')
        shot_path=out/'setup'/'exporter-page.png';shot_path.write_bytes(shot)
        from PIL import Image
        import io
        im=Image.open(io.BytesIO(shot)).convert('RGB')
        crop=im.crop((min(80,im.width-1),min(60,im.height-1),im.width,min(220,im.height)))
        app_header_pixels=sum(1 for r,g,b in crop.getdata() if r<65 and 45<=g<=90 and 70<=b<=130)
        if app_header_pixels<1000:raise RuntimeError(f'Guest screenshot does not visibly render the DATA-REL1 header (matching pixels={app_header_pixels}, size={im.size}); saved {shot_path}')
        win=harness.guest_command(d,['bash','-lc','wid=$(xdotool getactivewindow 2>/dev/null || true); xdotool getwindowname \"$wid\" 2>/dev/null || true'],timeout=8).strip()
        if 'Study Export Workbench' not in win:raise RuntimeError('browser window title does not show the Guest app: '+win)
        html=harness.guest_command(d,['curl','--noproxy','*','-fsS',app.ROUTES['exporter']],timeout=8)
        if 'Every unreleased package must match the current protocol scope' not in html or 'External release is disabled' not in html:
            raise RuntimeError('visible policy/external-release guard missing from GUI page')
        # Use only the restricted Guest CLI bridge to exercise the same Guest-local app state.
        initial=api_get(d,'/api/state')
        made=api_post(d,'/api/build',{'actor':'A'});after_a=api_get(d,'/api/state')
        a_pre=fx.evaluate_actor(after_a,'A')
        amendment=api_post(d,'/api/amendment',{'actor':'B'});after_b=api_get(d,'/api/state')
        a_stale=fx.evaluate_actor(after_b,'A');b_ok=fx.evaluate_actor(after_b,'B')
        recovery=api_post(d,'/api/revoke',{'actor':'A','package_id':made['package_id']})
        rebuilt=api_post(d,'/api/build',{'actor':'A'});after_recovery=api_get(d,'/api/state')
        recovered=fx.evaluate_episode({'A':after_recovery,'B':after_recovery})
        reset=api_post(d,'/api/reset',{})
        final=api_get(d,'/api/state')
        reset_ok=bool(reset.get('ok') and final['policy_version']==1 and not final['packages'] and not final['exclusions'] and not final['audit_log'])
        report.update({'app_health':json.loads(health),'browser_binary':browser,
          'visible_screenshot':str(shot_path.relative_to(out)),'active_window_title':win,'browser_tabs':tabs,
          'initial_workspace':initial,'package_build':made,'A_before_B':a_pre,
          'policy_amendment':amendment,'after_B':{'A':a_stale,'B':b_ok},
          'recovery':{'revoke':recovery,'rebuild':rebuilt,'evaluation':recovered},
          'reset_check':{'response':reset,'empty_initial_workspace_restored':reset_ok,'state':final},
          'control_summary':{'initial_A_pass':bool(a_pre.get('success')),
             'Shared_style_A_stale_fail':not bool(a_stale.get('success')),
             'B_amendment_pass':bool(b_ok.get('success')),
             'recover_both_pass':bool(recovered.get('success')),'reset_pass':reset_ok},
          'guest_tool_access':'setup/action commands ran inside OSWorld Guest through existing ActorContext CLI bridge; no host shell passed to model',
          'gui_page_policy_visible':True,'gui_header_color_pixels':app_header_pixels,'external_release_endpoint':'absent','external_network_traffic_audited':False})
        report['valid_smoke']=all(report['control_summary'].values())
        report['status']='completed' if report['valid_smoke'] else 'control_failure'
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc)};report.update({'status':'invalid_guest_smoke','valid_smoke':False,'error':error})
    finally:
        if ep is not None:
            try:ep.copy_artifacts(out/'guest-artifacts')
            except Exception as exc:report.setdefault('cleanup_errors',[]).append('artifact capture: '+str(exc))
            try:ep.close()
            except Exception as exc:report.setdefault('cleanup_errors',[]).append('guest close: '+str(exc))
        try:log.write(out/'events.jsonl')
        except Exception as exc:report.setdefault('cleanup_errors',[]).append('event log: '+str(exc))
        try:report['resource_lifecycle']=harness.verify_ledger(ledger) if ledger.exists() else None
        except Exception as exc:report.setdefault('cleanup_errors',[]).append('resource ledger verification: '+str(exc))
        write_json(out/'report.json',report)
    print(json.dumps({'out':str(out),'status':report.get('status'),'valid_smoke':report.get('valid_smoke'),
       'control_summary':report.get('control_summary'),'model_called':report.get('model_called'),
       'cleanup_errors':report.get('cleanup_errors',[]),'error':report.get('error')},ensure_ascii=False,indent=2))
    if report.get('status')!='completed':raise SystemExit(1)
if __name__=='__main__':main()
