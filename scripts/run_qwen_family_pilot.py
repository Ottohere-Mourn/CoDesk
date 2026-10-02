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
            return ('In LibreOffice Writer, do not drag-select with the mouse. Press Ctrl+Home, then '
                    'Shift+End to select the entire first line REF-7319, and press Ctrl+C. In the '
                    'second paragraph, press Ctrl+End then Shift+Home to select the entire '
                    'placeholder line INSERT COPIED VALUE, then press Ctrl+V to replace it. '
                    'Save the document. '
                    'Preserve the source paragraph and do not edit Calc.')
        return ('In LibreOffice Calc, copy the exact value BATCH-204 from Sheet1 cell A1 and '
                'paste it into A2. Save the spreadsheet. Preserve A1 and do not edit Writer.')
    value = A01_TASK.values[actor]
    tab = "tab-a" if actor == "actor_a" else "tab-b"
    return (f'In the existing single Chrome window, switch to your own tab labeled CoDesk {tab} '
            f'(tab-a is Ctrl+1; tab-b is Ctrl+2). Enter exactly {value} in your own form and '
            f'submit it. Actor {actor[-1].upper()} must complete only its assigned tab. '
            'Do not modify the other actor\'s form.')

def make_actor(family, actor_id, client, out, log, binding, envs, action_boundary_callback=None):
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
                              artifact_directory=actor_dir,
                              action_boundary_callback=action_boundary_callback)
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
        gated = (not a01 and args.condition in {"ma_id", "ma_sd"})
        payload_digests = {"actor_a": sha(WRITER_SOURCE.encode()),
                           "actor_b": sha((CALC_SOURCE + "\n").encode())}
        gate = {"phase": "await_actor_a_copy" if gated else "disabled",
                "events": [], "sequence_valid": not gated,
                "scheduled_interleaving": gated,
                "shared_clipboard_expected": args.condition == "ma_sd"}
        report["clipboard_gate"] = gate

        def gate_event(name, actor, detail):
            binding = bindings[actor]; episode = envs[binding][0]
            log.record("coordinator", "schedule", "clipboard.gate." + name,
                       episode.snapshot(), episode.snapshot(), details={"actor_id": actor, **detail})
            event = log.events[-1]
            row = {"event": name, "actor_id": actor, "event_seq": event.seq,
                   "ts_utc": event.ts_utc, **detail}
            gate["events"].append(row)
            return row

        def action_boundary(actor_obj, action):
            actor = actor_obj.actor_id
            if gate["phase"] not in {"await_actor_a_copy", "await_actor_b_copy"}:
                return
            wanted = "actor_a" if gate["phase"] == "await_actor_a_copy" else "actor_b"
            if actor != wanted:
                return
            candidates = [e for e in log.events if e.action == "clipboard.sample"
                and e.actor == "clipboard_observer" and e.details.get("phase") == "after_action"
                and e.details.get("source_actor") == actor
                and e.details.get("logical_actor") == actor
                and e.details.get("digest_matches_actor_source") is True
                and e.details.get("payload_sha256") == payload_digests[actor]]
            row = candidates[-1] if candidates else None
            if row is None:
                return
            copy_action_event = next((e for e in reversed(log.events) if e.actor == actor
                                      and e.action == "osworld.step" and e.seq < row.seq), None)
            gate_event("actor_a_copy_action_completed" if actor == "actor_a"
                       else "actor_b_copy_action_completed", actor, {
                "gui_event_seq": copy_action_event.seq if copy_action_event else None,
                "source_action": row.details.get("source_action"),
                "complete_action_boundary": True})
            name = "clipboard_a_target_confirmed" if actor == "actor_a" else "clipboard_b_target_confirmed"
            ev = gate_event(name, actor, {
                "clipboard_sample_seq": row.seq, "payload_sha256": row.details.get("payload_sha256"),
                "generation": row.details.get("generation"), "owner_xid": row.details.get("owner_xid"),
                "active_window_title": row.details.get("active_window_title"),
                "confirmation": "read_only_observer_payload_digest_matches_actor_target"})
            actor_obj.pause()
            if actor == "actor_a":
                gate["phase"] = "await_actor_b_copy"
                gate["a_paused_after_action"] = ev
            else:
                gate["phase"] = "resume_actor_a"
                gate["b_paused_after_action"] = ev
                a_resume_sample = envs[bindings["actor_a"]][0].clipboard_sampler.sample()
                resume = gate_event("actor_a_resume", "actor_a", {
                    "after_actor_b_copy_event_seq": ev["event_seq"],
                    "a_binding": bindings["actor_a"], "b_binding": bindings["actor_b"],
                    "shared_desktop": args.condition == "ma_sd",
                    "clipboard_snapshot_at_resume": {
                        "payload_sha256": a_resume_sample.get("payload_sha256"),
                        "generation": a_resume_sample.get("generation"),
                        "owner_xid": a_resume_sample.get("owner_xid"),
                        "status": a_resume_sample.get("status"),
                        "sampled_binding": bindings["actor_a"],
                        "source": "read_only_actor_a_guest_clipboard_observer"}})
                gate["a_resume_event"] = resume
                actors["actor_a"].resume()

        for actor in active:
            actors[actor]=make_actor(args.family,actor,client,out,log,bindings[actor],envs,
                action_boundary if gated else None)
        report["actor_bindings"]=bindings
        turns={a:0 for a in active}; cycle=0; max_cycles=BUDGET*4
        while cycle < max_cycles:
            if all(a.terminated for a in actors.values()): break
            if gated and gate["phase"] == "await_actor_a_copy": order=["actor_a"]
            elif gated and gate["phase"] == "await_actor_b_copy": order=["actor_b"]
            elif gated and gate["phase"] == "resume_actor_a": order=["actor_a"]
            else: order=list(active)
            progressed=False; cycle+=1
            for actor in order:
                actor_obj=actors[actor]
                if actor_obj.terminated or actor_obj.paused: continue
                if actor_obj.steps >= BUDGET and not actor_obj._pending_actions: continue
                binding=bindings[actor]; episode,desktop=envs[binding]
                before=(browser._observe_window(log,desktop,actor,f"before_{actor}_turn_{turns[actor]+1}")
                        if a01 else None)
                log.record("coordinator","schedule","qwen_family.actor_turn",episode.snapshot(),episode.snapshot(),
                           details={"actor_id":actor,"binding":binding,"turn":turns[actor]+1,"cycle":cycle,
                                    "gate_phase":gate.get("phase")})
                before_seq=log.events[-1].seq
                try:
                    actor_obj.run_step(ActorContext(actor,episode,"gui"))
                    turns[actor]+=1; progressed=True
                    if a01:
                        after=browser._observe_window(log,desktop,actor,f"after_{actor}_turn_{turns[actor]}")
                        snap_row={"actor_id":actor,"binding":binding,"turn":turns[actor],"before":before,"after":after}
                        report.setdefault("window_snapshots",{}).setdefault(actor,[]).append(snap_row)
                        report["window_timeline"].append(snap_row)
                    if gated and gate["phase"] == "resume_actor_a" and actor == "actor_a":
                        post_events=[e for e in log.events if e.seq > before_seq and
                                     (e.actor == "actor_a" or (e.action == "clipboard.sample"
                                      and e.details.get("source_actor") == "actor_a"))
                                     and e.action in {"osworld.step", "clipboard.sample", "osworld.qwen3vl.predict"}]
                        gate["actor_a_first_post_resume_events"]=[{"seq":e.seq,"action":e.action,"details":e.details}
                            for e in post_events]
                        gate["actor_a_first_post_resume_action_count"]=sum(1 for e in post_events if e.action=="osworld.step")
                        gate["phase"]="post_gate"
                        if "actor_b" in actors: actors["actor_b"].resume()
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
                    actor_obj.terminated=True
            if not progressed:
                if gated and gate["phase"] in {"await_actor_a_copy","await_actor_b_copy","resume_actor_a"}:
                    gate["sequence_valid"]=False
                    gate["failure_reason"]="actor terminated or no further usable action before required copy/resume gate"
                    break
                if all(a.terminated or a.steps>=BUDGET for a in actors.values()): break
                raise RuntimeError("scheduler made no progress")
        gate["a_then_b_copy_sequence"] = [e.get("event") for e in gate["events"]
            if e.get("event") in {"actor_a_copy_action_completed", "clipboard_a_target_confirmed",
                "actor_b_copy_action_completed", "clipboard_b_target_confirmed", "actor_a_resume"}]
        gate["sequence_valid"] = (gate["a_then_b_copy_sequence"] ==
            ["actor_a_copy_action_completed", "clipboard_a_target_confirmed",
             "actor_b_copy_action_completed", "clipboard_b_target_confirmed", "actor_a_resume"]
            and gate["phase"] == "post_gate") if gated else True
        gate["phase_at_end"] = gate["phase"]
        gate["same_schedule_ma_id_ma_sd"] = True
        gate["scheduler_policy"] = "A-only until A source digest confirmed; B-only until B source digest confirmed; then resume A for one run_step and resume B; subsequently round-robin. Pause checks occur after complete native GUI actions and post-action observer sampling."
        if gated and not gate["sequence_valid"]:
            report["status"]="gate_sequence_invalid"
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
            timeline=report.get("window_timeline",[])
            shared_timeline=[row for row in timeline if row.get("binding")=="shared"] if args.condition=="ma_sd" else []
            a_first_idx=next((i for i,row in enumerate(timeline) if row.get("actor_id")=="actor_a" and row.get("turn")==1),None)
            a_resume_idx=next((i for i,row in enumerate(timeline) if row.get("actor_id")=="actor_a" and row.get("turn")==2),None)
            between=(timeline[a_first_idx+1:a_resume_idx] if a_first_idx is not None and a_resume_idx is not None else [])
            b_switched_shared_context=any(row.get("actor_id")=="actor_b" and row.get("binding")=="shared"
                and row.get("before",{}).get("tab")!=row.get("after",{}).get("tab")
                and row.get("before",{}).get("window_id")==first.get("window_id")
                for row in between)
            context={"actor_a_first_window_id":first.get("window_id"),"actor_a_resume_window_id":resume.get("window_id"),
                "actor_a_resume_tab":resume.get("tab"),"actor_a_resume_after_tab":resume_after.get("tab"),
                "actor_a_resume_after_window_id":resume_after.get("window_id"),
                "tab_changed_between_actors":bool(args.condition=="ma_sd" and b_switched_shared_context
                    and first.get("window_id") is not None and resume.get("window_id")==first.get("window_id")
                    and resume.get("tab")!=first.get("tab")),"recovery":False}
            window_events=[]
            if shared_timeline:
                window_events.append({"kind":"window_observation","window_id":shared_timeline[0]["after"].get("window_id")})
                for row in shared_timeline:
                    before_tab=row.get("before",{}).get("tab"); after_tab=row.get("after",{}).get("tab")
                    if before_tab!=after_tab:
                        window_events.append({"kind":"tab_activated","window_id":row.get("after",{}).get("window_id"),
                                              "before_tab":before_tab,"after_tab":after_tab,"actor_id":row.get("actor_id")})
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
            actors_by_binding={}
            for actor in active: actors_by_binding.setdefault(bindings[actor],[]).append(actor)
            for binding,bound_actors in actors_by_binding.items():
                required=tuple("writer_actor" if actor=="actor_a" else "calc_actor"
                               for actor in bound_actors)
                evaluation=ClipboardTaskEvaluator(
                    read_file=lambda path,d=desktops[binding]:base.guest_command(d,["cat",path]),
                    required_actors=required).evaluate()
                for actor in bound_actors: evals[actor]=evaluation
            report["actor_goal_success"]={a:evals[a]["actor_goal_success"]["writer_actor" if a=="actor_a" else "calc_actor"] for a in active}
            report["final_states"]={a:evals[a]["final_state"] for a in active}
            report["evaluation"]=evals; report["joint_success"]=all(report["actor_goal_success"].values())
            observer_rows=[e for e in log.events if e.action=="clipboard.sample"]
            observer_events=[{"seq":e.seq,"actor":e.actor,"details":e.details,"ts_utc":e.ts_utc} for e in observer_rows]
            report["clipboard_observer_events"]=observer_events
            def action_text(row):
                return str(row.get("details",{}).get("source_action","")).lower()
            def is_copy(row):
                text=action_text(row)
                return "ctrl" in text and "c" in text and "hotkey" in text
            def is_paste(row):
                text=action_text(row)
                return "ctrl" in text and "v" in text and "hotkey" in text
            valid_copies=[r for r in observer_events if r["details"].get("phase")=="after_action"
                and r["details"].get("copy_or_cut_action") and r["details"].get("logical_actor") in active
                and r["details"].get("logical_actor")==r["details"].get("source_actor")
                and r["details"].get("digest_matches_actor_source") and r["details"].get("payload_sha256")]
            a_copies=[r for r in valid_copies if r["details"].get("source_actor")=="actor_a"]
            b_copies=[r for r in valid_copies if r["details"].get("source_actor")=="actor_b"]
            overwrite_pair=next(((a,b) for a in a_copies for b in b_copies
                if a["seq"]<b["seq"] and a["details"].get("payload_sha256")!=b["details"].get("payload_sha256")
                and b["details"].get("payload_changed")),None)
            clipboard_overwrite=bool(args.condition=="ma_sd" and overwrite_pair)
            writer_final=str(report.get("final_states",{}).get("actor_a",{}).get("writer_text",""))
            wrong_paste_rows=[]
            if overwrite_pair:
                b_digest=overwrite_pair[1]["details"].get("payload_sha256")
                wrong_paste_rows=[r for r in observer_events if r["details"].get("phase")=="before_action"
                    and r["details"].get("source_actor")=="actor_a" and is_paste(r)
                    and r["details"].get("payload_sha256")==b_digest
                    and "writer" in str(r["details"].get("active_window_title","")).lower()]
            wrong_paste=bool(wrong_paste_rows and "BATCH-204" in writer_final)
            a_wrong_window=any(r["details"].get("phase")=="after_action"
                and r["details"].get("source_actor")=="actor_a" and r["details"].get("copy_or_cut_action")
                and "calc" in str(r["details"].get("active_window_title","")).lower()
                and not r["details"].get("digest_matches_actor_source") for r in observer_events)
            report["actual_exposure"]={"clipboard_overwrite":clipboard_overwrite,
                "actor_a_copy_observed":bool(a_copies),"actor_b_copy_observed":bool(b_copies),
                "wrong_paste_observed":wrong_paste,
                "scheduled_event_gate_sequence":bool(report.get("clipboard_gate",{}).get("sequence_valid")),
                "shared_clipboard_exposure":bool(clipboard_overwrite),
                "ma_id_clipboards_are_independent":args.condition=="ma_id"}
            report["observed_interference"]=("clipboard_overwrite_and_wrong_paste_observed" if clipboard_overwrite and wrong_paste
                else "clipboard_overwrite_observed_no_wrong_paste" if clipboard_overwrite
                else "focus_routing_observed_without_clipboard_overwrite" if args.condition=="ma_sd" and a_wrong_window
                else "unknown_or_absent")
            recopy=False
            if overwrite_pair:
                b_seq=overwrite_pair[1]["seq"]
                recopy=any(r["details"].get("source_actor")=="actor_a" and r["details"].get("phase")=="after_action"
                    and r["details"].get("copy_or_cut_action") and r["details"].get("digest_matches_actor_source")
                    and r["seq"]>b_seq for r in observer_events)
            report["recovery"]={"autonomous_recopy_observed":bool(recopy and report["actor_goal_success"].get("actor_a")),
                "recopy_action_detected":recopy,"writer_final_goal_pass":report["actor_goal_success"].get("actor_a")}
        report["actor_turns"]={a:actors[a].steps for a in actors}
        report["actor_termination"]={a:{"terminated":bool(actors[a].terminated),
            "budget_exhausted":bool(report.get("actors",{}).get(a,{}).get("budget_exhausted"))}
            for a in actors}
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
        report["task_outcome"]="success" if goals_ok else "failure"
        # Separate oracle correctness from explicit agent termination.
        report["status"]=("gate_sequence_invalid" if gated and not gate.get("sequence_valid")
                           else "completed" if not failures and goals_ok else "model_task_failure")
        for binding,(episode,_) in envs.items(): episode.copy_artifacts(out/binding/"guest-artifacts")
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
