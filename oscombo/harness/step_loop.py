"""Step-loop harness: screenshot -> policy.predict -> execute pyautogui actions, until DONE / FAIL / max steps.

This is the official OSWorld agent loop, driven directly against the Guest so several agents can share it.
Options (``spec.options``): ``action_pause`` (s after each action, default 0.5), ``step_pause`` (s between
steps, default 1.0), ``wait_seconds`` (for WAIT actions, default 2), ``save_screenshots`` (default true).
With mediation (``ctx.broker`` / ``ctx.guard``, see ``oscombo/mediation.py``) observation and actions go through it.
"""
from __future__ import annotations

import time

from ..mediation import REFUSED_NOTICE
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
        self.notice: str | None = None

    def observe(self, ctx: AgentContext) -> bytes:
        if ctx.broker:
            with ctx.broker.lock:  # observe my own window, not whatever another agent left in front
                ctx.broker.bring_home(ctx.name)
                return ctx.guest.screenshot()
        if ctx.guard:
            ctx.guard.front()
        return ctx.guest.screenshot()

    def predict(self, ctx: AgentContext, obs: dict):
        instruction = ctx.instruction
        if self.notice:  # a mediation notice for the model: policies with a notice channel take it as text
            if hasattr(self.policy, "harness_notice"):
                self.policy.harness_notice = self.notice
            else:
                instruction = f"{self.notice}\n\n{instruction}"
            self.notice = None
        return self.policy.predict(instruction, obs)

    def execute(self, ctx: AgentContext, actions: list, rec: dict) -> None:
        guest, refused_in = ctx.guest, None
        for raw in actions or []:
            action = normalize_action(raw)
            if action in ("DONE", "FAIL"):
                rec["done" if action == "DONE" else "fail"] = True
                break
            if action == "WAIT":
                time.sleep(self.wait_seconds)
                continue
            before = guest.active_window()
            act = {"t": round(time.time() - ctx.t0, 1), "window_before": before, "code": action[-300:]}
            if ctx.broker and ctx.broker.refuses(ctx.name, action):
                act["refused"] = True
                refused_in = before
            elif ctx.guard:
                seen = ctx.guard.w.visible()
                guest.run_pyautogui(ctx.guard.wrap(action))
                ctx.guard.adopt_new(seen)
            else:
                guest.run_pyautogui(action)
            rec["actions"].append(act)
            time.sleep(self.action_pause)
        if refused_in:
            self.notice = REFUSED_NOTICE.format(window=refused_in)

    def run(self, ctx: AgentContext) -> AgentResult:
        res = AgentResult(status="running")
        for step in range(1, ctx.max_steps + 1):
            if ctx.stop.is_set():
                res.status = "timeout"
                return res
            shot = self.observe(ctx)
            if self.save_screenshots:
                (ctx.out / f"{ctx.name}-step{step:02d}.png").write_bytes(shot)
            obs = {"screenshot": shot}
            if getattr(self.policy, "needs_a11y", False):
                obs["accessibility_tree"] = ctx.guest.accessibility_tree()
            started = time.monotonic()
            response, actions = self.predict(ctx, obs)
            rec = {"step": step, "t": round(time.time() - ctx.t0, 1), "infer_s": round(time.monotonic() - started, 1),
                   "response": response_text(response), "actions": [], "done": False, "fail": False}
            if ctx.broker:
                with ctx.broker.lock:  # the whole batch runs on my window without another agent's input in between
                    ctx.broker.bring_home(ctx.name)
                    before_ids = ctx.broker.w.visible()
                    self.execute(ctx, actions, rec)
                    ctx.broker.after_batch(ctx.name, before_ids)
            else:
                self.execute(ctx, actions, rec)
            res.trace.append(rec)
            if rec["done"] or rec["fail"]:
                res.status = "done" if rec["done"] else "fail"
                return res
            time.sleep(self.step_pause)
        res.status = "max_steps"
        return res
