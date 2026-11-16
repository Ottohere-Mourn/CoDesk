# Official WeaveBench same-software pairs (2026-11-03)

## Scope and provenance

This batch uses actual task prompts and initial assets, not the earlier synthetic
p1–p3 or p10 tasks. The protocol is adapted for concurrent shared desktops, not an
official WeaveBench leaderboard reproduction.

- Upstream repository: `weavebench/WeaveBench`, commit `acf203ae24386aa9bcc0da950c533c8c796dc38e`.
- Hugging Face dataset: `wanlilll/WeaveBench`, commit `ec498fc530b685d2fea5823a64a0f7538c8bbf6a`.
- Downloaded originals: `runs/research/weavebench-official-20261103/`.
- Agent inputs contain only each original `Prompt` and the official `exec/` assets.
  No gallery solutions, hidden grading prose, expected outputs, or judge traces are exposed.
- `/tmp_workspace` aliases `/workspace`; prompts and output filenames are unchanged.
  The selected tasks have no overlapping required output filenames. Inputs merge
  only after checking for filename collisions.

| Pair | Role A | Role B |
|---|---|---|
| `wvink` | `DES_task_0_inkscape_vectorize_logo` | `DES_task_11_inkscape_svgo_node_diet` |
| `wvwriter` | `DOC_task_10_lo_writer_trackchanges_audit` | `DOC_task_2_heading_style_normalize` |

These pairs share application windows, focus, keyboard, mouse, clipboard, dialogs,
profile and filesystem, **not a single semantic document**. Inkscape starts with
the official traced SVG open; the raster-logo task opens/imports its original PNG
as part of its work. Writer starts with the contract and report both open in the
same application process/session. Separate private desktops and GUI profiles are
prohibited; normal additional document windows and headless helper processes are
allowed. The harness never refocuses on an agent's behalf after initialization.

## Experimental matrix

Each pair runs with Codex+Codex and Freehand+Freehand under three conditions:
simultaneous start, A then B, and B then A. All conditions get a fresh desktop and
byte-identical initial inputs. There are **12 paired conditions / 24 task attempts**,
one repetition each, plus unscored harness and judge preflights.

- Agent model: `gpt-6-astra`, reasoning `high`.
- Hybrid GUI+CLI throughout; no GUI-only restriction.
- Per agent: 300 desktop actions, 90 successful model responses, 1500 seconds.
- Native harness-local shell calls are not miscounted as desktop GUI actions.
- Four recent tool images retained upstream; native disk trajectories remain intact.
- The 1500-second budget standardizes the earlier experimental configuration; it
  differs from the four original task metadata timeouts (1200–1800 seconds).
- Core parallel/A→B comparisons run first; B→A runs last. Whole conditions are
  serialized, with agents simultaneous only inside the parallel condition.
- To avoid overlapping the old synthetic batch's API traffic, scored execution
  automatically waits for its terminal status, for at most two hours. This is
  separate from the disk/resource gate. No old job is stopped or modified.

Maximum model-execution time is about 8 h 20 min across the 12 conditions, plus
up to 4 h for judging at 600 seconds per task, and startup/resource overhead.
Typical runs can finish earlier. Resource checks require at least 40 GiB free,
12 GiB available RAM and acceptable I/O pressure; waits are bounded at 10 minutes
per condition. A 3600-second outer watchdog covers each paired agent run.

## Input preparation

Software is installed only into a personal rootless Docker image derived from the
already-working professional image. The resulting image ID, package versions,
upstream hashes, original prompts and frozen input hashes are archived remotely.

The SVG input is generated once by the exact Python block in the official DES11
warmup, including its randomized decoy ID; the resulting bytes are reused for all
conditions, not regenerated per attempt.

