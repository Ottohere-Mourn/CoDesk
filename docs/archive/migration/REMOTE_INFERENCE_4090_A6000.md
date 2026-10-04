# 4090 Remote Qwen Inference + A6000 Guest

**State:** one real Writer Solo end-to-end smoke passed on 2026-09-30. This is infrastructure acceptance, not a stability claim or a shared-condition result.

## Architecture

- **Guest and orchestration:** A6000 (`admin123-Super-Server`), project `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, OSWorld V2.1 Docker/QEMU Guest, screenshot/observation, native `Qwen3VLAgent`, action parser/execution, evaluator, artifacts, provenance and reset.
- **Inference:** 4090 (`supermicr-EG840G-G20`), local Transformers worker `scripts/local_qwen_worker.py`, checkpoint `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`, `CUDA_VISIBLE_DEVICES=0,1`, offline/local-files-only. It was served from `/home/mjh/.local/share/codesk-remote-qwen/709498e/local_qwen_worker.py`, SHA-256 `bf33d86d53ea9b271c5b0edd6150a8fbfd70108703fdb9304752ab52f805dba5`.
- **Transport:** SSH reverse port forward. The worker binds only `127.0.0.1:15485` on 4090; A6000 connects to its own loopback `http://127.0.0.1:15485`. No public endpoint, cloud API, or A6000 model load was used.
- A6000's `SWCUB_QWEN_INFERENCE_URL` selects the thin HTTP transport in `scripts/run_osworld_v2_1_office.py`. That transport forwards the existing Agent's messages and images, and returns the text response. The pinned OSWorld Qwen3VLAgent prompt, multimodal history construction, action schema/parser, relative-coordinate conversion, generation behavior, and 512-token cap were retained. The actual run used temperature 0, top-p 0.9; no scripted action/fallback was present.

## One-time verified run

- Run ID: `a6000-writer-4090-solo-20260930-r01`.
- Task: existing Writer solo, `OFFICE-GUI-GUI-001`, scenario `writer-osworld-agent-solo`; task metadata correctly marks it `unversioned-prototype` (it is not the formal Writer+Calc v1 task).
- Task goal: replace the existing Writer paragraph with exactly `Approved by GUI actor`, save it, and leave Calc unchanged.
- The A6000 Guest supplied five screenshots/observations. Five model responses were returned by 4090 and parsed by the native Agent: click, Ctrl+A, type target, Ctrl+S, and terminate-success. The four GUI actions were submitted to the real A6000 Guest. No actor script or human action filled in the goal.
- Evaluator: pass; Writer exact text matched, Calc remained `Record / Status; Quarterly / Draft`, and cross-application contamination was false. Actor used 5 turns of a 20-action budget. Reset verification passed using a replacement Guest and confirmed task files absent.
- Remote inference smoke before Guest: text request 200 / `READY` in 583 ms; image request 200 with a correct Writer description in 3.664 s. In the real run the five request round trips were 8.19, 6.10, 7.55, 6.97, and 6.63 seconds; server-side generation was about 5.37–7.02 seconds per response. Model load on 4090 took 212.4 s. No CUDA/OOM or transport errors were recorded.
- Run start was 09:38:12 UTC; run-owned Guest resource lifetime was about 303 seconds (09:38:17–09:43:20 UTC). Task Guest startup/readiness was slow and included blank-screen retries. The first Guest was replaced. The final Guest was ready and task completed; reset verification also passed. This is a readiness latency caveat, not an Agent failure. A separate diagnostic-only screenshot/accessibility probe logged two timeouts during reset; it submitted no actions and did not change the official run result.
- **Evidence:** `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/a6000-writer-4090-solo-20260930-r01/` (report, model trace, screenshots, events, remote request events, worker log, reset evidence, provenance). `report.json` is the evaluator result. `provenance.json` contains 29 artifact hashes; all currently verify. `provenance-reconciliation.json` preserves the original `run.log` hash and documents the hash-only correction after tee/stdout flush. No score, task state, trace, or evaluator was altered.

## Dual-actor architecture check (not an experiment)

The existing Writer+Calc Qwen coordinator constructs a distinct `Qwen3VLAgent` and `OSWorldAgentActor` for each Actor, with separate goals, actor IDs, per-actor artifact/observation/message directories, step budgets, and histories. Its coordinator iterates the fixed actor schedule synchronously and passes both objects the same inference-client interface. Thus one inference worker can be reused without merging Actor history, and the current scheduler submits one inference request at a time. The 4090 HTTP server uses `ThreadingHTTPServer`; this smoke did not test parallel request generation, queue fairness, dual Actors, MA-ID, or MA-SD. The dual-actor runner's current worker bootstrap is local-model oriented; wiring this remote endpoint into that runner remains an adapter integration task, not a verified capability. Do not claim two-Actor remote support until that integration is exercised.

