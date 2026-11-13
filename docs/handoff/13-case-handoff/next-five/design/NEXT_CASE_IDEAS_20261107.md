# Next practical case ideas ? design audit (2026-11-07)

Status: concept-screening only. No task fixture, model request, or formal experiment has been run for these ideas; one read-only Guest capability gate is recorded below. This note is intentionally outside the 16-case qualified roster.

## What the earlier results teach us

1. The robust recipe is not ?make the shared arm harder.? Freeze the same legitimate two-role workflow for every arm, use a stateful surface both actors naturally touch, and evaluate the consequential persisted business artifact.
2. A useful shared failure is a valid but wrong business output with a visible causal chain: expected target/state -> ordinary action by the second actor -> changed shared state -> first actor's intended action -> wrong persisted destination/value. Wrong reasoning or an omitted step alone is not enough.
3. A deterministic interleaving is a causal control, not model evidence. First prove exact isolated completion, target negative, and sham positive controls. Then one frozen GPT-6-Sol triplet; retain recovery as PASS and every invalid attempt.
4. Macro-workflow novelty and mechanism novelty differ. W1 is a useful receiving/QA workflow but explicitly reuses C-03's clipboard mechanism. DATA-REL1 similarly reuses a stale-business-state pattern. Count and describe them accordingly.
5. The validated roster already covers focus/input, clipboard, browser-tab context, active object/undo, shell CWD, viewport, reviewer identity, and stale business artifacts. Another tiny text/cell/form example is a poor next step. Prefer a materially different everyday artifact and an independently measurable shared state.

## Candidate ranking

Scores (1?5) are design judgments, not empirical results.

| Candidate | Everyday workflow | Mechanism distance from current roster | Exact oracle | Hybrid feasibility | Decision |
|---|---:|---:|---:|---:|---|
| PRINT-ROUTE1 - facilities dispatch packet routing | 4 | 5 | 5 | 0 | NO-GO in pinned Guest: no local queues/default; do not synthesize printers |
| ATTACH-EVIDENCE1 ? repair evidence filing | 5 | 2 | 5 | 4 | Useful workflow variant; overlap with S-01/A-01 must be accepted |
| TZ-SCHEDULE1 ? regional appointment handoff | 4 | 4 | 3 | 1 | Park: normal desktop timezone mutation may be unnatural and platform-dependent |

No candidate is currently ready to run. Promote none until its falsification gate passes.

## Host and Guest capability checkpoint (2026-11-07 16:03 +0800; pre-probe read-only snapshot)

- HealthCare root volume: 29 GiB free of 1.8 TiB (99% used). RAID1 has about 1.3 TiB free. Available RAM was 166 GiB, but 2 GiB swap was exhausted. No active Docker container or QEMU Guest was observed.
- A bounded search of the checked-out OSWorld desktop/provisioning sources found no documented CUPS / CUPS-PDF / printer-queue provisioning. That does not prove printers are absent from the actual qcow2 image.
- The OSWorld docker_vm_data directory resolves to RAID1, but the exact pinned Case2 base image used by the smoke runner (/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2) is a 14,891,810,816-byte regular file on the root filesystem, not a symlink. The 26 GiB Case-4 image was not checked in this candidate gate.
- Decision at this pre-probe snapshot: PRINT-ROUTE1 remained unresolved, not passed and not conclusively no-go. Do not start a Guest until the runner's overlay/log destinations are verified to remain on RAID1 and a fresh resource preflight is acceptable. Prefer a read-only image-inspection tool only after disk risk is addressed; do not apt-install large utilities on the 99%-full root volume.



---

## Candidate A: PRINT-ROUTE1 ? field-service dispatch and print-queue routing

### User-facing workflow

A small facilities desk closes the day's work-order handoff. Actor A validates two synthetic work orders, prepares technician job sheets and visitor access slips, checks that each packet is complete, and prints the field packet to the ordinary FIELD-DESK destination. Actor B resolves a normal safety exception for a different work order, produces the required restricted safety cover sheet, and prints it to the ordinary SAFETY-HOLD destination. Their outputs are separate, realistic documents; no one is instructed to change or ignore A's setting.

Use synthetic names, room numbers, and work-order IDs only. Expected artifacts are exact print jobs with content hashes, destination queue, originating app/document, and job timestamp.

### Primary shared state and causal signature

The candidate mechanism is a persistent, shared default print destination / last-selected printer in the Guest desktop. B's normal safety print changes that destination. A later prints a valid field packet while acting on the earlier expectation. A target failure requires the exact field packet to be spooled to SAFETY-HOLD instead of FIELD-DESK; content omission, wrong work order, failed printing, or a recovered/correctly rerouted job does not qualify.

