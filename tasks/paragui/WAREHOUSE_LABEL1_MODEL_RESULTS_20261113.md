# WAREHOUSE-LABEL1 — GPT-6-Sol triplet and control audit (2026-11-13)

## Decision

**No-go for the required PASS / FAIL / FAIL tuple.** GPT-6-Sol completed all ten print jobs in all three arms. Shared state is real (one stock profile is captured at job submission), and fixed GUI interleaving can make one job wrong, but the model noticed/managed the profile well enough to pass in both shared conditions. Keep the case as an exploratory workflow/control, not a qualified case; do not tune the prompt or inject a race to force model failure.

## Protocol and validity

The pair is an inventory clerk printing five 2x1 bin labels and a dispatch coordinator printing five 4x6 parcel labels on the same Riverside Logistics station. Each order has an exact copy count. Jobs and roles are disjoint; a wrong-profile job can be corrected by reprinting; both task oracles can be simultaneously satisfied. All model arms used the same two tasks, fixture, task source, reset, GPT-6-Sol, Codex CLI 0.165.0, high effort, GUI-only, and 45 tool-call cap per actor. MA-ID used two isolated guests; Shared and Shared+Lock each used a single Guest/session. API, reset, and evaluator were valid in all arms (`error=null`, `state_readable=true`).

The `fixture.sha256` files are identical across the model arms (app, expected state, seed DB); `source.sha256` files are identical too. The runner compared each installed task module to the branch source before starting. Every result uses the same task IDs and budget.

## Controls

| Control | Run ID | Result / meaning |
|---|---|---|
| Setup-only Guest smoke | `cdesk3-v2-guest-setup-20261112T155910Z-1091042` | Real Guest reset, one Chrome tab, local app startup and teardown succeeded; zero-action tasks intentionally score 0. |
| GUI scripted joint positive | `cdesk3-v2-scripted-joint-20261112T160814Z-1096607` | Both batch oracles 1.0 in the same Guest after scripted GUI clicks, typing, and submits. |
| GUI fixed-interleaving mechanism control | `cdesk3-v2-scripted-mechanism-control-20261112T161155Z-1098342` | A scripted Bin-2x1 → Parcel-4x6 profile switch between seeing and submitting B-104 made that job capture the wrong stock. Bins scored 0.8; parcels 1.0. This is a deliberately scheduled mechanism control, **not** natural/model evidence. |
| Earlier authoring attempt | `cdesk3-v2-scripted-joint-20261112T160418Z-1094753` | Script typo made B enter on the first five (bin) rows; score 1.0/0.0. Preserve as a harness-authoring attempt, exclude from task/model conclusions. |

Offline oracle controls also confirm all ten correct jobs let both score 1.0, wrong stock or copy count fails the corresponding item, and the station profile at submission time is what gets stored.

## Model results

| Arm | Run ID | Bin / Parcel score | GUI calls A/B | Input tokens (cached) | Output tokens | Total wall time |
|---|---|---:|---:|---:|---:|---:|
| MA-ID | `cdesk3-v2-ma-id-20261112T161600Z-1099988` | 1.00 / 1.00 | 18 / 19 | 878,505 (732,636) | 3,008 | 441.9s |
| Shared | `cdesk3-v2-shared-20261112T162411Z-1104670` | 1.00 / 1.00 | 37 / 42 | 2,557,694 (2,298,189) | 7,710 | 890.5s |
| Shared+Lock | `cdesk3-v2-shared-lock-20261112T164011Z-1111210` | 1.00 / 1.00 | 34 / 37 | 2,179,946 (1,957,149) | 6,089 | 805.2s |

Total: 5,616,145 input tokens (4,987,974 cached), 16,807 output tokens, 2,137.6 summed wall seconds. Shared and Shared+Lock have +42 and +34 combined GUI calls relative to MA-ID, and higher elapsed time, but cost overhead is not task failure. Shared+Lock had 60 mutating calls under the action lock; lock wait summed 9.027s and lock-held time 140.323s. Both actors finished under the same 45-call ceiling.

## Interpretation and limits

The control proves the station-wide profile is an actual shared setting and can affect a submitted job. The model triplet instead shows recoverability: all profiles/copy counts were correct in Shared and Shared+Lock, so this case does not meet the benchmark target. The task prompt explicitly told agents to verify the stock profile before each print; that is operationally sensible but gives a strong recovery cue. Do not remove the cue or add an arm-specific delay just to obtain FAIL. If retained in a broader workload-cost suite, report the increased interactions/time as a cost finding only.

This is a local browser simulation of a thermal-label workflow, not a physical printer/driver test. It is workflow-distinct from prior OS printer-destination troubleshooting but near warehouse inventory operations; it must not be presented as a novel underlying mechanism. The fixed interleaving is labeled separately from natural model concurrency.

## Artifacts

- Case source: `tasks/paragui/app_v2.py`, `build_v2.py`, `pg_v2.py`, `pg_v2_oracle.py`, `task_pgv2bins.py`, `task_pgv2cartons.py`, `spec_v2.md`.
- Offline tests: `tests/test_v2_oracle.py`, `tests/test_v2_setup.py`.
- Fixture assets: `/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets/v2/`.
- Runs, logs, action traces, screenshots, results: `/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/<run-id>/`.
- Guest overlay copies archived at `/mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays/<run-id>/`. `cp` warned that RAID did not preserve the source qcow chmod; the overlay file data exists. No other runs/overlays were removed.
