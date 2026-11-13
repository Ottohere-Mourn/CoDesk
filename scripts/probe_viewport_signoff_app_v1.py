#!/usr/bin/env python3
"""Deterministic Guest positive/negative controls for the local viewport signoff app."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, subprocess, sys, time, io
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
def _window(desktop):
 raw=base.guest_command(desktop,['bash','-lc','wid=$(xdotool getactivewindow 2>/dev/null || true); title=$(xdotool getwindowname "$wid" 2>/dev/null || true); cls=$(xprop -id "$wid" WM_CLASS 2>/dev/null | tail -1 || true); printf "%s\\t%s\\t%s\\n" "$wid" "$title" "$cls"']).strip().split('\t')
 while len(raw)<3:raw.append('')
 return {'xid':raw[0],'title':raw[1],'wm_class':raw[2]}
def _latest_obs(state,source):
 return next((x for x in reversed(state.get('observations',[])) if x.get('source')==source),None)
def _button_center(shot):
 from PIL import Image
 im=Image.open(io.BytesIO(shot)).convert('RGB');pix=im.load();w,h=im.size;color=(23,107,72);start=None
 for y in range(200,h):
  if sum(1 for x in range(w) if pix[x,y]==color)>80:
   start=y;break
 if start is None:raise RuntimeError('cannot locate first sign-off button pixels in screenshot')
 pts=[(x,y) for y in range(start,min(h,start+45)) for x in range(w) if pix[x,y]==color]
 if len(pts)<500:raise RuntimeError('insufficient first-button pixels in screenshot')
 xs=[p[0] for p in pts];ys=[p[1] for p in pts]
 return {'x':round((min(xs)+max(xs))/2),'y':round((min(ys)+max(ys))/2),'rect':[min(xs),min(ys),max(xs),max(ys)],'screen_size':[w,h],'sample_color':list(color),'pixel_count':len(pts)}
def _observe(ep,desk,out,label):
 ob=ep.refresh_observation(source='signoff_probe_'+label);shot=ob.get('screenshot')
 if not isinstance(shot,bytes) or not shot:raise RuntimeError('missing Guest screenshot: '+label)
 path=out/'screenshots'/(label+'.png');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(shot)
 return {'path':str(path.relative_to(out)),'sha256':hashlib.sha256(shot).hexdigest(),'shot':shot,'window':_window(desk)}
def _wait_source(desktop,source,timeout=4):
 end=time.monotonic()+timeout;state={}
 while time.monotonic()<end:
  state=app.query_state(desktop)
  if _latest_obs(state,source):return state
  time.sleep(.1)
 return state
def _reload(ctx,desktop):
 ctx.execute_gui_action("pyautogui.hotkey('ctrl','r')")
 return _wait_source(desktop,'page-load',8)
def _reset(ep,desktop,ctx):
 ctx.execute_gui_action("pyautogui.hotkey('ctrl','home')");time.sleep(.3)
 app.reset_state(desktop);_reload(ctx,desktop)
 return _wait_source(desktop,'page-load',2)
def _click_old(ctx,x,y):
 ctx.execute_gui_action(f'pyautogui.click({int(x)}, {int(y)})');time.sleep(.35)
def _scroll(ctx,down):
 ctx.execute_gui_action(f'pyautogui.scroll({-1 if down else 1}, x=700, y=500)');time.sleep(.35)
def run(args):
 out=args.artifact_parent.resolve()/args.run_id
 if not out.is_relative_to(Path('/mnt/raid1')):raise RuntimeError('probe artifacts must stay on RAID1')
 if out.exists():raise FileExistsError(out)
 if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip():raise RuntimeError('active Docker container(s); refusing Guest start')
 out.mkdir(parents=True);(out/'overlays').mkdir();ledger=out/'resource-events.jsonl'
 os.environ.update({'SWCUB_RUN_ID':args.run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),'OSWORLD_V2_DIR':str(OSWORLD)})
 os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
 identity=ensure_resource_identity(ledger);report={'run_id':args.run_id,'candidate':'VIEW-1 append-only release signoff with viewport-only scroll hit-test','task_version':'0.1.0-scripted-browser-signoff','model_used':False,'evidence_level':'deterministic local Guest GUI control; not model result','status':'starting','controls':{},'setup':{},'resource_identity':{'run_id':identity.run_id,'owner_token_recorded':True}}
 ep=desk=None;log=EventLog();started=time.monotonic()
 try:
  runtime='swcub/osworld-v2.1-qemu-runtime:local';image=base.resolve_guest_image_path()
  os.environ['SWCUB_OSWORLD_GUEST_IMAGE']=str(image);os.environ['SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime;os.environ['OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime;os.environ['SWCUB_OSWORLD_CACHE_DIR']=str(out.parent/'osworld-cache')
  image_id=subprocess.run(['docker','image','inspect',runtime,'--format','{{.Id}}'],capture_output=True,text=True,check=True,timeout=15).stdout.strip()
  report['runtime']={'runtime_image':runtime,'runtime_image_id':image_id,'guest_image':str(image)}
  ep,desk=base.make_desktop('view-signoff-probe',log,out,require_a11y_tree=False)
  report['setup']=app.install_and_launch(ep,desk,'view',out,args.run_id,'Reviewer-A')
  ctx=ActorContext('scripted_view_probe',ep,'gui')
  ready=_observe(ep,desk,out,'initial');state=app.query_state(desk);load=_latest_obs(state,'page-load')
  if not load or not load.get('button_rect'):raise RuntimeError('page-load did not record target button rectangle')
  rect=load['button_rect'];pix=_button_center(ready['shot']);x=pix['x'];y=pix['y']
  initial_window=_window(desk)
  report['coordinate']={'target_button_dom_rect':rect,'target_button_screenshot_pixels':pix,'frozen_screen_click':[x,y],'initial_scroll_y':load.get('scroll_y'),'initial_target_rect':load.get('target_rect'),'initial_decoy_rect':load.get('decoy_rect'),'window':initial_window}
  if not (0<=x<pix['screen_size'][0] and 0<=y<pix['screen_size'][1]):raise RuntimeError(f'computed target click outside screenshot: {(x,y)}')
  # Positive target control: without another actor's scroll, same point must sign off POL-17.
  _click_old(ctx,x,y);baseline=app.query_state(desk)
  base_events=[e for e in baseline['events'] if e.get('kind')=='signoff']
  report['controls']['no_scroll_positive']={'events':base_events,'exact_target_only':len(base_events)==1 and base_events[0].get('record_id')=='POL-17','window_after':_window(desk)}
  # Fresh local state and same frozen UI. A one-notch wheel event must shift the exact old button onto POL-29.
  _reset(ep,desk,ctx);pre=app.query_state(desk);pre_load=_latest_obs(pre,'page-load')
  _scroll(ctx,True);post=app.query_state(desk);scroll_obs=_latest_obs(post,'scroll')
  if not scroll_obs:raise RuntimeError('down-wheel did not produce browser scroll observation')
  _click_old(ctx,x,y);positive=app.query_state(desk);pos_events=[e for e in positive['events'] if e.get('kind')=='signoff']
  pre_target=pre_load.get('target_rect') or {};post_decoy=scroll_obs.get('decoy_rect') or {}
  mapping=(pre_target.get('top') is not None and post_decoy.get('top') is not None and abs(float(pre_target['top'])-float(post_decoy['top']))<=3)
  report['controls']['one_notch_positive']={'pre_scroll':pre_load,'after_scroll':scroll_obs,'events':pos_events,'scroll_delta':(scroll_obs.get('scroll_y',0)-(pre_load or {}).get('scroll_y',0)),'same_old_point_hits_POL29':len(pos_events)==1 and pos_events[0].get('record_id')=='POL-29','geometry_maps_target_to_decoy':mapping,'window_before_after':[initial_window,_window(desk)]}
  # Sham control: down then up yields a zero-net viewport offset and preserves old hit target.
  _reset(ep,desk,ctx);sham_pre=app.query_state(desk);sham_load=_latest_obs(sham_pre,'page-load');_scroll(ctx,True);_scroll(ctx,False);sham=app.query_state(desk);sham_obs=_latest_obs(sham,'scroll')
  _click_old(ctx,x,y);sham_final=app.query_state(desk);sham_events=[e for e in sham_final['events'] if e.get('kind')=='signoff']
  report['controls']['zero_net_scroll_sham']={'initial':sham_load,'final_observation':sham_obs,'final_scroll_y':sham_obs.get('scroll_y') if sham_obs else None,'events':sham_events,'same_old_point_hits_POL17':len(sham_events)==1 and sham_events[0].get('record_id')=='POL-17','window_unchanged':_window(desk)==initial_window}
  report['status']='completed'
 except Exception as exc:
  report['status']='probe_error';report['error']={'type':type(exc).__name__,'message':str(exc)}
 finally:
  if ep:
   try:ep.copy_artifacts(out/'guest-artifacts'/'view-signoff-probe')
   except Exception:pass
   try:ep.close()
   except Exception as exc:report.setdefault('close_errors',[]).append(type(exc).__name__)
  report['wall_seconds']=round(time.monotonic()-started,3);report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.is_file() else None;report['reset_success']=bool(report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record'))
  _json(out/'report.json',report);_json(out/'provenance.json',{'run_id':args.run_id,'source':base.git_source_state(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'app_sha256':hashlib.sha256(Path(app.__file__).read_bytes()).hexdigest()})
 print(json.dumps({'run_id':args.run_id,'status':report['status'],'zero_scroll_target':report.get('controls',{}).get('no_scroll_positive',{}).get('exact_target_only'),'scroll_hits_decoy':report.get('controls',{}).get('one_notch_positive',{}).get('same_old_point_hits_POL29'),'geometry_maps_target_to_decoy':report.get('controls',{}).get('one_notch_positive',{}).get('geometry_maps_target_to_decoy'),'sham_preserves_target':report.get('controls',{}).get('zero_net_scroll_sham',{}).get('same_old_point_hits_POL17'),'reset_success':report.get('reset_success'),'wall_seconds':report.get('wall_seconds'),'error':report.get('error'),'artifact_dir':str(out)}))
 return 0 if report.get('status')=='completed' else 1

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--artifact-parent',type=Path,default=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/probes'));run(ap.parse_args())
if __name__=='__main__':main()