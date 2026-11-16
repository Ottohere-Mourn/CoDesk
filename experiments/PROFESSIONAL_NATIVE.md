# Native Codex / Freehand professional-software pilot

This is a separate experiment from `professional_shared.py`'s custom Responses
desktop loop. It runs the installed Codex CLI binary or the existing Freehand
agent loop and restart supervisor. Each condition has two independent agents,
one shared Docker/X11 desktop, one application instance, and one native project.

The planned pilot has six conditions: Blender, FreeCAD and QGIS, each with a
Codex/Codex pair and a Freehand/Freehand pair. It does not mix harnesses inside a
pair and does not include matched sequential controls. Each condition starts
from fresh input files. Only one condition runs at a time to reduce API pressure;
its two agents start at a barrier and run concurrently.

## Personal-account rootless rebuild: 2026-11-03

The new CPU10 account is `yuke`, reached through `yuke-jump` and then `cpu10`.
Its data root is `~/data` (`/data/users/yuke`); the former `yifan` experiment
directory is not readable from this account. No old account, socket, or sudo
access is used. Current connection rules are in `~/code/GPU_node/CPU_NODE.md`.

A separate rebuild is deployed at
`/data/users/yuke/paraGUI/rebuilds/professional-native-hybrid-rootless-20261103T095500Z-r2`.
The local launch bundle is `../runs/launches/professional-native-hybrid-rootless-20261103T095500Z-r2`.
It restores the checksum-verified local p1–p3 authoring package, the unchanged
Python runner sources, Codex 0.163.0 and Freehand. The image is rebuilt in the
personal rootless daemon, not copied from the inaccessible shared daemon.

The non-root infrastructure controller runs in that daemon's network namespace
so that the existing internal-network desktop/API brokers work unchanged. Only
this controller receives the personal Docker socket and provider credentials.
Native agents remain separate non-root, restricted-network containers with no
socket, credential, reference, or grader mounts. Host Codex configuration is not
changed. This is a new environment/batch, not pooled with the earlier results.

Local and CPU regression checks both pass 75 tests. All three restored pristine
inputs score at most 1/6, and all six reference tasks score 1.0 in the new image.
The initial deployment's Codex preflight failed closed because the companion
`codex-code-mode-host` executable was omitted: no desktop actions or formal
conditions ran. That attempt is preserved without the `-r2` suffix. The retry
copies the complete native binary directory and freezes 104 deployment files.
It runs fresh Codex and Freehand hybrid preflights before the six-condition batch;
follow `run/launch-status.json` and `run/pilot/progress.json` in the retry root.

The retry completed on **2026-11-03 at 11:02:42 UTC**. Both preflights passed;
all six formal conditions passed integrity validation and all twelve agents
completed with exit code zero. Formal execution started at 10:18:20 UTC and
took 44 minutes 22 seconds. The common-final-state scores are:

| Software | Codex A / B | Freehand A / B |
|---|---|---|
| QGIS | 6/6, 5/6 | 6/6, 5/6 |
| Blender | 6/6, 6/6 | 6/6, 6/6 |
| FreeCAD | 5/6, 6/6 | 5/6, 6/6 |

Both QGIS B results fail `scale_and_field_notes`; both FreeCAD A results fail
`machining_drawing`. These are the unchanged grader's outcomes, not a diagnosis
of concurrency interference or proof of a grader defect. This remains a
single parallel pilot without sequential controls or repeated seeds.

The formal batch records 202 HTTP 200 responses and seven retried HTTP 503
responses. The relay windows history on 75 requests: maximum original image
count 26, maximum transmitted count four, and no HTTP 400 responses. All 104
frozen files and the CPU host configuration fingerprint verify unchanged;
all conditions use image `sha256:a9ffcf4b57ff9f2ab0454319bbd1c6237f7bf581a44991da0da602c5b76bf4ac`.
No experiment containers remain running. A checksum-verified full trajectory
archive, report and final audit are backed up locally under
`../runs/comparisons/professional-native-hybrid-rootless-20261103T095500Z-r2/`.

## Image-history fix: 2026-11-03

The r2 QGIS Codex B failure is a request-history issue, not evidence that the
CPU VM or API is unavailable. Reconstructing the original gateway trace shows
requests 49–53 contained 46–50 images and returned HTTP 200; request 54 contained
51 and returned HTTP 400: `Exceeded maximum number of images (50) allowed in
the request.` The compared Freehand B trace never exceeded four images; its
native config set `image_history_limit=4`. Both task models were `gpt-6-astra`.
Fifty is the cap observed at this configured provider, not a universal API limit.
The old failed run and its scores are not changed by this fix.

