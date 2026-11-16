# V34–V37 GPT-6-Sol 三臂 Pilot：结果与有效性审计

日期：2026-11-16
分支：`codex/all-codesk-cases-20261113`
模型：GPT-6-Sol/high；Codex CLI 0.165.0
协议：MA-ID 两个独立 Guest；Shared 单 Guest；Shared+Lock 单 Guest、每次 GUI 调用互斥。统一每 Actor 60 GUI calls 与 2400s timeout。每 case 一次模型 triplet；另有 scripted 两任务联合正控。完整原始结果保存在 HealthCare RAID：`/mnt/raid1/mjh/Projects/codesk-next5-20261115/runs/triplets`。

## 结论摘要

- 4 个新业务工作流均通过 scripted joint positive control（A/B 2/2）。
- **严格任务级 tuple 只观察到 V37 的 Actor B/restoration-validation：MA-ID PASS、Shared FAIL、Shared+Lock FAIL；这是一次性 pilot 观察，不是复现。**
- 其他 3 个均未达标：V34 Shared 两项都 PASS；V35 Actor A 独立即失败、Actor B 全通过；V36 Shared Actor A 失败但 Shared+Lock 恢复，两项 lock 都 PASS，且 Shared Actor B hit max_steps。
- 所以 **1/4 有同任务级三臂 tuple；0/4 有完整的双任务都满足三臂目标且两 Actor 均有效结束**。不要把 timeout/max_steps 算成期望机制失败。
- 本批仍是 Synthetic Desk 的同一 app-level active-panel/current-record 机制族，不能表述为四种独立桌面干扰机制。

## Case 结果

| Case | Scripted joint positive control | MA-ID (A/B) | Shared (A/B) | Shared+Lock (A/B) | 判定 |
|---|---:|---:|---:|---:|---|
| V34 Water quality | PASS 2/2 | 1 / 1 | 1 / 1 | 0 / 0 | Shared 未失败，无 tuple |
| V35 Aid appeal | PASS 2/2 | 0 / 1 | 0 / 1 | 0 / 1 | A 无模型独立正控；B 全 PASS |
| V36 Election equipment | PASS 2/2 | 1 / 1 | 0 / 1* | 1 / 1 | 锁臂恢复；不达标 |
| V37 Telecom restoration | PASS 2/2 | 1 / 1 | 1 / 0 | timeout / 0 | B 任务级 tuple；A timeout 排除 |

`*` V36 Shared B 的 result score 是 1，但 `status=max_steps`，用完 60 GUI calls；因此不是有效通过/失败证据，只记作预算触顶。V37 Shared+Lock A 的 JSON 中 Oracle score 0，但 Actor timeout，不能将该 0 当作机制 FAIL；只认已完成的 Actor B 任务级结果。

### 运行 IDs

| Case | MA-ID | Shared | Shared+Lock |
|---|---|---|---|
| V34 | `cdesk3-v34-ma-id-20261116T113726Z-3490778` | `cdesk3-v34-shared-20261116T114831Z-3497698` | `cdesk3-v34-shared-lock-20261116T120907Z-3508865` |
| V35 | `cdesk3-v35-ma-id-20261116T122559Z-3515968` | `cdesk3-v35-shared-20261116T123245Z-3519951` | `cdesk3-v35-shared-lock-20261116T124727Z-3525865` |
| V36 | `cdesk3-v36-ma-id-20261116T130401Z-3533563` | `cdesk3-v36-shared-20261116T130939Z-3537101` | `cdesk3-v36-shared-lock-20261116T133318Z-3545315` |
| V37 | `cdesk3-v37-ma-id-20261116T141039Z-3563508` | `cdesk3-v37-shared-20261116T142554Z-3571727` | `cdesk3-v37-shared-lock-20261116T150117Z-3587438` |

### Scripted Guest 正控 Run IDs

| Case | Run ID | 结果 |
|---|---|---|
| V34 | `cdesk3-v34-scripted-joint-20261116T112454Z-3483664` | 两任务 PASS (2/2) |
| V35 | `cdesk3-v35-scripted-joint-20261116T112756Z-3485453` | 两任务 PASS (2/2) |
| V36 | `cdesk3-v36-scripted-joint-20261116T113056Z-3487080` | 两任务 PASS (2/2) |
| V37 | `cdesk3-v37-scripted-joint-20261116T113351Z-3488812` | 两任务 PASS (2/2) |

### 成本 / 调用

