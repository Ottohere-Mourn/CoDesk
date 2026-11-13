# Case 4 Lite v1.0.0: frozen comparison plan (2026-10-31)

The task, native Kdenlive fixture, manifest, role instructions, Oracle, 15 desktop-call budget per actor, `gpt-6.1-sol` model, medium effort, relay settings, and KVM image remain the same in all three arms. A and B start together after setup. The only treatment is desktop topology: two Guests for Isolated, one Guest for Shared, and one Guest plus per-action desktop lock for Shared+Lock. Application setup starts each Guest and Kdenlive sequentially to avoid concurrent boot I/O; this occurs before the actor release in every arm.

Run one new episode in each arm, in this declared order, with fresh run roots:

1. `case4-v100-repeat-isolated-20261031a`
2. `case4-v100-repeat-shared-20261031a`
3. `case4-v100-repeat-shared-lock-20261031a`

All outcomes, including unexpected successes, failures, timeouts, and postprocessing faults, will be retained. An infrastructure-invalid episode may be repeated once after the cause is recorded and fixed; it will not be silently omitted. No task or scoring change will be made between arms. Report business Oracle, actor status, saved Guest artifacts, action/window timeline, lock wait, action duration, actor overlap, and total wall time separately. A focus-revalidation ablation, if attempted, is a fourth condition and will not be counted as part of the three-arm comparison.

## Storage repair amendment (2026-11-01)

The declared HDD Isolated run completed with a valid business FAIL: A saved the manifest and B exhausted 15 calls, leaving the wrong clips on V1/V2. The declared HDD Shared run failed before model release when the manifest editor never opened. A subsequent `setup-only` diagnostic failed before model release with Kdenlive stuck in uninterruptible disk wait. Both invalid setup runs remain in place and are excluded from business comparisons. The host's source image and overlay were on a spinning disk during sustained I/O pressure.

Copy the same native fixture image byte-for-byte to the host SSD, verify equal SHA-256 hashes, and place fresh overlays on the SSD. Run one `setup-only` check before model calls. If setup succeeds, make a new, separate storage-coherent three-arm cohort, in this order:

1. `case4-v100-ssd-isolated-20261101a`
2. `case4-v100-ssd-shared-20261101a`
3. `case4-v100-ssd-shared-lock-20261101a`

The task, fixture bytes, Oracle, role instructions, model settings, call limits, and actor release protocol remain frozen. The HDD Isolated episode is reported separately and never pooled with this cohort. Keep all SSD outcomes, including further setup faults; do not select successful runs to create the comparison.

## Prospective SSD replication (2026-11-01)

The first SSD cohort completed Isolated PASS, Shared FAIL, Shared+Lock PASS. The locked run still contained cross-call window misroutes, but the agents recovered. To assess whether the apparent lock benefit and Isolated/Shared gap repeat, run exactly one more SSD episode per arm with unchanged code, model, fixture, image, limits, and topology, in this order:

1. `case4-v100-ssd-isolated-20261101b`
2. `case4-v100-ssd-shared-20261101b`
3. `case4-v100-ssd-shared-lock-20261101b`

Report all outcomes, regardless of direction. Stop further Case 4 model repeats after this cohort and move to Case 2.
