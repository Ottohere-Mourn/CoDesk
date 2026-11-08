#!/usr/bin/env python3
"""No-model production GUI MCP control for CRM-LU1 full-form stale-write semantics."""
import json,os,secrets,shlex,sys,time,subprocess
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
os.environ.setdefault('OSWORLD_V2_DIR',str(OSWORLD))
from scripts import run_crm_lu1_hybrid_v2 as task
from scripts import run_writer_calc_v1 as base
from scripts import probe_calcmode1_menu_v1 as gui
from scripts import crm_lu1_fixture_v1 as fx
from swcub.resource_safety import ensure_resource_identity

def main():
    root=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/crm-lu1-guest-controls')
    runid='crm-lu1-gui-semantic-control-20261108-05';out=root/runid
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    ledger=out/'resource-events.jsonl'
    os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),
      'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),
      'OSWORLD_V2_DIR':str(OSWORLD),'SWCUB_OSWORLD_CACHE_DIR':str(root/'osworld-cache')})
    os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
    ident=ensure_resource_identity(ledger)
    log=base.EventLog();ep=d=None;result={'run_id':runid,'control':'B saves, A stale full-form saves, reload/re-save recovery','checks':{}}
    def call(tool,args,label):
        return gui.mcp(ep,d,out,tool,args,label,locked=False)
    try:
        if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip():raise RuntimeError('active Docker Guest')
        ep,d=base.make_desktop('crm-lu1-scripted',log,out/'guest-artifacts',require_a11y_tree=False)
        d.guest_key='crm-lu1-scripted'
        setup=task._setup_guest('crm-lu1-scripted',ep,d,out,runid,log)
        time.sleep(8)
        call('screenshot',{},'initial-ready')
        result['setup']=setup
        result['initial']=task._read_state(d)
        # Actor B switches to its own normal CRM section, edits and saves.
        call('click',{'x':480,'y':285},'B-select-billing-tab')
        call('click',{'x':600,'y':442},'B-focus-billing')
        call('key',{'keys':'ctrl+a'},'B-select-billing')
        call('type_text',{'text':'ap@northwind.example'},'B-enter-email')
        call('click',{'x':395,'y':470},'B-save')
        time.sleep(1)
        after_b=task._read_state(d)
        result['after_B']=after_b
        result['checks']['B_owner_update_passes']=fx.actor_success(after_b,'B')
        # No browser refresh: A's separate form remains loaded with billing-old.
        call('click',{'x':380,'y':285},'A-select-renewal-tab')
        call('click',{'x':600,'y':442},'A-focus-renewal')
        call('key',{'keys':'ctrl+a'},'A-select-renewal')
        call('type_text',{'text':'Jordan Lee'},'A-enter-contact')
        call('click',{'x':395,'y':470},'A-save-stale')
        time.sleep(1)
        after_a=task._read_state(d)
        result['after_A_stale_save']=after_a
        result['checks']['A_owner_update_passes']=fx.actor_success(after_a,'A')
        result['checks']['B_field_lost']=not fx.actor_success(after_a,'B')
        result['checks']['exact_lost_update_signature']=fx.lost_update_signature(after_a)
        # Standard recovery: reload the latest profile; B re-applies its source value.
        call('key',{'keys':'ctrl+r'},'reload-current-record')
        time.sleep(2)
        call('click',{'x':480,'y':285},'B-select-billing-for-recovery')
        call('click',{'x':600,'y':442},'B-focus-billing-for-recovery')
        call('key',{'keys':'ctrl+a'},'B-select-recovery-value')
        call('type_text',{'text':'ap@northwind.example'},'B-reenter-authorized-email')
        call('click',{'x':395,'y':470},'B-resave-after-reload')
        time.sleep(1)
        recovered=task._read_state(d)
        result['after_recovery']=recovered
        result['checks']['normal_recovery_joint_pass']=fx.joint_success(recovered)
        result['checks']['audit_preserves_overwrite_and_recovery']=len(recovered.get('events',[]))==3 and fx.lost_update_signature({'events':recovered['events'][:2]})
        result['control_pass']=all(result['checks'].values())
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        result['control_pass']=False
    finally:
        if ep is not None:
            try:ep.copy_artifacts(out/'guest-artifacts')
            except Exception as exc:result.setdefault('cleanup_errors',[]).append('copy: '+str(exc))
            try:ep.close()
            except Exception as exc:result.setdefault('cleanup_errors',[]).append('close: '+str(exc))
        try:
            result['resource_lifecycle']=base.verify_ledger(ledger)
            result['reset_success']=bool(result['resource_lifecycle'].get('all_containers_have_destroy_record'))
        except Exception as exc:
            result['reset_success']=False;result['cleanup_errors']=result.get('cleanup_errors',[])+['ledger: '+str(exc)]
        (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()

