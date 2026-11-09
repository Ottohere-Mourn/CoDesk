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
