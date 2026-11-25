"""Stateless native Responses CUA policy for the CONC batch.

Each model request starts with the current desktop frame only.  Prior model
response IDs and screenshot/tool-output history are deliberately not carried
forward, so request image count is bounded at one (hard fail above four).  The
runner still archives every step screenshot to disk.  This avoids accumulated
image contexts and preserves exact request/response tool-call pairing.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from oscombo.policies.base import require_model, response_text
from oscombo.policies.openai_cua import harden

MAX_IMAGES_PER_REQUEST = 4
APPROVED_API_HOSTS = {"api.haogpt.net", "sub2api-hk.ziplab.co"}


def _image_count(value: Any) -> int:
    if isinstance(value, dict):
        here = int(value.get("type") in {"input_image", "computer_screenshot"})
        return here + sum(_image_count(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_image_count(v) for v in value)
    return 0


class StatelessCUA:
    def __init__(self, agent: Any, max_images: int = MAX_IMAGES_PER_REQUEST):
        if not 1 <= int(max_images) <= MAX_IMAGES_PER_REQUEST:
            raise ValueError(f"max_images must be between 1 and {MAX_IMAGES_PER_REQUEST}")
        self.agent = harden(agent)
        self.max_images = int(max_images)
        self.recent_actions: list[str] = []
        self.recent_notes: list[str] = []
        self.recent_screenshots: list[dict[str, Any]] = []
        create = self.agent._create_response

        def capped_create(request_input, instructions):
            current_images = self._get_input_images(request_input)
            if len(current_images) > 1:
                raise RuntimeError("stateless frame guard expected exactly one current desktop image")
            augmented = deepcopy(request_input)
            # Some native-computer Responses gateways accept only one image
            # input per request. Keep the stricter route's current frame only;
            # the archived screenshots and textual action memory remain intact.
            history_limit = self.max_images - 1
            if current_images and history_limit and self.recent_screenshots:
                user_message = next(
                    (item for item in augmented if isinstance(item, dict) and item.get("role") == "user"),
                    None,
                )
                content = user_message.get("content") if user_message else None
                if isinstance(content, list):
                    current_uri = current_images[0].get("image_url")
                    current_pos = next(
                        (i for i, item in enumerate(content)
                         if isinstance(item, dict) and item.get("type") == "input_image"
                         and item.get("image_url") == current_uri),
                        None,
                    )
                    if current_pos is not None:
                        frame_items: list[dict[str, Any]] = []
                        history = self.recent_screenshots[-history_limit:]
                        for offset, frame in enumerate(history, start=1):
                            frame_items.extend([
                                {"type": "input_text", "text": f"Earlier desktop frame {offset} of {len(history)}; use only as recent visual context."},
                                deepcopy(frame),
                            ])
                        content[current_pos:current_pos] = frame_items
            count = _image_count(augmented)
            if count > self.max_images:
                # Refuse before sending. We add only standalone historical user
                # screenshots; no computer_call or computer_call_output item is
                # ever trimmed, so tool-call pairing stays intact.
                raise RuntimeError(
                    f"image-window guard refused request with {count} images; "
                    f"route limit is {self.max_images} (global maximum {MAX_IMAGES_PER_REQUEST})"
                )
            response = create(augmented, instructions)
            if current_images:
                self.recent_screenshots.append(deepcopy(current_images[0]))
                self.recent_screenshots = self.recent_screenshots[-3:]
            return response

        self.agent._create_response = capped_create

    def reset(self) -> None:
        self.agent.reset()
        self.agent.previous_response_id = None
        self.agent.pending_input_items = []
        self.agent.pending_computer_outputs = []
        self.recent_actions.clear()
        self.recent_notes.clear()
        self.recent_screenshots.clear()

    @staticmethod
    def _get_input_images(value: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(value, dict):
            if value.get("type") in {"input_image", "computer_screenshot"}:
                found.append(value)
            for child in value.values():
                found.extend(StatelessCUA._get_input_images(child))
        elif isinstance(value, (list, tuple)):
            for child in value:
                found.extend(StatelessCUA._get_input_images(child))
        return found

    @staticmethod
    def _is_screenshot_noop(action: Any) -> bool:
        if isinstance(action, dict) and str(action.get("type", "")).lower() in {"screenshot", "observe"}:
            return True
        code = action.get("action") or action.get("command") or "" if isinstance(action, dict) else str(action)
        return "".join(str(code).split()).lower() == "importtime;time.sleep(0.1)"

    @staticmethod
    def _brief_action(action: Any) -> str:
        if isinstance(action, dict):
            kind = str(action.get("type", "action"))
            args = action.get("args", action)
            if kind in {"click", "double_click", "right_click"}:
                return f"{kind} at ({args.get('x')},{args.get('y')})"
            if kind in {"type", "text", "write"}:
                value = args.get("text", args.get("value", ""))
                return f"typed text ({len(str(value))} characters; content withheld)"
            if kind == "keypress":
                return "keypress " + "+".join(args.get("keys", []))
            if kind == "scroll":
                dy = args.get("scroll_y", 0)
                return f"scroll {'down' if dy > 0 else 'up'} by {abs(dy)}"
            return repr(action)[:120]
        return str(action).replace("\n", " ")[:120]

    def predict(self, instruction: str, obs: dict[str, Any]):
        # Stateless requests contain no prior computer_call_output images.  All
        # call/output pairs within a single agent response remain handled by the
        # underlying Responses agent without pruning.
        self.agent.previous_response_id = None
        self.agent.pending_input_items = []
        self.agent.pending_computer_outputs = []
        prompt = instruction
        if self.recent_actions:
            prompt += "\n\nYour recent own desktop actions (latest last):\n" + "\n".join(
                f"- {item}" for item in self.recent_actions[-6:]
            )
        if self.recent_notes:
            prompt += "\n\nYour short carry-over notes (verify against the current screen):\n" + "\n".join(
                f"- {item}" for item in self.recent_notes[-3:]
            )
        response, actions = self.agent.predict(prompt, obs)
        note = " ".join(response_text(response).split())
        if note:
            self.recent_notes.append(note[:220])
            self.recent_notes = self.recent_notes[-3:]
        concrete = []
        for action in actions or []:
            if self._is_screenshot_noop(action):
                continue
            concrete.append(action)
            self.recent_actions.append(self._brief_action(action))
        self.recent_actions = self.recent_actions[-6:]
        return response, concrete


def make(env: Any, spec: dict) -> StatelessCUA:
    import os
    from mm_agents.gpt_response_api import GPTResponseAPIAgent
    base_url = (spec.get("base_url") or os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    if not base_url or urlparse(base_url).hostname not in APPROVED_API_HOSTS:
        raise RuntimeError("refusing agent startup: API endpoint host is not on the approved allowlist")
    if os.environ.get("OPENAI_BASE_URL", "").rstrip("/") != base_url:
        raise RuntimeError("refusing agent startup: explicit per-agent endpoint does not match runtime endpoint")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("refusing agent startup: OPENAI_API_KEY is unavailable (value suppressed)")
    model = require_model(spec)
    options = spec.get("options", {})
    agent = GPTResponseAPIAgent(
        env,
        platform="ubuntu",
        model=model,
        max_tokens=spec.get("max_tokens"),
        action_space="pyautogui",
        observation_type="screenshot",
        client_password="osworld-public-evaluation",
        provider_name="docker",
        reasoning_effort=spec.get("effort") or "medium",
        **options.get("agent_kwargs", {}),
    )
    # Verified sub2api native computer calls reject multiple image inputs,
    # whereas the general batch hard ceiling remains four. Select the route-
    # compatible limit before any Guest starts instead of learning by retry.
    image_limit = 1 if urlparse(base_url).hostname == "sub2api-hk.ziplab.co" else MAX_IMAGES_PER_REQUEST
    return StatelessCUA(agent, max_images=image_limit)
