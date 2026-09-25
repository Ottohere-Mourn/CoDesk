# NEXT_STEPS

## V0 status

The V0 engineering target is met for two controlled real desktop cases: GUI+CLI shared CSV and GUI+Human Replay focus competition. The implementation is small by design. There is no evidence yet about LLM behavior, general coordination ability, task coverage, or benchmark novelty.

## Next bounded tasks

1. Exercise `OSWorldSharedEpisode` against one pinned OSWorld release and environment image once those assets are explicitly provisioned; adapt its evaluator to independent hidden-state assertions for co-actor outcomes.
2. Replace the toy Tk surface with one realistic application only after preserving deterministic state inspection and reset. Avoid copying a large OSWorld dataset/image until a target provider and storage budget are chosen.
3. Add actor schedule permutations and event-log schema/version validation, then run repeated episodes to characterize runtime variance.
4. Conduct another related-work/artifact search before writing any priority or novelty claim; include concurrent UI, shared desktop sessions, user replay, and transaction-level benchmarks.
5. For model integration, keep one container per episode and pass only role-scoped tool clients. Do not expose evaluator code, host paths, or expected outputs to model processes.

## Known engineering limitations

- Docker apt package versions are directly pinned and the base image is digest-pinned; transitive Ubuntu archive availability still depends on upstream retention.
- The model-facing process boundary is not implemented. Current scripted actors are trusted Python classes; role-scoped tools are API separation, not a security boundary against malicious code.
- Current interaction is deterministic serial interleaving inside one real environment. OS-level simultaneous keystrokes and timing races are not evaluated.
