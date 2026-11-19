# MECH-04 — Calc Range Drift Case Card (2026-11-18)

## Mechanism and realistic task
Two actors update a shared Calc QC handoff ledger. Actor A sets B-5108 (Sterile tubing) Retest Flag to Recheck. Actor B sorts the table by Next Count ascending, then finds B-5112 by stable batch ID, sets Last Verified By to RM, and saves. The shared state is the active cell/range and the row order after sorting—not an activity-panel/current-record pointer, clipboard, focus switch, or Undo stack.

## Fixture and Oracle
- Fixture: /mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets/mechanism_expansion_v1/mech04/range-drift-log.ods
- SHA256: ccea29904da73a3274ba1177c89b35cffc35c4468e849bdd3efb2a95894af2b1
- Task version: 0.1.0; wrappers task_mech04a.py and task_mech04b.py. Oracle identifies rows by Batch ID, confirms all rows/columns, requires exact targets, and verifies date order ascending for Actor B. It does not depend on fixed row positions.
- Tests: 3 passed. Scripted Guest positive and fixed interleave controls passed. Positive A/B PASS/PASS; negative control shifts the active selection before typing and damages the header, causing both role Oracles to fail. Report: /mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech04-guest-control-20261118T101554Z-494308/report.json. This is mechanism validation by fixed schedule, not natural model evidence.

## GPT-6-Sol model pilot
Run group: /mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech04-sol-triplet-20261118T121209Z-550215/
- MA-ID: A/B both PASS; 7/15 GUI calls, 408.1 sec, 278,251 input tokens.
- Shared: A/B both FAIL (Oracle 0/0), 15/15 GUI calls, 675 sec, 420,454 input tokens. Actor B ended by declaring the sort/edit controls disabled; no API/Guest error. A claimed success but its Retest Flag target failed. Both agents returned terminal responses.
- Shared+Lock: A PASS / B FAIL, 8/16 GUI calls, 500.3 sec, 315,539 input tokens, action_lock=true. Actor B's last screenshot shows an ascending table and RM visibly entered for B-5112, but it had not saved; the final message explicitly says it could not save. The 16-call cap was exhausted before Ctrl+S. This is a real task failure, but not evidence that locking failed to protect a multi-action sort/edit operation.
- Lock telemetry: 20 events; total wait 2.083 sec (max 1.103 sec); total held 50.077 sec (max 4.283 sec). Actor logs report no focus-misroute flag. All model results and screenshot trails are retained. Audit: run-group pilot-audit.json.

## Judgement
This run has joint MA-ID PASS / joint Shared FAIL / joint Shared+Lock FAIL if joint success requires both actors. However, do NOT count it as a mechanism-qualified PASS/FAIL/FAIL case: the lock-arm miss is explained by an unsaved edit at the GUI-call cap, not demonstrated residual competition. The shared arm has genuine task-level failure and a same-sheet concurrent interaction, but the current event log does not isolate which cross-actor action caused the failures. Classify as exploratory evidence only. No repeat was run merely to chase a desired outcome.

## Reproduction
- Controls: scripts/run_mech04_controls.py
- Model triplet: scripts/run_mech04_sol_triplet_secure.sh; budget 16 per actor, model GPT-6-Sol, GUI MCP, same task version and fixture across arms.
- Lock-only completion: scripts/run_mech04_lock_only_secure.sh
- OSWorld venv: /home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python. Overlays/logs are on RAID; per-run Codex home is in /run/user/1002 tmpfs to avoid further root-disk growth.
