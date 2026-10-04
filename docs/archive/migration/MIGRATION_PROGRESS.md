# CoDesk A6000 Migration Progress

Date: 2026-09-30 (Asia/Shanghai)

## Current status

The independent A6000 copy and core non-Guest environment are prepared under /home1/mjh/Projects/CoDesk-V0-A6000. The 4090 source workspace was not modified. A6000 is not Guest-ready: user mjh lacks Docker daemon permission and cannot read/write /dev/kvm. No container, image load/build, Guest, or model inference was started on A6000.

## Migrated assets

| Asset | A6000 path | Verification |
|---|---|---|
| CoDesk full Git history | CoDesk/ and codesk-v0.bundle | branch v0, HEAD 69aac16441bfa544419aebc4685a67257c6ad8c8, 8 commits ahead of origin/v0; bundle SHA-256 3242386fb6c9e138a5217c9eb89c09138662d37e4174d56d71d08479119bea64 |
| OSWorld V2.1 checkout | external/OSWorld-V2-osworld-v2.1 | commit 3d778a3c9a34a079316f70df023b166700445792; modified Docker provider retained and separately saved as snapshots/OSWorld-V2-osworld-v2.1-provider.patch; patch SHA-256 1d0ca9fc2f6acd0c78948d1258522edf3080554efc307641407371128c323d4e |
| Guest base QCOW | assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2 | 14,891,810,816 bytes; SHA-256 28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a |
| Runtime archive | snapshots/osworld-v2.1-qemu-runtime-local.tar | 195,523,072 bytes; SHA-256 fca808b4ae7029f702b7c02957d89b6fb0bde0c1a3a7704f96308b0db1de41b5; expected source image ID sha256:002d09fa7cc4e08ce5321c3d0a261e336a2c17651726f8538bca4dcf991e82ec; not loaded |
| uv | tools/uv | version 0.12.18; SHA-256 b97ae0e1ed3661fcd0c446cc59d81f5720c24d35627b21814a7581fb67eba673 |
| OSWorld Python env | envs/osworld-v2.1 | Python 3.12.3; frozen dependency setup completed; requests, lxml and osworld_ffmpeg imports pass; FFmpeg 7.0.2-static copied from the source environment with matching hash |
| Audit | CoDesk/MIGRATION_A6000_AUDIT.md | copied audit SHA-256 ec1ab8ec779e30d5d793a5dcd1be94ad700c4b0870da92e51571d19dd8e4756f |

The provider patch, Guest and runtime archive are separate from the Git history. The original external checkout and old experiment results remain on 4090. No bulk history copy was made. Task Factory, task definitions, manifests, evaluator and tracked configs moved with Git.

## A6000 copy changes

The target branch remains 8 commits ahead of origin; no commit or push was made. Uncommitted migration-specific changes add optional same-backend topology. MA-ID exports one host workspace through QEMU 9p into two independently controlled Guests; MA-SD uses one Guest/session and that same workspace. Existing evaluator rules and task goals were not changed.

Other changes add a QEMU workspace mount, three one-episode validate-only configs, environment/readiness, bounded smoke, runtime-image preparation, Qwen environment setup and manual rollback scripts, plus offline topology tests. Same-backend logic is offline-validated only. 9p mounting, cross-Guest file visibility, reset and real application behavior need Docker/KVM and remain unverified.

## Non-Guest validation

- Changed Python modules compile; migration, readiness, image preparation, smoke, rollback and Guest entrypoint scripts pass bash -n.
- Runner --validate-only passed for Solo, MA-ID and MA-SD. Each config is one worker; Solo and MA-ID reserve two Guest slots, MA-SD one. These commands did not start a Guest.
- pytest -q --ignore=tests/test_real_workspace.py: 117 passed.
- The first full pytest run produced 117 passes and 9 setup errors in tests/test_real_workspace.py. Its fixture attempts to build a Docker X11 image; A6000 Docker access was denied before daemon access. It created no container/image and was not rerun. This is not a passing test.
- Read-only A6000 readiness: QCOW, OSWorld checkout and isolated OSWorld Python present; Docker daemon permission check and /dev/kvm access failed. Runtime image absent. The script exited nonzero as intended.

## Model migration

The 4090 audit identified Qwen3-VL-30B-A3B-Instruct under /mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct, with index total size 62,141,508,064 bytes (about 58 GiB). A6000 /home1 has about 8.4 TiB free and no quota. The source host SSH connection timed out in this turn; no model shard was copied and no weight hash is claimed.

Pinned runtime manifest and requirements are under snapshots/qwen3vl-runtime. The user-local setup script is scripts/setup_a6000_qwen_env.sh. It is currently installing CPython 3.13.2, then pinned PyTorch/Transformers dependencies with bounded download/build concurrency. It does not load weights or touch GPUs; final install status is pending. No model-load result exists. GPU inference remains deferred because the prior audit found active compute owned by other UIDs; those processes were not inspected or touched.

## Minimum single-worker acceptance

