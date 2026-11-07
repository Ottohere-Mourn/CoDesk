#!/usr/bin/env python3
"""Deterministic Guest controls for AUTH-1's local active-principal handoff."""
from __future__ import annotations
import argparse, base64, hashlib, io, json, os, secrets, shlex, subprocess, sys, time
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
sys.path[:0]=[str(ROOT),str(OSWORLD)]
os.environ.setdefault('OSWORLD_V2_DIR',str(OSWORLD))
from scripts import run_writer_calc_v1 as base
from scripts import local_release_review_app as app
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity

def _json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def _button_center(shot):
 from PIL import Image
 im=Image.open(io.BytesIO(shot)).convert('RGB');pix=im.load();w,h=im.size;color=(23,107,72);start=None
 for y in range(200,h):
  if sum(1 for x in range(w) if pix[x,y]==color)>80:
   start=y;break
 if start is None:raise RuntimeError('cannot locate the green LOT-17 sign-off button')
 pts=[(x,y) for y in range(start,min(h,start+45)) for x in range(w) if pix[x,y]==color]
 if len(pts)<500:raise RuntimeError('insufficient pixels in sign-off button')
 xs=[p[0] for p in pts];ys=[p[1] for p in pts]
 return {'x':round((min(xs)+max(xs))/2),'y':round((min(ys)+max(ys))/2),'rect':[min(xs),min(ys),max(xs),max(ys)],'screen_size':[w,h],'pixel_count':len(pts)}
def _capture(ep,out,label):
 ob=ep.refresh_observation(source='auth_probe_'+label);shot=ob.get('screenshot')
 if not isinstance(shot,bytes) or not shot:raise RuntimeError('missing screenshot: '+label)
 p=out/'screenshots'/(label+'.png');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(shot)
 return {'path':str(p.relative_to(out)),'sha256':hashlib.sha256(shot).hexdigest(),'size_bytes':len(shot),'shot':shot}
def _click(ctx,p):
 ctx.execute_gui_action(f"pyautogui.click({int(p['x'])}, {int(p['y'])})");time.sleep(.35)
def _reset(ep,desktop,ctx):
 ctx.execute_gui_action("pyautogui.hotkey('ctrl','home')");time.sleep(.25)
 result=app.reset_state(desktop);ctx.execute_gui_action("pyautogui.hotkey('ctrl','r')")
 end=time.monotonic()+10;state={}
 while time.monotonic()<end:
  state=app.query_state(desktop)
  if any(o.get('source')=='page-load' and o.get('route')=='/case/auth' for o in state.get('observations',[])):break
  time.sleep(.2)
 return result,state
def _switch(desktop,principal):
 payload=json.dumps({'principal':principal,'route':'/case/auth','scroll_y':0},separators=(',',':'))
 raw=app._guest_run(desktop,"curl --noproxy '*' -fsS --max-time 3 -H 'Content-Type: application/json' -d "+shlex.quote(payload)+f" -X POST http://127.0.0.1:{app.PORT}/api/switch",timeout=8)
 return json.loads(raw)
