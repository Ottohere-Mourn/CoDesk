# Timeline-and-Assets (`CDD-TLA-001`)

Offline-first case package for a small real-editor video task. The project is an MLT XML `.kdenlive` document with a Kdenlive subtitle sidecar; it is **not** a custom editor. This machine has no `kdenlive` or `melt` executable, so opening, saving, rendering and Guest interaction are pending real Kdenlive/OSWorld validation.

See [`TASK_CARD_ZH.md`](TASK_CARD_ZH.md) and [`IMPLEMENTATION_REPORT_ZH.md`](IMPLEMENTATION_REPORT_ZH.md). Fixed media is in `template/assets/`; the partial starter is `template/project/GreenLoop.kdenlive` and its SRT sidecar. The hidden parser/gold contract lives in package code and must not be mounted into an Actor workspace.

```bash
python -m oscombo.collab.timeline_and_assets prepare /tmp/codesk-tla/run-001 --run-id tla-run-001
python -m oscombo.collab.timeline_and_assets configure /tmp/codesk-tla/run-001 --condition collaborative_shared
python -m oscombo.collab.timeline_and_assets collab-serve --run-root /tmp/codesk-tla/run-001 --port 8767
python -m oscombo.collab.timeline_and_assets evaluate /tmp/codesk-tla/run-001
python -m oscombo.collab.timeline_and_assets reset /tmp/codesk-tla/run-001 --run-id tla-run-001
python -m pytest -q tests/test_timeline_and_assets.py
```

The positive project used in tests is constructed by the private fixture helper. A model episode must save its project through the actual Kdenlive GUI; direct XML generation is only a deterministic test oracle fixture.
