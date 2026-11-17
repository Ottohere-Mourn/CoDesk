# V43–V47 实现与实验进展（2026-11-17）

## 状态摘要

| 验证层 | 结果 |
|---|---|
| Fixture / Web App / expected Oracle | **5/5 已生成**，位于 RAID `/mnt/raid1/mjh/Projects/codesk-v43-v47-20261117/assets/v43..v47/` |
| OSWorld task adapter | **10/10 可由 OSWorld loader 加载**，任务 ID 和指令可读 |
| 自动化测试 | `tests/test_v456_oracles.py` **63 passed**；包括离线正负控、Oracle 边界和 5 个本地 HTTP 页面/保存 roundtrip |
| Scripted Guest joint 正控 | **5/5 完成**，每题 Agent A/B 均 1.0，run IDs 列于下文 |
| GPT-6-Sol 筛查 | V43–V47 最终有效三臂均完整。V47 首次 Shared 的 Agent B runner exit-code error 保留，随后仅做一次 infra retry 并取得有效 Shared 结果。 |

## Scripted Guest 正控

每题在独立 reset 后串行启动本批 Guests，A/B 均通过 Oracle。

| Case | Run ID | A/B 分数 |
|---|---|---|
| V43 | `cdesk3-v43-scripted-joint-20261117T101342Z-4076241` | 1.0 / 1.0 |
| V44 | `cdesk3-v44-scripted-joint-20261117T101910Z-4078443` | 1.0 / 1.0 |
| V45 | `cdesk3-v45-scripted-joint-20261117T102444Z-4080659` | 1.0 / 1.0 |
| V46 | `cdesk3-v46-scripted-joint-20261117T102745Z-4082142` | 1.0 / 1.0 |
| V47 | `cdesk3-v47-scripted-joint-20261117T103044Z-4083593` | 1.0 / 1.0 |

Run outputs, screenshots, resource ledgers, and archived overlays: `/mnt/raid1/mjh/Projects/codesk-v43-v47-20261117/{runs/triplets,overlays}`. Chrome CDP startup had transient socket-hang-up retries, recovered on all runs. DockerProvider allocated dynamic ports under a lock; the external `sharp_bhabha`/QEMU was not stopped, reset, or altered.

## GPT-6-Sol model arms

All runs used Codex CLI 0.165.0, `gpt-6-sol (high)`, GUI-only desktop MCP and 60-call budget. Scores below are A/B. Input token volumes are sizeable; each run was serialized and preserved.

