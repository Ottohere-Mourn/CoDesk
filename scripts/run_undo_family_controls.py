#!/usr/bin/env python3
"""Real Guest scripted positive and fixed-interleaving controls for MECH-06..09."""
from __future__ import annotations
import json, os, re, secrets, sys, time, traceback, shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OSW=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
SWC=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
IMAGE=OSW/'docker_vm_data/osworld-v2-ubuntu-x86.qcow2'
ASSETS=ROOT/'task_assets'
OUTROOT=Path('/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/undo-family')
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
from tasks.mechanism_expansion_v1 import undo_family as family

def cmd(g, script, timeout=60):
 r=g.execute(['bash','-lc',script],timeout)
 return (r.get('output') or '')+(r.get('error') or '')
def screenshot(g,out,name):
 (out/name).write_bytes(g.screenshot(patience=90))
def goto_cell(g,address):
 if not re.fullmatch(r'[A-Z]+[0-9]+',address): raise ValueError(f'bad cell address: {address}')
 letters=re.match(r'[A-Z]+',address).group(0); col=0
 for ch in letters: col=col*26+ord(ch)-64
 row=int(re.search(r'[0-9]+$',address).group(0))
 x=150+83*(col-1); y=314+18*(row-1)
 cmd(g,f'xdotool mousemove --sync {x} {y} click 1; sleep .3')

def enter_cell(g,address,value):
 goto_cell(g,address)
 cmd(g,'xdotool type --clearmodifiers --delay 15 '+shlex.quote(str(value))+'; xdotool key Return; sleep .3')
def save(g): cmd(g,'xdotool key ctrl+s; sleep 4')
def state(env,cid): return {r:family.evaluate(env,cid,r) for r in ('A','B')}
def stage_seed(g,s):
 address=f'{chr(65+s["a_temp_col"])}2'
 enter_cell(g,address,s["a_temp"])
 cmd(g,'xdotool key Up; sleep .3')
def reset_docs(g,controller,cid):
 spec=family.CASES[cid]; dest=f"{spec['work']}/{spec['file']}"; base=f"{spec['work']}/baseline/{spec['file']}"
 # Terminate the prior LibreOffice process before replacing its open document;
 # otherwise a stale in-memory copy can survive a filesystem reset.
 cmd(g,'xdotool key ctrl+q; sleep 1; pkill -9 -x soffice.bin 2>/dev/null || true; pkill -9 -x soffice 2>/dev/null || true; sleep 2; if pgrep -x soffice.bin >/dev/null; then echo STALE_CALC_PROCESS; exit 1; fi')
 cmd(g,f'cp {shlex.quote(base)} {shlex.quote(dest)}; setsid -f libreoffice --calc {shlex.quote(dest)} >/tmp/{cid}-calc.log 2>&1 < /dev/null')
 cmd(g,family._window_script(Path(spec['file']).stem),timeout=45); time.sleep(2)
 stage_seed(g,spec)