各格依次为 `Agent A (GUI calls / active seconds), Agent B (GUI calls / active seconds)`。秒数是 Actor 的 Harness 活跃时长，不等于整臂 wall time；并行 Actor 时不能简单相加当墙钟耗时。

| Case | MA-ID | Shared | Shared+Lock |
|---|---|---|---|
| V34 | 17/322s, 18/300s | 27/622s, 38/1054s | 38/728s, 40/838s |
| V35 | 13/138s, 16/206s | 29/382s, 42/702s | 41/830s, 31/482s |
| V36 | 13/120s, 14/138s | 35/624s, 60/1266s* | 41/2074s, 42/922s |
| V37 | 14/184s, 16/694s | 28/1960s, 26/652s | 46/2400s timeout, 59/1434s |

12 个模型 arms 共调用 744 次 GUI 工具（不含 scripted controls）；按 result JSON 的 `total_s` 汇总约 4.05 小时顺序运行时间。V37 Shared+Lock A 在 2400s 上限被终止；V36 Shared B 用尽 60 calls。Token usage 存在于每个 `result.json`；V37 lock Agent A 的 usage unavailable，不能把该臂 token 统计成 0 成本。

## 干扰证据和边界

- MA-ID / Shared / Shared+Lock 全部 `actions.jsonl` 合计未记录 `focus_switch_action=true` 或 `misrouted_focus_before=true`。因此本批**没有 OS 窗口焦点误路由的直接遥测证据**。
- V34、V35、V36、V37 的动作级锁等待/持有累计分别为 11.824/171.686s、3.305/129.867s、8.226/166.479s、10.810/242.219s；整批约等待 34.165s、锁持有 710.251s。锁是单个 GUI 调用期间的互斥，不会把某个 Actor 的“选中面板—连续多次填写—保存”变成事务，故不能据此推断其消除了面板状态竞态。
- V37 Shared 的 Actor B Oracle 失败且已完成 run；其日志/agent 最终文本报告在恢复验证中，桌面活动面板反复跳到 incident review，未保存输入被清空。Shared+Lock B 最终表示记录仍未保存，结果亦为 Oracle 0。可支持“逐调用锁没有解决该任务”的单次观察，不代表锁机制普遍无效。
- V37 锁臂 A 在 2400s timeout，且 agent stdout 有长时间上游重连；只作为 infra/预算无效，不纳入错误机制判定。B 锁臂已正常结束、59/60 calls、Oracle 0。
- V35 A 在 MA-ID 独立臂也拿到 0，说明此任务/模型基线不成立，不能因 Shared 与 lock 都是 0 就宣称共享导致失败。
- V36 Shared A 有有效 0，lock A 得 1，呈现锁下恢复而不是目标 tuple；B Shared 触顶，不能计负例。
- V34 Shared A/B 都得 1，表明该工作流在此一次模型运行中没有引出 Shared 业务失败。

## Fixtures / 复现 / 验证

每个 case 的三臂 `fixture.sha256` 一致：
- V34 `app_v34.py` 534cb940…；case `case.json` 7f1681a7…；expected 43ad983d…；seed `a4956872…`
- V35 `app_v35.py` e91c6ee3…；case c4c39ae6…；expected 14966dca…；seed 7cc073d3…
- V36 `app_v36.py` b28ce5e3…；case 0b32b175…；expected 08dc3048…；seed 6b58ec6f…
- V37 `app_v37.py` 265e7016…；case 4befb6d6…；expected ec1cb1ad…；seed 82b61638…

V34/V35 运行期间的 Guest 资源在三臂间一致。为减轻 `/dev/shm` 压力，V36 Shared+Lock 和 V37 三臂把临时 overlay 改为 RAID 路径；该 runner 路径更改会改变这些 run 的 `source.sha256`，但**不改变 case/prompt/task module/fixture/模型配置或 lock 语义**。环境当时约根盘剩余 31–32GB (99%)、RAID 剩余约 906GB、`/dev/shm` 剩余约 13GB，因此没有清理或覆盖已有实验数据。

重新运行命令和 Case/Oracle 说明见 [四个 Case 卡](../../docs/FOUR_NEW_DUALAGENT_CASES_V34_V37_20261116_ZH.md)。在 repo 根执行 `bash scripts/run_new_case_arm.sh v34 ma-id|shared|shared-lock`（一次一个 arm；逐次单独调用），其他 case 替换 ID。Harness 会校验任务模块是否与 OSWorld runtime 同步；需要通过安全的隐藏输入/credential 环境提供 API key，不能提交到 Git。
