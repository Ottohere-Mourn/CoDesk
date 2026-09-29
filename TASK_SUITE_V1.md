# CoDesk Task Suite V1

**State:** design freeze candidate plus offline contract code. This phase did not launch a Guest, model, application, or real episode. Only the Writer/Calc scripted anchor has prior three-condition scripted evidence as reported in the project history; the registered GUI+CLI task is an existing protocol anchor. All other entries are design-only.

## Research question and task boundary

CoDesk V1 asks whether independently goal-directed actors lose performance, contaminate one another's work, or need extra recovery when their actions share one live desktop session. Its primary treatment is the shared control plane: active window, keyboard, pointer, modal stack, clipboard, and application context. GUI+CLI shared-record work is retained as an auxiliary state-consistency comparison, not the definition of the benchmark.

The unit is a two-actor task with two independently scorable goals. Every actor must pass its Solo control. Joint feasibility is stated as a simultaneous exact final state. MA-ID and MA-SD preserve the same goal text, application seed, actor budget, and schedule; desktop topology is the intended contrast. The task suite does not count independent workers on independent screens as shared-desktop interaction.

## Related-work boundary checked for V1

The nearest GUI-computer-use work reviewed is materially different in its execution boundary:

- **ParaGUIBench** uses multiple GUI workers with separate full desktop/container instances and per-worker mouse/keyboard focus, connected through a shared mounted filesystem. Its tasks cover web/file search, shopping/navigation, file operations, and search-and-write. It is a close parallel-GUI/shared-file baseline, but its published setup does not put workers on one live display/input session. See the [paper, especially §3.1–3.3](https://arxiv.org/html/2607.22689) and [task/code repository](https://github.com/pkgunboat/ParaGUIBench).
- **OSWorld-Noisy / ENVS** keeps OSWorld-style single-agent tasks and evaluators while inserting deterministic, recoverable perturbations such as dialogs, overlays, and benign user activity. Its user activity is interference/noise, not a second actor with an independently scored task goal. CoDesk must therefore give the second actor a real goal and score both actors. See [paper, §3 and benchmark construction](https://arxiv.org/html/2606.22948) and [code](https://github.com/ArtysicistZ/ENVS).
- **DeskCraft** includes multi-turn user interaction, interruptions, and user-simulator feedback in desktop workflows. This is relevant to interruption and recovery, but its protocol is centered on one agent interacting with a user simulator; it does not establish simultaneous independent actors sharing keyboard, pointer, and focus. See [paper, task protocol](https://arxiv.org/html/2606.03103) and [code](https://github.com/mrwwk/DeskCraft).
- **WeaveBench** evaluates one computer-use trajectory that combines GUI and CLI/code interfaces in a task. That motivates the auxiliary GUI+CLI track, but does not itself compare independent actors contending for one desktop session. See [paper](https://arxiv.org/html/2606.09426), [project](https://weavebench.github.io), and [Microsoft Research record](https://www.microsoft.com/en-us/research/publication/weavebench-a-long-horizon-real-world-benchmark-for-computer-use-agents-with-hybrid-interfaces/).
- **OSWorld** remains the single-agent desktop baseline and supplies the Guest/desktop execution substrate, not a multi-actor shared-input protocol. See [official repository](https://github.com/xlang-ai/OSWorld) and [NeurIPS benchmark record](https://proceedings.neurips.cc/paper_files/paper/2024/hash/5d413e48f84dc61244b6be550f1cd8f5-Abstract-Datasets_and_Benchmarks_Track.html).

These sources support a scope distinction, not a novelty claim. Before claiming a first benchmark of this kind, a fresh citation-chain and artifact audit is still required at paper submission time. Source check date: 2026-09-29.

## V1 family and instance plan

Eight instances are the initial design target across four families. Two are existing anchors; six are prospective. A design-only task is not yet executable simply because its contract is in the registry.

| ID | Family / status | Actor A goal | Actor B goal | Shared object and natural interaction | Joint oracle and attribution |
|---|---|---|---|---|---|
| `CODESK-TA-OFFICE-001` | Focus/input routing; scripted anchor | Save exact Writer text | Set Calc B2 and preserve other cells | Same desktop focus, keyboard and pointer; normal Writer/Calc window activation interleaves | Existing exact saved ODF evaluator checks both outputs and contamination; attribute only when focus/input events precede the mismatching action |
| `CODESK-TA-CONTEXT-002` | Focus/input routing; design-only | Append exact review sentence in Writer | Enter exact audit label in Calc | B completes its own valid Calc step between A's Writer keystrokes; tests focus revalidation across a compound action | Exact ODF content/cells and wrong-window/other-cell inspection; evidence must link the focus change to the action |
| `CODESK-TB-CLIPBOARD-001` | Clipboard ownership; design-only | Transfer `REF-7319` to its Writer destination | Transfer `BATCH-204` to its Calc destination | B's valid copy replaces the session clipboard after A copies; focus may still be correct | Exact source/destinations plus clipboard generation trace; wrong value alone is insufficient attribution |
| `CODESK-TB-CLIPBOARD-002` | Clipboard ownership; design-only | Preserve a two-cell Calc TSV transfer | Place exact ticket phrase in Writer | Text copy changes a shared multi-cell clipboard payload/format; probes cell boundaries rather than only token value | Saved cell matrix/document plus private clipboard format/generation; exact adjacent-cell contamination check |
| `CODESK-TC-MODAL-001` | Window/dialog competition; design-only | Save Writer to exact ODT path/format | Save Calc to exact ODS path and preserve cell value | Actors open their own save/format dialogs; other dialog may cover a waiting target | Reopened file content, exact path/format, and modal-owner-at-action trace; no forced wrong confirmation |
| `CODESK-TC-WINDOW-002` | Window/dialog competition; design-only | Save Writer review copy | Download assigned CSV while preserving existing reference | Browser's normal download decision changes the active window while Writer has a separate persistence goal | File hashes, exact paths, saved ODF and prompt/window event trace; destructive overwrite is never injected |
| `CODESK-TD-STALE-MERGE-001` | GUI+CLI shared state; registered anchor | Set GUI status, preserve CLI note | Set CLI note, preserve GUI status | GUI cached whole-record snapshot and CLI update address one record | Existing authoritative backend evaluator checks both fields/schema/revision; lost update requires read/write revision evidence |
| `CODESK-TD-APPEND-002` | GUI+CLI shared state; design-only | Append unique GUI review entry | Append unique CLI review entry | Both read and append a shared activity log; tests truncation, duplicate retry, and append completeness | Parse exact entry multiset/counts and schema; attribute only with write/revision evidence |

### Why these are not eight surface variants

The four families expose different shared resources and evaluator evidence: (1) OS focus/input target, (2) session-global clipboard payload independent of focus, (3) modal/window ownership and persistence action semantics, and (4) backend/file revision and append integrity. The second instance in a family is retained only if an offline contract and later real pilot show a distinct evaluator signature. In particular, Clipboard 002 is a hypothesis about structured payload boundaries; drop it if it reduces to the same lost-token outcome as Clipboard 001. The two window tasks likewise need distinct action evidence, not just different application names.

## Control protocol

| Condition | Desktop/input topology | State control | Interpretation |
|---|---|---|---|
| Solo | Run A and B separately on clean resets | Same task seed; inactive actor's target remains at its seeded value | Establish both individual capabilities and evaluator correctness |
| MA-ID | One independent desktop/input session per actor, same goals and frozen schedule | Desktop-contention tasks use non-colliding output artifacts; shared-state tasks use isolated backend clones | Control for independent work and orchestration without shared state mutation |
| MA-SD | Both actors on one live Guest desktop/session; coordinator serializes action submission | Same goals, actor budgets and schedule; the natural shared resource is common | Estimate extra loss/contamination/recovery associated with sharing the actual resource |

Do not compare MA-ID and MA-SD if their actor order, number of opportunities, reset seed, model budget, or evaluator changes. Do not silently share a backend in a desktop-only control: where a task's mechanism is explicitly a shared backend, clone it for MA-ID and use one backend in MA-SD. Record this topology per instance.

## Per-episode measures

Primary outcomes: actor-A success, actor-B success, joint success (both plus integrity invariants), and Solo-to-MA condition delta. Additional measures are:

- **Interference:** exact target/cross-target mismatch with an event chain identifying another actor's intervening change to the named shared resource. Report unsupported cases as unattributed.
- **Coordination failure:** task goal lost after a valid partner action, stale/unowned context action, duplicate/truncated append, or wrong modal/payload use. Keep mechanism-specific counts separate.
- **Recovery:** conflict detection evidence, recovery actions after the first conflict, actions/time until both exact goals hold, and whether recovery preserves the partner's goal.
- **State consistency:** exact final document/cell/file/backend values, schema, source preservation, and duplicate/unintended writes.
- **Work and environment:** per-actor actions, elapsed active time, focus/modal/clipboard generation changes, reset success, and environment-validity status.

All success is determined by task code against hidden authoritative state. Screenshots and event evidence support attribution; a vision-language judge does not decide correctness.

## Validation gates and current boundary

For every prospective instance: prove A Solo, prove B Solo, demonstrate an oracle-positive joint state, run a negative-control schedule that allows organic failure without force-routing, demonstrate recovery availability, test reset, and inspect an event-linked failure signature. Then run a small real-Guest pilot. Do not promote from design-only on unit tests alone.

Offline code added in this phase validates the eight-entry registry, review-only config, exact-state oracle helper, reset-state helper, and evidence-gated interaction metrics. It does not implement app setup for the six new instances, connect those instances to `run_codesk_experiment.py`, or establish real-Guest success. See [registry](TASK_REGISTRY_V1.md) and [implementation checklist](TASK_SUITE_V1_IMPLEMENTATION.md).
