# Build-and-Verify (`CDD-BV-001`)

This independent case is an offline, synthetic OrderDesk source repair plus browser regression workflow. See [`TASK_CARD_ZH.md`](TASK_CARD_ZH.md) for the frozen task and [`IMPLEMENTATION_REPORT_ZH.md`](IMPLEMENTATION_REPORT_ZH.md) for implementation boundaries and test evidence.

```bash
python -m oscombo.collab.build_and_verify prepare runs/build_and_verify/local-001 --run-id local-001
python -m oscombo.collab.build_and_verify configure runs/build_and_verify/local-001 --condition collaborative_shared
python -m oscombo.collab.build_and_verify serve --run-root runs/build_and_verify/local-001 --port 8766
```

Sign in using the role-specific password in the run's private `secrets/browser_credentials.json`. In a separate process, `collab-serve --run-root ...` exposes the existing run-scoped Data-to-Deck message and attachment API. The hidden oracle baseline and credentials must never be mounted into an Actor workspace.

Offline tests: `python -m pytest -q tests/test_build_and_verify.py`. These tests include HTTP/API and a fake-DOM event contract; they are not real browser or OSWorld Guest evidence. No Guest/model runner is included in this first offline phase.
