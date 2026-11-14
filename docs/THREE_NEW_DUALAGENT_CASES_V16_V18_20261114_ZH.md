# V16–V18：新增三个 Dual-Agent 工作流 Case

日期：2026-11-14
目标分支：`codex/all-codesk-cases-20261113`

本批新增三种合成业务工作流，并已完成脚本 Guest 双任务正控与 GPT-6-Sol MA-ID / Shared / Shared+Lock 单次筛选。三个 case 都通过一次筛选元组，但属于同一个本地合成 intranet app 的 active-panel/current-record 共享上下文家族，**不是三个新干扰机制，也没有重复 triplet 证据**。

## Case cards

| ID | Actor A | Actor B | 公用业务状态与可观察结果 | Oracle |
|---|---|---|---|---|
| **V16 LAKESIDE-COLD-CHAIN** | 对冷藏记录 `CHILL-271` 完成温度/纠正措施：5.8 C；将密封产品移入备用冷藏柜；复测 3.4 C；日志 TEMP-271。 | 对同一冷藏记录完成批次处置：HOLD、18 trays、Backup cooler B-2、FS-271。 | 餐饮食品安全场景下，同一冷藏记录的温度处理和批次隔离任务在两个活动面板间切换；共享当前面板与记录可能导致保存错面板或字段不完整。 | 对目标记录每方四项字段精确匹配，并验证已保存状态。 |
| **V17 HARBOR-MUSEUM-COLLECTION** | 对藏品 `OBJ-2306` 完成状态 STABLE、Two-person lift、Vault B-3、COND-2306 条件报告。 | 为同一藏品完成 Gallery 2 North Wall、Wall cleat、50 lux、EXH-2306 展陈放置。 | 藏品状态与展陈安排均绑定 OBJ-2306，切换 Collection Condition 与 Exhibition Placement 工作面板会改变后续输入语境。 | 对目标藏品两面板各四项字段精确匹配，且记录持久化。 |
| **V18 SUNFIELD-SOLAR-HANDOVER** | 对光伏场址 `PV-614` 填报 PASS、7.6 kW、anti-islanding PASS、COM-614 调试验收记录。 | 为同一场址完成 APPROVED、8.0 kW、Energy Operations、PTO-614 并网授权移交。 | 调试结果和并网移交同属一个场址记录；切换 PV Commissioning Test 与 Utility Authorization 面板时共享当前工作面板/记录。 | 对目标场址两面板各四项字段精确匹配，并确认保存。 |

所有数据、组织与任务记录为本地 synthetic fixture；没有真实个人信息、真实付款或真实电网控制。Case 任务是数据录入/工作流状态记录，不评判监管合规、食品安全或工程质量本身。

## 结果摘要

三案均有 MA-ID 两方 PASS、Shared 至少一方 Oracle FAIL、Shared+Lock 至少一方 Oracle FAIL；各为一次有效三臂结果。Shared+Lock 是 per-action lock，不锁完整表单事务。V16 温控记录在两个共享臂失败；V17 展陈记录在 Shared 失败、Shared+Lock 两任务失败；V18 并网记录在 Shared 失败、Shared+Lock 两任务失败。Oracle state 可读，实验没有把 Guest/API/SSH 错误计作任务 FAIL。

完整 run ID、分数、GUI 调用/Token/秒数、锁等待和实验边界见[模型结果审计](../tasks/paragui/V16_V18_MODEL_RESULTS_20261114_ZH.md)。

## Fixture、Oracle、执行入口

- 任务定义和期望值：`tasks/paragui/v456_data.json` 的 `v16`/`v17`/`v18`。
- Fixture 应用：`tasks/paragui/app_v456_template.py` + `tasks/paragui/build_v456.py`；构建产物在 RAID `/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets/v16|v17|v18`。
- Setup/状态读取：`tasks/paragui/pg_v16.py`、`pg_v17.py`、`pg_v18.py`；task modules 分别为 `task_pgv16temp.py`、`task_pgv16lot.py`、`task_pgv17condition.py`、`task_pgv17exhibit.py`、`task_pgv18commission.py`、`task_pgv18utility.py`。共用 `pg_v456_oracle.py`。
- OSWorld task IDs：V16 `pgv16temp` / `pgv16lot`；V17 `pgv17condition` / `pgv17exhibit`；V18 `pgv18commission` / `pgv18utility`。
- 每案真实 Guest 脚本双任务正控：`python scripts/run_v456_guest_control.py v16|v17|v18`。
- 三臂模型执行：`bash scripts/run_new_case_arm.sh v16|v17|v18 ma-id|shared|shared-lock`，一次传入一个版本与一个 arm。运行前核对 repo/runtime task-module 内容一致；运行数据在 RAID `runs/triplets/`，临时 overlay 在 `/dev/shm/codesk-next3/overlays/`，不纳入 Git。API key 从 stdin 注入，不写入代码、文档和结果文件。

三案拓宽到食品冷链、博物馆藏品、光伏验收/并网三个不同日常流程，但实验操作结构仍然近似：同一个实体记录、两个面板、双方各四字段。不要以此取代具有不同底层共享机制的 case，也不要将 app-panel context 证据说成 OS 窗口级焦点遥测。
