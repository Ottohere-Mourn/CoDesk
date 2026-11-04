#!/usr/bin/env python3
"""Scripted GUI positive/negative controls for Writer Match case persistence."""
from __future__ import annotations
import base64, hashlib, json, os, secrets, shlex, shutil, subprocess, sys, time, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102'); OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
sys.path[:0]=[str(ROOT),str(OSWORLD)];os.environ.setdefault('OSWORLD_V2_DIR',str(OSWORLD))
from scripts import run_writer_calc_v1 as base
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
CASE='CODESK-NEXT-FIND-001'; RUN=os.environ.get('SWCUB_FIND_RUN_ID','find-matchcase-scripted-controls-20261104-01'); SHARED_ONLY=os.environ.get('SWCUB_FIND_SHARED_ONLY')=='1'
DOC=['Release readiness report | controlled terminology', 'Status A: pending | owner review complete.', 'Status B: Pending | owner review complete.', 'Status C: PENDING | owner review complete.', 'Archive code: DRAFT | retained for exact-case review.']
EXPECTED_SHARED=['Release readiness report | controlled terminology','Status A: approved | owner review complete.','Status B: Pending | owner review complete.','Status C: PENDING | owner review complete.','Archive code: REVIEW | retained for exact-case review.']
EXPECTED_ALL=['Release readiness report | controlled terminology','Status A: approved | owner review complete.','Status B: approved | owner review complete.','Status C: approved | owner review complete.','Archive code: DRAFT | retained for exact-case review.']
def put_json(p,v): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def active(d):
 s=base.guest_command(d,['bash','-lc','w=$(xdotool getactivewindow); printf "%s\\t%s\\n" "$w" "$(xdotool getwindowname $w)"']).strip().split('\t')
 return {'xid':s[0] if s else '', 'title':s[1] if len(s)>1 else ''}
def read_text(d): return base.GuestLibreOfficeBindingEvaluator._parse_writer(base.guest_command(d,['cat',base.WRITER_PATH],timeout=30))
def capture(ep,out,label):
 out.mkdir(parents=True,exist_ok=True)
 obs=ep.refresh_observation(source='find_'+label); shot=obs.get('screenshot');tree=obs.get('accessibility_tree')
 if isinstance(shot,bytes):(out/(label+'.png')).write_bytes(shot)
 if not isinstance(tree,str) or not tree.strip(): raise RuntimeError('accessibility tree unavailable at '+label)
 (out/(label+'.xml')).write_text(tree,encoding='utf-8');root=ET.fromstring(tree)
 dialog=next((e for e in root.iter() if e.tag=='dialog' and e.attrib.get('name')=='Find and Replace'),None)
 if dialog is None: raise RuntimeError('Find and Replace dialog absent at '+label)
 cb=next((e for e in dialog.iter() if e.tag=='check-box' and e.attrib.get('name')=='Match case'),None)
 if cb is None: raise RuntimeError('Match case checkbox absent')
 def xy(e,attr='screencoord'):
  z=next((v for k,v in e.attrib.items() if k.endswith(attr)),None)
  if not z: raise RuntimeError('missing a11y '+attr+' on '+e.attrib.get('name',''))
  return tuple(int(x.strip()) for x in z.strip('()').split(','))
 cxy=xy(cb); search=next((e for e in dialog.iter() if e.tag=='text' and next((v for k,v in e.attrib.items() if k.endswith('screencoord')),'')=='(735, 388)'),None)
 repl=next((e for e in dialog.iter() if e.tag=='text' and next((v for k,v in e.attrib.items() if k.endswith('screencoord')),'')=='(735, 479)'),None)
 btn=next((e for e in dialog.iter() if e.tag=='push-button' and e.attrib.get('name')=='Replace All'),None)
 if search is None or repl is None or btn is None: raise RuntimeError('required Find/Replace controls not located')
 return {'match_case':next((v=='true' for k,v in cb.attrib.items() if k.endswith('checked')),False),'checkbox_xy':cxy,'search_xy':xy(search),'replace_xy':xy(repl),'replace_all_xy':xy(btn),'tree_sha256':hashlib.sha256(tree.encode()).hexdigest(),'screenshot':bool(shot)}
def open_dialog(ctx,ep,out,label):
 ctx.execute_gui_action("pyautogui.hotkey('ctrl','h')");time.sleep(1.5); s=capture(ep,out,label);s['active']=None
 return s
def toggle_match(ctx,ep,out,label,desired=True):
 s=capture(ep,out,label+'_before_toggle')
 if s['match_case']!=desired:
  x,y=s['checkbox_xy'];ctx.execute_gui_action(f'pyautogui.click({x+20}, {y+11})');time.sleep(.8);s=capture(ep,out,label+'_after_toggle')
 if s['match_case']!=desired: raise RuntimeError(f'Match case did not toggle to {desired}: {s}')
 return s
