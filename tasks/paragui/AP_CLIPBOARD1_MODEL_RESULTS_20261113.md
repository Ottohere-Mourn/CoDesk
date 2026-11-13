# AP-CLIPBOARD1 - GPT-6-Sol model results

Date: 2026-11-13. One compact-fixture triplet; no repeat is claimed.
Model/runtime: GPT-6-Sol via api.haogpt.net, Codex CLI 0.165.0, GUI-only; max 60 calls/actor and 2400 s actor timeout. No Guest CLI or collaboration MCP.
Task IDs: pgv5invoices (A), pgv5expenses (B). Joint PASS means both exact task scores are 1.0.

## Triplet

| Arm | Run ID | Invoices A | Claims B | GUI calls A/B | actor_s A/B | Aggregate input tokens (cached) | output | reasoning |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| MA-ID | cdesk3-v5-ma-id-20261113T072336Z-1538703 | 1.0 (done) | 1.0 (done) | 25 / 26 | 486.1 / 682.1 | 1,685,213 (1,313,137) | 4,269 | 602 |
| Shared | cdesk3-v5-shared-20261113T073931Z-1545618 | 0.0 (fail) | 0.0 (fail) | 46 / 22 | 442.1 / 442.1 | 1,169,038 (798,671) | 8,675 | 5,211 |
| Shared+Lock | cdesk3-v5-shared-lock-20261113T074956Z-1550241 | 1.0 (done) | 0.0 (fail) | 56 / 38 | 608.1 / 562.1 | 1,617,998 (1,246,507) | 8,706 | 4,592 |

One-time case-level tuple: MA-ID joint PASS; Shared joint FAIL; Shared+Lock joint FAIL. Each result has error=null and Codex exited normally; these are model task outcomes, not API/Guest/evaluator-invalid runs.

## Observed interaction and limits

- MA-ID: each actor entered and verified its two finance rows, including the exact copied source references.
- Shared: the invoice actor reported values landing in the wrong AP fields and the visible work area switching to staff reimbursements. The claims actor reported that its form changed to supplier invoices and text was routed into that form. Both exact oracles scored 0/2.
- Shared+Lock: invoices passed; the claims actor said the desk repeatedly reverted to invoices during expense entry and stopped rather than save unverified values. Claims scored 0/2. Trace telemetry: 54 locked A calls and 35 locked B calls; wait 11.127 s + 8.639 s; held 122.938 s + 79.720 s. Per-action locking serialized calls but did not hold the shared panel/form context over a complete workflow.
- This is direct shared-work-area/focus evidence. It does not prove clipboard-buffer overwrite: no clipboard payload telemetry showed one actor replacing another's copied reference. Count it as a shared-desktop finance workflow outcome, not a validated clipboard-only mechanism.
- The fixture is a local deterministic finance portal, not a commercial AP product. Before publication, either add direct clipboard observability or narrow the claim to shared-panel/focus interference.

## Controls and reproducibility

- Current compact-fixture scripted joint-positive Guest control: cdesk3-v5-scripted-joint-20261113T061059Z-1508791, A=2/2 and B=2/2.
- Offline V4-V6 Oracle suite: 9 passed. Identical modules, model, GUI-only rights, 60-call/2400-s budget and harness in all arms.
- fixture.sha256 manifests are byte-identical; manifest-file SHA-256: 6551f15d2c2f0d7fe34eb67a495ed2b187ab8282d70d064d31509383b1c65dc6.
- source.sha256 manifests are byte-identical; manifest-file SHA-256: e4367f4a74c3aaae9193c59329b8c3714096367ad60d59d5069aafa98b7d4ca4.
- Results, traces, screenshots and Codex logs are under /mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/<run-id>/. Archived RAID overlays matched tmpfs sources by SHA-256 for all three arms; cp emitted permission-metadata warnings despite identical copied content.
- Token counts are not converted to dollars.
