# EDIT-MODE1 — Scripted Controls and GPT-6-Sol Pilot Results

Updated: 2026-11-12. **Disposition: no-go for the required three-arm tuple.** The case has a valid isolated PASS and a valid Shared FAIL, but Shared+Lock recovered to full PASS. Do not count this as a qualified case.

## Frozen task and state

- Actor A: insert READY followed by a space immediately before HOLD-FOR-REVIEW in the first line.
- Actor B: replace four underscores in the reviewer-code field with AB12, using Writer's Insert/Overwrite key, without selecting text.
- Fixture: the same three-paragraph packaged ODT for all arms. The pair setup now uploads/opens it once per Guest; the second task setup checks a Guest-local marker and does not reopen the same file.
- Joint PASS terminal state is possible and both evaluators accept the other actor's untouched or correct completed line.
- Guard paragraph must remain exact. Source/runtime module parity and fixture hashes matched across the model arms.

## Cheap Guest controls (not model results)

All controls used the pinned OSWorld Guest, LibreOffice Writer, deterministic keyboard actions, and file-content oracles:

| Control | Run ID | Result | Interpretation |
|---|---|---:|---|
| Isolated pair | e1-isolated-overwrite-20261112T133041Z-1025083 | A=1.0, B=1.0 | Each task is independently GUI-solvable from the same fixture. |
| Shared, B restores Insert mode before stopping | e1-scripted-insert-20261112T132712Z-1023519 | A=1.0, B=1.0 | Negative control: with Insert mode active, the insertion leaves both lines intact. |
| Shared, B leaves Overwrite mode active; A then types at the correct caret | e1-scripted-overwrite-20261112T132346Z-1021884 | A=0.75, B=0.75 | Positive mechanism control: saved line is exactly “Release status: STATUS | READY OR-REVIEW”; the reviewer code is exactly AB12; the guard is intact. This is the expected OVR-overwrite signature. Each task's cross-line guard correctly makes the corrupted joint state non-PASS. |

Earlier setup-only attempts are retained but excluded: the first hand-written flat XML opened as raw text; a later shared setup exposed that opening/uploading the same Writer file twice raises a LibreOffice external-change dialog; and initial keyboard controls had incorrect caret placement. These were repaired before the valid controls and model arms. Their run directories are under runs/e1-controls/; they are not task-result evidence.

## GPT-6-Sol / Codex CLI 0.165.0 model triplet

All three runs were serial, GUI-only, high effort, same prompts/fixture/model/45-call-per-Actor budget/reset protocol, and had error=null. Input tokens below include cached tokens in parentheses; API credentials are not in the repository.

| Arm | Run ID | A/B oracle scores | A/B GUI calls | A/B active seconds | Total wall seconds | Input tokens (cached) | Output tokens |
|---|---|---:|---:|---:|---:|---:|---:|
| MA-ID | cdesk3-e1-ma-id-20261112T133550Z-1028541 | 1.0 / 1.0 | 4 / 6 | 94 / 114 | 295.2 | 266,103 (230,425) | 2,441 |
| Shared | cdesk3-e1-shared-20261112T134519Z-1033286 | 0.5 / 0.5 | 45 / 45 | 934 / 936 | 1,095.8 | 4,041,882 (3,682,658) | 24,013 |
| Shared+Lock | cdesk3-e1-shared-lock-20261112T140439Z-1041957 | 1.0 / 1.0 | 38 / 30 | 1,102 / 580 | 1,252.9 | 2,520,386 (2,233,114) | 14,209 |

**Interpretation.** MA-ID passed. Shared was an effective task-level failure, not an API/Guest failure: both Actors reached their call budgets and declared the shared Writer input too corrupted to finish. The final saved document in both evaluator paths had status “ABREADYHOLD-FOR-REVIEW” and reviewer field “ABab12”; the guard paragraph survived. The live action trace shows both actors manipulating the same Writer window, with interleaved Insert toggles, text entry, and undo attempts. This is a shared-input collision, but **not** the clean scripted OVR signature; do not claim the model run proved that specific sub-mechanism.

Shared+Lock passed both tasks and saved the exact joint target. Sixty modifying MCP calls carried the per-action lock; total recorded wait was 4.349 s, total held time 144.033 s, maximum wait 2.901 s. Per-action serialization plus the models' recovery was sufficient for this task. Thus the required Shared+Lock FAIL condition was not met; **EDIT-MODE1 is no-go for the requested tuple**. Keep the result as a useful control showing a lock-resolvable text-editing collision, not as one of the completed new cases.

Across the model triplet: 6,828,371 input tokens (6,146,197 cached), 40,663 output tokens, and 2,643.9 summed wall seconds (~44.1 min); no GPU was used. Guest result/log/trace/screenshots and downloaded ODTs remain on RAID under runs/triplets/<run-id>/. The runner reported permission-setting warnings when copying QEMU overlays from tmpfs; no existing run/overlay was removed. Do not claim those overlay archives are complete.

## Decision

- Strict new-case qualification count unchanged: **0/3**.
- E1's cheap controls establish the mechanism can occur, but the tested model triplet demonstrates that the supplied action lock is enough to recover.
- Do not tune the old task by adding an arbitrary barrier or hiding the mode state. Move to a materially different candidate for slot 2; preserve this pilot as-is.
