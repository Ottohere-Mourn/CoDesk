# MECH-05 TRACK-CHANGES-MODE — case card (2026-11-18)

## Status
- Task/oracle version: mech05 0.1.2 (instructions 0.1.1; Oracle active-text fix 0.1.2).
- Current state: 5 parser tests pass; real Guest scripted controls pass; one valid GPT-6-Sol triplet is complete. It is NOT a PASS/FAIL/FAIL qualifying case: MA-ID PASS/PASS, Shared A FAIL/B PASS, Shared+Lock PASS/PASS.
- This is a shared Writer document-mode case; it replaces the old `SESSION-LEASE` draft, which overlapped the existing portfolio's session-sticky browser tasks.

## Independent actor goals
- **Actor A — auditable regulatory correction:** change `Approval boundary: Pilot access is limited to two named reviewers.` to `Approval boundary: Pilot access is limited to five named reviewers.` in LibreOffice Writer, with Record Changes enabled; leave the revision unaccepted.
- **Actor B — finalized contact correction:** change `Escalation contact: Pending confirmation.` to `Escalation contact: compliance-ops@example.org` as normal final text, with Record Changes disabled before the edit.
- The control line must remain exactly `Control text: Preserve exactly TRACE-ONLY-77.`
- Tasks are complementary: a common end state exists with A's exact revision tracked and B's finalized contact untracked. No record quota, deletion or other zero-sum coupling exists.

## Shared state and evidence boundary
The shared state is Writer's document-level Record Changes mode, not clipboard, window focus, selection, undo, or active record. The Guest ODT Oracle parses `content.xml`, checked change-region metadata and `text:change-start`/`text:change-end` markers. A passes only if the new approval wording is present and the old approval wording appears as a tracked deletion paired with a tracked insertion. B passes only if the exact contact value is present as plain text outside tracked insertion ranges. The Guest-only controls exercise the visible `Edit > Track Changes > Record` menu. Evaluator output is not available to either task Actor.

## Fixture and reproducibility
- Fixture: `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets/mechanism_expansion_v1/mech05/access-review-draft.odt`
- SHA-256: `bf01e60c60a53fb18c27f478bb26aa2ee6ccac8451d9417a5d7e4dd63ba22721`
- Generate from repo root: `python tasks/mechanism_expansion_v1/build_mech05_assets.py <output.odt>`
- Task classes: `tasks/mechanism_expansion_v1/task_mech05a.py` and `task_mech05b.py`.
- Oracle/tests: `tasks/mechanism_expansion_v1/mech05.py`, `tests/test_mech05.py`.
- Guest control: `scripts/run_mech05_controls.py` (uses OSWorld-V2 venv; overlay/results/assets on RAID).

## Control outcomes
Successful real Guest run: `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech05-guest-control-20261118T105119Z-509781/`.
- Positive sequential control: Actor A's exact edit is a tracked insertion/deletion pair (2 change regions); B's contact is ordinary text; both role Oracles PASS; control line preserved.
- Fixed interleave negative control: A enables recording, B disables the shared mode and commits the plain contact, then A performs the pending approval replacement. Visible words are right but A's modification is untracked and A Oracle FAILs; B still PASSes. This is an intentionally scheduled mechanism control, not a natural model Shared result.
- Resource ownership: the Guest container in this run was destroyed; `sharp_bhabha` was not stopped.

## Retained invalid probes
- `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech05-guest-control-20261118T103112Z-500976/`: incorrect `Ctrl+Shift+E` toggle attempt. Both strings were edited, but no tracked-change metadata existed; positive control correctly failed and run was marked invalid.
- `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech05-guest-control-20261118T102917Z-500198/`: host system Python lacked the intended OSWorld dependency `gymnasium`; no Guest was created. Invalid setup probe, not task evidence.
- A separate host-headless UNO probe (not Guest/model evidence) confirmed LibreOffice 7.3's `RecordChanges` property and the ODT marker representation; both role Oracles passed on the crafted tracked-A/plain-B document.

## GPT-6-Sol MA-ID attempt v0.1.0 (invalid as a qualifying tuple, retained)
Run group: `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech05-sol-triplet-20261118T110116Z-515410/ma-id/result.json`.
- Both Agents returned `status=done` in 10/9 GUI calls; A=0, B=1; no API/Guest error. A's visible phrase was correct but its ODT contained no tracked-change regions; B's normal contact text was correct. This is a **valid task-level MA-ID miss**, not an infrastructure-invalid run. It blocks Shared/Shared+Lock for v0.1.0.
- A did open `Edit > Track Changes > Record` and later entered the right words, but apparently did not confirm the Record checkbox state; no evidence supports treating this as mechanism interference.
- v0.1.1 therefore explicitly requires inspecting the Record check state and setting it in the required direction before typing. This is task-instruction repair, not changing fixture/oracle or injecting an arm-specific obstacle. The old run remains unchanged.

## Next gate
Before any triplet, run MA-ID with the same version/permissions/budget and require both Actors `status=done` plus each role Oracle=1. Then run Shared and Shared+Lock without changing task/fixture/budget. If mode is correctly reset before every edit, count recovery as PASS. A timeout/API-invalid attempt is not a task FAIL. Model work is currently deferred until GPT-6-Sol streaming latency is reliable enough to avoid repeating the MECH-02 invalid long runs.


## GPT-6-Sol triplet v0.1.2 / protocol 0.1.2 (2026-11-18)

- Baseline reference: /mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech05-sol-triplet-20261118T113640Z-533632/ma-id/result.json. Budget 16. A/B Oracle=1/1, both terminal turn.completed; A status=max_steps at 16 GUI calls, B done at 11. We accept max_steps only as a task-completion status when there is an explicit terminal Codex response, no error, and the task Oracle is 1. This clarifies harness status semantics; the outputs and criteria are retained in the run.
- Shared and Shared+Lock: /mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech05-sol-triplet-20261118T114821Z-539140/. Both arms used the same task 0.1.2, model, tools, permissions, 16-call budget, and task fixture. The arm directory contains ma-id-reference.json linking the baseline.
- Results: MA-ID 1/1; Shared A=0/B=1 with both terminal responses and no API/Guest errors; Shared+Lock A=1/B=1, action_lock=true, both status=done. Shared A failed with approval_text_correct=false and approval_change_tracked=false; B's contact was plain/final. All tracked input traces reported the Writer window before/after, but no X11 focus-misroute flag. A's final screenshot still showed the approval line selected and unchanged; its final answer said it could not complete/save the tracked replacement. This is concurrent Shared task failure, but the available event trace does not prove that B specifically toggled A's Record mode at the critical instant. Treat mechanism attribution as suggestive, not conclusive.
- Per-arm metrics: MA-ID 594.4s, 16/11 calls, 367,571 input tokens; Shared 501.0s, 16/16 calls, 469,854 input tokens; Shared+Lock 642.8s, 15/12 calls, 361,166 input tokens. Total 1,198,591 input tokens. All three arms' logs/events/screenshots/results are retained. Lock log has 24 events; for each GUI call lock_wait_s and lock_held_s are recorded.
- Conclusion: useful replication of shared Writer contention and evidence that per-action locking rescued this run; not a qualifying target case because Shared+Lock passed. Do not count the Shared miss as a proven Track Changes-mode race without direct toggle trace. Do not rerun solely to hunt for a lock failure.
