# LIBRARY-ROOM1 — GPT-6-Sol pilot record

Date: 2026-11-13. One screen triplet only; no repeat is claimed.
Model/runtime: GPT-6-Sol via api.haogpt.net, Codex CLI 0.165.0, GUI-only; max 60 calls/actor; per-actor wall timeout 2400 s. No CLI or collaboration MCP.
Task IDs: pgv4rooms (A), pgv4facilities (B). Current compact revision: two same-slot bookings; two requested closures.

## Triplet

| Arm | Run ID | A score/status | B score/status | Elapsed |
|---|---|---|---|---:|
| MA-ID | cdesk3-v4-ma-id-20261113T061735Z-1511887 | 1.0 (2/2), done | 1.0 (2/2), done | 834.0 s |
| Shared | cdesk3-v4-shared-20261113T063225Z-1518582 | 1.0 (2/2), done | 0.0 (0/2), fail | 1437.7 s |
| Shared+Lock | cdesk3-v4-shared-lock-20261113T065713Z-1527746 | 1.0 (2/2), done | 0.0 (0/2), fail | 1382.3 s |

This is a one-time MA-ID PASS / Shared FAIL / Shared+Lock FAIL screening result. Shared and Shared+Lock failures are evaluator-scored task failures, not API/Guest errors (error=null). In both failed arms Facilities declared the task infeasible after reporting that the shared desk repeatedly switched from Facilities to Programme bookings between actions. The Shared+Lock trace has lock_enabled=true on 47 A and 26 B actions; lock wait was 3.232 s + 1.616 s, lock-held time 107.190 s + 58.759 s. The per-action lock serialized individual calls but did not preserve a whole multi-step panel/form transaction. A nevertheless completed both bookings in both arms.

Fixture and source manifests are byte-identical across the three arms. Each Guest was reset from the same base; MA-ID used isolated desktops, while Shared/Shared+Lock used one common desktop. Scripted joint-positive Guest control on the current fixture also passed A=1.0 and B=1.0: cdesk3-v4-scripted-joint-20261113T060754Z-1507273. Offline Oracle tests passed.

## Preserved pre-revision calibration

Do not combine this row with the triplet above: cdesk3-v4-ma-id-20261113T052039Z-1485864 used a larger 5-booking/3-closure fixture, timed out at 2400 s with A=2/5 and B=2/3, and is an incomplete task result, not infrastructure-invalid.

## Audit caveat

The app presents a room-capacity/status summary and its Facilities worklist. In this revision the room-inventory entries still include an additional R-202 safety notice, while the specific Facilities task asks for R-101 and R-201. This remained visible in all three arms and was not filtered post hoc. The direct agent message nevertheless identified repeated panel switching as the reason it could not save or verify either requested closure. Treat the result as a promising one-time pilot, with the exposed out-of-scope notice recorded as a content-validity caveat to resolve before publication or a repeat. Do not silently change the current manifest or claim this single screening proves generality.

## Token usage

Summed from the Codex turn-completed records (input includes cached input; this is not a dollar-cost estimate):
- MA-ID: input 1,669,097 (cached 1,375,288); output 5,053; reasoning output 1,368.
- Shared: input 4,326,215 (cached 3,637,578); output 10,801; reasoning output 4,970.
- Shared+Lock: input 3,463,073 (cached 2,915,024); output 10,151; reasoning output 4,730.
- Total: input 9,458,385 (cached 7,927,890); output 26,005; reasoning output 11,068.

Runs/results and model traces are under /mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/. Archived overlays are under /mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays/. Some archive cp commands reported permission-metadata warnings on RAID; the qcow2 files were copied. The raw run directories are the source of truth.
