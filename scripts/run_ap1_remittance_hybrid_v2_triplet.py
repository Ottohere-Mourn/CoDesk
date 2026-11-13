#!/usr/bin/env python3
"""GPT-6-Sol AP-1 remittance workflow Hybrid v2 triplet."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, secrets, shlex, subprocess, sys, threading, time, uuid
from pathlib import Path

ROOT=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
IMAGE=Path('/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2')
RUNTIME='swcub/osworld-v2.1-qemu-runtime:local'
ARTIFACT_ROOT=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/ap1-remittance-hybrid-v2')
MODEL='gpt-6-sol'
TASK_ID='AP1-REMITTANCE'
TASK_VERSION='0.2.1-hybrid-v2-preparer-credit-handoff'
BUDGET=30
TOKEN_BUDGET=16000
ARMS=('ma_id','ma_sd','ma_sd_lock')
APP=ROOT/'scripts'/'ap1_remittance_app_v2.py'
FIXTURE=ROOT/'scripts'/'ap1_remittance_fixture_v2.py'
EVAL=ROOT/'scripts'/'ap1_remittance_eval_v2.py'
STATE='/tmp/ap1-v021/state.json'
APP_ROOT='/tmp/ap1-v021/project'
PROMPTS={
'A':"""You are the AP remittance preparer for synthetic remittance RA-221 from NORTHWIND-SYN. Use the restricted Guest CLI to read RA-221.txt, SUPPLIER-STMT-221.txt, and DISPUTE-33.txt. Reconcile the current ledger as shown in the preparer page: include eligible INV-AP-071, INV-AP-072, and INV-AP-073 at their current open balances; exclude disputed INV-AP-074 and keep the PRICE_MISMATCH exception with reference DISPUTE-33. CN-AP-019 is approved but currently unapplied; do not apply it, and do not net an unapplied credit into this draft. In the GUI, mark the source documents reviewed, save a READY local payment draft at the current ledger revision, and send Actor B a handoff with the total and exception. Do not release or export a payment.""",
'B':"""You are the AP credit clerk for the same synthetic NORTHWIND-SYN remittance RA-221. Read CN-AP-019.txt using the restricted Guest CLI. In the GUI, apply approved credit memo CN-AP-019 exactly once for 25,000 cents to INV-AP-071. Verify its resulting open balance is 95,000 cents and notify Actor A that the credit was applied. Respect role separation: do not edit or rebuild the preparer's payment draft; the preparer owns that artifact. Do not release or export a payment."""
}
PROMPT_SHA={a:hashlib.sha256(t.encode()).hexdigest() for a,t in PROMPTS.items()}
ASSET_SHA={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (APP,FIXTURE,EVAL)}
FIXTURE_SHA=hashlib.sha256(''.join(f'{k}:{v}\n' for k,v in sorted(ASSET_SHA.items())).encode()).hexdigest()
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
for k,v in {'OSWORLD_V2_DIR':str(OSWORLD),'SWCUB_OSWORLD_GUEST_IMAGE':str(IMAGE),
 'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME,'OSWORLD_DOCKER_RUNTIME_IMAGE':RUNTIME}.items():os.environ.setdefault(k,v)
from scripts import run_writer_calc_v1 as base
from scripts import ap1_remittance_fixture_v2 as fx
from scripts.ap1_remittance_eval_v2 import evaluate_store
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor,_start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore,make_server
from oscombo.harness.hybrid_v2 import MCP_PYTHON,MCP_SITE
from swcub.resource_safety import ensure_resource_identity

def _json(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def _preflight(parent):
 import shutil
 if not APP.is_file() or not FIXTURE.is_file() or not EVAL.is_file():raise RuntimeError('AP-1 Guest app assets missing')
 if shutil.disk_usage('/').free<24*1024**3:raise RuntimeError('root free below 24 GiB')
 if shutil.disk_usage('/mnt/raid1').free<100*1024**3:raise RuntimeError('RAID1 free below 100 GiB')
 mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
 if mem<20*1024**3:raise RuntimeError('MemAvailable below 20 GiB')
 if not parent.is_relative_to(Path('/mnt/raid1')):raise RuntimeError('artifacts must be on RAID1')
 if subprocess.run(['docker','ps','-q'],capture_output=True,text=True,timeout=20,check=True).stdout.strip():raise RuntimeError('active Docker container; refusing Guest')
 if not IMAGE.is_file() or subprocess.run(['docker','image','inspect',RUNTIME],capture_output=True,timeout=20).returncode:raise RuntimeError('pinned Guest/runtime missing; no pull')
 if not os.environ.get('SWCUB_SOL_API_KEY'):raise RuntimeError('SWCUB_SOL_API_KEY absent; no Guest/model started')
def _env(out,runid):
 (out/'overlays').mkdir(parents=True,exist_ok=True);ledger=out/'resource-events.jsonl'
 os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),
   'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),
   'OSWORLD_V2_DIR':str(OSWORLD)})
 os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
 return ledger,ensure_resource_identity(ledger)
