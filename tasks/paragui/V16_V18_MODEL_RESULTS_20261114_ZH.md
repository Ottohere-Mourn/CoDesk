# V16–V18 Dual-Agent 模型三臂结果审计

日期：2026-11-14
分支：`codex/all-codesk-cases-20261113`
模型/运行时：GPT-6-Sol；Codex CLI 0.165.0；OSWorld V2；每位 Actor 最多 60 次 GUI MCP 调用；单臂运行超时 2400 秒。

## 判定口径与结论

一次性筛选目标为：**MA-ID 两任务 PASS；Shared 至少一任务 FAIL；Shared+Lock 至少一任务 FAIL**。三个修订版 case 均有真实 Guest scripted joint positive control（两任务 PASS），且各完成一组 MA-ID / Shared / Shared+Lock triplet。九个模型 run 均 `error: null`、Oracle state 可读；失败均是 Oracle 对已保存业务字段的有效 0 分，不是 Guest、API 或 SSH 基础设施错误。三案都满足一次性 score tuple，**不代表重复性或失败率证据**。

| Case / arm | run ID | A/B Oracle 分数 | GUI calls A/B | input / output tokens | Agent 秒 A/B | run wall 秒 |
|---|---|---:|---:|---:|---:|---:|
| V16 MA-ID | `cdesk3-v16-ma-id-20261114T102857Z-2242213` | 1 / 1 | 11 / 16 | 486,745 / 1,188 | 142.0 / 182.0 | 365.6 |
| V16 Shared | `cdesk3-v16-shared-20261114T103534Z-2246231` | 0 / 1 | 14 / 32 | 1,167,154 / 3,528 | 226.0 / 532.1 | 686.1 |
| V16 Shared+Lock | `cdesk3-v16-shared-lock-20261114T104734Z-2251505` | 0 / 1 | 12 / 21 | 668,927 / 1,980 | 130.1 / 250.1 | 402.4 |
| V17 MA-ID | `cdesk3-v17-ma-id-20261114T105440Z-2254973` | 1 / 1 | 13 / 15 | 505,674 / 1,119 | 144.1 / 176.1 | 358.3 |
| V17 Shared | `cdesk3-v17-shared-20261114T110108Z-2259855` | 1 / 0 | 36 / 30 | 1,947,313 / 6,000 | 524.1 / 390.0 | 673.6 |
| V17 Shared+Lock | `cdesk3-v17-shared-lock-20261114T111244Z-2264503` | 0 / 0 | 26 / 45 | 2,277,495 / 4,723 | 330.0 / 686.1 | 837.0 |
| V18 MA-ID | `cdesk3-v18-ma-id-20261114T112705Z-2270105` | 1 / 1 | 10 / 15 | 435,597 / 896 | 144.1 / 284.1 | 464.4 |
| V18 Shared | `cdesk3-v18-shared-20261114T113518Z-2275953` | 1 / 0 | 44 / 34 | 2,573,783 / 5,515 | 634.1 / 464.1 | 813.8 |
| V18 Shared+Lock | `cdesk3-v18-shared-lock-20261114T114926Z-2282107` | 0 / 0 | 36 / 50 | 3,108,365 / 7,721 | 682.1 / 1,110.2 | 1,259.6 |

Tokens are provider-reported totals; tool calls count GUI MCP operations. `Agent 秒` is per-actor active runtime and can overlap; `run wall 秒` is triplet run duration. MA-ID arms use isolated Guests; Shared uses the shared Guest without an action lock; Shared+Lock serializes each GUI action, **not the multi-action form transaction**.

## Guest scripted positive controls

三次控制均在真实 OSWorld Guest 执行，A 与 B 的精确字段 Oracle 均为 1/1。它们校验 fixture/task/oracle 和独立脚本化填表通路，不替代模型结果：

- V16：`cdesk3-v16-scripted-joint-20261114T101727Z-2236368`
- V17：`cdesk3-v17-scripted-joint-20261114T102159Z-2238772`
- V18：`cdesk3-v18-scripted-joint-20261114T102445Z-2240215`

## 每案结果与可观察证据

