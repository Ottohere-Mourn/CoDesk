"""Concrete, lazy-loaded OSWorld V2.1 Guest backend for CoDesk V1.

Construction is side-effect free. A Guest is created only when
create_owned_guest() is explicitly invoked by RuntimeExecutor. Cleanup verifies
full ID, project/run/owner labels, and the per-run creation ledger.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, field
import base64, hashlib, json, os, secrets, shlex, subprocess, sys, time
from pathlib import Path
from typing import Any, Callable, Sequence

from .core import EventLog
from .resource_safety import (ResourceIdentity, ResourceLedger, ensure_resource_identity,
                              verify_container_identity, FULL_CONTAINER_ID)
from .runtime_v1 import RuntimeBackendUnavailable
from .osworld_readiness import wait_for_guest_desktop

@dataclass
class OSWorldGuest:
    slot: str
    desktop: Any
    episode: Any
    run_id: str
    ledger: ResourceLedger
    identity: ResourceIdentity
    fixtures: dict[str, bytes] = field(default_factory=dict)
    launched: list[dict[str, Any]] = field(default_factory=list)

class A6000OSWorldBackend:
    """Pinned OSWorld V2.1 Docker/QEMU adapter; no import or Guest on init."""
    def __init__(self, *, repo_root: Path, guest_image: Path, osworld_root: Path,
                 cache_dir: Path, runtime_image: str, artifact_root: Path,
                 evaluator_observers: dict[str, Callable] | None = None,
                 guest_timeout: float = 300):
        self.repo_root=repo_root.resolve(); self.guest_image=guest_image.resolve()
        self.osworld_root=osworld_root.resolve(); self.cache_dir=cache_dir.resolve()
        self.runtime_image=runtime_image; self.artifact_root=artifact_root.resolve()
        self.evaluator_observers=evaluator_observers or {}; self.guest_timeout=guest_timeout
        self.last_readiness: dict[str, Any]={}; self._guests: dict[int,OSWorldGuest]={}
        self._identities: dict[str,tuple[ResourceIdentity,ResourceLedger]]={}; self._scheduler_event_callback=None
    def set_scheduler_event_callback(self,callback): self._scheduler_event_callback=callback
    def notify_observer_event(self,event):
        if self._scheduler_event_callback is not None: self._scheduler_event_callback(event)

    @classmethod
    def from_environment(cls, repo_root: Path):
        root=Path(os.environ.get("CODESK_A6000_ROOT",str(repo_root.parent))).expanduser()
        return cls(repo_root=repo_root,
          guest_image=Path(os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE",root/"assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2")),
          osworld_root=Path(os.environ.get("OSWORLD_V2_DIR",root/"external/OSWorld-V2-osworld-v2.1")),
          cache_dir=Path(os.environ.get("SWCUB_OSWORLD_CACHE_DIR",root/"assets/osworld-v2.1/task-cache")),
          runtime_image=os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE","swcub/osworld-v2.1-qemu-runtime:a6000"),
          artifact_root=Path(os.environ.get("CODESK_ARTIFACT_ROOT",root/"artifacts")))

    def static_preflight(self) -> dict[str,Any]:
        provider=self.osworld_root/"desktop_env/providers/docker/provider.py"
        checks={"repo":self.repo_root.is_dir(),"osworld_source":(self.osworld_root/"desktop_env/desktop_env.py").is_file(),
          "guest_image":self.guest_image.is_file(),"cache_dir_parent":self.cache_dir.parent.is_dir(),
          "docker_provider_patch":provider.is_file() and "SWCUB_OWNED_RESOURCE_SAFETY" in provider.read_text(errors="ignore"),
          "runtime_image_configured":bool(self.runtime_image),"artifacts_parent_exists":self.artifact_root.parent.exists()}
        missing=[k for k,v in checks.items() if not v]
        return {"status":"CODE_READY" if not missing else "MISSING_IMPLEMENTATION",
                "checks":checks,"missing":missing,"guest_started":False,
                "docker_daemon_checked":False,"model_endpoint_checked":False}

    @contextmanager
    def _resource_env(self, identity: ResourceIdentity):
        values={"SWCUB_RUN_ID":identity.run_id,"SWCUB_OWNER_TOKEN":identity.owner_token,
                "SWCUB_RESOURCE_LEDGER":str(identity.ledger_path),
                "SWCUB_RESOURCE_IDENTITY_INITIALIZED":""}
        previous={k:os.environ.get(k) for k in values}
        os.environ.update(values)
        try: yield
        finally:
            for key,value in previous.items():
                if value is None: os.environ.pop(key,None)
                else: os.environ[key]=value

    def _new_identity(self, plan: dict[str,Any]):
        run_id=str(plan["ownership"]["run_id"])
        if run_id in self._identities: return self._identities[run_id]
        output=(self.repo_root/plan["artifact_contract"]["root_template"]).resolve()
        if self.repo_root not in output.parents: raise RuntimeBackendUnavailable("artifact path escapes project root")
        output.mkdir(parents=True,exist_ok=True)
        ledger_path=output/"resource-events.jsonl"
        identity=ResourceIdentity(run_id,secrets.token_hex(32),ledger_path)
        ledger=ResourceLedger(ledger_path)
        with self._resource_env(identity): ensure_resource_identity(ledger_path)
        self._identities[run_id]=(identity,ledger)
        return identity,ledger

    def create_owned_guest(self, run_id: str, guest_slot: str, ownership: dict[str,Any]):
        if run_id!=ownership.get("run_id"): raise RuntimeBackendUnavailable("run ownership mismatch")
        # Do not bypass the pinned provider's project labels and append-only ledger.
        preflight=self.static_preflight()
        if preflight["status"]!="CODE_READY": raise RuntimeBackendUnavailable(f"A6000 Guest preflight failed: {preflight['missing']}")
        plan={"ownership":ownership,"artifact_contract":{"root_template":f"runs/{run_id}"}}
        identity,ledger=self._new_identity(plan)
        sys.path.insert(0,str(self.osworld_root))
        desktop=None
        try:
            from desktop_env.desktop_env import DesktopEnv
            from .osworld_adapter import OSWorldSharedEpisode
            from .osworld_readiness import wait_for_guest_desktop
            with self._resource_env(identity):
                desktop=DesktopEnv(provider_name="docker",path_to_vm=str(self.guest_image),
                    cache_dir=str(self.cache_dir),os_type="Ubuntu",action_space="pyautogui")
                episode=OSWorldSharedEpisode(desktop)
                episode.log=EventLog()
                original_record=episode.log.record
                def record_and_forward(*args,**kwargs):
                    original_record(*args,**kwargs)
                    event=episode.log.events[-1]
                    self.notify_observer_event({"kind":event.kind,"actor":event.actor,
                      "action":event.action,"outcome":event.outcome,"seq":event.seq,
                      "details":event.details,"observed_revision":event.observed_revision})
                episode.log.record=record_and_forward
                episode.reset(task_config=None)
                wait_for_guest_desktop(episode,desktop,timeout=self.guest_timeout,retry_interval=5)
        except Exception as exc:
            # Close only when provider creation is present in this exact run ledger.
            try:
                provider=getattr(desktop,"provider",None); container=getattr(provider,"container",None)
                full_id=str(getattr(container,"id",""))
                if FULL_CONTAINER_ID.fullmatch(full_id) and ledger.has_created_container(full_id,identity):
                    container.reload(); verify_container_identity(full_id,container.attrs,identity)
                    desktop.close()
            except Exception as cleanup_exc:
                raise RuntimeBackendUnavailable(f"OSWorld Guest startup failed ({type(exc).__name__}: {exc}); owned cleanup failed ({type(cleanup_exc).__name__}: {cleanup_exc}); preserve and inspect ledger {ledger.path}") from exc
            raise RuntimeBackendUnavailable(f"OSWorld Guest startup/readiness failed: {type(exc).__name__}: {exc}") from exc
        handle=OSWorldGuest(guest_slot,desktop,episode,run_id,ledger,identity)
        self._verify_created_guest(handle)
        self._guests[id(handle)]=handle
        return handle

    def _verify_created_guest(self, guest: OSWorldGuest):
        provider=getattr(guest.desktop,"provider",None); container=getattr(provider,"container",None)
        full_id=str(getattr(container,"id",""))
        if not FULL_CONTAINER_ID.fullmatch(full_id): raise RuntimeBackendUnavailable("Guest provider has no full container ID")
        if not guest.ledger.has_created_container(full_id,guest.identity):
            raise RuntimeBackendUnavailable("Guest container is not recorded as created by this run")
        container.reload(); verify_container_identity(full_id,container.attrs,guest.identity)
        guest.episode.log.record("environment","ownership","guest.owned_created",{},
            {"container_id":full_id,"run_id":guest.run_id},details={"guest_slot":guest.slot})

    def _command(self, guest: OSWorldGuest, argv: Sequence[str], timeout=60):
        import requests
        response=requests.post(f"http://{guest.desktop.vm_ip}:{guest.desktop.server_port}/execute",
          json={"command":list(map(str,argv)),"shell":False,"timeout":timeout},timeout=(5,timeout+10))
        response.raise_for_status(); payload=response.json()
        if payload.get("returncode",0) not in (0,None): raise RuntimeBackendUnavailable(f"Guest command failed: {payload!r}")
        return str(payload.get("output",""))

    def clone_workspace(self, plan, guest, workspace_id):
        root=f"/home/oem/codesk/{workspace_id}"
        self._command(guest,["python3","-c",f"from pathlib import Path; Path({root!r}).mkdir(parents=True,exist_ok=True)"])
        guest.workspace_root=root

    def copy_fixture(self, guest, source: Path, guest_path: str, sha256_hex: str):
        data=source.read_bytes()
        if hashlib.sha256(data).hexdigest()!=sha256_hex: raise RuntimeBackendUnavailable(f"host fixture hash mismatch: {source}")
        encoded=base64.b64encode(data).decode("ascii")
        code=("import base64,hashlib; from pathlib import Path; p=Path("+repr(guest_path)+"); p.parent.mkdir(parents=True,exist_ok=True); "
              "d=base64.b64decode("+repr(encoded)+"); p.write_bytes(d); print(hashlib.sha256(p.read_bytes()).hexdigest())")
        observed=self._command(guest,["python3","-c",code],timeout=90).strip().splitlines()[-1]
        if observed!=sha256_hex: raise RuntimeBackendUnavailable(f"Guest fixture hash mismatch: {guest_path}")
        guest.fixtures[guest_path]=data

    def launch_application(self, guest, app: str, target: str):
        target_q=shlex.quote(target)
        if app=="Writer": command=f"nohup soffice --writer --nologo --norestore {target_q} >/tmp/codesk-writer.log 2>&1 </dev/null &"
        elif app=="Calc": command=f"nohup soffice --calc --nologo --norestore {target_q} >/tmp/codesk-calc.log 2>&1 </dev/null &"
        elif app in {"Browser","Chromium"}:
            command=f"nohup chromium --no-sandbox --user-data-dir=/tmp/codesk-chrome-{guest.slot} file://{target_q} >/tmp/codesk-browser.log 2>&1 </dev/null &"
        elif app=="Terminal": command="nohup xterm >/tmp/codesk-terminal.log 2>&1 </dev/null &"
        else: raise RuntimeBackendUnavailable(f"unsupported application launch binding: {app}")
        self._command(guest,["bash","-lc",command])
        guest.launched.append({"app":app,"target":target})

    def wait_application_ready(self, guest, app: str, target: str):
        processes={"Writer":"soffice","Calc":"soffice","Browser":"chromium","Chromium":"chromium","Terminal":"xterm"}
        proc=processes.get(app)
        if not proc: return {"ready":False,"reason":"unsupported_app"}
        process_probe={"Writer":"pgrep -x soffice.bin || pgrep -x soffice",
          "Calc":"pgrep -x soffice.bin || pgrep -x soffice","Browser":"pgrep -x chromium",
          "Chromium":"pgrep -x chromium","Terminal":"pgrep -x xterm"}[app]
        deadline=time.monotonic()+90; last=""
        while time.monotonic()<deadline:
            last=self._command(guest,["bash","-lc",f"({process_probe}) >/tmp/codesk-proc-check 2>&1 && echo APP_RUNNING || true; xdotool getactivewindow getwindowname 2>/dev/null || true; test -r {shlex.quote(target)} && echo TARGET_READABLE"])
            if "TARGET_READABLE" in last and "APP_RUNNING" in last:
                lines=[x for x in last.splitlines() if x and x not in {"TARGET_READABLE","APP_RUNNING"}]
                return {"ready":True,"process_match":True,"target_readable":True,"active_window":lines[-1] if lines else None}
            time.sleep(1)
        raise RuntimeBackendUnavailable(f"{app} readiness timeout for {target}: {last[-1000:]}")

    def prepare_workflow(self,plan,guest):
        handler=self.workflow_setup_handlers.get(plan["workflow_id"])
        if handler is None: return
        handler(plan,guest,self)

    def observe_initial_state(self, guest, plan):
        shot=guest.episode.refresh_observation("runtime_initial_state")
        return {"screenshot_available":bool(shot.get("screenshot")),"guest_slot":guest.slot,
                "fixture_paths":sorted(guest.fixtures),"active_window":guest.episode._active_window_title()}

    def verify_initial_state(self, guest, plan, observed):
        expected={x["guest_path"]:x["sha256"] for x in plan["fixture_assets"]}
        files_ok=(observed.get("screenshot_available",False) and set(guest.fixtures)==set(expected))
        # A screenshot and byte-identical fixtures do not prove app-level initial
        # values/selection/context. Fail closed until that workflow observer exists.
        semantic_observer=self.evaluator_observers.get(plan["workflow_id"])
        return {"verified":bool(files_ok and semantic_observer and getattr(semantic_observer,"verify_initial",None)),
                "fixture_count":len(guest.fixtures),"expected_fixture_count":len(expected),
                "initial_state_semantic_check":"REGISTERED" if semantic_observer else "MISSING"}

    def actor_context(self, actor_id, guest):
        from .environment import ActorContext
        return ActorContext(actor_id,guest.episode,"gui")

    def action_count(self, guest): return sum(guest.episode.actor_steps.values())
    def refresh_after_turn(self, guests):
        for guest in guests: guest.episode.refresh_observation("runtime_turn_boundary")

    def collect_hidden_state(self, guests: Sequence[OSWorldGuest], plan: dict[str,Any]):
        observer=self.evaluator_observers.get(plan["workflow_id"])
        if observer is None:
            raise RuntimeBackendUnavailable(f"no exact hidden-state observer registered for {plan['workflow_id']}")
        return observer(guests,plan,self)

    def collect_artifacts(self, guests, plan, output):
        output=Path(output); output.mkdir(parents=True,exist_ok=True); rows=[]
        for guest in guests:
            dest=output/"guest-artifacts"/guest.slot; dest.mkdir(parents=True,exist_ok=True)
            guest.episode.copy_artifacts(dest)
            guest.episode.log.write(dest/"events.jsonl")
            rows.append({"slot":guest.slot,"guest_container_id":guest.desktop.provider.container.id,
                         "screenshots":sorted(p.name for p in dest.glob("*.png")),"fixture_paths":sorted(guest.fixtures)})
        return {"guests":rows,"ownership_ledger":str(guests[0].ledger.path) if guests else None}

    def reset_guest(self, guest, plan):
        guest.episode.reset(task_config=None)
        wait_for_guest_desktop(guest.episode,guest.desktop,timeout=self.guest_timeout,retry_interval=5)
        for asset in plan["fixture_assets"]: self.copy_fixture(guest,Path(asset["host_path"]),asset["guest_path"],asset["sha256"])
        for app in plan["required_apps"]:
            for asset in plan["fixture_assets"]:
                if asset["app"]==app:
                    self.launch_application(guest,app,asset["guest_path"])
                    self.wait_application_ready(guest,app,asset["guest_path"])
        self.prepare_workflow(plan,guest)
        observer=self.evaluator_observers.get(plan["workflow_id"])
        verify=getattr(observer,"verify_initial",None) if observer else None
        if not callable(verify): return {"verified":False,"guest_slot":guest.slot,"reason":"exact workflow initial-state verifier missing"}
        verified=bool(verify([guest],plan,self))
        return {"verified":verified,"guest_slot":guest.slot,"reset_kind":"OSWorld_snapshot_plus_fixture_rematerialization"}

    def cleanup_owned_guest(self, guest, ownership):
        if ownership.get("run_id")!=guest.run_id: raise RuntimeBackendUnavailable("cleanup run_id mismatch")
        self._verify_created_guest(guest)
        container=guest.desktop.provider.container; full_id=container.id
        guest.desktop.close()
        if guest.ledger.has_created_container(full_id,guest.identity):
            # Provider's patched stop_emulator records destroy only after exact ID/labels verification.
            rows=[json.loads(line) for line in guest.ledger.path.read_text().splitlines() if line.strip()]
            destroyed=any(r.get("resource_id")==full_id and r.get("event")=="destroyed" for r in rows)
            if not destroyed: raise RuntimeBackendUnavailable("provider closed Guest without destruction ledger entry")
        self._guests.pop(id(guest),None)
        return {"ownership_verified":True,"container_id":full_id,"cleanup":"provider-owned exact-ID cleanup"}
