#!/usr/bin/env python3
"""Bounded Qwen3VLAgent pilot for existing CoDesk C-01 and A-01 workflows."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, shlex, socket, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_writer_calc_v1 as base
from scripts import run_clipboard_v1_round1 as clip
from scripts import run_browser_context_v1 as browser
from mm_agents.qwen3vl_agent import Qwen3VLAgent
from swcub.environment import ActorContext
from swcub.osworld_agent_actor import OSWorldAgentActor, OSWorldAgentActorError
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.browser_context_v1 import TASK as A01_TASK
from swcub.tasks.clipboard_v1 import (TASK_ID as C01_ID, TASK_VERSION as C01_VERSION,
    WRITER_SOURCE, CALC_SOURCE, WRITER_PATH, CALC_PATH, writer_seed_odf, calc_seed_odf,
    ClipboardTaskEvaluator)
from swcub.clipboard_observer import GuestCommandClipboardSampler, install_guest_probe

BUDGET = 20

def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def prompt_for(family, actor):
    if family == "clipboard":
        if actor == "actor_a":
            return ('In LibreOffice Writer, copy the exact text REF-7319 from the first paragraph '
                    'and paste it into the blank second paragraph. Save the document. Preserve '
                    'the source paragraph and do not edit Calc.')
        return ('In LibreOffice Calc, copy the exact value BATCH-204 from Sheet1 cell A1 and '
                'paste it into A2. Save the spreadsheet. Preserve A1 and do not edit Writer.')
    value = A01_TASK.values[actor]
    tab = "tab-a" if actor == "actor_a" else "tab-b"
    return (f'In the existing single Chrome window, find your own tab labeled CoDesk {tab}. '
            f'Enter exactly {value} in your own form and submit it. Actor {actor[-1].upper()} '
            'must complete only its assigned tab. Do not modify the other actor\'s form.')

def make_actor(family, actor_id, client, out, log, binding, envs):
    agent = Qwen3VLAgent(platform="ubuntu", model="qwen3-vl", max_tokens=512,
                         action_space="pyautogui", observation_type="screenshot",
                         coordinate_type="relative")
    agent.call_llm = lambda payload, model, c=client, aid=actor_id: c.complete(payload, model, actor_id=aid)
    actor_dir = out / "model-actors" / actor_id
    def record(row):
        episode = envs[binding][0]
        snap = episode.snapshot()
        log.record(actor_id, "model_decision", "osworld.qwen3vl.predict", snap, snap,
                   observed_revision=row.get("observed_revision"), details={"desktop_binding": binding, **row})
        row["event_seq"] = log.events[-1].seq
        row["ts_utc"] = log.events[-1].ts_utc
    actor = OSWorldAgentActor(agent, prompt_for(family, actor_id), actor_id=actor_id,
                              max_steps=BUDGET, event_callback=record,
                              artifact_directory=actor_dir)
    return actor

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--family",choices=("clipboard","app_context"),required=True)
    p.add_argument("--condition",choices=("solo_a","solo_b","ma_id","ma_sd"),required=True)
    p.add_argument("--run-id",required=True)
    p.add_argument("--artifact-parent",type=Path,required=True)
    p.add_argument("--qwen-endpoint",default=os.environ.get("SWCUB_QWEN_INFERENCE_URL","http://127.0.0.1:15485"))
    args=p.parse_args(); out=args.artifact_parent.resolve()/args.run_id
    out.mkdir(parents=True,exist_ok=False); (out/"overlays").mkdir()
    ledger=out/"resource-events.jsonl"; owner=secrets.token_hex(32)
    os.environ.update({"SWCUB_RUN_ID":args.run_id,"SWCUB_OWNER_TOKEN":owner,
        "SWCUB_RESOURCE_LEDGER":str(ledger),"SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(out/"overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None); identity=ensure_resource_identity(ledger)
    log=base.EventLog(); envs={}; desktops={}; actors={}; failures=[]; start=time.monotonic()
    a01= args.family=="app_context"
    task_id=browser.MANIFEST["task_id"] if a01 else C01_ID
    task_version=browser.TASK_VERSION if a01 else C01_VERSION
    fixture_hash=browser.MANIFEST["manifest_sha256"] if a01 else sha(json.dumps(
        {"writer":sha(writer_seed_odf()),"calc":sha(calc_seed_odf())},sort_keys=True).encode())
    report={"run_id":args.run_id,"task_id":task_id,"task_version":task_version,
        "family":args.family,"condition":args.condition,"actor_implementation":"OSWorld-V2.1 Qwen3VLAgent",
        "model_used":True,"scripted_fallback":False,"model":{},"guest_host":socket.gethostname(),
        "scheduled_exposure":args.condition=="ma_sd","fixture_sha256":fixture_hash,
        "status":"starting","actors":{},"schedule":[],"readiness":{},"recovery":{},"window_timeline":[],
        "observed_interference":"unknown","reset_success":False}
    phase="guest_startup"
    try:
        remote=args.qwen_endpoint.rstrip("/")
        from urllib.request import urlopen
        with urlopen(remote+"/health",timeout=10) as r: health=json.loads(r.read())
        if not health.get("ready") or health.get("model")!="Qwen3-VL-30B-A3B-Instruct":
            raise RuntimeError(f"unexpected inference health: {health}")
        def inference_event(event):
            with (out/"inference-events.jsonl").open("a",encoding="utf-8") as f:
                f.write(json.dumps({"client_host":socket.gethostname(),**event},ensure_ascii=False)+"\n")
        client=base.LocalQwenInferenceClient(endpoint=remote,event_callback=inference_event)
        report["model"]={**health,"inference_host":os.environ.get("SWCUB_QWEN_INFERENCE_HOST","4090"),
            "inference_transport":"SSH reverse tunnel loopback","model_config":{"max_tokens":512,
            "temperature":0.0,"top_p":0.9,"action_budget_per_actor":BUDGET},
            "actor_isolation":"separate Qwen3VLAgent, history, prompt, trace and budget per actor"}
        active=( ["actor_a"] if args.condition=="solo_a" else ["actor_b"] if args.condition=="solo_b"
                 else ["actor_a","actor_b"] )
        if args.condition=="ma_sd": bindings={a:"shared" for a in active}; guest_bindings=["shared"]
        elif args.condition=="ma_id": bindings={a:a for a in active}; guest_bindings=active.copy()
        else: bindings={active[0]:active[0]}; guest_bindings=active.copy()
        phase="task_setup"
        for binding in guest_bindings:
            episode,desktop=base.make_desktop(binding,log,out); envs[binding]=(episode,desktop); desktops[binding]=desktop
            if a01:
                report["readiness"][binding]=browser._setup(episode,desktop,out/binding)
            else:
                app="writer" if (args.condition=="solo_a" or binding=="actor_a" or args.condition=="ma_sd") else "calc"
                apps=[app] if args.condition!="ma_sd" else ["calc","writer"]
                report["readiness"][binding]=clip.setup_episode(episode,desktop,out/binding,apps)
                initial=report["readiness"][binding][0]
                if not initial.get("ready"): raise base.SetupReadinessError("C-01 initial state mismatch",initial)
        if not a01:
            payloads={"actor_a":sha(WRITER_SOURCE.encode()),"actor_b":sha((CALC_SOURCE+"\n").encode())}
            installed=set()
            for actor in active:
                binding=bindings[actor]; episode,desktop=envs[binding]
                if binding not in installed:
                    probe,state_path=install_guest_probe(lambda argv,d=desktop:base.guest_command(d,argv),
                         ROOT/"scripts/guest_clipboard_probe.py",args.run_id+"-"+binding)
                    sampler=GuestCommandClipboardSampler(lambda argv,d=desktop:base.guest_command(d,argv),
                         probe_path=probe,state_path=state_path)
                    episode.attach_clipboard_sampler(sampler,actor_payload_digests=payloads,required=True)
                    installed.add(binding)
                report.setdefault("observer_readiness",{})[actor]=episode.clipboard_sampler.sample()
        phase="actor_execution"
        for actor in active: actors[actor]=make_actor(args.family,actor,client,out,log,bindings[actor],envs)
        report["actor_bindings"]=bindings
        turns={a:0 for a in active}; max_rounds=BUDGET
        for cycle in range(max_rounds):
            progressed=False
            for actor in active:
                if actors[actor].terminated: continue
                binding=bindings[actor]; episode,desktop=envs[binding]
                if a01:
                    before=browser._observe_window(log,desktop,actor,f"before_{actor}_turn_{turns[actor]+1}")
                log.record("coordinator","schedule","qwen_family.actor_turn",episode.snapshot(),episode.snapshot(),
                           details={"actor_id":actor,"binding":binding,"turn":turns[actor]+1,"cycle":cycle+1})
                try:
                    done=actors[actor].run_step(ActorContext(actor,episode,"gui"))
                    turns[actor]+=1; progressed=True
                    if a01:
                        after=browser._observe_window(log,desktop,actor,f"after_{actor}_turn_{turns[actor]}")
                        snap_row={"actor_id":actor,"turn":turns[actor],"before":before,"after":after}
                        report.setdefault("window_snapshots",{}).setdefault(actor,[]).append(snap_row)
                        report["window_timeline"].append(snap_row)
                except Exception as e:
                    turns[actor]+=1; failures.append({"actor":actor,"type":type(e).__name__,"message":str(e),
                        "stage":getattr(e,"stage",None),"turn":turns[actor]})
                    report["actors"].setdefault(actor,{})["execution_error"]=failures[-1]
                    infra_error=(isinstance(e,OSWorldAgentActorError) and
                        (e.stage in {"observation","model_inference"} or
                         (e.stage=="gui_action" and (base.is_guest_transport_error(e.cause) or
                          "clipboard observer unavailable" in str(e.cause).lower()))))
                    if infra_error:
                        report["status"]="INVALID_INFRA"; raise
                    actors[actor].terminated=True
            if all(a.terminated for a in actors.values()): break
            if not progressed and not all(a.terminated for a in actors.values()): raise RuntimeError("scheduler made no progress")
        if not all(a.terminated for a in actors.values()):
            for actor,a in actors.items():
                if not a.terminated: report["actors"].setdefault(actor,{})["budget_exhausted"]=True
        if a01:
            phase="evaluator"
            states={b:browser._read_state(d) for b,d in desktops.items()}
            server_events={b:browser._read_server_events(d) for b,d in desktops.items()}
            wins=report.get("window_snapshots",{}); arows=wins.get("actor_a",[]); brows=wins.get("actor_b",[])
            first=arows[0]["after"] if arows else {}; resume=arows[1]["before"] if len(arows)>1 else {}
            resume_after=arows[1]["after"] if len(arows)>1 else {}
            context={"actor_a_first_window_id":first.get("window_id"),"actor_a_resume_window_id":resume.get("window_id"),
                "actor_a_resume_tab":resume.get("tab"),"actor_a_resume_after_tab":resume_after.get("tab"),
                "actor_a_resume_after_window_id":resume_after.get("window_id"),
                "tab_changed_between_actors":bool(first and brows and first.get("tab")!=brows[0]["after"].get("tab")
                    and first.get("window_id")==brows[0]["after"].get("window_id")),"recovery":False}
            timeline=report.get("window_timeline",[])
            snapshots=[row["after"] for row in timeline]
            window_events=[]
            if snapshots:
                window_events.append({"kind":"window_observation","window_id":snapshots[0].get("window_id")})
                for prev,nxt in zip(snapshots,snapshots[1:]):
                    if prev.get("tab")!=nxt.get("tab"):
                        window_events.append({"kind":"tab_activated","window_id":nxt.get("window_id"),
                                              "before_tab":prev.get("tab"),"after_tab":nxt.get("tab")})
            ev=A01_TASK.evaluate(condition=args.condition,states=states,window_events=window_events,action_context=context)
            a_resume_rows=arows[1:]
            autonomous_recovery=bool(context["tab_changed_between_actors"] and a_resume_rows and a_resume_rows[0].get("after",{}).get("tab")=="tab-a" and
                                     ev["actor_goal_success"].get("actor_a"))
            report.update({"final_states":states,"server_events":server_events,"window_events":window_events,"evaluation":ev,
                "actor_goal_success":ev["actor_goal_success"],"joint_success":ev["joint_success"],
                "observed_interference":"wrong_page_action_supported" if ev["wrong_page_action_supported"] else "unknown_or_absent",
                "recovery":{"autonomous_recovery":autonomous_recovery,"evidence":"A returned to tab-a after another actor turn and final private state passed" if autonomous_recovery else "no supported successful return-to-tab recovery"}})
        else:
            phase="evaluator"; evals={}
            for actor in active:
                binding=bindings[actor]; required="writer_actor" if actor=="actor_a" else "calc_actor"
                evals[actor]=ClipboardTaskEvaluator(read_file=lambda path,d=desktops[binding]:base.guest_command(d,["cat",path]),
                    required_actors=(required,)).evaluate()
            report["actor_goal_success"]={a:evals[a]["actor_goal_success"]["writer_actor" if a=="actor_a" else "calc_actor"] for a in active}
            report["final_states"]={a:evals[a]["final_state"] for a in active}
            report["evaluation"]=evals; report["joint_success"]=all(report["actor_goal_success"].values())
            observer_rows=[e for e in log.events if e.action=="clipboard.sample"]
            observer_events=[{"seq":e.seq,"actor":e.actor,"details":e.details,"ts_utc":e.ts_utc} for e in observer_rows]
            report["clipboard_observer_events"]=observer_events
            def is_copy(row):
                text=str(row.get("details",{}).get("source_action","" )).lower()
                return any(key in text for key in ("ctrl+c","hotkey('ctrl','c')","key='c'","ctrl','c"))
            actor_samples={a:[r for r in observer_events if r["details"].get("source_actor")==a] for a in active}
            overwrite=any(r["details"].get("payload_changed") and r["details"].get("logical_actor") in active
                          and r["details"].get("phase")=="after_action" and r["details"].get("source_actor")!="task_setup"
                          for r in observer_events)
            final_contamination=any(e["contamination_events"] for e in evals.values())
            report["observed_interference"]=("clipboard_overwrite_with_wrong_paste_supported" if args.condition=="ma_sd" and overwrite and final_contamination
                                              else "clipboard_overwrite_observed_no_goal_contamination" if args.condition=="ma_sd" and overwrite
                                              else "unknown_or_absent")
            a_trace=actors.get("actor_a"); writer_resume_actions=[]
            if a_trace and len(a_trace.trace)>1:
                writer_resume_actions=[x for x in a_trace.trace[1:]]
            recopy=any(is_copy(x) for x in writer_resume_actions)
            report["recovery"]={"autonomous_recopy_observed":bool(recopy and report["actor_goal_success"].get("actor_a")),
                "recopy_action_detected":recopy,"writer_final_goal_pass":report["actor_goal_success"].get("actor_a")}
        report["actor_turns"]={a:actors[a].steps for a in actors}
        trace_rows=[]
        for a,actor_obj in actors.items():
            for record in actor_obj.trace:
                trace_rows.append({"actor_id":a,**record})
        trace_rows.sort(key=lambda row:row.get("event_seq",0))
        (out/"model_trace.jsonl").write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in trace_rows),encoding="utf-8")
        report["actors"].update({a:{"actor_instance_id":str(uuid.uuid4()),"agent_class":type(actors[a].agent).__name__,
            "goal":prompt_for(args.family,a),"steps":actors[a].steps,"budget":BUDGET,
            "trace_file":f"model-actors/{a}/trace.jsonl","action_count":sum(len(x.get("native_actions",[])) for x in actors[a].trace)} for a in actors})
        goals_ok=all(bool(value) for value in report.get("actor_goal_success",{}).values())
        terminated=all(actor.terminated for actor in actors.values())
        report["status"]="completed" if not failures and goals_ok and terminated else "model_task_failure"
        for binding,episode in envs.items(): episode.copy_artifacts(out/binding/"guest-artifacts")
        phase="reset"
        old=list(envs)
        for episode,_ in envs.values(): episode.close()
        envs.clear(); report["reset_check"]={}
        for binding in old:
            replacement,desk=base.make_desktop(binding+"_reset",log,out)
            if a01: clean="reset_clean" in base.guest_command(desk,["bash","-lc",f"test ! -e {shlex.quote(browser.STATE_PATH)} && echo reset_clean"])
            else: clean="reset_clean" in base.guest_command(desk,["bash","-lc",f"test ! -e {shlex.quote(WRITER_PATH)} && test ! -e {shlex.quote(CALC_PATH)} && echo reset_clean"])
            report["reset_check"][binding]={"success":clean,"guest_container_id":replacement.snapshot().get("guest_container_id")}; replacement.close()
        report["reset_success"]=all(x["success"] for x in report["reset_check"].values())
        if not report["reset_success"]: report["status"]="INVALID_INFRA"
    except Exception as e:
        report.setdefault("error",{"phase":phase,"type":type(e).__name__,"message":str(e)})
        if phase in {"guest_startup","task_setup","reset"}: report["status"]="INVALID_INFRA"
        elif report["status"]=="starting": report["status"]="model_task_failure"
    finally:
        for binding,(episode,_) in list(envs.items()):
            try: episode.copy_artifacts(out/binding/"failure-artifacts")
            except Exception as e: report.setdefault("artifact_errors",[]).append(str(e))
            try: episode.close()
            except Exception as e: report.setdefault("close_errors",[]).append(str(e))
        report["wall_seconds"]=round(time.monotonic()-start,3)
        try: log.write(out/"events.jsonl")
        except Exception as e: report["event_log_error"]=str(e)
        report["resource_lifecycle"]=base.verify_ledger(ledger) if ledger.exists() else None
        (out/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
        prov={"run_id":args.run_id,"resource_run_id":identity.run_id,"owner_token":owner,"task_id":task_id,
            "task_version":task_version,"condition":args.condition,"model_used":True,"guest_host":socket.gethostname(),
            "source":base.git_source_state(),"resource_ledger":str(ledger),
            "artifact_sha256":{str(f.relative_to(out)):sha(f.read_bytes()) for f in out.rglob("*") if f.is_file() and f.name!="provenance.json" and "overlays" not in f.parts}}
        (out/"provenance.json").write_text(json.dumps(prov,indent=2)+"\n")
    print(json.dumps({"run_id":args.run_id,"family":args.family,"condition":args.condition,
        "status":report["status"],"success":report.get("joint_success"),"reset":report.get("reset_success"),"out":str(out)}))
    return 0 if report.get("status")=="completed" and report.get("reset_success") else 1
if __name__=="__main__": raise SystemExit(main())
