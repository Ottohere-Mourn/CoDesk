#!/usr/bin/env python3
from __future__ import annotations
import base64,hashlib,json,os,secrets,shlex,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
IMAGE=Path('/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2')
RUNTIME='swcub/osworld-v2.1-qemu-runtime:local'
ART=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/calcmode1-controls')
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
for k,v in {'OSWORLD_V2_DIR':str(OSWORLD),'SWCUB_OSWORLD_GUEST_IMAGE':str(IMAGE),'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME,'OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME}.items(): os.environ.setdefault(k,v)
from scripts import run_writer_calc_v1 as base
from oscombo.harness.hybrid_v2 import MCP_PYTHON,MCP_SITE
from swcub.core import EventLog
from swcub.resource_safety import ensure_resource_identity
from swcub.task_factory import render_calc_fods
GUEST_FILE='/tmp/codesk-calcmode1/Quote-2042.fods'
GRID=[['Quote ID','Q-SYN-2042'],['Units','10'],['Unit Rate Cents','8000'],['Margin Basis Points','1500'],['Quoted Total Cents','']]
def preflight():
    if __import__('shutil').disk_usage('/').free<20*1024**3: raise RuntimeError('root free below 20 GiB')
    if __import__('shutil').disk_usage('/mnt/raid1').free<100*1024**3: raise RuntimeError('RAID1 free below 100 GiB')
    if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,timeout=20,check=True).stdout.strip(): raise RuntimeError('active Docker guest/container')
    if not IMAGE.is_file() or subprocess.run(['docker','image','inspect',RUNTIME],capture_output=True,timeout=20).returncode: raise RuntimeError('pinned image/runtime missing; no pull')
def guest(d,argv,timeout=35): return base.guest_command(d,argv,timeout=timeout)
def write_guest(ep,content):
    payload=base64.b64encode(content).decode()
    code='from pathlib import Path;import base64;p=Path('+repr(GUEST_FILE)+');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode('+repr(payload)+'))'
    ep.cli_action('calcmode_fixture_write','python3 -c '+shlex.quote(code))
def mcp(ep,d,out,tool,args,label,locked=False):
    log=out/'desktop_mcp'/'actions.jsonl';log.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update({'OSCOMBO_GUEST_URL':f'http://{d.vm_ip}:{d.server_port}','OSCOMBO_ACTION_LOG':str(log),'OSCOMBO_MAX_STEPS':'30','OSCOMBO_ACTOR_ID':'probe','OSCOMBO_EPISODE_ID':label,'OSCOMBO_GUEST_KEY':'calcmode1','OSCOMBO_CONDITION':os.environ.get('CALCMODE_CONDITION','collaborative_shared'),'PYTHONPATH':os.pathsep.join(x for x in (MCP_SITE,str(HYBRID),str(ROOT),str(OSWORLD),os.environ.get('PYTHONPATH','')) if x)})
    if locked or os.environ.get('CALCMODE_LOCKED')=='1': env['OSCOMBO_ACTION_LOCK_FILE']=str(out/'locks'/'guest-actions.lock')
    else: env.pop('OSCOMBO_ACTION_LOCK_FILE',None)
    cp=subprocess.run([MCP_PYTHON,'-m','oscombo.desktop_tools',tool,json.dumps(args)],env=env,capture_output=True,text=True,timeout=90)
    if cp.returncode: raise RuntimeError(f'{tool} MCP returned {cp.returncode}: {cp.stderr[-700:]}')
    result=json.loads(cp.stdout)
    if result.get('error'): raise RuntimeError(f'{tool} error: {result["error"]}')
    if result.get('image'):
        target=out/'screenshots'/f'{label}-{tool}.png';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(base64.b64decode(result['image']))
    return {'tool':tool,'args':args,'text':str(result.get('text',''))[:300]}
def set_cell(ep,d,out,row,col,value,label):
    mcp(ep,d,out,'key',{'keys':'ctrl+home'},label+'-home')
    for _ in range(row): mcp(ep,d,out,'key',{'keys':'down'},label+'-down')
    for _ in range(col): mcp(ep,d,out,'key',{'keys':'right'},label+'-right')
    mcp(ep,d,out,'type_text',{'text':str(value)},label+'-type')
    mcp(ep,d,out,'key',{'keys':'enter'},label+'-enter')
