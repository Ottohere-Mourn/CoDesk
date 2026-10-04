# CoDesk Shared Backend V2 Validation

Date: 2026-09-30  
Node: A6000 canonical experiment node  
Scope: identify and validate a LibreOffice-compatible replacement for the rejected 9p backend. No Qwen inference or mechanism experiment was run.

## Decision

**Status: BLOCKED.** Virtiofs cannot run under the current project QEMU container policy without relaxing container restrictions. The project-scoped NFSv4 server starts, but the OSWorld Guest cannot mount it; attempts stop before shared filesystem probes or LibreOffice startup. The shared-backend blocker remains open.

9p remains rejected for LibreOffice workspaces based on the prior syscall trace: LibreOffice's mode-0600 temporary file create succeeds, but reopening that same file returns EACCES. This report does not repeat 9p tuning.

## Virtiofs audit

| Check | Result |
|---|---|
| QEMU version | QEMU 6.2.0 in `swcub/osworld-v2.1-qemu-runtime:a6000` |
| QEMU device support | `vhost-user-fs-device` and `vhost-user-fs-pci` are present |
| virtiofsd | `/usr/lib/qemu/virtiofsd`, version 6.2.0, present in runtime image |
| Host device access | `/dev/fuse` is available; `/dev/kvm` is accessible to the project account |
| Minimal project-container test | virtiofsd exits at `unshare(CLONE_FS) failed with EPERM` under the current Docker seccomp policy |
| Safe next step | None under current policy. Enabling unconfined seccomp or adding container capabilities would be a security-policy change and was not attempted. |

The runtime contains the QEMU frontend and virtiofsd, but its default container confinement prevents the daemon startup it needs. That is a runtime security constraint, not evidence that virtiofs itself is incompatible with LibreOffice.

## NFSv4 fallback implementation

A project-scoped NFS-Ganesha gateway was added under `infra/nfs-gateway/` and wired into `scripts/run_writer_calc_v1.py` using `--shared-backend-transport nfs4`.

- Image base: Ubuntu 22.04 pinned by digest in `infra/nfs-gateway/Dockerfile`.
- NFS-Ganesha packages: 3.5-1ubuntu1 (`nfs-ganesha`, `nfs-ganesha-vfs`).
- Runtime image tag: `swcub/codesk-nfs-gateway:jammy-v2`; final local image ID: `sha256:e6928d5c91dbaa8f940e98075ee3a57c5b7835e83fc3bce29b304dfe004ef3e4`.
- The gateway exports only run-owned `task/` and `reset/` directories. It binds to Docker bridge gateway `172.17.0.1:12049/tcp`; port 2049 and other host services were not modified.
- `rpcbind` is started only inside the gateway container and is not published. Ganesha logs “NFS SERVER INITIALIZED” and the bridge-bound TCP port accepts connections.
- Guest mount uses NFSv4.1/TCP and `mount -i` to avoid requiring the optional `mount.nfs4` userspace helper.
- Guest identities are intended to map via `Squash=All` to the owning project UID/GID 1037:1037. The export folders are under the run artifact root and marked with run ownership metadata.

