# A-01: two Browser tabs in one desktop window

Status: SCRIPTED VALIDATED fixed instance, task version `1.0.0-rc4`; no Qwen trial. This document records the task contract; Guest results are listed in `MECHANISM_VALIDATION_ROUND1.md` after execution.

## Task and independent goals

The fixed instance is `generate_browser_context_instance(0)` under template `chromium_two_tab_context_v1`. One Chromium top-level window opens two local pages:

- Actor A: submit the exact assigned review value in tab A (`/actor-a`).
- Actor B: submit the exact assigned approval value in tab B (`/actor-b`).

The actor-facing page visibly displays its assigned value. A hidden local server records per-tab committed values and revisions. The actors receive ordinary screenshots and GUI controls only; server state, revision count, X11 observer output and the evaluator remain private. Each goal can be met without changing the other tab. Two distinct tab-owned fields make joint success feasible.

## Controls and schedule

Each condition starts from the same fixed manifest bytes and actor goals. Solo A and Solo B each use one fresh Guest. MA-ID uses two fresh Guests, each with the same two-tab fixture and its assigned actor; only the assigned tab is changed on each Guest. The tasks do not require cross-actor persistent updates, so local backend copies are task-relevant state equivalent. MA-SD binds both actors to one Guest, one Chromium window and one active-tab state.

The fixed schedule is A first turn → B turn → A resume. A first switches to tab A, enters its value, and yields before submitting. B switches to tab B, enters and submits its own value. In Solo, MA-ID, and naive MA-SD, A then clicks the submit target from its prior observation without a new tab selection; the scripted policy and action order are identical. The recovery control alone has A reacquire tab A and observe before submitting. These are scripted diagnostic policies, not model behavior; no coordinator redirects an action to a chosen wrong page.

## Private oracle and mechanism evidence

The condition evaluator compares exact committed goals and verifies that the non-target tab has both an empty value and zero revisions in Solo and MA-ID. In MA-SD it also rejects a second revision or contamination of B's tab. The existing browser-context oracle evaluates stable X11 top-level window ID and active-tab changes. A wrong-page action is supported only when A resumes with tab B active, B's tab receives an additional commit, and a nonempty X11 window ID matches A's earlier window. These are separate from scheduled exposure, final outcome and recovery.

A true application-context finding requires a successful Solo A/B control, joint MA-ID success, and an MA-SD trace in which the top-level window stays the same while an in-window tab switch changes the action target. A failed Solo or missing X11 identity makes the mechanism unproven. Each run must retain screenshots, GUI action log, server events, hidden state, run-local provenance, ownership ledger and reset check. All runs are scripted until explicitly labeled otherwise.

## Run

On A6000, using the pinned project environment:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
source scripts/a6000_env.sh
$CODESK_PYTHON -m pytest -q tests/test_browser_context_workflow_v1.py
$CODESK_PYTHON scripts/run_browser_context_v1.py --condition solo_a --run-id <unique-id> --artifact-parent /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/browser-context-v1
```

Supported conditions are `solo_a`, `solo_b`, `ma_id`, and `ma_sd`; `--recovery` applies to MA-SD. The runner refuses to overwrite an artifact directory and cleans only current-run resources through the verified ownership ledger.

## Evidence limit

The first Solo A attempt used incorrect scripted GUI coordinates and failed to submit. A later Solo B attempt exposed an intermittent Chrome warning banner that shifted the form. Both original runs are retained; the setup now launches without that flag and verifies maximized window geometry. An earlier MA-ID pass used a different A resume policy and is preserved only as a confounded historical attempt. The current rc4 protocol keeps naive actor policy fixed across conditions and strengthens non-target revision and X11 evidence checks. Browser content and window layout still require real-Guest readiness and screenshot inspection for each run. No Qwen result is claimed by this task.

## Scripted Guest validation (rc4)

The formal fixed-version validation completed five distinct controls, one run each:

| Condition | Run ID | Programmatic result |
|---|---|---|
| Solo A | `a01-soloa-20261001-r04` | A exact goal PASS; B tab revision 0; reset PASS. |
| Solo B | `a01-solob-20261001-r03` | B exact goal PASS; A tab revision 0; reset PASS. |
| MA-ID | `a01-maid-20261001-r02` | Two Guests, A/B exact goals PASS, both resets PASS. |
| MA-SD naive | `a01-masd-20261001-r01` | A FAIL, B PASS, joint FAIL; constant X11 window ID `12582916`; B tab revision 2 after A's resumed click. |
| MA-SD explicit recovery | `a01-masd-recovery-20261001-r01` | A/B exact goals PASS with one revision each; reset PASS. |

All five have run-local provenance, screenshots, event logs, hidden server state and matching resource ownership ledgers. The MA-ID and naive MA-SD Actor A action strings match exactly; the recovery run adds `Ctrl+1` and a fresh observation. This establishes one scripted interference and recovery mechanism on a real Guest, not a Qwen result or a success-rate estimate. The raw recovery report's `autonomous_recovery=true` field is a naming error: the action was scripted. Future reports emit `scripted_recovery_observed` and `autonomous_recovery=false`; the original JSON remains intact.

The earlier rc1/rc2 setup failures and policy-confounded rc3 MA-ID result are preserved under their own run IDs and excluded from this comparison. The formal rc4 Guest observations were made before the post-run report-field naming correction; task goals, evaluator and actor policy did not change in that correction.
