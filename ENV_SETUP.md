# OSWorld V2.1 Guest setup

This setup adds a real OSWorld V2.1 Ubuntu Guest to the existing V0 scripted workspace. It uses a pinned official Guest image and the tagged OSWorld code. The upstream Docker runtime image could not be pulled from the current network, so the working path builds a small local QEMU/KVM runtime from a digest-pinned Ubuntu base. That fallback is local compatibility infrastructure; it is not the official OSWorld runtime image.

## Pinned inputs and storage

- OSWorld-V2 source tag: `osworld-v2.1`, commit `3d778a3c9a34a079316f70df023b166700445792`.
- Release manifest: [`outputs/osworld-v2.1/environment/release_manifest.json`](outputs/osworld-v2.1/environment/release_manifest.json).
- Official Guest archive: `osworld-v2-ubuntu-x86.qcow2.zip`, 14,891,811,084 bytes, SHA-256 `14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3`.
- Extracted Guest: `/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2` (50 GiB virtual size; 13.9 GiB allocated; `qemu-img` reports `corrupt: false`).
- OSWorld checkout: `/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1`; its `docker_vm_data` points to the RAID1 cache.
- QEMU overlays and task cache: `/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/{overlays,task-cache}`. Episode overlays are disposable copy-on-write files; do not delete the base image.
- The verified VM archive and overlay data are on `/mnt/raid1/mjh`, not `/data`.

Host checks on 2026-09-26: Docker works; `/dev/kvm` can be passed through to a container; 80 CPU threads and ample RAM are present. The invoking user is not in the host `kvm` group, so the runner passes the device directly without editing host groups or global configuration. `/mnt/raid1/mjh` had about 1.9 TiB free at inspection.

## Reproduce setup

From the repository root:

```bash
scripts/setup_osworld_v2_1.sh
scripts/build_osworld_v2_1_runtime.sh
scripts/run_osworld_v2_1_quickstart.sh
```

The setup script checks the exact source commit and release manifest, verifies archive size and SHA-256, extracts to RAID1, creates a symlink in the external checkout, and installs the pinned host environment with `uv sync --frozen --no-dev`. It does not download gated tasks/assets unless `OSWORLD_V2_DOWNLOAD_GATED_ASSETS=1` is explicitly set. Those assets require an authenticated Hugging Face account with access; they were not available here.

The local runtime is built from `infra/osworld-v2.1-qemu-runtime/Dockerfile`. Its Ubuntu base is pinned by digest; installed packages and versions are recorded in `outputs/osworld-v2.1/environment/runtime-packages.txt`. A narrow patch script adapts the pinned external Docker provider to this runtime image and to RAID1-backed per-episode QCOW overlays.

Run the real two-actor CSV episode with:

```bash
scripts/run_osworld_v2_1_shared_csv.sh
```

To preserve a separate run directory:

```bash
OSWORLD_V2_RUN_DIR="$PWD/outputs/osworld-v2.1/shared-csv-repeat" \
  scripts/run_osworld_v2_1_shared_csv.sh
```

The deterministic stale whole-file overwrite control runs in its own fresh Guest and is expected to produce a failed joint evaluator result while the control itself passes when the missing CLI row is detected and reset succeeds:

```bash
OSWORLD_V2_RUN_DIR="$PWD/outputs/osworld-v2.1/stale-overwrite" \
  scripts/run_osworld_v2_1_shared_csv.sh --scenario stale-overwrite
```

This starts a real Guest, waits up to five minutes for a nonblank desktop screenshot, seeds a shared Guest CSV through its CLI endpoint, then runs GUI and CLI scripted actors through the same `DesktopEnv`/Guest. The GUI actor clicks GNOME Activities, searches for Terminal, and types a Python append command into the visible terminal. The CLI actor appends its own row through the Guest command endpoint. The evaluator reads the final file on the host through a private callback that is not present in actor contexts. The runner then resets and checks that a fresh Guest has a different container ID and no task file.

## Verified execution

- Official OSWorld `quickstart.py` ran against the pinned Guest: reset, visible screenshot/API startup, PyAutoGUI right-click, successful action and close all completed.
- Real shared CSV report: [`outputs/osworld-v2.1/shared-csv/report.json`](outputs/osworld-v2.1/shared-csv/report.json). Both actors completed in environment `osworld-7313b75158b0`; the report records the same Guest container ID for the shared task. Exact expected rows passed with no missing/duplicate rows.
- Independent repeat report: [`outputs/osworld-v2.1/shared-csv-repeat-02/report.json`](outputs/osworld-v2.1/shared-csv-repeat-02/report.json) records the same final CSV SHA-256 from a separate Guest/container.
- Real stale-overwrite negative control: [`outputs/osworld-v2.1/stale-overwrite/report.json`](outputs/osworld-v2.1/stale-overwrite/report.json) shows CLI row missing after the GUI actor commits its stale snapshot. The evaluator correctly rejects joint completion; the control succeeds by detecting the conflict and the subsequent reset passes.
- Actual Guest screenshots and intermediate GUI observations are under [`outputs/osworld-v2.1/shared-csv/`](outputs/osworld-v2.1/shared-csv/); the actor-attributed JSONL trace is `events.jsonl`.
- Reset check passed: the fresh Guest had a different container ID and `/tmp/swcub_shared.csv` was absent.
- Earlier failed GUI attempts and the upstream readiness timeout are retained in `shared-csv-attempt-01` through `shared-csv-attempt-04`; they are not counted as passes.

## Boundaries

The OSWorld V2.1 gated task set/assets and an official scored task were not exercised. The shared CSV and stale-overwrite cases are deterministic project probes on the actual OSWorld Guest, not official OSWorld task scores. The upstream official Docker runtime pull is still unavailable; these runs used the documented local runtime fallback. Actual multi-window focus contention, GUI+Human Replay on this Guest, and model actors remain unverified. Existing Docker/Xvfb focus tests are separate local-environment evidence.