New native runs use `--image-history-limit 4` by default, passed to both
Freehand's native configuration and the host Responses relay. The relay:

- Windows image parts in both Codex's `custom_tool_call_output.output[]` and
  Freehand's `function_call_output.output[]`; changing message content alone
  would miss the actual Codex screenshots.
- Keeps the newest four tool images in ordinary single-screenshot calls,
  preserves all images in the newest image-bearing tool output, and pins
  non-tool images such as task/reference input. Pinned images reduce the
  remaining 50-image request budget. If references plus the newest observation
  exceed it, the request fails explicitly rather than silently deleting them.
- Replaces old image parts with a text archival marker, retaining item order,
  call IDs, tool calls/results, text, reasoning and model settings. It leaves
  the native history and original gateway request intact; screenshots remain
  available in the recorded trajectory.
- Applies to both `/responses` and `/responses/compact`, forwards SSE unchanged,
  and records a versioned policy, original/sent/omitted counts, omitted JSON
  paths and exact outgoing SHA256/byte count. Request summaries include counts;
  manifests/results identify the changed harness condition.
- Requires full stateless input; hidden `previous_response_id`/`conversation`
  history is rejected when this policy is enabled. Both observed native traces
  used full stateless input. Unconfigured generic relays remain pass-through.

Use the same limit for preflight and batch; an old preflight without this
policy cannot authorize a new batch. This is an explicit **harness adaptation**,
not a claim that stock Codex now has an image-count option. Token-based context
compaction is separate; local request-size and token budgets still apply.
No host/VM Codex settings or permission policy are changed.

### Validation at 07:48 UTC

- The final local suite passed **155 tests**, covering both native tool-output
  shapes, 100-observation histories, pinned references/current observations,
  SSE, retry determinism, compaction routing, trace audits, CLI/config wiring
  and preflight-policy mismatch rejection.
- Reconstructed and checked **all 54** real Codex B requests offline. Only
  selected image parts change; restoring those parts reproduces each original
  request exactly. Request 54 changes **51 → 4** images, omitting 47.
- Replayed that failed request on CPU VM10 through the patched relay with the
  same provider credentials/model/reasoning settings. The only additional
  request override was `max_output_tokens=512` to bound validation cost.
  The provider returned **HTTP 200, `completed`**, in about 4.5 seconds.
  It returned a tool call; **zero returned actions were executed**. This is a
  real request/relay check, not a resumed native agent or full benchmark run.
- SHA256 checks confirm the historical frozen source, original failed trace,
  original stdout and VM Codex config remained unchanged (18 protected files).
- CPU evidence and the exact patched relay/replay script are separate at
  `/data/yuke/paraGUI/research/image-history-20261103T074801Z/`. A credential-free
  evidence copy is `../runs/validation/image-history-20261103T074801Z/evidence.json`.
  The corrected full runner has not been deployed as a new CPU benchmark
  attempt; a fresh matching preflight is required before starting one.

## Hybrid pilot launched on 2026-11-03

At **08:07:26 UTC**, started the separate user service
`paragui-professional-hybrid-20261103T080412Z.service` on CPU VM10. Its root is
`/data/yuke/paraGUI/comparisons/professional-native-hybrid-20261103T080412Z/`.
This is a fresh **hybrid GUI+CLI, four-image-window** attempt, not a continuation
or replacement of the old GUI-only scores. No p4–p9 candidates are included.

- The exact local runner snapshot and a separate Freehand runtime copy are
  frozen for this attempt. Seventy-seven source/runtime/dataset/binary files
  have SHA256 guards; existing task inputs, graders and native binaries are
  reused without modification. No new API credentials are copied to agents.
- **75 CPU tests passed**. The durable launcher then runs separate Codex and
  Freehand two-agent preflights. Both agents in each preflight must complete a
  screenshot and the target-container CLI probe before the batch is authorized.
- After both pass, the queue runs QGIS/Codex, QGIS/Freehand, Blender/Freehand,
  Blender/Codex, FreeCAD/Codex, FreeCAD/Freehand. Conditions are sequential;
  each condition has two independent concurrent agents sharing one desktop.
  Each agent is bounded by 300 actions, 90 successful responses and 1,500 seconds.
