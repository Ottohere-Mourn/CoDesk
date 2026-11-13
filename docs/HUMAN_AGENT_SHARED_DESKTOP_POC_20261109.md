# Human–Agent Shared Desktop PoC — 2026-11-09

## Scope and implementation

This is a **single-task runnable PoC**, not a finished benchmark. Work was isolated from the pre-existing checkout:

- Worktree: `/home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109`
- Branch: `codex/human-agent-shared-poc-20261109`
- Base commit: `976024720adba9a6087ec4c8526f26be0c8555db`
- Results: `/mnt/raid1/mjh/Projects/codesk-human-agent-poc-20261109/results/`
- Guest base image: `/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2`

The User Actor is scripted and uses the existing `ScriptedPolicy`. The model Agent uses the existing Codex CLI Harness and the existing `desktop_tools.py` GUI MCP. No new model loop, GUI driver, or runtime was implemented. The scripted User and direct replay Agent actions log a unified append-only event stream (`events.jsonl`) with actor/episode/run IDs, wall/monotonic times, action start/end, input, expected app, active window before/after, screenshot path, status, error, and lock wait. Per-action screenshots and focus-change screenshots are retained.

Tasks, from deterministic initial fixtures:

- **User / Writer:** append `Status verified: PO-441 completed.` as the final non-empty line of `service-report.txt`, save.
- **Agent / Calc:** in `budget.xlsx`, set C2 (Router quantity) to `3`, E2 to `Approved PO-441`; preserve the other specified cells and save.

Oracles read the saved files from the Guest (report text and XLSX XML), not from the action trace. The independent mode uses two concurrent OSWorld Guests from the same immutable base. XLSX ZIP entries now have fixed timestamps so byte hashes are comparable across Guests.

## Environment and safety

- Docker container launch and actual QEMU/KVM acceleration worked (`-machine pc,accel=kvm`); Guest GUI became responsive, reset was separately verified using a Guest-side sentinel that disappeared after reset.
- All new overlays, screenshots, traces, and run results are on RAID at the path above. Existing overlays/runs were not deleted.
- Earlier valid Case 2/3 measurements: root filesystem ~98% used with ~36 GB free; RAID ~1.2 TB free; no GPU used. Guest startup/GUI readiness then took ~2–3 minutes per Guest/condition. On 2026-11-09 Case 4 setup retries took ~9–10 minutes to reach the desktop, while unrelated concurrent workloads remained active; all artifacts were written to RAID. Root later reached 99% used (~33 GB free), swap remained full, and RAID had ~1.2 TB free. No GPU was used by this PoC.
- The OSWorld venv initially lacked the optional `mcp` package, so Codex could not expose desktop tools. Installed/pinned `mcp==1.16.0` with compatible `starlette<0.48` and `PyJWT<2.9`; `pip check` is clean. Codex CLI `0.155.0` was run using Node `22.23.1`.
- The first bare `https://api.haogpt.net` attempt POSTed to `/responses` and received HTTP 405. The small real-Agent comparison therefore used the previously validated fallback `https://docode.cc/v1` (Responses API). The API key was provided to the remote process through no-echo stdin only; it is not present in the repository, config snapshots, or result files.

## No-model controls

All times below are end-to-end condition elapsed; “Actor time” excludes Guest startup.

| Mode | Result | Actor work / observed cost | End-to-end |
|---|---|---:|---:|
| User-only | PASS | User 5 GUI actions, 12.3 s; 0 misroutes, 0 rework | 206.9 s |
| Agent-only replay | PASS | Agent 11 actions, 21.2 s; 0 misroutes | 179.8 s |
| Independent replay | PASS / PASS | User 5 actions, 11.3 s; Agent 11, 22.8 s; initial fixture equivalence = true | 180.0 s |
| Shared replay (open-loop) | **Both failed** | User 5 actions, Agent 11; Agent had 10 focus-mismatch actions; no API/action exceptions | 175.5 s |
| Shared + PerActionLock replay | **Both failed** | User waited 1.53 s; Agent 2.99 s total lock wait | 177.3 s |

The Shared replay shows genuine input interference in the *scripted natural/open-loop run*: Agent keystrokes went to Writer, corrupting the report, while the Calc workbook stayed unchanged. In Shared+PerActionLock, simultaneous tool calls were serialized, but the lock did not cover a multi-action task or think-time: the User’s line landed in Calc C2 and the Agent’s values landed in C3/E3. Thus this lock is a call-level mutex, not a task/transaction lock.

A first Independent attempt compared raw XLSX hashes and reported false because ZIP timestamps varied. After fixing the fixture writer to use deterministic ZIP metadata, the rerun had equal SHA-256 hashes for both initial fixtures and both oracles passed. The failed/initial run is retained; use `no-model-v10/independent-deterministic` as the valid Independent result.

## Forced focus probe and recovery

Path: `no-model-v10/forced-probe/`. This is explicitly labeled a **forced mechanism probe**, not a natural-interference measurement.

- Fixed replay: a probe Agent moves focus from Writer to Calc between the User’s navigation and input. User Oracle fails; one focus change was recorded.
- Recoverable User: it only checks its own visible active-window title (no evaluator or other Agent state), detects the wrong app, refocuses Writer, and achieves the User Oracle after one recovery (5.12 s recovery time; total User Actor time 15.17 s).
- Important limitation: the text typed before recovery remains as a side effect in Calc A2. Recovery restores the User’s report but does not undo collateral damage to the other document.

