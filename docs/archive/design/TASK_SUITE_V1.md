# CoDesk Task Suite V1

**Revision:** backend-controlled comparison and mechanism de-duplication, based on `b645f24`.

**Evidence boundary:** this phase only changed offline design/code. It did not launch a Guest, model, or application. Project history reports prior Writer/Calc scripted three-condition validation, but static runner inspection shows old MA-ID used separate Guests/workspaces while MA-SD used one Guest. Those runs validate task/setup/evaluator behavior, but do not isolate a causal shared-desktop effect. The GUI+CLI anchor is registered in the prior protocol and was not rerun here. Clipboard and modal tasks below remain design-only.

## Scope and experiment boundary

CoDesk's core outcome is the extra effect of sharing a live desktop control plane: focus, keyboard, pointer, window/modal stack, and session clipboard. An application backend or shared filesystem is a separate factor. A contrast that changes both desktop topology and backend topology cannot identify a shared-desktop effect.

Keep these two studies distinct:

1. **Shared-desktop core:** hold the application/backend instance, seed, actor goals, budgets, schedule, and evaluator constant between MA-ID and MA-SD. MA-ID uses independent desktop/input sessions connected to the same backend; MA-SD uses one session. Use unique non-overlapping files/fields where the task is meant to test only desktop controls.
2. **Shared-state auxiliary:** hold the same authoritative backend instance constant in MA-ID and MA-SD as well. Both conditions may experience backend-level stale state. The MA-ID vs MA-SD contrast estimates only additional desktop-mediated effects. Add backend-private cells as a separate factor if the backend effect itself is being measured; do not call the diagonal `MA-ID/private backend` vs `MA-SD/shared backend` a desktop-sharing comparison.

For a causal decomposition of state-consistency tasks, record a 2x2 topology: desktop `{independent, shared}` × backend `{private, shared}`. The controlled shared-desktop effect is the independent-vs-shared desktop contrast at a fixed backend level. If the environment cannot connect independent desktop sessions to the same backend, defer that causal claim rather than silently substituting isolated copies. Static inspection of `scripts/run_writer_calc_v1.py` confirmed its previous MA-ID made a separate Guest per actor, so the new same-backend condition is not covered by those old results.

Each task has two independently scored goals. Both must pass their own Solo controls, and their exact desired outputs must be simultaneously satisfiable. Actor actions remain autonomous. The scheduler may arrange a deterministic opportunity for interaction, but may not inject the wrong clipboard value, redirect an action, or require an error.

## Literature boundary checked