- Codex uses the previously authorized `container-unrestricted` mode only
  inside its guarded Docker harness. Host/VM Codex config fingerprints are
  checked before each stage and again on exit. No host permission change occurs.
- `launch-status.json` tracks tests/preflights/pilot; `pilot/progress.json`
  tracks the six conditions once started. Logs are `cpu-tests.log`,
  `preflight-{codex,freehand}-01.log`, `pilot.log` and the per-condition logs.
  Any preflight failure prevents the batch; a condition error stops the queue.

The initial launch record establishes that the service entered the Codex
preflight stage, not that any native agent or full benchmark completed. Local
launcher/deployment records are under
`../runs/launches/professional-native-hybrid-20261103T080412Z/`.

### Infrastructure delay and guarded retry

The initial preflight failed at **08:09:09 UTC**, before any model request:
creating its desktop container exceeded the existing 90-second deadline.
A separate disposable `true`-only container probe also timed out after 180
seconds. The shared VM showed up to 88% CPU I/O wait, roughly 80% full I/O
pressure and over 11 GiB of dirty pages. These are storage-pressure observations,
not an API or image-history failure. The failed attempt is retained unchanged;
its VM Codex fingerprint guard passed. No Docker restart, pruning of shared
containers, permission change or intervention in another workload was attempted.

At **08:16:23 UTC**, started the separate service
`paragui-professional-hybrid-20261103T080412Z-r2.service`, rooted at
`/data/yuke/paraGUI/comparisons/professional-native-hybrid-20261103T080412Z-r2/`.
It uses the same runner code plus a launcher-only resource gate, with **78**
frozen files. Its 75 CPU tests passed again. Before each preflight and the pilot,
it waits for three consecutive 10-second samples with I/O wait and full I/O
pressure below 20%, dirty pages below 2 GiB and at least 40 GiB free disk space.
Each gate waits at most one hour, then fails without starting that stage.
Waiting makes no model calls. No failed output directory is reused.

At **08:17 UTC** the retry was active in `waiting-resources-codex`, not yet a
running model experiment. `resource-status.json` and `resource-samples.jsonl`
show the gate measurements; `launch-status.json` remains the authoritative stage
record. Once healthy, the service automatically runs both native preflights and
then the six-condition batch; it still fails closed on any preflight error.

### Running update: 2026-11-03 08:30 UTC

The first resource gate passed at **08:24:11 UTC**, after about 7.5 minutes;
this was waiting for I/O pressure to subside, not a disk-repair operation.
Codex's two-agent hybrid preflight passed at **08:24:51 UTC** and Freehand's
passed at **08:25:54 UTC**. Every agent completed one screenshot and one target
CLI probe. The formal pilot started at **08:26:25 UTC**.

At 08:30 UTC, QGIS/Codex is running: agents A/B have 11/14 successful HTTP 200
responses, with GUI and CLI actions recorded. Their latest requests retained
four images from original histories of six and twelve respectively, confirming
that the new image window is active in a native rollout. Other conditions remain
queued; these observations are not final task scores. The workload responsible
for the earlier storage-pressure spike has not been identified.

The two timed-out diagnostic/preflight container creations later materialized
as stopped/created containers. After verifying their exact names, image,
commands and mounts, only those two owned remnants were removed; the old
bind-mounted experiment files and all live/other containers were preserved.

## Current interaction policy: 2026-11-03

New native runs default to `--interaction-mode hybrid`: GUI, terminal/CLI,
application consoles and programming are allowed. `--interaction-mode gui-only`
retains the historical restricted condition as an explicitly labelled ablation.
Permission mode and interaction mode are independent: the default permission
mode is still `reviewed`; `container-unrestricted` remains explicit and Docker-only.
No host/VM Codex configuration is changed.

In hybrid mode Codex's native shell is enabled in its private `/session`, as
Freehand's Bash already is. Target files still reside only in the desktop
container. Both agents can send a single `shell` action through the same desktop
MCP/bridge, for example:

```json
{"actions":[{"type":"shell","command":"pwd; python3 --version","timeout":30}]}
```

