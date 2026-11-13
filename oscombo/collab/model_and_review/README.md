# Model-and-Review

`CDD-MAR-001` is an offline implementation of a two-role Blender lamp geometry and presentation case. The oracle contract, run plans, actor instructions, message binding and Blender-side generator are present.

**Current status: `REAL_BLEND_FIXTURE_AND_BACKGROUND_ORACLE_VALIDATED / GUI_GUEST_PENDING`.** Genuine initial and private Gold `.blend` files were generated and reopened with Blender 5.2.2 LTS. The structural oracle and run reset were exercised on real files. No Blender GUI, OSWorld Guest, or model was launched.

Read [`TASK_CARD_ZH.md`](TASK_CARD_ZH.md) and [`IMPLEMENTATION_REPORT_ZH.md`](IMPLEMENTATION_REPORT_ZH.md). The private Gold is `fixtures/gold_state.json`; do not copy it into an Actor workspace. `blender/build_fixture.py` creates a genuine Blender file only when explicitly run in Blender. `oracle.py` evaluates normalized snapshots offline and uses Blender itself to extract state from a real `.blend`.

## Offline commands

```bash
python -m pytest tests/test_model_and_review.py
python -m oscombo.collab.model_and_review plan --condition collaborative_shared --run-id mar-example
```

The checked-in fixture locations are `fixtures/initial.blend` and `fixtures/private/gold.blend` (keep the Gold outside Actor workspaces). Reproduce them with the project-local Blender 5.2.2 binary:

```bash
BLENDER_BIN="${CODESK_BLENDER_BIN:?set this to a local Blender 5.2+ executable}"
OMP_NUM_THREADS=2 "$BLENDER_BIN" --background --factory-startup -t 2 \
  --python oscombo/collab/model_and_review/blender/build_fixture.py -- \
  --output oscombo/collab/model_and_review/fixtures/initial.blend --variant initial
OMP_NUM_THREADS=2 "$BLENDER_BIN" --background --factory-startup -t 2 \
  --python oscombo/collab/model_and_review/blender/build_fixture.py -- \
  --output oscombo/collab/model_and_review/fixtures/private/gold.blend --variant gold
```

The Blender 5.x writer may store `.blend` files as Zstandard-compressed containers. The adapter accepts the plain Blender signature or Zstandard container signature, then requires Blender itself to open and parse the scene before a real artifact is evaluated.

`prepare`, `evaluate`, and `reset` now use the genuine starter fixture. The first background save/reopen/oracle/reset validation passed; Guest GUI interaction and live application-state logging remain pending.
