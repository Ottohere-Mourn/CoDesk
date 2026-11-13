# CoDesk Collaboration Case Registry

This registry covers the seven standalone collaboration cases in this checkout. Offline fixtures and scripted or application-level checks are not model-agent results. No OSWorld Guest, QEMU, or model was started for Cases 6–7 in this branch update.

## Validation status

| # | Case | Fixture / Oracle evidence | Offline tests | Application / Guest / Agent boundary |
|---:|---|---|---|---|
| 1 | [Data-to-Deck](data_to_deck/TASK_CARD_ZH.md) (`CDD-RECON-001`) | Real ODS/ODP fixtures; positive/negative Oracle. Historical Guest run performed actual Calc/Impress GUI save/reopen, artifact collection and reset. Initial official score failed on ODS protected sheets; a later standards-aware parser patch rescored the same collected Guest outputs and a host-LO-resaved ODS to official PASS. | `tests/test_data_to_deck.py` | **Guest scripted GUI: PASS** for application and lifecycle; **official post-fix artifact Oracle: PASS**. It was not an Agent episode. Qwen grounding attempts did not establish successful task solvability; Solo/MA-ID/MA-SD model evidence is not closed. |
| 2 | [Ticket-to-Resolution](ticket_to_resolution/TASK_CARD_ZH.md) (`CDD-TTR-001`) | Deterministic SQLite fixture, web UI, transactional Oracle, positive/negative controls and reset are offline implemented. | `tests/test_ticket_to_resolution.py` | **Offline: PASS. Guest: BLOCKED_RESOURCE** at the documented resource gate; no Guest GUI episode, Single Agent, MA-ID, MA-SD or model result. The Guest report records that the Guest was not started. |
| 3 | [Build-and-Verify](build_and_verify/TASK_CARD_ZH.md) (`CDD-BV-001`) | Deterministic web-app fixture and code-state/function Oracle; API/fake-DOM controls. | `tests/test_build_and_verify.py` | **Offline: PASS.** Fake-DOM and HTTP checks are not a real browser. Guest, Solo, MA-ID, MA-SD and model are pending. |
| 4 | [Timeline-and-Assets](timeline_and_assets/TASK_CARD_ZH.md) (`CDD-TLA-001`) | Real MLT/Kdenlive project XML, media fixtures and parser Oracle; deterministic Gold/negative controls. | `tests/test_timeline_and_assets.py` | **Offline: PASS.** Kdenlive is unavailable in the documented environment; application open/save, Guest, Solo, MA-ID and MA-SD are pending. |
| 5 | [Model-and-Review](model_and_review/TASK_CARD_ZH.md) (`CDD-MAR-001`) | Real initial and Gold `.blend` files; Blender 5.2.2 background parse, structural Oracle, save/reopen and reset passed. | `tests/test_model_and_review.py` | **Blender background/application-file: PASS. GUI/Guest, Solo, MA-ID, MA-SD and model are pending.** Background Blender is not GUI-Agent evidence. |
| 6 | [Spreadsheet Handoff](spreadsheet_handoff/TASK_CARD_ZH.md) (`CDD-SH-001`) | Real ODS initial/Gold; cached formulas; protected inputs; positive/negative Oracle; append-only version store and reset. | `tests/test_spreadsheet_handoff.py` | **Offline + LibreOffice Calc ODS save/reopen: PASS.** Guest GUI, Single Agent, MA-ID, MA-SD, natural handoff/interference/recovery pending. |
| 7 | [Workspace Assembly](workspace_assembly/TASK_CARD_ZH.md) (`CDD-WA-001`) | Real ODT, PNG, PDF, CSV and text fixtures; complete Gold tree; path/hash/manifest/link Oracle and controls. | `tests/test_workspace_assembly.py` | **Offline + LibreOffice Writer same-path open/save/reopen: PASS.** File Manager/Writer Guest GUI, Single Agent, MA-ID, MA-SD and natural interference/recovery pending. |

## Reproduce offline checks

From repository root, with repository dependencies installed:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 python -m pytest -q \
  tests/test_data_to_deck.py \
  tests/test_ticket_to_resolution.py \
  tests/test_build_and_verify.py \
  tests/test_timeline_and_assets.py \
  tests/test_model_and_review.py \
  tests/test_spreadsheet_handoff.py \
  tests/test_workspace_assembly.py