This executes as desktop UID 1000, in `/workspace`, with the shared X display,
not as a host shell. There is still no Docker socket, host-home, evaluator,
reference or credential mount. Commands have a 60-second maximum (also bounded
by the agent deadline), return up to 16 KiB per stdout/stderr stream, and record
exit code, timeout and a fresh screenshot. A command is the only action in its
call; same-process-group children are killed on return, so long-lived background
jobs are unsupported. This is resource management, not an adversarial process
sandbox: deliberate process-group escape is not prevented by this helper.
The Docker boundary is the isolation boundary.

Each broker event records `channel=gui|cli|observation`; results contain
`broker_action_counts`. Native harness-local shell calls remain in native logs,
and code typed into a console remains GUI-mediated input: channel counts are
not a reliable count of all programming activity or comparable units of work.
Do not interpret CLI calls as clicks or aggregate old GUI-only scores into a
hybrid result. Parallel shell requests use no cross-agent lock. Scripts must
preserve the coagent's edits; no stale offline project may replace the live one.
Auxiliary CLI processes are permitted, so manifests record the *initial*
application count rather than asserting only one process exists throughout.

A hybrid `--smoke` requires **both** agents to take a screenshot and successfully
execute a harmless target-container CLI probe. The batch validates the interaction
mode, permission mode and both action logs; an old GUI-only preflight cannot
authorize a hybrid batch. Pass the same mode to preflight and batch. Always use
a new output directory; frozen historical sources/results remain untouched.

This code change does not register p4–p9 or claim any new model-driven run.
The existing p1–p3 dataset and graders are unchanged. See
`../tasks/professional_v2/README.md` for the six hybrid task candidates.

### Validation on 2026-11-03

- Full local suite: **128 tests passed**, including the hybrid Codex/Freehand
  prompts, permission-mode separation, preflight mismatch checks, concurrent
  command dispatch, bounded output and timeout/child cleanup tests.
- A separate real local Docker CLI transport check passed seven checks: host
  entry rejection, desktop UID/cwd/DISPLAY environment, concurrent shared-file
  access, nonzero exit/stderr capture, timeout, output cap and unchanged host
  Codex config hash. The container used `python:3.11-slim`, UID 1000, no network,
  a read-only root, dropped capabilities, and only a disposable workspace mount.
  It was removed after validation. Evidence:
  `../runs/validation/professional-hybrid-20261103T044555Z/manifest.json`.
- This validates CLI transport, **not** a real professional GUI or native-agent
  rollout. The documented VM10 SSH route failed at the local jump forwarding
  port (`Connection refused`); no new VM deployment or model experiment was
  started. Historical experiment sources, scores and VM Codex settings remain
  untouched. A fresh two-agent hybrid preflight is required before a batch.
- Follow-up at **04:53 UTC**: VM10 is reachable through the current managed
  route `gpu48-jump -> cpu10`; the `remote_cpu/vm10.py` manager helper also
  succeeds. The failed attempt used a legacy route, not evidence of VM downtime.
  See `../docs/SERVER_PLAN.md` for current per-machine key selection and the
  outer jump master's lifetime caveat. This follow-up only checks connectivity;
  it does not deploy or start a model experiment or change any key/permission.

## Historical GUI-only access (2026-11-02)

- Existing VM and host Codex settings are never modified. Privileged Docker mode
  is never used. The default Codex mode remains `reviewed`; the explicitly
  authorized container-only alternative is described below.
- Codex has a new per-agent `CODEX_HOME`, `sandbox_mode = "workspace-write"`,
  `approval_policy = "on-request"`, and its shell tool and subagents disabled.
  The noninteractive CLI uses its native `--approve-for-me` approval reviewer;
  requests still undergo review rather than bypassing approvals. Plain `exec`
  rejected MCP requests under its effective `never` policy in the retained
  preflight, despite the on-request configuration.
  The CLI requests `codex-auto-review` for this reviewer. The relay forwards that
  exact model name without substitution, separately from the pinned task model.
  If the provider cannot serve it, the preflight fails closed; approval checks
  are not disabled. Reviewer calls and usage are recorded separately by model.
  A stdio MCP server exposes only the desktop-action schema. This is native
  Codex orchestration/context management with a GUI-only tool configuration,
  not unrestricted native coding-agent access in the default `reviewed` mode.
- Freehand's source, Bash/finish tools, transcript editing and restart supervisor
  are preserved. Bash operates only in its isolated harness container; a bridge
  command returns desktop screenshots through its native image-manifest channel.
  Its initial recent-image limit is four. These native context/tool differences
  are part of the harness comparison, not a pure model comparison.
