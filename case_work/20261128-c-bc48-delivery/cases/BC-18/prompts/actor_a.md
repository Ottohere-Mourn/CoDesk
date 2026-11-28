Process the security and access escalations in the local Escalation Hub at `http://127.0.0.1:18118/`.

Handle SEC-102, ACC-104, and SEC-109 using `ticket_sources.csv` and `escalation_policy.pdf`. Assign each ticket to the responsible team, prepare source-reference and impact evidence, and submit a Phase 1 review. Read the rejection details, add the missing root-cause evidence from the source notes, submit a new review, and approve only after the review is READY. Export the three approved records with evidence to `~/workspace/ticket_hub/out/security_access_approvals.json` and verify them in the ticket list.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
