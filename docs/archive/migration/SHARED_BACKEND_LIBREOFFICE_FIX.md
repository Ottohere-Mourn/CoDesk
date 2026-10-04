# Shared Backend / LibreOffice Save Investigation

Date: 2026-09-30 (A6000, OSWorld V2.1 Guest)

## Decision

**Root cause class: C — the deployed QEMU virtfs/9p local backend's effective guest ownership and mode handling is incompatible with LibreOffice's save-temp reopen path.** It is not a general host directory write-permission failure. The exact trigger is LibreOffice creating a mode-0600 temporary file, then reopening it; the 9p server returns EACCES on that reopen. Changing QEMU's security_model from none to either mapped-xattr or mapped-file did not change the Guest-visible result in this deployment.

**Do not use this 9p backend for shared LibreOffice workspaces.** The default project configuration has been restored to the existing security_model=none image/tag so unrelated existing 9p fixtures retain their previous behavior. Candidate runtime images and all failed run artifacts were preserved; none is the accepted office backend.

The practical replacement to prototype is **virtiofs**, with one run-scoped host workspace exported to every Guest in the condition. MA-ID and MA-SD must use the same workspace/backend topology and the same export implementation; only desktop/session sharing may differ. Do not resume mechanism or model experiments until the acceptance gate below passes.

## Evidence and classification

| Evidence | Result | Interpretation |
|---|---|---|
| Local-filesystem control local-control-ma-sd-20260930-r09 | One real Guest; the same Writer and Calc Flat ODF fixtures opened by their exact filenames; both no-op GUI saves preserved the exact seeded state; setup_validation.ready=true, success=true, provenance_status=complete; container destroy recorded | The LibreOffice apps, fixture, GUI readiness and local filesystem save path work. This is the control, not evidence that shared 9p works. |
| Original 9p trace shared9p-save-trace-masd-20260930-r10 | Guest user 1000:1000; seeded target writable; directory mode 0777; create/truncate/rename/delete probe passed. table.fods opened and advisory lock succeeded. On save, openat(...lu*.tmp, O_RDWR|O_CREAT|O_EXCL, 0600) succeeds, then openat(...same tmp, O_RDWR|O_CREAT, 0666) returns -1 EACCES. | Rules out a simple inability to write the directory or open/lock the seeded document. The failing operation is the app's save-temp reopen. |
| QEMU mapped-xattr attempt shared9p-mappedxattr-single-masd-20260930-r12 | Actual QEMU process argv confirmed security_model=mapped-xattr,fmode=0666,dmode=0777; same temporary-file reopen returns EACCES. Readiness failed and provenance capture also hit PermissionError reading the 9p lock file from the host evaluator path. | The option was active, but did not correct the deployed server's effective mapping. Not a pass. |
| QEMU mapped-file attempt shared9p-mappedfile-single-masd-20260930-r13 | Actual QEMU argv confirmed security_model=mapped-file,fmode=0666,dmode=0777; same reopen returns EACCES. The host-side .virtfs_metadata directory was root-owned/inaccessible to the normal evaluator process; provenance capture failed reading the lock file. | Also not a pass; its metadata layout adds an evaluator-access issue. |
| Earlier r08 shared-9p attempt | One Guest reached Calc readiness; same setup/save validation failed | Consistent with the trace-confirmed failure. |

The permission probes deliberately do not count as LibreOffice compatibility tests. Conversely, the trace is direct application evidence: the saved document remains byte/semantic-equivalent to the initial fixture after the failed GUI save, while the exact temp-file reopen is denied. Trace lines also include unrelated read-only permission errors under /usr/lib and /usr/share; those are not the save root cause. The decisive lines are the /tmp/swcub_office/lu*.tmp create/reopen sequence.

QEMU documents none, mapped-xattr, and mapped-file as distinct local 9p security models; mapped-xattr stores metadata in extended attributes and mapped-file uses .virtfs_metadata. Those are supported configurations in principle, but both alternatives were tested against this real Guest and did not pass this task. See [QEMU invocation documentation, -virtfs](https://www.qemu.org/docs/master/system/invocation.html#virtfs).

## Artifact index

All artifacts are retained under /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/:

- Control: mechanism-validation-round1/local-control-ma-sd-20260930-r09/
- Original 9p syscall trace: shared-backend-diagnostics/shared9p-save-trace-masd-20260930-r10/syscall-trace/calc-relevant.txt and calc-full.json
- mapped-xattr failed reproduction: shared-backend-diagnostics/shared9p-mappedxattr-single-masd-20260930-r12/
- mapped-file failed reproduction: shared-backend-diagnostics/shared9p-mappedfile-single-masd-20260930-r13/

Each reproduction retains error.json, screenshots/accessibility captures, event trace, syscall trace where enabled, workspace files, provenance status and resource-events.jsonl. Both new containers have full-ID destroy records; no unknown container was touched. There are no active Guest containers at report time.

## Acceptance status

| Gate | Status | Evidence / reason |
|---|---|---|
| A. Single-Guest Writer save | **PASS on Guest-local filesystem only; FAIL on shared 9p** | r09 opens/saves both apps. All 9p runs fail during Calc setup save before episode validity. |
| B. Single-Guest Calc save | **PASS on Guest-local filesystem only; FAIL on shared 9p** | Same as A; trace pinpoints temp-file reopen EACCES. |
| C. Two Guests simultaneously mount one shared backend | **NOT RUN** | Stopped at the required single-Guest gate; a failing backend must not be promoted to a two-Guest test. |
| D. Both Guests save their target files on that backend | **NOT RUN** | C was not reached. |
| E. Evaluator/reset/provenance | **FAIL / INCOMPLETE for candidate 9p modes** | r12 and r13 provenance failed on host PermissionError reading a lock file. Run-owned containers were destroyed, but a task reset/evaluator pass was not established. |
| F. No cross-task contamination | **NOT VERIFIED** | No valid shared-backend episode completed. |

**Mechanism-experiment blocker: NOT REMOVED.** No Qwen or MA-ID/MA-SD experiment was launched in this investigation.

## Next backend prototype: virtiofs

1. Add a project-owned runtime image variant containing a pinned virtiofsd; expose only the run-scoped workspace and required FUSE device to the runtime container. Do not grant broad container privileges without a separate security review.
2. Mount the same host path into the Guest using virtiofs. Confirm the Guest sees the expected user and normal POSIX mode/lock/temp/rename/unlink/fsync behavior; verify the host evaluator can read outputs without privilege escalation or sidecar metadata.
3. Run the exact local-control fixtures and real LibreOffice no-op save, then Writer and Calc independently on one Guest. Collect trace and provenance.
4. Only after single-Guest save/readback passes, run two Guests simultaneously against the same backend path and have each save its distinct target. Verify both visible outputs, evaluator, reset, provenance and absence of cross-task contamination.
5. Confirm topology equivalence explicitly: MA-ID and MA-SD use the same backend type, run-scoped workspace source, ownership mapping and evaluator-visible files. Then rerun a clean single/two-Guest regression before releasing the mechanism-experiment blocker.

Do not change evaluator semantics, task goals, or ownership safety rules to accommodate a backend. If virtiofs cannot be safely supplied through the existing runtime container, evaluate a project-scoped network filesystem service with identical topology in both conditions rather than falling back to separate MA-ID workspaces.
