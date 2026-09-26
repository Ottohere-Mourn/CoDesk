# NEXT_STEPS

## V0 status

V0 now has real OSWorld V2.1 Guest episodes for GUI+GUI using Writer and Calc, GUI+CLI using a Guest-local browser app with stale-cache updates, and GUI+Human Replay using independent browser form goals. Solo goals, joint-feasible schedules, interference controls, hidden-state evaluators, event traces, screenshots, and reset checks are present. The study is small and uses deterministic scripted actors with the pinned local QEMU runtime fallback.

## Next bounded tasks

1. Repeat each negative-control OSWorld condition from a clean Guest start. The positive focus-aware schedules now have two successful runs each; negative-control replication remains one run per task. Report condition-level counts and retain failed runs; do not interpret the mixed-condition aggregate as performance.
2. Add a Writer/Calc schedule that tests recovery after a focus steal while checking both saved files. Confirm independent solo solvability before comparing schedules.
3. Replace the deterministic Human Replay form action with a recorded user trajectory or live input source when human behavior becomes an evaluation target.
4. When access becomes available, run one official OSWorld task through its upstream evaluator and retry the pinned upstream runtime image. Continue labeling local-runtime evidence separately.
5. If model integration becomes useful, run a small smoke with one Guest per episode and role-scoped clients. Keep evaluator code, host paths, and expected outputs outside actor processes.

## Known engineering limitations

- Docker apt package versions are directly pinned and the base image is digest-pinned; transitive Ubuntu archive availability still depends on upstream retention.
- The model-facing process boundary is not implemented. Current scripted actors are trusted Python classes; role-scoped tools are API separation, not a security boundary against malicious code.
- Current interaction is deterministic serial interleaving inside one real environment. OS-level simultaneous keystrokes and timing races are not evaluated.
- The real-application study has a small number of hand-run episodes and retained debugging attempts. Its aggregate mixes solo, positive, and negative-control conditions and is descriptive only.
- The existing repeatability run has four fixed Docker/Xvfb schedules and 20 total episodes. Its timing excludes image build/reset and is not a capacity or latency benchmark.
- OSWorld V2.1 currently uses a local QEMU runtime compatibility image because the pinned upstream runtime could not be pulled; Guest/task versions remain pinned. V2.1 task and asset datasets are gated and the official task evaluator path remains unavailable on this host.
