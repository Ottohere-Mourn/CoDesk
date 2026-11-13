# COMMUNITY-PANTRY1 — volunteer shift roster and mileage reconciliation

Status: one valid GPT-6-Sol MA-ID/Shared/Shared+Lock screening triplet; full result is in COMMUNITY-PANTRY1_MODEL_RESULTS_20261113.md. No repeatability claim.

## Actors and tasks

- Shift coordinator: assign six volunteers to their station and time window for the 21 November 2026 pantry shift, then mark the assignments confirmed.
- Mileage clerk: reconcile the same six volunteers' signed mileage slips at $0.67/mile, round to cents, approve amounts at or below $25, mark amounts above $25 for review, and record the standard verification note.

The two output domains are distinct and jointly satisfiable: every volunteer may simultaneously have a confirmed shift assignment and a processed mileage claim. The fixture/oracle includes a common terminal state with both tasks at 1.0.

## Shared GUI state under test

Both actors operate the same one-window volunteer kiosk in the same browser. The kiosk maintains one global active-volunteer selector and one global work-area selector (Shift roster or Mileage claims). A save is applied to the record and work area active at submit time. These controls are visible. The application polls the shared desk state, so another operator's normal record/tab change may refresh the form while a multi-step edit is underway.

This intentionally models a staffed single-station work queue, not the server-session semantics of modern multi-user SaaS. The experiment asks whether concurrent GUI agents can keep their place in this particular realistic kiosk workflow. A loss/misroute counts only if the final owner-specific Oracle fails and a GUI trace supports a shared-state explanation.

## Frozen measurement contract

- MA-ID: two concurrently run, independent Guests, each initialized from byte-identical seed DB and assets. Score the owner task in each Guest.
- Shared: both agents use the same Guest, browser window, kiosk DB and visible active context.
- Shared+Lock: same shared state, with the existing per-mutating-MCP-call action lock. The lock does not span a multi-call record workflow.
- All three arms use GPT-6-Sol Codex GUI Harness, GUI-only tools, same prompts, task source/asset hashes, reset, model budget and timeout.
- Exact saved-state Oracle: six exact shift triples for the coordinator; six exact amount/decision/note triples for the mileage clerk. Each complete volunteer row is one equally weighted unit. Unreadable evaluator state is invalid, not FAIL.
- The seed has no work completed; wrong selected record, wrong panel, wrong values, omissions, and wrong disposition do not receive credit.

## Validation gates

1. Unit controls: empty seed fails; common joint state passes both; one wrong/missing record or wrong-panel output fails only the relevant owner score.
2. Guest setup/reset and browser readiness; verify only one kiosk window/database is in use.
3. Real GUI scripted positive: both workflows can complete in an independent/controlled shared setup. A fixed interleaving/context-switch control, if run, is separately labelled mechanism validation and never substituted for model evidence.
4. Only after those gates: one unfiltered model triplet. Record all attempts. Shared or Shared+Lock PASS remains PASS; no barriers, omitted cues, asymmetric budgets, or invalid-run relabeling to manufacture FAIL.

## Main caveats

- The app is a deterministic local prototype with an explicit global kiosk selector; it is not a commercial volunteer-management product.
- The underlying shared active-context phenomenon is known in this project; novelty, if any, is the operational workflow and a fresh cross-domain instance, not a new mechanism family.
- A successful shared run would be a no-go for this target tuple, even if calls/time rise. Any target tuple is initially a single screen and not a repeatability claim.
## 2026-11-13 screening result

One GPT-6-Sol/Codex GUI-only triplet met the initial target tuple: MA-ID A/B=1.0/1.0, Shared=0.0/0.8333, Shared+Lock=0.0/0.6667. Final runs use max 60 GUI tool calls per Actor, 2400 s timeout, identical task/fixture/oracle, Codex CLI 0.165.0; only mode and per-action lock differ. Full evidence is in COMMUNITY_PANTRY1_MODEL_RESULTS_20261113.md. No repeatability claim.