The Ganesha parameter names were checked against the Ubuntu Jammy 3.5 package manual: [ganesha-core-config](https://manpages.ubuntu.com/manpages/jammy/man8/ganesha-core-config.8.html). Startup emits DBus and Kerberos credential-cache warnings but reaches server initialization and opens the configured TCP listener. This only verifies service startup; it does not verify an NFS mount or file operation.

## Filesystem and application results

| Gate | Status | Evidence |
|---|---|---|
| Guest filesystem probes (`create`, read/write, chmod, close/reopen 0600, temp, rename/atomic replace, unlink, fsync, advisory lock, directory operations) | **NOT RUN / BLOCKED** | Both NFS Guest runs failed during `mount`; the newly wired probe therefore did not execute. The probe code is present but not counted as evidence. |
| Single-Guest Writer save/reopen on NFS | **FAIL (not reached)** | Guest startup failed at NFS mount before application setup. This is an environment invalidity, not a Writer/model task failure. |
| Single-Guest Calc save/reopen on NFS | **FAIL (not reached)** | Same startup failure, before Calc setup. |
| Prior Guest-local filesystem control | **PASS, control only** | `mechanism-validation-round1/local-control-ma-sd-20260930-r09`: named Writer and Calc fixtures opened, no-op GUI saves preserved exact seeded state, readiness/provenance passed, and Guest destruction was recorded. This says nothing about NFS. |
| Prior shared 9p save | **FAIL** | `SHARED_BACKEND_LIBREOFFICE_FIX.md` and trace run `shared9p-save-trace-masd-20260930-r10` show the 0600 temp-file reopen EACCES. |

## NFS Guest attempts and preserved artifacts

1. `nfs-ma-id-r01-20260930` — NFS gateway and first Guest started. Mount failed with `mount: /tmp/swcub_office: bad option; ... might need a /sbin/mount.<type> helper program`. Provenance is complete; startup error, screenshot, overlay, events, and resource ledger are retained under:
   `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/shared-backend-v2/ma-id-validation/nfs-ma-id-r01-20260930/`
2. `nfs-ma-id-r02-20260930` — retried with `mount -i` to skip external mount helpers. It failed with the same Guest mount error. This artifact also records complete provenance and owned-resource destruction:
   `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/shared-backend-v2/ma-id-validation/nfs-ma-id-r02-20260930/`
3. `nfs-guest-kernel-diagnostic-20260930` — one Guest started for a read-only mount-support diagnostic; the diagnostic command was malformed by host-side quoting before it reached the Guest. The Guest was closed and its failed attempt is preserved. No conclusion about Guest kernel NFS support is drawn from this run.
4. `nfs-guest-kernel-diagnostic-02-20260930` — diagnostic command path also failed before producing its requested output; Guest closed normally. This attempt adds no kernel-support evidence.
5. `nfs-gateway-config-probe-*` — project-labeled gateway startup probes are retained under `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/shared-backend-v2/`; their exact container IDs and destroy records are in each `resource-events.jsonl`. The first two Ganesha configurations exited before listening; the final configuration started and listened, then its owned container was removed.

The two MA-ID attempts do not count as task episodes and do not count against Actor success. Both fail at setup before the second Guest is started, so no two-Guest shared mount, file visibility, LibreOffice save, evaluator, task reset, or coherency test occurred. Runner-level owned-resource cleanup and provenance recording completed; task reset was not reached.

## MA-ID / MA-SD topology

The same-workspace runner path assigns one backend ID and one run-scoped NFS gateway/export to the episode. MA-ID is configured to mount that export in two separate Guest desktops; MA-SD is configured to mount the same export type/path in its one shared Guest. The task and reset exports are separate subdirectories served by the same gateway implementation.

**Design-level topology: MATCHED. Runtime topology: NOT VALIDATED.** Neither condition completed an NFS mount, and no MA-SD run was launched. Do not claim a causal comparison until both runtime paths mount the same backend implementation and pass the file/app gates.

## Acceptance checklist

1. 0600 create/close/reopen: **NOT RUN**.
2. Writer save, close, reopen and exact evaluator: **NOT RUN**.
3. Calc save, close, reopen and exact evaluator: **NOT RUN**.
4. Single-Guest repeatability: **NOT ESTABLISHED**.
5. Two Guests simultaneously mounting one backend: **NOT RUN**.
6. Guest A/B visibility in both directions: **NOT RUN**.
7. Separate Writer/Calc saves without contamination: **NOT RUN**.
8. Evaluator on accepted shared backend: **NOT RUN**.
9. Task reset on accepted shared backend: **NOT RUN** (run-owned Guest/container cleanup passed on invalid startup attempts).
10. Matched operational MA-ID / MA-SD topology: **NOT ESTABLISHED**.

**Mechanism-experiment blocker: NOT CLEARED.** Continue to prohibit Qwen and Clipboard/Modal/Application Context experiments until the backend gate passes.

## Reproduction commands

From A6000:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
source scripts/a6000_env.sh

# Build/update only the project-owned gateway image
(cd infra/nfs-gateway && docker build -f Dockerfile.v2 -t swcub/codesk-nfs-gateway:jammy-v2 .)

# Reproduce the failed (environment-invalid) two-Guest setup attempt with a fresh run ID
"$CODESK_PYTHON" scripts/run_writer_calc_v1.py \\
  --condition ma_id --repeat 1 \\
  --run-id <new-unique-run-id> \\
  --artifact-parent "$CODESK_ARTIFACT_ROOT/shared-backend-v2/ma-id-validation" \\
  --actor-implementation scripted \\
  --backend-topology same_workspace \\
  --shared-backend-transport nfs4
```

No Docker prune, unknown-resource operation, host system change, or Qwen inference was performed. All started containers were created with this run's labels and exact full IDs and were destroyed with ledger records. Project-built images and all failure artifacts were preserved.

## Next safe step

Do not retry LibreOffice yet. The next engineering action requires choosing an explicitly project-scoped Guest capability path: (a) stage the NFS client userspace helper into the project Guest image and verify the kernel/client support, or (b) select a different supported backend that requires no host-wide security change. After a successful Guest mount, run the 0600 filesystem probe first; only then run Writer and Calc single-Guest saves (two fresh runs each), followed by two-Guest visibility and save checks. Until then, keep the mechanism experiment blocker open.