ParaGUIBench is the nearest parallel GUI benchmark reviewed: its workers use separate full desktops and input focus while coordinating over a shared mounted directory, so it covers parallel execution and artifact coordination rather than one shared live input session. [Paper §III-A–C](https://arxiv.org/html/2607.22689), [repository](https://github.com/pkgunboat/ParaGUIBench).

OSWorld-Noisy evaluates recoverable interruptions layered over original single-agent OSWorld tasks; its concurrent benign activity is a perturbation source, not a second independent goal that is jointly scored. [Paper §4 and Appendix B](https://arxiv.org/html/2606.22948), [code](https://github.com/ArtysicistZ/ENVS). DeskCraft's interaction protocol advances user phases in response to `agent_ask`, fixed step count, or completion and uses a user simulator; this is close to interruption/recovery but not independent actors sharing the same input device. [Paper §3.3 and Appendix B](https://arxiv.org/html/2606.03103), [code](https://github.com/mrwwk/DeskCraft). WeaveBench requires one agent to interleave GUI and CLI/code operations in a task trajectory; it motivates the auxiliary hybrid interface track but does not test two actors sharing a desktop. [Paper](https://arxiv.org/html/2606.09426), [project](https://weavebench.github.io). OSWorld remains the single-agent live desktop substrate. [Official repository](https://github.com/xlang-ai/OSWorld).

These comparisons establish a scope distinction, not an absolute novelty claim. Artifact/version and citation-chain review remains necessary before publication.

## Retained V1 suite

The suite is reduced to four entries across four families; the former eight-entry list is not retained as eight tasks.

| ID | Family / status | Independent goals | Mechanism and controlled oracle |
|---|---|---|---|
| `CODESK-TA-OFFICE-001` | Focus/input routing; prior scripted anchor, revised control unvalidated | Writer saves exact text; Calc sets B2 and preserves all other cells | Existing saved-ODF evaluator and focus/input event trace. Revised MA-ID and MA-SD require the same workspace/backend binding; only input-session topology differs. |
| `CODESK-TB-CLIPBOARD-001` | Clipboard ownership; design-only priority pilot | Writer transfers its source token to its destination; Calc transfers a different source token to its destination | Distinguishes session clipboard replacement from focus by observing clipboard generation/payload, active/focused target, and exact final destination. Full plan below. |
| `CODESK-TC-MODAL-001` | Window/dialog competition; design-only | Writer saves exact ODT at its path; Calc saves exact ODS at its path and preserves its assigned value | Exact persisted paths/content plus active modal/window owner at action. No confirmation key is forced into the wrong dialog. |
| `CODESK-TD-STALE-MERGE-001` | GUI+CLI shared state; existing auxiliary anchor | GUI changes status; CLI changes note; both preserve the partner field | Existing authoritative record evaluator. Backend identity is the same in MA-ID and MA-SD, so backend stale-write effects cannot masquerade as a desktop-sharing effect. |

### Candidate de-duplication decisions

| Prior candidate | Decision | Reason |
|---|---|---|
| Focus 002, multi-step focus handoff | Merge as a stress variant of the existing focus family | Same active-window/keyboard-routing mechanism and exact destination-contamination signature. Retain only if compound-action timing gives a different causal/evaluator signature. |
| Clipboard 002, multi-cell TSV payload | Merge as a payload-format variant of Clipboard 001 | It still tests replacement of the same session-global clipboard. Cell-boundary corruption is a useful secondary signature, but not yet evidence for a separate task. |
| Window 002, browser download prompt | Defer as a modal-context variant | It repeats active-window/modal ownership while adding download policy and filesystem overwrite risks. Keep only if it exposes a distinct, observable dialog-ownership failure. |
| Append 002, GUI+CLI activity log | Defer as an auxiliary consistency candidate | Exactly-once append semantics may be distinct from stale whole-record overwrite, but it expands the auxiliary transaction family and lacks a validated GUI append path. |

The deferred IDs live in `deferred_variants` metadata, not in the benchmark task count or experiment config.

## Outcome accounting

Never collapse exposure, terminal task result, and recovery into one “interference rate.” For each episode record three independent blocks:

1. **Exposure:** count declared exposure opportunities and actually observed resource changes separately. Tag each with `source=natural` or `source=scheduled_stress` and a unique `opportunity_id`. The episode exposure rate is unique opportunities with at least one observed exposure / declared opportunities, reported separately by source; raw exposure-event counts are also retained. A scheduled competition window is a stress opportunity; it is not a failure and is not a natural-model failure rate.
2. **Task outcome:** evaluate Actor A, Actor B, and joint success from the hidden exact-state oracle, independently of whether an exposure happened. Overall model task-failure rate uses all valid assigned episodes as its denominator. Conditional failure given exposure may be a secondary diagnostic only and must state its denominator.
3. **Recovery:** record conflict evidence/detection, recovery actions, and final success after a recovery action as separate fields. `recovery_success` is not applicable if no conflict/recovery occurred. Report operational recovery from trace and final state; do not infer internal model awareness.

If an episode has a failing final state but no event chain linking it to the shared resource, classify it as model/task failure or unattributed; do not assign a shared-desktop cause based on its condition label.

## Clipboard 001 task protocol

**Seed:** two stable source values in distinct saved artifacts; two empty, distinct destination fields; known clean session clipboard. Actor A is assigned the Writer source/destination; actor B the Calc source/destination. Token values are exact and different. Each source remains available for recovery. Both targets are checked after saving and reopening.

**Solo controls:** run A alone and B alone from clean fixtures. Each must demonstrate actual GUI copy then paste, achieve its own exact destination, preserve its source, and leave the inactive artifact unchanged. Also run a reset/clipboard-clear check. If either Solo goal fails, do not interpret paired failures.

**MA-ID:** two independent displays/input sessions with one constant workspace/backend identity and separate X11 clipboard selections. Use the same instructions, per-actor budgets, turn schedule, source seed, distinct destinations, and oracle as MA-SD. This checks that shared files/backend alone do not create the clipboard interaction.

**MA-SD:** one live Guest desktop/X server and one `CLIPBOARD` selection shared by both actors; same workspace/backend, goals, budgets, schedule, and evaluator as MA-ID. The predeclared stress schedule places B's valid copy/paste between A's copy and paste as an opportunity. The coordinator does not perform A's paste, alter either payload, or command an incorrect action. A may re-observe, re-copy, verify its payload, refocus, and recover normally.

**Recovery positive control:** run scripted actors that use the same ordinary GUI copy/paste actions. When the observer reports that A's payload changed, the recovery actor reselects A's stable source, copies it again, checks that the observed generation/digest is A's, focuses A's destination, pastes, saves, and verifies both outputs. This is only a recoverability/evaluator control, never mixed into model success statistics. Real model MA-SD episodes retain autonomy; a recovery-instruction prompt, if later tested, is a separately labeled intervention.

## Clipboard observation and attribution plan

The current OSWorld adapter logs action source, observed revision, and active-window title before/after an action. A repository code search found no clipboard payload, selection owner, or generation observer. Therefore the current artifacts cannot yet distinguish clipboard replacement from wrong focus.

Add a private Guest-side observer before episodes:

- **Owner:** sample the X11 `CLIPBOARD` selection owner XID and X server timestamp. Subscribe to XFixes owner-change notification if available. Do not equate owner XID/process with an actor: clipboard managers may own the selection.
- **Payload/generation:** sample offered `TARGETS`/MIME types and a digest of canonical text (`UTF8_STRING`, fallback `STRING`) before/after every actor action. Increment a task-local generation when owner/timestamp or digest changes. Owner-change events alone can miss same-owner replacement; the ICCCM says an owner should reacquire ownership if its selection value changes, but measure payload as a cross-check. Do not expose hashes or state to the agents.
- **Logical owner attribution:** link a changed digest to an Actor only when the event is bracketed by a single actor's copy/cut action and the digest matches that actor's known source. If multiple candidate actions, clipboard-manager handoff, missing sample, or unsupported format makes it ambiguous, store `logical_actor=null` and do not claim which actor overwrote it.
- **Focus and paste target:** log intended application, active X11 window XID/title, and focused accessibility object/Calc cell immediately before paste where available; record the paste action's actor/source and resulting saved Writer/Calc state. Active window alone is not proof of focused widget. If recipient evidence is missing, keep routing attribution unknown.
- **Cause rules:** clipboard-supported case requires (a) A copied its expected payload, (b) another actor's action changed clipboard generation/payload before A's paste, (c) A's paste was directed to A's expected target, and (d) final state or trace shows the wrong/missing payload. Focus-routing case requires target-window/widget mismatch or wrong destination evidence. If both occur, allow a multi-cause/ambiguous category; do not force a single label.
- **Observer validity:** first test whether read-only selection sampling itself changes ownership, stalls copy/paste, or changes actor timing. Compare observer-on/observer-off scripted Solo controls. If sampling perturbs the environment or misses an in-action change, mark instrumentation invalid and do not use those episodes for causal claims.

X11 defines a selection owner window and a server timestamp; XFixes provides selection-change notifications. The ICCCM describes selection transfer and instructs a client whose selection value changes to reacquire ownership, but owner identity still does not identify the benchmark actor. See [XGetSelectionOwner/XSetSelectionOwner reference](https://xorg.freedesktop.org/archive/X11R6.8.0/doc/XGetSelectionOwner.3.html), [X.Org release notes on XFixes selection notification](https://www.x.org/archive/X11R6.8.1/PDF/RELNOTES.pdf), and [ICCCM selection conventions](https://xorg.freedesktop.org/archive/X11R7.7/doc/xorg-docs/icccm/icccm.html).

## Promotion gate

Do not promote Clipboard 001 from design-only until: observer fidelity and non-perturbation are demonstrated; both Solo controls and MA-ID joint state pass; scheduled stress produces logged exposure without forced action; clipboard and focus error signatures can be separated; scripted recopy recovery restores both goals; reset clears selection and restores exact artifact seeds. Then run limited real-agent evaluation and report natural and scheduled-stress strata separately.
