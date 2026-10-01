# CoDesk Workflow Suite V1

Status: **scope frozen at eight fixed workflow templates; evidence is bounded scripted Guest validation, except F-01's separate historical Qwen evidence.** No Qwen episode was run for C-02 or F-02. One episode per listed control is feasibility evidence, not a reliability estimate.

## Protocol boundary

CoDesk evaluates independent computer-use Actors operating under one shared, non-exclusive desktop state. Conditions are:

- **Solo:** one Actor and one fresh Guest.
- **MA-ID:** two independently controlled Guest desktops initialized from byte-identical task-relevant fixtures. These workflows do not require one Actor to read another Actor's persistent file changes.
- **MA-SD:** both Actors take turns on the same Guest, desktop and relevant ephemeral GUI state.

Hold task version, fixture, goals, schedule, action budget, evaluator and reset contract fixed. Record scheduled exposure, observed state/target interference, goal outcome and recovery separately. The private evaluator reads final application state; Actors receive GUI observations only. An exposure or state change alone is not a task failure.

## Frozen templates

| ID | Family / mechanism | Apps and distinct operation graph | Actor A goal | Actor B goal | Objective oracle | Recovery | Evidence status |
|---|---|---|---|---|---|---|---|
| F-01 | Focus / input routing | Writer + Calc; direct text entry plus single-cell edit | Save the assigned Writer content | Save the assigned Calc cell value | Path-bound ODF content/cell checks and untouched-state checks | Reobserve and reactivate the intended app/target | **Legacy validated**: historical Qwen Solo, MA-ID 2/2 pass, MA-SD 2/2 fail; older task/runner evidence, not a fresh V1 protocol run. See `MECHANISM_VALIDATION_ROUND1.md`, `REAL_DUAL_AGENT_EVAL_REPORT.md`. |
| F-04 | Focus / input routing | Calc rectangular-cell visits plus Writer paragraph replacement | Fill B2:C3 and preserve guard cells | Replace the assigned Writer paragraph only | Exact full Calc matrix plus Writer content/guard oracle | Refocus, reselect the rectangle, continue | **Scripted validated**: prior Solo A/B, MA-ID, naive MA-SD and refocus recovery evidence in `WORKFLOW_IMPLEMENTATION_V1.md`; no model evidence. |
| F-02 | Focus / input routing | Browser review form plus Writer anchored comment; select anchor → form transaction → add comment | Add `Review note 482` to the selected `Review anchor` and save | Submit case `CASE-901` with decision `APPROVE` exactly once | Saved FODT annotation text/name/end and intact anchor/guard; private Browser payload and revision=1 | Reacquire Writer, reselect anchor, then add comment | **Scripted Guest validated (one bounded run/control):** Solo A/B PASS, MA-ID joint PASS, naive MA-SD FAIL with A's comment keystrokes routed while Chrome was active and Browser revision 3, recovery MA-SD joint PASS. Artifacts `f02-{solo*,maid,masd*}-20261001-r01`; MA-ID is the one matching `r01`. Repeated Browser revisions after A's wrong-target actions are observed; the exact triggering key is not isolated. |
| C-01 | Clipboard state | Writer + Calc; plain-text copy → interruption → paste | Transfer exact assigned text | Independently transfer B's text to its target | Exact saved destination content, guard integrity and clipboard observer sequence | Reacquire source, recopy and paste | **Scripted validated** under historical fixed fixture; no Qwen evidence. See `CLIPBOARD_001_STATUS.md`, `MECHANISM_VALIDATION_ROUND1.md`. |
| C-03 | Clipboard state | Calc rectangular range copy/paste plus Writer paragraph copy | Transfer the exact 2×2 table range | Duplicate the assigned Writer paragraph | Full Calc matrix, Writer content/guards, clipboard payload digest and GUI target | Reacquire Calc source and recopy range | **Scripted validated**: Solo A/B, MA-ID, naive MA-SD and recopy recovery in `WORKFLOW_IMPLEMENTATION_V1.md`; no Qwen evidence. |
| C-02 | Clipboard state | Browser → Writer hyperlink; Browser URL selection/copy → Writer link dialog, while B copies/submits another URL | Set visible label `Reference link` to exact href A and save | Submit exact URL B in Browser exactly once | Saved ODF `<text:a>` label and `xlink:href` checked independently; Browser payload/revision and guard exact | Recopy Source A and replace hyperlink href | **Scripted Guest validated (one bounded run/control):** Solo A/B PASS, MA-ID joint PASS, naive MA-SD A fails/B passes with clipboard digest changing A→B before paste into Hyperlink URL field, recovery MA-SD joint PASS after recopy. Artifacts `c02-{soloa,solob,maid-r02,masd,masd-recovery}-20261001-r01` except MA-ID is `c02-maid-20261001-r02`. `c02-maid-...-r01` is an infrastructure-invalid attempt (wrong provider image), preserved and excluded. |
| A-01 | Application context (candidate family) | One Chromium top-level window, two tabs/forms; switch page context inside same app | Submit the exact value to tab A | Submit the distinct exact value to tab B | Per-tab private submission/revision and tab-target event stream; stable top-level X11 window ID | Re-select own tab, observe, submit | **Scripted Guest validated**: Solo A/B, MA-ID, naive MA-SD and tab-recovery evidence in `MECHANISM_VALIDATION_ROUND1.md` / `WORKFLOW_SUITE_V2.md`; no Qwen evidence. Keep only as distinct from Focus while same-window/tab evidence remains reproducible. |
| A-02 | Application context (candidate family) | One Chromium tab and URL; select in-page record → edit → commit | Change record A only | Change record B only | Per-record values/revisions, selected-record events; stable X11 window/tab/URL | Reselect own record, observe, commit | **Scripted Guest validated**: five bounded Guest runs (Solo A/B, MA-ID, naive MA-SD, recovery), with same window/tab/URL and a misapplied commit to B; see `WORKFLOW_SUITE_V2.md` A-02 report section. No Qwen evidence. |

