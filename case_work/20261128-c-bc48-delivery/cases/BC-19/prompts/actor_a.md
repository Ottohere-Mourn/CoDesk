Configure and validate the risk-decision policy in `~/workspace/rule_lab/rules.yaml`.

Use `rule_requirements.txt` and `risk_tests.csv`. Set the 60-second velocity window, review threshold, maximum-attempt rule, and blocked region so all five expected decisions match. Preserve the routing section when editing the full rules document. Reload the engine at `http://127.0.0.1:18119/reload`, run `/evaluate/risk`, and save its complete results to `~/workspace/rule_lab/out/risk_report.json`.

The public engine schema is JSON-compatible YAML: the `risk` object uses exactly `velocity_window_s` (integer seconds), `min_risk_to_review` (numeric score threshold), `max_attempts` (integer), and `blocked_region` (region string). Derive their values from `rule_requirements.txt` and the test inputs. Keep the top-level `version` and `routing` objects intact. Apply with HTTP POST `/reload`; GET `/evaluate/risk` returns the full regression report.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
