# Shared-Workspace Benchmark V2 Task Suite

## Status and scope

V2 contains two mechanism-focused tasks and eight validated real-Guest episodes. During Phase 3, the three legacy GUI+Human Replay focus episodes were rerun into fresh output directories under the current ownership ledger and stamped with the same task version and provenance schema as the five existing suite episodes. All actors are deterministic scripted actors. No model was loaded, no evaluator rule was changed, and no benchmark task-count sweep was performed.

| Task | Interaction mechanism | Independent goals | Naive trigger | Recovery condition | Evaluator |
|---|---|---|---|---|---|
| `SWCUB-FOCUS-ROUTING-001` | GUI control contention over one desktop's active window and keyboard focus | GUI writes `Approved` to Document; Human Replay writes `Review note` to Chat | GUI observes Document; Human Replay takes Chat focus and writes; GUI types without reacquiring focus | GUI reselects Document after Human Replay's turn, then types | `GuestFocusEvaluator`, reading exact Guest terminal files after actors finish |
| `SWCUB-STALE-MERGE-001` | GUI cached record conflicts with a CLI update to shared application state | GUI sets `gui_status=Approved`; CLI sets `cli_note=Reviewed by CLI` | GUI observes cached revision 0; CLI writes revision 1; GUI saves its stale whole-record cache and drops the CLI field | GUI refreshes the latest state before editing and saving | `GuestWebStateEvaluator`, reading the Guest-local service's final JSON after actors finish |

Task definitions and condition mapping are machine-readable in [`tasks/task_suite_v2.json`](tasks/task_suite_v2.json). The runner and validator reuse the pinned OSWorld V2.1 adapter, existing scripted actors, orchestrator, and evaluator implementations. Actor contexts do not expose evaluator callbacks or hidden backend state.

## Task A — GUI control contention

**Task ID:** `SWCUB-FOCUS-ROUTING-001`
**Guest surface:** one OSWorld V2.1 desktop with two visible GNOME Terminal windows, titled `Document` and `Chat`. Each terminal writes to its own Guest file. Both actors send real mouse and keyboard operations to the same X11 desktop.

- GUI Actor's independent goal: `/tmp/swcub_document.txt` contains exactly `Approved\n`.
- Human Replay's independent goal: `/tmp/swcub_chat.txt` contains exactly `Review note\n`.
- Naive trigger: GUI observes Document, Human Replay activates Chat and enters its own note, then GUI resumes without checking or reacquiring focus. The observed negative control writes `Approved` into Chat and leaves Document empty.
- Recovery: GUI clicks the Document window before typing. The Human Replay goal remains intact.
- Hidden scoring: the existing `GuestFocusEvaluator` reads both files through the evaluator-only Guest command callback. It checks exact final contents and rejects cross-window contamination.
- Reset check: the runner reboots the same pinned Guest image into a distinct labeled container and verifies both task files are absent.

Solo validation exists for each actor. The negative control is considered validated when the evaluator rejects the joint state and the expected focus misrouting is present; `evaluation.success=false` in that case is intentional.

## Task B — GUI+CLI shared state consistency

**Task ID:** `SWCUB-STALE-MERGE-001`
**Guest surface:** one OSWorld V2.1 desktop running the local Chrome review page and its local JSON backend. The GUI page caches a whole record; the CLI actor updates that same backend through its local endpoint.

- Initial backend state: `gui_status=Draft`, `cli_note=Draft`, `revision=0`.
- GUI Actor's independent goal: set `gui_status=Approved`.
- CLI Actor's independent goal: set `cli_note=Reviewed by CLI`.
- Naive trigger: GUI loads revision 0; CLI updates `cli_note` and advances the backend revision; GUI saves its cached whole record. In the validated run, final `revision=2`, `gui_status=Approved`, and `cli_note=Draft`, so the GUI goal passes while the CLI update is lost.
- Recovery: GUI refreshes the record after the CLI update, changes only `gui_status`, and saves. Final state retains both values at revision 2.
- Hidden scoring: the existing `GuestWebStateEvaluator` reads the backend JSON through a host-held Guest command callback after actors finish. The expected fields are not exposed to actors.
- Reset check: a clean Guest reset removes `/tmp/swcub_web/state.json` and verifies a different full Guest container ID.

This task tests stale-cache overwrite and refresh/rebase behavior. The local `/replace` endpoint accepts a whole cached record rather than rejecting an old application revision; the evaluator exposes the resulting lost update. It does not claim to test a server-side compare-and-swap rejection dialog.

## Episode results

`scenario_success` means the declared condition behaved as intended, including a correctly detected negative control. It is distinct from `evaluation.success`, which must be false for an intentional failure trigger.

