# Case 4 Lite v1.0.0: frozen comparison plan (2026-10-31)

The task, native Kdenlive fixture, manifest, role instructions, Oracle, 15 desktop-call budget per actor, `gpt-6.1-sol` model, medium effort, relay settings, and KVM image remain the same in all three arms. A and B start together after setup. The only treatment is desktop topology: two Guests for Isolated, one Guest for Shared, and one Guest plus per-action desktop lock for Shared+Lock. Application setup starts each Guest and Kdenlive sequentially to avoid concurrent boot I/O; this occurs before the actor release in every arm.

Run one new episode in each arm, in this declared order, with fresh run roots:

1. `case4-v100-repeat-isolated-20261031a`
2. `case4-v100-repeat-shared-20261031a`
3. `case4-v100-repeat-shared-lock-20261031a`

All outcomes, including unexpected successes, failures, timeouts, and postprocessing faults, will be retained. An infrastructure-invalid episode may be repeated once after the cause is recorded and fixed; it will not be silently omitted. No task or scoring change will be made between arms. Report business Oracle, actor status, saved Guest artifacts, action/window timeline, lock wait, action duration, actor overlap, and total wall time separately. A focus-revalidation ablation, if attempted, is a fourth condition and will not be counted as part of the three-arm comparison.
