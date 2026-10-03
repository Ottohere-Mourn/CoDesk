"""Thin factory for the pinned OSWorld Qwen3VLAgent and remote inference path."""
from __future__ import annotations
import hashlib,os,sys
from pathlib import Path
from typing import Any,Callable

class OSWorldQwenActorFactory:
    def __init__(self,osworld_root:Path,inference_endpoint:str,*,max_steps=20,event_sink=None):
        self.osworld_root=osworld_root.resolve(); self.endpoint=inference_endpoint.rstrip("/")
        self.max_steps=max_steps; self.event_sink=event_sink or (lambda _e:None); self._client=None
    def _load(self):
        if self._client is not None:return
        sys.path.insert(0,str(self.osworld_root))
        from mm_agents.qwen3vl_agent import Qwen3VLAgent
        from scripts.run_writer_calc_v1 import LocalQwenInferenceClient
        import json
        from urllib.request import urlopen
        with urlopen(self.endpoint+"/health",timeout=10) as response: health=json.loads(response.read())
        if not health.get("ready") or health.get("model")!="Qwen3-VL-30B-A3B-Instruct":
            raise RuntimeError("remote endpoint health does not match pinned Qwen3-VL-30B-A3B-Instruct")
        self._client=LocalQwenInferenceClient(endpoint=self.endpoint,event_callback=self.event_sink)
    def __call__(self,spec:Any,artifact_dir:Path,action_boundary:Callable[[str,Any],None]):
        self._load()
        from mm_agents.qwen3vl_agent import Qwen3VLAgent
        from .osworld_agent_actor import OSWorldAgentActor
        agent=Qwen3VLAgent(platform="ubuntu",model="qwen3-vl",max_tokens=512,
          action_space="pyautogui",observation_type="screenshot",coordinate_type="relative")
        agent.call_llm=lambda payload,model,client=self._client,actor_id=spec.actor_id:client.complete(payload,model,actor_id=actor_id)
        goal=str(spec.goal)
        record=lambda row:self.event_sink({"kind":"model_actor_trace","actor_id":spec.actor_id,**row})
        def boundary(_actor,action): action_boundary(action)
        return OSWorldAgentActor(agent,goal,actor_id=spec.actor_id,max_steps=self.max_steps,
          event_callback=record,artifact_directory=artifact_dir,action_boundary_callback=boundary)
