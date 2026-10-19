"""Official OSWorld ``mm_agents`` agents as policies, with a swappable model transport.

``chat-pyautogui``       ``PromptAgent`` (screenshot in, pyautogui code out) over any OpenAI-compatible
                         ``/chat/completions`` endpoint, e.g. a local vLLM server with Qwen-VL.
``responses-pyautogui``  ``O3Agent`` (planner, pyautogui code out) over a ``/responses``-only endpoint, for
                         models without the native computer tool.
``osworld-agent``        any agent class: ``options.agent_class = "mm_agents.uitars_agent:UITARSAgent"`` plus its
                         constructor kwargs in ``options.agent_kwargs``. ``options.transport = "chat" | "responses"``
                         replaces its ``call_llm`` with our transport; omit it to keep the agent's own client.

Spec fields used: ``model``, ``max_tokens``, ``effort``, ``base_url``, ``api_key_env`` (name of the env var
holding the key; default ``OPENAI_API_KEY``), ``options``.
"""
from __future__ import annotations

import importlib
import inspect
import os
from typing import Any

from ..osworld import client_password
from .base import require_model
from .transports import ChatCompletionsTransport, ResponsesTransport


def _transport(kind: str, spec: dict) -> Any:
    key = os.environ.get(spec.get("api_key_env") or "OPENAI_API_KEY")
    if kind == "chat":
        return ChatCompletionsTransport(require_model(spec), spec.get("base_url"), key)
    if kind == "responses":
        return ResponsesTransport(require_model(spec), spec.get("base_url"), key,
                                  reasoning_effort=spec.get("effort"))
    raise ValueError(f"unknown transport {kind!r} (chat | responses)")


def make_chat_pyautogui(env: Any, spec: dict) -> Any:
    from mm_agents.agent import PromptAgent
    opts = spec.get("options", {})
    agent = PromptAgent(platform="ubuntu", model=require_model(spec), max_tokens=spec.get("max_tokens") or 1500,
                        action_space="pyautogui", observation_type="screenshot",
                        max_trajectory_length=opts.get("max_trajectory_length", 3),
                        client_password=client_password())
    agent.call_llm = _transport("chat", spec)
    return agent


def make_responses_pyautogui(env: Any, spec: dict) -> Any:
    from mm_agents.o3_agent import O3Agent
    agent = O3Agent(platform="ubuntu", model=require_model(spec), max_tokens=spec.get("max_tokens") or 4096,
                    client_password=client_password(), action_space="pyautogui", observation_type="screenshot",
                    max_steps=spec.get("max_steps", 50))
    agent.call_llm = _transport("responses", spec)
    return agent


def make_osworld_agent(env: Any, spec: dict) -> Any:
    opts = spec.get("options", {})
    if "agent_class" not in opts:
        raise ValueError("osworld-agent needs options.agent_class, e.g. mm_agents.uitars_agent:UITARSAgent")
    module, _, name = opts["agent_class"].partition(":")
    cls = getattr(importlib.import_module(module), name)
    kwargs = dict(opts.get("agent_kwargs", {}))
    params = inspect.signature(cls.__init__).parameters
    defaults = {"model": spec.get("model"), "platform": "ubuntu", "action_space": "pyautogui",
                "observation_type": "screenshot", "client_password": client_password(), "env": env}
    for key, value in defaults.items():
        if key in params and key not in kwargs and value is not None:
            kwargs[key] = value
    agent = cls(**kwargs)
    if opts.get("transport"):
        agent.call_llm = _transport(opts["transport"], spec)
    if opts.get("needs_a11y"):
        agent.needs_a11y = True
    return agent
