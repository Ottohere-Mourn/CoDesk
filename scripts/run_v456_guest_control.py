#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,shutil,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright
REPO=Path('/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112')
OSW=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
SWC=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
sys.path[:0]=[str(REPO),str(SWC),str(OSW)]
from oscombo import combo
from oscombo.osworld import load_task,task_get
ASSETS=Path('/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets')
RUNROOT=Path('/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets')
OVERLAY_TMP=Path('/dev/shm/codesk-next3/overlays')
OVERLAY_ARCHIVE=Path('/mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays')
BASE=Path('/dev/shm/codesk-next3/osworld-v2-ubuntu-x86.qcow2')
TASKS={
'v4':['v2/pgv4rooms','v2/pgv4facilities'],
'v5':['v2/pgv5invoices','v2/pgv5expenses'],
'v6':['v2/pgv6accommodations','v2/pgv6seating'],'v7':['v2/pgv7labcustody','v2/pgv7benchreview'],'v8':['v2/pgv8permitreview','v2/pgv8permitfees'],'v9':['v2/pgv9dispatch','v2/pgv9parts'],'v10':['v2/pgv10followup','v2/pgv10equipment'],'v11':['v2/pgv11holds','v2/pgv11returns'],'v12':['v2/pgv12review','v2/pgv12intake'],'v13':['v2/pgv13catalog','v2/pgv13access'],'v14':['v2/pgv14disposition','v2/pgv14rework'],'v15':['v2/pgv15badge','v2/pgv15induction'],'v16':['v2/pgv16temp','v2/pgv16lot'],'v17':['v2/pgv17condition','v2/pgv17exhibit'],'v18':['v2/pgv18commission','v2/pgv18utility'],'v19':['v2/pgv19housekeeping','v2/pgv19arrival'],'v20':['v2/pgv20exportdocs','v2/pgv20loadplan'],'v21':['v2/pgv21accession','v2/pgv21pickup'],'v22':['v2/pgv22turnover','v2/pgv22techcall']}
PORTS={'v4':8139,'v5':8140,'v6':8141,'v7':8142,'v8':8143,'v9':8144,'v10':8145,'v11':8146,'v12':8147,'v13':8148,'v14':8149,'v15':8150,'v16':8151,'v17':8152,'v18':8153,'v19':8154,'v20':8155,'v21':8156,'v22':8157}
def wait_reload(page,ms=400):
 page.wait_for_timeout(ms)
def choose(page,item):
 page.locator('.item[data-id="'+item+'"]').click(timeout=10000);wait_reload(page)
def panel(page,which):
 page.locator('.tab[data-panel="'+which+'"]').click(timeout=10000);wait_reload(page)
def fill(page,key,value):
 page.locator('#f-'+key).fill(str(value),timeout=10000)
def select(page,key,value):
 page.locator('#f-'+key).select_option(label=str(value),timeout=10000)
def save(page):
 page.locator('#save').click(timeout=10000);page.wait_for_timeout(700)
def generic_form(page,values):
 for key,value in values.items():
  field=page.locator('#f-'+key)
  if field.evaluate('(el)=>el.tagName.toLowerCase()')=='select':field.select_option(label=str(value))
  else:field.fill(str(value))
def positive_control(case,page,expected):
 if case=='v4':
  panel(page,'A')
  rooms={'EV-311':'R-102','EV-312':'R-203','EV-313':'R-204','EV-314':'R-203','EV-315':'R-203'}
  for iid,row in expected['A'].items():
   choose(page,iid);select(page,'room',rooms[iid]);select(page,'time_slot',row['time_slot']);select(page,'setup',row['setup']);save(page)
  panel(page,'B')
  for iid,row in expected['B'].items():
   choose(page,iid);select(page,'status',row['status']);fill(page,'reason',row['reason']);fill(page,'work_order',row['work_order']);save(page)
 elif case=='v5':
  panel(page,'A')
  for iid,row in expected['A'].items():
   choose(page,iid);fill(page,'vendor',row['vendor']);fill(page,'amount',row['amount']);fill(page,'due_date',row['due_date'])
   page.locator('#copy-ref').click();page.locator('#f-invoice_ref').click();page.keyboard.press('Control+V');save(page)
  panel(page,'B')
  for iid,row in expected['B'].items():
   choose(page,iid);fill(page,'employee',row['employee']);fill(page,'amount',row['amount']);fill(page,'cost_center',row['cost_center'])
   page.locator('#copy-ref').click();page.locator('#f-receipt_ref').click();page.keyboard.press('Control+V');save(page)
 elif case=='v6':
  panel(page,'A')
  for iid,row in expected['A'].items():
   choose(page,iid);select(page,'support',row['support']);select(page,'room_type',row['room_type']);fill(page,'approval_ref',row['approval_ref']);save(page)
  panel(page,'B')
  for iid,row in expected['B'].items():
   choose(page,iid);select(page,'room',row['room']);fill(page,'seat',row['seat']);fill(page,'arrival',row['arrival']);select(page,'equipment',row['equipment']);save(page)
 else:
  for which in ('A','B'):
   panel(page,which)
   for iid,row in expected[which].items():
    choose(page,iid);generic_form(page,row);save(page)