def fill_and_replace(ctx,ep,out,label,find,replace):
 s=capture(ep,out,label+'_dialog');
 for xy,value in ((s['search_xy'],find),(s['replace_xy'],replace)):
  x,y=xy;ctx.execute_gui_action(f"pyautogui.click({x+180}, {y+17})");ctx.execute_gui_action("pyautogui.hotkey('ctrl','a')");ctx.execute_gui_action('pyautogui.write('+repr(value)+')')
 filled=capture(ep,out,label+'_filled');
 x,y=s['replace_all_xy'];ctx.execute_gui_action("pyautogui.hotkey('alt','l')");time.sleep(1.5)
 obs=ep.refresh_observation(source='find_'+label+'_after_replace_action'); shot=obs.get('screenshot'); tree=obs.get('accessibility_tree')
 if isinstance(shot,bytes):(out/(label+'_post_action.png')).write_bytes(shot)
 if isinstance(tree,str):(out/(label+'_post_action.xml')).write_text(tree,encoding='utf-8')
 state={'active_after_replace':active_from_ctx(ctx),'a11y_tree_available':bool(tree),'a11y_tree_sha256':hashlib.sha256(tree.encode()).hexdigest() if isinstance(tree,str) else None}
 # Dismiss LO's optional replacement-count popup, then close Find/Replace.
 a=active_from_ctx(ctx);state['active_after_replace']=a
 # Escape safely dismisses an optional count alert, then closes the search dialog; no document keystroke is injected.
 ctx.press_key('esc');time.sleep(.3);ctx.press_key('esc');time.sleep(.4);ctx.execute_gui_action("pyautogui.hotkey('ctrl','s')");time.sleep(1)
 return state
def active_from_ctx(ctx):
 # Resolve concrete Guest executor through the episode adapter, not the host shell.
 env=ctx._environment
 while hasattr(env,'_environment'): env=env._environment
 d=getattr(env,'desktop',None) or getattr(env,'_desktop',None)
 if d is None:
  # caller stores exact Guest context on adapter for explicit instrumentation
  d=getattr(ctx,'_find_desktop',None)
 if d is None: return {'xid':'','title':'unknown'}
 return active(d)
def exact(actual,expected): return actual.splitlines()==expected

