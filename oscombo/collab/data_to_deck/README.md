# Data-to-Deck case package

This package is a separate, first executable implementation of case `CDD-RECON-001` v0.2.1. It does not change the OSWorld Combo runner or any historical result.

## Offline commands

Run from the repository root:

```bash
python -m oscombo.collab.data_to_deck prepare /tmp/cdd-instance
python -m oscombo.collab.data_to_deck plan single_agent --check-live
python -m oscombo.collab.data_to_deck plan collaborative_isolated
python -m oscombo.collab.data_to_deck plan collaborative_shared
python -m oscombo.collab.data_to_deck protocol-smoke --output /tmp/cdd-protocol-smoke
python -m oscombo.collab.data_to_deck serve --root /tmp/cdd-run/protocol --run-id cdd-run-001 --condition collaborative_shared
```

After actors have saved their outputs, score them with `evaluate`; see `TASK_CARD_ZH.md` for exact arguments. The evaluator is deterministic and checks each actor separately, the joint result, and protected non-target workbook content.

## Live run boundary

The condition planner fixes one Guest for Single-Agent, two isolated Guests initialized from the same fixture bundle for Collaborative-Isolated, and one shared live desktop for Collaborative-Shared. All conditions retain the same message/attachment capability and total model-token budget. This package does not yet bind a real OSWorld Guest lifecycle or Qwen3VLAgent. `plan --check-live` reports missing prerequisites without starting a Guest.

The message service is run-scoped, loopback-only, token-authenticated and append-only. It supports `POST /messages`, `GET /messages`, `POST /attachments`, and `GET /attachments/<id>`. Keep the startup tokens private. An OSWorld Guest bridge/forwarder and live actor adapter are still required before GUI agents inside Guests can use the service.

Current host-local LibreOffice import/export checks, if performed, are compatibility evidence only. They do not establish Guest ODS/ODP save/reopen, artifact collection, GUI window/focus logging, or reset behavior.
