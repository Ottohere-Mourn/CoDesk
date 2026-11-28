Configure and validate the request-routing policy in `~/workspace/rule_lab/rules.yaml`.

Use `rule_requirements.txt` and `route_tests.csv`. Add every required path rule with its exact primary, fallback, and timeout values. Preserve the risk section when editing the full rules document. Reload the engine at `http://127.0.0.1:18119/reload`, run `/evaluate/routes`, and save its complete results to `~/workspace/rule_lab/out/routing_report.json`.

The `routing` object contains `rules`, an array of objects with exactly `path`, `primary`, `fallback`, and numeric `timeout_s`. Derive values from `route_tests.csv`. Keep the top-level `version` and `risk` objects intact. Apply with HTTP POST `/reload`; GET `/evaluate/routes` returns the full regression report.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