def main():
 parent=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs');out=parent/RUN
 if out.exists():raise RuntimeError('artifact exists')
 if not out.is_relative_to(Path('/mnt/raid1')):raise RuntimeError('artifact path safety violation')
 if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip():raise RuntimeError('active containers; refusing run')
 if shutil.disk_usage('/').free<20*1024**3 or shutil.disk_usage('/mnt/raid1').free<100*1024**3:raise RuntimeError('disk safety floor failed')
 out.mkdir(parents=True);(out/'overlays').mkdir();ledger=out/'resource-events.jsonl';os.environ.update({'SWCUB_RUN_ID':RUN,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays')});os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None);identity=ensure_resource_identity(ledger)
 log=EventLog();eps={};desks={};contexts={};report={'run_id':RUN,'case_id':CASE,'task_version':'0.1.0-scripted-gui-controls','model_used':False,'qwen_called':False,'status':'starting','controls':{},'artifacts':str(out)};started=time.monotonic()
 def start(name):
  ep,d=base.make_desktop(name,log,out,require_a11y_tree=True);eps[name]=ep;desks[name]=d;ctx=ActorContext(name,ep,'gui');ctx._find_desktop=d;contexts[name]=ctx
  b64=base64.b64encode(base.render_writer_fodt(DOC)).decode('ascii');code='from pathlib import Path;import base64;p=Path('+repr(base.WRITER_PATH)+');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode('+repr(b64)+'))'
  base.guest_command(d,['python3','-c',code],timeout=30);launch='nohup soffice --nologo --norestore --nofirststartwizard --writer '+shlex.quote(base.WRITER_PATH)+' >/tmp/codesk-find-'+name+'.log 2>&1 </dev/null & sleep 7';base.guest_command(d,['bash','-lc',launch],timeout=20)
  ready=base.wait_for_app_document(ep,d,'writer',base.WRITER_PATH,out/'readiness'/name,timeout=240)
  if read_text(d)!='\n'.join(DOC):raise RuntimeError(name+' fixture exact-text mismatch')
  report.setdefault('readiness',{})[name]=ready;report.setdefault('xids',{})[name]=active(d)
 def gui_replace(name,find,repl,label):
  ctx=contexts[name];return fill_and_replace(ctx,eps[name],out/label, label,find,repl)
 try:
  runtime='swcub/osworld-v2.1-qemu-runtime:local';os.environ['SWCUB_OSWORLD_GUEST_IMAGE']=str(base.resolve_guest_image_path());os.environ['SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime;os.environ['OSWORLD_DOCKER_RUNTIME_IMAGE']=runtime;os.environ['SWCUB_OSWORLD_CACHE_DIR']=str(parent/'osworld-cache');report['runtime_image_id']=subprocess.run(['docker','image','inspect',runtime,'--format','{{.Id}}'],capture_output=True,text=True,check=True).stdout.strip()
  # Shared-view positive control: A observes default, B changes only Match case then edits a distinct line.
  start('shared');ctx=contexts['shared'];p0=open_dialog(ctx,eps['shared'],out,'shared-default');report['controls']['shared_default']=p0
  if p0['match_case']:raise RuntimeError('unexpected non-default Match case in clean profile')
  ctx.press_key('esc');time.sleep(.3);bopen=open_dialog(ctx,eps['shared'],out,'shared_b_dialog');bset=toggle_match(ctx,eps['shared'],out,'shared_b',True);report['controls']['shared_b_toggle']=bset
  b_result=fill_and_replace(ctx,eps['shared'],out,'shared_b_replace','DRAFT','REVIEW');b_text=read_text(desks['shared']);report['controls']['shared_b_task']={'dialog_action':b_result,'exact_text':b_text,'success':b_text=='\n'.join([*DOC[:4],'Archive code: REVIEW | retained for exact-case review.'])}
  if not report['controls']['shared_b_task']['success']:raise RuntimeError('shared B scripted Replace All did not produce exact expected output')
  aopen=open_dialog(ctx,eps['shared'],out,'shared_a_reopen');report['controls']['shared_a_reopened_state']=aopen
  a_result=fill_and_replace(ctx,eps['shared'],out,'shared_a_replace','pending','approved');shared_text=read_text(desks['shared']);report['controls']['shared_positive']={'a_replace':a_result,'same_xid_both_actors':report['xids']['shared']['xid']==active(desks['shared'])['xid'],'exact_text':shared_text,'expected_text':'\n'.join(EXPECTED_SHARED),'pass':shared_text=='\n'.join(EXPECTED_SHARED)}
  if not report['controls']['shared_positive']['pass']:raise RuntimeError('shared positive control oracle failed')
  if not SHARED_ONLY:
    # MA-ID negative: B toggles and completes its separate Guest task; A's clean independent profile remains insensitive.
    start('ma_id_a');start('ma_id_b');a0=open_dialog(contexts['ma_id_a'],eps['ma_id_a'],out,'ma_id_a_default_before_b');report['controls']['ma_id_a_default_before_b']=a0
    if a0['match_case']:raise RuntimeError('MA-ID A profile did not start with Match case off')
    contexts['ma_id_a'].press_key('esc');open_dialog(contexts['ma_id_b'],eps['ma_id_b'],out,'ma_id_b_dialog');b0=capture(eps['ma_id_b'],out,'ma_id_b_before_toggle')
    if b0['match_case']:raise RuntimeError('MA-ID B profile did not start with Match case off')
    toggle_match(contexts['ma_id_b'],eps['ma_id_b'],out,'ma_id_b',True);bmr=fill_and_replace(contexts['ma_id_b'],eps['ma_id_b'],out,'ma_id_b_replace','DRAFT','REVIEW');bmt=read_text(desks['ma_id_b'])
    report['controls']['ma_id_b_task']={'match_case_set':True,'action':bmr,'exact_text':bmt,'success':bmt=='\n'.join([*DOC[:4],'Archive code: REVIEW | retained for exact-case review.'])}
    a_after=open_dialog(contexts['ma_id_a'],eps['ma_id_a'],out,'ma_id_a_after_b');report['controls']['ma_id_a_after_other_guest_b_toggle']=a_after
    if a_after['match_case']:raise RuntimeError('B preference leaked into A independent Guest')
    ar=fill_and_replace(contexts['ma_id_a'],eps['ma_id_a'],out,'ma_id_a_replace','pending','approved');at=read_text(desks['ma_id_a'])
    report['controls']['ma_id_negative']={'a_replace':ar,'exact_text':at,'expected_text':'\n'.join(EXPECTED_ALL),'pass':at=='\n'.join(EXPECTED_ALL),'state_is_off_after_b_other_guest_toggle':not a_after['match_case']}
  report['status']='completed'
 except Exception as e:report.update({'status':'probe_error','error':{'type':type(e).__name__,'message':str(e)}})
 finally:
  for n,ep in list(eps.items()):
   try:ep.copy_artifacts(out/'guest-artifacts'/n)
   except Exception:pass
   try:ep.close()
   except Exception as e:report.setdefault('close_errors',{})[n]=str(e)
  report['reset_success']=not report.get('close_errors');report['wall_seconds']=round(time.monotonic()-started,2);report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None;log.write(out/'events.jsonl');put_json(out/'report.json',report)
 print(json.dumps({'status':report['status'],'shared_positive':report.get('controls',{}).get('shared_positive',{}).get('pass'),'ma_id_negative':report.get('controls',{}).get('ma_id_negative',{}).get('pass'),'ma_id_state_isolated':report.get('controls',{}).get('ma_id_negative',{}).get('state_is_off_after_b_other_guest_toggle'),'wall_seconds':report['wall_seconds'],'reset_success':report['reset_success'],'resources':report['resource_lifecycle'],'artifact_dir':str(out),'error':report.get('error')},ensure_ascii=False))
if __name__=='__main__':main()
