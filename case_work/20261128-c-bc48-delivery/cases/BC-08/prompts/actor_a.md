Implement the Metrics Summary feature in `~/workspace/ops-portal/`, which is on the `main` Git branch and served at `http://127.0.0.1:8096/` in Google Chrome.

Read `specs/spec_metrics.pdf` and inspect `portal.db`. Add `GET /api/metrics/summary?start=YYYY-MM-DD&end=YYYY-MM-DD` to `app.py`. Use inclusive dates; exclude rows whose day or latency is NULL; return `avg_latency_ms`, `total_requests`, and `error_rate_pct`, with numeric results rounded to two decimal places. Add the Metrics navigation entry, date-range controls, and KPI cards in `templates/layout.html` and `static/app.js`.

Restart the service with `bin/portalctl restart`. Verify the three required ranges from the specification through the live API and browser UI. Save `~/workspace/verify_metrics.json` containing the feature name, commit hash, and exact range/result records. Commit your completed feature on `main` and verify the service, commit, and record.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them. Verify the live service, Git state, and JSON record before finishing.
