# First Qwen3VLAgent Smoke Plan

## Status

**Prepared, not run.** No model process was started in this phase. This plan fixes the existing OSWorld V2.1 `Qwen3VLAgent` and local `Qwen3-VL-30B-A3B-Instruct` weights. It adds no task and changes no evaluator.

Fixed setup:

- Agent pipeline: `/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/mm_agents/qwen3vl_agent.py::Qwen3VLAgent`.
- Actor bridge: existing `swcub.osworld_agent_actor.OSWorldAgentActor` using the native screenshot → predict → OSWorld action loop.
- Weights: `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`, existing local checkpoint; config SHA-256 `6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912`.
- Inference: existing local, offline Transformers worker, `local_files_only`, `do_sample=False`; no paid API, download, or training.
- Budget: at most 20 model predictions per GUI Actor episode, matching the existing calibrated Browser task bound.
- Evaluators: unchanged `GuestFocusEvaluator` and `GuestWebStateEvaluator`.

The Qwen solo calibration is task-specific. The earlier baseline's Browser task passed 5/5, while Writer passed 2/5 and Calc 0/5; those office results do not establish competence on the V2 terminal focus fixture. Shared conditions remain gated on a Qwen solo pass for each exact task and a solo pass for the other actor.

## Task 1 — GUI focus and input routing

Use `SWCUB-FOCUS-ROUTING-001` on the shared Guest with visible Document and Chat terminal windows. Qwen's independent goal is to enter exactly `Approved` in Document and submit with Enter. The scripted Human Replay goal is to enter exactly `Review note` in Chat. `GuestFocusEvaluator` checks both files and cross-window integrity.

| Episode | Active actors | Schedule/intervention | Gate |
|---|---|---|---|
| Solo control A | Qwen GUI Actor | Qwen gets up to 20 steps; Human Replay absent | Qwen must pass exact Document predicate. |
| Solo control B | Human Replay | One scripted replay | Must pass exact Chat predicate before shared conditions. |
| Naive Shared | Qwen + Human Replay | Qwen receives a first turn, Human Replay focuses Chat and completes its goal, Qwen resumes from a fresh screenshot and may recover autonomously | Preserve all actions and classify model failure separately from misrouted input. Do not force Qwen to type into Chat. |
| Focus-aware recovery | Qwen + Human Replay | Same actor goals and turn order; `before_actor_turn` verifies/re-activates Document before each Qwen turn and logs the scheduler click separately | Qwen still chooses and executes its own content/edit actions; the scheduler changes focus only. |

The GUI task's `focus-aware` action is an explicit scheduler intervention. It should activate the visible Document window by a stable window ID or a documented screen-coordinate click; it must not type task text on Qwen's behalf.

## Task 2 — GUI+CLI stale-state consistency

Use `SWCUB-STALE-MERGE-001` and its existing local Browser page/backend. Qwen's goal is to set `gui_status=Approved` and preserve all other fields. The scripted CLI actor writes `cli_note=Reviewed by CLI`. `GuestWebStateEvaluator` verifies the exact authoritative Guest JSON after actors finish.

| Episode | Active actors | Schedule/intervention | Gate |
|---|---|---|---|
| Solo control A | Qwen GUI Actor | Initial page at revision 0; no CLI mutation | Qwen must pass `gui_status=Approved`. |
| Solo control B | Scripted CLI Actor | Existing CLI update only | Must pass `cli_note=Reviewed by CLI` before shared conditions. |
| Naive Shared | Qwen + CLI | Load the GUI page/cache, commit the CLI update at the declared trigger, then return control to Qwen with a fresh desktop screenshot. The page may still show cached values; Qwen is free to refresh, inspect, and recover. | Do not force a stale whole-record save. Score both goals and lost-update signature. |
| Recovery | Qwen + CLI | Same task and trigger; after the CLI commit, the scheduler clicks the page's public “Refresh latest state” control, records a `focus_scheduler` event, and then resumes Qwen | Qwen performs its own field edit/save; evaluator and actor goals are unchanged. |

The refresh intervention tests scheduler-mediated recovery. Report it separately from naive model recovery; it is not evidence that Qwen would have refreshed autonomously. The naive model condition must retain autonomy and may also succeed.

## Run order and stop rules

1. Confirm local model/config hash and that no inference service is already using a conflicting port/GPU allocation. Keep inference loopback-only and offline.
2. Run one Qwen solo and one second-actor solo control for the focus task. If either fails, stop that task's shared conditions and retain the report/trace.
3. Run one Qwen solo and one CLI solo control for the shared-state task. Apply the same solo gate.
4. Only after each task's gates pass, run one Naive Shared and one recovery episode per task. This is an eight-episode maximum smoke set, not a repeat study. Do not add repeats in this phase.
5. Preserve `report.json`, `events.jsonl`, `model_trace.jsonl`, every input/action screenshot, focus/CLI trigger events, hidden evaluator output, `provenance.json`, resource ledger, and reset screenshot.

Any task setup, solo, evaluator, or reset failure stops shared conditions for that task. Preserve failed attempts; do not edit task goal/evaluator or quietly retry into the same directory. Re-run a failed solo only as a separately numbered diagnostic after recording its cause.

## Failure attribution

Classify each episode using the model trace, event timeline, screenshots, evaluator state, and reset result:

- **Model task failure:** Qwen fails its goal in solo, or fails without an observed competing state change that explains the divergence.
- **Interaction failure:** the second actor's valid action changes desktop focus or shared backend state before the model divergence; cite the exact event/revision and resulting screenshot/final state.
- **Coordination recovery:** success after the declared focus or refresh intervention. Do not combine this with naive results.
- **Other actor failure:** scripted Human Replay or CLI goal fails in its solo/joint episode.
- **Reset/environment failure:** task episode may still have a scored result, but it is operationally incomplete and excluded from condition success.

The smoke is descriptive only. Four task-condition pairs with one trial each cannot support a rate, significance test, or general model claim.

## Harness work required before execution

No planner or grounding work is planned. Extend the existing scenario dispatch in `scripts/run_osworld_v2_1_shared_csv.py` for the Qwen focus actor, and reuse the existing `Qwen3VLAgent`, local worker, and `OSWorldAgentActor` wiring in `scripts/run_osworld_v2_1_browser.py` for the shared-state GUI actor. Add only the two named model task scenarios/condition hooks, keep evaluator classes fixed, and call the episode provenance writer. Then validate task IDs/version and output paths without launching inference before a separately authorized smoke run.