- **V16 Cold-Chain Incident / CHILL-271**：MA-ID 两方全字段保存。Shared 与 Shared+Lock 中，温控任务 A（pgv16temp）均 0/1、批次隔离任务 B（pgv16lot）均 1/1。对应 SQLite state 可读，0 分任务的目标记录存在，但目标字段未精确匹配。两个共享臂各有一有效失败。
- **V17 Museum Collection / OBJ-2306**：MA-ID 两方全字段保存。Shared 中条件报告 A 为 1/1，展陈放置 B 为 0/1；B 最终说明工作台在展陈与条件报告间反复切换，无法可靠确认并保存正确表单。Shared+Lock 中两方均为 0/1；B 报告字段在录入前不断重置。锁只串行化单次 GUI 动作，不能保证“切面板—填多字段—保存”的事务不中断。
- **V18 Solar Commissioning / PV-614**：MA-ID 两方全字段保存。Shared 中调试验收 A 为 1/1、并网移交 B 为 0/1；Shared+Lock 两方均为 0/1。失败记录的 Guest state 均可读、PV-614 精确匹配，但 Oracle 检查的表单数据不满足目标值。模型两臂均正常退出，未返回基础设施异常。

以上失败是**同一合成应用内共享活动面板/当前记录造成的任务结果损害**。没有独立 OS window-focus telemetry；不能据此宣称已直接测出跨 OS 窗口键鼠误路由，也不能说三案发现了三种新机制。

## Action-lock 等待统计

来自每臂 `locks/agent-action-lock-events.jsonl`；是锁请求事件数，不等同全部 GUI 调用：

| Case | 锁请求数 | 等待总计 (秒) | 平均等待 (秒) | 最大单次等待 (秒) | 临界区持有总计 (秒) |
|---|---:|---:|---:|---:|---:|
| V16 Shared+Lock | 28 | 2.720 | 0.097 | 2.682 | 66.888 |
| V17 Shared+Lock | 65 | 11.471 | 0.176 | 2.903 | 159.513 |
| V18 Shared+Lock | 80 | 15.116 | 0.189 | 2.474 | 189.640 |

锁等待不高不代表没有干扰：每次 click/type/key 虽被序列化，任一 Actor 仍可在另一 Actor 的两个动作之间切换 app 工作面板并改变后续输入语境。Shared+Lock 不是事务级隔离。

## Fixture、Oracle、复现

- 任务配置、值、Fixture 预期：`tasks/paragui/v456_data.json` 的 `v16`、`v17`、`v18`。
- UI/SQLite 资产生成：`tasks/paragui/app_v456_template.py` 与 `tasks/paragui/build_v456.py`；RAID 构建资产：`/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets/v16|v17|v18`。
- Task setup/Oracle：`tasks/paragui/pg_v16.py`–`pg_v18.py`、六个 `task_pgv16*.py` / `task_pgv17*.py` / `task_pgv18*.py`；共用精确 Oracle `pg_v456_oracle.py`。
- OSWorld task IDs：V16 `pgv16temp` / `pgv16lot`；V17 `pgv17condition` / `pgv17exhibit`；V18 `pgv18commission` / `pgv18utility`。
- 脚本正控：`python scripts/run_v456_guest_control.py v16|v17|v18`。
- 模型臂：`bash scripts/run_new_case_arm.sh v16|v17|v18 ma-id|shared|shared-lock`（每次传一个 case ID 和一个 arm）。脚本校验 repo 与 OSWorld runtime task-module 内容一致；模型 key 从 stdin 读取，不进源码。
- Raw traces / screenshots / result.json 在 RAID：`/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/<run-id>/`；临时 overlay 在 `/dev/shm/codesk-next3/overlays/`，脚本会尝试复制至 RAID overlays。

## 告警与解释边界

九个模型臂均产生完整 `result.json`，run 顶层 error 为 null。Guest Chrome CDP 启动时有初始 socket-hang-up 重试，随后重试打开正确 app；未因此判为无效。每次结束的 tmpfs overlay 归档可能打印 RAID `cp` chmod “Operation not permitted” 并提示 archive 未完整；**不要清理或覆盖这些目录**。这不影响 RAID 上完整的 run metadata、Oracle 检查、动作与模型日志，也未作为任务 FAIL 的依据。

本批增加三个经一次筛选命中的合成工作流案例，而非重复性实验或独立机制复现。保留原始失败、锁轨迹与 run ID；告警不改写模型分数。
