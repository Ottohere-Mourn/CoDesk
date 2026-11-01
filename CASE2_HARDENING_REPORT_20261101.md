# Case 2 Lite v1.1.3: HealthCare hardening and three-arm comparison

Branch: `codex/case2-hardening`. The fixture, role task, GUI, backend state machine, Oracle, `gpt-6.1-sol` medium, 15 desktop calls per actor, and 1800 s actor wall cap were held fixed across the new model arms. A and B start together. The same B handoff suspension rule applies in both desktop topologies. Only Shared+Lock adds the per-input lock. Raw run directories, screenshots, databases, and credentials remain outside Git.

## Code and environment

`03f40d4` parses both numeric ProtocolStore timestamps and SQLite ISO timestamps, audits actual B `read_messages` calls against GUI review events, and separates `business_status`, `collaboration_process_status`, `execution_status`, and reset/cleanup faults. The old reset exception could replace a real business FAIL with `INFRA_FAIL`; the new report retains both outcomes. `b5414d5` predeclared the three model IDs and symmetric 1800 s cap. `14ccc96`, `d04febd`, and `dee3fde` documented and implemented a byte-identical SSD Guest image and predeclared Isolated/Shared controls. `5fa050d` accepts the already predeclared `ttr-v113-hardening-*` model IDs; the initial pre-Guest invocation failed validation without creating a run or calling the model. The image copied from the HDD has matching source/destination SHA-256 `28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a`.

The Case 2 runner tests pass (14/14). The new runs report KVM, one shared business service/database per run, unchanged base image, a reliable pre-reset Oracle snapshot, pristine database reset, released ports, and Guest/overlay cleanup. Early Guest screenshot timeouts recovered during setup; no new model arm has an infrastructure or API failure.

## Real Guest GUI scripted controls

| Topology | Run ID | Positive | Negative | Reset/cleanup |
| --- | --- | --- | --- | --- |
| Isolated | `ttr-v113-hardening-isolated-control-20261101a` | A6/B7, correct $88 refund and resolved ticket, Oracle PASS | A6/B4, wrong amount rejected, zero refunds, Oracle FAIL as intended | Pristine/verified |
| Shared | `ttr-v113-hardening-shared-control-20261101a` | A6/B7, correct $88 refund and resolved ticket, Oracle PASS | A6/B4, wrong amount rejected, zero refunds, Oracle FAIL as intended | Pristine/verified |

Both positive and negative controls include an actual B message read and GUI review view. They use the same SSD image and Guest Adapter as the model cohort. The earlier HDD Isolated control `ttr-lite-healthcare-v113-isolated-control-20261031a` also passed, but it is not pooled with SSD performance.

## Frozen SSD model cohort

| Arm and run ID | Business / process / execution | A/B calls | B suspended | Actor wall / total run | GUI input overlaps |
| --- | --- | --- | ---: | ---: | ---: |
| Isolated `ttr-v113-hardening-isolated-20261031a` | PASS / FAIL / VALID | 8/12, both done | 255.51 s | 821.61 / 1416.37 s | 0 |
| Shared `ttr-v113-hardening-shared-20261031a` | PASS / FAIL / VALID | 10/14, both done | 124.25 s | 901.38 / 1107.17 s | 0 |
| Shared+Lock `ttr-v113-hardening-shared-lock-20261031a` | PASS / FAIL / VALID | 10/15, B reached call cap after business completion | 174.34 s | 543.42 / 734.19 s | 0 |

In all three runs the Oracle confirms one A-authored review, one B-issued $88 refund on damaged line O-2048-L2, order remaining $147, and T-1042 resolved with the saved transaction. All three have pristine reset and verified cleanup. The B suspension occurs in both Isolated and Shared, so it is a collaboration scheduling cost, not a Shared-only effect. The actor wall measures model execution; total run time also includes Guest boot, setup, Oracle, reset, and cleanup. Different model trajectories and server load prevent causal inference from wall-time differences.

