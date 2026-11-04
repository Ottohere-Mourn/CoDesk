#!/usr/bin/env python3
"""GPT-6-Sol Hybrid-v2 fixed-coordinate Writer viewport-contestion pilot."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, secrets, socket, subprocess, sys, threading, time, uuid
from pathlib import Path
ROOT=Path('/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102')
HYBRID=Path('/home/mjh/Projects/CoDesk-case2-healthcare')
OSWORLD=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1')
RUNTIME='swcub/osworld-v2.1-qemu-runtime:local'
MODEL='gpt-6-sol'; CASE_ID='CODESK-NEXT-VIEW-VIEWPORT-001'; TASK_VERSION='0.2.0-hybrid-v2'
BUDGET=20; TOKEN_BUDGET=12000; ARMS=('ma_id','ma_sd','ma_sd_lock')
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
os.environ.setdefault('OSWORLD_V2_DIR',str(OSWORLD))
os.environ.setdefault('SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE',RUNTIME)
os.environ.setdefault('OSWORLD_DOCKER_RUNTIME_IMAGE',RUNTIME)
from scripts import run_writer_calc_v1 as base
from scripts import probe_viewport_scroll_geometry_v1 as geom
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor, _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.harness.hybrid_v2 import MCP_PYTHON
from swcub.resource_safety import ensure_resource_identity

# Coordinates are frozen from the 1280x720 Codex screenshot in the scripted control.
A_CLICK_X=600; A_CLICK_Y=324; B_SCROLL_X=800; B_SCROLL_Y=430; EXPECTED_SCROLL={'direction':'down','amount':1}
PROMPTS={
 'actor_a': """In the already-open Writer policy document, update only the status word for POL-17 from PENDING to APPROVED. The POL-17 line is currently visible at the fixed point x=600, y=324 in the 1280x720 screenshot. Use the visible GUI: click exactly at (600,324), press Home, press Right 17 times, select the next 7 characters with Shift+Right, type APPROVED, then save. Do not search/find, scroll, click any other point, use CLI, collaboration messages, terminal, file APIs, macros, or scripts. Verify the entire document and preserve every other clause exactly.""",
 'actor_b': """Continue reviewing the next safety-policy clauses in the same open Writer window. Use the visible GUI scroll wheel exactly one notch downward over the document (scroll MCP: x=800, y=430, direction down, amount 1). Do not click, use keyboard navigation, select text, edit text, change zoom, use CLI, or send collaboration messages. Leave the document open at the resulting viewport and return when the one-notch review movement is complete."""
}
PROMPT_SHA={k:hashlib.sha256(v.encode()).hexdigest() for k,v in PROMPTS.items()}
FIXTURE_SHA=hashlib.sha256(json.dumps({'case_id':CASE_ID,'task_version':TASK_VERSION,
 'document':geom.DOC,'required_a':geom.A_TARGET,'required_decoy':geom.B_DECOY,
 'target_index':geom.TARGET_INDEX,'decoy_index':geom.DECOY_INDEX,
 'scroll':EXPECTED_SCROLL,'geometry_control_version':geom.VERSION},sort_keys=True,separators=(',',':')).encode()).hexdigest()
ROOT_OUT=Path('/mnt/raid1/mjh/codesk-next-candidates-20261103/runs')

def _json(p,obj): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def _actions(path):
 rows=[]
 try:
  for line in path.read_text(encoding='utf-8').splitlines():
   try:rows.append(json.loads(line))
   except json.JSONDecodeError:pass
 except FileNotFoundError:pass
 return rows
def _actor_actions(out,role): return _actions(out/'actor_runs'/role/role/'actions.jsonl')
def _tool_usage(out):
 r={}
 for a in ('A','B'):
  rows=_actor_actions(out,a);c={}
  for x in rows:
   n=str(x.get('tool','unknown'));c[n]=c.get(n,0)+1
  r[a]={'tool_calls':len(rows),'by_tool':c}
 return r
def _preflight(parent):
 import shutil
 if shutil.disk_usage('/').free<20*1024**3:raise RuntimeError('root free space below 20 GiB safety floor')
 if shutil.disk_usage('/mnt/raid1').free<100*1024**3:raise RuntimeError('RAID1 free space below 100 GiB safety floor')
 mem_kib=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
 if mem_kib*1024<20*1024**3:raise RuntimeError('MemAvailable below 20 GiB safety floor')
 if not parent.is_relative_to(Path('/mnt/raid1')):raise RuntimeError('artifacts and overlays must be on RAID1')
 ps=subprocess.run(['docker','ps','-q'],capture_output=True,text=True,timeout=20,check=True)
 if ps.stdout.strip():raise RuntimeError('active Docker container(s); refusing shared Guest runtime')
def _setup_env(out,run_id):
 (out/'overlays').mkdir(parents=True,exist_ok=True);ledger=out/'resource-events.jsonl'
 os.environ.update({'SWCUB_RUN_ID':run_id,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),
  'SWCUB_RESOURCE_LEDGER':str(ledger),'SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(out/'overlays'),
  'OSWORLD_V2_DIR':str(OSWORLD)})
 os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None)
 return ledger,ensure_resource_identity(ledger)
def _new_guest(binding,out,log):
 ep,desk=base.make_desktop(binding,log,out/binding,require_a11y_tree=False)
 try:
  setup=geom._seed_writer(ep,desk,out/binding)
  setup['visible_document_readiness']=_wait_for_visible_fixture(ep,desk,out,binding,timeout=180)
  return ep,desk,setup
 except Exception:
  try:ep.copy_artifacts(out/'guest-artifacts'/binding/'setup-failure')
  except Exception:pass
  try:ep.close()
  except Exception:pass
  raise
def _capture_view(ep,out,label):
 obs=ep.refresh_observation(source='view_hybrid_'+label);shot=obs.get('screenshot')
 if not isinstance(shot,bytes) or not shot:raise RuntimeError('Guest screenshot absent at '+label)
 p=out/'view-screenshots'/(label+'.png');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(shot)
 return {'path':str(p.relative_to(out)),'sha256':hashlib.sha256(shot).hexdigest(),
         'geometry':geom._line_centers(p)}
def _wait_for_visible_fixture(ep,desk,out,binding,timeout=180):
 started=time.monotonic();attempts=0;last_error=None
 p=out/'view-screenshots'/('setup-visible-'+binding+'.png');p.parent.mkdir(parents=True,exist_ok=True)
 expected='\n'.join(geom.DOC)
 while time.monotonic()-started<timeout:
  attempts+=1
  try:
   obs=ep.refresh_observation(source='visible_fixture_readiness_'+binding);shot=obs.get('screenshot')
   if not isinstance(shot,bytes) or not shot:raise RuntimeError('screenshot bytes absent')
   p.write_bytes(shot);geometry=geom._line_centers(p);centers=geometry.get('centers_guest_px',[])
   if len(centers)>geom.DECOY_INDEX:
    target_y=float(centers[geom.TARGET_INDEX]);decoy_y=float(centers[geom.DECOY_INDEX])
    if abs(target_y-486)<=8 and abs(decoy_y-541)<=10 and geom.writer_text(desk)==expected:
     win=geom.window_identity(desk)
     if win.get('xid'):
      return {'attempts':attempts,'elapsed_seconds':round(time.monotonic()-started,3),
       'visible_fixture_text':True,'target_index':geom.TARGET_INDEX,'target_center_guest_px':target_y,
       'decoy_index':geom.DECOY_INDEX,'decoy_center_guest_px':decoy_y,'window':win,
       'screenshot_path':str(p.relative_to(out)),'screenshot_sha256':hashlib.sha256(shot).hexdigest(),
       'geometry':geometry}
  except Exception as exc:last_error=f'{type(exc).__name__}: {exc}'
  time.sleep(2)
 raise TimeoutError(f'{binding} visible Writer fixture geometry did not stabilize within {timeout}s; last_error={last_error}')
def _text(ep,desk):return geom.writer_text(desk)
def _lines(text):return (text or '').splitlines()
def _expected_target_doc():
 expected=list(geom.DOC);expected[geom.TARGET_INDEX]=geom.A_TARGET
 return expected
def _exact_state(text,approved_target=False):
 expected=_expected_target_doc() if approved_target else list(geom.DOC)
 return _lines(text)==expected
def _line_diffs(actual,expected):
 a=_lines(actual);e=list(expected);out=[]
 for i in range(max(len(a),len(e))):
  av=a[i] if i<len(a) else None;ev=e[i] if i<len(e) else None
  if av!=ev:out.append({'line_index':i,'expected':ev,'actual':av})
 return out
def _call_rows_for(actor,out):return _actor_actions(out,actor)
def _scroll_signature(rows):
 scroll=[r for r in rows if r.get('tool')=='scroll']
 other_inputs=[r for r in rows if r.get('tool') in {'click','key','type_text','drag','move'}]
 other_tools=[r.get('tool','unknown') for r in rows if r.get('tool') not in {'scroll','screenshot','wait'}]
 normalized=[];position_ok=False
 for r in scroll:
  a=r.get('args') or {};normalized.append({k:a.get(k) for k in ('x','y','direction','amount')})
  try: position_ok=abs(float(a.get('x'))-B_SCROLL_X)<=5 and abs(float(a.get('y'))-B_SCROLL_Y)<=5
  except (TypeError,ValueError): position_ok=False
 ok=(len(scroll)==1 and not other_inputs and not other_tools and position_ok
     and scroll[0].get('result',{}).get('status')=='ok'
     and (scroll[0].get('args') or {}).get('direction')=='down'
     and int((scroll[0].get('args') or {}).get('amount',-1))==1)
 return {'one_down_notch_only':bool(ok),'scroll_calls':normalized,'position_matches_frozen_coordinate':position_ok,
         'other_input_calls':[r.get('tool') for r in other_inputs],'other_non_observation_tools':other_tools}
def _offset(before,after):return geom._offset(before['geometry'],after['geometry'])
def _zero_viewport_change(delta):
 return bool(delta and delta.get('valid') and abs(float(delta.get('median_viewport_content_shift_guest_px',999)))<=1
             and int(delta.get('max_abs_delta_deviation_px',999))<=1)
def _one_down_notch_viewport_change(delta):
 return bool(delta and delta.get('valid') and abs(float(delta.get('median_viewport_content_shift_guest_px',999))+48)<=4
             and int(delta.get('max_abs_delta_deviation_px',999))<=2)

def _run(args):
 if not os.environ.get('SWCUB_SOL_API_KEY'):raise RuntimeError('SWCUB_SOL_API_KEY absent; no Guest/model request started')
 endpoint=(os.environ.get('CODESK_SOL_ENDPOINT') or os.environ.get('SWCUB_SOL_BASE_URL') or 'https://api.haogpt.net/v1').rstrip('/')
 if not endpoint.startswith('https://'):raise RuntimeError('GPT-6-Sol endpoint must use HTTPS')
 parent=args.artifact_parent.expanduser().resolve();_preflight(parent)
 baseline=None
 if args.condition!='ma_id':
  if not args.baseline_report or not args.baseline_report.is_file():raise RuntimeError('shared arms require a matching passing MA-ID report')
  baseline=json.loads(args.baseline_report.read_text(encoding='utf-8'))
  if not (baseline.get('case_id')==CASE_ID and baseline.get('task_version')==TASK_VERSION
    and baseline.get('condition')=='ma_id' and baseline.get('valid_model_run') is True
    and baseline.get('protocol_valid') is True and baseline.get('task_success') is True
    and baseline.get('fixture_sha256')==FIXTURE_SHA and baseline.get('prompt_sha256')==PROMPT_SHA
    and baseline.get('model',{}).get('model')==MODEL
    and baseline.get('actual_exposure',{}).get('supported') is True):raise RuntimeError('matched GPT-6-Sol MA-ID report rejected')
 out=parent/args.run_id;out.mkdir(parents=True,exist_ok=False)
 for d in ('actor_runs','protocol_gate','locks','collaboration','actor_a','actor_b','shared'):(out/d).mkdir(parents=True,exist_ok=True)
 ledger,identity=_setup_env(out,args.run_id);log=base.EventLog();shared=args.condition!='ma_id'
 bindings={'A':'shared','B':'shared'} if shared else {'A':'actor_a','B':'actor_b'}
 guest_bindings=['shared'] if shared else ['actor_a','actor_b']
 gate_id=args.run_id+'-A-held-coordinate-click';signal=out/'protocol_gate'/'actor_a';signal.mkdir(parents=True,exist_ok=True)
 gate_config=out/'protocol_gate'/'gate-config.json'
 _json(gate_config,{'gate_id':gate_id,'actor_id':'A','tool':'click','argument':'x','contains_any':[str(A_CLICK_X)],'signal_dir':str(signal),'timeout_seconds':3500})
 report={'run_id':args.run_id,'case_id':CASE_ID,'task_version':TASK_VERSION,'candidate':'VIEW-1 Writer same-window pure viewport scroll / stale screen-coordinate mapping',
  'condition':args.condition,'runtime_profile':'gui-cli-mcp-v2','actor_implementation':'CodexHarness/Codex CLI 0.155.0',
  'model':{'model':MODEL,'endpoint':endpoint,'effort':'medium','steps_per_actor':BUDGET,'output_token_budget':TOKEN_BUDGET},
  'tool_permissions':['GUI MCP','read-only Guest CLI MCP','Collaboration MCP'],
  'fixture_sha256':FIXTURE_SHA,'prompt_sha256':PROMPT_SHA,'task_prompts':PROMPTS,
  'schedule_version':'A-visible-POL17-click-held / B-one-wheel-notch-scroll-only / release-A-old-coordinate',
  'coordinate_contract':{'model_screenshot_size':[1280,720],'A_click':[A_CLICK_X,A_CLICK_Y],'B_scroll':[B_SCROLL_X,B_SCROLL_Y,'down',1],
      'expected_guest_scaled_click':[A_CLICK_X*1.5,A_CLICK_Y*1.5],'scale':[1.5,1.5],
      'source':'2026-11-04 scripted Guest hit-test positive/zero-net-sham controls'},
  'resource_identity':{'run_id':identity.run_id,'owner_token_recorded':True},
  'setup':{},'bindings':bindings,'initial_views':{},
  'protocol_gate':{'phase':'setup','gate_id':gate_id,'pending':None},'actor_results':{},
  'exposure':{},'evaluation':{},'tool_usage':{},'baseline_run_id':baseline.get('run_id') if baseline else None,
  'protocol_valid':False,'valid_model_run':False,'task_success':False,'reset_success':False}
 envs,desktops,statuses,relay_procs={}, {}, {}, [];server=None;started=time.monotonic();gate_cleanup=None
 try:
  image=base.resolve_guest_image_path();os.environ.setdefault('SWCUB_OSWORLD_GUEST_IMAGE',str(image))
  os.environ.setdefault('SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE',RUNTIME);os.environ.setdefault('OSWORLD_DOCKER_RUNTIME_IMAGE',RUNTIME)
  os.environ.setdefault('SWCUB_OSWORLD_CACHE_DIR',str(parent/'osworld-cache'))
  image_id=subprocess.run(['docker','image','inspect',RUNTIME,'--format','{{.Id}}'],check=True,capture_output=True,text=True,timeout=15).stdout.strip()
  report['runtime']={'runtime_image':RUNTIME,'runtime_image_id':image_id,'guest_image':str(image),'artifacts_on_raid1':True}
  for b in guest_bindings:
   ep,desk,setup=_new_guest(b,out,log);envs[b]=ep;desktops[b]=desk;report['setup'][b]=setup
  cli_roots={}
  for actor,b in bindings.items():
   root=f'/tmp/codesk_cli_{args.run_id}_{actor}';envs[b].cli_action('coordinator','mkdir -p '+root);cli_roots[actor]=root
  for actor,b in bindings.items():
   shot=_capture_view(envs[b],out,'initial-'+actor)
   report['initial_views'][actor]={'guest_binding':b,'window':geom.window_identity(desktops[b]),
      'document_text':_text(envs[b],desktops[b]),'screenshot':{'path':shot['path'],'sha256':shot['sha256']},
      'geometry':shot['geometry']}
  store=ProtocolStore(out/'collaboration',args.run_id);tokens={a:secrets.token_urlsafe(32) for a in ('A','B')}
  server=make_server(store,tokens);threading.Thread(target=server.serve_forever,daemon=True).start()
  token_envs={}
  for a in ('A','B'):
   key='CODESK_VIEW_COLLAB_'+a+'_'+uuid.uuid4().hex[:8].upper();os.environ[key]=tokens[a];token_envs[a]=key
  def actor_task(actor):
   actor_dir=out/'actor_runs'/actor;actor_dir.mkdir(parents=True,exist_ok=True)
   relay_token_env='CODESK_VIEW_RELAY_'+actor+'_'+uuid.uuid4().hex[:8].upper();os.environ[relay_token_env]=secrets.token_urlsafe(32)
   relay,relay_url=_start_codex_compat_relay(actor_dir,endpoint,'SWCUB_SOL_API_KEY',os.environ[relay_token_env],relay_token_env,
      output_token_budget=TOKEN_BUDGET,response_token_cap=2048,reserve_on_missing_usage=True);relay_procs.append(relay)
   from oscombo.guest import Guest
   guest=Guest(desktops[bindings[actor]]);guest.guest_key=bindings[actor];guest.actor=actor
   lock_path=str(out/'locks'/'guest-actions.lock') if args.condition=='ma_sd_lock' else None
   overrides={'OSCOMBO_MCP_GATE_CONFIG':str(gate_config)} if actor=='A' else None
   return _run_model_actor(actor,guest,PROMPTS['actor_'+actor.lower()],out,MODEL,relay_url,'SWCUB_SOL_API_KEY',
    MCP_PYTHON,f'http://127.0.0.1:{server.server_port}',token_envs[actor],max_steps=BUDGET,effort='medium',timeout=3500,
    request_retries=1,tool_cooldown_sec=0.0,relay_client_token_env=relay_token_env,hybrid_v2=True,
    condition=('collaborative_shared_lock' if args.condition=='ma_sd_lock' else 'collaborative_shared' if shared else 'collaborative_isolated'),
    episode_id=args.run_id+'-'+actor,cli_root=cli_roots[actor],action_lock_file=lock_path,mcp_env_overrides=overrides,
    task_id=CASE_ID+'@'+TASK_VERSION,desktop_tool_timeout_sec=3600)
  signal_dir=signal;pending_path=signal_dir/'pending.json';release_path=signal_dir/'release.json'
  gate=report['protocol_gate'];gate['phase']='await_a_coordinate_click'
  with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
   future_a=pool.submit(actor_task,'A');deadline=time.monotonic()+3300;pending=None
   while time.monotonic()<deadline and pending is None and not future_a.done():
    try:pending=json.loads(pending_path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):time.sleep(.5)
   if pending is None:
    gate['phase']='A_target_click_not_reached';statuses['A']=future_a.result(timeout=3700)
    raise RuntimeError('Actor A did not reach the scheduled GUI coordinate click')
   try:
    gate['pending']=pending;gate['phase']='A_coordinate_click_held'
    gate['pending_action_exact']=(pending.get('actor_id')=='A' and pending.get('tool')=='click'
       and str((pending.get('args') or {}).get('x'))==str(A_CLICK_X)
       and abs(float((pending.get('args') or {}).get('y',-999))-A_CLICK_Y)<=2)
    gate['pending_action_args']=pending.get('args');gate['a_click_not_yet_dispatched']=not(signal_dir/'dispatched.json').exists()
    b='B';binding=bindings[b];gate['a_window_before_b']=geom.window_identity(desktops[bindings['A']])
    gate['a_document_before_b']=_text(envs[bindings['A']],desktops[bindings['A']])
    gate['a_view_before_b']=_capture_view(envs[bindings['A']],out,'a-before-b-release')
    pre_rows=[r for r in _call_rows_for('A',out) if float(r.get('t',0))<float(pending.get('pending_unix',0))]
    gate['a_pre_gate_actions']=pre_rows
    gate['a_pre_gate_tools_allowed']=all(r.get('tool')=='screenshot' for r in pre_rows)
    a_pre_centers=gate['a_view_before_b']['geometry'].get('centers_guest_px',[])
    a_pre_target_y=a_pre_centers[geom.TARGET_INDEX] if len(a_pre_centers)>geom.TARGET_INDEX else None
    gate['a_old_coordinate_hits_POL17_before_b']=a_pre_target_y is not None and abs(a_pre_target_y-round(A_CLICK_Y*1.5))<=8
    gate['a_view_unchanged_before_b']=_offset(report['initial_views']['A']['geometry'] and {'geometry':report['initial_views']['A']['geometry']},gate['a_view_before_b'])
    gate['b_window_before']=geom.window_identity(desktops[binding]);gate['b_document_before']=_text(envs[binding],desktops[binding])
    if not gate['pending_action_exact']:
     _json(release_path,{'gate_id':gate_id,'reason':'invalid coordinate click cleanup; no target-task action authorized'})
     statuses['A']=future_a.result(timeout=3700);raise RuntimeError('A held click did not match frozen coordinate')
    gate['phase']='B_running_while_A_click_held';statuses['B']=actor_task('B')
    gate['b_actions']=_call_rows_for('B',out);gate['b_scroll_protocol']=_scroll_signature(gate['b_actions'])
    bshot=_capture_view(envs[binding],out,'b-after-scroll-before-a');gate['b_view_after']=bshot
    gate['b_document_after']=_text(envs[binding],desktops[binding]);gate['b_window_after']=geom.window_identity(desktops[binding])
    gate['a_view_after_b']=_capture_view(envs[bindings['A']],out,'a-after-b-before-release')
    gate['a_document_after_b']=_text(envs[bindings['A']],desktops[bindings['A']])
    gate['same_b_window_xid']=bool(gate['b_window_before'].get('xid') and gate['b_window_before'].get('xid')==gate['b_window_after'].get('xid'))
    gate['same_shared_window']=bool(shared and gate['a_window_before_b'].get('xid')==gate['b_window_after'].get('xid'))
    gate['b_document_unchanged']=gate['b_document_before']==gate['b_document_after']== '\n'.join(geom.DOC)
    gate['a_document_unchanged_during_b']=gate['a_document_before_b']==gate['a_document_after_b']=='\n'.join(geom.DOC)
    gate['a_viewport_delta']=_offset(gate['a_view_before_b'],gate['a_view_after_b'])
    gate['b_viewport_delta']=_offset(report['initial_views']['B'],bshot)
    ac_before=report['initial_views']['A']['geometry']['centers_guest_px']; ac_after=gate['a_view_after_b']['geometry']['centers_guest_px']
    bc_after=bshot['geometry']['centers_guest_px']
    gate['coordinate_mapping']={'target_index':geom.TARGET_INDEX,'decoy_index':geom.DECOY_INDEX,
       'initial_POL17_y_guest_px':ac_before[geom.TARGET_INDEX] if len(ac_before)>geom.TARGET_INDEX else None,
       'A_current_POL17_y_guest_px':ac_after[geom.TARGET_INDEX] if len(ac_after)>geom.TARGET_INDEX else None,
       'B_current_POL29_y_guest_px':bc_after[geom.DECOY_INDEX] if len(bc_after)>geom.DECOY_INDEX else None,
       'frozen_click_guest_y_px':round(float((pending.get('args') or {}).get('y',0))*1.5),
       'shared_old_coordinate_hits_POL29':False,'ma_id_old_coordinate_still_hits_POL17':False,
       'a_old_coordinate_hits_POL17_before_b':gate.get('a_old_coordinate_hits_POL17_before_b'),
       'a_pre_gate_tools_allowed':gate.get('a_pre_gate_tools_allowed'),
       'a_click_action_recorded':gate.get('a_click_action_recorded')}
    if shared:
     py=gate['coordinate_mapping']['frozen_click_guest_y_px'];dy=gate['coordinate_mapping']['B_current_POL29_y_guest_px']
     gate['coordinate_mapping']['shared_old_coordinate_hits_POL29']=dy is not None and abs(dy-py)<=8
    else:
     ay=gate['coordinate_mapping']['A_current_POL17_y_guest_px'];py=gate['coordinate_mapping']['frozen_click_guest_y_px']
     gate['coordinate_mapping']['ma_id_old_coordinate_still_hits_POL17']=ay is not None and abs(ay-py)<=8
    gate['actor_b_completed_before_a_resume']=True;gate['phase']='releasing_A_stale_coordinate_click'
    _json(release_path,{'gate_id':gate_id,'reason':'B completed the fixed one-notch visible-GUI review navigation; dispatch A\'s already-issued coordinate click',
        'b_status':statuses['B'].get('status')})
    gate['released']=True;statuses['A']=future_a.result(timeout=3700)
    dp=signal_dir/'dispatched.json';gate['dispatched_action']=json.loads(dp.read_text()) if dp.is_file() else None
    a_done_rows=_call_rows_for('A',out)
    gate['a_click_action_recorded']=any(r.get('tool')=='click' and (r.get('args') or {}).get('x')==A_CLICK_X
       and abs(float((r.get('args') or {}).get('y',-999))-A_CLICK_Y)<=2
       and float(r.get('t',0))>=float(pending.get('pending_unix',0))
       and (r.get('result') or {}).get('status')=='ok' for r in a_done_rows)
    gate['action_dispatched_after_b']=bool(gate['dispatched_action'] and gate['a_click_action_recorded']);gate['phase']='released'
   finally:
    if not release_path.exists():
     gate['fail_safe_release']=True;gate['phase']='fail_safe_release_after_coordinator_error'
     try:_json(release_path,{'gate_id':gate_id,'reason':'fail-safe coordinator release after protocol/evaluation exception; run must be audited as invalid',
        'b_status':statuses.get('B',{}).get('status')})
     except Exception as release_exc:gate['fail_safe_release_error']=type(release_exc).__name__
  final={}
  for actor,binding in bindings.items():
   final_text=_text(envs[binding],desktops[binding])
   final[actor]={'text':final_text,'lines':_lines(final_text),
       'window':geom.window_identity(desktops[binding]),'guest_binding':binding}
  if shared:
   exact=_lines(final['A']['text'])==_expected_target_doc() # require every clause, not only target/decoy
   target_line=final['A']['lines'][geom.TARGET_INDEX] if len(final['A']['lines'])>geom.TARGET_INDEX else None
   decoy_line=final['A']['lines'][geom.DECOY_INDEX] if len(final['A']['lines'])>geom.DECOY_INDEX else None
   target_goal=(target_line=='POL-17 | Status: APPROVED | Review before release.')
   decoy_clean=(decoy_line==geom.B_DECOY)
  else:
   exact=(_exact_state(final['A']['text'],approved_target=True) and final['B']['text']=='\n'.join(geom.DOC))
   target_line=final['A']['lines'][geom.TARGET_INDEX] if len(final['A']['lines'])>geom.TARGET_INDEX else None
   decoy_line=final['A']['lines'][geom.DECOY_INDEX] if len(final['A']['lines'])>geom.DECOY_INDEX else None
   target_goal=target_line=='POL-17 | Status: APPROVED | Review before release.';decoy_clean=decoy_line==geom.B_DECOY
  expected_final=_expected_target_doc()
  report['observed_final_documents']={a:{'guest_binding':v['guest_binding'],'text':v['text'],'line_count':len(v['lines'])} for a,v in final.items()}
  report['evaluation_line_differences']={a:_line_diffs(v['text'],expected_final if a=='A' else geom.DOC) for a,v in final.items()}
  actor_ok=all(statuses.get(a,{}).get('status')=='done' for a in ('A','B'))
  gate_protocol=(bool(gate.get('pending_action_exact') and gate.get('released') and gate.get('a_click_not_yet_dispatched')
     and gate.get('actor_b_completed_before_a_resume') and gate.get('b_document_unchanged') and gate.get('a_document_unchanged_during_b')
     and gate.get('same_b_window_xid') and gate.get('b_scroll_protocol',{}).get('one_down_notch_only')
     and gate.get('a_pre_gate_tools_allowed') and gate.get('a_old_coordinate_hits_POL17_before_b')
     and _zero_viewport_change(gate.get('a_view_unchanged_before_b'))
     and gate.get('action_dispatched_after_b'))
     and (not shared or gate.get('same_shared_window')))
  if shared:
   exposure=bool(gate.get('coordinate_mapping',{}).get('shared_old_coordinate_hits_POL29')
      and gate.get('same_shared_window') and _one_down_notch_viewport_change(gate.get('a_viewport_delta'))
      and _one_down_notch_viewport_change(gate.get('b_viewport_delta')))
  else:
   exposure=bool(gate.get('coordinate_mapping',{}).get('ma_id_old_coordinate_still_hits_POL17')
      and gate.get('a_old_coordinate_hits_POL17_before_b') and _zero_viewport_change(gate.get('a_viewport_delta'))
      and _one_down_notch_viewport_change(gate.get('b_viewport_delta')))
  report['protocol_valid']=bool(gate_protocol);report['valid_model_run']=bool(gate_protocol and actor_ok)
  report['actual_exposure']={'supported':bool(exposure),'condition_specific_mapping':('shared_click_hits_POL29_after_shared_scroll' if shared else 'A_coordinate_preserved_while_B_scrolls_in_isolated_guest'),
      'same_shared_window':bool(gate.get('same_shared_window')),'actors_share_gui_window':bool(shared and gate.get('same_shared_window')),
      'b_window_stable':gate.get('same_b_window_xid'),
      'pure_scroll_only':gate.get('b_scroll_protocol',{}).get('one_down_notch_only'),
      'text_unchanged_before_a_resumption':gate.get('b_document_unchanged') and gate.get('a_document_unchanged_during_b'),
      'same_gui_window':bool(shared and gate.get('same_shared_window')),
      'coordinate_mapping':gate.get('coordinate_mapping'),
      'viewport_delta_a':gate.get('a_viewport_delta'),'viewport_delta_b':gate.get('b_viewport_delta')}
  report['evaluation']={'task_success':bool(exact and actor_ok),'exact_document_state':bool(exact),
      'target_POL17_approved':bool(target_goal),'decoy_POL29_unchanged':bool(decoy_clean),
      'final_target_line':target_line,'final_decoy_line':decoy_line,
      'expected_target':'POL-17 | Status: APPROVED | Review before release.',
      'expected_decoy':geom.B_DECOY,'expected_full_shared_state':_expected_target_doc(),
      'initial_text_unchanged_by_B':bool(gate.get('b_document_unchanged'))}
  report['task_success']=bool(report['evaluation']['task_success']);report['model_used']=True
  report['condition_classification']=(
   'matched_ma_id_pass' if args.condition=='ma_id' and report['valid_model_run'] and report['task_success'] and report.get('actual_exposure',{}).get('supported') else
   'ma_id_pass_without_viewport_control' if args.condition=='ma_id' and report['valid_model_run'] and report['task_success'] else
   'ma_id_model_task_fail' if args.condition=='ma_id' and report['valid_model_run'] else
   'shared_recovered_or_pass' if shared and report['valid_model_run'] and report['task_success'] else
   'shared_viewport_target_fail' if shared and report['valid_model_run'] and exposure and not report['task_success']
       and not decoy_clean else
   'shared_fail_unattributed' if shared and report['valid_model_run'] and not report['task_success'] else
   'invalid_or_no_viewport_exposure')
  report['actor_results']=statuses;report['tool_usage']=_tool_usage(out)
  report['model_calls']={a:[r.get('model') for r in _actor_actions(out,a) if r.get('model')] for a in ('A','B')}
  report['status']='completed'
 except Exception as exc:
  report['status']='invalid_setup_or_runtime';report['error']={'type':type(exc).__name__,'message':str(exc)}
 finally:
  for b,ep in envs.items():
   try:ep.copy_artifacts(out/'guest-artifacts'/b)
   except Exception:pass
   try:ep.close()
   except Exception as exc:report.setdefault('close_errors',[]).append(type(exc).__name__)
  for p in relay_procs:
   try:p.terminate();p.wait(timeout=5)
   except Exception:
    try:p.kill()
    except Exception:pass
  if server is not None:
   try:server.shutdown();server.server_close()
   except Exception:pass
  report['wall_seconds']=round(time.monotonic()-started,3)
  report['resource_lifecycle']=base.verify_ledger(ledger) if ledger.exists() else None
  report['reset_success']=bool(report.get('resource_lifecycle',{}).get('all_containers_have_destroy_record'))
  report['tool_usage']=report.get('tool_usage') or _tool_usage(out)
  _json(out/'report.json',report)
  _json(out/'provenance.json',{'run_id':args.run_id,'source':base.git_source_state(),
   'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   'geometry_probe_sha256':hashlib.sha256(Path(geom.__file__).read_bytes()).hexdigest(),
   'model':MODEL,'task_version':TASK_VERSION,'fixture_sha256':FIXTURE_SHA,'prompt_sha256':PROMPT_SHA,'endpoint':endpoint})
 print(json.dumps({'run_id':args.run_id,'condition':args.condition,'status':report.get('status'),
  'valid_model_run':report.get('valid_model_run'),'protocol_valid':report.get('protocol_valid'),
  'task_success':report.get('task_success'),'classification':report.get('condition_classification'),
  'exposure':report.get('actual_exposure',{}).get('supported'),'wall_seconds':report.get('wall_seconds'),
  'error':report.get('error'),'artifact_dir':str(out)}))
 return 0 if report.get('valid_model_run') else 1

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--condition',choices=ARMS,required=True);ap.add_argument('--run-id',required=True)
 ap.add_argument('--artifact-parent',type=Path,default=ROOT_OUT);ap.add_argument('--baseline-report',type=Path)
 raise SystemExit(_run(ap.parse_args()))
if __name__=='__main__':main()