## Reproduction commands

These commands use the already-installed user environments and known paths. Pick a new unique run directory for each episode; do not reuse this run ID or overwrite its artifact.

### 1. Start the private 4090 worker

Run on 4090 as `mjh`:

```bash
MODEL=/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct
WORKER=/home/mjh/.local/share/codesk-remote-qwen/709498e/local_qwen_worker.py
STATE=/home/mjh/.local/state/codesk/remote-inference/NEW-RUN
mkdir -m 700 -p "$STATE"
CUDA_VISIBLE_DEVICES=0,1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
/opt/miniconda3/bin/python "$WORKER" --model "$MODEL" --device auto --port 15485 \
  >"$STATE/model_worker.log" 2>&1 &
echo $! >"$STATE/model_worker.pid"
curl --fail http://127.0.0.1:15485/health
```

Confirm the health JSON names the expected model, host, PID, CUDA devices and loopback bind. This is an owned worker; before stopping it, verify PID and full command line against the pid file and exact worker path.

### 2. Make it reachable only through SSH

From 4090, after `ssh A6000` succeeds:

```bash
CONTROL=/home/mjh/.local/state/codesk/remote-inference/NEW-RUN/ssh-control
ssh -M -S "$CONTROL" -fNT \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -R 127.0.0.1:15485:127.0.0.1:15485 A6000
```

On A6000 verify `curl --fail http://127.0.0.1:15485/health`. The service remains bound to loopback on both ends.

### 3. Run one calibrated Writer Solo on A6000

On A6000 as `mjh`, from the CoDesk repo. The normal wrapper checks/patches the configured OSWorld provider and logs the run; use the already-installed OSWorld environment and runtime image. The run directory must be new:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
export OSWORLD_V2_DIR=/home1/mjh/Projects/CoDesk-V0-A6000/external/OSWorld-V2-osworld-v2.1
export OSWORLD_DOCKER_RUNTIME_IMAGE=swcub/osworld-v2.1-qemu-runtime:a6000
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$OSWORLD_DOCKER_RUNTIME_IMAGE"
export SWCUB_OSWORLD_GUEST_IMAGE=/home1/mjh/Projects/CoDesk-V0-A6000/assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2
export SWCUB_QWEN_INFERENCE_URL=http://127.0.0.1:15485
export SWCUB_QWEN_INFERENCE_HOST=supermicr-EG840G-G20
export SWCUB_QWEN_SERVER_LOG_PATH=/home/mjh/.local/state/codesk/remote-inference/NEW-RUN/model_worker.log
export OSWORLD_V2_RUN_DIR=/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/NEW-UNIQUE-RUN
./scripts/run_osworld_v2_1_office.sh writer-osworld-agent-solo
```

The past run used OSWorld V2.1 Python 3.12.3. Check the wrapper's configured Python/environment before running; do not let `uv` create a different environment or download packages unexpectedly. The wrapper creates a Guest and requires Docker/KVM; use the read-only environment check and ownership ledger first. A readiness failure invalidates the environment attempt and must be retained separately from model task success.

### 4. Close only this run's resources

The runner should destroy its run-owned Guest and stamp the resource ledger/provenance. Verify the exact run's `resource-events.jsonl`, full container IDs, and that no active container for this run remains. After copying the worker log into the artifact, stop the tunnel with:

```bash
ssh -S "$CONTROL" -O exit A6000
```

Then terminate only the verified PID from this run, and only if its full command line still matches the worker. Never use Docker prune or a broad process/container match.

## Integrity notes and limits

- One Writer Solo passed; this does not establish repeatability, Calc Solo, two-Actor behavior, or shared-desktop interference.
- The task is an unversioned prototype and was not silently relabeled as Writer+Calc V1. No benchmark evaluator or task definition changed.
- A preflight typo pointed one image request at a nonexistent CoDesk-relative artifact path; the text preflight had succeeded, the bad attempt did not send an image, and the corrected image request passed. This is retained in `preflight/preflight-attempts.jsonl`.
- An early worker startup created `/mnt/raid1/mjh/CoDesk-V1-artifacts/remote-qwen-a6000-20260930-r01` under the existing `ywj` owner. The ownership check denied chmod; the process was stopped, and this directory was not deleted or modified further. Subsequent logs/artifacts are under `mjh`-owned paths. Do not touch that shared path without its owner’s approval.
- No model server or tunnel remains running after this run. The 4090 checkpoint is shared/read-only for this work and was not changed.
