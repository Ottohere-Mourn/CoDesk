# NEXT_STEPS

## V0 status

V0 now has real OSWorld V2.1 Guest episodes for GUI+GUI using Writer and Calc, GUI+CLI using a Guest-local browser app with stale-cache updates, and GUI+Human Replay using independent browser form goals. Solo goals, joint-feasible schedules, interference controls, hidden-state evaluators, event traces, screenshots, and reset checks are present. The study is small and uses deterministic scripted actors with the pinned local QEMU runtime fallback.

## Next bounded tasks

1. All three current local VLM solo smokes failed at the model action/grounding stage, while the evaluator and reset behaved correctly. Pause model-conditioned shared comparisons until a local model demonstrates a successful solo task.
2. If model work resumes, address GUI coordinate grounding or choose a simpler real application target, then rerun solo first. Only after solo success run the corresponding sequential, naive shared, and focus-aware episodes; attribute model errors separately from shared-focus interference.
3. Keep scripted GUI+Human Replay evidence separate. Existing real Guest form goals have independent solo and focus-aware cases; a model+Human episode is meaningful only after that model passes its solo task.
4. The three scripted negative controls have now each been repeated on fresh Guests with evaluator detection and reset verified. Future repeats should be bounded and reported as descriptive counts only.
5. When access becomes available, run one official OSWorld task through its upstream evaluator and retry the pinned upstream runtime image. Continue labeling local-runtime evidence separately.

## Known engineering limitations

- Docker apt package versions are directly pinned and the base image is digest-pinned; transitive Ubuntu archive availability still depends on upstream retention.
- Local VLM inference runs in a loopback-only host process that receives screenshots and task prompts. This is an engineering boundary against evaluator data exposure, not a hardened sandbox for arbitrary model code.
- Current interaction is deterministic serial interleaving inside one real environment. OS-level simultaneous keystrokes and timing races are not evaluated.
- The real-application study has a small number of hand-run episodes and retained debugging attempts. Its aggregate mixes solo, positive, and negative-control conditions and is descriptive only.
- The existing repeatability run has four fixed Docker/Xvfb schedules and 20 total episodes. Its timing excludes image build/reset and is not a capacity or latency benchmark.
- OSWorld V2.1 currently uses a local QEMU runtime compatibility image because the pinned upstream runtime could not be pulled; Guest/task versions remain pinned. V2.1 task and asset datasets are gated and the official task evaluator path remains unavailable on this host.