- Agent containers have a read-only root filesystem, a private writable harness
  directory, no Linux capabilities, and an internal-only Docker network. They
  receive neither task files nor the Docker socket, host home, graders, reference
  outputs or upstream API credentials. Credentials remain in the host relay.
- The desktop container has no network. Both harnesses reach it only through the
  same validated GUI primitives. Opening a console through the GUI is prohibited
  by the task prompt, not blocked by the operating system.
- There is no cross-agent input lock, automatic refocusing or communication.
  A second outstanding desktop call from the *same* agent is refused. Log locks
  protect bookkeeping only. Both agents know the desktop is shared but see only
  their own task.

### Explicit container-only unrestricted mode

On 2026-11-02 the user authorized `danger-full-access` plus `never` **only inside
the experimental Docker harnesses**, and explicitly prohibited these settings
and YOLO on the host or VM itself. Select this mode with
`--codex-permissions container-unrestricted` on both the preflight and batch.
The batch rejects a preflight obtained under a different permission policy.

The per-agent on-disk config still defaults to `workspace-write/on-request`.
Only `/bridge/codex_entry.py`, launched as the command inside `docker run`, adds
the two process-local `-c` overrides. It first checks Docker's marker, non-root
execution, `/session` as the working directory and HOME, and the isolated
`CODEX_HOME=/session/codex-home`; otherwise it refuses to start Codex. This is an
accidental-host-launch guard, not a replacement for Docker isolation.
No `--yolo` flag or native auto-review model is used in this mode. Its effective
permissions are nevertheless YOLO-equivalent: reports explicitly set
`yolo_enabled=true`, `yolo_flag_used=false`, and record the container-only scope.
`permission-audit.json` records the entry checks inside each harness runtime.
Collection also verifies the native task model's `turn_context` records against
the requested sandbox, approval policy and working directory; a mismatch fails
the condition rather than being reported as a successful preflight.

The read-only root filesystem, limited writable session mount, dropped Linux
capabilities, internal network, credential isolation and GUI broker remain in
place. The shell tool, subagents and web search remain disabled. Opening an
application console via the GUI is still only prohibited by the prompt.
Previously collected runs and frozen source directories are not rewritten;
this permission change must use a separate source snapshot and run directory.

## Collection

`professional_native.py` runs one condition. Its `--smoke` mode asks both agents
to obtain a screenshot, report the visible application and finish without
changing the project. Real model/desktop preflights must pass for both harnesses
before `professional_native_batch.py` accepts a six-condition batch.

Defaults per agent: 300 GUI primitives, 90 successful model responses, 1500
seconds. The collector records native output, isolated native session files,
host-side request/response traces, every GUI primitive and screenshot, shared
focus/timing events, and exact collector source snapshots. Native context
compaction and retry traffic remain visible in the request logs.

Both agents stop before the desktop is removed and the original six-check
graders inspect the common final files. A process exit code is not task success.
`concurrency.json` includes cross-agent timing, observation exposure and action
log consistency checks. `index.html` replays the interleaved GUI actions.

Failed preflights and runs are retained in separate directories. The batch stops
on collection/infrastructure errors rather than silently retrying or replacing
results. It writes `progress.json` and `REPORT.md` after each condition.

## Interpretation

This pilot is exploratory, with one run per condition. It cannot establish a
stable success rate or isolate the causal effect of concurrency. Matched solo
and both sequential orders remain follow-up work. FreeCAD's SVG representation
check and QGIS's literal north-label check are unchanged; preserve raw scores
and document any semantic grading issues separately.

The original wide-permission adapter in `codex_vm10.py` is **not used** by this
experiment. Source and launch configuration for this experiment are in
`professional_native.py`, with the stdio/command bridge in
`professional_bridge.py`.

Validation: `python -m pytest -q tests/test_professional_native.py`.

## Launch status on 2026-11-02

Freehand's two-agent screenshot preflight passed. Each agent obtained an actual
QGIS screenshot through the bridge and identified the window; input files were
unchanged. Its three-condition pilot was started as the VM10 user service
`paragui-professional-freehand-20261102.service`, in order QGIS, Blender, FreeCAD.
Results are under
`/data/yuke/paraGUI/comparisons/professional-native-20261102/freehand-pilot/`.
This is a launch record, not a claim that the tasks have finished or passed.

