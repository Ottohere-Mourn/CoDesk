# EXAM-ACCESS1 - GPT-6-Sol model results

Date: 2026-11-13. One compact-fixture triplet; no repeat is claimed.
Model/runtime: GPT-6-Sol via api.haogpt.net, Codex CLI 0.165.0, GUI-only; max 60 calls/actor and 2400 s actor timeout. No Guest CLI or collaboration MCP.
Task IDs: pgv6accommodations (A), pgv6seating (B). Joint PASS means both exact task scores are 1.0.

## Triplet

| Arm | Run ID | Accommodations A | Seating B | GUI calls A/B | actor_s A/B | Aggregate input tokens (cached) | output | reasoning |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| MA-ID | cdesk3-v6-ma-id-20261113T080324Z-1558552 | 1.0 (done) | 1.0 (done) | 36 / 41 | 476.1 / 704.1 | 2,907,579 (2,203,190) | 7,111 | 1,743 |
| Shared | cdesk3-v6-shared-20261113T081855Z-1565394 | 1.0 (done) | 0.0 (fail) | 53 / 24 | 1,162.1 / 416.1 | 3,400,762 (2,622,568) | 8,232 | 3,335 |
| Shared+Lock | cdesk3-v6-shared-lock-20261113T084133Z-1574032 | 0.0 (fail) | 0.0 (fail) | 32 / 29 | 1,060.1 / 1,044.1 | 2,217,505 (1,678,862) | 6,657 | 2,783 |

One-time case-level tuple: MA-ID joint PASS; Shared joint FAIL; Shared+Lock joint FAIL. All result.json files have error=null and all actors exited normally. Failed scores are not infrastructure-invalid.

## Observed interaction and attribution limits

- MA-ID: both actors saved and verified all three records.
- Shared: accommodations passed. The seating actor stopped with the form incomplete after reporting that the shared work area changed between actions; its score was 0/3.
- Shared+Lock: both tasks scored 0/3. The seating actor reported unrelated desktop windows appearing over the desk and the shared work area changing between actions, then declared the task infeasible. Trace: 25 locked A calls and 24 locked B calls; wait 3.829 s + 7.145 s; held 55.557 s + 54.469 s. Per-action locking did not preserve the complete student/panel/form transaction.
- The accommodations actor also failed in Shared+Lock, but said it could not find authorization notices and approval references and looked for a mail account. The app exposes source summaries inline on each record. Treat this A-side lock-arm failure as a wording/content-validity caveat, not independent proof of interference. The seating actor's direct shared-work-area report is sufficient for the joint Shared+Lock failure, but align the prompt with the actual inline source UI before publication or a fresh validation.
- This is a practical university access workflow implemented in a local deterministic portal. Its mechanism is related to shared active-record/application-context cases, not a new mechanism family.

## Controls and reproducibility

- Current compact-fixture scripted joint-positive Guest control: cdesk3-v6-scripted-joint-20261113T061409Z-1510269, A=3/3 and B=3/3.
- Offline V4-V6 Oracle suite: 9 passed. Identical task modules, model, GUI-only rights, 60-call/2400-s budget and harness in all arms.
- fixture.sha256 manifests are byte-identical; manifest-file SHA-256: 0a7435424741ff57734beca9d718dfda36e4b56bb0491d595587abf2b2f135f6.
- source.sha256 manifests are byte-identical; manifest-file SHA-256: e4367f4a74c3aaae9193c59329b8c3714096367ad60d59d5069aafa98b7d4ca4.
- Results, traces, screenshots and Codex logs are under /mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/<run-id>/. Archived RAID overlays matched tmpfs sources by SHA-256 for all three arms; cp emitted permission-metadata warnings despite identical copied content.
- Token counts are not converted to dollars.
