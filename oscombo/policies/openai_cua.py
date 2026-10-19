"""OpenAI computer-use models (native ``computer`` tool) through the official OSWorld ``GPTResponseAPIAgent``.

Prompt, Responses-API loop (``previous_response_id`` + ``computer_call_output`` screenshots) and the
computer-action -> pyautogui conversion are the official ones. Endpoint and key come from the process
environment (``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``) as in the official agent; an Azure OpenAI
``.../openai/v1`` endpoint works too.

Two transport fixes are applied (prompts, actions and parsing are untouched):

1. After a text-only turn (no ``computer_call``) the official follow-up sends an ``input_image`` together with
   ``previous_response_id``, which the computer tool rejects (HTTP 400 "Computer tool only allows input image
   without previous response"). Only the text part is sent; the model then asks for a screenshot itself.
2. Rate limits (429) and transient upstream errors are retried, since several agents share one deployment.

Extra constructor kwargs: ``options.agent_kwargs``. Known endpoint limit: some deployments reject a chained
request with more than 50 images, so keep ``max_steps`` <= 48 for this policy.
"""
from __future__ import annotations

import os
import random
import sys
import time
from typing import Any

from ..osworld import client_password
from .base import require_model


def harden(agent: Any) -> Any:
    build = agent._build_followup_input

    def followup(screenshot_b64, user_response):
        items = build(screenshot_b64, user_response)
        if agent.previous_response_id:
            for item in items:
                if item.get("role") == "user" and isinstance(item.get("content"), list):
                    item["content"] = [c for c in item["content"] if c.get("type") != "input_image"]
        return items

    create = agent._create_response
    rate_retries = int(os.environ.get("OSCOMBO_RATE_LIMIT_RETRIES", "60"))

    def create_with_backoff(request_input, instructions):
        delay, other, limited = 30.0, 0, 0
        while True:
            try:
                return create(request_input, instructions)
            except RuntimeError as exc:
                msg = str(exc)
                if any(k in msg for k in ("429", "Too Many", "rate_limit", "rate limit")):
                    limited += 1
                    print(f"RATE_LIMIT_RETRY {limited}", file=sys.stderr, flush=True)
                    if limited > rate_retries:
                        raise
                    time.sleep(random.uniform(2.0, 10.0))
                    continue
                if not any(k in msg for k in ("500", "502", "503", "timeout", "Timeout", "Connection")) or other == 5:
                    raise
                other += 1
                time.sleep(delay)
                delay = min(delay * 2, 240.0)

    agent._build_followup_input = followup
    agent._create_response = create_with_backoff
    return agent


def make(env: Any, spec: dict) -> Any:
    from mm_agents.gpt_response_api import GPTResponseAPIAgent
    agent = GPTResponseAPIAgent(env, platform="ubuntu", model=require_model(spec),
                                max_tokens=spec.get("max_tokens"), action_space="pyautogui",
                                observation_type="screenshot", client_password=client_password(),
                                provider_name="docker", reasoning_effort=spec.get("effort") or "medium",
                                **spec.get("options", {}).get("agent_kwargs", {}))
    return harden(agent)