## Small GPT-6-Sol Codex comparison

All four runs used Codex CLI 0.155.0, the same GPT-6-Sol endpoint, same task version, GUI MCP permissions, and `--budget 10` GUI calls.

| Mode | User Oracle | Agent Oracle / Codex status | Calls / Actor time | Total |
|---|---|---|---:|---:|
| Agent-only | n/a | PASS / done | 9 / 124 s | 278.5 s |
| Independent | PASS | PASS / done | 5 User actions; 9 Agent calls / 9.7 s User, 82 s Agent | 238.4 s |
| Shared | PASS | **FAIL / max_steps** | 5 User actions; Agent consumed 10-call budget / 9.3 s User, 142.1 s Agent | 294.4 s |
| Shared + PerActionLock | PASS | PASS / done | 5 User actions; 9 Agent calls / 10.7 s User, 96 s Agent; lock wait User 1.21 s, Agent 0.85 s | 245.8 s |

Interpretation is deliberately narrow: this is one episode per condition. In this natural model schedule, the scripted User finished before the model changed focus to Calc, so the model Shared run did **not** show a User task loss. The model Shared Agent used its ten-call budget without saving/finishing; in the Independent and Locked conditions it finished in nine calls. One trial is not evidence that the lock caused the difference. The no-model Shared runs are the clearer direct interference control; the Codex runs demonstrate the real GUI MCP/Guest/Oracle path and show the need to model natural action timing and think time.

## Artifacts

Each run directory contains `run.json`, `events.jsonl`, screenshots/action logs, `resource-ledger.jsonl`, and the run-owned overlay(s). Successful main paths:

- `no-model-v8/user-only-fixed/`
- `no-model-v9/agent-only-replay/`
- `no-model-v10/independent-deterministic/`
- `no-model-v10/shared-replay/`
- `no-model-v10/shared-lock-replay/`
- `no-model-v10/forced-probe/`
- `codex-v2/agent-only/`
- `codex-v2/independent/`
- `codex-v2/shared/`
- `codex-v2/shared-lock/`

Invalid infrastructure attempts are also retained under `codex-v1/` (missing MCP dependency/import issue and initial endpoint path error); do not count them as Agent failures.

## Reproduction

Use the OSWorld venv and existing checkout. Do not put API keys on the command line or in a result/config file.

```bash
cd /home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109
export PYTHONPATH=/home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109:/home/mjh/Projects/Shared-Workspace-Benchmark-V0:/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1
PY=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python
$PY -m oscombo.human_poc --mode shared --agent replay --out /mnt/raid1/mjh/Projects/codesk-human-agent-poc-20261109/results/repro/shared
```

For a Codex run, set `OPENAI_API_KEY` in the process environment via a secret manager/no-echo stdin, set `CODEX_NODE_BIN=/home/mjh/.nvm/versions/node/v22.23.1/bin` and `CODEX_CLI_BIN=/home/mjh/.cache/codesk-codex-0.155.0-20261108/node_modules/.bin/codex`, then run the same command with `--agent codex --budget 10 --timeout 600 --model gpt-6-sol --base-url https://docode.cc/v1`.

## Limits and next work

This validates a runnable platform path, not a benchmark result: one small task pair, one scripted User policy, one run per arm, and one Codex episode per arm. Active-window polling is 0.5 s and can miss very brief focus changes; action-level screenshots/Oracle outcomes complement it. PerActionLock covers one complete GUI call plus its screenshot, not the GUI workflow or model inference.

Next: add several ordinary multi-step User workflows, define richer User cost/recovery measurements, and compare fixed replay with an online-but-private User policy. Keep forced probes separately labeled from natural open-loop trials. Re-run multiple episodes only after task timing and measurement reliability are established.

## Five-case Linux extension (2026-11-09)

After the minimum PoC, a machine-readable casebook was added at docs/HUMAN_AGENT_CASEBOOK_LINUX_V1_20261109.md with five distinct shared-state mechanisms: (1) cross-app focus routing, (2) clipboard handoff, (3) same-app active-cell selection drift, (4) document-global undo history, and (5) modal PDF export transaction versus foreground Writer input. The cards specify ordinary user/Agent task pairs, shared state, separate task oracles, independent controls, potential user harm, and a forced-probe boundary.

Case 1 has the earlier GUI-only/model smoke evidence. Case 3 has one valid no-model replay in each of five conditions. Case 2 v1 was replayed in five conditions, but the v2 target-refocus change still needs a full rerun. Cases 4/5 have code/design only; Case 4 Guest setup repeatedly failed before actor execution, so neither is validated. Do not count these as passed benchmark cases. The current setup blocker and retained invalid artifacts are documented in the casebook. Machine-readable cards are in oscombo/human_casebook.py and are listed with:

    python -m oscombo.human_casebook --json

Static casebook tests check the five unique mechanism labels and minimum per-case protocol fields. Case 4 setup debugging created several retained Guest overlays on RAID, but no model/API call was made. Casebook v3–v9 were setup-invalid; v10 ran a scripted sequence but screenshots showed Writer was unresponsive and the actions were not reliably delivered. Do not count v10's raw final-state Oracle PASS.
