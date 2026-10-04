# Agent Adapter Interface

This document describes the current adapter seam. It does not add another model adapter. Scripted actors remain useful for task and scheduler validation, but do not count as model-agent results.

## Minimal actor contract

The general actor protocol is in `swcub/actors.py`: an actor has `actor_id`, `role`, and `run(context)`. Step-capable actors expose `run_step(context) -> bool`. `ActorContext` is role-scoped and provides the observations/actions allowed for that actor. The coordinator owns scheduling, environment reset, event logging, resource lifecycle, and final evaluation.

For an OSWorld GUI model actor, the concrete bridge is `swcub/osworld_agent_actor.py`:

- The supplied OSWorld agent implements `predict(instruction, observation)` and `reset()`.
- The adapter calls `context.observe()` and requires screenshot bytes; observation/history and visual grounding remain inside the supplied OSWorld agent.
- It forwards the agent's native action sequence to `context.execute_gui_action()` without replacing the planner, parser, or action format.
- It records actor ID, screenshot hash and resolution, raw response, native actions, observed revision, inference latency, and step budget.
- It supports actor-local step budget, `pause()`, `resume()`, and `yield_turn()`. The scheduler must pause only at action boundaries; environment reset is not actor reset.

## Current Qwen reference

`swcub/osworld_qwen_actor_factory.py` loads the pinned OSWorld `mm_agents.qwen3vl_agent.Qwen3VLAgent`. It checks the configured endpoint health and expected model ID, constructs the official agent with Ubuntu, screenshot observation, PyAutoGUI action space, relative coordinates, and the recorded token limit, then injects the existing inference client. The factory binds each actor's own goal, identity, trace sink, action budget, and artifact directory.

This is a reference path, not a statement that the model service is currently running or that all 30 workflows have passed live validation. Keep model weights, prompts, parser, decoding, and model-specific API behavior within the existing OSWorld agent/inference integration. This phase implements no new adapter.

## Hidden evaluator boundary

Agent input may include its assigned goal, public observations, and its own action history. It must not receive expected final values, evaluator state, partner-private state, or instrumentation fields that reveal a hidden conflict. Runtime observers and evaluators read authoritative/hidden state outside the agent context and emit actor-attributed provenance after each event.

## Adding an adapter later

A future adapter should implement the existing actor seam, preserve per-actor history/budget/state, submit actions through `ActorContext`, and emit the standard trace/provenance fields. Before a shared run, demonstrate one Solo episode per actor and verify reset and evaluator boundaries. Do not add another planner or alter task/evaluator semantics as part of adapter integration.

## Source references

- `swcub/actors.py` — `Actor` protocol and scripted actor examples.
- `swcub/environment.py` — role-scoped `ActorContext` and environment contract.
- `swcub/osworld_agent_actor.py` — OSWorld `predict`/`reset` bridge, action forwarding, trace, pause/resume/yield.
- `swcub/osworld_qwen_actor_factory.py` — pinned Qwen reference factory.
- `swcub/orchestrator.py` — multi-actor scheduling and event ownership.
