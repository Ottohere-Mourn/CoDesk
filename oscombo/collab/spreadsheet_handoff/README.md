# Spreadsheet Handoff

Offline-ready CoDesk Case 6. It uses a real ODS workbook and an append-only single-writer version store. It has not been run in OSWorld Guest or with an Agent.

```bash
python -m oscombo.collab.spreadsheet_handoff plan single_agent
python -m oscombo.collab.spreadsheet_handoff prepare runs/spreadsheet-handoff/demo --run-id demo
python -m oscombo.collab.spreadsheet_handoff configure runs/spreadsheet-handoff/demo collaborative_shared
python -m oscombo.collab.spreadsheet_handoff evaluate runs/spreadsheet-handoff/demo
python -m oscombo.collab.spreadsheet_handoff reset runs/spreadsheet-handoff/demo --run-id demo
python -m pytest -q tests/test_spreadsheet_handoff.py
```

`prepare` creates a new empty run root and preserves all existing paths. `evaluate` scores the current committed ODS revision. `reset` appends a new revision containing the exact initial workbook and retains prior revisions/events. The `private/` fixture is evaluator-only and must not be mounted to Actors.
