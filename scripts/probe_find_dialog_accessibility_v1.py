#!/usr/bin/env python3
"""No-model read-only reconnaissance of LibreOffice Writer Find/Replace dialog."""
from __future__ import annotations
import base64, hashlib, json, os, secrets, shlex, subprocess, sys, time
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
sys.path[:0]=[str(ROOT),str(OSWORLD)]
os.environ.setdefault('OSWORLD_V2_DIR',str(OSWORLD))
from scripts import run_writer_calc_v1 as base
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
DOC=['Release readiness report','Status values: pending / Pending / PENDING.','Protected phrase: DRAFT']
def json_write(p,v): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def active(desktop):
 s=base.guest_command(desktop,['bash','-lc','w=$(xdotool getactivewindow); printf "%s\\t%s\\n" "$w" "$(xdotool getwindowname $w)"']).strip().split('\t')
 return {'xid':s[0] if s else '', 'title':s[1] if len(s)>1 else ''}
def main():
 run_id='find-dialog-a11y-probe-20261104-01'; parent=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs');out=parent/run_id
 if out.exists(): raise RuntimeError('artifact directory already exists')
 if not parent.is_relative_to(Path('/mnt/raid1')): raise RuntimeError('artifact parent outside RAID1')
 if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip(): raise RuntimeError('active containers; refusing')
 if __import__('shutil').disk_usage('/').free<20*1024**3 or __import__('shutil').disk_usage('/mnt/raid1').free<100*1024**3: raise RuntimeError('disk floor failed')
 out.mkdir(parents=True);(out/'overlays').mkdir();ledger=out/'resource-events.jsonl'
 os.environ.update({'SWCUB_RUN_ID':run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays')});os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
 identity=ensure_resource_identity(ledger); log=EventLog(); ep=desk=None; report={'run_id':run_id,'case_id':'CODESK-NEXT-FIND-001','purpose':'No-model accessibility reconnaissance only','model_used':False,'qwen_called':False,'status':'starting','disk_free_start_bytes':__import__('shutil').disk_usage('/').free}
 try:
  runtime='swcub/osworld-v2.1-qemu-runtime:local';os.environ['SWCUB_OSWORLD_GUEST_IMAGE']=str(base.resolve_guest_image_path());os.environ['SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime;os.environ['OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime;os.environ['SWCUB_OSWORLD_CACHE_DIR']=str(parent/'osworld-cache')
  report['runtime_image_id']=subprocess.run(['docker','image','inspect',runtime,'--format','{{.Id}}'],capture_output=True,text=True,check=True).stdout.strip()
  ep,desk=base.make_desktop('find_probe',log,out,require_a11y_tree=True)
  b64=base64.b64encode(base.render_writer_fodt(DOC)).decode('ascii');code=('from pathlib import Path; import base64; p=Path('+repr(base.WRITER_PATH)+'); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(base64.b64decode('+repr(b64)+'))')
  base.guest_command(desk,['python3','-c',code],timeout=30)
  launch='nohup soffice --nologo --norestore --nofirststartwizard --writer '+shlex.quote(base.WRITER_PATH)+' >/tmp/codesk-find-probe.log 2>&1 </dev/null & sleep 7'
  base.guest_command(desk,['bash','-lc',launch],timeout=20)
  report['readiness']=base.wait_for_app_document(ep,desk,'writer',base.WRITER_PATH,out/'readiness',timeout=180)
  ctx=ActorContext('scripted_probe',ep,'gui'); before=active(desk);ctx.execute_gui_action("pyautogui.hotkey('ctrl','h')");time.sleep(2)
  obs=ep.refresh_observation(source='find_dialog_probe');shot=obs.get('screenshot');tree=obs.get('accessibility_tree')
  if isinstance(shot,bytes):(out/'find-dialog.png').write_bytes(shot)
  if isinstance(tree,str):(out/'find-dialog.accessibility.xml').write_text(tree,encoding='utf-8')
  nodes=[]
  if isinstance(tree,str) and tree.strip():
   import xml.etree.ElementTree as ET
   root=ET.fromstring(tree)
   for e in root.iter():
    attrs={k:v for k,v in e.attrib.items()}
    if any(q in json.dumps(attrs,ensure_ascii=False).casefold() for q in ('case','find','replace','search')):nodes.append({'tag':e.tag,'attrs':attrs})
  report.update({'active_before':before,'active_dialog':active(desk),'observation_keys':list(obs),'screenshot_available':bool(shot),'a11y_available':bool(tree),'a11y_chars':len(tree) if isinstance(tree,str) else 0,'matched_accessibility_nodes':nodes,'tree_sha256':hashlib.sha256(tree.encode()).hexdigest() if isinstance(tree,str) else None,'gui_open_ctrl_h':True})
  ctx.press_key('esc');time.sleep(1);report['active_after_close']=active(desk);report['status']='completed'
 except Exception as e: report.update({'status':'probe_error','error':{'type':type(e).__name__,'message':str(e)}})
 finally:
  if ep:
   try:ep.copy_artifacts(out/'guest-artifacts'/'find_probe')
   except Exception:pass
   try:ep.close()
   except Exception as e:report.setdefault('close_error',str(e))
  report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
  report['wall_seconds']=round(time.monotonic()-identity.started_monotonic,2) if hasattr(identity,'started_monotonic') else None
  report['disk_free_end_bytes']=__import__('shutil').disk_usage('/').free;log.write(out/'events.jsonl');json_write(out/'report.json',report)
 print(json.dumps({'status':report['status'],'dialog':report.get('active_dialog'),'matches':report.get('matched_accessibility_nodes'),'a11y':report.get('a11y_available'),'resources':report.get('resource_lifecycle'),'artifact_dir':str(out),'error':report.get('error')},ensure_ascii=False))
if __name__=='__main__':main()
