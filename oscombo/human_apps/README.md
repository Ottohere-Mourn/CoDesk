# Handoff form fixture

`oscombo.human_apps.handoff_form` provides a small standard-library HTTP form app for a simulated human actor. It has no third-party dependencies or Guest/model calls.

```python
from oscombo.human_apps.handoff_form import create_fixture, make_server, evaluate

db_path = "/path/on/guest/handoff.sqlite"
manifest = create_fixture(db_path, run_id="run-001")
server = make_server(db_path, host="0.0.0.0", port=0)
# `server.server_address` gives the selected address and ephemeral port.
# Serve in a thread/process, then open that address from the Guest browser.
# After the user submits the form, evaluate(db_path) returns its offline Oracle result.
```

The public fixture manifest contains initial ticket state and a stable SHA-256 digest, not evaluation targets. The app exposes only `/`, `/submit`, and a plain `/healthz`; the Oracle is an offline Python API and has no HTTP endpoint. SQLite stores the current form state and an append-only submission history. Recreate the fixture before each run.

# Offline shared-mailbox workflow fixture

`oscombo.human_apps.mail_workflow` contains the proposed HA-MAIL local mailbox
fixture. Run-scoped SQLite state backs the ordinary Inbox, message-thread,
policy, review, draft, and Sent pages. Actors see the task evidence and use only
HTTP pages; the expected outcomes are checked by `evaluate()` after the actors
finish. The local app never contacts external email services.

# Offline shared-calendar planning fixture

`oscombo.human_apps.calendar_planning` provides a synthetic local Calendar UI with separate Personal and Project Team calendars, visible meeting brief/availability/room pages, and run-scoped SQLite state. `create_fixture()` creates the same reproducible empty calendar state used by User-only, Agent-only, Independent, Shared and Shared+PerActionLock. `evaluate()` is an offline post-run Oracle; the app never connects to a real calendar provider or sends invitations. See `docs/HA_CALENDAR_CASE_V1_20261110_ZH.md` for the task card, controls, pilot results and limitations.


# Offline inventory replenishment/receiving fixture

oscombo.human_apps.inventory_ops provides HA-INVENTORY, a local synthetic Warehouse Dashboard backed by run-scoped SQLite. The Codex GUI Actor drafts replenishments for SKU-A/B/C using visible stock, policy, approved vendor, case-pack and inbound pages; the scripted User receives SKU-D from a visible packing slip. create_fixture() restores the initial state and a source digest. evaluate() is an offline post-run Oracle for draft correctness, one-time receipt, and unchanged stock; it is never exposed as an Actor endpoint. The app has no connection to an external ERP/WMS. See docs/HA_INVENTORY_CASE_V1_20261111_ZH.md for the complete task, pilot runs and limitations.
