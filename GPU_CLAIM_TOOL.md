# GPU claim helper

## Source audit

The closest source in sibling project long-video-token-compression is scripts/gpu_watcher.py, indexed in that project's scripts/README.md. It polls nvidia-smi memory/utilization, then starts a caller-provided command after two eligible polls by default: 20-second polling, <=1000 MiB used, <=5% utilization (about 40 seconds total). It never kills/preempts existing processes, but it does not inspect compute PIDs, offer a separate owner-verified stop path, or wait two minutes. The task-specific watch_videoeval_pro_longva_pilot.py uses 10-second intervals and two stable polls (about 20 seconds). Both depend on Python standard library and nvidia-smi.

CoDesk scripts/resource/gpu_claim.py is a minimal safety-hardened adaptation of that poll-and-launch approach. Requirements: Python 3, nvidia-smi, Linux /proc; no third-party Python dependency. It was added but NOT started in this round.

## Rule

Every requested physical GPU must continuously pass all checks for 120 seconds: zero compute PIDs (even if utilization is 0%), used memory <=512 MiB, and utilization <=5%. Any failed sample resets the whole window. Query/schema errors fail closed. The helper resamples immediately before starting the command, then records its owner token, PID, process start time/group, selected GPUs and status in a run-specific ownership.json.

Starting the command is the claim; this does not create a host-wide reservation against non-cooperating schedulers. A race remains between the last sample and process launch. Coordinate GPU ownership before use.

## Commands (not run in this round)

Start in the foreground with a new run directory:
python scripts/resource/gpu_claim.py watch --gpu-indices 2,3 --run-dir artifacts/gpu-claims/<new-run-id> -- python -u path/to/command.py --your-args

Inspect:
python scripts/resource/gpu_claim.py status artifacts/gpu-claims/<run-id>/ownership.json

Stop:
python scripts/resource/gpu_claim.py stop artifacts/gpu-claims/<run-id>/ownership.json

The watcher writes ownership.json and worker.log. Ctrl-C/SIGTERM uses the same cleanup path. Stop verifies UID, boot ID, watcher/worker PID start time, owner token in /proc, and dedicated process group before signaling. It refuses on mismatch, signals only this run's watcher and launched worker session, and never deletes artifacts or touches containers.
