# CoDesk Prototype Status V1

Checkpoint basis: `8aa889f`. This phase did not launch a Guest, Docker workload, or model.
Host load at inspection was 1/5/15-minute average `313.91 / 325.60 / 329.25`; swap was
fully consumed. Live smokes are therefore deferred. Existing historical artifacts remain
unchanged and are not represented as new runs.

## Four mechanism prototypes

| Mechanism | Current code path | Offline state | Live Guest status |
|---|---|---|---|
| Focus / input routing | `scripts/run_writer_calc_v1.py`, `swcub/actors.py`, `swcub/task_factory.py` office template | Existing Writer/Calc task and exact saved-ODF oracle; generated instances use the same workflow. The current fixed scripted actors hard-code their outputs and are not parameter-bound to generated seeds. | Historical scripted evidence exists for the anchor only. No episode run in this phase. |
| Clipboard ownership | `swcub/tasks/clipboard_v1.py`, `swcub/clipboard_observer.py`, `scripts/guest_clipboard_probe.py` | Normal GUI copy/paste actor, exact saved ODF evaluator, private observer/tracker and offline event attribution exist. | Observer-on/off, real clipboard observer fidelity, setup/reset, Solo/MA-ID/MA-SD remain unvalidated per `CLIPBOARD_001_STATUS.md`. |
| Modal ownership | `swcub/tasks/prototypes_v1.py` (`writer_calc_save_dialog_v1`) | New deterministic manifest builder, ODF seeds, final path/content/format oracle, and dialog-owner evidence evaluator. No native-dialog actor/setup runner yet. | Not run; no dialog attribution evidence. |
| Application context | `swcub/tasks/prototypes_v1.py` (`chromium_two_tab_context_v1`), `ScriptedBrowserTabActor` | New two-tab fixture source, distinct actor goals, exact backend-state oracle, and same-window/tab-transition evidence schema. | Not run. X11 window ID + page visibility instrumentation have not been joined in a real episode. |

GUI+CLI stale-state remains an **auxiliary control**, not a fifth core GUI mechanism.
No old evaluator, task result, or historical artifact was changed.

## Evidence boundary

- New offline tests validate manifest determinism/schema, fixture-source syntax, exact
  evaluator outcomes, and whether evidence is marked `unknown` when absent.
- These tests do not demonstrate Writer/Calc or Chromium GUI reachability, native dialog
  ownership, clipboard observer non-perturbation, reset, MA-ID topology, or real desktop
  focus/tab events.
- This phase produced **zero new real Guest trajectories and zero new model trajectories**.
- The existing scripted Writer/Calc runner is still anchored to fixed target strings
  (`Approved by GUI actor`, `Approved`). It cannot currently execute arbitrary office
  factory content without parameter-bound actors and runner initialization.

## Extension priority

1. **Clipboard 001:** first because probe, actor actions, task oracle, and ownership rules
   already exist; live observer-on/off comparison is the gate before attribution claims.
2. **Application Context A1:** next; wire the two-tab server into a Guest setup, log X11
   active-window ID alongside page visibility/tab events, then validate same window ID and
   changing tab IDs without exposing private evaluator state.
3. **Modal M1:** after defining and verifying a stable LibreOffice Save As/format-confirm
   interaction on the pinned Guest. Require native dialog XID, owner app/window, target
   path, and confirmation action evidence. If title/ownership is ambiguous, retain `unknown`.
4. **Focus F1:** reuse the historical task, then make actor targets instance-driven before
   treating generated office seeds as executable instances.

## First task production plan

Do not batch-generate by seed. Keep one fixed seed per mechanism and produce two or three
instances only after its scripted Guest gates pass. A family is promoted only after both
actors independently pass Solo, joint completion passes, negative controls fail for the
intended oracle reason, reset returns the exact initial state, and mechanism instrumentation
has an observer-on/off integrity check where applicable. Then compare MA-ID and MA-SD with
the same backend and task seed. All failures, environment-invalid episodes, and screenshots
remain in append-only per-run artifact directories.