```

The last two test modules conditionally skip their LibreOffice round-trip if LibreOffice or its system UNO module is unavailable. They never start an OSWorld Guest or call a model. Model-and-Review's `.blend` fixture parsing depends on the configured Blender runtime; its existing report records the verified version and paths.

## Commands and dependencies

### 1. Data-to-Deck

```bash
python -m oscombo.collab.data_to_deck prepare /tmp/codesk-dd/run-001
python -m oscombo.collab.data_to_deck plan collaborative_shared
python -m oscombo.collab.data_to_deck protocol-smoke
python -m oscombo.collab.data_to_deck local-office-smoke
python -m oscombo.collab.data_to_deck evaluate --authority AUTHORITY.ods --analysis ANALYSIS.ods --draft DRAFT.odp --deck FINAL.odp
```

Dependencies: Python project environment; LibreOffice is used by the optional headless format smoke; real GUI execution requires the pinned OSWorld V2.1 provider/Guest and a Guest-safe actor/message bridge. The committed Guest report documents the historical Guest and run ID; its original score and post-fix rescoring artifacts are both retained.

### 2. Ticket-to-Resolution

```bash
python -m oscombo.collab.ticket_to_resolution prepare /tmp/codesk-ttr/run-001 --run-id ttr-run-001
python -m oscombo.collab.ticket_to_resolution plan --condition collaborative_shared --run-id ttr-run-001 --output /tmp/codesk-ttr/run-001/run_config.json
python -m oscombo.collab.ticket_to_resolution serve --db /tmp/codesk-ttr/run-001/db/case.sqlite3 --credentials /tmp/codesk-ttr/run-001/secrets/browser_credentials.json --host 127.0.0.1 --port 8765
python -m oscombo.collab.ticket_to_resolution collab-serve --run-root /tmp/codesk-ttr/run-001
python -m oscombo.collab.ticket_to_resolution evaluate /tmp/codesk-ttr/run-001
python -m oscombo.collab.ticket_to_resolution reset /tmp/codesk-ttr/run-001 --run-id ttr-run-001
```

Dependencies: Python standard-library SQLite/HTTP components and the existing message protocol; real run additionally needs OSWorld Guest, browser GUI, local-service bridge and a second Guest for MA-ID.

### 3. Build-and-Verify

```bash
python -m oscombo.collab.build_and_verify prepare /tmp/codesk-bv/run-001 --run-id bv-run-001
python -m oscombo.collab.build_and_verify configure /tmp/codesk-bv/run-001 --condition collaborative_shared
python -m oscombo.collab.build_and_verify serve --run-root /tmp/codesk-bv/run-001 --port 8766
python -m oscombo.collab.build_and_verify collab-serve --run-root /tmp/codesk-bv/run-001
python -m oscombo.collab.build_and_verify evaluate /tmp/codesk-bv/run-001
python -m oscombo.collab.build_and_verify reset /tmp/codesk-bv/run-001 --run-id bv-run-001
```

Dependencies: Python and Node.js for the fake-DOM keyboard contract test; real run needs GUI editor, browser, OSWorld Guest and the existing Guest action/provenance adapter. The current package has no full MA-ID/MA-SD Guest coordinator.

### 4. Timeline-and-Assets

```bash
python -m oscombo.collab.timeline_and_assets prepare /tmp/codesk-tla/run-001 --run-id tla-run-001
python -m oscombo.collab.timeline_and_assets configure /tmp/codesk-tla/run-001 --condition collaborative_shared
python -m oscombo.collab.timeline_and_assets collab-serve --run-root /tmp/codesk-tla/run-001 --port 8767
python -m oscombo.collab.timeline_and_assets evaluate /tmp/codesk-tla/run-001
python -m oscombo.collab.timeline_and_assets reset /tmp/codesk-tla/run-001 --run-id tla-run-001
```

Dependencies: Python with PyAV/OpenCV for deterministic media fixtures; Kdenlive is required for application/Guest validation. The documented host did not have Kdenlive or `melt`.

### 5. Model-and-Review

```bash
python -m oscombo.collab.model_and_review plan --condition collaborative_shared --run-id mar-run-001
python -m oscombo.collab.model_and_review prepare /tmp/codesk-mar/run-001 --run-id mar-run-001
python -m oscombo.collab.model_and_review configure /tmp/codesk-mar/run-001 --condition collaborative_shared
python -m oscombo.collab.model_and_review evaluate /tmp/codesk-mar/run-001
python -m oscombo.collab.model_and_review reset /tmp/codesk-mar/run-001 --run-id mar-run-001
```

Dependencies: project-local Blender 5.2.2+ for real `.blend` generation and extraction; `CODESK_BLENDER_BIN` selects the executable. Guest validation additionally needs Blender GUI in OSWorld Guest. Keep `fixtures/private/gold.blend` and `gold_state.json` outside actor mounts.

### 6. Spreadsheet Handoff

```bash
python -m oscombo.collab.spreadsheet_handoff plan collaborative_shared --run-id sh-run-001
python -m oscombo.collab.spreadsheet_handoff prepare /tmp/codesk-sh/run-001 --run-id sh-run-001
python -m oscombo.collab.spreadsheet_handoff configure /tmp/codesk-sh/run-001 collaborative_shared
python -m oscombo.collab.spreadsheet_handoff serve-messages /tmp/codesk-sh/run-001
python -m oscombo.collab.spreadsheet_handoff evaluate /tmp/codesk-sh/run-001
python -m oscombo.collab.spreadsheet_handoff reset /tmp/codesk-sh/run-001 --run-id sh-run-001
```

Dependencies: Python project environment; LibreOffice is optional for the ODS serialization regression. Real validation requires Calc in Guest plus a Guest adapter exposing the existing version repository and message service without changing their topology between MA-ID/MA-SD.

### 7. Workspace Assembly

```bash
python -m oscombo.collab.workspace_assembly plan collaborative_shared --run-id wa-run-001
python -m oscombo.collab.workspace_assembly prepare /tmp/codesk-wa/run-001 --run-id wa-run-001
python -m oscombo.collab.workspace_assembly configure /tmp/codesk-wa/run-001 collaborative_shared
python -m oscombo.collab.workspace_assembly serve-messages /tmp/codesk-wa/run-001
python -m oscombo.collab.workspace_assembly evaluate /tmp/codesk-wa/run-001
python -m oscombo.collab.workspace_assembly reset /tmp/codesk-wa/run-001 --run-id wa-run-001
```

Dependencies: Python/Pillow and optional LibreOffice Writer + system UNO for the same-path headless round-trip. Real validation requires a Guest file manager and Writer plus an adapter that connects one canonical run workspace to either one or two desktops; the current plan does not implement that Guest mount bridge.

## Shared limitations and safety

- No Case 6/7 run in this update reached Guest, Solo, MA-ID, MA-SD, or model validation.
- The case packages reuse the same Data-to-Deck message/attachment service. Tokens and hidden oracle directories under run roots are private; do not mount them into actor workspaces.
- Case 6's ODS repository and Case 7's canonical workspace are condition-invariant in configuration. The Guest adapters that expose them to desktop sessions are pending; do not interpret offline plan equality as a completed backend test.
- Message count does not prove substantive collaboration. Window changes alone do not prove interference. Future attribution requires action/screenshot/app-state evidence and a non-atomic sampling caveat.
- A reset restores task state but does not turn an unsuccessful episode into a successful one. Existing run outputs, histories and artifacts should be retained.
- The seven task fixtures, hidden gold states, and oracles are case-local. Reusing the common message/provenance library does not create cross-case data or result dependencies.

## Guest resource and application requirements

These are planning requirements for future validation, not claims that the runs have been performed. A Solo or Shared episode needs one Guest; a valid Isolated episode needs two Guests alive for the same episode. Do not substitute sequential single-Guest execution for Isolated.

| Case | Minimum Guest application/runtime | Guest count by condition | Additional runtime/data needs |
|---|---|---|---|
| Data-to-Deck | LibreOffice Calc + Impress; browser is not required for the core case | Solo 1; Isolated 2; Shared 1 | The historical Guest scripted GUI lifecycle passed. A Guest-safe actor/message bridge is still needed for agent episodes. |
| Ticket-to-Resolution | Browser + local simulated service | Solo 1; Isolated 2; Shared 1 | Each condition must use the same episode database and service semantics; local-service reachability from both Guests remains to be validated. |
| Build-and-Verify | GUI code editor + browser + local web app | Solo 1; Isolated 2; Shared 1 | Node.js is used by offline tests; Guest validation needs the editor/browser app setup and service bridge. |
| Timeline-and-Assets | Kdenlive + fixture media | Solo 1; Isolated 2; Shared 1 | Kdenlive/MLT availability and codec compatibility must be established in the Guest image. |
| Model-and-Review | Blender GUI + real `.blend` fixture | Solo 1; Isolated 2; Shared 1 | Blender GUI must be available in the Guest. The host-side Blender background validation does not satisfy this requirement. |
| Spreadsheet Handoff | LibreOffice Calc | Solo 1; Isolated 2; Shared 1 | Both isolated desktops must connect to the same versioned workbook repository and handoff service; the Guest adapter is pending. |
| Workspace Assembly | File manager + LibreOffice Writer | Solo 1; Isolated 2; Shared 1 | Both isolated desktops must access the same canonical run workspace under the same path semantics; the Guest mount/action adapter is pending. |

Model evaluation additionally requires a separately provisioned inference endpoint and a recorded model/action budget. This registry does not reserve GPU resources or authorize model calls.
