# Four-task shared desktop scaling pilot — 2026-11-04

## Scope update: four-concurrent only

At 09:48 UTC on 2026-11-04, the user requested only four-concurrent runs and their
scores. The original controller and the active Freehand width-1 condition were
stopped; remaining width-1/2 work is cancelled. Already-recorded control artifacts
are preserved, not reclassified as successful results. No four-agent task is rerun.
Only the eight existing four-agent task outcomes are judged, starting with role D
for both harnesses. The new tmux session is `paragui-weave-quad-judge-r1`, controller
`paragui-weave-quad-judge-controller-r1`. The original scope below is retained for
audit; `scope-change-20261104.json` and pre-change progress/report copies preserve
the intervention. Live `run/batch/REPORT.md` now shows only four-agent scores.

## Workload and controls

This continues the official-task pair experiments with **four independent agents
on one desktop**, not four desktops and not a mixed Codex/Freehand team.

| Role | Official task | Software |
|---|---|---|
| A | `DES_task_0_inkscape_vectorize_logo` | Inkscape |
| B | `DES_task_11_inkscape_svgo_node_diet` | Inkscape |
| C | `DOC_task_10_lo_writer_trackchanges_audit` | LibreOffice Writer |
| D | `DOC_task_2_heading_style_normalize` | LibreOffice Writer |

The original task prompts are unchanged. The source is the **frozen initial input
dataset**, never an earlier agent's outputs. The two colliding input `README.md`
files are retained under `task_readmes/wvink/` and `task_readmes/wvwriter/`, with a
neutral index at the workspace root. Primary inputs and output filenames are
unchanged. `/tmp_workspace` still aliases `/workspace`.

This is a **mixed-software, separate-document scaling pilot**: two Inkscape tasks
plus two Writer tasks. It is not four tasks modifying one document or four tasks
in one application. All conditions have the same four tasks, initial workspace,
two applications, three starting document windows, image and desktop resources.

Each harness runs all three concurrency levels once:

- Width 4: A+B+C+D start together behind one barrier.
- Width 2: A+B run together, then C+D together on the same continuing desktop.
- Width 1: A, B, C, D run serially on that desktop.

Total: **six conditions, 24 task attempts**, plus unscored four-agent preflights.
Priority order: Freehand-4, Codex-4, Codex-2, Freehand-2, Freehand-1, Codex-1.
This gives an early four-agent diagnostic, but is not randomized and is not a
statistically calibrated estimate. Old two-task trials are not identical controls;
primary comparisons must use these newly matched four-task conditions.

## Fixed configuration

- Model `gpt-6-astra`, reasoning `high`.
- Hybrid GUI+CLI, including application APIs and XML when not prohibited by the
  actual task Prompt. No private desktops or separate GUI profiles.
- Per task: 300 desktop actions, 90 successful model responses, 1500 seconds.
- Four recent tool images upstream; raw observations retained on disk.
- Desktop: 4 CPUs, 8 GiB RAM, 1600×1000 Xvfb display; tool images 1280×800.
- Each harness: 2 CPUs, 2 GiB; private context and writable runtime.
- One DBus session, shared application profiles, clipboard, keyboard/mouse and
  filesystem. Explicit DBus addressing also lets target CLI calls join that session.
- No cross-agent action lock, automatic refocusing or inference concurrency cap.
  The existing per-agent outstanding-call guard remains.
- Native retry settings are unchanged. Four simultaneous model clients can expose
  API token-rate limits; failures are labeled as such, not as GUI errors.

The scheduler waits for all members of one wave before starting the next. The
manifest stores the intended waves and concurrency, while `concurrency.json`
records actual peak distinct active agents, time at each activity level and
overlapping HTTP requests. Duplicate requests from one agent do not count as
additional agents.

## Readiness and durability