def main(case):
 if case not in TASKS:raise SystemExit('usage: run_v456_guest_control.py v4|v5|v6|v7|v8|v9|v10|v11|v12|v13|v14|v15|v16|v17|v18|v19|v20|v21|v22')
 runid=f'cdesk3-{case}-scripted-joint-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{os.getpid()}'
 out=RUNROOT/runid;over=OVERLAY_TMP/runid;archive=OVERLAY_ARCHIVE/runid
 out.mkdir(parents=True,exist_ok=False);over.mkdir(parents=True,exist_ok=False)
 os.environ.update({'OSWORLD_DIR':str(OSW),'PARAGUI_TASK_ASSETS':str(ASSETS),'OSCOMBO_GUEST_IMAGE':str(BASE),
  'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':'swcub/osworld-v2.1-qemu-runtime:local','SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(over),
  'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':os.urandom(32).hex(),'SWCUB_RESOURCE_LEDGER':str(out/'resources/resource_ledger.jsonl'),
  'SWCUB_OSWORLD_VM_READY_TIMEOUT':'600','PYTHONPATH':f'{REPO}:{SWC}:{OSW}'})
 result={'run_id':runid,'case':case,'kind':'scripted_gui_joint_positive','tasks':TASKS[case],'started_utc':datetime.now(timezone.utc).isoformat(),'error':None}
 env=None
 try:
  fixture={}
  for f in sorted((ASSETS/case).rglob('*')):
   if f.is_file():fixture[str(f.relative_to(ASSETS/case))]=hashlib.sha256(f.read_bytes()).hexdigest()
  (out/'fixture.sha256').write_text(''.join(f'{h}  {p}\n' for p,h in sorted(fixture.items())))
  env=combo.boot(str(BASE),str(out/'cache'));tasks=[load_task(t) for t in TASKS[case]]
  result['task_ids_loaded']=[str(task_get(t,'id')) for t in tasks]
  result['setup']=combo.setup_tasks(env,tasks);time.sleep(25)
  guest=__import__('oscombo.guest',fromlist=['Guest']).Guest(env);(out/'start.png').write_bytes(guest.wait_desktop())
  expected=json.loads((ASSETS/case/'expected.json').read_text())
  cdp=f'http://{env.vm_ip}:{getattr(env,"chromium_port",9222)}';version=None
  for _ in range(30):
   try:version=requests.get(cdp+'/json/version',timeout=3).json();break
   except Exception:time.sleep(2)
  if not version:raise RuntimeError('Guest Chrome DevTools endpoint not ready')
  port=PORTS[case];url=f'http://127.0.0.1:{port}/desk'
  with sync_playwright() as pw:
   browser=pw.chromium.connect_over_cdp(cdp);context=browser.contexts[0]
   try:context.grant_permissions(['clipboard-read','clipboard-write'],origin=f'http://127.0.0.1:{port}')
   except Exception:pass
   page=next((p for p in context.pages if f':{port}/' in p.url),context.pages[-1] if context.pages else context.new_page())
   if f':{port}/' not in page.url:page.goto(url)
   page.wait_for_load_state('domcontentloaded');page.wait_for_selector('.tab',timeout=30000)
   positive_control(case,page,expected)
   result['end_url']=page.url;page.screenshot(path=str(out/'end-browser.png'),full_page=True)
   (out/'end.png').write_bytes(guest.screenshot());browser.close()
  result['scores']=combo.evaluate_tasks(env,tasks,[False,False],result);result['status']='complete'
 except Exception as e:
  result['status']='error';result['error']=f'{type(e).__name__}: {e}'[:500];result['traceback']=traceback.format_exc()[-4000:]
  if env:
   try:(out/'failure.png').write_bytes(env.controller.get_screenshot() or b'')
   except Exception:pass
 finally:
  if env:
   try:env.close()
   except Exception as e:result.setdefault('warnings',[]).append(f'close:{type(e).__name__}:{e}'[:200])
  try:
   archive.mkdir(parents=True,exist_ok=True)
   if over.exists():subprocess.run(['cp','-r','--sparse=auto','--no-preserve=all',str(over)+'/.',str(archive)],check=True)
  except Exception as e:result.setdefault('warnings',[]).append(f'overlay_archive:{type(e).__name__}:{e}'[:200])
  result['finished_utc']=datetime.now(timezone.utc).isoformat();(out/'result.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else '')
