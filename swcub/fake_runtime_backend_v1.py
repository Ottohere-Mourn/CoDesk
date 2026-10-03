"""Offline-only fake backend for runner/orchestration contract tests.

It never launches a process, Guest, model, container, or application and must not
be used as benchmark evidence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
from typing import Any, Sequence

@dataclass
class FakeGuest:
    slot: str
    run_id: str
    ownership: dict[str,Any]
    files: dict[str,bytes]=field(default_factory=dict)
    state: dict[str,Any]=field(default_factory=lambda:{"actors":{"A":{},"B":{},"guards":{"main":"PRESERVE"}}})
    action_count: int=0
    launched: list[dict[str,str]]=field(default_factory=list)
    cleaned: bool=False
    reset_ok: bool=True

@dataclass
class FakeContext:
    actor_id: str
    guest: FakeGuest
    def observe(self): return {"screenshot":b"fake-only", "actor_id":self.actor_id}
    def execute_gui_action(self, action):
        self.guest.action_count+=1
        self.guest.state["actors"][self.actor_id]["value"]=str(action)

class FakeGuestBackend:
    FAKE_BACKEND_ONLY=True
    def __init__(self, *, fail_at: str|None=None, fail_reset=False):
        self.fail_at=fail_at; self.fail_reset=fail_reset; self.events=[]; self.guests=[]; self.last_readiness={}
    def _fail(self, stage):
        if self.fail_at==stage: raise RuntimeError(f"injected fake backend failure at {stage}")
    def create_owned_guest(self,run_id,guest_slot,ownership):
        self._fail("create"); g=FakeGuest(guest_slot,run_id,dict(ownership)); self.guests.append(g)
        self.events.append({"event":"created","slot":guest_slot,"run_id":run_id}); return g
    def clone_workspace(self,plan,guest,workspace_id):
        self._fail("clone"); guest.workspace_id=workspace_id; self.events.append({"event":"workspace_cloned","slot":guest.slot})
    def copy_fixture(self,guest,source,guest_path,sha256_hex):
        self._fail("fixture"); data=Path(source).read_bytes()
        if hashlib.sha256(data).hexdigest()!=sha256_hex: raise ValueError("fixture hash mismatch")
        guest.files[guest_path]=data; self.events.append({"event":"fixture_copied","slot":guest.slot,"path":guest_path})
    def launch_application(self,guest,app,target):
        self._fail("launch"); guest.launched.append({"app":app,"target":target}); self.events.append({"event":"app_launched","app":app})
    def wait_application_ready(self,guest,app,target):
        self._fail("readiness"); self.last_readiness[f"{guest.slot}:{app}"]={"ready":True,"target":target}; return self.last_readiness[f"{guest.slot}:{app}"]
    def observe_initial_state(self,guest,plan): return {"screenshot_available":True,"fixture_count":len(guest.files)}
    def verify_initial_state(self,guest,plan,observed):
        ok=observed.get("screenshot_available") and len(guest.files)==len(plan["fixture_assets"])
        return {"verified":bool(ok),"fake":True}
    def actor_context(self,actor_id,guest): return FakeContext(actor_id,guest)
    def action_count(self,guest): return guest.action_count
    def refresh_after_turn(self,guests):
        self._fail("refresh"); self.events.append({"event":"refreshed","guests":len(guests)})
    def collect_hidden_state(self,guests,plan):
        evaluator=json.loads(Path(plan["evaluator_binding"]["host_path"]).read_text())
        state=json.loads(json.dumps(evaluator["initial_state"]))
        by_slot={g.slot:g for g in guests}
        topology="ma_id" if len(guests)==2 else "ma_sd"
        for i,actor in enumerate(plan["actors"]):
            guest=by_slot.get(f"actor_{actor['actor_id']}") if topology=="ma_id" else guests[0]
            if guest and actor["actor_id"] in guest.state["actors"]:
                value=guest.state["actors"][actor["actor_id"]].get("value")
                if value is not None: state["actors"][actor["actor_id"]]["value"]=value
        return state
    def collect_artifacts(self,guests,plan,output):
        out=Path(output); out.mkdir(parents=True,exist_ok=True)
        p=out/"fake-backend-artifact.json"; p.write_text(json.dumps({"warning":"FAKE_ONLY","slots":[g.slot for g in guests]}))
        self.events.append({"event":"artifacts_collected"}); return {"fake_only":True,"path":str(p)}
    def reset_guest(self,guest,plan):
        if self.fail_reset or self.fail_at=="reset": return {"verified":False,"fake":True}
        guest.state={"actors":{"A":{"value":plan["actors"][0]["initial_value"]},"B":{"value":plan["actors"][1]["initial_value"]},"guards":{"main":"PRESERVE"}}}
        self.events.append({"event":"reset","slot":guest.slot}); return {"verified":guest.reset_ok,"fake":True}
    def cleanup_owned_guest(self,guest,ownership):
        if ownership.get("run_id")!=guest.run_id or ownership!=guest.ownership: raise RuntimeError("fake ownership mismatch")
        guest.cleaned=True; self.events.append({"event":"cleaned","slot":guest.slot}); return {"ownership_verified":True,"fake":True}

class FakeActor:
    def __init__(self,spec,callback):
        self.spec=spec;self.callback=callback;self.terminated=False;self.paused=False;self.done=False;self.phase=0
        self.history_workflow=(spec.actor_id=="A" and "temporary" in spec.operation.lower() and "undo" in spec.operation.lower())
    def reset(self): self.terminated=False;self.paused=False;self.done=False;self.phase=0
    def pause(self): self.paused=True
    def resume(self): self.paused=False
    def run_step(self,context):
        if self.history_workflow and self.phase==0:
            context.execute_gui_action(self.spec.expected_value);self.callback(f"type_text('{self.spec.expected_value}')")
            self.phase=1;return False
        if self.history_workflow and self.phase==1:
            context.execute_gui_action("Undo ctrl+z")
            context.guest.state["actors"][self.spec.actor_id]["value"]=self.spec.initial_value
            self.callback("hotkey('ctrl','z')");self.phase=2;self.done=True;self.terminated=True;return True
        if self.done:self.terminated=True;return True
        context.execute_gui_action(self.spec.expected_value);self.callback(f"type_text('{self.spec.expected_value}')")
        self.done=True;self.terminated=True;return True

def fake_actor_factory(spec,artifact_dir,action_boundary):
    artifact_dir.mkdir(parents=True,exist_ok=True); return FakeActor(spec,action_boundary)
