# CoDesk Benchmark Handoff

## Current state

- Canonical repository: A6000 node at `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, branch `v0`.
- Benchmark scope: five frozen families, four software domains, 30 workflow templates after second-wave expansion.
- First 15 workflows and their previous 600-instance suite remain preserved under `benchmarks/codesk_v1/`.
- Final 600-task suite is separately versioned under `benchmarks/codesk_v1_final/`.
- Current final status is `OFFLINE_FINAL_SUITE_READY` only after generator metadata reports 600/600 runtime plan compilation and no missing implementation.
- No Guest, Docker, or Qwen was started during offline production.

## Next validation sequence

1. Run one real Guest setup/readiness/reset smoke for each new workflow, first verifying application identity and fixture contents.
2. Fix or defer any workflow with an unstable native GUI operation or unreliable hidden-state observer.
3. Run Solo A and Solo B gates before any shared condition.
4. Run the matching MA-ID and MA-SD schedules with equivalent initialized fixtures and serialized actor actions.
5. Preserve screenshots/action events and report exposure, observed interference, final outcome, recovery, and contamination separately.
6. Only after workflow-level real validation, freeze eligible templates and decide whether to expand fixed instance quotas.

## Evidence boundary

Offline CODE_READY and FakeBackend lifecycle pass do not establish model solvability, natural interference, recovery, or Guest compatibility. `FULL_HANDOFF_READY` is not claimed until real runtime validation has been completed.
