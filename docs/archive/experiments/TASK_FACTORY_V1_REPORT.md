# Task Factory V1 offline build report

## Result

The current build contains **2 registered templates across 2 existing families**.
It generated and saved **8 Writer+Calc candidate instances** (seeds 0–7). All 8
passed deterministic regeneration, initialization-file hash checks, exact
initial-state parsing, separate Writer/Calc Solo oracle controls, joint oracle,
non-target contamination negative control, and semantic deduplication.

| Measure | Count / status |
|---|---:|
| Registered templates | 2 |
| Persisted Writer+Calc candidates | 8 |
| Writer+Calc candidates passing all offline checks | 8 / 8 |
| New generated candidates validated in Guest | 0 |
| Clipboard candidates persisted | 0 |
| Clipboard template manifests verified offline | Supported, design-only |
| 250-seed generation capacity check | 250 unique IDs/fingerprints in dry-run |

The fixed legacy Writer+Calc instance remains the only real-app anchor. Its
historical evidence is untouched. The eight new instances only establish that
the factory and oracle contract work on generated artifacts; they do not inherit
the anchor's real-app success rate. Clipboard 001 remains design-only pending
the observer-on/off and Guest task gates.

## Template coverage matrix

| Family / template | What varies per instance | Reused code | Offline checks | Real status |
|---|---|---|---|---|
| Office / `writer_calc_independent_edits_v1` | Case entity, Writer draft/final text, Calc row key/status; actor write sets remain Writer body and Calc B2 | OSWorld adapter, existing Writer/Calc evaluator XML parsers, shared Flat ODF renderer; old runner seed helpers now call that renderer | 8 generated manifests and all oracle controls pass | Existing seed-0 task is an anchor; generated instances unvalidated in Guest |
| Clipboard / `clipboard_transfer_v1` | Distinct source tokens, exact destinations, generated ODF files | Common manifest/hash/run interfaces and parameterized Clipboard evaluator | Manifest/file hashes and dynamic initial/final ODF evaluator tested | Design-only; observer fidelity, setup, reset, and MA-ID topology remain unvalidated |

No task count is added by coordinates, window layout, repeat number, or actor
budget. These values are in `RunConfig` and its `run_id`, not a `task_id` or
content fingerprint.

## Reproduction and commands

The checked-in candidate set can be verified with:

```bash
python scripts/task_factory_v1.py verify tasks/generated_v1/office_writer_calc
```

The generator supports a dry-run or persisted range up to 300 instances. For
example, a future 250-item output should use a new, empty output path:

```bash
python scripts/task_factory_v1.py generate \
  --family office_writer_calc --count 250 --start-seed 1000 \
  --output tasks/generated_v1/office_writer_calc_250
```

No 250-item set was written in this phase. A dry-run generated 250 unique task
IDs in 0.36 seconds with about 22 MiB peak RSS. The saved eight-instance set
occupies 130,165 bytes. A linear estimate for 300 similarly small instances is
about 4.9 MB and under a second of generator time; actual size/time may vary with
content and filesystem. This estimates manifest production only, not human
review or Guest evaluation.

For a full controlled matrix of Solo Writer, Solo Calc, MA-ID, and MA-SD, the
episode count is `instances × 4 conditions × repeats`. Thus 200–300 instances at
3 repeats would require 2,400–3,600 episodes. Guest time per episode is not
estimated here because this offline-only phase collected no new Guest timings.

## Limitations and next gates

1. Review whether the eight generated case prompts constitute useful task
   instances for humans/models, not merely valid data permutations. The factory
   must not be presented as 200–300 novel interaction mechanisms.
2. Run a small, resource-approved Guest subset before changing generated task
   evidence status. Confirm LibreOffice saves/reopens all generated Flat ODF files
   exactly and that the target controls remain stable across content variants.
3. Keep Clipboard observer-on/off and a same-backend MA-ID adapter as separate
   real-environment gates; the factory does not bypass either.
4. Only after the template passes those gates, decide whether to persist a larger
   instance set. Bulk generation is not itself validation.
