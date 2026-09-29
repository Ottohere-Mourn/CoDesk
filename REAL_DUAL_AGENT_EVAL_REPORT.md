# CoDesk Writer + Calc: Real Dual-Agent Evaluation

## Protocol and limits

Task `CODESK-TA-OFFICE-001` version `1.0.0`; OSWorld V2.1; local Qwen3-VL-30B-A3B-Instruct through the existing OSWorld Qwen3VLAgent. Each model episode uses two distinct Qwen actor objects and one local inference process. MA-ID has two Guests; MA-SD has one shared Guest. Model schedules use the same fixed Writer/Calc round-robin order. Scripted episodes are excluded.

Artifact root: `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-dual-agent-eval-20260929`. Attempts discovered: 2; all-attempt reset/provenance/artifact checks pass: `False`.

These are small task-specific observations, not a stable performance estimate.

## Results by condition

| Condition | Attempts | Valid | Env/service invalid | Writer | Calc | Joint | Reset / provenance / artifacts | Focus/window transitions | Focus conflicts | Misrouted input | Contamination | Cross-actor stale | Recovery actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| solo | 2 | 0 | 2 | n/a | n/a | 0/0 | 0/2 · 0/2 · 0/2 | 0 | 0 | 0 | 0 | 0 | 0 |
| ma_id | 0 | 0 | 0 | n/a | n/a | 0/0 | 0/0 · 0/0 · 0/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ma_sd | 0 | 0 | 0 | n/a | n/a | 0/0 | 0/0 · 0/0 · 0/0 | 0 | 0 | 0 | 0 | 0 | 0 |

### Execution metrics

Per valid episode average model-turn elapsed time (includes observation, inference, and serial action submission); action counts are GUI submissions recorded by the Guest adapter.

- **solo:** writer_actor: None GUI actions, None s; calc_actor: None GUI actions, None s
- **ma_id:** writer_actor: None GUI actions, None s; calc_actor: None GUI actions, None s
- **ma_sd:** writer_actor: None GUI actions, None s; calc_actor: None GUI actions, None s

## Validity and interpretation

2 attempts were marked environment/service/runner invalid and are excluded from model success denominators. Their IDs and reasons are retained in `REAL_DUAL_AGENT_FAILURE_CASES.md`.
A shared-desktop effect is attributed only when the episode is valid and both the event log shows input routed to the wrong active application and the final ODF evaluator shows corresponding unexpected state mutation. Goal misses without both forms of evidence remain model/task or unattributed failures. Staleness counts include only actions with another actor's commit since that actor's last observation; repeated actions within one model-issued action batch are not counted as cross-actor stale.
Recovery actions are observable focus-reacquisition actions after a focus mismatch (for example, explicit Alt+Tab or a later action that returns to the Actor's target window). This measures behavior and does not claim access to the model's internal conflict awareness.
Scripted negative controls are reported separately in the historical `REAL_APP_TRACK_A_RESULTS.md` and never mixed into this table.

## Reproduction

Run one episode at a time on a shared host; this preserves the single active model worker and limits MA-ID to two active task Guests. Example:

```bash
bash scripts/run_writer_calc_v1.sh --condition ma_id --repeat 1 \
  --run-id <unique-run-id> \
  --artifact-parent /mnt/raid1/mjh/CoDesk-V1-artifacts/real-dual-agent-eval \
  --actor-implementation qwen3vl
```