## Strict handoff and the real information dependency

The strict audit requires A's saved review, A's message, B's actual read, B's GUI review view *after that read*, then B's refund. Its failure in all three runs is supported by pre-reset SQLite audit events and collaboration read logs, not timestamp parsing ambiguity:

| Arm (UTC) | A saved review | B opened review | A sent message | B read message | B issued refund |
| --- | --- | --- | --- | --- | --- |
| Isolated | 09:09:46.921 | 09:09:47.125 | 09:10:23.775 | 09:10:37.280 | 09:14:33.478 |
| Shared | 09:26:47.890 | 09:26:50.421 | 09:27:18.848 | 09:27:37.396 | 09:32:48.361 |
| Shared+Lock | 09:45:06.924 | 09:45:08.272 | 09:45:31.859 | 09:45:42.722 | 09:48:13.356 |

The backend refuses a refund without an A-saved, current review and the correct line/amount; the negative controls verify that. Thus A's review is a necessary, verifiable business dependency for B's refund. The message is currently an audited process event, not a backend prerequisite or necessary information source: B can discover the review in the shared service seconds after A saves it. The model then reads the handoff but does not reopen the review, contrary to the task's specified order. The B GUI screenshot after reading may still show the open review; it does not establish that the first review view occurred after the read. Do not claim strict collaboration PASS from these three business successes.

## Shared GUI interference and Action Lock

The new SSD Shared and Shared+Lock runs both passed the business Oracle. Their desktop proxy records zero cross-actor same-Guest input overlaps, zero proxy errors, and no confirmed misrouting. Foreground changes during five sampled inputs in each arm are diagnostic candidates only: the window samples are not atomic and screenshots must support attribution. Shared B's action-4 screenshot shows the correct saved review; action 10 shows the $88 refund and unresolved ticket; action 14 shows the green resolved-ticket receipt. Locked B's action 15 also shows the correct refund and resolved ticket. This cohort therefore does not demonstrate an additional Shared business failure or a benefit from Action Lock.

The locked run logged 22 GUI inputs and exactly 0 s measured lock wait. Shared without lock already had zero overlapping inputs; the lock had no collision to prevent in this episode. Its shorter wall time and larger reported token use (357,069 versus Shared 212,199) are model/run variability, not a measured speedup or overhead caused by the lock. The old 900 s locked run `ttr-lite-healthcare-v113-shared-lock-20261031a` failed with A timeout and B `handoff_wait_timeout` after 856.54 s suspended and only two B calls; that was budget-invalid, not evidence that the lock caused a business failure. Raising the symmetric actor cap to 1800 s allowed the new locked run to finish, with 174.34 s B suspended and no lock contention.

The earlier HDD Shared run `ttr-lite-healthcare-v113-shared-20261031a` is a useful counterexample: B's third screenshot shows A's browser on its sign-in page after a shared-window sign-out interaction, both actors exhausted 15 calls, and the raw Oracle has zero saved reviews/refunds and the ticket OPEN. Its final `INFRA_FAIL` was a subsequent reset exception caused by the A browser still being at sign-in; the business failure remains real and is now reported separately by the hardened runner. A second earlier Shared run `...shared-20261031b` passed the business Oracle, as did the earlier Isolated run `...isolated-20261031a`. These older 900 s HDD episodes are not pooled with the new 1800 s SSD cohort.

## Supported conclusion and limit

The Case 2 Lite business task is solvable on real KVM Guest GUI in both topologies, and the scoring/reset path now distinguishes business, strict process, model validity, and infrastructure. The current small SSD cohort is 1/1 business PASS in each arm; it cannot establish a Shared disadvantage or an Action Lock benefit. One older Shared failure has screenshot-supported cross-window sign-in disruption, but Shared also succeeded in another old run. The systematic strict-process failure reveals that the message is not a necessary information channel in the present task; making it necessary would require an explicitly new, symmetrically applied task/GUI version and fresh controls/comparison, not reinterpretation of these runs.
