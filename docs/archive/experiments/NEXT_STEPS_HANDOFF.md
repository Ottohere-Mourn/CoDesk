# CoDesk next-step handoff

## Frozen scope and evidence

- V1 is frozen at 3 families / 8 workflow templates. Do not expand scope during the next phase.
- All 8 templates have scripted validation; this is not model evidence.
- Focus F-01 has real Qwen evidence: Solo pass; MA-ID 2/2 joint pass; MA-SD 2/2 joint fail. Writer actions were observed executing while Calc was foreground.
- Clipboard C-01 and Application Context A-01 still need real Qwen pilots.
- The 200-task plan is 8 templates × 25 fixed instances; generation has not formally begun.
- Selection/Active Object is merged into Application Context. Workspace Object Lifecycle is outside V1.
- Shared-filesystem/backend engineering (9p/virtiofs/NFS) is frozen; do not reopen.
- The 4090 remote-inference -> A6000 Guest path has a real Writer Solo success record. It is a single-task path validation, not evidence for C-01/A-01.

## P0 — immediately after resource recovery

1. Coordinate a genuinely free two-GPU allocation. Latest 4090 snapshot shows fzx compute PIDs on all 8 GPUs; do not start Qwen or the claim tool against occupied cards.
2. Recheck the existing 4090 inference endpoint -> A6000 Guest path with the smallest already-calibrated Writer Solo smoke. Verify screenshot/observation, real model action, evaluator, provenance, artifacts and reset. Mark infrastructure faults INVALID_INFRA.
3. Run C-01 Qwen: Solo A/B, MA-ID, MA-SD.
4. Run A-01 Qwen: Solo A/B, MA-ID, MA-SD.
5. Begin with 2 repeats per condition; stop if outcomes agree, add a third only for disagreement. Keep scheduled exposure, observed interference, final outcome and autonomous recovery separate. Hold model, prompt, task/evaluator, schedule, budget and task-relevant initial state fixed across MA-ID/MA-SD.

## P1 — after Qwen pilot closure

1. Update QWEN_FAMILY_PILOT_REPORT.md with all valid/invalid attempts, logs, screenshots, exposure/interference/outcome/recovery and attribution.
2. Decide whether each family has model-level evidence; never mix scripted and model outcomes.
3. Only then begin fixed-instance generation: 8 frozen templates × 25 instances. Start with a small batch per template and validate deterministic regeneration, hashes, independent goals, exact oracle and deduplication before generating the remainder.

## P2 — large-compute execution handoff

1. Give the executor frozen instance manifests and exact task/evaluator version hashes.
2. Run approved Solo / MA-ID / MA-SD with matched task-relevant backend topology, schedule and budgets; isolate run IDs/artifacts and preserve failures.
3. Bound concurrency using observed CPU, RAM, GPU, Guest capacity and resource ownership. The claim helper is optional and is not a host-wide reservation against non-cooperating users.
4. Aggregate per-instance exposure, interference, success, recovery, reset, provenance and invalid-infrastructure status. Do not discard failures or invalid attempts.

## P3 — final analysis and paper package

1. Compare shared-desktop results against Solo and independent-desktop controls; separate capability failures from evidence-supported interaction interference.
2. Report effect sizes, uncertainty intervals, denominators, invalid infrastructure, recovery and family/task heterogeneity. Small pilots are mechanism evidence, not stable performance estimates.
3. Produce benchmark card/protocol, reproducible task/evaluator/run package, main results tables, failure taxonomy, limitations and evidence-linked paper narrative.

## Invariants

- Do not expand beyond frozen scope during pilot closure.
- Do not start shared conditions if either actor's Solo control is invalid or fails.
- MA-ID and MA-SD preserve equivalent task-relevant workspace/backend topology; shared desktop is the changed factor.
- Do not claim desktop-sharing effects from backend-topology changes.
- Preserve every attempt and original artifact; do not tune evaluator rules to observed results.
- Never docker prune, stop unknown resources, or touch another user's processes/data.
