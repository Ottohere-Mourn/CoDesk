Implement the Incident Triage and CSV Export feature in `~/workspace/ops-portal/`, which is on the `main` Git branch and served at `http://127.0.0.1:8096/` in Google Chrome.

Read `specs/spec_triage.pdf` and inspect `portal.db`. Add `GET /api/incidents/export?severity=LEVEL` to `app.py`. Match severity case-insensitively and exactly, sort matching records by `created_at` descending, and return CSV with the header `incident_id,service,severity,status,created_at`. Add the Triage navigation entry, severity filter, and CSV export control in `templates/layout.html` and `static/app.js`.

Restart the service with `bin/portalctl restart`. Verify the CRITICAL and HIGH filters through the live API and browser UI, including downloaded CSV contents. Save `~/workspace/verify_triage.json` containing the feature name, commit hash, and exact counts/verification results. Commit your completed feature on `main` and verify the service, commit, and record.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them. Verify the live service, Git state, and JSON record before finishing.
