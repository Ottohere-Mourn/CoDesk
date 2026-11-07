#!/usr/bin/env python3
"""GPT-6-Sol Hybrid v2 triplet for the composite warehouse receiving workflow."""
from __future__ import annotations
import base64, concurrent.futures, hashlib, io, json, os, secrets, shlex, shutil, subprocess, sys, threading, time, uuid
from pathlib import Path
from PIL import Image, ImageStat

ROOT = Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
HYBRID = Path("/home/mjh/Projects/CoDesk-case2-healthcare")
OSWORLD = Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
IMAGE = Path("/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2")
RUNTIME = "swcub/osworld-v2.1-qemu-runtime:local"
ARTIFACT_ROOT = Path("/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/composite-warehouse-receiving-v027")
MODEL = "gpt-6-sol"
BUDGET, TOKEN_BUDGET = 18, 18000
SCHEDULE_VERSION = "warehouse-receiving-v018-uniform-18-step-18k-output-mcp-context-restore"
BUDGET_RATIONALE = "Uniform 18-step and 18,000 output-token caps across all arms. The prior valid MA-SD arm consumed the old 12,000-token cap before completion, so raise output allowance equally rather than lowering the tool-step cap; the source remains a distinct ASN browser tab for realistic context switching."
ARMS = ("ma_id", "ma_sd", "ma_sd_lock")
sys.path[:0] = [str(ROOT), str(HYBRID), str(OSWORLD)]
os.environ.setdefault("OSWORLD_V2_DIR", str(OSWORLD))
os.environ.setdefault("SWCUB_OSWORLD_GUEST_IMAGE", str(IMAGE))
os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)
os.environ.setdefault("OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)

from scripts import run_writer_calc_v1 as base
from scripts.wf_composite_receiving_v2 import (
    APP_DIR, APP_SERVER, ASN_LOT, EXPECTED, FIXTURE_DOCUMENTS, FIXTURE_SHA256,
    PORT, QA_DISPOSITION, SERVER_PATH, STATE_PATH, TASK_ID, TASK_VERSION,
    clipboard_failure_attribution, collaboration_contract, evaluate_state, mechanism_evidence)
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.harness.hybrid_v2 import MCP_PYTHON, MCP_SITE
from swcub.clipboard_observer import GuestCommandClipboardSampler, install_guest_probe
from swcub.resource_safety import ensure_resource_identity

PROMPTS = {
"A": """You are the receiving clerk for PO-2407. The browser has three task tabs: Receiving (Ctrl+1), ASN-2407 source document (Ctrl+2), and QA-19 (Ctrl+3). Work in the visible GUI. First send Actor B a short collaboration handoff identifying the BN-07 exception, source lot LOT-B07, and 3 cartons held for QA. On Receiving, enter this complete ledger:
AX-14 | received=24 | accepted=24 | held=0 | shortage=0 | lot=LOT-A14
BN-07 | received=18 | accepted=15 | held=3 | shortage=0 | lot=LOT-B07
CR-22 | received=11 | accepted=11 | held=0 | shortage=1 | lot=LOT-C22
DT-31 | received=6 | accepted=6 | held=0 | shortage=0 | lot=LOT-D31
Wait until the workspace shows “Ledger draft saved”; the four-row draft auto-saves, so do not click the final Save button yet. Switch to ASN-2407 with Ctrl+2 and verify/copy the LOT-B07 value from the labeled read-only lot field using Ctrl+A then Ctrl+C. Return to Receiving with Ctrl+1, click Held lot reference, and paste. Do not retype from memory. Wait 1 second and inspect the value once; if wrong, use the ASN tab to re-copy the source value and return to Receiving to correct it. After the lot reference is correct, click “Save receiving and discrepancy” once and verify totals: received 59, accepted 56, held 3, shortage 1. Held cartons are excluded from available inventory. Preserve the source PO, ASN, QA bulletin and unrelated records.""",
"B": """You are the QA technician for inbound notice QA-19. The browser has Receiving (Ctrl+1), ASN-2407 (Ctrl+2), and QA-19 (Ctrl+3) tabs. First read Actor A's collaboration handoff. Switch to QA-19 with Ctrl+3, verify the notice concerns LOT-B07 and 3 cartons, and use the visible GUI to copy the read-only field labeled “Standard QA disposition to copy” (Ctrl+A, Ctrl+C), then paste it into QA disposition. Wait 1 second and inspect once; do not paste twice unless incorrect. Save the exact phrase and reply to Actor A with the confirmed lot, quantity, and hold reason. Do not retype the phrase or modify the receiving ledger or source bulletin. You may inspect and correct your work."""
}
PROMPT_SHA = {a: hashlib.sha256(v.encode()).hexdigest() for a,v in PROMPTS.items()}
APP_SHA = hashlib.sha256(APP_SERVER.encode()).hexdigest()
TASKMOD_SHA = hashlib.sha256((ROOT/"scripts/wf_composite_receiving_v2.py").read_bytes()).hexdigest()
RUNNER_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
PROBE_SHA = hashlib.sha256((ROOT/"scripts/guest_clipboard_probe.py").read_bytes()).hexdigest()
LOT_SHA = hashlib.sha256(ASN_LOT.encode()).hexdigest()
QA_SHA = hashlib.sha256(QA_DISPOSITION.encode()).hexdigest()

def _json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")

def _preflight():
    if shutil.disk_usage("/").free < 20*1024**3: raise RuntimeError("root free space below 20 GiB")
    if shutil.disk_usage("/mnt/raid1").free < 100*1024**3: raise RuntimeError("RAID1 free space below 100 GiB")
    mem=int(next(x.split()[1] for x in Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:")))*1024
    if mem < 20*1024**3: raise RuntimeError("MemAvailable below 20 GiB")
    if subprocess.run(["docker","ps","-q"],capture_output=True,text=True,check=True,timeout=20).stdout.strip():
        raise RuntimeError("active Docker container; refusing Guest start")
    if not IMAGE.is_file(): raise RuntimeError("pinned Guest image missing")
    if subprocess.run(["docker","image","inspect",RUNTIME],capture_output=True,timeout=20).returncode:
        raise RuntimeError("pinned runtime is not local; no pull/build")
    if not os.environ.get("SWCUB_SOL_API_KEY"): raise RuntimeError("GPT-6-Sol API key absent; no Guest started")

def _start_receiving_codex_relay(run_root, upstream, api_key_env, client_token, client_token_env,
                                  output_token_budget, response_token_cap):
    """Start the run-owned relay with a body-size-aware upload timeout for screenshots."""
    import requests
    ready = run_root / "codex_relay_ready.json"
    log_path = run_root / "codex_relay.log"
    cmd = [sys.executable, "-u", "-m", "oscombo.responses_tool_image_relay",
           "--upstream", upstream, "--api-key-env", api_key_env,
           "--client-token-env", client_token_env,
           "--ready-file", str(ready),
           "--event-log", str(run_root / "codex_relay_events.jsonl"),
           "--output-token-budget", str(int(output_token_budget)),
           "--response-token-cap", str(int(response_token_cap)),
           "--reserve-on-missing-usage", "--size-aware-upload-timeout"]
    relay_env = {name: os.environ[name] for name in (
        "PATH", "HOME", "PYTHONPATH", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "no_proxy", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")
                 if name in os.environ}
    relay_env.update({api_key_env: os.environ[api_key_env],
                      client_token_env: client_token, "PYTHONUNBUFFERED": "1"})
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=HYBRID, env=relay_env,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Codex compatibility relay exited {process.returncode}; see {log_path}")
        if ready.exists():
            info = json.loads(ready.read_text())
            if info.get("pid") == process.pid:
                base_url = f"http://127.0.0.1:{info['port']}/v1"
                try:
                    response = requests.get(f"http://127.0.0.1:{info['port']}/health", timeout=2)
                    if response.ok and response.json().get("ready"):
                        return process, base_url
                except requests.RequestException:
                    pass
        time.sleep(0.2)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    raise TimeoutError(f"Codex compatibility relay not ready within 20s; see {log_path}")


def _env(out, run_id):
    (out/"overlays").mkdir(parents=True,exist_ok=True)
    ledger=out/"resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID":run_id,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER":str(ledger),"SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(out/"overlays"),
        "OSWORLD_V2_DIR":str(OSWORLD)})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None)
    return ledger,ensure_resource_identity(ledger)

def _state(desk):
    raw=base.guest_command(desk,["curl","--noproxy","*","-fsS",f"http://127.0.0.1:{PORT}/api/state"],timeout=10)
    return json.loads(raw)

def _desktop_mcp_call(tool, args, out, desk, binding, phase, condition):
    """Coordinator-only GUI restore through the same Guest-facing executor as actor MCP tools."""
    root=out/"coordinator_mcp"/f"{binding}-{phase}"
    root.mkdir(parents=True,exist_ok=True)
    action_log=root/"actions.jsonl"
    env=os.environ.copy()
    env.update({"OSCOMBO_GUEST_URL":f"http://{desk.vm_ip}:{desk.server_port}",
        "OSCOMBO_ACTION_LOG":str(action_log),"OSCOMBO_MAX_STEPS":"12",
        "OSCOMBO_MCP_SETTLE":"0.15","OSCOMBO_ACTOR_ID":"coordinator_restore",
        "OSCOMBO_EPISODE_ID":out.name+"-"+binding+"-"+phase,
        "OSCOMBO_GUEST_KEY":binding,
        "OSCOMBO_CONDITION":"collaborative_shared_lock" if condition=="ma_sd_lock" else "collaborative_shared",
        "PYTHONPATH":os.pathsep.join(x for x in
            (MCP_SITE,str(HYBRID),str(ROOT),str(OSWORLD),os.environ.get("PYTHONPATH","")) if x)})
    lock=out/"locks"/"guest-actions.lock"
    if condition=="ma_sd_lock":
        env["OSCOMBO_ACTION_LOCK_FILE"]=str(lock)
    else:
        env.pop("OSCOMBO_ACTION_LOCK_FILE",None)
    cp=subprocess.run([MCP_PYTHON,"-m","oscombo.desktop_tools",tool,json.dumps(args)],
        env=env,capture_output=True,text=True,timeout=180,check=False)
    if cp.returncode:
        raise RuntimeError(f"coordinator desktop MCP exited {cp.returncode}: {cp.stderr[-1200:]}")
    try: result=json.loads(cp.stdout)
    except Exception as exc:
        raise RuntimeError(f"coordinator desktop MCP returned invalid JSON: {cp.stdout[-1200:]}") from exc
    if result.get("error"):
        raise RuntimeError("coordinator desktop MCP failed: "+str(result["error"]))
    image=base64.b64decode(result["image"]) if result.get("image") else None
    return {"tool":tool,"args":args,"text":result.get("text"),
        "image":image,"image_bytes":len(image) if image else 0,
        "image_sha256":hashlib.sha256(image).hexdigest() if image else None,
        "action_log":str(action_log.relative_to(out))}

def _window(desk):
    raw=base.guest_command(desk,["bash","-lc",'wid=$(xdotool getactivewindow 2>/dev/null || true); title=$(xdotool getwindowname "$wid" 2>/dev/null || true); printf "%s\\t%s\\n" "$wid" "$title"'])
    row=raw.rstrip("\n").split("\t",1)
    return {"xid":row[0] if row else "", "title":row[1] if len(row)>1 else ""}

def _visual_digest(raw):
    if not isinstance(raw,bytes) or not raw:return None
    try:
        im=Image.open(io.BytesIO(raw)).convert("RGB").resize((1280,720))
        return hashlib.sha256(im.tobytes()).hexdigest()
    except Exception:return None

def _frame_audit(raw):
    if not isinstance(raw, bytes) or not raw:
        return {"content_ready": False, "reason": "empty_screenshot"}
    try:
        im=Image.open(io.BytesIO(raw)).convert("RGB")
        w,h=im.size
        page=im.crop((int(w*.08),int(h*.08),int(w*.96),int(h*.93))).resize((96,54))
        colors=len(set(page.getdata()));std=max(ImageStat.Stat(page).stddev)
        return {"size": [w,h], "page_crop_colors": colors,
                "page_crop_max_stddev": round(std,3), "content_ready": colors>=32 and std>5}
    except Exception as e:
        return {"content_ready": False, "reason": f"{type(e).__name__}: {e}"}

def _active_route(state):
    for x in reversed(state.get("observations",[])):
        if x.get("visible") is True and x.get("kind") in {"visibility-change","window-focus","page-load"}:
            return x.get("route")
    return None

def _initial_ok(state):
    return (state.get("task_id")==TASK_ID and state.get("task_version")==TASK_VERSION
            and state.get("documents")==FIXTURE_DOCUMENTS
            and all(state.get(k)=="" for k in EXPECTED))

def _setup_guest(ep,desk,binding,out,run_id):
    # Install the private clipboard probe and attach its sampler before the
    # first episode action. Setup CLI calls are logged through ActorContext,
    # so attaching after app bootstrap violates OSWorldSharedEpisode's
    # pre-actor instrumentation invariant even though no model has run yet.
    probe,observer=install_guest_probe(lambda argv,d=desk:base.guest_command(d,argv),
        ROOT/"scripts/guest_clipboard_probe.py",run_id+"-"+binding)
    sampler=GuestCommandClipboardSampler(lambda argv,d=desk:base.guest_command(d,argv),
        probe_path=probe,state_path=observer)
    ep.attach_clipboard_sampler(sampler,actor_payload_digests={"A":LOT_SHA,"B":QA_SHA},required=True)
    sampler.sample()
    code=base64.b64encode(APP_SERVER.encode()).decode()
    py=("from pathlib import Path; import base64; p=Path("+repr(SERVER_PATH)+"); "
        "p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(base64.b64decode("+repr(code)+")); p.chmod(0o700)")
    ep.cli_action("task_setup","python3 -c "+shlex.quote(py))
    start=("nohup /usr/bin/python3 "+shlex.quote(SERVER_PATH)+" --state "+shlex.quote(STATE_PATH)
        +" --port "+str(PORT)+" >/tmp/codesk-warehouse-receiving.log 2>&1 </dev/null & "
        +"echo $! >/tmp/codesk-warehouse-receiving.pid")
    ep.cli_action("task_setup","bash -lc "+shlex.quote(start))
    health=""; deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        try:
            health=base.guest_command(desk,["curl","--noproxy","*","-fsS","--max-time","2",f"http://127.0.0.1:{PORT}/health"],timeout=5)
            if '"ok"' in health: break
        except Exception: time.sleep(.25)
    if '"ok"' not in health: raise RuntimeError("Guest-local app health failed: "+health[:300])
    browser=base.guest_command(desk,["bash","-lc","command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE"]).strip().splitlines()[-1]
    if browser=="NONE": raise RuntimeError("Chromium unavailable")
    profile=f"{APP_DIR}/profile-{run_id}-{binding}"
    initial_route="/case/qa" if binding=="actor_b" else "/case/receiving"
    expected_title="Quality Disposition - QA-19" if initial_route=="/case/qa" else "Warehouse Receiving - PO-2407"
    task_tabs=("/case/receiving","/case/asn","/case/qa")
    task_urls=[f"http://127.0.0.1:{PORT}"+route for route in task_tabs]
    launch=("nohup "+shlex.quote(browser)+" --no-sandbox --start-maximized --no-first-run --no-default-browser-check "
        "--disable-dev-shm-usage --disable-gpu --disable-extensions --disable-background-networking --no-proxy-server --remote-debugging-port=9222 "
        +"--user-data-dir="+shlex.quote(profile)+" --new-window "
        +" ".join(shlex.quote(url) for url in task_urls)
        +" >/tmp/codesk-warehouse-browser.log 2>&1 </dev/null & echo $! >/tmp/codesk-warehouse-browser.pid")
    ep.cli_action("task_setup","bash -lc "+shlex.quote(launch))
    loaded=set(); shot=None; title=""; state={}; initial_tab_selected=False
    for attempt in range(1,81):
        obs=ep.refresh_observation(source="receiving_fixture_readiness")
        shot=obs.get("screenshot") if isinstance(obs,dict) else None
        title=_window(desk)["title"]; state=_state(desk)
        loaded={x.get("route") for x in state.get("observations",[]) if x.get("kind")=="page-load"}
        if not initial_tab_selected and {"/case/receiving","/case/asn","/case/qa"}.issubset(loaded):
            from swcub.environment import ActorContext
            selector=ActorContext("fixture_initial_tab_"+binding,ep,"gui")
            selector.press_key("ctrl+3" if binding=="actor_b" else "ctrl+1")
            initial_tab_selected=True
            time.sleep(.5)
            continue
        if shot and expected_title in title and {"/case/receiving","/case/asn","/case/qa"}.issubset(loaded): break
        time.sleep(.5)
    else:
        diagnostics={}
        probes={
            "app_log":"tail -n 30 /tmp/codesk-warehouse-receiving.log 2>&1",
            "browser_log":"tail -n 50 /tmp/codesk-warehouse-browser.log 2>&1",
            "processes":"ps -ef | grep -E 'chromium|chrome|receiving/server.py' | grep -v grep | head -20",
            "page_status":f"curl --noproxy '*' -sS -o /dev/null -w '%{{http_code}} %{{url_effective}}' http://127.0.0.1:{PORT}/case/receiving",
            "cdp":"curl --max-time 2 -fsS http://127.0.0.1:9222/json/list",
            'active_window':"wid=$(xdotool getactivewindow 2>/dev/null || true); xdotool getwindowname '$wid' 2>&1",
        }
        for name,command in probes.items():
            try: diagnostics[name]=base.guest_command(desk,["bash","-lc",command],timeout=8)[:3000]
            except Exception as exc: diagnostics[name]=f"{type(exc).__name__}: {exc}"
        raise RuntimeError("Guest browser/app readiness failed: "+json.dumps(
            {"title":title,"loaded":sorted(loaded),"diagnostics":diagnostics},ensure_ascii=False))
    if not _initial_ok(state): raise RuntimeError("initial synthetic fixture not exact")
    shot=None; frame={}
    for _ in range(8):
        observation=ep.refresh_observation(source="receiving_fixture_ready_confirmed")
        shot=observation.get("screenshot") if isinstance(observation,dict) else None
        frame=_frame_audit(shot)
        if frame.get("content_ready"): break
        time.sleep(.5)
    if not frame.get("content_ready"): raise RuntimeError("browser frame is blank/flat: "+json.dumps(frame))
    file=out/"setup"/f"{binding}-browser-ready.png"; file.parent.mkdir(parents=True,exist_ok=True); file.write_bytes(shot)
    return {"health":health,"browser":browser,"fixture_sha256":FIXTURE_SHA256,"app_sha":APP_SHA,
        "initial_business_state":{k:state[k] for k in ("task_id","task_version","documents","receipt_ledger","held_lot_ref","qa_disposition")},
        "loaded_routes":sorted(loaded),"active_route":_active_route(state),
        "active_window":_window(desk),"screenshot":str(file.relative_to(out)),"screenshot_content":frame,
        "screenshot_sha256":hashlib.sha256(shot).hexdigest(),"clipboard_probe":probe,"attempts":attempt}

def _activate(actor,ep,desk,out,binding,phase,condition=None):
    route="/case/receiving" if actor=="A" else "/case/qa"
    title_marker="Warehouse Receiving - PO-2407" if actor=="A" else "Quality Disposition - QA-19"
    key="1" if actor=="A" else "3"
    nav=f"xdotool key --clearmodifiers ctrl+{key}; sleep 1"
    restore_via_mcp=actor=="A" and phase=="before_A_resume"
    condition=condition or "ma_sd"
    mcp_nav=None
    if restore_via_mcp:
        mcp_nav=_desktop_mcp_call("key",{"keys":"ctrl+1"},out,desk,binding,phase,condition)
    else:
        ep.cli_action("coordinator","bash -lc "+shlex.quote(nav))
    reference=None
    if actor=="B" and phase=="before_B":
        reference=out/"setup"/f"{binding}-browser-ready.png"
    elif actor=="A" and phase=="before_A_resume":
        reference=out/"setup"/"shared-B-before_B.png"
    reference_sha=hashlib.sha256(reference.read_bytes()).hexdigest() if reference and reference.is_file() else None
    attempts=[]; shot=None; state={}; active=None; win={}; frame={}; focused=None; shot_sha=None
    for attempt in range(1,9):
        if restore_via_mcp:
            if attempt==1:
                shot=mcp_nav.get("image")
            else:
                wait_result=_desktop_mcp_call("wait",{"seconds":0.75},out,desk,binding,phase,condition)
                shot=wait_result.get("image")
        else:
            obs=ep.refresh_observation(source="hybrid_v2_"+phase+f"_readiness_{attempt}")
            shot=obs.get("screenshot") if isinstance(obs,dict) else None
        state=_state(desk); active=_active_route(state); win=_window(desk); frame=_frame_audit(shot)
        focused=next((x.get("active_id") for x in reversed(state.get("observations",[]))
                      if x.get("route")==route and x.get("kind")=="focus" and x.get("visible") is True),None)
        shot_sha=hashlib.sha256(shot).hexdigest() if isinstance(shot,bytes) else None
        reference_visual_sha=_visual_digest(reference.read_bytes()) if reference and reference.is_file() else None
        current_visual_sha=_visual_digest(shot)
        visual_changed=reference_visual_sha is None or current_visual_sha!=reference_visual_sha
        row={"actor":actor,"binding":binding,"phase":phase,"expected_route":route,
             "active_route":active,"expected_window_title_contains":title_marker,
             "active_window":win,"focused_target":focused,"screenshot":bool(shot),
             "screenshot_content":frame,"screenshot_sha256":shot_sha,
             "reference_screenshot_sha256":reference_sha,"reference_visual_sha256":reference_visual_sha,
             "visual_sha256":current_visual_sha,"visual_changed_from_other_role":visual_changed}
        if (active==route and title_marker in win.get("title","")
                and frame.get("content_ready") and visual_changed):
            break
        attempts.append(row)
        time.sleep(.75)
    else:
        raise RuntimeError("role context failed after bounded visual retries: "+json.dumps(
            {"last":row,"attempts":attempts},ensure_ascii=False))
    row["readiness_attempts"]=attempt
    if restore_via_mcp:
        focus_result=_desktop_mcp_call("click",{"x":667,"y":501},out,desk,binding,phase,condition)
        shot=focus_result.get("image") or shot
        time.sleep(.25)
        state=_state(desk)
        row["active_route"]=_active_route(state)
        row["active_window"]=_window(desk)
        row["focused_target_before_release"]=next((x.get("active_id") for x in reversed(state.get("observations",[]))
            if x.get("route")==route and x.get("kind")=="focus" and x.get("visible") is True),None)
        row["restore_executor"]="desktop_mcp"
        row["restore_tool_log"]=focus_result["action_log"]
        row["restore_key_call"]={"text":mcp_nav.get("text"),"action_log":mcp_nav["action_log"]}
        row["restore_focus_call"]={"text":focus_result.get("text"),"image_sha256":focus_result.get("image_sha256")}
        row["screenshot_content"]=_frame_audit(shot)
        row["screenshot_sha256"]=hashlib.sha256(shot).hexdigest() if shot else None
        if (row["active_route"]!=route
                or title_marker not in row["active_window"].get("title","")
                or row["focused_target_before_release"]!="held-lot-ref"
                or not row["screenshot_content"].get("content_ready")):
            raise RuntimeError("MCP context restoration failed validation: "+json.dumps(row,ensure_ascii=False))
    p=out/"setup"/f"{binding}-{actor}-{phase}.png";p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(shot)
    row["screenshot_path"]=str(p.relative_to(out))
    return row

def _actions(out,actor):
    p=out/"actor_runs"/actor/actor/"actions.jsonl"; rows=[]
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
    except FileNotFoundError: pass
    return rows

def _has_key(rows,key):
    key=key.casefold().replace("control+","ctrl+")
    return any(r.get("tool")=="key" and key in str(r.get("args",{}).get("keys","")).casefold().replace("control+","ctrl+") for r in rows)

def _arm(parent,condition,baseline):
    run="warehouse-receiving-sol-hybrid-v2-"+condition+"-"+uuid.uuid4().hex[:8]
    out=parent/run;out.mkdir(parents=True,exist_ok=False)
    for d in ("actor_runs","actor_a","actor_b","shared","protocol_gate","locks","collaboration","reset"):(out/d).mkdir(parents=True,exist_ok=True)
    ledger,identity=_env(out,run); log=base.EventLog(); shared=condition!="ma_id"
    gate={"enabled":shared,"gate_id":run+"-held-lot-paste","phase":"not_started",
        "trigger":"Actor A key ctrl+v to Held lot reference","pending":None,"released":False}
    signal=out/"protocol_gate"/"actor_a";signal.mkdir(parents=True,exist_ok=True)
    gatefile=out/"protocol_gate"/"gate-config.json"
    _json(gatefile,{"gate_id":gate["gate_id"],"actor_id":"A","tool":"key","argument":"keys",
        "contains_any":["ctrl+v","control+v"],"signal_dir":str(signal),"timeout_seconds":3500})
    envs={};desks={};bindings={};setups={};relays=[];secret_envs=[];statuses={}
    started=time.monotonic(); report={"run_id":run,"task_id":TASK_ID,"task_version":TASK_VERSION,
        "fixture_sha256":FIXTURE_SHA256,"prompt_hashes":PROMPT_SHA,"source_hashes":{"task":TASKMOD_SHA,"runner":RUNNER_SHA,"app":APP_SHA,"clipboard_probe":PROBE_SHA},
        "condition":condition,"runtime_profile":"gui-cli-mcp-v2","actor_implementation":"CodexHarness/Codex CLI 0.155.0",
        "model":MODEL,"endpoint":os.environ.get("CODESK_SOL_ENDPOINT","https://api.haogpt.net/v1"),
        "budget_per_actor":BUDGET,"per_actor_output_budget":TOKEN_BUDGET,
        "budget_rationale":BUDGET_RATIONALE,
        "tool_permissions":["GUI MCP","read-only Guest CLI MCP","Collaboration MCP"],
        "schedule_version":SCHEDULE_VERSION,
        "baseline_required_for_shared":True,"baseline_accepted":False,"bindings":bindings,"setups":setups,
        "context_handoffs":[],"protocol_gate":gate,"actors":{},"clipboard_boundaries":{},
        "reset_success":False,"valid_model_run":False,"protocol_valid":False}
    _json(out/"prompts.json",PROMPTS)
    _json(out/"provenance-initial.json",{"source_commit":base.git_source_state(),"task":TASK_ID,"version":TASK_VERSION,
        "fixture_sha256":FIXTURE_SHA256,"condition":condition,"model":MODEL,"permissions":report["tool_permissions"],
        "budget":BUDGET,"source_hashes":report["source_hashes"]})
    server=None
    try:
        if shared:
            if not baseline or baseline.get("model_task_outcome")!="PASS" or not baseline.get("valid_model_run"):
                raise RuntimeError("matched passing MA-ID baseline missing")
            report["baseline_accepted"]=True;report["baseline_run_id"]=baseline["run_id"]
        plan=[("shared",["A","B"])] if shared else [("actor_a",["A"]),("actor_b",["B"])]
        for binding,actors in plan:
            ep,desk=base.make_desktop(binding,log,out/binding,require_a11y_tree=False)
            # Register the Guest before fixture setup so failures still flow
            # through the single teardown/reset path and retain the real setup
            # error instead of being rewritten as an empty-reset failure.
            envs[binding],desks[binding]=ep,desk
            for a in actors:bindings[a]=binding
            try:
                setups[binding]=_setup_guest(ep,desk,binding,out,run)
            except Exception:
                try:ep.copy_artifacts(out/"setup-failure-artifacts"/binding)
                except Exception:pass
                raise
        cli_roots={}
        for actor,binding in bindings.items():
            root=f"/tmp/codesk_cli_{run}_{actor.lower()}";envs[binding].cli_action("task_setup","mkdir -p "+shlex.quote(root));cli_roots[actor]=root
        for actor in ("A","B"):
            if actor in bindings:report["context_handoffs"].append(_activate(actor,envs[bindings[actor]],desks[bindings[actor]],out,bindings[actor],"initial"))
        tokens={a:secrets.token_urlsafe(32) for a in ("A","B")}
        store=ProtocolStore(out/"collaboration",run);server=make_server(store,tokens)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        token_envs={}
        for a in ("A","B"):
            n="CODESK_WF_COLLAB_"+a+"_"+uuid.uuid4().hex[:8].upper();os.environ[n]=tokens[a];secret_envs.append(n);token_envs[a]=n
        def actor_task(actor):
            actor_out=out/"actor_runs"/actor;actor_out.mkdir(parents=True,exist_ok=True)
            relay_env="CODESK_WF_RELAY_"+actor+"_"+uuid.uuid4().hex[:8].upper()
            os.environ[relay_env]=secrets.token_urlsafe(32);secret_envs.append(relay_env)
            relay,url=_start_receiving_codex_relay(actor_out,os.environ.get("CODESK_SOL_ENDPOINT","https://api.haogpt.net/v1"),
                "SWCUB_SOL_API_KEY",os.environ[relay_env],relay_env,
                output_token_budget=TOKEN_BUDGET,response_token_cap=2048);relays.append(relay)
            from oscombo.guest import Guest
            guest=Guest(desks[bindings[actor]]);guest.guest_key=bindings[actor];guest.actor=actor
            overrides={"OSCOMBO_MCP_GATE_CONFIG":str(gatefile)} if actor=="A" and shared else None
            lock=str(out/"locks"/"guest-actions.lock") if condition=="ma_sd_lock" else None
            return _run_model_actor(actor,guest,PROMPTS[actor],out,MODEL,url,"SWCUB_SOL_API_KEY",MCP_PYTHON,
                f"http://127.0.0.1:{server.server_port}",token_envs[actor],max_steps=BUDGET,effort="medium",
                timeout=3500,request_retries=1,tool_cooldown_sec=0.0,relay_client_token_env=relay_env,
                hybrid_v2=True,condition="collaborative_shared_lock" if condition=="ma_sd_lock" else
                "collaborative_shared" if shared else "collaborative_isolated",episode_id=run+"-"+actor,
                cli_root=cli_roots[actor],action_lock_file=lock,mcp_env_overrides=overrides,
                task_id=TASK_ID+"@"+TASK_VERSION,desktop_tool_timeout_sec=3600)
        if not shared:
            for a in ("A","B"):statuses[a]=actor_task(a)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fa=pool.submit(actor_task,"A");pending_path=signal/"pending.json";deadline=time.monotonic()+3300;pending=None
                while time.monotonic()<deadline and pending is None and not fa.done():
                    try:pending=json.loads(pending_path.read_text(encoding="utf-8"))
                    except (FileNotFoundError,json.JSONDecodeError):time.sleep(.5)
                if pending is None:
                    gate["phase"]="A_held_paste_not_reached";gate["source_copy_seen"]=_has_key(_actions(out,"A"),"ctrl+c")
                    try:statuses["A"]=fa.result(timeout=3700)
                    except Exception as e:statuses["A"]={"status":"error","error":f"{type(e).__name__}: {e}"}
                    try:statuses["B"]=actor_task("B")
                    except Exception as e:statuses["B"]={"status":"error","error":f"{type(e).__name__}: {e}"}
                else:
                    gate["pending"]=pending;gate["phase"]="A_held_paste_pending"
                    gate["source_copy_seen"]=_has_key(_actions(out,"A"),"ctrl+c")
                    gate["clipboard_after_A_pending"]=envs["shared"].clipboard_sampler.sample()
                    state=_state(desks["shared"])
                    gate["active_route_at_gate"]=_active_route(state)
                    focus_event = next((x for x in reversed(state.get("observations",[]))
                        if x.get("route")=="/case/receiving" and x.get("kind")=="focus"
                        and x.get("visible") is True),None)
                    gate["focus_event_at_gate"]=focus_event
                    gate["focus_at_gate"]=focus_event.get("active_id") if focus_event else None
                    try:
                        report["context_handoffs"].append(_activate("B",envs["shared"],desks["shared"],out,"shared","before_B"))
                        statuses["B"]=actor_task("B")
                    except Exception as e:statuses["B"]={"status":"error","error":f"{type(e).__name__}: {e}"}
                    after_b=_state(desks["shared"])
                    gate["B_exact_before_A_resume"]=evaluate_state(after_b)["actor_goal_success"]["actor_b"]
                    gate["B_terminated_before_A_resume"]=statuses.get("B",{}).get("status") in {"done","max_steps","fail"}
                    report["clipboard_boundaries"]["after_B"]=envs["shared"].clipboard_sampler.sample()
                    try:
                        handoff=_activate("A",envs["shared"],desks["shared"],out,"shared","before_A_resume",condition)
                        report["context_handoffs"].append(handoff);gate["active_route_before_release"]=handoff["active_route"]
                        gate["focus_target_before_release"]=handoff["focused_target"]
                    except Exception as e:gate["restore_A_context_error"]=f"{type(e).__name__}: {e}"
                    _json(signal/"release.json",{"gate_id":gate["gate_id"],"reason":"B finished QA; A receiving page active; release pending paste",
                        "actor_b_status":statuses.get("B",{}).get("status")})
                    gate["released"]=True;gate["phase"]="A_paste_dispatched_after_B"
                    try:statuses["A"]=fa.result(timeout=3700)
                    except Exception as e:statuses["A"]={"status":"error","error":f"{type(e).__name__}: {e}"}
                    report["clipboard_boundaries"]["after_A_resume"]=envs["shared"].clipboard_sampler.sample()
        report["actors"]=statuses
        states={b:_state(d) for b,d in desks.items()};report["final_states"]=states
        report["app_events"]={b:s.get("events",[]) for b,s in states.items()}
        report["app_observations"]={b:s.get("observations",[]) for b,s in states.items()}
        report["clipboard_observer_health"]={b:e.clipboard_observer_health for b,e in envs.items()}
        report["actor_actions"]={a:{"calls":len(_actions(out,a)),"copy":_has_key(_actions(out,a),"ctrl+c"),
            "paste":_has_key(_actions(out,a),"ctrl+v")} for a in ("A","B")}
        collab_path=out/"collaboration"/"events.jsonl"
        collab_events=[]
        if collab_path.is_file():
            for line in collab_path.read_text(encoding="utf-8").splitlines():
                try: collab_events.append(json.loads(line))
                except json.JSONDecodeError: pass
        report["collaboration_events"]=collab_events
        report["collaboration_contract"]=collaboration_contract(collab_events)
        if condition=="ma_id":
            evals={a:evaluate_state(states[bindings[a]]) for a in ("A","B")}
            goal={a:evals[a]["actor_goal_success"]["actor_"+a.lower()] for a in ("A","B")}
            success=all(goal.values()) and report["collaboration_contract"]["success"]
            report["evaluation"]={**evals,"collaboration_contract":report["collaboration_contract"]}
            report["actor_goal_success"]=goal
        else:
            final=states["shared"];ev=evaluate_state(final)
            success=ev["condition_success"] and report["collaboration_contract"]["success"]
            ba=gate.get("clipboard_after_A_pending",{});bb=report["clipboard_boundaries"].get("after_B",{})
            paste=next((x for x in report["app_observations"]["shared"] if x.get("kind")=="paste" and x.get("route")=="/case/receiving"),None)
            pasted=paste.get("payload_text") if isinstance(paste,dict) else None
            pasted_sha=hashlib.sha256(pasted.encode()).hexdigest() if isinstance(pasted,str) else None
            pending=gate.get("pending") or {}
            intervening=(ba.get("payload_sha256")==LOT_SHA and bb.get("payload_sha256")==QA_SHA
                and bb.get("payload_sha256")!=ba.get("payload_sha256")
                and report["actor_actions"]["A"]["copy"] and report["actor_actions"]["B"]["copy"])
            context=(gate.get("active_route_at_gate")=="/case/receiving"
                and gate.get("active_route_before_release")=="/case/receiving"
                and gate.get("focus_target_before_release")=="held-lot-ref"
                and gate.get("focus_at_gate")=="held-lot-ref"
                and pending.get("actor_id")=="A" and pending.get("guest_key")=="shared"
                and pending.get("tool")=="key" and "ctrl+v" in str(pending.get("args",{}).get("keys","")).casefold())
            mech=mechanism_evidence(expected_copy_sha256=LOT_SHA,clipboard_at_paste_sha256=pasted_sha,
                paste_target_id=paste.get("target_id") if isinstance(paste,dict) else None,
                target_is_held_lot_ref=context and isinstance(paste,dict) and paste.get("target_id")=="held-lot-ref",
                final_held_lot_ref=str(final.get("held_lot_ref","")),
                actor_a_copy_seen=report["actor_actions"]["A"]["copy"],actor_b_copy_seen=report["actor_actions"]["B"]["copy"],
                intervening_overwrite=intervening)
            report["evaluation"]={"shared":ev,"clipboard_mechanism":mech,
                "collaboration_contract":report["collaboration_contract"]}
            gate["paste_event_after_dispatch"]=paste;gate["context_correct_at_paste"]=context
            report["mechanism_exposure_valid"]=bool(context and intervening and pasted_sha==bb.get("payload_sha256"))
            attribution=clipboard_failure_attribution(final,mech)
            report["mechanism_failure_attribution"]=attribution
            report["mechanism_supported_task_fail"]=bool(report["mechanism_exposure_valid"]
                and attribution["supported_isolated_failure"]
                and report["collaboration_contract"]["success"]
                and not ev["actor_goal_success"]["actor_a"] and ev["actor_goal_success"]["actor_b"])
            report["protocol_valid"]=bool(gate.get("released") and gate.get("B_terminated_before_A_resume")
                and gate.get("source_copy_seen") and pending.get("actor_id")=="A" and pending.get("guest_key")=="shared"
                and pending.get("tool")=="key" and "ctrl+v" in str(pending.get("args",{}).get("keys","")).casefold()
                and envs["shared"].clipboard_observer_health.get("valid") is True)
        report["condition_success"]=success
        statuses_ok=bool(statuses) and all(x.get("status") in {"done","max_steps","fail"} for x in statuses.values())
        report["valid_model_run"]=statuses_ok and (not shared or report["protocol_valid"])
        if report["valid_model_run"]:
            report["status"]="completed"
            report["model_task_outcome"]="PASS" if success else "FAIL"
        else:
            report["status"]="invalid_model_or_protocol"
            report["model_task_outcome"]="environment_or_model_invalid"
    except Exception as e:
        report["status"]="invalid_infrastructure_or_protocol";report["error"]={"type":type(e).__name__,"message":str(e)}
        report["model_task_outcome"]="environment_or_model_invalid";report["valid_model_run"]=False
    finally:
        for b,ep in list(envs.items()):
            try:ep.copy_artifacts(out/"guest-artifacts"/b)
            except Exception as e:report.setdefault("artifact_errors",[]).append(f"{b}: {e}")
            try:ep.close()
            except Exception as e:report.setdefault("close_errors",[]).append(f"{b}: {e}")
        reset_rows={}
        for b in sorted(set(bindings.values())):
            rep=None
            try:
                rd=out/"reset"/b;rd.mkdir(parents=True,exist_ok=True)
                rep,rdsk=base.make_desktop(b+"_reset",log,rd,require_a11y_tree=False)
                chk=base.guest_command(rdsk,["bash","-lc","test ! -e "+shlex.quote(SERVER_PATH)+" && test ! -e "+shlex.quote(STATE_PATH)+" && echo reset_clean"])
                reset_rows[b]={"success":"reset_clean" in chk,"replacement_guest_id":rep.snapshot().get("guest_container_id")}
            except Exception as e:reset_rows[b]={"success":False,"error":f"{type(e).__name__}: {e}"}
            finally:
                if rep is not None:
                    try:rep.copy_artifacts(out/"reset-artifacts"/b)
                    except Exception:pass
                    try:rep.close()
                    except Exception:pass
        report["reset_check"]=reset_rows;report["reset_success"]=bool(reset_rows) and all(x.get("success") for x in reset_rows.values())
        if not report["reset_success"]:
            report["valid_model_run"]=False
            report["model_task_outcome"]="environment_or_model_invalid"
            report["reset_invalidates_run"]=True
            if report.get("status")=="completed":
                report["status"]="invalid_environment_reset"
            if not reset_rows:
                report["reset_verification_note"]="No Guest binding reached setup registration; preserve the original setup error and resource-lifecycle evidence."
        if server:
            try:server.shutdown();server.server_close()
            except Exception:pass
        for p in relays:
            try:p.terminate();p.wait(timeout=10)
            except Exception:
                try:p.kill()
                except Exception:pass
        for k in secret_envs:os.environ.pop(k,None)
        try:log.write(out/"events.jsonl")
        except Exception as e:report.setdefault("event_log_errors",[]).append(str(e))
        report["wall_seconds"]=round(time.monotonic()-started,2)
        report["resource_lifecycle"]=base.verify_ledger(ledger) if ledger.exists() else None
        if not report["resource_lifecycle"] or not report["resource_lifecycle"].get("all_containers_have_destroy_record") or not report["resource_lifecycle"].get("labels_consistent"):
            report["valid_model_run"]=False;report["model_task_outcome"]="environment_or_model_invalid";report["status"]="invalid_resource_lifecycle"
        report["provenance"]={"run_id":identity.run_id,"source_commit":base.git_source_state(),
            "fixture_sha256":FIXTURE_SHA256,"source_hashes":{"task":TASKMOD_SHA,"runner":RUNNER_SHA,"app":APP_SHA,"clipboard_probe":PROBE_SHA},
            "condition":condition,"guest_image":str(base.resolve_guest_image_path()),"resource_ledger":str(ledger)}
        _json(out/"report.json",report);_json(out/"provenance.json",report["provenance"])
    return report

def main():
    _preflight()
    ARTIFACT_ROOT.mkdir(parents=True,exist_ok=True)
    parent=ARTIFACT_ROOT/("warehouse-receiving-sol-"+time.strftime("%Y%m%d-%H%M%S")+"-triplet")
    parent.mkdir(parents=True,exist_ok=False)
    reports=[];baseline=None
    for arm in ARMS:
        row=_arm(parent,arm,baseline);reports.append(row)
        if arm=="ma_id":
            baseline=row
            if row.get("model_task_outcome")!="PASS" or not row.get("valid_model_run"):break
        elif not row.get("valid_model_run"):break
    result={"task_id":TASK_ID,"task_version":TASK_VERSION,"fixture_sha256":FIXTURE_SHA256,
        "runtime_profile":"gui-cli-mcp-v2","model":MODEL,
        "per_actor_step_budget":BUDGET,"per_actor_output_budget":TOKEN_BUDGET,
        "schedule_version":SCHEDULE_VERSION,"budget_rationale":BUDGET_RATIONALE,
        "acceptance_target":"MA-ID exact PASS / MA-SD clipboard-attributable FAIL / MA-SD+Lock clipboard-attributable FAIL",
        "arms":[{"run_id":r["run_id"],"condition":r["condition"],"outcome":r.get("model_task_outcome"),
            "valid":r.get("valid_model_run"),"success":r.get("condition_success"),
            "protocol_valid":r.get("protocol_valid"),"collaboration_success":r.get("collaboration_contract",{}).get("success"),
            "mechanism_exposure_valid":r.get("mechanism_exposure_valid"),
            "mechanism_supported_task_fail":r.get("mechanism_supported_task_fail"),
            "reset_success":r.get("reset_success")} for r in reports]}
    _json(parent/"triplet_result.json",result)
    print(json.dumps({"triplet":str(parent),**result},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
