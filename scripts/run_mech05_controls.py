#!/usr/bin/env python3
"""MECH-05 Writer Record-Changes mode positive and fixed-interleave controls."""
from __future__ import annotations
import json,os,secrets,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OSW=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
SWC=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
IMAGE=OSW/'docker_vm_data/osworld-v2-ubuntu-x86.qcow2'
ASSETS=Path('/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets')
OUTROOT=Path('/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls')
TASK_A=ROOT/'tasks/mechanism_expansion_v1/task_mech05a.py'
TASK_B=ROOT/'tasks/mechanism_expansion_v1/task_mech05b.py'
sys.path[:0]=[str(ROOT),str(SWC),str(OSW)]
os.environ.update({'OSWORLD_DIR':str(OSW),'PARAGUI_TASK_ASSETS':str(ASSETS),
 'OSCOMBO_GUEST_IMAGE':str(IMAGE),'SWCUB_OSWORLD_GUEST_IMAGE':str(IMAGE),
 'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':'swcub/osworld-v2.1-qemu-runtime:local',
 'OSWORLD_DOCKER_RUNTIME_IMAGE':'swcub/osworld-v2.1-qemu-runtime:local',
 'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(OUTROOT/'overlays'),
 'SWCUB_OSWORLD_CACHE_DIR':str(OUTROOT/'osworld-cache')})
from oscombo import combo
from oscombo.guest import Guest
from oscombo.osworld import load_task
from swcub.resource_safety import ensure_resource_identity
from tasks.mechanism_expansion_v1 import mech05 as pair

def cmd(g,script,timeout=60):
 r=g.execute(['bash','-lc',script],timeout)
 return (r.get('output') or '')+(r.get('error') or '')
def screenshot(g,out,name): (out/name).write_bytes(g.screenshot(patience=90))
def toggle_record_changes(g):
 # Use the visible Edit > Track Changes > Record menu. Guest X display is 1920x1080.
 cmd(g,'xdotool key --clearmodifiers alt+e; sleep .35; xdotool mousemove --sync 190 430 click 1; sleep .35; xdotool mousemove --sync 465 430 click 1; sleep .8')
def replace_text(g,old,new):
 cmd(g,'xdotool key --clearmodifiers ctrl+Home; sleep .2')
 # Find leaves the matching text selected; typing replaces only that occurrence.
 cmd(g,'xdotool key --clearmodifiers ctrl+f; sleep .3')
 cmd(g,"xdotool type --clearmodifiers --delay 4 '"+old+"'; xdotool key Return; sleep .4; xdotool key Escape; sleep .3")
 cmd(g,"xdotool type --clearmodifiers --delay 3 '"+new+"'; sleep .8; xdotool key ctrl+s; sleep 4")
def state(g): return {r:pair.evaluate(g.env,r) for r in ('A','B')}
def reset_docs(g,controller):
 cmd(g,'xdotool key ctrl+q; sleep 2; pkill -x soffice.bin 2>/dev/null || true; sleep 2')
 cmd(g,f'cp {pair.WORK}/baseline/access-review-draft.odt {pair.ODT}')
 key=f"{getattr(controller,'vm_ip','')}:{getattr(controller,'server_port','')}"
 pair._SETUP.discard(key); pair.setup(controller,'A'); time.sleep(3)
def main():
 runid='mech05-guest-control-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+str(os.getpid())
 out=OUTROOT/runid; out.mkdir(parents=True,exist_ok=False); (out/'overlays').mkdir()
 os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(out/'resource-events.jsonl')})
 os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None); ensure_resource_identity(out/'resource-events.jsonl')
 env=None; report={'run_id':runid,'case_id':'MECH-05 TRACK-CHANGES-MODE','task_version':pair.TASK_VERSION,'control_version':'0.1.0','kind':'scripted_gui_controls','model_used':False,'status':'starting','external_containers_stopped':False}
 try:
  tasks=[load_task(str(TASK_A)),load_task(str(TASK_B))]
  env=combo.boot(str(IMAGE),str(out/'cache')); report['setup']=combo.setup_tasks(env,tasks)
  time.sleep(4); g=Guest(env); controller=env.setup_controller; screenshot(g,out,'initial.png')
  # Positive control: A correctly enables tracking before editing; B switches it off before final copy.
  toggle_record_changes(g); report['positive_a_record_mode_on']=True; screenshot(g,out,'positive-record-on.png')
  replace_text(g,pair.A_OLD,pair.A_NEW); screenshot(g,out,'positive-after-a.png')
  toggle_record_changes(g); report['positive_b_record_mode_off']=True; screenshot(g,out,'positive-record-off.png')
  replace_text(g,pair.B_OLD,pair.B_NEW); report['positive_state']=state(g); screenshot(g,out,'positive-final.png')
  report['positive_joint_pass']=all(report['positive_state'][r]['score']==1.0 for r in ('A','B'))
  if not report['positive_joint_pass']: raise AssertionError('Positive GUI control did not preserve A tracked / B plain semantics')
  # Fixed mechanism control: B legitimately resets the shared mode before A's pending entry.
  reset_docs(g,controller); screenshot(g,out,'negative-reset.png')
  toggle_record_changes(g); report['negative_a_enabled_tracking']=True; screenshot(g,out,'negative-a-enabled.png')
  toggle_record_changes(g); report['negative_b_disabled_tracking_before_own_edit']=True; screenshot(g,out,'negative-b-disabled.png')
  replace_text(g,pair.B_OLD,pair.B_NEW); screenshot(g,out,'negative-after-b.png')
  replace_text(g,pair.A_OLD,pair.A_NEW); screenshot(g,out,'negative-final-before-save.png')
  cmd(g,'xdotool key ctrl+s; sleep 4'); report['negative_state']=state(g); screenshot(g,out,'negative-final.png')
  a=report['negative_state']['A']; b=report['negative_state']['B']
  report['fixed_track_changes_toggle_race']=(a['score']==0.0 and b['score']==1.0 and not a['checks'].get('approval_change_tracked') and b['checks'].get('contact_is_plain_final_text'))
  report['status']='passed' if report['fixed_track_changes_toggle_race'] else 'invalid_control_oracle'
 except Exception as e:
  report['status']='invalid_infra_or_control_failure'; report['error']=f'{type(e).__name__}: {e}'; report['traceback']=traceback.format_exc()[-5000:]
 finally:
  report['guest_close_succeeded']=False; report['owned_guest_destroyed']=False
  if env:
   try: env.close(); report['guest_close_succeeded']=True
   except Exception as e: report['close_error']=str(e)
  try:
   ev=[json.loads(l) for l in (out/'resource-events.jsonl').read_text().splitlines() if l.strip()]
   report['owned_guest_destroyed']=any(x.get('event')=='destroyed' and x.get('resource_type')=='container' for x in ev)
  except Exception: pass
  (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'status':report['status'],'positive_joint_pass':report.get('positive_joint_pass'),'fixed_track_changes_toggle_race':report.get('fixed_track_changes_toggle_race'),'artifacts':str(out),'error':report.get('error')},ensure_ascii=False))
 return 0 if report['status']=='passed' else 1
if __name__=='__main__': raise SystemExit(main())