| Case / arm | Run ID | A/B | duration | input / output tokens | Assessment |
|---|---|---:|---:|---:|---|
| V43 MA-ID (original wording) | `cdesk3-v43-ma-id-20261117T103512Z-4085625` | `0/1` | 858.6s | 465,317 / 1,086 | A entered `3`, source stated `Detail 3`; original prompt only said “detail”, so wording ambiguity. Preserved, excluded from corrected-prompt criterion. |
| V43 MA-ID (clarified) | `cdesk3-v43-ma-id-20261117T105312Z-4093865` | `1/1` | 500.8s | 482,135 / 1,178 | Valid isolated double-pass after explicitly requiring exact `Detail` prefix. |
| V43 Shared | `cdesk3-v43-shared-20261117T110147Z-4101145` | `1/0` | 930.5s | 1,731,255 / 5,145 | B role fails in shared. |
| V43 Shared+Lock | `cdesk3-v43-shared-lock-20261117T111730Z-4107412` | `1/0` | 1,004.3s | 1,540,592 / 5,050 | Same B role still fails. **Role-consistent PASS/FAIL/FAIL hit.** |
| V44 MA-ID | `cdesk3-v44-ma-id-20261117T113429Z-4113827` | `1/1` | 397.7s | 427,517 / 1,353 | Valid isolated double-pass. |
| V44 Shared | `cdesk3-v44-shared-20261117T114122Z-4117860` | `0/1` | 804.8s | 1,195,518 / 4,276 | A role fails. |
| V44 Shared+Lock | `cdesk3-v44-shared-lock-20261117T115503Z-4123122` | `1/0` | 612.3s | 1,458,352 / 5,036 | B fails instead. Pair outcome fails in both arms, but no single role is FAIL in both; do **not** count as role-consistent PASS/FAIL/FAIL. |
| V45 MA-ID | `cdesk3-v45-ma-id-20261117T120530Z-4128582` | `1/1` | 700.4s | 529,423 / 1,325 | Valid isolated double-pass. |
| V45 Shared | `cdesk3-v45-shared-20261117T121723Z-4133817` | `1/0` | 965.2s | 1,793,310 / 6,884 | B role fails in shared. |
| V45 Shared+Lock | `cdesk3-v45-shared-lock-20261117T123342Z-4139357` | `0/0` | 579.9s | 1,059,127 / 5,947 | Both roles fail; B also fails in preceding Shared. **Role-consistent PASS/FAIL/FAIL hit.** |
| V46 MA-ID | `cdesk3-v46-ma-id-20261117T124341Z-4143377` | `1/1` | 761.6s | 505,380 / 1,300 | Valid isolated double-pass. |
| V46 Shared | `cdesk3-v46-shared-20261117T125634Z-4148602` | `1/0` | 985.7s | 2,052,304 / 4,721 | B role fails in shared. |
| V46 Shared+Lock | `cdesk3-v46-shared-lock-20261117T131314Z-4155252` | `0/1` | 1821.8s | 1,922,863 / 4,149 | Final result valid after transient upstream reconnects; A failed, B passed. Together with Shared `1/0`, there is a pair-level failure under both arms but not a same-role FAIL/FAIL path. |
| V47 MA-ID | `cdesk3-v47-ma-id-20261117T134352Z-4164499` | `1/1` | 990.1s | 426,639 / 1,229 | Valid isolated double-pass. |
| V47 Shared (first attempt, infra-invalid) | `cdesk3-v47-shared-20261117T140036Z-4171518` | A=`0`; B=`error` | 499.4s | 230,478 / 584 | Agent B exited code 1 before model usage; preserved, not counted as FAIL and not substituted/deleted. A has an Oracle failure but the two-agent arm is incomplete. |
| V47 Shared (single infra retry) | `cdesk3-v47-shared-20261117T140913Z-4175003` | `0/1` | 1934.3s | 1,606,456 / 3,546 | Both actors ended normally; A fails, B passes. Use this as the valid Shared arm, retain the earlier invalid run. |
| V47 Shared+Lock | `cdesk3-v47-shared-lock-20261117T144141Z-4183912` | `0/0` | 611.9s | 955,076 / 2,614 | Both roles fail; A also failed in preceding valid Shared. **Role-consistent PASS/FAIL/FAIL hit.** |

### Interpretation

- V43, V45 and V47 meet the strict **same-role** isolated PASS → Shared FAIL → Shared+Lock FAIL criterion once each, without repeat trials.
- V44 and V46 meet only **pair-level** semantics: the combined pair is unsuccessful in both shared conditions, but a different role fails under Shared versus Lock. Do not describe these two as same-role persistent mechanism hits.
- Overall, **5/5** have valid MA-ID double pass and pair-level Shared FAIL / Shared+Lock FAIL; **3/5** have same-role persistent FAIL under both shared arms.
- These five remain variants in one Synthetic Desk active-panel/current-record mechanism family, not five independent concurrency mechanisms.

## Environment and runner notes

At preflight root had about 28 GB free (99% used), RAID about 884 GB free (95% used), `/dev/shm` about 13 GB free, 80 CPUs, load ~5–6 and swap full. Fixtures/runs/overlays reside on RAID; avoid cleaning existing evidence. Guests were serialized. The original note suggesting fixed default ports prevented Guest boot was wrong: installed OSWorld DockerProvider dynamically scans and assigns free ports under `/tmp/docker_port_allocation.lck`.

## Completion / audit status

All five cases have valid MA-ID, Shared and Shared+Lock outcomes under the clarified, unchanged prompt/Oracle (except the explicitly clarified V43 drawing-detail wording); V47 has one retained Shared infra-invalid attempt followed by a single valid retry. The sequence had no repeated effective trials. Preserve every run. Do not claim five distinct mechanisms: these are five industry/task variants of the Synthetic Desk active-panel/current-record competition.