def case_run(cid):
 spec=family.CASES[cid]
 runid=f'{cid}-undo-controls-{time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())}-{os.getpid()}'
 out=OUTROOT/runid; out.mkdir(parents=True,exist_ok=False); (out/'overlays').mkdir()
 os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),
  'SWCUB_RESOURCE_LEDGER':str(out/'resource-events.jsonl')})
 os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None); ensure_resource_identity(out/'resource-events.jsonl')
 env=None
 report={'run_id':runid,'case_id':cid.upper(),'task_version':family.TASK_VERSION,'kind':'scripted_gui_controls',
  'control_version':'0.3.0','model_used':False,'status':'starting','external_containers_stopped':False,
   'initial_gui_precondition':{'staged_cell':f'{chr(65+spec["a_temp_col"])}2','staged_value':spec["a_temp"],'unsaved_before_actor_start':True},
  'positive_sequence':['stages A edit','A verifies listed row cells','A Ctrl+Z and verifies baseline','A review marker/save','B target field/save'],
  'negative_sequence':['stages A edit','B target field/save','A verifies listed row cells','A Ctrl+Z and verifies baseline','A review marker/save']}
 try:
  tasks=[load_task(str(ROOT/f'tasks/mechanism_expansion_v1/task_{cid}a.py')),
         load_task(str(ROOT/f'tasks/mechanism_expansion_v1/task_{cid}b.py'))]
  env=combo.boot(str(IMAGE),str(out/'cache-positive'))
  report['setup']=combo.setup_tasks(env,tasks)
  time.sleep(5); g=Guest(env); controller=env.setup_controller
  screenshot(g,out,'initial.png'); report['initial_state']=state(env,cid)
  # Positive control follows the v0.5 A checklist before Undo.
  for col in spec['a_verify_cols']: goto_cell(g,f'{chr(65+col)}2')
  cmd(g,'xdotool key --clearmodifiers ctrl+z; sleep .6')
  goto_cell(g,f'{chr(65+spec["a_temp_col"])}2'); save(g)
  enter_cell(g,f'{chr(65+spec["a_mark_col"])}2',spec['a_mark']); save(g)
  for col,value in spec['b_values'].items(): enter_cell(g,f'{chr(65+col)}3',value)
  save(g); report['positive_state']=state(env,cid); screenshot(g,out,'positive-final.png')
  report['positive_joint_pass']=all(report['positive_state'][r]['score']==1.0 for r in ('A','B'))
  if not report['positive_joint_pass']: raise AssertionError('positive control failed one or both task oracles')
  # Use a fresh Guest for the negative interleave. This avoids in-place
  # LibreOffice restart ambiguity and recreates the staged precondition from
  # the same immutable base file.
  report['positive_guest_closed']=False
  env.close(); report['positive_guest_closed']=True; env=None
  tasks=[load_task(str(ROOT/f'tasks/mechanism_expansion_v1/task_{cid}a.py')),
         load_task(str(ROOT/f'tasks/mechanism_expansion_v1/task_{cid}b.py'))]
  env=combo.boot(str(IMAGE),str(out/'cache-negative'))
  report['negative_setup']=combo.setup_tasks(env,tasks)
  time.sleep(5); g=Guest(env)
  screenshot(g,out,'negative-initial.png')
  report['negative_initial_state']=state(env,cid)
  for col,value in spec['b_values'].items(): enter_cell(g,f'{chr(65+col)}3',value)
  save(g); report['negative_before_undo']=state(env,cid); screenshot(g,out,'negative-before-undo.png')
  for col in spec['a_verify_cols']: goto_cell(g,f'{chr(65+col)}2')
  cmd(g,'xdotool key --clearmodifiers ctrl+z; sleep .7')
  goto_cell(g,f'{chr(65+spec["a_temp_col"])}2'); save(g)
  enter_cell(g,f'{chr(65+spec["a_mark_col"])}2',spec['a_mark']); save(g)
  report['negative_state']=state(env,cid); screenshot(g,out,'negative-final.png')
  a=report['negative_state']['A']; b=report['negative_state']['B']
  report['negative_mechanism_observed']=(
   report['negative_before_undo']['B']['checks']['b_target_fields_saved'] and
   a['checks'].get('temporary_edit_undone') is False and
   b['checks'].get('b_target_fields_saved') is False)
  report['status']='passed' if report['negative_mechanism_observed'] else 'invalid_control_oracle'
 except Exception as e:
  report['status']='invalid_infra_or_control_failure'; report['error']=f'{type(e).__name__}: {e}'
  report['traceback']=traceback.format_exc()[-5000:]
 finally:
  report['guest_close_succeeded']=False; report['owned_guest_destroyed']=False
  if env:
   try: env.close(); report['guest_close_succeeded']=True
   except Exception as e: report['close_error']=str(e)
  try:
   events=[json.loads(x) for x in (out/'resource-events.jsonl').read_text().splitlines() if x.strip()]
   report['owned_guest_destroyed']=any(x.get('event')=='destroyed' and x.get('resource_type')=='container' for x in events)
  except Exception: pass
  (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'case_id':cid,'status':report['status'],'positive_joint_pass':report.get('positive_joint_pass'),
  'negative_mechanism_observed':report.get('negative_mechanism_observed'),'artifacts':str(out),
  'error':report.get('error')},ensure_ascii=False))
 return report

def main():
 OUTROOT.mkdir(parents=True,exist_ok=True)
 selected=sys.argv[1:] or list(family.CASES)
 reports=[]
 for cid in selected:
  if cid not in family.CASES: raise SystemExit(f'unknown case {cid}')
  import shutil
  if shutil.disk_usage('/').free < 19*1024**3:
   raise SystemExit('root free space below 19 GiB; refusing Guest start')
  reports.append(case_run(cid))
  if reports[-1]['status']!='passed': break
 print(json.dumps({'summary':{r['case_id']:r['status'] for r in reports},'all_passed':len(reports)==len(selected) and all(r['status']=='passed' for r in reports)},ensure_ascii=False))
 return 0 if len(reports)==len(selected) and all(r['status']=='passed' for r in reports) else 1
if __name__=='__main__': raise SystemExit(main())