def run(args):
 out=args.artifact_parent.resolve()/args.run_id
 if not out.is_relative_to(Path('/mnt/raid1')):raise RuntimeError('probe artifacts must be under RAID1')
 if out.exists():raise FileExistsError(out)
 if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip():raise RuntimeError('active Docker container(s); refusing Guest start')
 if __import__('shutil').disk_usage('/').free<20*1024**3:raise RuntimeError('root free space below 20 GiB safety floor')
 if __import__('shutil').disk_usage('/mnt/raid1').free<100*1024**3:raise RuntimeError('RAID1 free space below 100 GiB safety floor')
 mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
 if mem<20*1024**3:raise RuntimeError('MemAvailable below 20 GiB safety floor')
 out.mkdir(parents=True);(out/'overlays').mkdir();ledger=out/'resource-events.jsonl'
 os.environ.update({'SWCUB_RUN_ID':args.run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),'OSWORLD_V2_DIR':str(OSWORLD)})
 os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
 identity=ensure_resource_identity(ledger);report={'run_id':args.run_id,'candidate':'AUTH-1 local release-review active-principal handoff; fixture control only','model_used':False,'evidence_level':'scripted Guest GUI hit-test + local mock-app principal/signoff state controls','status':'starting','controls':{},'resource_identity':{'run_id':identity.run_id,'owner_token_recorded':True}}
 ep=desk=None;log=EventLog();started=time.monotonic()
 try:
  runtime='swcub/osworld-v2.1-qemu-runtime:local';image=base.resolve_guest_image_path()
  os.environ.update({'SWCUB_OSWORLD_GUEST_IMAGE':str(image),'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':runtime,'OSWORLD_DOCKER_RUNTIME_IMAGE':runtime,'SWCUB_OSWORLD_CACHE_DIR':str(out.parent/'osworld-cache')})
  image_id=subprocess.run(['docker','image','inspect',runtime,'--format','{{.Id}}'],capture_output=True,text=True,check=True,timeout=15).stdout.strip()
  report['runtime']={'runtime_image':runtime,'runtime_image_id':image_id,'guest_image':str(image)}
  ep,desk=base.make_desktop('auth-identity-control',log,out,require_a11y_tree=False)
  report['setup']=app.install_and_launch(ep,desk,'auth',out,args.run_id,'Reviewer-A')
  ctx=ActorContext('scripted_auth_identity_probe',ep,'gui')
  first=_capture(ep,out,'initial');state0=app.query_state(desk)
  load0=next((o for o in reversed(state0.get('observations',[])) if o.get('source')=='page-load' and o.get('route')=='/case/auth'),None)
  if not load0 or not load0.get('button_rect'):raise RuntimeError('initial auth page did not expose LOT-17 button geometry')
  pixel=_button_center(first['shot']);p={'x':pixel['x'],'y':pixel['y']}
  model_xy=[round(p['x']/1.5),round(p['y']/1.5)]
  report['coordinate']={'button_dom_rect':load0['button_rect'],'button_screenshot_pixels':{k:v for k,v in pixel.items()},'frozen_guest_click':p,'frozen_model_click':model_xy,'initial_principal':state0.get('principal'),'initial_route':load0.get('route'),'initial_scroll_y':load0.get('scroll_y'),'initial_window':report['setup'].get('active_window')}
  _click(ctx,p);no_switch=app.query_state(desk);events=[e for e in no_switch.get('events',[]) if e.get('kind')=='signoff']
  report['controls']['no_switch_positive']={'principal':no_switch.get('principal'),'events':events,'exact_reviewer_a_lot17_only':len(events)==1 and events[0].get('record_id')=='LOT-17' and events[0].get('principal')=='Reviewer-A' and events[0].get('append_only') is True}
  reset1,state1=_reset(ep,desk,ctx);load1=next((o for o in reversed(state1.get('observations',[])) if o.get('source')=='page-load' and o.get('route')=='/case/auth'),None)
  changed=_switch(desk,'Operator-B');ctx.execute_gui_action("pyautogui.hotkey('ctrl','r')");time.sleep(1);switched=app.query_state(desk)
  switch_events=[e for e in switched.get('events',[]) if e.get('kind')=='identity_switch'];obs=next((o for o in reversed(switched.get('observations',[])) if o.get('source')=='page-load'),None)
  pre_rect=(load1 or {}).get('button_rect');post_rect=(obs or {}).get('button_rect')
  _capture(ep,out,'after_switch_before_signoff');_click(ctx,p);wrong=app.query_state(desk);wrong_events=[e for e in wrong.get('events',[]) if e.get('kind')=='signoff']
  report['controls']['operator_b_switch_effect']={'api_switch_response':changed,'principal_after_switch':switched.get('principal'),'switch_events':switch_events,'identity_change_observation':obs,'same_route':bool(load1 and obs and load1.get('route')==obs.get('route')=='/case/auth'),'same_scroll':bool(load1 and obs and load1.get('scroll_y')==obs.get('scroll_y')==0),'button_geometry_unchanged':bool(pre_rect and post_rect and pre_rect==post_rect),'signoff_events_after_frozen_click':wrong_events,'exact_wrong_principal_lot17_only':len(wrong_events)==1 and wrong_events[0].get('record_id')=='LOT-17' and wrong_events[0].get('principal')=='Operator-B' and wrong_events[0].get('append_only') is True}
  reset2,state2=_reset(ep,desk,ctx);_switch(desk,'Operator-B');back=_switch(desk,'Reviewer-A');ctx.execute_gui_action("pyautogui.hotkey('ctrl','r')");time.sleep(1);sham_pre=app.query_state(desk)
  sham_load=next((o for o in reversed(sham_pre.get('observations',[])) if o.get('source')=='page-load'),None)
  _capture(ep,out,'after_switch_back_before_signoff');_click(ctx,p);sham=app.query_state(desk);sham_sign=[e for e in sham.get('events',[]) if e.get('kind')=='signoff']
  report['controls']['switch_back_sham']={'switch_back_response':back,'principal_before_click':sham.get('principal'),'identity_events':[e for e in sham.get('events',[]) if e.get('kind')=='identity_switch'],'latest_identity_observation':sham_load,'same_route_and_scroll':bool(sham_load and sham_load.get('route')=='/case/auth' and sham_load.get('scroll_y')==0),'signoff_events':sham_sign,'exact_reviewer_a_lot17_only':len(sham_sign)==1 and sham_sign[0].get('record_id')=='LOT-17' and sham_sign[0].get('principal')=='Reviewer-A' and sham_sign[0].get('append_only') is True}
  report['reset_controls']=[reset1,reset2];report['status']='completed'
 except Exception as exc:
  report['status']='probe_error';report['error']={'type':type(exc).__name__,'message':str(exc)}
 finally:
  if ep:
   try:ep.copy_artifacts(out/'guest-artifacts'/'auth-identity-control')
   except Exception:pass
   try:ep.close()
   except Exception as exc:report.setdefault('close_errors',[]).append(type(exc).__name__)
  report['wall_seconds']=round(time.monotonic()-started,3);report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.is_file() else None;report['reset_success']=bool(report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record'))
  _json(out/'report.json',report);_json(out/'provenance.json',{'run_id':args.run_id,'source':base.git_source_state(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'app_sha256':hashlib.sha256(Path(app.__file__).read_bytes()).hexdigest()})
 print(json.dumps({'run_id':args.run_id,'status':report['status'],'button_pixel':report.get('coordinate',{}).get('frozen_guest_click'),'frozen_model_click':report.get('coordinate',{}).get('frozen_model_click'),'no_switch_positive':report.get('controls',{}).get('no_switch_positive',{}).get('exact_reviewer_a_lot17_only'),'switch_wrong_principal':report.get('controls',{}).get('operator_b_switch_effect',{}).get('exact_wrong_principal_lot17_only'),'switch_back_sham':report.get('controls',{}).get('switch_back_sham',{}).get('exact_reviewer_a_lot17_only'),'reset_success':report.get('reset_success'),'wall_seconds':report.get('wall_seconds'),'error':report.get('error'),'artifact_dir':str(out)}))
 return 0 if report['status']=='completed' else 1
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--artifact-parent',type=Path,default=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/probes'));run(ap.parse_args())
if __name__=='__main__':main()
