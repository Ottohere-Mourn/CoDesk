"""Step-loop harness: screenshot -> policy.predict -> execute pyautogui actions, until DONE / FAIL / max steps.

This is the official OSWorld agent loop, driven directly against the Guest so several agents can share it.
Options (``spec.options``): ``action_pause`` (s after each action, default 0.5), ``step_pause`` (s between
steps, default 1.0), ``wait_seconds`` (for WAIT actions, default 2), ``save_screenshots`` (default true).
"""
from __future__ import annotations

import time

from ..policies import make_policy
from ..policies.base import normalize_action, response_text
from .base import AgentContext, AgentResult, Harness


class StepLoopHarness(Harness):
    def prepare(self, ctx: AgentContext) -> None:
        self.policy = make_policy(ctx.guest.env, self.spec)
        self.policy.reset()
        opts = self.spec.get("options", {})
        self.action_pause = float(opts.get("action_pause", 0.5))
        self.step_pause = float(opts.get("step_pause", 1.0))
        self.wait_seconds = float(opts.get("wait_seconds", 2.0))
        self.save_screenshots = bool(opts.get("save_screenshots", True))

    def run(self, ctx: AgentContext) -> AgentResult:
        res = AgentResult(status="running")
        guest = ctx.guest
        for step in range(1, ctx.max_steps + 1):
            if ctx.stop.is_set():
                res.status = "timeout"
                return res
            shot = guest.screenshot()
            if self.save_screenshots:
                (ctx.out / f"{ctx.name}-step{step:02d}.png").write_bytes(shot)
            obs = {"screenshot": shot}
            if getattr(self.policy, "needs_a11y", False):
                obs["accessibility_tree"] = guest.accessibility_tree()
            started = time.monotonic()
            response, actions = self.policy.predict(ctx.instruction, obs)
            rec = {"step": step, "t": round(time.time() - ctx.t0, 1), "infer_s": round(time.monotonic() - started, 1),
                   "response": response_text(response), "actions": [], "done": False, "fail": False}
            for raw in actions or []:
                action = normalize_action(raw)
                if action in ("DONE", "FAIL"):
                    rec["done" if action == "DONE" else "fail"] = True
                    break
                if action == "WAIT":
                    time.sleep(self.wait_seconds)
                    continue
                before = guest.active_window()
                guest.run_pyautogui(action)
                rec["actions"].append({"t": round(time.time() - ctx.t0, 1), "window_before": before,
                                       "code": action[-300:]})
                time.sleep(self.action_pause)
            res.trace.append(rec)
            if rec["done"] or rec["fail"]:
                res.status = "done" if rec["done"] else "fail"
                return res
            time.sleep(self.step_pause)
        res.status = "max_steps"
        return res
