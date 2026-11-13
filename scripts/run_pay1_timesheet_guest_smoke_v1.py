#!/usr/bin/env python3
"""PAY-1 no-model Guest smoke and server-side state controls; no formal/model arm."""
from __future__ import annotations
import base64, hashlib, json, os, secrets, shlex, shutil, subprocess, sys, time, uuid
from pathlib import Path

ROOT=Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
HYBRID=Path("/home/mjh/Projects/CoDesk-case2-healthcare")
OSWORLD=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
IMAGE=Path("/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2")
RUNTIME="swcub/osworld-v2.1-qemu-runtime:local"
ART=Path("/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/pay1-timesheet-v1")
sys.path[:0]=[str(ROOT),str(HYBRID),str(OSWORLD)]
for k,v in {"OSWORLD_V2_DIR":str(OSWORLD),"SWCUB_OSWORLD_GUEST_IMAGE":str(IMAGE),
            "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE":RUNTIME,"OSWORLD_DOCKER_RUNTIME_IMAGE":RUNTIME}.items():
    os.environ.setdefault(k,v)
from scripts import run_writer_calc_v1 as base
from scripts import pay1_timesheet_fixture_v1 as fx
from scripts import pay1_timesheet_app_v1 as app
from oscombo.harness.hybrid_v2 import MCP_PYTHON,MCP_SITE
from swcub.resource_safety import ensure_resource_identity