def _write_guest(ep,dest,content,label,readonly=False):
 encoded=base64.b64encode(content.encode('utf-8')).decode('ascii')
 py='from pathlib import Path;import base64;p=Path('+repr(dest)+');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode('+repr(encoded)+'))'+(';p.chmod(0o444)' if readonly else '')
 ep.cli_action(label,'python3 -c '+shlex.quote(py))
def _setup_guest(ep,d,binding,out,runid,shared):
 for path in (APP,FIXTURE):
  _write_guest(ep,APP_ROOT+'/scripts/'+path.name,path.read_text(encoding='utf-8'),'ap1_install_'+path.stem,readonly=True)
 _write_guest(ep,APP_ROOT+'/scripts/__init__.py','','ap1_install_package_marker',readonly=True)
 app_log='/tmp/ap1-v021/app.log'
 argv=['/usr/bin/python3','-m','scripts.ap1_remittance_app_v2','--host','127.0.0.1','--port','8765','--state',STATE]
 spawn='import subprocess;subprocess.Popen('+repr(argv)+',cwd='+repr(APP_ROOT)+',stdin=subprocess.DEVNULL,stdout=open('+repr(app_log)+',\'ab\'),stderr=subprocess.STDOUT,start_new_session=True);print(\'started\')'
 ep.cli_action('ap1_app_start','python3 -c '+shlex.quote(spawn))
 health='';deadline=time.monotonic()+25
 while time.monotonic()<deadline:
  try:health=base.guest_command(d,['curl','--noproxy','*','-fsS','--max-time','2','http://127.0.0.1:8765/health'],5)
  except Exception:time.sleep(.5);continue
  if '"ok":true' in health:break
  time.sleep(.5)
 if '"ok":true' not in health:raise RuntimeError('AP-1 Guest app failed health check: '+health[:200])
 browser=base.guest_command(d,['bash','-lc','command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE'],10).strip().splitlines()[-1]
 if browser=='NONE':raise RuntimeError('Chromium unavailable in pinned Guest')
 launch='nohup '+shlex.quote(browser)+' --no-sandbox --start-maximized --no-first-run --no-default-browser-check --disable-dev-shm-usage --disable-extensions --disable-background-networking --no-proxy-server --user-data-dir=/tmp/ap1-v021/chrome --new-window http://127.0.0.1:8765/preparer >/tmp/ap1-v021/browser.log 2>&1 </dev/null &'
 ep.cli_action('ap1_browser_start','bash -lc '+shlex.quote(launch))
 if shared:
  ep.cli_action('ap1_cli_roots','mkdir -p /tmp/ap1-v021-cli-A /tmp/ap1-v021-cli-B')
 else:
  ep.cli_action('ap1_cli_root_'+binding,'mkdir -p '+shlex.quote('/tmp/ap1-v021-cli-'+binding[-1]))
 actor=binding[-1] if binding!='shared' else 'both'
 if binding=='shared':
  for a in ('A','B'):
   docs=('RA-221','SUPPLIER-STMT-221','DISPUTE-33') if a=='A' else ('CN-AP-019',)
   for doc in docs:_write_guest(ep,f'/tmp/ap1-v021-cli-{a}/{doc}.txt',fx.SOURCE_DOCS[doc],'ap1_source_'+a+'_'+doc,readonly=True)
 else:
  docs=('RA-221','SUPPLIER-STMT-221','DISPUTE-33') if actor=='A' else ('CN-AP-019',)
  for doc in docs:_write_guest(ep,f'/tmp/ap1-v021-cli-{actor}/{doc}.txt',fx.SOURCE_DOCS[doc],'ap1_source_'+actor+'_'+doc,readonly=True)
 shot_env=os.environ.copy()
 log=out/'readiness'/binding/'desktop_mcp'/'actions.jsonl';log.parent.mkdir(parents=True,exist_ok=True)
 shot_env.update({'OSCOMBO_GUEST_URL':f'http://{d.vm_ip}:{d.server_port}','OSCOMBO_ACTION_LOG':str(log),
  'OSCOMBO_MAX_STEPS':'3','OSCOMBO_ACTOR_ID':'setup','OSCOMBO_EPISODE_ID':runid+'-'+binding+'-setup',
  'OSCOMBO_GUEST_KEY':binding,'OSCOMBO_CONDITION':'collaborative_shared_lock' if os.environ.get('AP1_LOCKED')=='1' else 'collaborative_shared',
  'PYTHONPATH':os.pathsep.join(x for x in (MCP_SITE,str(HYBRID),str(ROOT),str(OSWORLD),os.environ.get('PYTHONPATH','')) if x)})
 if os.environ.get('AP1_LOCKED')=='1':shot_env['OSCOMBO_ACTION_LOCK_FILE']=str(out/'locks'/'gui-actions.lock')
 cp=subprocess.run([MCP_PYTHON,'-m','oscombo.desktop_tools','screenshot','{}'],env=shot_env,capture_output=True,text=True,timeout=90)
 if cp.returncode:raise RuntimeError('AP-1 production GUI MCP readiness failed: '+cp.stderr[-600:])
 obj=json.loads(cp.stdout)
 if obj.get('error') or not obj.get('image'):raise RuntimeError('AP-1 GUI MCP readiness screenshot missing')
 png=base64.b64decode(obj['image']);shot=out/'readiness'/binding/'screenshots'/'ap1-preparer.png';shot.parent.mkdir(parents=True,exist_ok=True);shot.write_bytes(png)
 from PIL import Image,ImageStat
 import io
 im=Image.open(io.BytesIO(png)).convert('RGB')
 if im.width<1000 or im.height<600 or max(ImageStat.Stat(im).stddev)<8:raise RuntimeError('AP-1 readiness screenshot blank')
 initial=_read_state(d)
 if initial.get('core')!=fx.fresh_state() or initial.get('reviewed_source_ids'):raise RuntimeError('AP-1 clean initial state mismatch')
 return {'binding':binding,'health':health,'browser':browser,'app_state_path':STATE,
   'initial_state_sha256':hashlib.sha256(json.dumps(initial,sort_keys=True).encode()).hexdigest(),
   'visible_gui_screenshot':str(shot),'screenshot_dimensions':[im.width,im.height],
   'screenshot_stddev':ImageStat.Stat(im).stddev,'guest_id':ep.snapshot().get('guest_container_id')}
