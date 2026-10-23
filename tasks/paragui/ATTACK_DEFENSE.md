# paraGUI attack / defense rounds

Goal: 10 *cases* (task pairs) of two computer-use agents sharing one desktop that remain hard **even after a defender
has improved the harness as much as the rules allow**, each with trajectories under every harness version. The data
records the arms race: which harness change fixed which failure, and which failures survive.

Background: dataset v1 (the o/m/w/d/f/x pairs plus revised c pairs in this directory): 24+5 pairs,
gpt-6-astra, both tasks pass in 100% of sequential runs but 20% of concurrent runs and 9% with SelfGuard (each
harness refocusing its own windows). Most failures: one agent declares the task infeasible after noticing
interference (e.g. both type into the same login form; one navigates the shared browser tab away; one restores a
stale copy of a document the other has just reformatted).

## Roles

### Blue (defender) — improves the harness
Writes `oscombo/defense/<version>.py` (`class Defense(DefenseBase)`, hooks in `oscombo/defense/__init__.py`), version
names `v1`, `v2`, ... Each version is evaluated by the lead on the case pool (parallel runs) plus a solo/sequential
regression set. Blue may read everything: task specs (`tasks/paragui/spec_*.md`), task code, all trajectories.

Hard rules (a version that breaks one is rejected):
1. **Per harness only.** The defense runs inside one agent's harness. No shared state, lock, registry, file,
   socket or naming convention between the two harnesses, no assumption that the other agent uses the same harness.
   (Real product: two assistants from different vendors on the user's computer.)
2. **Never tell the model** that another agent/user exists, or anything about anyone else's task. Generic,
   task-independent guidance that is identical for every task is allowed (and is also active when the agent works
   alone). The runner drops texts matching `oscombo.defense.FORBIDDEN` and counts violations; the lead also reviews.
3. **General.** No task ids, file names, URLs, user names, or task-specific app lists. Mechanisms for a class of
   application (e.g. "this harness always works in its own browser window / profile", "type text atomically",
   "verify the target before typing") are fine if applied uniformly to every task.
4. **No performance cost.** With the defense on, solo and sequential scores must not drop (regression set: every
   pool task alone ×1, plus sequential runs), and median steps / wall time may grow by at most ~20%.
5. Must not change task setup, assets, checkers, model, step budget or the runner outside the hook interface
   (ask the lead if a new hook is needed; hooks are added for everyone).

Useful facts: Guest = Ubuntu 22.04 GNOME under QEMU without KVM (slow), X11, `xdotool`/`wmctrl` available, apps
started by the task setup before the agents begin; `guest_sh(cmd)` runs a shell in the Guest; the model acts with
pyautogui code (`transform_action` sees it before execution); `--mediation selfguard` (oscombo/mediation.py) is the previous
baseline (refocus own windows, full-speed typing). The model's own reasoning text per step is in trace.jsonl.

### Red (attacker) — builds harder cases
Writes new task pairs with the dataset-v1 framework (`README.md`; pair ids `a1`, `a2`, ... task ids `pga1...`).
Red sees the current defense code and its evaluation results (white box) and designs pairs whose contention survives
it. All AUTHORING quality rules apply (realistic, long-horizon, GUI-required, robust checkers, offline self-test).
Additional rules:
- **Not contrived**: the two requests must be things a real user plausibly delegates at the same time; the shared
  resource must be shared because that is how the user's computer is (one mail profile, one company web session,
  one working copy, one open document), not because the pair is rigged.
- **Coordination can make both succeed**: no zero-sum design; sequential runs must pass.
- **Defense-agnostic**: the pair may not detect or special-case the harness (no checks for defense artefacts).

### Lead — runs everything, referees
Deploys versions/pairs, runs: solo screen (new pairs ×2, with the current defense), sequential (×2 orders),
parallel ×4 (2 orders × 2) under the current defense; reviews rule compliance; feeds results back to both sides.

## Scoring
Per pair and harness version: `both-pass` = fraction of parallel runs where both tasks score ≥ 0.8.
A pair counts as a **case** for the final set when: seq both-pass ≥ 1/2 (and solo passes), and parallel both-pass
under the **final** defense version ≤ 1/4. Final selection: the 10 pairs with the largest seq − par gap under the
final version (ties: longer tasks, more GUI-only content, diversity across application families).