MA-ID gets separate cloned Guests, so B's printer-default change must not affect A's print destination. Shared and Shared+Lock use one Guest and the identical two-role task. The lock is per tool call: it should not protect the interval between A observing/choosing a destination and printing after B's independent job. Record the actual lock and tool schedule; do not claim simultaneous print-call contention unless measured.

### Oracle and causal evidence

The exact state oracle checks:
- every requested job was generated exactly once;
- all required fields and document hashes are exact;
- A's packet is in FIELD-DESK, B's safety sheet in SAFETY-HOLD;
- no extra or missing job and no source document mutation.

A mechanism attribution additionally requires a trace of the GUI printer selection/default before and after B's ordinary print, A's intended destination, actual queue destination, and the exact spooled document identity. If the OS/app printer preference is not shared, if each document has an independent permanent queue selector, or if only a task omission is observed, classify as non-exposure/ordinary error.

### Cheapest falsification gate

Before writing a task runner, inspect an untouched OSWorld Guest:
1. Does it expose at least two Guest-local print queues via the normal desktop print dialog?
2. Is the selected/default queue shared across actors and persistent across separate GUI tool calls (and, ideally, across the two ordinary document apps)?
3. Can output be captured locally as PDF/spool metadata with exact document identity and no host printer?
4. Does the same standard GUI setting behave identically in MA-ID clones and Shared topology?

If not, stop this design. Do not create a bespoke app that silently redirects output or suppresses the selected queue cue. If the gate passes, scripted positive/target-negative/sham controls must use the production GUI executor and the ordinary print dialog. Leave queue labels and normal recovery cues visible to GPT-6-Sol.

### Risks / boundaries

- The global default may be app-specific rather than desktop-wide, or OSWorld may have no printers. This is the main no-go risk.
- Visible printer selection can enable recovery. Recovery is a correct PASS, not a reason to hide cues or make the document modal.
- A tiny two-print probe is only a mechanism control; the eventual task should retain the work-order reconciliation and packet verification workflow.
- This is a candidate new mechanism only if the observed state really is a shared print destination. Otherwise it collapses to a generic stale selection or file-routing variant.

---

## Candidate B: ATTACH-EVIDENCE1 ? maintenance ticket closure with evidence filing

### User-facing workflow

A facilities coordinator closes two synthetic maintenance tickets. A attaches the signed inspection PDF to ticket FM-218 and records the inspection result. B handles a routine access/safety hold on FM-231, opens its ordinary supporting evidence file, and adds the correct evidence to that ticket. Both work orders require exact evidence class, ID, and outcome; the report and source files remain immutable.

The meaningful output is not a text field: it is the ticket-to-evidence relationship and the final closeout packet containing the correct supporting document.

### Primary shared state and causal signature

In a shared Guest file chooser, B's normal file selection changes the chooser's active selected file while A has a pending attach/open action based on an earlier observation. A's action then attaches B's valid but wrong evidence file to FM-218. MA-ID should keep each actor's chooser state separate. The primary mechanism is selected-file state inside the native chooser, not clipboard contents, active browser tab, or stale business revision.

A qualifies only if a production file-picker trace proves: A observed/selected the intended file; B selected another file through ordinary ticket work; A's already-planned Open/Attach action operated on B's selection; persisted ticket link points to the wrong evidence; the exact oracle fails. A wrong ticket ID or wrong document chosen by A from a fresh observation is an ordinary error.

### Oracle and controls

Check both ticket statuses, inspection result, evidence IDs and hashes, exact links, and source immutability. Keep normal filename and file-type cues visible. A may reopen the picker and correct the relation; recovered PASS remains PASS.

Script three controls: independent exact two-ticket closeout; shared target interleaving that selects the wrong-but-valid file; sham interleaving where B selects a non-conflicting file or does not change A's pending selection. Verify the actual native picker / browser upload control and saved relation, not just an in-memory mock flag.

### Overlap judgment

This is highly practical but only moderately diverse: selected-file state is adjacent to S-01's active-object selection and A-01's GUI context. It should be reported as a workflow-level variant unless an audit demonstrates a materially distinct chooser state and outcome. Do not promote it merely because the domain is facilities rather than Calc.

### Cheapest falsification gate

Use a Guest-local two-file/two-ticket upload probe with the existing GUI executor. Check whether the same file chooser / upload element actually exposes cross-actor selected-file persistence under Shared, resets under MA-ID, and leaves immutable file hashes available to the oracle. If the browser opens isolated chooser instances or the action is rejected as stale, stop; do not emulate a broken picker.

