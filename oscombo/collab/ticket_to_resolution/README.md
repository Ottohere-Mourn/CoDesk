# Ticket-to-Resolution (`CDD-TTR-001`)

Deterministic, local synthetic after-sales workflow for Single-Agent, Collaborative-Isolated, and Collaborative-Shared execution. The business application is a GUI; there is no real payment gateway.

## Offline setup and evaluation

```bash
python -m oscombo.collab.ticket_to_resolution prepare /tmp/codesk-ttr/run-001 --run-id ttr-run-001
python -m oscombo.collab.ticket_to_resolution plan --condition collaborative_shared --run-id ttr-run-001 --output /tmp/codesk-ttr/run-001/run_config.json
python -m oscombo.collab.ticket_to_resolution evaluate /tmp/codesk-ttr/run-001
```

Evaluation before an episode is expected to fail the business-success check. The manifest and credentials are written under the run's private `oracle/` and `secrets/` directories. Keep those paths outside Actor context.

Start the app using the per-run credentials:

```bash
python -m oscombo.collab.ticket_to_resolution serve \
  --db /tmp/codesk-ttr/run-001/db/case.sqlite3 \
  --credentials /tmp/codesk-ttr/run-001/secrets/browser_credentials.json \
  --host 127.0.0.1 --port 8765
```

Start the existing CoDesk message/attachment service in a separate process:

```bash
python -m oscombo.collab.ticket_to_resolution collab-serve \
  --run-root /tmp/codesk-ttr/run-001
```

The episode plan and `integration.py` bind actor identity, message-service URL, and actor-scoped token to the existing `CodexHarness` collaboration MCP tools. No task or evaluator logic is added to the message server.

## Current implementation boundary

- `spec.py`: fixed gold fixture facts and full A/B/S instructions.
- `database.py`: deterministic SQLite seed, business transitions, idempotency, review validation, append-only business audit.
- `webapp.py`: visible support GUI and session/role enforcement.
- `oracle.py`: independent final-state, cross-reference, audit-order, and protected-state checks.
- `runner.py`: run setup, condition topology plan, ownership-checked reset, CLI.
- `guest_smoke.py`: real OSWorld GUI smoke; only use after resource and ownership preflight.

See `TASK_CARD_ZH.md` for the frozen task semantics and `IMPLEMENTATION_REPORT_ZH.md` for evidence boundaries and current smoke status.