def preflight():
    if shutil.disk_usage("/").free<20*1024**3:raise RuntimeError("root free space below 20 GiB")
    if shutil.disk_usage("/mnt/raid1").free<100*1024**3:raise RuntimeError("RAID1 free space below 100 GiB")
    mem=int(next(x.split()[1] for x in Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:")))*1024
    if mem<20*1024**3:raise RuntimeError("MemAvailable below 20 GiB")
    if subprocess.run(["docker","ps","-q"],capture_output=True,text=True,check=True,timeout=20).stdout.strip():
        raise RuntimeError("active Docker container; refusing Guest start")
    if not IMAGE.is_file():raise RuntimeError("pinned Guest image missing")
    if subprocess.run(["docker","image","inspect",RUNTIME],capture_output=True,timeout=20).returncode:
        raise RuntimeError("pinned runtime missing locally; no pull/build")
def guest(d,argv,timeout=30):return base.guest_command(d,argv,timeout=timeout)
def state(d):return json.loads(guest(d,["curl","--noproxy","*","-fsS",f"http://127.0.0.1:{app.PORT}/api/state"],10))
def post(d,path,obj):
    data=base64.b64encode(json.dumps(obj).encode()).decode()
    raw=guest(d,["curl","--noproxy","*","-fsS","-X","POST","-H","Content-Type: application/json","--data-binary",f"@-","http://127.0.0.1:{app.PORT}"+path],10) if False else None
    # URL-encode JSON to avoid shell quoting and stdin-dependent Guest RPC.
    import urllib.parse
    encoded=urllib.parse.quote(json.dumps(obj,separators=(",",":")),safe="")
    cmd="python3 -c "+shlex.quote("import urllib.request;u='http://127.0.0.1:"+str(app.PORT)+path+"';d="+repr(encoded)+";import urllib.parse;r=urllib.request.urlopen(urllib.request.Request(u,data=urllib.parse.unquote(d).encode(),headers={'Content-Type':'application/json'},method='POST'));print(r.read().decode())")
    return json.loads(guest(d,["bash","-lc",cmd],10))
def write_guest(ep, dest, content, label):
    encoded=base64.b64encode(content.encode()).decode()
    py="from pathlib import Path;import base64;p=Path("+repr(dest)+");p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode("+repr(encoded)+"));p.chmod(0o444)"
    ep.cli_action(label,"python3 -c "+shlex.quote(py))
def run_cli_mcp(d,out,root,runid):
    log=out/"guest_cli"/"B"/"actions.jsonl";log.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update({"OSCOMBO_GUEST_URL":f"http://{d.vm_ip}:{d.server_port}","OSCOMBO_ACTION_LOG":str(log),
        "OSCOMBO_MAX_STEPS":"4","OSCOMBO_ACTOR_ID":"B","OSCOMBO_EPISODE_ID":runid+"-B",
        "OSCOMBO_GUEST_KEY":"pay1-smoke","OSCOMBO_CONDITION":"collaborative_isolated",
        "OSCOMBO_CLI_ROOT":root,"OSCOMBO_CLI_ALLOWED_COMMANDS":"pwd,ls,cat,stat,grep,head,tail",
        "OSCOMBO_CLI_MAX_TIMEOUT_SEC":"20","OSCOMBO_CLI_MAX_OUTPUT_BYTES":"12000",
        "PYTHONPATH":os.pathsep.join(x for x in (MCP_SITE,str(HYBRID),str(ROOT),str(OSWORLD),os.environ.get("PYTHONPATH","")) if x)})
    snippet="import json;from oscombo.guest_cli_tools import run_guest_cli;print(json.dumps(run_guest_cli(['cat','correction.json'],"+repr(root)+"),ensure_ascii=False))"
    cp=subprocess.run([MCP_PYTHON,"-c",snippet],env=env,capture_output=True,text=True,timeout=60)
    if cp.returncode:raise RuntimeError("Guest CLI MCP failed: "+cp.stderr[-800:])
    result=json.loads(cp.stdout)
    if not result.get("ok"):raise RuntimeError("Guest CLI result failed: "+json.dumps(result))
    return {"ok":True,"output":result.get("output"),"log":str(log.relative_to(out))}
def run_desktop_screenshot(d,out,runid):
    log=out/"desktop_mcp"/"B"/"actions.jsonl";log.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update({"OSCOMBO_GUEST_URL":f"http://{d.vm_ip}:{d.server_port}","OSCOMBO_ACTION_LOG":str(log),
       "OSCOMBO_MAX_STEPS":"4","OSCOMBO_ACTOR_ID":"B","OSCOMBO_EPISODE_ID":runid+"-B",
       "OSCOMBO_GUEST_KEY":"pay1-smoke","OSCOMBO_CONDITION":"collaborative_isolated",
       "PYTHONPATH":os.pathsep.join(x for x in (MCP_SITE,str(HYBRID),str(ROOT),str(OSWORLD),os.environ.get("PYTHONPATH","")) if x)})
    cp=subprocess.run([MCP_PYTHON,"-m","oscombo.desktop_tools","screenshot","{}"],env=env,capture_output=True,text=True,timeout=60)
    if cp.returncode:raise RuntimeError("Desktop MCP screenshot failed: "+cp.stderr[-800:])
    obj=json.loads(cp.stdout)
    if obj.get("error") or not obj.get("image"):raise RuntimeError("Desktop MCP returned no screenshot: "+str(obj.get("error")))
    png=base64.b64decode(obj["image"]);path=out/"screenshots"/"payroll-desk.png";path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(png)
    from PIL import Image,ImageStat
    import io
    im=Image.open(io.BytesIO(png)).convert("RGB");small=im.resize((96,54))
    audit={"dimensions":[im.width,im.height],"distinct_colors":len(set(small.getdata())),
           "max_stddev":round(max(ImageStat.Stat(small).stddev),3),"sha256":hashlib.sha256(png).hexdigest()}
    if audit["distinct_colors"]<32 or audit["max_stddev"]<5:raise RuntimeError("blank Guest screenshot "+json.dumps(audit))
    return {"ok":True,"screenshot":str(path.relative_to(out)),"audit":audit,"action_log":str(log.relative_to(out))}
def main():
    preflight()
    runid="pay1-guest-smoke-"+time.strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6]
    out=ART/runid;out.mkdir(parents=True,exist_ok=False);(out/"overlays").mkdir()
    ledger=out/"resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID":runid,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER":str(ledger),"SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(out/"overlays"),
        "OSWORLD_V2_DIR":str(OSWORLD)})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None);identity=ensure_resource_identity(ledger)
    log=base.EventLog();ep=d=None;started=time.monotonic()
    report={"run_id":runid,"model_called":False,"api_called":False,"task_id":fx.TASK_ID,
       "task_version":fx.TASK_VERSION,"source_fixture_sha256":fx.SOURCE_FIXTURE_SHA256,
       "runner_semantics":"one no-model Guest setup; no actor task run"}
    try:
        ep,d=base.make_desktop("pay1-no-model-smoke",log,out/"shared",require_a11y_tree=False)
        baseline=ep.refresh_observation(source="pay1-baseline")
        server=app.server_text(fx.SOURCE_FIXTURE_SHA256)
        write_guest(ep,app.SERVER_PATH,server,"pay1_app_install")
        start="nohup /usr/bin/python3 "+shlex.quote(app.SERVER_PATH)+" --state "+shlex.quote(app.STATE_PATH)+" --port "+str(app.PORT)+" >/tmp/codesk-pay1.log 2>&1 </dev/null & echo $! >/tmp/codesk-pay1.pid"
        ep.cli_action("pay1_app_start","bash -lc "+shlex.quote(start))
        deadline=time.monotonic()+20;health=""
        while time.monotonic()<deadline:
            try:health=guest(d,["curl","--noproxy","*","-fsS","--max-time","2",f"http://127.0.0.1:{app.PORT}/health"],5)
            except Exception:time.sleep(.25);continue
            if '"ok": true' in health or '"ok":true' in health:break
            time.sleep(.25)
        if '"ok"' not in health:raise RuntimeError("Guest app health failed: "+health[:300])
        evidence=json.dumps({"document_id":fx.CORRECTION_ID,"employee_id":fx.EMPLOYEE_ID,
           "week_id":fx.WEEK_ID,"corrected_hours_tenths":fx.CORRECTED_HOURS_TENTHS,
           "authorized_by":fx.SUPERVISOR_ID,"signed":True,"reason_code":fx.CORRECTION_SOURCE["reason_code"]},ensure_ascii=False,indent=2)
        cli_root="/tmp/codesk-pay1-cli-B"
        write_guest(ep,cli_root+"/correction.json",evidence,"pay1_cli_evidence_setup")
        cli=run_cli_mcp(d,out,cli_root,runid)
        browser=guest(d,["bash","-lc","command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE"],10).strip().splitlines()[-1]
        if browser=="NONE":raise RuntimeError("Chromium unavailable in pinned Guest")
        profile="/tmp/codesk-pay1/chrome-"+runid
        urls=shlex.quote(app.ROUTES["clerk"])+" "+shlex.quote(app.ROUTES["supervisor"])
        launch="nohup "+shlex.quote(browser)+" --no-sandbox --start-maximized --no-first-run --no-default-browser-check --disable-dev-shm-usage --disable-extensions --disable-background-networking --no-proxy-server --user-data-dir="+shlex.quote(profile)+" --new-window "+urls+" >/tmp/codesk-pay1-browser.log 2>&1 </dev/null & echo $! >/tmp/codesk-pay1-browser.pid"
        ep.cli_action("pay1_browser_start","bash -lc "+shlex.quote(launch))
        from swcub.environment import ActorContext
        gui=ActorContext("pay1-smoke-navigation",ep,"gui")
        gui.press_key("ctrl+l");gui.type_text(app.ROUTES["clerk"]);gui.press_key("enter")
        title="";deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            title=guest(d,["bash","-lc",'wid=$(xdotool getactivewindow 2>/dev/null||true);xdotool getwindowname "$wid" 2>/dev/null||true'],5).strip()
            if "Payroll Close Desk" in title:break
            time.sleep(.25)
        if "Payroll Close Desk" not in title:raise RuntimeError("visible clerk page did not load: "+repr(title))
        gui_obs=ep.refresh_observation(source="pay1-clerk-page-visible")
        shot=gui_obs.get("screenshot") if isinstance(gui_obs,dict) else None
        if not isinstance(shot,bytes) or len(shot)<1000:raise RuntimeError("no visible GUI screenshot from ActorContext")
        sp=out/"screenshots"/"actorcontext.png";sp.parent.mkdir(parents=True,exist_ok=True);sp.write_bytes(shot)
        desktop=run_desktop_screenshot(d,out,runid)
        initial=state(d)
        # Guest-local API controls: ordinary correct isolated outcomes, stale Shared outcome, normal recovery, then reset.
        post(d,"/api/payment",{"actor":"A","hours_tenths":80,"ui_observed_hours_tenths":80})
        a_state=state(d)
        b_state=fx.fresh_state();fx.apply_signed_correction(b_state)
        isolated=fx.evaluate_isolated(a_state,b_state)
        post(d,"/api/reset",{})
        post(d,"/api/correction",{"actor":"B"})
        post(d,"/api/payment",{"actor":"A","hours_tenths":80,"ui_observed_hours_tenths":80})
        stale=fx.evaluate_shared(state(d))
        post(d,"/api/void",{"actor":"A","payment_id":"PAY-W19-E-08-01"})
        post(d,"/api/payment",{"actor":"A","hours_tenths":60,"ui_observed_hours_tenths":60})
        recovered=fx.evaluate_shared(state(d))
        post(d,"/api/reset",{})
        reset_state=state(d)
        report.update({"health":health,"browser_window_title":title,"initial_state":fx.evaluate_actor(initial,"A"),
          "guest_cli_mcp":cli,"desktop_mcp_screenshot":desktop,"actorcontext_screenshot":str(sp.relative_to(out)),
          "scripted_positive_isolated_control":isolated,"scripted_shared_stale_control":stale,
          "scripted_shared_void_reissue_control":recovered,
          "final_reset":{"initial_hours":reset_state["timecard"]["approved_hours_tenths"],
                         "payment_lines":len(reset_state["payment_lines"]),"audit_log":len(reset_state["audit_log"])},
          "status":"smoke_pass"})
        if not cli.get("ok") or "COR-W19-E08" not in cli.get("output","") or not isolated["success"] or stale["success"] or not recovered["success"] or report["final_reset"]!={"initial_hours":80,"payment_lines":0,"audit_log":0}:
            report["status"]="smoke_failed";raise RuntimeError("PAY-1 Guest controls did not match expected contract")
    except Exception as exc:
        report.update({"status":"invalid","error":{"type":type(exc).__name__,"message":str(exc)}})
        raise
    finally:
        if ep:
            try:ep.copy_artifacts(out/"guest-artifacts")
            except Exception as exc:report["artifact_error"]=str(exc)
            try:ep.close()
            except Exception as exc:report["close_error"]=str(exc)
        try:log.write(out/"events.jsonl")
        except Exception as exc:report["event_log_error"]=str(exc)
        report["wall_seconds"]=round(time.monotonic()-started,2)
        report["resource_lifecycle"]=base.verify_ledger(ledger) if ledger.exists() else None
        report["provenance"]={"resource_run_id":identity.run_id,"source_commit":base.git_source_state(),
           "app_sha256":hashlib.sha256(app.server_text(fx.SOURCE_FIXTURE_SHA256).encode()).hexdigest(),
           "guest_image":str(IMAGE)}
        (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"out":str(out),"status":report.get("status"),"wall_seconds":report["wall_seconds"],
       "cli_ok":report.get("guest_cli_mcp",{}).get("ok"),
       "isolated_pass":report.get("scripted_positive_isolated_control",{}).get("success"),
       "shared_stale_fail":not report.get("scripted_shared_stale_control",{}).get("success",True),
       "recovery_pass":report.get("scripted_shared_void_reissue_control",{}).get("success"),
       "reset":report.get("final_reset"),"lifecycle":report.get("resource_lifecycle")},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
