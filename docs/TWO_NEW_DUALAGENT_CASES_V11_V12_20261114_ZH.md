# V11–V12：两个新增 Dual-Agent 工作流 Case

日期：2026-11-14。目标分支：`codex/all-codesk-cases-20261113`。

这两个新增 case 均完成：task/fixture/oracle、真实 Guest scripted joint positive control，以及 GPT-6-Sol Codex GUI-only 的 MA-ID / Shared / Shared+Lock 三臂 pilot。两案各有一次有效的目标 tuple；这是一次性 screening，不是重复性或统计显著性证据。逐臂 run ID、分数、状态、调用量与 Token 见[模型结果报告](../tasks/paragui/V11_V12_MODEL_RESULTS_20261114_ZH.md)。

## 候选卡

| ID | 独立 Actor 任务 | 共用状态和干扰路径 | 用途与新颖性边界 |
|---|---|---|---|
| **V11 LIBRARY-CIRCULATION1** | A：为 COPY-1102 / 2088 / 3194 准备 pending hold：状态、取书分馆、到期日、通知编号。B：处理这三本已归还图书：品相、去向、精确书架位置、回执编号。 | 同一图书记录、worklist 和浏览器 app 的当前 panel/record；A 与 B 需要在 Hold fulfillment / Return processing 两个 panel 间切换。两组业务字段不互相覆盖，但活动工作区是共享的。 | 日常图书馆流通与归还工作流。复用既有 active-panel/current-record/input-routing 干扰族，不宣称是新底层机制。 |
| **V12 CIVIC-RECORDS1** | A：严格依照合成审阅说明，为 PR-508-A / 512-B / 519-C 填 release action、redacted pages、basis 和 review ref。B：依据 intake slip 填 source office、收件日期、文档类型及 custody ref。 | 同一批三个合成文档及当前 panel/record；A 和 B 分别操作 Disclosure review / Intake & custody。动作间切换可令另一方打开的业务表单失效。 | 公共记录文档审核和入库登记。明确只执行任务卡中的合成说明，不做任何法律推断；没有真实个人或法律案件数据。与 V11 业务域不同，但底层仍是共享 app context。 |

## Fixture、Oracle 与复现

- 数据、字段定义和逐条预期值：`tasks/paragui/v456_data.json` 的 `v11` / `v12` 条目。
- app、DB seed 和 expected 文件构建器：`tasks/paragui/app_v456_template.py`、`tasks/paragui/build_v456.py`。两案端口分别为 8146 / 8147；正控生成的本地 Fixture 位于 HealthCare RAID 的 `assets/v11`、`assets/v12`，不把体积较大的运行资产加入 Git。
- setup / evaluator：`tasks/paragui/pg_v11.py`、`pg_v12.py`、`pg_v456_oracle.py`；OSWorld task ID：`pgv11holds`、`pgv11returns`、`pgv12review`、`pgv12intake`。
- 正控：`python scripts/run_v456_guest_control.py v11` 和 `... v12`；它们在实际 Guest 中对双方任务做 scripted joint completion，并各自 Oracle 评分 1.0。
  - V11：`cdesk3-v11-scripted-joint-20261113T165032Z-1779822`
  - V12：`cdesk3-v12-scripted-joint-20261113T165334Z-1781308`
- GPT-6-Sol 三臂入口：`bash scripts/run_new_case_arm.sh v11|v12 ma-id|shared|shared-lock`。需使用现有 HealthCare OSWorld/Guest/Codex CLI 环境；密钥只能由受控运行时通过 stdin 注入，不能写进源文件、命令行参数或 artifacts。各臂固定 Codex CLI 0.165.0、GPT-6-Sol、每 Actor 最多 60 次 GUI 调用、同任务与 Fixture，仅改变独立/共享桌面及每动作锁。Shared+Lock 是每个 GUI action 的互斥锁，不是全任务/全表单事务锁。
- 结果和完整事件、截图保存在 HealthCare RAID：`/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/`；复现路径、组件依赖和设备要求沿用前述 runner。API key 不进入 Git。

## 结果解读

- 两案 MA-ID 中 A、B 均满分。
- V11 Shared 与 Shared+Lock 都是两 Actor 不满分；V12 两种 Shared arm 中 Intake Actor 不满分，Review Actor 满分。按 portfolio handoff 的严格筛选规则“每个实验臂至少有一个 task score < 1.0”，两案均命中一次性 tuple。
- V12 Shared+Lock 中 Review Actor 虽拿到 1.0，但消耗完 60 次 GUI-call 上限，runner 状态为 `max_steps`；Intake Actor 因应用在输入间被切回另一 panel 而失败。故记录为**有效 lock-arm 任务失败，但含 Review Actor 的预算触顶/停止方式 caveat**，不可把 A 的 max_steps 伪装成任务失败，也不要忽略 B 的机制性失败。
- 两案都是同一类浏览器 app 的合成界面，用来筛查 workflow task 是否暴露共享桌面上下文干扰；不能据此主张真实图书馆/市政系统的生态有效性，也不是新增两种独立机制。
- 不挑选性删除失败的尝试：V11 有一次 Shared SSH 会话断连且无最终 `result.json`；V12 首次 Shared+Lock 遇 API SSE/transport 错误并人工中止。两者在结果报告中列为无效并保留原 artifacts，最终 tuple 用各自一次有效 triplet。
