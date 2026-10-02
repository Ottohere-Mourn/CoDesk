#!/usr/bin/env python3
"""Bounded real-Guest probe for same-window Calc active-cell contention."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, secrets, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import run_writer_calc_v1 as base
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.task_factory import render_calc_fods
TASK_ID="CODESK-FAMILY-SELECTION-001"; TASK_VERSION="0.1.0-probe"
GUEST_PATH="/tmp/codesk_selection/task.fods"
INITIAL=[["Name","Target A","Unused"],["Row2","B2 seed","Unused"],["Row3","Unused","C3 seed"]]
TARGETS={"actor_a":{"cell":"B2","value":"A-7319"},"actor_b":{"cell":"C3","value":"B-2042"}}
NS={"table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0","text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0","office":"urn:oasis:names:tc:opendocument:xmlns:office:1.0"}
def cmd(desktop,argv,timeout=40): return base.guest_command(desktop,argv,timeout=timeout)
def selection(desktop):
    py="import json,uno; c=uno.getComponentContext(); r=c.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',c); x=r.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); d=x.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',x); a=d.getCurrentComponent().getCurrentSelection().getRangeAddress(); print(json.dumps({'sheet':a.Sheet,'start_column':a.StartColumn,'start_row':a.StartRow,'end_column':a.EndColumn,'end_row':a.EndRow}))"
    raw=cmd(desktop,["python3","-c",py],timeout=15).strip().splitlines()[-1]
    return json.loads(raw)
def active(desktop):
    raw=cmd(desktop,["bash","-lc","xid=$(xdotool getactivewindow); printf '%s\\n' \"$xid\"; xdotool getwindowname $xid"],timeout=10).splitlines()
    return {"xid":raw[0] if raw else "", "title":raw[1] if len(raw)>1 else ""}
def clipboard_digest(desktop):
    raw=cmd(desktop,["bash","-lc","timeout 2 xclip -selection clipboard -o 2>/dev/null | sha256sum | cut -d' ' -f1 || true"],timeout=8).strip()
    return raw.splitlines()[-1] if raw else ""
def select_cell(ctx,cell):
    col=ord(cell[0].upper())-ord('A'); row=int(cell[1:])-1
    ctx.press_key("ctrl+home")
    for _ in range(col): ctx.press_key("Right")
    for _ in range(row): ctx.press_key("Down")
def put(ctx,value): ctx.type_text(value); ctx.press_key("ctrl+s"); time.sleep(1)
def read_fods(raw):
    import xml.etree.ElementTree as ET
    root=ET.fromstring(raw); table=root.find('.//table:table',NS); rows=[]
    if table is None: return rows
    for row in table.findall('table:table-row',NS):
        vals=[]
        for cell in row.findall('table:table-cell',NS):
            p=cell.find('text:p',NS); vals.append(''.join(p.itertext()) if p is not None else '')
        rows.append(vals)
    return rows
def evaluate(desktop, required):
    raw=cmd(desktop,["cat",GUEST_PATH],timeout=20).encode(); grid=read_fods(raw); expected=[list(r) for r in INITIAL]
    for actor in required:
        spec=TARGETS[actor]; col=ord(spec['cell'][0])-ord('A'); row=int(spec['cell'][1:])-1; expected[row][col]=spec['value']
    actual=[row[:len(expected[i])] + ['']*max(0,len(expected[i])-len(row)) for i,row in enumerate(grid[:len(expected)])]
    while len(actual)<len(expected): actual.append([])
    return {"success":actual==expected,"expected_grid":expected,"actual_grid":actual,"output_sha256":hashlib.sha256(raw).hexdigest()}
def main():
    p=argparse.ArgumentParser(); p.add_argument('--condition',choices=['solo_a','solo_b','ma_id','ma_sd','ma_sd_recovery'],required=True); p.add_argument('--run-id',required=True); p.add_argument('--artifact-parent',type=Path,required=True); a=p.parse_args()
    out=a.artifact_parent.resolve()/a.run_id; out.mkdir(parents=True,exist_ok=False); (out/'overlays').mkdir(); ledger=out/'resource-events.jsonl'
    os.environ.update({'SWCUB_RUN_ID':a.run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays')}); os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None); ident=ensure_resource_identity(ledger)
    log=EventLog(); envs={}; desktops={}; selection_events=[]; start=time.monotonic(); phase='guest_startup'
    report={'run_id':a.run_id,'task_id':TASK_ID,'task_version':TASK_VERSION,'condition':a.condition,'status':'starting','model_used':False,'actor_implementation':'scripted','guest_host':os.uname().nodename,'scheduled_exposure':a.condition in {'ma_id','ma_sd','ma_sd_recovery'},'actors':{},'selection_timeline':[],'observed_interference':'unknown','recovery':{'attempted':a.condition=='ma_sd_recovery'}}
    def start_binding(binding):
        ep,desk=base.make_desktop(binding,log,out); envs[binding]=ep; desktops[binding]=desk
        b64=base64.b64encode(render_calc_fods(INITIAL)).decode()
        script=f"from pathlib import Path; import base64; p=Path({GUEST_PATH!r}); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(base64.b64decode({b64!r}))"
        cmd(desk,['python3','-c',script],timeout=20)
        cmd(desk,['bash','-lc',f"soffice --nologo --norestore --nofirststartwizard --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' --calc {GUEST_PATH} >/tmp/codesk-selection-soffice.log 2>&1 & sleep 7"],timeout=15)
        ready=base.wait_for_app_document(ep,desk,'calc',GUEST_PATH,out/binding/'readiness',timeout=120)
        probe=cmd(desk,['python3','-c','import uno; print("UNO_READY")'],timeout=10)
        if 'UNO_READY' not in probe: raise RuntimeError('UNO read-only selection observer unavailable')
        report.setdefault('readiness',{})[binding]={'app':ready,'uno_observer':True,'initial_selection':selection(desk),'initial_active_window':active(desk)}
        ep.log.record('task_setup','healthcheck','selection.observer_ready',{},report['readiness'][binding],details={'read_only':True})
    def mark(actor,binding,event,details=None):
        desk=desktops[binding]; row={'actor_id':actor,'event':event,'selection':selection(desk),'active_window':active(desk),'clipboard_sha256':clipboard_digest(desk),'monotonic':time.monotonic(),**(details or {})}; selection_events.append(row)
        log.record(actor,'instrumentation','selection.'+event,{},row,details={'read_only_observer':True,'hidden_from_actor':True}); return row
    try:
        phase='setup'
        if a.condition in {'solo_a','solo_b'}:
            who='actor_a' if a.condition=='solo_a' else 'actor_b'; start_binding(who); actor=ActorContext(who,envs[who],'gui'); spec=TARGETS[who]
            select_cell(actor,spec['cell']); row=mark(who,who,'target_selected',{'expected_cell':spec['cell']})
            if (row['selection']['start_column'],row['selection']['start_row'])!=(ord(spec['cell'][0])-65,int(spec['cell'][1:])-1): raise RuntimeError('target selection did not match oracle')
            put(actor,spec['value']); report['actors'][who]={'goal':spec,'selected':row}; report['evaluation']=evaluate(desktops[who],[who]); report['joint_success']=report['evaluation']['success']
        else:
            shared=a.condition!='ma_id'
            if shared: start_binding('shared'); bindings={'actor_a':'shared','actor_b':'shared'}
            else: start_binding('actor_a'); start_binding('actor_b'); bindings={'actor_a':'actor_a','actor_b':'actor_b'}
            contexts={x:ActorContext(x,envs[bindings[x]],'gui') for x in ('actor_a','actor_b')}
            spec=TARGETS['actor_a']; select_cell(contexts['actor_a'],spec['cell']); arow=mark('actor_a',bindings['actor_a'],'target_selected',{'expected_cell':spec['cell'],'gate':'pause_A_after_selection'})
            if arow['selection']['start_column']!=1 or arow['selection']['start_row']!=1: raise RuntimeError(f"A target selection mismatch: {arow['selection']}")
            specb=TARGETS['actor_b']; select_cell(contexts['actor_b'],specb['cell']); brow=mark('actor_b',bindings['actor_b'],'target_selected',{'expected_cell':specb['cell'],'gate':'pause_B_after_selection'})
            if brow['selection']['start_column']!=2 or brow['selection']['start_row']!=2: raise RuntimeError(f"B target selection mismatch: {brow['selection']}")
            put(contexts['actor_b'],specb['value']); mark('actor_b',bindings['actor_b'],'goal_saved',{'value':specb['value']})
            put(contexts['actor_a'],TARGETS['actor_a']['value']); mark('actor_a',bindings['actor_a'],'resumed_stale_selection_write',{'value':TARGETS['actor_a']['value']})
            if a.condition=='ma_sd_recovery':
                for who in ('actor_a','actor_b'):
                    c=contexts[who]; sp=TARGETS[who]; select_cell(c,sp['cell']); mark(who,bindings[who],'recovery_reselected',{'cell':sp['cell']}); put(c,sp['value']); mark(who,bindings[who],'recovery_saved',{'cell':sp['cell']})
                report['recovery']['success']=True
            report['bindings']=bindings; report['actor_goal_success']={}
            if shared:
                ev=evaluate(desktops['shared'],['actor_a','actor_b']); report['evaluation']=ev
                report['actor_goal_success']={'actor_a':ev['actual_grid'][1][1]=='A-7319','actor_b':ev['actual_grid'][2][2]=='B-2042'}
            else:
                report['evaluation']={who:evaluate(desktops[bindings[who]],[who]) for who in bindings}; report['actor_goal_success']={who:report['evaluation'][who]['success'] for who in bindings}
            report['joint_success']=all(report['actor_goal_success'].values())
            active_ids={r['active_window']['xid'] for r in selection_events}; report['same_top_level_window']=shared and len(active_ids)==1
            report['clipboard_unchanged']=len({r['clipboard_sha256'] for r in selection_events})<=1
            report['observed_interference']=bool(shared and not report['joint_success'] and report['same_top_level_window'] and report['clipboard_unchanged'])
            for ep in envs.values(): ep.copy_artifacts(out/f'guest-{ep.environment_id}-artifacts')
        report['selection_timeline']=selection_events; report['status']='completed'; phase='reset'
        for ep in list(envs.values()): ep.close()
        envs.clear(); report['reset_success']=True
    except Exception as exc:
        report['status']='invalid_setup' if phase in {'guest_startup','setup'} else 'probe_error'; report['error']={'phase':phase,'type':type(exc).__name__,'message':str(exc)}
        for ep in envs.values():
            try: ep.copy_artifacts(out/'failure-artifacts')
            except Exception: pass
            try: ep.close()
            except Exception: pass
        envs.clear()
    finally:
        report['wall_seconds']=round(time.monotonic()-start,2); report['selection_timeline']=selection_events; log.write(out/'events.jsonl'); report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
        (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n'); (out/'provenance.json').write_text(json.dumps({'run_id':ident.run_id,'source':base.git_source_state(),'task_id':TASK_ID,'task_version':TASK_VERSION,'instance_sha256':hashlib.sha256(json.dumps({'initial':INITIAL,'targets':TARGETS},sort_keys=True).encode()).hexdigest(),'artifact_sha256':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='provenance.json' and 'overlays' not in p.parts}},indent=2)+'\n')
    print(json.dumps({'run_id':a.run_id,'status':report['status'],'joint_success':report.get('joint_success'),'goal_success':report.get('actor_goal_success'),'interference':report.get('observed_interference'),'same_window':report.get('same_top_level_window'),'clipboard_unchanged':report.get('clipboard_unchanged'),'reset_success':report.get('reset_success'),'artifact_dir':str(out),'error':report.get('error')})); return 0 if report['status']=='completed' and report.get('reset_success') else 1
if __name__=='__main__': raise SystemExit(main())
