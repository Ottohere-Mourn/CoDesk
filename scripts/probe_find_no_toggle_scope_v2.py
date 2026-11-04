#!/usr/bin/env python3
"""No-model same-session no-toggle negative and second-Writer-window scope controls."""
from __future__ import annotations
import base64, json, os, secrets, shlex, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
sys.path[:0]=[str(ROOT),str(OSWORLD)]
os.environ.setdefault('OSWORLD_V2_DIR',str(OSWORLD))
from scripts import run_writer_calc_v1 as base
from scripts import probe_find_matchcase_persistence_v1 as helper
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
RUN=os.environ.get('SWCUB_FIND_CONTROL_RUN_ID','find-matchcase-negative-scope-controls-20261104-02')
PARENT=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs')
OUT=PARENT/RUN
def put(p,v): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def main():
    if OUT.exists(): raise RuntimeError('artifact directory already exists')
    if not OUT.is_relative_to(Path('/mnt/raid1')): raise RuntimeError('artifact path safety violation')
    if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip(): raise RuntimeError('active containers; refusing')
    if shutil.disk_usage('/').free<20*1024**3 or shutil.disk_usage('/mnt/raid1').free<100*1024**3: raise RuntimeError('disk safety floor failed')
    OUT.mkdir(parents=True); (OUT/'overlays').mkdir()
    ledger=OUT/'resource-events.jsonl'
    os.environ.update({'SWCUB_RUN_ID':RUN,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(OUT/'overlays')})
    os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
    ensure_resource_identity(ledger)
    log=EventLog(); ep=desk=ctx=None
    report={'run_id':RUN,'case_id':'CODESK-NEXT-FIND-001','task_version':'0.1.0-no-toggle-scope-controls','model_used':False,'qwen_called':False,'status':'starting','purpose':'same-Guest no-toggle negative control and second Writer window option-scope probe'}
    started=time.monotonic()
    try:
        runtime='swcub/osworld-v2.1-qemu-runtime:local'
        os.environ['SWCUB_OSWORLD_GUEST_IMAGE']=str(base.resolve_guest_image_path())
        os.environ['SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime
        os.environ['OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime
        os.environ['SWCUB_OSWORLD_CACHE_DIR']=str(PARENT/'osworld-cache')
        report['runtime_image_id']=subprocess.run(['docker','image','inspect',runtime,'--format','{{.Id}}'],capture_output=True,text=True,check=True,timeout=15).stdout.strip()
        ep,desk=base.make_desktop('find_no_toggle',log,OUT,require_a11y_tree=True)
        ctx=ActorContext('scripted_control',ep,'gui'); ctx._find_desktop=desk
        payload=base64.b64encode(base.render_writer_fodt(helper.DOC)).decode('ascii')
        code='from pathlib import Path;import base64;p=Path('+repr(base.WRITER_PATH)+');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode('+repr(payload)+'))'
        base.guest_command(desk,['python3','-c',code],timeout=30)
        launch='nohup soffice --nologo --norestore --nofirststartwizard --writer '+shlex.quote(base.WRITER_PATH)+' >/tmp/codesk-find-negative.log 2>&1 </dev/null & sleep 7'
        base.guest_command(desk,['bash','-lc',launch],timeout=20)
        report['readiness']=base.wait_for_app_document(ep,desk,'writer',base.WRITER_PATH,OUT/'readiness',timeout=240)
        report['initial_text']=helper.read_text(desk)
        original_window=helper.active(desk); report['original_window']=original_window
        before=helper.open_dialog(ctx,ep,OUT,'no-toggle-before-b')
        report['no_toggle_before_b']=before
        if before['match_case'] is not False: raise RuntimeError('clean Writer did not start with Match case off')
        ctx.press_key('esc'); time.sleep(.4)
        helper.open_dialog(ctx,ep,OUT,'no-toggle-b-dialog')
        b_action=helper.fill_and_replace(ctx,ep,OUT,'no-toggle-b-replace','DRAFT','REVIEW')
        b_text=helper.read_text(desk)
        expected_b='\n'.join([*helper.DOC[:4],'Archive code: REVIEW | retained for exact-case review.'])
        report['b_without_toggle']={'action':b_action,'exact_text':b_text,'expected_text':expected_b,'exact_task':b_text==expected_b}
        if not report['b_without_toggle']['exact_task']: raise RuntimeError('B no-toggle task did not complete')
        after_b=helper.open_dialog(ctx,ep,OUT,'no-toggle-after-b')
        report['no_toggle_after_b']=after_b
        if after_b['match_case'] is not False: raise RuntimeError('no-toggle B unexpectedly changed Match case')
        ctx.press_key('esc'); time.sleep(.3)
        helper.open_dialog(ctx,ep,OUT,'no-toggle-a-dialog')
        a_action=helper.fill_and_replace(ctx,ep,OUT,'no-toggle-a-replace','pending','approved')
        no_toggle_text=helper.read_text(desk)
        expected=['Release readiness report | controlled terminology','Status A: approved | owner review complete.','Status B: approved | owner review complete.','Status C: approved | owner review complete.','Archive code: REVIEW | retained for exact-case review.']
        report['no_toggle_negative']={'action':a_action,'exact_text':no_toggle_text,'expected_text':'\n'.join(expected),'pass':no_toggle_text.splitlines()==expected,'same_writer_xid':original_window['xid']==helper.active(desk)['xid']}
        if not report['no_toggle_negative']['pass']: raise RuntimeError('same-session no-toggle negative oracle failed')
        helper.open_dialog(ctx,ep,OUT,'scope-original-before-toggle')
        after_toggle=helper.toggle_match(ctx,ep,OUT,'scope-original',True)
        report['scope_toggle_in_original_window']=after_toggle
        ctx.press_key('esc'); time.sleep(.4)
        second_path='/tmp/codesk-find-second-window.fodt'
        second=base64.b64encode(base.render_writer_fodt(['Second Writer window scope probe'])).decode('ascii')
        second_code='from pathlib import Path;import base64;p=Path('+repr(second_path)+');p.write_bytes(base64.b64decode('+repr(second)+'))'
        base.guest_command(desk,['python3','-c',second_code],timeout=30)
        base.guest_command(desk,['bash','-lc','nohup soffice --nologo --norestore --nofirststartwizard --writer '+shlex.quote(second_path)+' >/tmp/codesk-find-second-window.log 2>&1 </dev/null & sleep 6'],timeout=20)
        second_before=helper.active(desk); report['second_window_before_dialog']=second_before
        ctx.execute_gui_action("pyautogui.hotkey('ctrl','h')"); time.sleep(1.5)
        second_state=helper.capture(ep,OUT,'scope-second-window-dialog')
        report['second_window_scope']={'same_profile_different_xid':bool(second_before['xid'] and second_before['xid']!=original_window['xid']),'window':second_before,'match_case':second_state['match_case'],'checkbox_state':second_state}
        ctx.press_key('esc'); time.sleep(.3); ctx.execute_gui_action("pyautogui.hotkey('ctrl','w')"); time.sleep(2)
        returned=helper.active(desk); report['returned_to_original_window']=returned
        report['scope_returned_to_original_xid']=returned['xid']==original_window['xid']
        report['status']='completed'
    except Exception as exc:
        report.update({'status':'probe_error','error':{'type':type(exc).__name__,'message':str(exc)}})
    finally:
        if ep:
            try: ep.copy_artifacts(OUT/'guest-artifacts'/'find_no_toggle')
            except Exception: pass
            try: ep.close()
            except Exception as exc: report.setdefault('close_errors',[]).append(type(exc).__name__)
        report['wall_seconds']=round(time.monotonic()-started,2)
        report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
        report['reset_success']=bool(report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record'))
        put(OUT/'report.json',report)
    print(json.dumps({'run_id':RUN,'status':report.get('status'),'no_toggle_pass':report.get('no_toggle_negative',{}).get('pass'),'match_case_before_after_b':[report.get('no_toggle_before_b',{}).get('match_case'),report.get('no_toggle_after_b',{}).get('match_case')],'second_window_match_case':report.get('second_window_scope',{}).get('match_case'),'same_xid_confirmed':report.get('second_window_scope',{}).get('same_profile_different_xid'),'returned_original':report.get('scope_returned_to_original_xid'),'wall_seconds':report.get('wall_seconds'),'reset_success':report.get('reset_success'),'error':report.get('error'),'artifact_dir':str(OUT)},ensure_ascii=False))
if __name__=='__main__': main()