### Counts and evidence boundary

- Frozen inventory: **8 fixed templates** across 3 families (Focus 3, Clipboard 3, Application Context 2).
- Fresh real-Guest C-02/F-02 controls this phase: 11 episode attempts, including one invalid C-02 MA-ID startup attempt. Ten valid runs completed with reset and provenance; C-02 MA-ID r02 is valid, r01 is retained as infrastructure invalid. All outcome counts above are per single episode, not aggregate performance claims.
- Scripted tasks are not model-agent evidence. Only F-01 has historical Qwen paired evidence among these templates; it predates the current harmonized runner and is labeled legacy.
- Modal remains paused. No shared filesystem/backend mechanism is in V1 core. MA-ID and MA-SD task-relevant fixtures are equivalent; physical filesystem sharing is not a requirement.

## Task instance expansion gate

Use `TASK_INSTANCE_GENERATION_PLAN.md`. An instance must freeze meaningfully different task content, target objects, initial state and oracle under the same operation graph. Seed, filename, text token, layout, coordinates, schedule and repeats alone do not count. Generate only after a template's setup, Solo A/B, MA-ID, naive MA-SD, explicit recovery, reset and provenance controls pass. Start with three reviewed fixed instances per template and oracle positive/negative tests; then decide whether the remaining 25/template expansion is justified. The target 200–300 fixed instances is a plan: **zero generated under that plan so far**.

## Qwen pilot

`QWEN_PILOT_PLAN.md` remains **design only**. Keep the first pilot to existing representatives F-01, C-01 and A-01. Use OSWorld Qwen3VLAgent + Qwen3-VL-30B-A3B without changing prompts, parser, model, goal or evaluator; A6000 Guest, 4090 inference. Run each Actor Solo first, then MA-ID and MA-SD under matched fixture/schedule/budget. Permit autonomous observation and recovery. Stop shared conditions if either Solo is infeasible. Save action/screenshot trajectory, focus/tab/clipboard evidence, final oracle, reset and provenance. Current phase ran no Qwen experiment.

## Reproduction and artifact index

Canonical code: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk` on branch `v0`. A6000 run artifacts: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-expansion-v1/`. Each episode has `report.json`, `events.jsonl`, `provenance.json`, `resource-events.jsonl`, screenshots, saved final state and reset result. C-02/F-02 command form:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
scripts/run_browser_writer_workflows_v1.sh \
  --template C-02 --condition ma_sd --run-id UNIQUE_RUN_ID \
  --artifact-parent /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-expansion-v1
```

Condition choices: `solo_a`, `solo_b`, `ma_id`, `ma_sd`; add `--recovery` only for explicit MA-SD recovery. Always use a new run ID. Use the wrapper: it sources `scripts/a6000_env.sh` and supplies the pinned A6000 provider/Guest paths. A direct invocation that omits that environment selects the wrong upstream default provider image and yields an invalid infrastructure timeout; the failed C-02 MA-ID attempt is retained as `c02-maid-20261001-r01`.
