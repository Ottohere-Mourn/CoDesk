# CoDesk Writer + Calc: Real Dual-Agent Failure Cases

Source artifact root: `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-dual-agent-eval-20260929`. 2 failed or invalid model attempts retained.

## dualqwen-solo-r01-20260929

- Condition/repeat: `solo` / `1`
- Valid for model scoring: `False`
- Category: `experiment_management_abort`
- Reason: `A separate active Qwen Solo run was detected on the shared OSWorld host. This run was interrupted to avoid simultaneous model loading and exceeding the single-worker resource plan.`
- Scenario: `None`
- Actor goals: `{'writer_actor': None, 'calc_actor': None}`
- Actor errors: `{}`
- Artifacts: `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-dual-agent-eval-20260929/dualqwen-solo-r01-20260929`

## dualqwen-solo-r01b-20260929

- Condition/repeat: `solo` / `1`
- Valid for model scoring: `False`
- Category: `environment_service_failure`
- Reason: `OSWorld screenshot service at localhost:5000 repeatedly timed out during Writer readiness. At interruption, separate OSWorld QEMU Guests from other run IDs were concurrently active and also forwarded localhost:5000; the run is contaminated for readiness diagnosis and excluded from model scoring.`
- Scenario: `None`
- Actor goals: `{'writer_actor': None, 'calc_actor': None}`
- Actor errors: `{}`
- Artifacts: `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-dual-agent-eval-20260929/dualqwen-solo-r01b-20260929`
