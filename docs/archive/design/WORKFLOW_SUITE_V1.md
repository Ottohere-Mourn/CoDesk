# CoDesk V1 Workflow Suite

## Frozen scope

The benchmark has five families and four software domains. Workflow identity depends on a distinct application-operation graph and shared state, not on text, seed, or window geometry. The first 15 workflows remain preserved in `benchmarks/codesk_v1/` as the previous 600-instance prototype/production snapshot. The final suite is generated separately at `benchmarks/codesk_v1_final/`.

| Family | Workflow IDs | Count |
|---|---|---:|
| Focus / Input Routing | F-01, F-04, F-02, F-N1, F-05, F-06, F-07 | 7 |
| Clipboard State | C-01, C-03, C-02, C-N1, C-04, C-05, C-06 | 7 |
| Application Context | A-01, A-N1, A-03, A-04, A-05 | 5 |
| Selection / Active Object | A-02, S-01, S-N1, S-02, S-03, S-04 | 6 |
| Undo / Redo History | U-01, U-N1, U-02, U-03, U-04 | 5 |
| **Total** | 30 workflows | **30** |

## Evidence labels

- `SCRIPTED / GUEST-VALIDATED`: use only when a preserved real Guest run exists for that exact workflow/version.
- `OFFLINE-CODE-READY`: schema, deterministic fixtures, evaluator, runtime binding, runtime-plan compilation, and FakeBackend lifecycle gates pass.
- `DESIGN-ONLY`: no concrete production runtime binding.

The 15 second-wave workflows are `OFFLINE-CODE-READY`; they are not Guest-validated. FakeBackend tests are explicitly not benchmark evidence. Existing historical evidence remains attached to the first-wave artifacts and is not rewritten by this expansion.

## Topology protocol

Solo scores one selected actor and protects the inactive actor's target. MA-ID runs both actors on independently controlled desktops from equivalent initialized fixtures. MA-SD serializes GUI actions on one desktop. Goals, fixture, model/action budget, evaluator, and workflow schedule are held fixed across MA-ID and MA-SD. Real execution must separately report scheduled exposure, observed interference, outcome, and recovery.