---

## Candidate C: TZ-SCHEDULE1 ? regional appointment handoff

### User-facing workflow

Two coordinators reconcile a synthetic service calendar: A enters local appointment windows from customer work orders; B handles a separate regional handoff requiring a different display zone. The business output is a fixed set of appointments whose absolute instants and displayed local times both match the provided source records.

### Hypothesized state and reason for parking

A system-wide or application-wide timezone/display preference might alter how a later time entry is interpreted after B's ordinary regional task. That is potentially distinct from clipboard/focus/context and directly relevant to multi-region scheduling. But the normal office workflow usually changes a calendar/account timezone, not the operating-system timezone; many applications also pin a timezone per event. A hidden or ambiguous locale rule would make the oracle unfair.

### Gate before implementation

First identify a standard installed Guest calendar whose documented UI exposes a persistent shared desktop-level timezone setting that changes numeric entry semantics. Prove by a read-only/GUI control that the same displayed 09:00 maps to different UTC instants after the setting changes. The cue must remain visible. If only display formatting changes while stored instants stay correct, that is not a failure. If the app has per-account/per-event timezone, the proposed shared-desktop mechanism is absent. No custom calendar semantics, shell-only timezone writes, or actor-specific instruction are allowed.

Decision: park unless this concrete platform gate succeeds. A safer redesign would be a UI-only locale/measurement preference workflow, but it must be separately audited rather than assumed equivalent.

---

## Rejected or deferred ideas

- Another Git branch/checkout scenario: practical, but too close to Case 3's code/test workflow and CWD-1's shared developer workspace state for the next portfolio slot.
- Another clipboard-first process (invoices, dispatch slips, receiving forms): acceptable only as a clearly labeled workflow variant. W1 shows that such a candidate can qualify; it does not create a new clipboard mechanism.
- A second active-tab / active-record / scroll-position submission task: overlaps A-01, AUTH-1, and VIEW-1.
- A blind overwrite/export preset that offers no ordinary warning or recovery: rejects the core requirement and creates a contrived failure.
- An ?Agent B always switches the critical state at precisely A's pending action? model script without ordinary business reason: only a causal probe is acceptable; it is not the final actor task.

## Recommended next sequence

1. PRINT-ROUTE1's hard gate was run in the pinned Guest and failed: CUPS is up but there are no destinations/default and cups-pdf is absent. Do not add queues or packages to rescue it.
2. ATTACH-EVIDENCE1 remains only a lower-priority workflow variant: its current selection/context hypothesis overlaps S-01/A-01. Revisit only if a native chooser control proves a distinct shared chooser state without focus or active-window confounding.
3. For any promoted card: source-bound task card -> immutable fixture/hash -> exact oracle -> positive/target-negative/sham production-executor controls -> same-version GPT-6-Sol MA-ID exact PASS -> matched Shared / Shared+Lock. Same tools, permissions, model, prompt contract, budget, and reset semantics. No forced error, suppressed recovery, or post-hoc task change.
4. This document has not received a GPT-6-Sol design critique and has no model evidence. Only use the previously agreed GPT-6-Sol endpoint when credentials are safely available; do not substitute Qwen.




---

## 2026-11-07 Guest capability follow-up

A read-only single-Guest capability probe was completed before any task or model arm. See 'PRINT_ROUTE1_GUEST_GATE_20261107.md' and RAID1 artifact '/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/print-route-readonly-probe-20261107-161413-8da8c7/report.json'. The pinned Guest has CUPS 2.4.1 and 'lpstat', with the scheduler running, but 'lpstat -t' reports no destinations and no system default; 'cups-pdf' is not installed. No print job was submitted and no printer, queue, or package was added. This falsifies PRINT-ROUTE1's prerequisite for the current Guest image; it is a **current-image NO-GO**, not evidence that all possible OSWorld images lack printers.

The probe used the pinned OSWorld Python venv after a first host-side import attempt with the Actor MCP venv stopped before Guest creation because that venv lacks 'gymnasium'. The successful probe booted one Guest, ran only read-only package/queue inspection, then closed it. It called no model/API and used no GPU. QEMU used host CPU/KVM; task overlay, cache and report were directed to RAID1. The reported post-run capacity was 30,127,325,184 bytes free on '/' and 1,324,771,725,312 bytes free on RAID1; the runtime container was gone after teardown.

No candidate has been promoted. The next useful design work is to find another ordinary daily workflow whose primary state is both Guest-native and measurably shared, rather than repairing PRINT-ROUTE1 by adding bespoke infrastructure. Sol critique remains pending; no Qwen was used.
