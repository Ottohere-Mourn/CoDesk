# CoDesk：3个新双 Agent Case 设计卡

更新：2026-11-12。目标是在统一 Codex GUI Harness 下验证 **MA-ID PASS / Shared FAIL / Shared+Lock FAIL**。截至本次真实模型首轮，S1 与 K2 各有一组三臂结果符合目标；K1 三臂均 PASS，不符合目标。详见文末的真实实验补记。

## 统一协议
- MA-ID：两个 Agent 在并发运行的独立 Guest 中执行；各自从相同 pair fixture/reset 开始。
- Shared：两 Agent 共用同一 Guest、浏览器会话及业务数据库。
- Shared+Lock：同 Shared，加每次修改型 GUI MCP 调用期间的 per-action lock；不锁思考过程，也不提供跨多个 GUI 操作的事务。
- 三臂固定 Codex GUI Harness、GPT-6-Sol、任务对、fixture、GUI MCP-only 权限、预算与 reset；无 Guest CLI、宿主 Shell 或协作消息 MCP。
- 仅有效运行参与判定。API/Guest/reset/evaluator 错误均为 invalid，不得算共享失败；不添加 arm-specific 障碍或人为 barrier，不筛选有利尝试。

## S1 — SHELTER-INTAKE1：家庭安置与安全封房
**工作流：** 晚班收容所为新到家庭安排房间，同时处理安全检查发现的危险。
- Agent A（Intake）：查看四张家庭卡与房间清单，为每户安排草稿；家庭不得拆分、不得超容量；轮椅用户需无障碍房间，训练中的伴侣动物只能进入允许动物的房间；写安置备注。
- Agent B（Facilities）：按 SAFE-204 检查的西侧插座焦糊味关闭 CR-201，容量置零，建立高优先级维修工单。
- 共享状态：房间可用状态/容量。H-103 为四人家庭；CR-201 是唯一容量至少为四人的房间。封房会使共享 DB 中已有或正在制作的 placement 失效。
- Oracle 分别检查四户唯一安置、人数、当前容量、无障碍/动物条件、草稿和备注，以及精确的封房/工单字段。
- MA-ID 两边各自拥有完整初始房间资源，可单独完成。冲突来自安全封房与容量约束，不是某一臂专属 GUI 陷阱。
- 边界：本地可复现的收容所运营台，不外推真实 SaaS 的事务语义。

## K1 — COURT-SERVICE1：法庭立案材料与送达回证
**工作流：** 书记员同时整理新案件立案材料并归档另一案件的送达证明。
- Agent A：为 SC-208 填原被告、金额、指定附件，置为 Ready for clerk check。
- Agent B：为 SC-193 填送达日期、送达方式、送达员 ID 与结果。
- 共享状态：合成旧式 Clerk Desk 使用全局 active-docket；提交记录受当前活动案件上下文影响。
- Oracle 依据显式 docket ID 精确检查全部字段，不能只凭表单已保存判 PASS。
- MA-ID 两个 Guest 有各自独立案件选择器。Shared 中可能出现错案保存，且动作锁不覆盖多步骤填表流程。
- 边界/重合：与 Case 3/A-01 的活动记录上下文机制近邻；新增的是立案+送达两个书记员日常流程，不宣称新底层机制。UI 是本地旧式桌面模拟，不代表现代多标签法院产品。

## K2 — ROUTE-RECON1：早班派车路线与客户改期
**工作流：** 调度员按已发布的早班 manifest 编制路线，客服同时处理客户改期。
- Agent A：基于 08:00 冻结 manifest，为 RTE-17 设定四站顺序、Van 4、发车时间、日期及 Draft 状态。
- Agent B：处理客户通话，将 WO-503 改为 Deferred、改排到 2026-11-14 并保存客户原话。
- 共享状态：路线草稿、工单状态/日期同在 dispatch board。WO-503 改期后，仍包含该停靠点的路线会变陈旧；逐次 GUI 锁不提供跨工作流版本事务。
- Oracle 分别检查路线字段/顺序与工单更新；Shared 若路线仍含已改期工单则 Agent A 不通过。模型若能及时恢复则保留为 PASS，不强行判败。
- MA-ID 两 Guest 各从相同工单与 manifest 开始，可各自完成任务。
- 边界/重合：与 PAY-1/DATA-REL1 的 stale-artifact 机制近邻；宏观流程为现场派车与客服改期，不宣称全新底层机制。本地调度板不能外推生产调度系统。

