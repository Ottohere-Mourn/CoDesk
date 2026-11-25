from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_policy():
    base = types.ModuleType("oscombo.policies.base")
    base.require_model = lambda spec: spec["model"]
    base.response_text = lambda value: ""
    cua = types.ModuleType("oscombo.policies.openai_cua")
    cua.harden = lambda agent: agent
    for name, module in {
        "oscombo": types.ModuleType("oscombo"),
        "oscombo.policies": types.ModuleType("oscombo.policies"),
        "oscombo.policies.base": base,
        "oscombo.policies.openai_cua": cua,
    }.items():
        sys.modules[name] = module
    path = Path(__file__).parents[1] / "common" / "stateless_cua.py"
    spec = importlib.util.spec_from_file_location("batch_stateless_cua", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeAgent:
    def __init__(self):
        self.previous_response_id = None
        self.pending_input_items = []
        self.pending_computer_outputs = []
        self.requests = []

    def reset(self):
        pass

    def _create_response(self, request_input, instructions):
        self.requests.append(request_input)
        return {"ok": True}


def request(frame: str):
    return [{"role": "user", "content": [
        {"type": "input_text", "text": "task"},
        {"type": "input_image", "image_url": f"data:image/png;base64,{frame}", "detail": "original"},
    ]}]


class ImageWindowTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_policy()
        self.agent = FakeAgent()
        self.policy = self.mod.StatelessCUA(self.agent)

    def test_rolling_window_is_current_plus_three_previous(self):
        for frame in ("A", "B", "C", "D", "E"):
            self.agent._create_response(request(frame), "instructions")
        counts = [self.mod._image_count(req) for req in self.agent.requests]
        self.assertEqual(counts, [1, 2, 3, 4, 4])
        urls = [x["image_url"] for x in self.mod.StatelessCUA._get_input_images(self.agent.requests[-1])]
        self.assertEqual(urls, [f"data:image/png;base64,{letter}" for letter in ("B", "C", "D", "E")])

    def test_reset_clears_history(self):
        self.agent._create_response(request("A"), "instructions")
        self.policy.reset()
        self.agent._create_response(request("B"), "instructions")
        self.assertEqual(self.mod._image_count(self.agent.requests[-1]), 1)

    def test_window_clamps_history_to_three_earlier_frames(self):
        self.agent._create_response(request("A"), "instructions")
        self.policy.recent_screenshots = [
            {"type": "input_image", "image_url": f"data:image/png;base64,{x}"}
            for x in ("B", "C", "D", "E")
        ]
        self.agent._create_response(request("F"), "instructions")
        urls = [x["image_url"] for x in self.mod.StatelessCUA._get_input_images(self.agent.requests[-1])]
        self.assertEqual(urls, [f"data:image/png;base64,{letter}" for letter in ("C", "D", "E", "F")])

    def test_strict_route_sends_only_current_frame(self):
        strict_agent = FakeAgent()
        policy = self.mod.StatelessCUA(strict_agent, max_images=1)
        for frame in ("A", "B", "C", "D"):
            strict_agent._create_response(request(frame), "instructions")
        counts = [self.mod._image_count(req) for req in strict_agent.requests]
        self.assertEqual(counts, [1, 1, 1, 1])
        self.assertEqual(len(policy.recent_screenshots), 3)

    def test_route_limit_fails_closed(self):
        strict_agent = FakeAgent()
        self.mod.StatelessCUA(strict_agent, max_images=1)
        # Force an attempted two-image frame to prove the route-specific guard.
        two = request("current")
        two[0]["content"].append({"type": "input_image", "image_url": "data:image/png;base64,extra"})
        with self.assertRaisesRegex(RuntimeError, "exactly one current desktop image"):
            strict_agent._create_response(two, "instructions")

    def test_oversized_tool_result_input_fails_closed_without_pruning(self):
        oversized = request("A")
        oversized[0]["content"].extend(
            {"type": "input_image", "image_url": f"data:image/png;base64,{letter}"}
            for letter in ("B", "C", "D", "E")
        )
        before = len(self.agent.requests)
        with self.assertRaisesRegex(RuntimeError, "exactly one current desktop image"):
            self.agent._create_response(oversized, "instructions")
        self.assertEqual(len(self.agent.requests), before)


if __name__ == "__main__":
    unittest.main()