def read_grid(d):
    raw=guest(d,['cat',GUEST_FILE],25)
    rows=base.GuestLibreOfficeBindingEvaluator._parse_calc(raw)
    return raw,rows
def uno_state(d):
    py=("import json,uno; c=uno.getComponentContext(); r=c.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',c); x=r.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); m=x.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',x); doc=m.getCurrentComponent(); sh=doc.getSheets().getByIndex(0); q=sh.getCellRangeByName('B5'); u=sh.getCellRangeByName('B2'); print(json.dumps({'auto_calculate':doc.isAutomaticCalculationEnabled(),'formula':q.getFormula(),'formula_value':q.getValue(),'units_value':u.getValue(),'document_url':doc.getURL(),'document_title':doc.Title}))")
    raw=guest(d,['python3','-c',py],20).strip().splitlines()[-1]
    return json.loads(raw)
def main():
    role=os.environ.get('CALCMODE_ROLE','shared');locked=os.environ.get('CALCMODE_LOCKED')=='1'
    condition='collaborative_isolated' if role.startswith('ma_id') else 'collaborative_shared_lock' if locked else 'collaborative_shared'
    os.environ['CALCMODE_CONDITION']=condition
    if role not in ('ma_id_a','ma_id_b','shared'): raise ValueError('CALCMODE_ROLE must be ma_id_a, ma_id_b, or shared')
    preflight();runid='calcmode1-'+role+('-lock' if locked else '')+'-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    out=ART/runid;out.mkdir(parents=True,exist_ok=False);(out/'overlays').mkdir()
    ledger=out/'resource-events.jsonl';os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),'OSWORLD_V2_DIR':str(OSWORLD)});os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
    identity=ensure_resource_identity(ledger);event=EventLog();ep=d=None;report={'run_id':runid,'task_id':'CODESK-QUOTE-CALC-MODE-001','task_version':'0.1.0-controls','model_called':False,'api_called':False,'status':'starting'};t=time.monotonic()
    try:
        ep,d=base.make_desktop('calcmode1_probe',event,out/'guest-artifacts')
        d.guest_key='calcmode1'
        content=render_calc_fods(GRID,'Quote-2042');write_guest(ep,content)
        launch="soffice --nologo --norestore --nofirststartwizard --accept='socket,host=localhost,port=2002;urp;StarOffice.ComponentContext' --calc "+shlex.quote(GUEST_FILE)+" >/tmp/codesk-calcmode1-soffice.log 2>&1 </dev/null & sleep 7"
        ep.cli_action('calcmode_soffice_start','bash -lc '+shlex.quote(launch))
        ready=base.wait_for_app_document(ep,d,'calc',GUEST_FILE,out/'readiness',timeout=120)
        set_cell(ep,d,out,4,1,'=B2*B3*(1+B4/10000)','formula')
        mcp(ep,d,out,'key',{'keys':'ctrl+s'},'save-formula');time.sleep(1)
        raw,grid=read_grid(d);initial_uno_state=uno_state(d)
        before=mcp(ep,d,out,'screenshot',{},'before-data-menu')
        role=os.environ.get('CALCMODE_ROLE','shared')
        mode_menu=None;menu_screenshot=None;mode_off=None;raw_stale=None;grid_stale=None;state_stale=None
        raw_recalc=None;grid_recalc=None;state_recalc=None;checks={}
        if role in ('ma_id_b','shared'):
            mode_menu=mcp(ep,d,out,'key',{'keys':'alt+d'},'B-open-data-menu',locked=locked)
            mcp(ep,d,out,'click',{'x':335,'y':219},'B-open-calculate-submenu',locked=locked)
            menu_screenshot=mcp(ep,d,out,'screenshot',{},'B-calculate-menu')
            mcp(ep,d,out,'click',{'x':532,'y':270},'B-toggle-autocalculate-off',locked=locked)
            time.sleep(0.5);mode_off=uno_state(d)
            mcp(ep,d,out,'key',{'keys':'ctrl+s'},'B-save-manual-mode',locked=locked)
            if role=='ma_id_b': raw_stale,grid_stale=read_grid(d);state_stale=uno_state(d)
        if role in ('ma_id_a','shared'):
            set_cell(ep,d,out,1,1,'12','A-update-units')
            mcp(ep,d,out,'key',{'keys':'ctrl+s'},'A-save-updated-units',locked=locked);time.sleep(0.7)
            raw_stale,grid_stale=read_grid(d);state_stale=uno_state(d)
        if role=='shared':
            mcp(ep,d,out,'key',{'keys':'f9'},'A-manual-recalculate',locked=locked)
            mcp(ep,d,out,'key',{'keys':'ctrl+s'},'A-save-recalculated',locked=locked);time.sleep(0.7)
            raw_recalc,grid_recalc=read_grid(d);state_recalc=uno_state(d)
            checks={'visible_menu_toggle_disabled_auto_calc':mode_off['auto_calculate'] is False,
              'input_updated_to_12':grid_stale[1][1]=='12' and state_stale['units_value']==12,
              'formula_stayed_stale_after_input':grid_stale[4][1]=='92000' and state_stale['formula_value']==92000,
              'manual_recalc_recovered_formula':grid_recalc[4][1]=='110400' and abs(float(state_recalc['formula_value'])-110400)<0.01,
              'recovery_left_manual_mode_enabled':state_recalc['auto_calculate'] is False}
        elif role=='ma_id_a':
            checks={'default_auto_calculation_enabled':initial_uno_state['auto_calculate'] is True,
              'input_updated_to_12':grid_stale[1][1]=='12' and state_stale['units_value']==12,
              'automatic_formula_recalculation':grid_stale[4][1]=='110400' and abs(float(state_stale['formula_value'])-110400)<0.01}
        elif role=='ma_id_b':
            checks={'visible_menu_toggle_disabled_auto_calc':mode_off['auto_calculate'] is False,
              'input_values_unchanged':grid_stale==grid,
              'formula_unchanged':state_stale['formula_value']==92000.0 and state_stale['auto_calculate'] is False}
        report.update({'status':'controls_pass' if all(checks.values()) else 'control_mismatch',
          'role':role,'condition':condition,'locked_actions':locked,'readiness':ready,
          'fixture_sha256':hashlib.sha256(content).hexdigest(),'initial_grid':grid,
          'initial_uno_state':initial_uno_state,'initial_fods_sha256':hashlib.sha256(raw.encode()).hexdigest(),
          'data_menu_action':mode_menu,'submenu_screenshot':menu_screenshot,'mode_off_uno_state':mode_off,
          'stale_grid_after_A_update':grid_stale,'stale_uno_state':state_stale,
          'recalculated_grid':grid_recalc,'recalculated_uno_state':state_recalc,'checks':checks,
          'stale_fods_sha256':hashlib.sha256(raw_stale.encode()).hexdigest() if raw_stale else None,
          'recalculated_fods_sha256':hashlib.sha256(raw_recalc.encode()).hexdigest() if raw_recalc else None,
          'screenshots':sorted(str(x.relative_to(out)) for x in (out/'screenshots').glob('*.png')),
          'guest_container_id':ep.snapshot().get('guest_container_id')})
    except Exception as e:
        report.update({'status':'error','error':{'type':type(e).__name__,'message':str(e)}})
        if ep:
            try:ep.copy_artifacts(out/'failure-artifacts')
            except Exception:pass
    finally:
        if ep:
            try:ep.copy_artifacts(out/'guest-artifacts')
            except Exception as e:report.setdefault('cleanup_errors',[]).append(str(e))
            try:ep.close()
            except Exception as e:report.setdefault('cleanup_errors',[]).append(str(e))
        try:event.write(out/'events.jsonl')
        except Exception as e:report.setdefault('cleanup_errors',[]).append(str(e))
        report['wall_seconds']=round(time.monotonic()-t,2)
        try:report['resource_lifecycle']=base.verify_ledger(ledger)
        except Exception as e:report['cleanup_errors']=[str(e)]
        report['provenance']={'resource_run_id':identity.run_id,'source_commit':base.git_source_state(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'guest_image':str(IMAGE)}
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')
    print(json.dumps({'out':str(out),'status':report['status'],'role':report.get('role'),'condition':report.get('condition'),'checks':report.get('checks'),'wall_seconds':report.get('wall_seconds'),'error':report.get('error'),'lifecycle_ok':report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record')},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