1. Confirm Docker and KVM access, free /home1, and read-only scripts/a6000_environment_check.sh. Stop if any check fails.
2. Verify the QCOW SHA-256 listed above.
3. Review existing container IDs/labels and run ownership ledgers. Do not stop/delete anything. Stop if ownership is ambiguous.
4. Run scripts/a6000_prepare_runtime_image.sh. It checks the base image ID and refuses to overwrite an existing target tag without the CoDesk label.
5. Run scripts/run_a6000_single_worker_smoke.sh. This is one coordinator worker with two independent Guest slots for the Writer/Calc solo pair. The script refuses to proceed if any project-labelled container already exists.
6. Verify readiness, screenshots, GUI actions, saved ODF state, evaluator, provenance/ownership ledger and reset. Only then consider same-backend MA-ID/MA-SD.

Rollback means stop scheduling on A6000 and resume from the untouched 4090 copy. Preserve A6000 artifacts/resources for review. Do not delete or prune.

## Migration night update (2026-09-30, supersedes the earlier model-transfer snapshot above)

- The source Qwen3-VL-30B-A3B-Instruct directory was copied read-only from `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct` into `/home1/mjh/Projects/CoDesk-V0-A6000/models/Qwen/Qwen3-VL-30B-A3B-Instruct` using a single rsync stream limited to 8 MiB/s. Rsync reported 62,153,207,754 total source bytes and exit 0. All 13 expected safetensors shard files are present at the target. The index metadata's 62,141,508,064-byte total is the shard total and excludes auxiliary tokenizer/config files.
- Source-side SHA-256 generation for every model file is still running at low I/O priority; no weight checksum claim is made until target verification completes. Guest ZIP archive is not yet copied.
- Final non-Guest regression rerun: 117 tests passed in 0.71 s (`snapshots/a6000-validation/offline-tests-final.log`). Shell syntax passed. Three Solo/MA-ID/MA-SD runner configs passed `--validate-only` and were saved in `snapshots/a6000-validation/config-validate-only-final.log`.
- Readiness rerun sees the QCOW and all 13 weight shards, but exits 1 because Docker daemon access is denied/uncheckable and `/dev/kvm` is inaccessible. This run starts no container or Guest. Evidence: `snapshots/a6000-validation/readiness-final.log`.
- No GPU query, model load/inference, Docker image load/build, Guest start, model episode, Git commit, or push was performed. Same-backend MA-ID/MA-SD implementation remains offline-only and needs Guest verification.

## Artifact verification addendum (2026-09-30)

- Qwen source manifest: `snapshots/qwen3vl-runtime/qwen-model.sha256`, 26 entries covering all 13 shards and model configuration/tokenizer assets. The full target `sha256sum --check` completed successfully; evidence in `snapshots/a6000-validation/qwen-checksums.log`.
- CPU-only Qwen API import passed with `CUDA_VISIBLE_DEVICES` empty (`snapshots/a6000-validation/model-interface-final.log`). This did not load model weights or query/use a GPU.
- OSWorld V2.1 official ZIP asset `osworld-v2-ubuntu-x86.qcow2.zip` is being copied at a single-stream 8 MiB/s to `snapshots/osworld-v2.1-guest-archive/`. The raw QCOW remains separately available at `assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2`; neither is unpacked over the other. ZIP hash and final integrity result are pending transfer completion.

## Final migration-night status (2026-09-30)

- Transfer completion: Qwen model directory (62,153,207,754 bytes, 26 files) and official OSWorld V2.1 Guest ZIP (14,891,811,084 bytes) are on `/home1`. Both rsyncs were a single stream capped at 8 MiB/s; sources remain unchanged. Full Qwen target SHA-256 verification passed. Guest ZIP target hash equals the OSWorld V2.1 release manifest value `14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3`, and its central directory contains the expected QCOW member. Transfer evidence is summarized in `../snapshots/a6000-validation/transfer-log.md`.
- `scripts/verify_a6000_assets.sh` completed with exit 0, verifying the Git bundle, QCOW, Docker runtime tar, provider patch, uv binary, Guest ZIP, all Qwen files, and pinned Transformers source-file hashes. Full output is in `../snapshots/a6000-validation/asset-verification-final.log`.
- CPU-only local config and processor load succeeded: `Qwen3VLMoeConfig`, `Qwen3VLProcessor`, and `Qwen2Tokenizer`, with `local_files_only=True` and `CUDA_VISIBLE_DEVICES=''`. This is not a weight/model inference test. Qwen import test also passed.
- Final non-Guest validation: 117 tests passed; shell syntax passed; Solo, same-backend MA-ID, and same-backend MA-SD configs each passed runner `--validate-only`. `git diff --check` passed. Logs are under `../snapshots/a6000-validation/`.
- Final readiness remains blocked, exit 1: Docker CLI exists but daemon access is denied/uncheckable; `/dev/kvm` is inaccessible. No Docker image was loaded/built, no container or Guest was started, and no model weights were loaded for inference. These are not passed Guest tests.
- Same-backend MA-ID/MA-SD topology is implemented and offline-tested only: MA-ID uses two Guest desktop sessions with one host workspace export; MA-SD uses one Guest session with that workspace. 9p mount visibility, app behavior, persistence and reset are still unverified until permissions are granted.
- Git remains on `v0`, HEAD `69aac16441bfa544419aebc4685a67257c6ad8c8`, 8 commits ahead of `origin/v0`; migration changes remain uncommitted. No commit or push was made. The 4090 working tree was left untouched.
- `/home1` readiness output reports 8.3 TiB free of 9.1 TiB after migration.

