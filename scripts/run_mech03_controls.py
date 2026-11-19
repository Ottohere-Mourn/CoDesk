#!/usr/bin/env python3
"""Real Guest positive and stale-focus negative controls for MECH-03.
No model is used. The negative is a fixed mechanism control, not a natural concurrency estimate.
"""
from __future__ import annotations
import json,os,secrets,sys,time,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OSW=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
SWC=Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
IMAGE=Path(os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE",OSW/"docker_vm_data/osworld-v2-ubuntu-x86.qcow2"))
ASSETS=Path(os.environ.get("PARAGUI_TASK_ASSETS","/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets"))
OUTROOT=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls")
TASK_A=ROOT/"tasks/mechanism_expansion_v1/task_mech03a.py"
TASK_B=ROOT/"tasks/mechanism_expansion_v1/task_mech03b.py"
sys.path[:0]=[str(ROOT),str(SWC),str(OSW)]
os.environ.update({"OSWORLD_DIR":str(OSW),"PARAGUI_TASK_ASSETS":str(ASSETS),
 "OSCOMBO_GUEST_IMAGE":str(IMAGE),"SWCUB_OSWORLD_GUEST_IMAGE":str(IMAGE),
 "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE":"swcub/osworld-v2.1-qemu-runtime:local",
 "OSWORLD_DOCKER_RUNTIME_IMAGE":"swcub/osworld-v2.1-qemu-runtime:local",
 "SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(OUTROOT/"overlays"),
 "SWCUB_OSWORLD_CACHE_DIR":str(OUTROOT/"osworld-cache")})
from oscombo import combo
from oscombo.guest import Guest
from oscombo.osworld import load_task
from swcub.resource_safety import ensure_resource_identity

REPLY="We have received your service request and will respond by 3 PM."

def cmd(g,script,timeout=60):
    r=g.execute(["bash","-lc",script],timeout)
    return (r.get("output") or "")+(r.get("error") or "")
def activate(g,title):
    q=__import__("shlex").quote(title)
    out=cmd(g,f"wid=$(xdotool search --onlyvisible --name {q} 2>/dev/null | tail -1 || true); test -n \"$wid\" && xdotool windowactivate --sync \"$wid\"")
    time.sleep(.5)
    info=g.active_window_info()
    if not info.get("title") or title.casefold() not in info["title"].casefold():
        raise RuntimeError(f"could not activate {title}: {info}, output={out[-400:]}")
    return info
def switch_alt_tab(g,title):
    cmd(g,"xdotool key alt+Tab; sleep .6")
    info=g.active_window_info()
    if not info.get("title") or title.casefold() not in info["title"].casefold():
        raise RuntimeError(f"Alt+Tab expected {title}: {info}")
    return info

def type_amount(g):
    # Same GUI path as the task card: click the visible D12 cell, then type/commit/save.
    cmd(g,"xdotool mousemove --sync 420 500 click 1; sleep .2; xdotool type --clearmodifiers --delay 20 '1250.00'; xdotool key Return; sleep .5; xdotool key ctrl+s; sleep 2")
def edit_reply(g):
    cmd(g,"xdotool key ctrl+a; sleep .2; xdotool type --clearmodifiers --delay 20 'We have received your service request and will respond by 3 PM.'; sleep .3; xdotool key ctrl+s; sleep 2")
def state(g):
    a=__import__("tasks.mechanism_expansion_v1.mech03",fromlist=["evaluate"]).evaluate(g.env,"A")
    b=__import__("tasks.mechanism_expansion_v1.mech03",fromlist=["evaluate"]).evaluate(g.env,"B")
    return {"A":a,"B":b}
def screenshot(g,path):Path(path).write_bytes(g.screenshot(patience=90))
def reset_docs(g,setup_controller):
    # Save both documents, then close LibreOffice cleanly so the next launch does not
    # enter the crash-recovery prompt. Force-kill is only a last resort after timeout.
    activate(g,"customer-response")
    cmd(g,"xdotool key ctrl+q; sleep 2")
    cmd(g,"for i in $(seq 20); do pgrep -x soffice.bin >/dev/null || exit 0; sleep 1; done; pkill -x soffice.bin 2>/dev/null || true; sleep 2")
    # Original input copies are immutable for this run.
    cmd(g,"cp /home/user/Documents/MECH03/baseline/service-adjustments.ods /home/user/Documents/MECH03/service-adjustments.ods; "
          "cp /home/user/Documents/MECH03/baseline/customer-response.odt /home/user/Documents/MECH03/customer-response.odt")
    pair=__import__("tasks.mechanism_expansion_v1.mech03",fromlist=["setup"])
    pair._SETUP.discard(f"{getattr(setup_controller,'vm_ip','')}:{getattr(setup_controller,'server_port','')}")
    pair.setup(setup_controller,"A")
    pair.setup(setup_controller,"B")
    time.sleep(2)
def main():
    runid="mech03-guest-control-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+str(os.getpid())
    OUTROOT.mkdir(parents=True,exist_ok=True);out=OUTROOT/runid;out.mkdir(parents=True,exist_ok=False);(out/"overlays").mkdir()
    os.environ.update({"SWCUB_RUN_ID":runid,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
      "SWCUB_RESOURCE_LEDGER":str(out/"resource-events.jsonl")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None)
    identity=ensure_resource_identity(out/"resource-events.jsonl")
    env=None;report={"run_id":runid,"case_id":"MECH-03","task_version":"0.6.0",
                     "kind":"scripted_gui_controls","control_version":"0.1.8","model_used":False,"status":"starting",
                     "external_containers_stopped":False,"resource_identity":identity.run_id}
    try:
        if not IMAGE.is_file():raise FileNotFoundError(IMAGE)
        if not (ASSETS/"mechanism_expansion_v1/mech03/service-adjustments.ods").is_file():
            raise FileNotFoundError("MECH-03 assets absent; run build_mech03_assets.py")
        tasks=[load_task(str(TASK_A)),load_task(str(TASK_B))]
        report["loaded_task_ids"]=[t.id for t in tasks]
        env=combo.boot(str(IMAGE),str(out/"cache"));report["setup"]=combo.setup_tasks(env,tasks)
        time.sleep(5);g=Guest(env);setup_controller=env.setup_controller
        screenshot(g,out/"initial.png");report["initial_focus"]=g.active_window_info()
        # Positive control: B edits the initially frontmost Writer, then A switches to Calc.
        report["positive_focus_writer"]=g.active_window_info();edit_reply(g)
        report["positive_focus_calc"]=switch_alt_tab(g,"service-adjustments");type_amount(g)
        report["positive_focus_after_save"]=g.active_window_info()
        report["positive_state"]=state(g);screenshot(g,out/"positive.png")
        report["positive_joint_pass"]=all(report["positive_state"][r]["score"]==1.0 for r in ("A","B"))
        if not report["positive_joint_pass"]:raise AssertionError("MECH-03 GUI positive control failed")
        reset_docs(g,setup_controller)
        # Fixed interleaving negative control: B finishes correctly in Writer, leaves it foreground;
        # A's already-planned Calc text entry is dispatched without re-observation/refocus.
        switch_alt_tab(g,"service-adjustments")
        preplanned={"intended_window":"service-adjustments","action":"type 1250.00 + Enter + Ctrl+S"}
        switch_alt_tab(g,"customer-response");edit_reply(g)
        before=g.active_window_info()
        cmd(g,"xdotool type --clearmodifiers --delay 20 '1250.00'; xdotool key Return; sleep .5; xdotool key ctrl+s; sleep 2")
        after=g.active_window_info()
        report["negative_state"]=state(g);report["stale_plan"]=preplanned
        report["misroute"]={"actual_window_before":before,"actual_window_after":after,
             "target_mismatch":not ("service-adjustments" in (before.get("title") or "").casefold()),
             "wrong_app_effect":report["negative_state"]["B"]["score"]==0.0 and report["negative_state"]["A"]["score"]==0.0}
        screenshot(g,out/"negative.png")
        report["negative_control_passed"]=report["misroute"]["target_mismatch"] and report["misroute"]["wrong_app_effect"]
        if not report["negative_control_passed"]:raise AssertionError("MECH-03 focus negative lacked input-routing effect")
        report["status"]="passed"
    except Exception as e:
        report["status"]="invalid_infra_or_control_failure";report["error"]=f"{type(e).__name__}: {e}";report["traceback"]=traceback.format_exc()[-5000:]
    finally:
        close=False
        if env:
            try:env.close();close=True
            except Exception as e:report["close_error"]=f"{type(e).__name__}: {e}"
        report["guest_close_succeeded"]=close
        ev=[]
        try:ev=[json.loads(l) for l in (out/"resource-events.jsonl").read_text().splitlines() if l.strip()]
        except Exception:pass
        report["owned_guest_destroyed"]=any(x.get("event")=="destroyed" and x.get("resource_type")=="container" for x in ev)
        (out/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
        print(json.dumps({"status":report["status"],"positive_joint_pass":report.get("positive_joint_pass"),
          "negative_control_passed":report.get("negative_control_passed"),"initial_focus":report.get("initial_focus"),
          "misroute":report.get("misroute"),"artifacts":str(out),"error":report.get("error")},ensure_ascii=False))
    return 0 if report["status"]=="passed" else 1
if __name__=="__main__":raise SystemExit(main())
