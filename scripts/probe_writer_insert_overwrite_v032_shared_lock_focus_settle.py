#!/usr/bin/env python3
"""Scripted LibreOffice Insert/Overwrite state-scope feasibility control."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, secrets, shlex, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import run_writer_calc_v1 as base
from scripts import run_workflows_v1 as core
from scripts import run_sol_writer_overwrite_v1 as solrunner
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity

CASE_ID="CODESK-NEXT-EDIT-OVERWRITE-001"
VERSION="0.3.2-scripted-shared-lock-focus-settle"
DOC=("Release status: STATUS | HOLD-FOR-REVIEW",
     "Reviewer code: ____; change only this fixed-width code.",
     "Guard phrase: DO-NOT-ALTER-THIS-LINE")
A_PHRASE="HOLD-FOR-REVIEW"
A_INSERT="READY "
B_PLACEHOLDER="____"
B_REPLACEMENT="AB12"

def window_identity(desktop):
    command=("wid=$(xdotool getactivewindow 2>/dev/null || true); "
             "title=$(xdotool getwindowname \"$wid\" 2>/dev/null || true); "
             "class=$(xprop -id \"$wid\" WM_CLASS 2>/dev/null | tail -1 || true); "
             "printf \"%s\\t%s\\t%s\\n\" \"$wid\" \"$title\" \"$class\"")
    parts=base.guest_command(desktop,["bash","-lc",command]).strip().split("\t")
    while len(parts)<3: parts.append("")
    return {"xid":parts[0],"title":parts[1],"wm_class":parts[2]}

def capture(ctx,out,label):
    obs=ctx.observe()
    shot=obs.get("screenshot")
    tree=obs.get("accessibility_tree")
    folder=out/"observations"
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/f"{label}.png"
    tree_target=folder/f"{label}.accessibility.xml"
    if isinstance(shot,bytes) and shot:
        target.write_bytes(shot)
    if isinstance(tree,str) and tree.strip():
        tree_target.write_text(tree,encoding="utf-8")
    return {"screenshot_available":isinstance(shot,bytes) and bool(shot),
            "screenshot_sha256":hashlib.sha256(shot).hexdigest() if isinstance(shot,bytes) else None,
            "observation_file":str(target.relative_to(out)) if isinstance(shot,bytes) and shot else None,
            "accessibility_tree_available":isinstance(tree,str) and bool(tree.strip()),
            "accessibility_tree_sha256":hashlib.sha256(tree.encode()).hexdigest() if isinstance(tree,str) else None,
            "accessibility_tree_file":str(tree_target.relative_to(out)) if isinstance(tree,str) and tree.strip() else None,
            "mode_readout_claimed":False}

def search_and_collapse(ctx,text):
    ctx.press_key("ctrl+f"); ctx.type_text(text); ctx.press_key("enter"); ctx.press_key("esc"); ctx.press_key("right")

def b_toggle_and_edit(ctx, *, restore_to_insert=False):
    # Re-focus the Writer canvas before deterministic keyboard navigation.
    ctx.execute_gui_action("pyautogui.click(600, 282)")
    # Fixed-width reviewer code is column 15 of line 2. Do not select text:
    # overwrite-mode must operate on the four existing placeholder characters.
    ctx.execute_gui_action("pyautogui.hotkey('ctrl', 'home')")
    ctx.execute_gui_action("pyautogui.press('down')")
    ctx.execute_gui_action("pyautogui.press('home')")
    ctx.execute_gui_action("pyautogui.press('right', presses=15)")
    ctx.execute_gui_action("pyautogui.press('insert')")
    ctx.execute_gui_action("pyautogui.write('AB12')")
    ctx.execute_gui_action("pyautogui.hotkey('ctrl', 's')")
    time.sleep(8)  # wait for Writer save to settle before sampling
    # Negative control leaves the same view in INS after the same code edit.
    # The positive control intentionally ends in OVR.
    if restore_to_insert:
        ctx.execute_gui_action("pyautogui.press('insert')")
    # Hand the shared view back with its caret at A's intended insertion point.
    ctx.execute_gui_action("pyautogui.hotkey('ctrl', 'home')")
    ctx.execute_gui_action("pyautogui.press('right', presses=25)")

def a_stale_insert(ctx):
    # Cursor is already at the insertion point; only the keyboard text batch is stale.
    ctx.execute_gui_action("pyautogui.write('READY ')")
    ctx.execute_gui_action("pyautogui.hotkey('ctrl', 's')")

def writer_text(desktop):
    raw=base.guest_command(desktop,["cat",base.WRITER_PATH],timeout=30)
    return base.GuestLibreOfficeBindingEvaluator._parse_writer(raw)

def prepare(episode,desktop,out,binding):
    data=base.render_writer_fodt(list(DOC))
    b64=base64.b64encode(data).decode("ascii")
    code=("from pathlib import Path; import base64; "
          f"p=Path({base.WRITER_PATH!r}); p.parent.mkdir(parents=True,exist_ok=True); "
          f"p.write_bytes(base64.b64decode({b64!r}))")
    episode.cli_action("task_setup","python3 -c "+shlex.quote(code))
    launch=(f"nohup soffice --nologo --norestore --nofirststartwizard --writer "
            f"{shlex.quote(base.WRITER_PATH)} >/tmp/codesk-edit-overwrite.log 2>&1 </dev/null & "
            "echo $! >/tmp/codesk-edit-overwrite.pid; sleep 7")
    episode.cli_action("task_setup","bash -lc "+shlex.quote(launch))
    try:
        ready=solrunner.wait_writer_ready(episode,desktop,out,timeout=300)
    except base.SetupReadinessError as exc:
        def diagnostic(argv):
            try: return {"output":base.guest_command(desktop,argv,timeout=20)}
            except Exception as err: return {"error":f"{type(err).__name__}: {err}"}
        details={"readiness_error":str(exc),
            "launch_log":diagnostic(["bash","-lc","cat /tmp/codesk-edit-overwrite.log 2>&1 || true"]),
            "pid_file":diagnostic(["bash","-lc","cat /tmp/codesk-edit-overwrite.pid 2>&1 || true"]),
            "office_processes":diagnostic(["bash","-lc","ps -eo pid,stat,cmd | grep -E '[s]office|[s]office.bin' || true"]),
            "display_environment":diagnostic(["bash","-lc","echo DISPLAY=$DISPLAY; xdotool getactivewindow getwindowname 2>&1 || true"]),
            "binary_version":diagnostic(["bash","-lc","soffice --version 2>&1"])}
        (out/"setup-validation").mkdir(parents=True,exist_ok=True)
        (out/"setup-validation"/f"{binding}-launch-diagnostics.json").write_text(json.dumps(details,indent=2)+"\n")
        raise
    episode.refresh_observation(source="writer_overwrite_ready")
    setup_ctx=ActorContext("task_setup",episode,"gui")
    setup_ctx.execute_gui_action("pyautogui.hotkey('ctrl', 'home')")
    setup_ctx.execute_gui_action("pyautogui.press('right', presses=25)")
    time.sleep(5)  # let Writer settle after initialization
    return {"ready":ready,"initial_text":writer_text(desktop),
            "window":window_identity(desktop),"cursor_seed_actions":["ctrl+home","right x25"]}

def probe_condition(condition,out,log,started,all_eps):
    shared=condition!="ma_id"
    bindings={"actor_a":"shared","actor_b":"shared"} if shared else {"actor_a":"actor_a","actor_b":"actor_b"}
    guest_bindings=["shared"] if shared else ["actor_a","actor_b"]
    eps={}; desks={}; setups={}
    for binding in guest_bindings:
        ep,desk=base.make_desktop(binding,log,out,require_a11y_tree=False)
        eps[binding]=ep; desks[binding]=desk; all_eps.append(ep)
        setups[binding]=prepare(ep,desk,out,binding)
    lock=core.PerActionLock(started) if condition=="ma_sd_lock" else None
    contexts={}
    for actor,binding in bindings.items():
        env=core.LockedActionEnvironment(eps[binding],lock) if lock else eps[binding]
        contexts[actor]=ActorContext(actor,env,"gui")
    initial={actor:{"text":setups[binding]["initial_text"],"window":window_identity(desks[binding])}
             for actor,binding in bindings.items()}
    # A observes and holds its already-planned visible keyboard batch before B acts.
    observation=capture(contexts["actor_a"],out,f"{condition}-a-before-b")
    held=[A_INSERT,"ctrl+s"]
    b_toggle_and_edit(
        contexts["actor_b"],
        restore_to_insert=(condition=="ma_sd_ins_control"))
    time.sleep(5)
    after_b={"text":writer_text(desks[bindings["actor_b"]]),
             "window":window_identity(desks[bindings["actor_b"]]),
             "observation":capture(contexts["actor_b"],out,f"{condition}-after-b")}
    gate_revision=contexts["actor_a"]._observed_revision
    a_stale_insert(contexts["actor_a"])
    time.sleep(5)
    final={actor:{"text":writer_text(desks[binding]),
                  "window":window_identity(desks[binding])}
           for actor,binding in bindings.items()}
    expected_a="Release status: STATUS | READY HOLD-FOR-REVIEW"
    expected_b="Reviewer code: AB12"
    a_text=final["actor_a"]["text"]
    a_goal_exact=expected_a in a_text
    review_status_preserved="HOLD-FOR-REVIEW" in a_text
    guard_phrase_preserved="Guard phrase: DO-NOT-ALTER-THIS-LINE" in a_text
    a_ok=a_goal_exact and review_status_preserved and guard_phrase_preserved
    b_ok=expected_b in final["actor_b"]["text"]
    mode_signature=("OVERWRITE_EFFECT" if "READY OR-REVIEW" in a_text
                    else "INSERT_EFFECT" if a_ok else "OTHER_OR_NO_EFFECT")
    a_events=[e for e in log.events if e.actor=="actor_a" and e.kind=="gui"]
    b_events=[e for e in log.events if e.actor=="actor_b" and e.kind=="gui"]
    first_a_after_b=next((e for e in a_events if e.observed_revision==gate_revision
                          and e.details.get("stale_due_other_actor")),None)
    result={"condition":condition,"bindings":bindings,"initial":initial,
        "a_observation":observation,"held_a_plan":held,
        "b_after_state_change":after_b,"final":final,
        "evaluation":{"actor_a_goal_exact":a_goal_exact,
            "actor_a_review_status_preserved":review_status_preserved,
            "actor_a_guard_phrase_preserved":guard_phrase_preserved,
            "actor_a_guard_preserved":review_status_preserved and guard_phrase_preserved,
            "actor_b_code_exact":b_ok,"task_success":a_ok and b_ok,
            "mode_signature":mode_signature,
            "misinserted_guard_prefix":"READY OR-REVIEW" in a_text},
        "protocol":{"same_shared_window":shared and
            after_b["window"].get("xid")==initial["actor_a"]["window"].get("xid"),
            "a_old_observation_revision":gate_revision,
            "a_first_action_stale_due_other_actor":bool(first_a_after_b),
            "a_first_action_sequence":first_a_after_b.seq if first_a_after_b else None,
            "b_gui_action_count":len(b_events)},
        "negative_control_mode_restored_to_insert":condition=="ma_sd_ins_control",
        "control_signature_observed":{
            "positive_overwrite_signature":bool(
                condition in {"ma_sd","ma_sd_lock"} and
                mode_signature=="OVERWRITE_EFFECT" and b_ok and
                review_status_preserved is False and guard_phrase_preserved and
                shared and first_a_after_b is not None),
            "insert_mode_negative_control_pass":bool(
                condition=="ma_sd_ins_control" and a_ok and b_ok and
                mode_signature=="INSERT_EFFECT" and shared and
                first_a_after_b is not None),
            "mode_state_verified":False,
            "manual_mode_adjudication_required":True,
            "limitation":"mode state must be manually confirmed in saved GUI screenshot/accessibility evidence; text signature alone is not an independent mode readout"},
        "lock":lock.summary() if lock else {"enabled":False}}
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--run-id",required=True); ap.add_argument("--artifact-parent",type=Path,required=True)
    ap.add_argument("--conditions",default="ma_id,ma_sd,ma_sd_ins_control,ma_sd_lock")
    args=ap.parse_args(); conditions=tuple(x.strip() for x in args.conditions.split(",") if x.strip())
    allowed={"ma_id","ma_sd","ma_sd_lock","ma_sd_ins_control"}
    if not conditions or any(x not in allowed for x in conditions): raise RuntimeError("invalid --conditions")
    parent=args.artifact_parent.expanduser().resolve()
    if not parent.is_relative_to(Path("/mnt/raid1")): raise RuntimeError("artifacts must be on RAID1")
    out=parent/args.run_id; out.mkdir(parents=True,exist_ok=False); (out/"overlays").mkdir()
    ledger=out/"resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID":args.run_id,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER":str(ledger),"SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(out/"overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None)
    identity=ensure_resource_identity(ledger); log=EventLog(); all_eps=[]; started=time.monotonic()
    runtime_image="swcub/osworld-v2.1-qemu-runtime:local"
    os.environ["OSWORLD_V2_DIR"]=str(base.OSWORLD_V2_DIR)
    guest_image=base.resolve_guest_image_path()
    os.environ["SWCUB_OSWORLD_GUEST_IMAGE"]=str(guest_image)
    os.environ["SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE"]=runtime_image
    os.environ["OSWORLD_DOCKER_RUNTIME_IMAGE"]=runtime_image
    os.environ["SWCUB_OSWORLD_CACHE_DIR"]=str(parent/"osworld-cache")
    if not guest_image.is_file():
        raise RuntimeError("pinned local Guest qcow2 is missing")
    image_check=subprocess.run(["docker","image","inspect",runtime_image,"--format","{{.Id}}"],
        check=True,capture_output=True,text=True,timeout=15)
    runtime_image_id=image_check.stdout.strip()
    if runtime_image_id!="sha256:002d09fa7cc4e08ce5321c3d0a261e336a2c17651726f8538bca4dcf991e82ec":
        raise RuntimeError("pinned local runtime image ID differs from audited image")
    report={"run_id":args.run_id,"case_id":CASE_ID,"task_version":VERSION,
        "runtime":{"runtime_image":runtime_image,"runtime_image_id":runtime_image_id,
                   "guest_image":str(guest_image),"artifacts_on_raid1":True},
        "candidate":"LibreOffice Writer Insert/Overwrite mode scope","model_used":False,
        "evidence_level":"scripted GUI/ODF semantic control; not GPT-6-Sol task evidence",
        "source_state":base.git_source_state(),"status":"starting","conditions":{}}
    try:
        for condition in conditions:
            d=out/condition; d.mkdir(); report["conditions"][condition]=probe_condition(condition,d,log,started,all_eps)
        report["status"]="completed"
    except Exception as exc:
        report["status"]="probe_error"; report["error"]={"type":type(exc).__name__,"message":str(exc)}
    finally:
        for ep in all_eps:
            try: ep.copy_artifacts(out/"guest-artifacts"/ep.environment_id)
            except Exception: pass
            try: ep.close()
            except Exception as exc: report.setdefault("close_errors",[]).append(type(exc).__name__)
        report["wall_seconds"]=round(time.monotonic()-started,3)
        report["resource_lifecycle"]=base.verify_ledger(ledger) if ledger.exists() else None
        log.write(out/"events.jsonl")
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        (out/"provenance.json").write_text(json.dumps({"run_id":identity.run_id,
            "source":base.git_source_state(),"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+"\n")
    print(json.dumps({"run_id":args.run_id,"status":report["status"],
        "conditions":{k:v.get("evaluation") for k,v in report.get("conditions",{}).items()},
        "error":report.get("error"),"wall_seconds":report.get("wall_seconds"),"artifact_dir":str(out)}))
    return 0 if report["status"]=="completed" else 1
if __name__=="__main__": raise SystemExit(main())