def _read_state(d):
 raw=base.guest_command(d,['cat',STATE],timeout=20)
 return json.loads(raw)
def _actions(out,actor):
 p=out/'actor_runs'/actor/actor/'actions.jsonl';rows=[]
 if p.exists():
  for line in p.read_text(encoding='utf-8').splitlines():
   try:rows.append(json.loads(line))
   except json.JSONDecodeError:pass
 return rows
def _relay_count(out,actor):
 p=out/'actor_runs'/actor/'codex_relay_events.jsonl';n=0
 if p.exists():
  for line in p.read_text(encoding='utf-8').splitlines():
   try:e=json.loads(line)
   except json.JSONDecodeError:continue
   n+=bool(e.get('request_json') and e.get('upstream_status')==200 and e.get('model')==MODEL)
 return n
def _run(args):
 endpoint=(os.environ.get('CODESK_SOL_ENDPOINT') or 'https://docode.cc/v1').rstrip('/')
 if not endpoint.startswith('https://'):raise RuntimeError('Sol endpoint must use HTTPS')
 parent=args.artifact_parent.expanduser().resolve();_preflight(parent);out=parent/args.run_id
 if out.exists():raise FileExistsError(out)
 baseline=None
 if args.condition!='ma_id':
  if not args.baseline_report or not args.baseline_report.is_file():raise RuntimeError('shared arms require successful MA-ID baseline')
  baseline=json.loads(args.baseline_report.read_text(encoding='utf-8'))
  if not (baseline.get('task_id')==TASK_ID and baseline.get('task_version')==TASK_VERSION and baseline.get('condition')=='ma_id'
   and baseline.get('fixture_sha256')==FIXTURE_SHA and baseline.get('prompt_sha256')==PROMPT_SHA
   and baseline.get('valid_model_run') is True and baseline.get('task_success') is True and baseline.get('reset_success') is True
   and baseline.get('model',{}).get('model')==MODEL):raise RuntimeError('matched successful MA-ID report rejected')
 out.mkdir(parents=True,exist_ok=False)
 for x in ('actor_runs','collaboration','guest-artifacts','readiness','locks'):(out/x).mkdir(parents=True,exist_ok=True)
 os.environ['SWCUB_OSWORLD_CACHE_DIR']=str(parent/'osworld-cache')
 ledger,ident=_env(out,args.run_id);log=base.EventLog();shared=args.condition!='ma_id';locked=args.condition=='ma_sd_lock'
 report={'run_id':args.run_id,'task_id':TASK_ID,'task_version':TASK_VERSION,
  'candidate':'AP-1 remittance preparation followed by approved-credit posting',
  'condition':args.condition,'runtime_profile':'gui-cli-mcp-v2','actor_implementation':'reused CodexHarness / Codex CLI 0.155.0',
  'model':{'model':MODEL,'endpoint':endpoint,'effort':'medium','request_retries':5,'steps_per_actor':BUDGET,'output_token_budget_per_actor':TOKEN_BUDGET},
  'tool_permissions':['GUI MCP','restricted Guest CLI MCP','Collaboration MCP'],
  'asset_sha256':ASSET_SHA,'fixture_sha256':FIXTURE_SHA,'prompt_sha256':PROMPT_SHA,'task_prompts':PROMPTS,
  'schedule':'same sequential order A preparer then B credit clerk in every arm; no simultaneous native actions',
  'lock_semantics':{'enabled':locked,'scope':'production fcntl lock on each GUI/Guest CLI MCP action',
   'interpretation':'does not make the draft-save to later credit-post interval one atomic business transaction'},
  'bindings':{'A':'private_A','B':'private_B'} if not shared else {'A':'shared','B':'shared'},
  'baseline_run_id':baseline.get('run_id') if baseline else None,'guest_setup':{},'actor_results':{},
  'handoff_state':{},'final_states':{},'evaluations':{},'tool_usage':{},'model_calls':{},
  'valid_model_run':False,'task_success':False,'reset_success':False}
 eps={};desks={};relays=[];server=None;statuses={};state_a_handoff=None;started=time.monotonic()
 try:
  image_id=subprocess.run(['docker','image','inspect',RUNTIME,'--format','{{.Id}}'],capture_output=True,text=True,check=True,timeout=15).stdout.strip()
  report['runtime']={'runtime_image':RUNTIME,'runtime_image_id':image_id,'guest_image':str(IMAGE)}
  store=ProtocolStore(out/'collaboration',args.run_id);tokens={a:secrets.token_urlsafe(32) for a in ('A','B')}
  server=make_server(store,tokens);threading.Thread(target=server.serve_forever,daemon=True).start();token_env={}
  for a in ('A','B'):
   name='AP1_COLLAB_'+a+'_'+uuid.uuid4().hex[:8].upper();os.environ[name]=tokens[a];token_env[a]=name
  def make_binding(binding):
   ep,d=base.make_desktop(binding,log,out/'guest-artifacts'/binding,require_a11y_tree=False)
   eps[binding]=ep;desks[binding]=d;d.guest_key=binding
   report['guest_setup'][binding]=_setup_guest(ep,d,binding,out,args.run_id,shared)
   return ep,d
  def close_binding(binding,ep):
   try:ep.copy_artifacts(out/'guest-artifacts'/binding)
   except Exception as exc:report.setdefault('artifact_errors',[]).append(f'{binding}: {exc}')
   try:ep.close()
   except Exception as exc:report.setdefault('close_errors',[]).append(f'{binding}: {exc}')
   eps.pop(binding,None);desks.pop(binding,None)
  def run_actor(actor,binding,ep,d):
   actor_dir=out/'actor_runs'/actor;actor_dir.mkdir(parents=True,exist_ok=True)
   relay_env='AP1_RELAY_'+actor+'_'+uuid.uuid4().hex[:8].upper();os.environ[relay_env]=secrets.token_urlsafe(32)
   relay,url=_start_codex_compat_relay(actor_dir,endpoint,'SWCUB_SOL_API_KEY',os.environ[relay_env],relay_env,
     output_token_budget=TOKEN_BUDGET,response_token_cap=2048,reserve_on_missing_usage=True);relays.append(relay)
   from oscombo.guest import Guest
   guest=Guest(d);guest.guest_key=binding;guest.actor=actor
   cli_root=f'/tmp/ap1-v021-cli-{actor}'
   lock=str(out/'locks'/'gui-actions.lock') if locked else None
   return _run_model_actor(actor,guest,PROMPTS[actor],out,MODEL,url,'SWCUB_SOL_API_KEY',MCP_PYTHON,
     f'http://127.0.0.1:{server.server_port}',token_env[actor],max_steps=BUDGET,effort='medium',timeout=3500,
     request_retries=5,tool_cooldown_sec=0.0,relay_client_token_env=relay_env,hybrid_v2=True,
     condition='collaborative_shared_lock' if locked else 'collaborative_shared' if shared else 'collaborative_isolated',
     episode_id=args.run_id+'-'+actor,cli_root=cli_root,action_lock_file=lock,
     task_id=TASK_ID+'@'+TASK_VERSION,desktop_tool_timeout_sec=3600)
  final_states={}
  if shared:
   binding='shared';ep,d=make_binding(binding)
   statuses['A']=run_actor('A',binding,ep,d);state_a_handoff=_read_state(d)
   report['handoff_state']={'A':state_a_handoff}
   statuses['B']=run_actor('B',binding,ep,d);final_states['shared']=_read_state(d)
   close_binding(binding,ep)
   a_handoff=evaluate_store(state_a_handoff,'preparer');b_final=evaluate_store(final_states['shared'],'credit')
   joint=evaluate_store(final_states['shared'],'shared')
   report['evaluations']={'A_at_handoff':a_handoff,'B_after_credit':b_final,
      'final_shared_joint':joint,'draft_stale_signature':{
       'source_revision':final_states['shared']['core']['payment_draft'].get('source_revision'),
       'ledger_revision':final_states['shared']['core'].get('ledger_revision'),
       'actual_total_cents':final_states['shared']['core']['payment_draft'].get('total_cents'),
       'expected_current_total_cents':fx.expected_total(final_states['shared']['core'])}}
   success=bool(a_handoff.get('success') and b_final.get('success') and joint.get('actor_a',{}).get('success') and joint.get('actor_b',{}).get('success'))
  else:
   for actor in ('A','B'):
    binding='private_'+actor;ep,d=make_binding(binding)
    statuses[actor]=run_actor(actor,binding,ep,d);state=_read_state(d);final_states[binding]=state
    if actor=='A':state_a_handoff=state;report['handoff_state']={'A':state}
    close_binding(binding,ep)
   a_final=evaluate_store(final_states['private_A'],'preparer');b_final=evaluate_store(final_states['private_B'],'credit')
   report['evaluations']={'A_private':a_final,'B_private':b_final}
   success=bool(a_final.get('success') and b_final.get('success'))
  report['actor_results']=statuses;report['final_states']=final_states
  rows={a:_actions(out,a) for a in ('A','B')}
  report['tool_usage']={a:{'calls':len(rows[a]),'by_tool':{t:sum(r.get('tool')==t for r in rows[a]) for t in sorted({r.get('tool','unknown') for r in rows[a]})},
     'tools':[r.get('tool') for r in rows[a]]} for a in ('A','B')}
  cp=out/'collaboration'/'events.jsonl';report['collaboration_events']=[]
  if cp.exists():
   for line in cp.read_text(encoding='utf-8').splitlines():
    try:report['collaboration_events'].append(json.loads(line))
    except json.JSONDecodeError:pass
  actor_ok=all(statuses.get(a,{}).get('status') in {'done','max_steps','fail'} for a in ('A','B'))
  report['model_calls']={a:_relay_count(out,a) for a in ('A','B')}
  report['model_call_evidence']='Codex relay successful GPT-6-Sol upstream request_json records'
  report['model_used']=any(report['model_calls'].values());report['task_success']=bool(success)
  report['valid_model_run']=bool(actor_ok and report['model_used'] and all(report['model_calls'].get(a,0)>0 for a in ('A','B')))
  report['condition_classification']=('MA-ID_PASS' if args.condition=='ma_id' and success else
   'MA-ID_FAIL' if args.condition=='ma_id' and report['valid_model_run'] else
   'Shared_FAIL' if args.condition=='ma_sd' and report['valid_model_run'] and not success else
   'Shared_PASS' if args.condition=='ma_sd' and report['valid_model_run'] and success else
   'Shared+Lock_FAIL' if locked and report['valid_model_run'] and not success else
   'Shared+Lock_PASS' if locked and report['valid_model_run'] and success else 'INVALID')
  report['status']='completed' if report['valid_model_run'] else 'invalid_model_or_protocol'
 except KeyboardInterrupt:
  report['status']='invalid_setup_or_runtime';report['error']={'type':'KeyboardInterrupt','message':'Interrupted before valid completion; not a task failure.'}
  report['valid_model_run']=False;report['task_success']=False
 except Exception as exc:
  report['status']='invalid_setup_or_runtime';report['error']={'type':type(exc).__name__,'message':str(exc)}
 finally:
  for binding,ep in list(eps.items()):close_binding(binding,ep)
  for proc in relays:
   try:proc.terminate();proc.wait(timeout=8)
   except Exception:
    try:proc.kill()
    except Exception:pass
  if server is not None:
   try:server.shutdown();server.server_close()
   except Exception:pass
  try:
   from swcub.resource_safety import cleanup_docker_cli_container
   events=[json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
   created={e.get('resource_id') for e in events if e.get('event')=='created' and e.get('resource_type')=='container'}
   destroyed={e.get('resource_id') for e in events if e.get('event')=='destroyed' and e.get('resource_type')=='container'}
   for cid in sorted(created-destroyed):
    try:cleanup_docker_cli_container(cid,ident,reason='runner_finally_owned_orphan_cleanup')
    except Exception as exc:report.setdefault('orphan_cleanup_errors',[]).append(f'{cid}: {type(exc).__name__}: {exc}')
  except Exception as exc:report.setdefault('orphan_cleanup_errors',[]).append(f'{type(exc).__name__}: {exc}')
  report['wall_seconds']=round(time.monotonic()-started,2)
  try:report['resource_lifecycle']=base.verify_ledger(ledger);report['reset_success']=bool(report['resource_lifecycle'].get('all_containers_have_destroy_record'))
  except Exception as exc:report['resource_lifecycle']={'error':str(exc)};report['reset_success']=False
  if not report['reset_success']:report['valid_model_run']=False
  if report.get('status')=='completed' and not report['reset_success']:report['status']='invalid_environment_reset'
  _json(out/'report.json',report)
  _json(out/'provenance.json',{'run_id':args.run_id,'source_commit':base.git_source_state(),
     'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'asset_sha256':ASSET_SHA,
     'fixture_sha256':FIXTURE_SHA,'prompt_sha256':PROMPT_SHA,'model':MODEL,'task_version':TASK_VERSION,'endpoint':endpoint})
 print(json.dumps({'run_id':args.run_id,'condition':args.condition,'status':report.get('status'),
   'valid_model_run':report.get('valid_model_run'),'task_success':report.get('task_success'),
   'classification':report.get('condition_classification'),'evaluations':report.get('evaluations'),
   'wall_seconds':report.get('wall_seconds'),'error':report.get('error'),'out':str(out)},ensure_ascii=False,indent=2))
 return 0 if report.get('valid_model_run') else 1

def main():
 p=argparse.ArgumentParser();p.add_argument('--condition',choices=ARMS,required=True);p.add_argument('--run-id',required=True)
 p.add_argument('--baseline-report',type=Path);p.add_argument('--artifact-parent',type=Path,default=ARTIFACT_ROOT)
 raise SystemExit(_run(p.parse_args()))
if __name__=='__main__':main()