Both harnesses undergo a four-agent screenshot and CLI preflight in the actual
two-application desktop. Readiness requires all four agents to obtain successful
model output and perform both operations, correct image policy and isolation,
and observed four-agent lifetime overlap. Native terminal status is kept separate:
a final-response rate-limit error does not erase otherwise verified tool access.
Each harness gets at most two preflight attempts; originals remain archived.

The controller is detached in personal-account tmux and uses only personal
rootless Docker. Host Codex configuration is fingerprinted and not changed.
Agents/judges receive neither the Docker socket nor provider secrets. Graders,
ground truth and published solutions are absent from agent/desktop mounts.

Resource gates retain at least 40 GiB free disk and 12 GiB available memory, with
bounded waits. Outer watchdogs cover each condition. All six execution conditions
run before any quality judge starts, avoiding judge traffic during execution.
An unsuccessful condition or judge is retained and does not silently stop later
conditions. No selected task is automatically rerun to replace a poor outcome.

Maximum task-time budget across the six conditions is approximately 5 h 50 min,
excluding preflight, startup and resource waits. Judging follows separately with
900 seconds per task, up to 6 additional hours. Per-condition efficiency tables
are available as soon as each execution ends, before quality scoring completes.

## Quality policy v2

The previous Writer-heading judge applied an UNO/XML prohibition from hidden
grading prose, although the agent-visible task did not state it and the protocol
allowed hybrid operation. This pilot does **not** repeat that protocol conflict.

The unchanged upstream trajectory-aware judge template is still used in isolated
Codex, but its normative `task.md` contains only the original agent-visible
**Prompt**. The packaging note makes clear that hidden method prohibitions must
not be invented and the Prompt takes precedence over conflicting reference
thresholds. Real GUI evidence, authenticity, required artifacts and explicit task
constraints still apply. The label is `agent-visible-hybrid-v2`, **not** an official
WeaveBench leaderboard evaluation. The original full specifications are retained
privately for provenance; old runs/scores remain unchanged.

The judge receives attributed trajectories for all four agents and one shared
frozen final workspace. Evidence mounts are read-only. Missing/malformed/timed-out
scores stay null, not zero. A completed agent is not automatically a successful
task. Quality equivalence must be checked before interpreting token/time savings.

## Metrics

`performance.json` records per-role and aggregate:

- First-agent-start to last-agent-finish wall time, excluding setup/judging.
- Sum of agent elapsed times, with overlap counted separately.
- Reported input/output/cached/reasoning tokens and missing-usage request counts.
- Successful responses, action-channel counts, HTTP 429 and other request errors.
- Explicit Freehand retry sleeps when available; absent Codex counters stay null.
- Actual agent and HTTP concurrency.

Failures are not counted as faster, cheaper successful work. Token counts include
repeated context and cached inputs; they are not an invoice estimate. Time saved
from overlapping execution must not be confused with lower aggregate agent time.

## Deployment

```text
/data/users/yuke/paraGUI/weavebench/quad-20261104-r1/
  dataset/provenance.json
  frozen-inputs.sha256
  run/launch-status.json
  run/batch/progress.json
  run/batch/REPORT.md
  run/batch/{freehand,codex}-c{1,2,4}-r1/
  backup/reports-final.tar.gz
```

Tmux: `paragui-weave-quad-r1`; controller: `paragui-weave-quad-controller-r1`.
Runtime image: `paragui/weavebench-pairs:20261103`, pinned to
`sha256:312f8d9f1b52d7494c98fe2d7fc88c58e818234db4b72a9aa1f2e956364d412e`.

Local summary mirror: `runs/comparisons/weavebench-quad-20261104-r1/latest/`, updated
every three minutes by `paragui-weave-quad-mirror-r1` for up to 18 hours. This is a
compact report/score/performance mirror, not a full screenshot archive.

Live status: `bash runs/launches/weavebench-quad-20261104-r1/status.sh` from CoDesk.

Local scheduler, waveform concurrency, input isolation, legacy regression and
prompt-grounded scoring tests: **129 passed** before deployment.
