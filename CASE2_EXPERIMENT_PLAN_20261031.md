# Case 2 Lite v1.1.3: comparison plan (2026-10-31)

The ticket, order, evidence, policy, application, role instructions, fixture, Oracle, 15 desktop-call budget per actor, model, effort, and Guest image are identical across arms. The audit fix at `03f40d4` changes reporting only: business success, strict collaboration process, model/budget status, and reset faults remain separate. The A review is a backend prerequisite for B's refund; the collaboration message is audited as a process event, not assumed necessary for the transaction.

After Case 4's planned comparison finishes, run one fresh episode each in this order:

1. `ttr-v113-hardening-isolated-20261031a`
2. `ttr-v113-hardening-shared-20261031a`
3. `ttr-v113-hardening-shared-lock-20261031a`

Use an explicit 1800-second wall limit for both actors in all three arms. The older 900-second runs remain a separate cohort; do not pool them as equivalent. Start A and B together, retain the existing symmetric B handoff suspension rule, and apply only the input lock in the third arm. Keep all outcomes, including unexpected successes and infrastructure faults. Report business Oracle, strict handoff audit, screenshot-supported focus errors, lock wait, active model time, suspension time, and total wall time separately.