Codex's retained `preflight-codex-07` reached its native approval reviewer, but
the upstream service returned HTTP 403 for `codex-auto-review`: that model is
unavailable to the configured API key. Both agents correctly refused to execute
the screenshot without completed approval. No Codex formal condition was started.
The approval was not overridden, the reviewer was not replaced with the task
model, and no YOLO mode was enabled. Continuing Codex requires a working native
approval service or explicit user authorization of an alternative scoped
desktop-tool approval workflow.

Early preflights also exposed Docker default subnet exhaustion (resolved with
an unused, overlap-checked internal subnet), missing deployment support code,
and the plain-exec approval-policy mismatch. They remain separately archived.
HTTP 429 token-rate limits occurred in both harness preflights and at pilot
startup; these are transport limitations, not evidence of GUI interference.

## Container-only launch queued on 2026-11-02

The authorized alternative is deployed separately at
`/data/yuke/paraGUI/comparisons/professional-native-container-20261102/`, with its
own frozen `source/` and `launch.sh`. The user service
`paragui-professional-codex-container-20261102.service` was started at 08:25 UTC.
It waits for the existing Freehand batch to stop before making any model calls,
then runs a two-agent QGIS screenshot preflight and, only if that succeeds,
the Codex QGIS, Blender and FreeCAD conditions. Both the preflight and batch
explicitly select `container-unrestricted`; the older reviewed preflights are
not reused. Real GUI preflight success was still pending at this launch record.

Validation before launch: 88 local tests passed, including 21 native-runner
tests; the same 21 tests passed on VM10. The real VM rejected the container
entry guard, and a non-root isolated Docker container passed that guard without
executing Codex or calling the model. This boundary check is not a GUI preflight.
The local and VM Codex config hashes remained unchanged. The launcher compares
the VM config fingerprint before preflight, before the batch and on exit, and
records `launch-status.json`, `vm-config-before.sha256` and
`vm-config-after.sha256`. Previous experiments and their frozen source remain
unchanged.

## Progress checked on 2026-11-02 at 13:35 UTC

Freehand finished collecting all three conditions at 08:45:52 UTC. Raw
six-check scores are QGIS A 6/6, B 1/6; Blender A 3/6, B 2/6; and FreeCAD
A 5/6, B 1/6. All three collection-integrity validations passed, but five of
the six agent runs reached the time limit. The request logs contain 200 HTTP
429 responses in total. These are exploratory scores under rate limiting,
not success rates or evidence isolating the effect of GUI concurrency.

The original queued Codex attempt failed at 08:46:22 UTC before native agents
started: the launcher passed `runtime/freehand` instead of its parent `runtime`
as `--freehand-runtime`, preventing import of the shared trace module. Its
source, failed run and logs are retained unchanged. The runner now checks the
required package layout before creating a desktop; 90 local tests and 23
VM-native-runner tests passed after this correction.

The separate corrected attempt is
`/data/yuke/paraGUI/comparisons/professional-native-container-20261102-r2/`.
Its real two-agent screenshot preflight passed: each Codex agent made one GUI
screenshot action and three successful model responses, identified
`HarborDrainage — QGIS`, and exited normally. Both native session records
confirmed `danger-full-access`, `never`, and `/session`; container entry audits
confirmed the isolated home and non-root Docker execution. The VM's Codex
configuration fingerprint was unchanged after preflight.

The service `paragui-professional-codex-container-20261102-r2.service` started
the formal batch at 13:35:41 UTC. QGIS is running, with Blender and FreeCAD
pending; this is a startup record, not a claim of task completion. Follow
`codex-pilot/progress.json` in that attempt directory for live status.

## Progress checked on 2026-11-02 at 16:10 UTC

The corrected r2 batch is now `stopped_on_error`, not running. Its QGIS
condition ended at 13:49:07 UTC with common-final-state scores A 6/6 and B 3/6.
Agent A completed; agent B exited with code 1 after 162 GUI actions. Blender
and FreeCAD remain pending because the batch stopped on that error. This
snapshot does not establish the underlying error cause or attribute it to GUI
concurrency. The failed condition and its original scores remain untouched;
no replacement or retry is launched by this research update.

Separate work now researches public professional-software trajectories and
authors original task candidates. See
`../docs/PROFESSIONAL_BENCHMARK_RESEARCH_20261102.md` and
`../tasks/professional_v2/README.md`. These new candidates do not replace any
frozen p1–p3 task or experimental result.
