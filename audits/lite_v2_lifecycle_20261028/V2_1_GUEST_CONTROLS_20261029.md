# Lite v2.1 real Guest controls (2026-10-29)

This is validation of the independent v2.1 Adapter and equivalent-unit Oracle. It does not replay the frozen model comparison. Both positive scripted Actors edit real Ubuntu OSWorld GUI applications through QEMU TCG. Scripted controls run A then B to deterministically test files, messages and scoring; they are not evidence of concurrent model behavior.

| Control | Unique run ID | Guests | Real GUI calls A/B | Oracle A/B/joint | Reopen/reset | Wall time |
|---|---|---:|---:|---|---|---:|
| Shared positive | `cdd-lite-v2-1-scripted-shared-pos-20261029T105609Z` | 1 | 7/6 | PASS/PASS/PASS | passed / 1 clean | 904 s |
| Isolated positive | `cdd-lite-v2-1-scripted-isolated-pos-20261029T111132Z` | 2 | 7/6 | PASS/PASS/PASS | passed / 2 clean | 1407 s |
| Shared wrong-value negative | `cdd-lite-v2-1-scripted-shared-neg-20261029T113521Z` | 1 | 7/6 | FAIL/FAIL/FAIL (expected) | passed / 1 clean | 832 s |

Both positive runs show actual Calc and Impress windows in GUI action logs and save real ODS/ODP outputs. The Isolated bridge published revision 1 for each role, verified saved bytes in the peer Guest, and reported zero sync errors. Both own outputs reopened byte-identically; the other role's copy reopened read-only. The public Fixture bytes and A/B base role instructions match v2.0.0, while the Guest root and scorer version are separate. The longer Isolated wall time includes two TCG Guest boots and resets; it does not estimate a model execution penalty.

The Shared negative control performed real Calc and Impress GUI actions. It deliberately saved `-10` in A's analysis while the public source implies `-11`. The v2.1 Oracle rejected A's signed change and B's consistency with that saved analysis, despite accepting B's wording and source citation. Thus A/B/joint are FAIL for the intended scoring reason; this is the expected **negative-control pass**, not a model failure. The runner exited 2 because the scored task failed; file recovery, reopen, sync and reset succeeded.

Versioned [control evidence](evidence/v2_1_guest_controls) contains selected real GUI screenshots and actions, messages, saved-file revision events, final ODS/ODP files, Oracle outputs, reopen checks, reset results and SHA-256 manifests. The positive controls had zero bridge sync errors; each produced one saved revision per role. The negative run likewise had a verified bridge and no sync errors.

The original v2.0.0 formal Shared/Isolated runs and their frozen Oracle outputs remain unchanged. [The scorer control file](v2_1_rescore_controls.json) reports retrospective v2.1 scores on those real artifacts, explicitly as re-scoring rather than a new episode. The real Guest handoff wake diagnostic is reported in [CONTINUATION_REPORT.md](CONTINUATION_REPORT.md).