| Episode | Condition | Evaluator | Scenario / reset | Evidence |
|---|---|---:|---:|---|
| `focus-gui-solo` | GUI solo | pass | pass / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/focus-gui-solo/report.json>), [screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/focus-gui-solo/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/focus-gui-solo/events.jsonl>) |
| `focus-human-solo` | Human Replay solo | pass | pass / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-human-solo/report.json>), [provenance](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-human-solo/provenance.json>), [screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-human-solo/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-human-solo/events.jsonl>) |
| `focus-stale` | Naive focus-loss trigger | expected fail | detected / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-stale/report.json>), [provenance](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-stale/provenance.json>), [misrouted screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-stale/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-stale/events.jsonl>) |
| `focus-recovery` | Coordinated focus recovery | pass | pass / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-recovery/report.json>), [provenance](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-recovery/provenance.json>), [screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-recovery/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/focus-recovery/events.jsonl>) |
| `gui-cli-gui-solo` | GUI solo | pass | pass / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-gui-solo/report.json>), [screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-gui-solo/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-gui-solo/events.jsonl>) |
| `gui-cli-cli-solo` | CLI solo | pass | pass / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-cli-solo/report.json>), [screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-cli-solo/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-cli-solo/events.jsonl>) |
| `gui-cli-stale` | Naive stale-save trigger | expected fail | detected / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-stale/report.json>), [screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-stale/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-stale/events.jsonl>) |
| `gui-cli-refresh` | Coordinated refresh and merge | pass | pass / pass | [report](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-refresh/report.json>), [screenshot](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-refresh/guest-screen.png>), [event log](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2/gui-cli-refresh/events.jsonl>) |

All eight entries pass the suite validator. Every episode now has an ownership ledger with full Guest container ID, project/run/owner labels, create/destroy records, screenshots, event log, evaluator report, reset screenshot, and a provenance sidecar whose artifact digests validate. The three focus reruns use new paths; previous artifacts were preserved.

The complete machine-readable result is [`suite-validation.json`](</mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol/suite-validation.json>). It records 8/8 validated episodes, two task mechanisms, exact active actor rosters, one shared Guest per episode, screenshots, evaluator outcome, reset outcome, and verified ownership ledgers.

## Reproduction

Prerequisites are the existing pinned OSWorld V2.1 checkout, runtime image, and Guest image documented in [`ENV_SETUP.md`](ENV_SETUP.md). The runner uses no model and makes no external API call. Each command writes episode logs and screenshots to its own RAID1 directory:

```bash
SUITE_ROOT=/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2
PROTOCOL_ROOT=/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2-protocol
export SWCUB_OSWORLD_OVERLAY_HOST_DIR="$PROTOCOL_ROOT/overlays"

OSWORLD_V2_RUN_DIR="$PROTOCOL_ROOT/focus-human-solo" \
  scripts/run_osworld_v2_1_shared_csv.sh --scenario focus-human-solo
OSWORLD_V2_RUN_DIR="$PROTOCOL_ROOT/focus-stale" \
  scripts/run_osworld_v2_1_shared_csv.sh --scenario focus-stale
OSWORLD_V2_RUN_DIR="$PROTOCOL_ROOT/focus-recovery" \
  scripts/run_osworld_v2_1_shared_csv.sh --scenario focus-recovery

SWCUB_OSWORLD_RUN_DIR="$SUITE_ROOT/gui-cli-gui-solo" \
  scripts/run_osworld_v2_1_browser.sh gui-cli-gui-solo
SWCUB_OSWORLD_RUN_DIR="$SUITE_ROOT/gui-cli-cli-solo" \
  scripts/run_osworld_v2_1_browser.sh gui-cli-cli-solo
SWCUB_OSWORLD_RUN_DIR="$SUITE_ROOT/gui-cli-stale" \
  scripts/run_osworld_v2_1_browser.sh gui-cli-stale
SWCUB_OSWORLD_RUN_DIR="$SUITE_ROOT/gui-cli-refresh" \
  scripts/run_osworld_v2_1_browser.sh gui-cli-refresh

python scripts/validate_task_suite_v2.py \
  --run-root "$SUITE_ROOT" \
  --output "$PROTOCOL_ROOT/suite-validation.json"
```

These commands show the original episode output locations. All eight episode directories already exist at those paths. For a new execution, choose a fresh output directory and use a copied manifest whose `artifact_dir` points to that directory before stamping and validation. Never rerun into an existing output directory; runners preserve episode evidence and do not clean old artifacts.

## Validation summary and limits

- **Passed:** 2 task mechanisms; both actors' solo goals for each task; two real shared Guest negative controls detected by hidden-state evaluators; two coordinated recovery episodes; reset checks and provenance validation for all eight episodes; 8/8 suite validation.
- **Intentional evaluator failures:** `focus-stale` and `gui-cli-stale`. Their suite episode outcome passes because the evaluator and scenario classifier detect the specified interference.
- **Not tested:** model behavior, statistical reliability, multi-machine coordination, simultaneous sub-step concurrency, or server-side CAS conflict rejection.
- **Operational note:** OSWorld logs a missing optional `dataimpulse.json` proxy-settings warning at import time. It did not block these local-only Guest tasks; Chrome used the local loopback service.
