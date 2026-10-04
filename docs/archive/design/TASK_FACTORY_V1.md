# CoDesk Task Factory V1

## Four-level identity model

| Level | Identity | Defines | Does not define |
|---|---|---|---|
| Family | `family_id` | Interaction mechanism and evaluator contract, e.g. office control | App wording or run repetition |
| Template | `template_id` + version | Reusable initial-state renderer, independent goals, oracle and feasibility checks | Window positions or episode count |
| Instance | `task_id`, `instance_id`, seed | Concrete document/sheet content, goals, initial files, expected state and hashes | Condition, repetition, screen geometry |
| Run | `run_id` | One instance under a condition/repeat/budget/layout | A new benchmark task |

`RunConfig.window_geometry`, `repeat`, condition, Solo actor, and actor budget are outside the
instance manifest and content fingerprint. Changing them creates another run
record, never another task. The current factory keeps the actor schedule in the
template manifest so it is replayed identically across conditions.

## Manifest and reproducibility contract

Every generated instance includes:

- family, template/version, unique task and instance IDs, and a fixed integer seed;
- independent actor roles/goals, initial and expected authoritative state;
- non-target integrity constraints and an explicit disjoint-write-set joint-feasibility claim;
- evaluator/oracle definition and deterministic turn schedule;
- each initialization file's guest path, byte size, SHA-256, and base64 seed bytes;
- semantic content fingerprint and whole-manifest SHA-256.

`verify_manifest()` regenerates the object from its registered template and seed;
`verify_initial_files()` checks the embedded file bytes. `write_instance()` writes
an immutable per-instance directory and refuses to overwrite it. The CLI's
`verify` command checks all of these and runs the offline office oracle controls.
The factory is offline-only; environment reset and file seeding are injected
callbacks and it never launches a Guest or application.

## Registered templates and coverage

| Family | Template | Mechanism/variation | Current evidence |
|---|---|---|---|
| `CODESK-TA-OFFICE` | `writer_calc_independent_edits_v1` | Two distinct task entities/status goals; Writer body and Calc B2 are disjoint write sets | Existing fixed Writer+Calc task is the real-app anchor. Generated variants are offline candidates only. |
| `CODESK-TB-CLIPBOARD` | `clipboard_transfer_v1` | Unique Writer/Calc source tokens and destinations | Factory interface and saved-state oracle are offline-tested. Clipboard observer fidelity and Guest task are unvalidated; remain design-only. |

No new interaction family is introduced. Clipboard IDs produced by the factory
do not promote Clipboard 001 or change its evidence status.

## Current candidate set

Eight Office instances are checked in under `tasks/generated_v1/office_writer_calc/`.
They use seeds 0–7, distinct scenario text/goals, unique IDs, and exact seeded
FODT/FODS contents. For every candidate the offline validator checks:

1. Seed files parse to the declared initial state.
2. Writer Solo and Calc Solo each satisfy only the assigned goal and preserve the other artifact.
3. A jointly satisfying final state passes both actor oracles.
4. A non-target Calc mutation is rejected and reported as contamination.
5. IDs and semantic fingerprints are unique; the manifest regenerates byte-for-byte from its seed.

These checks establish offline oracle validity and structural joint feasibility,
not successful GUI execution. **New generated instances with Guest validation: 0.**

## Commands

Generate up to 300 instances without launching an environment:

```bash
python scripts/task_factory_v1.py generate \
  --family office_writer_calc --count 8 --start-seed 0 \
  --output tasks/generated_v1/office_writer_calc
```

Output paths are immutable: generation fails if the output directory already
exists. Verify a generated set:

```bash
python scripts/task_factory_v1.py verify tasks/generated_v1/office_writer_calc
```

Generate a Clipboard set only for offline fixture/interface development:

```bash
python scripts/task_factory_v1.py generate \
  --family clipboard --count 8 --start-seed 0 \
  --output tasks/generated_v1/clipboard_design_only
```

Clipboard output remains design-only until the Guest observer and task promotion
gates pass.