The official DOC10 generator has a corrupt `_PLAN_BLOB` and fails without its
documented fallback. During **preparation only**, the original `_plan_source.py`
is mounted read-only at the generator's fallback path `/gt/_plan_source.py` in an
isolated container. The generator is unchanged. Only its resulting contract and
the original `exec/` files reach the desktop; no GT mount or fallback source is
present during agent execution. Missing dependencies or this preparation failure
are not scored as agent difficulty.

## Grading and caveats

The upstream `weavebench/eval/agent_judge/prompt_template.txt` is archived and used
unchanged, except its normal case-ID substitution. A short packaging note explains
role attribution and aliases. The **judge executor is isolated Codex CLI, not the
upstream OpenClaw runtime**, using `gpt-6-astra/high`. This is an adapted-runtime
application of the official rubric, not the official scoring pipeline.

The judge can read the original task spec/GT, common frozen final workspace,
requested outputs, both attributed raw trajectories, and captured screenshots.
Evidence mounts are read-only. Its output remains separate from raw task results.
The official final-score formula and per-artifact clause evidence are validated;
malformed, missing or timed-out judgments stay `null`/`judge_error`, never zero.
The operational pass threshold is 0.8; continuous scores and raw evidence remain.

The two agent preflights passed (real screenshots and target CLI operations).
The first judge preflight made real inspection calls but hit API HTTP 429 token
rate limits while p10 was still active. Its incomplete record is retained. This
negative-control attempt is not a verified scoring calibration. The recovery
controller waits for p10, then starts the real task matrix without making a failed
judge preflight a global gate. Per-task judge errors likewise do not stop subsequent
conditions; any missing scores need rejudging rather than being interpreted as
task failures. API error counts/latency must be separated from GUI interference.

Known upstream rubric inconsistencies remain visible for subsequent audit:

- DES11's old `Expected Behavior`/GT use weaker compression/PSNR thresholds than
  its current agent Prompt and grading checklist.
- DES0's palette tolerance differs between Prompt and grading prose.
- DES11 calls its `M … Z` decoy a ≤1-node path, despite its stated command-count
  definition counting both `M` and `Z`. This ambiguity must not become evidence
  for concurrency-induced failure.
- DOC2 has method restrictions in hidden grading prose absent from its Prompt.
- DOC10's expected revision total is plan-based; the actual generator can omit
  a revision whose anchor is absent. The task explicitly tolerates count drift.

Do not infer concurrency harm from score deltas alone. Inspect cross-agent
interleavings, focus changes, real screenshots, and output overwrites. Single
repetitions do not estimate success probabilities or establish causality.

## Deployment and inspection

CPU10 personal account `yuke`, rootless Docker only:

```text
/data/users/yuke/paraGUI/weavebench/official-pairs-20261103-r1/
  source/                  frozen experiment adapter and tests
  dataset/                 original prompts, assets and isolated judge metadata
  runtime/                 full Codex binaries and Freehand runtime
  logs/                    image build, fixture and controller logs
  run/launch-status.json   current launch stage
  run/batch/progress.json  live 12-condition matrix
  run/batch/REPORT.md      automatically updated table and caveats
  run/batch/<condition>/   raw traces, common snapshot, judged summaries
  backup/reports-final.tar.gz
```

Active recovery tmux session: `paragui-weave-recovery-r1`; controller:
`paragui-weave-controller-r1`. The original preflight session was `paragui-weave-r1`.
Host Codex configuration is fingerprinted before and after; it is never altered.
The controller has the personal Docker socket, but agents and judges do not.
API secrets remain controller-side; isolated processes reach an authenticated
relay on an internal network. All original experimental results are preserved.

A local tmux mirror (`paragui-weave-mirror-r1`) downloads compact status and scores
every three minutes for up to 18 hours into
`runs/comparisons/weavebench-official-pairs-20261103-r1/latest/`. This provides an
off-node copy of reports, not a full off-node copy of every screenshot or trace.

Use `bash runs/launches/weavebench-official-pairs-20261103-r1/status.sh` from the
repository to fetch compact status without exposing credentials.
