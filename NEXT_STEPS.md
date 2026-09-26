# NEXT_STEPS

## V0 status

The V0 engineering target is met for two controlled real Docker/Xvfb desktop cases: GUI+CLI shared CSV and GUI+Human Replay focus competition. A pinned OSWorld V2.1 Guest is now also running: GUI+CLI success, exact stale-overwrite conflict detection, repeated deterministic output, and clean Guest reset have passed. OSWorld multi-window GUI focus/Human Replay and official task scoring are still pending. The implementation is small by design. There is no evidence yet about LLM behavior, general coordination ability, task coverage, or benchmark validity.

## Next bounded tasks

1. Stabilize a real Guest multi-window focus protocol, then port the two-window GUI+Human Replay case to OSWorld and verify both independent goals, focus theft, recovery, and reset through Guest state.
2. Resolve access to the gated V2.1 task/assets and rebind one official task evaluator without exposing state to actors; the custom shared CSV case itself is not an official scored benchmark task.
3. The native V0 Tk/Xvfb focus and CSV cases already provide deterministic control conditions. Add a real application (for example, LibreOffice Calc) only after a deterministic hidden-state evaluator and reset are available in the Guest.
4. Event-log schema/version validation is implemented for schema V1, exposed through `python -m swcub.cli validate-events`, and covered by tests. The initial two task specifications now live in `tasks/v0_manifest.json` with a structural validator. A bounded five-episode-per-policy replay check covers both CSV actor orders, focus recovery, and stale-focus failure; it checks scripted determinism and rough runtime only.
5. For model integration, keep one Guest per episode and pass only role-scoped tool clients. Do not expose evaluator code, host paths, or expected outputs to model processes.

## Known engineering limitations

- Docker apt package versions are directly pinned and the base image is digest-pinned; transitive Ubuntu archive availability still depends on upstream retention.
- The model-facing process boundary is not implemented. Current scripted actors are trusted Python classes; role-scoped tools are API separation, not a security boundary against malicious code.
- Current interaction is deterministic serial interleaving inside one real environment. OS-level simultaneous keystrokes and timing races are not evaluated.
- The repeatability run has four fixed policy schedules and 20 total episodes. Its timing excludes image build/reset and is not a capacity or latency benchmark.
- OSWorld V2.1 currently uses a local QEMU runtime compatibility image because the pinned upstream runtime could not be pulled; Guest/task versions remain pinned. V2.1 task and asset datasets are gated and the official task evaluator path remains unavailable on this host.
