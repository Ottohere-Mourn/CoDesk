"""Step-loop harness: screenshot -> policy.predict -> execute pyautogui actions, until DONE / FAIL / max steps.

This is the official OSWorld agent loop, driven directly against the Guest so several agents can share it.
Options (``spec.options``): ``action_pause`` (s after each action, default 0.5), ``step_pause`` (s between
steps, default 1.0), ``wait_seconds`` (for WAIT actions, default 2), ``save_screenshots`` (default true),
``chain_steps`` (long-horizon runs: start a fresh model conversation every N predictions with a carry-over note of
the agent's recent steps, default 40; some computer-use endpoints reject chains with more than 50 images; 0 = never),
``wall_s`` (per-agent wall clock, default 7200 s -> status ``timeout``).
With mediation (``ctx.broker`` / ``ctx.guard``, see ``oscombo/mediation.py``) or a per-harness defense
(``ctx.defense``, see ``oscombo/defense``) observation and actions go through it.
"""
from __future__ import annotations

import time

from ..defense import clean_text
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
        self.chain_steps = int(opts.get("chain_steps", 40))
        self.wall_s = float(opts.get("wall_s", 7200))
        self.notice: str | None = None
        self.chain_len = 0
        self.chain_resets = 0
        self.carry_over = ""
        self.instruction = ctx.instruction
        if ctx.defense:  # generic, task-independent guidance only; texts revealing other actors are dropped
            text = ctx.defense.instruction(ctx.instruction)
            if text != ctx.instruction:
                extra = text[len(ctx.instruction):] if text.startswith(ctx.instruction) else text
                extra = clean_text(extra, ctx.defense.stats)
                if extra:
                    self.instruction = ctx.instruction + extra if text.startswith(ctx.instruction) else text

    def observe(self, ctx: AgentContext) -> bytes:
        if ctx.broker:
            with ctx.broker.lock:  # observe my own window, not whatever another agent left in front
                ctx.broker.bring_home(ctx.name)
                return ctx.guest.screenshot()
        if ctx.guard:
            ctx.guard.front()
        if ctx.defense:
            ctx.defense.before_observe()
            return ctx.defense.observe(ctx.guest.screenshot())
        return ctx.guest.screenshot()

    def maybe_reset_chain(self, step: int, trace: list[dict]) -> None:
        """Fresh conversation every ``chain_steps`` predictions; it gets the task again plus the agent's own recent
        notes and actions (the screen itself shows the current state)."""
        if not self.chain_steps or self.chain_len < self.chain_steps:
            return
        lines = []
        for r in [r for r in trace if "step" in r][-12:]:
            note = " ".join(str(r.get("response") or "").split())[:240]
            acts = " | ".join(" ".join(a["code"].split())[-140:] for a in r["actions"])[:420]
            lines.append(f"- step {r['step']}: {note or '(no notes)'} -> actions: {acts or '(none)'}")
        self.carry_over = (
            f"\n\n[Progress note from your earlier work on this same task: you have already taken {step - 1} steps; "
            "the conversation was restarted to save context, nothing on the computer was reset. Continue from the "
            "current state of the screen; do not redo finished work. Your most recent steps, oldest first:\n"
            + "\n".join(lines) + "]")
        self.policy.reset()
        self.chain_len = 0
        self.chain_resets += 1

    def predict(self, ctx: AgentContext, obs: dict):
        instruction = self.instruction + self.carry_over
        if self.notice:  # a mediation notice for the model: policies with a notice channel take it as text
            if hasattr(self.policy, "harness_notice"):
                self.policy.harness_notice = self.notice
            else:
                instruction = f"{self.notice}\n\n{instruction}"
            self.notice = None
        self.chain_len += 1
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
            elif ctx.defense:
                new = ctx.defense.transform_action(action)
                if new is None:
                    act["skipped_by_defense"] = True
                else:
                    if new != action:
                        act["rewritten"] = new[-300:]
                    guest.run_pyautogui(new)
                ctx.defense.after_action(action, act)
            else:
                guest.run_pyautogui(action)
            rec["actions"].append(act)
            time.sleep(self.action_pause)
        if refused_in:
            self.notice = REFUSED_NOTICE.format(window=refused_in)
        if ctx.defense:
            note = clean_text(ctx.defense.notice(), ctx.defense.stats)
            if note:
                self.notice = note
                rec["defense_notice"] = note

    def run(self, ctx: AgentContext) -> AgentResult:
        res = AgentResult(status="running")
        res.extra["chain_resets"] = 0
        if ctx.defense:
            ctx.defense.start(set(ctx.setup_windows))
        started_at = time.time()
        for step in range(1, ctx.max_steps + 1):
            if ctx.stop.is_set() or time.time() - started_at > self.wall_s:
                res.status = "timeout"
                return res
            shot = self.observe(ctx)
            if self.save_screenshots:
                (ctx.out / f"{ctx.name}-step{step:02d}.png").write_bytes(shot)
            obs = {"screenshot": shot}
            if getattr(self.policy, "needs_a11y", False):
                obs["accessibility_tree"] = ctx.guest.accessibility_tree()
            self.maybe_reset_chain(step, res.trace)
            res.extra["chain_resets"] = self.chain_resets
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
