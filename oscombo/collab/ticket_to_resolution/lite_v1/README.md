# Ticket-to-Resolution Lite v1.2.0

Lite v1.2.0 is a short-task Case 2 workflow based on `CDD-TTR-001`. It retains the v1.1.3 T-1042 fixture, orders, policies, money rules, backend state machine and review requirement. Versioned B-only pre-verification is a scored double-check record; it does not alter the expected $88 dock-only refund.

## Collaborative workflow

A checks the source records, saves the current Case Review, and sends B its actual generated Review ID without the proposed amount. B first saves an independent eligibility/line/evidence/shipping/total check, then reads A's message and enters its Review ID in the GUI lookup. B compares both records before issuing the refund and resolving the ticket. The Lite home page has no Review polling or latest-ID disclosure. B cannot open the Review GUI route until a pre-verification exists. Review opens, collaboration reads, order, refund and resolution events are audited separately.

The same task and checks apply in Isolated, Shared and Shared+Lock. Do not treat a Shared failure as a success criterion. The existing 15 desktop-call budget per actor and 1800-second actor wall limit remain provisional until the symmetric Isolated model pilot establishes sufficient margin.

## Validation

```bash
/opt/miniconda3/bin/python -m pytest -q \
  tests/test_ticket_to_resolution_lite.py \
  tests/test_ticket_to_resolution_lite_model_runner.py \
  tests/test_ticket_to_resolution_lite_native_diagnostics.py
```

The HealthCare orchestration entrypoint is `infra/run_ticket_to_resolution_lite_healthcare.py`. Run scripted controls on Isolated and Shared before the model pilot. Control defaults cover positive, wrong-refund, wrong-precheck and missing-Review-ID paths:

```bash
PY=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python
$PY infra/run_ticket_to_resolution_lite_healthcare.py --mode controls \
  --condition collaborative_isolated --run-id ttr-lite-v120-control-isolated-UNIQUE
```

Model arms must run serially with a new run ID and identical budget, Guest image, task, fixture, instructions and wall cap. Preserve all logs and reset/cleanup outcomes in each run root. Private model credentials live only on HealthCare and must never be copied into the repository or logs.