## 设计审计与通过门槛
三案主题分别为收容安置、法庭书记业务、现场派车，区别于同一表单换 ID；但都是本地合成应用，真实模型三臂仍是关键验证。仅当一组三臂有效结果同时满足：MA-ID 两边 Oracle 均为 1.0；Shared 至少一侧低于 1.0；Shared+Lock 至少一侧低于 1.0；且两失败臂有可归因的共享状态/GUI证据，才报告首轮满足目标。初始设计阶段为 0/3；截至下方真实模型实验补记为 **2/3 首轮符合**（S1、K2；K1 不符合）。


## 2026-11-12 GPT-6-Sol 真实模型首轮结果（权威更新）

新端点 `/v1` 通过 GPT-6-Sol 模型列表及最小 Responses 调用预检。九个有效模型臂均使用 GPT-6-Sol、Codex CLI 0.165.0、high effort、GUI-only、每 Agent 45 次 GUI MCP 调用上限；无 Qwen。API key 仅在运行时注入，未写入仓库。真实结果不受此前旧 key 额度错误影响。

成功标准：MA-ID 两个 oracle 均 1.0；Shared 和 Shared+Lock 各至少一个 oracle <1.0；失败必须可由业务状态/GUI 轨迹解释。有效结果如下：

| Case | Arm | Agent A/B score | GUI calls A/B | input tokens (cached) | output tokens | elapsed s |
|---|---|---:|---:|---:|---:|---:|
| S1 | MA-ID | 1.0 / 1.0 | 18 / 6 | 654,974 (553,333) | 2,542 | 486.7 |
| S1 | Shared | 0.5 / 1.0 | 22 / 23 | 1,299,037 (1,118,630) | 5,888 | 581.4 |
| S1 | Shared+Lock | 0.5 / 1.0 | 11 / 10 | 524,783 (432,806) | 3,462 | 319.6 |
| K1 | MA-ID | 1.0 / 1.0 | 14 / 12 | 689,115 (570,683) | 2,178 | 406.3 |
| K1 | Shared | 1.0 / 1.0 | 40 / 31 | 2,835,504 (2,542,614) | 8,451 | 967.2 |
| K1 | Shared+Lock | 1.0 / 1.0 | 23 / 29 | 1,770,415 (1,550,061) | 4,838 | 787.4 |
| K2 | MA-ID | 1.0 / 1.0 | 19 / 12 | 865,015 (746,972) | 2,639 | 455.7 |
| K2 | Shared | 0.1429 / 0.25 | 42 / 45 | 2,617,483 (2,328,166) | 9,729 | 749.7 |
| K2 | Shared+Lock | 0.8571 / 1.0 | 23 / 29 | 1,699,210 (1,513,460) | 4,768 | 738.0 |

- **S1 SHELTER-INTAKE1：首轮符合。** MA-ID 完整通过。两共享臂中 Facilities Agent 正确封闭唯一足以容纳 H-103 的 CR-201 并创建工单；Intake 未能满足 household assignment oracle（0.5 为部分硬约束分，不是 infra invalid）。共享焦点/页面切换轨迹及可行容量被耗尽，构成业务性失败证据。Shared+Lock 只串行单次 GUI mutation，不会创造额外床位。
- **K1 COURT-SERVICE1：no-go。** 三臂双方全 PASS。Shared 臂有较高 GUI 调用数和耗时，但成本增加不是任务失败；不能声称达标。其 active-docket 设计也与 Case 3/A-01 上下文机制近邻，不建议简单调参继续救。
- **K2 ROUTE-RECON1：首轮符合。** MA-ID 完整通过。Shared 中共享 GUI 焦点在路线草稿与 WO-503 客户改期页间反复变化，两边均部分失败。Shared+Lock 中客服任务全通过，但路线仍包含已 Deferred 的 WO-503，故路线 oracle 0.8571；锁没有跨工作流版本事务。
- 九个有效 arm 均 `error=null`，没有将 infrastructure-invalid 计作 FAIL。累计约 12,955,536 input tokens（11,356,725 cached）、44,495 output tokens，elapsed 总和约 5,492 秒（91.5 分钟）。run IDs 与逐次完整日志位于相应 RAID run directories，见 handoff。
- 初始准备阶段的 Guest timeout、NTFS Codex HOME、旧 key 额度错误仍作为 infra-invalid 历史保留，不能与上述有效结果混算。

结论：本批目标目前 **2/3 首轮通过**（S1、K2），无第二次重复；K1 应替换为机制更不同的工作流，而不是把 1.0/1.0 改判失败。
