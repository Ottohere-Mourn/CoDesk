# NEXT_STEPS

## V0 status

The V0 engineering target is met for controlled Docker/Xvfb and pinned OSWorld V2.1 Guest cases: GUI+CLI shared CSV success and stale-overwrite detection; GUI+Human Replay independent window goals, focus recovery, and stale-focus misdirection; and clean Guest reset. The OSWorld Guest results use deterministic scripted actors and a local runtime fallback. Official task scoring, model behavior, GUI+GUI coordination, and broader task coverage remain untested.

## Next bounded tasks

1. Resolve access to the gated V2.1 task/assets and rebind one official task evaluator without exposing state to actors; the custom CSV and terminal-focus cases are not official scored benchmark tasks.
2. Add one realistic multi-application task (for example, LibreOffice Calc) while preserving exact hidden-state checks and reset. GUI+GUI scheduling and simultaneous input races need separate scenarios and instrumentation.
3. Rerun the scripted Guest cases on the upstream official Docker runtime when registry access is available, then verify the setup on a second host before making reproducibility claims.
4. Event-log schema/version validation is implemented for schema V1, exposed through `python -m swcub.cli validate-events`, and covered by tests. The initial two task specifications now live in `tasks/v0_manifest.json` with a structural validator. A bounded five-episode-per-policy replay check covers both CSV actor orders, focus recovery, and stale-focus failure; it checks scripted determinism and rough runtime only.
5. For model integration, keep one Guest per episode and pass only role-scoped tool clients. Do not expose evaluator code, host paths, or expected outputs to model processes.

## Known engineering limitations

- Docker apt package versions are directly pinned and the base image is digest-pinned; transitive Ubuntu archive availability still depends on upstream retention.
- The model-facing process boundary is not implemented. Current scripted actors are trusted Python classes; role-scoped tools are API separation, not a security boundary against malicious code.
- Current interaction is deterministic serial interleaving inside one real environment. OS-level simultaneous keystrokes and timing races are not evaluated.
- The repeatability run has four fixed policy schedules and 20 total episodes. Its timing excludes image build/reset and is not a capacity or latency benchmark.
- OSWorld V2.1 currently uses a local QEMU runtime compatibility image because the pinned upstream runtime could not be pulled; Guest/task versions remain pinned. V2.1 task and asset datasets are gated and the official task evaluator path remains unavailable on this host.
