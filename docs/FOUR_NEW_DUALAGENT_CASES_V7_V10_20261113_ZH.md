# 四个新增 Dual-Agent case cards：V7–V10

日期：2026-11-13。目标分支：`codex/all-codesk-cases-20261113`。

四个工作流均已实现独立任务、共享 SQLite Fixture、panel-specific Oracle、GUI scripted joint positive control，并各完成一轮真实 GPT-6-Sol 三臂模型 screening。详细结果、run ID、任务分数、token/call 成本及机制限制见 [模型结果报告](../tasks/paragui/V7_V10_MODEL_RESULTS_20261113_ZH.md)。

| ID | 两个工作流 | 共用状态与干扰暴露 | 差异边界 |
|---|---|---|---|
| V7 LAB-WATER1 | A：登记三份合成水样及 custody 记录、保留 warm-sample HOLD。B：录入 bench result/calibration 并保留 QC hold。 | 共用批次 worklist/active sample；另一方切记录可能让表单目标变化。 | 实验室 intake/bench 工作流；既有 context/input-routing 机制。 |
| V8 CITY-PERMIT1 | A：审查并路由三份 right-of-way 申请。B：登记相应 fee receipt。 | 共用 permit queue/current application；两组字段兼容。 | 市政审批业务外壳；通用 current-record routing。 |
| V9 FIELD-SERVICE1 | A：按技能和时间窗安排技师。B：为同一工单预约零件。 | 共用 work-order context；review/save 间的选择可能切换。 | dispatch/parts workflow，和早期 W2 概念有相似处，不是全新机制。 |
| V10 CARE-TRANSITION1 | A：为合成出院案例登记随访诊所/日期/回电人/指示状态。B：确认居家设备及交付信息。 | 共用 discharge case list/current case；输出字段可同时保留。 | 合成 care-transition 协作；无真实患者资料/临床建议。 |

## 代码、Fixture、Oracle 和运行方式

- Fixture/config：`tasks/paragui/v456_data.json`；通用 app/builder/oracle：`build_v456.py`、`app_v456_template.py`、`pg_v456_oracle.py`。
- Case 数据/定义：`tasks/paragui/pg_v7.py` 至 `pg_v10.py`；任务类：`task_pgv7*` 至 `task_pgv10*`。
- 两 actor 的目标是分开的字段；Oracle 对各自三条记录的终态精确匹配。所有 actor-only/独立模型 controls 和四个 scripted joint Guest controls 均通过。
- Guest scripted controls：
  - V7 `cdesk3-v7-scripted-joint-20261113T112700Z-1655427`
  - V8 `cdesk3-v8-scripted-joint-20261113T113024Z-1657020`
  - V9 `cdesk3-v9-scripted-joint-20261113T113355Z-1658760`
  - V10 `cdesk3-v10-scripted-joint-20261113T113717Z-1660426`
- Model arms：`scripts/run_new_case_arm.sh v7|v8|v9|v10 ma-id|shared|shared-lock`。固定 GPT-6-Sol/Codex GUI-only、60 次 GUI call/Actor、相同任务与 budget，只更改 desktop topology/lock。
- Regression：`python -m pytest -q tests/test_v456_oracles.py tests/test_v7_v10_reference_controls.py`；四个 app setup/build 可由 `scripts/run_v456_guest_control.py v7|v8|v9|v10` 重建/正控。

## 当前结论

固定种子的一次模型三臂结果中，**四案均命中** MA-ID PASS / Shared FAIL / Shared+Lock FAIL（按每臂有至少一任务未达到满分判定）。V9 Shared+Lock 的 parts 任务只完成 2/3 并用尽 60-call 预算，必须标注预算混杂。所有结果只有一次，不是重复性/显著性证据。

四案都表现为同一 browser 应用中的 active work-area/form/record context 切换或 reset；应作为同一 shared active-context/input-routing family 的不同实用工作流，而**不是四种新机制**。Shared+Lock 只串行化每个 GUI action，没有锁定完整表单工作流。现有 window-focus telemetry 未测量浏览器应用内部 panel/tab 切换；强因果归因需后续增加语义级 context telemetry。完整分析见模型结果报告。

未按某臂结果注入障碍或调参。API/Guest runs 均有效、Oracle state 可读；overlay 对 RAID FUSE 的 chmod 警告及 artifact 路径在结果报告中如实说明。
