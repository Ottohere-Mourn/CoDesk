# CoDesk Instance Generation V1

## Deterministic generation

`swcub.production_v1` owns the frozen 15-workflow parameter catalog. Each workflow combines 4 semantic domain schemas × 5 operation-specific target/object profiles × 2 target/guard layouts = 40 fixed candidates. The seed only permutes candidate selection/order; it is excluded from identity. Repeating the same workflow/profile/layout yields the same ID, public fixture bytes, evaluator, and hashes.

These are fixed **offline candidate instances**. The five newly added workflows keep their actual evidence labels (`F-N1: guest_solo`; `C-N1/A-N1/S-N1/U-N1: offline`); no generated record upgrades runtime evidence. An offline exact-state oracle test does not prove that a GUI setup or operation is Guest-ready.

## Per-workflow semantic axes

| Workflow | Fixed structure / operation graph | Varying task-relevant fields | Invalid combinations / oracle and fixture coupling |
|---|---|---|---|
| F-01 | Writer decision + Calc field | domain/entity, Calc headers/cell, Writer paragraph, guard placement | A/B targets must differ; FODT paragraph and FODS cell are exact-state targets. |
| F-04 | Calc rectangle + Writer paragraph | range bounds/shape, paragraph role, domain, guard position | Range must be rectangular and nonempty; fixture matrix dimensions match oracle. |
| F-02 | Writer anchored comment + Browser form | comment anchor kind, form field pair, domain, guard placement | Anchor/form targets distinct; private form revision and Writer annotation state checked. |
| C-01 | Plain-text transfer to Writer/Calc | payload semantics, destination object, insertion/guard layout, domain | A/B destinations distinct; exact payload and clipboard generation are treatment/oracle fields. |
| C-03 | Calc rectangle transfer + Writer paragraph copy | rectangle dimensions/target slot, paragraph role, domain | Rectangle has >=2 cells and destination is Writer; expected matrix/table shape exact. |
| C-02 | Browser URL ↔ Writer hyperlink | link semantic kind, href destination field, domain, target | Visible label and href are separately exact; URL field and Writer link remain distinct. |
| A-01 | Two tab/page forms in one top-level Browser | tab/page identity, form fields, domain, target layout | Top-level window fixed; per-tab submission oracle; this schema must not collapse into app switching. |
| A-02 | One page, selected record then edit | record-type pair, selected record objects, domain | Same page/context; record IDs distinct; per-record values/revisions are exact. |
| S-01 | Calc active-cell selection then edit | cell pair, domain, cell relation | Selected cells distinct and on same sheet; full-grid oracle preserves all other cells. |
| U-01 | Calc shared undo stack | edited cell pair, edit class, undo depth/order | One undoable A operation precedes B; exact grid and transaction sequence checked. |
| F-N1 | Two Writer windows/documents | paragraph role, domain, doc-specific guard position | Two paths/windows must remain distinct; path-bound FODT oracle. Runtime gate remains incomplete. |
| C-N1 | Browser rich HTML table → Writer table | table shape, destination slot, domain | MIME/structure must survive; plain text alone is insufficient; runtime gate remains incomplete. |
| A-N1 | One-tab SPA route transition | route pair, route field, transaction/domain | Same tab/window, distinct routes and revisions; URL/tab-only changes invalid. Runtime gate remains incomplete. |
| S-N1 | Writer text range selection + format | range class/target pair, action, guard layout | Non-overlapping ranges and exact ODF spans; selection observer still needs Guest validation. |
| U-N1 | Writer document shared undo history | paragraph pair, edit operation/depth, domain | A undo targets last shared-history event after B; paragraph oracle plus history trace. Runtime gate remains incomplete. |

The catalog is parameterized but deliberately finite. It does not claim 600 distinct operation graphs; it provides 15 workflow templates and up to 40 reviewed semantic profiles per workflow. Content identifiers and text values do not count as standalone diversity axes.

## Commands

```bash
python scripts/generate_instances.py --workflow F-01 --count 3 --seed 2026 --output /tmp/codesk-f01 --validate
python scripts/generate_suite.py --quota-per-workflow 40 --seed 2026 --output benchmarks/codesk_v1
python scripts/offline_self_test.py
```

Generation never starts Guest, Docker, model or application processes. Do not overwrite an existing suite directory. Preserve its manifest and hashes as an immutable checkpoint.
