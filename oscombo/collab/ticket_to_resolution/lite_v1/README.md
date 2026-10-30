# Ticket-to-Resolution Lite v1

Lite v1 is a separate short-task variant of `CDD-TTR-001`; the original task, fixtures, full UI, and Oracle remain unchanged. The compact Case Desk page keeps the ticket, order lines, delivery evidence, policy, review form, and processor form together. The independent Oracle still checks business state and audit evidence.

## Collaborative dependency

Role A can save the structured review; only role B can issue the refund and resolve the ticket. The service rejects a refund that does not match A's valid review, source evidence, order line, and amount. B must read A's collaboration message and open the saved review in the GUI. The coordinator records message sends/reads, review creation, GUI review access, refund, and resolution separately. The positive scripted control uses six A and seven B GUI actions (13 total, excluding login, setup, screenshots, and the collaboration read); the negative control submits an incorrect amount and verifies that no refund succeeds.

## Validation

Run the focused offline tests with the local proxy bypassed for loopback services:

```bash
NO_PROXY='127.0.0.1,localhost,::1,10.0.2.100' no_proxy='127.0.0.1,localhost,::1,10.0.2.100' \
  .venv/bin/pytest -q tests/test_ticket_to_resolution.py tests/test_ticket_to_resolution_lite.py
```

Real Guest scripted controls:

```bash
PYTHONPATH="$PWD" /opt/data/private/mjh/deps/osworld/venv-native-qemu/bin/python \
  infra/run_ticket_to_resolution_lite_native.py --mode controls \
  --condition collaborative_shared --run-id ttr-lite-shared-controls-UNIQUE
```

Use `collaborative_isolated` for the two-desktop control. The Guest runner waits for a rendered desktop and checks that the Guest can fetch the sign-in page before running controls. If the Guest capture source matches the audited original SHA, it applies the lossless fast-PNG encoding repair only inside the run-owned overlay, verifies the service restart, and preserves the source/diff/hash evidence. The read-only OSWorld base image is never changed.

Real screenshot-driven model episodes use the private configuration at `/opt/data/private/mjh/secrets/codesk-gui-pilot.json`; never copy its credentials into the repository or command line:

```bash
PYTHONPATH="$PWD" /opt/data/private/mjh/deps/osworld/venv-native-qemu/bin/python \
  infra/run_ticket_to_resolution_lite_model.py --condition single_agent \
  --run-id ttr-lite-single-UNIQUE
```

Use the same runner with `collaborative_shared` or `collaborative_isolated` for paired conditions. `--pilot` applies an explicitly smaller action/time budget; `--mitigation input-lock` is a separate Shared-only ablation. A normal early B exit before A's review/message is visible pauses B without model or desktop calls and resumes the same private Codex session when the public handoff is ready; the role wall-clock and shared desktop-call budgets continue unchanged.

## Evidence

Each unique run ID gets a private directory under `/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite/`. Keep failed runs. Controls store screenshots, scripted GUI actions, collaboration events, Oracle results, image/cleanup checks, and progress checkpoints. Model runs additionally store role traces, screenshots, model request usage/latency, focus and input-overlap samples, lifecycle events, resource samples, Oracle and handoff audits, and a pre-reset SQLite snapshot.