### Shortest permission-ready acceptance

1. On A6000, run `cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk && bash scripts/a6000_environment_check.sh`. Continue only if Docker daemon and `/dev/kvm` both report access; do not change permissions locally.
2. Review existing project-labelled container IDs/ownership ledgers. If any exist or ownership is unclear, stop and report; do not stop or remove resources.
3. Run `bash scripts/a6000_prepare_runtime_image.sh`; it verifies the pinned runtime tar and base image ID, loads/builds only the CoDesk-tagged runtime, and refuses to overwrite a tag without CoDesk ownership.
4. Run `bash scripts/run_a6000_single_worker_smoke.sh` for one bounded Writer/Calc Solo pair. Validate Writer/Calc readiness, screenshots, saved ODFs, evaluator, provenance and reset.
5. Only after that passes, run one MA-ID then one MA-SD scripted smoke to validate same-backend workspace mounts. Do not start Qwen inference until GPU allocation is explicitly clear; then set `CODESK_CUDA_VISIBLE_DEVICES` for that run.

## Permission restoration and first real Guest acceptance (2026-09-30; supersedes earlier blocked-readiness statements)

- A6000 now grants `mjh` Docker daemon access and read/write `/dev/kvm` via the `docker` and `kvm` groups. The read-only `scripts/a6000_environment_check.sh` now passes, including the Guest QCOW, both runtime tags, isolated OSWorld Python, and model asset presence. No permission or system configuration was changed by CoDesk.
- Host snapshot at acceptance: 144 logical CPUs; load 6.68/22.05/37.09, `MemAvailable` about 222 GB, CPU PSI avg10 0.00/avg60 0.00; no CoDesk-labelled container existed before retry. The run used one coordinator worker; the paired Solo protocol required at most two active Guest slots.
- Runtime image preparation completed: the migrated `:local` image was present and retained; a separate `:a6000` image was built (image ID `sha256:8e4d74c1fbec619992e1c4b8c80d9fa613d5d2af4d0e443d2e43da3bcba03dc7`). No pre-existing tag was overwritten and no image/container cleanup was performed.
- First smoke attempt `a6000-wc-solo-smoke` is preserved and classified as runner bootstrap/environment failure before Guest creation: `uv --project ... run --frozen` attempted an isolated build of `osworld-ffmpeg` and timed out fetching `setuptools>=77` metadata from `files.pythonhosted.org`. Evidence: `../snapshots/a6000-validation/single-worker-smoke.log`; the failed attempt's artifact directory is retained.
- Narrow A6000 runner fix: `scripts/run_writer_calc_v1.sh` now uses the prepared `CODESK_PYTHON` environment directly when available, avoiding network-dependent `uv` build isolation. It also prioritizes `SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE` so the configured A6000 runtime tag is not silently replaced by the legacy `:local` default. The retry below used the preserved `:local` image because the old precedence was resolved before this correction; future invocations select `:a6000`.
- Real scripted Guest smoke passed under unique experiment ID `a6000-wc-solo-smoke-retry-01`; config: `configs/a6000_writer_calc_solo_smoke_retry01.json`. It ran one coordinator worker and the existing paired Solo condition, with independent Writer and Calc Guest desktops. Wall clock: 615.487 s. Both exact goals passed: Writer text `Approved by GUI actor`; Calc cells `[["Record","Status"],["Quarterly","Approved"]]`. No contamination or unexpected state mutation was found; LibreOffice 7.3.7.2 was observed in both Guests.
- Readiness evidence includes named application screenshots, accessibility trees, keyboard-interaction probes, and no-op-save persistence checks under `../artifacts/writer-calc-v1/a6000-wc-solo-smoke-retry-01/episodes/0001-solo-r01/.../setup-validation/`. Final ODFs, action screenshots, event/provenance/resource ledgers and report are in the same artifact tree.
- Programmatic reset passed 1/1 for both desktops; each reset verified task files absent in a fresh Guest. Four Guest containers were created and all four have matching destroy-request/destroyed records under the same run ID and owner token. After completion, no CoDesk-labelled container remained. Artifact integrity 1/1; provenance complete; evaluator success 1/1.
- Post-fix non-Guest regression: `python -m pytest -q --ignore=tests/test_real_workspace.py` passed 117/117 in 0.72 s. Retry config `--validate-only` and `git diff --check` passed. No model service or GPU was started; this is a scripted environment acceptance, not a Qwen episode.
- An OSWorld settings warning noted absent optional `evaluation_examples/settings/proxy/dataimpulse.json`; it did not prevent the offline Writer/Calc episode. Keep the initial failed attempt and this successful retry as separate evidence; do not overwrite or merge their outcomes.

The earlier read-only audit sections record the state at their own timestamps. This addendum records the subsequent permission change and real Guest acceptance; it does not retroactively revise the initial audit snapshot.
