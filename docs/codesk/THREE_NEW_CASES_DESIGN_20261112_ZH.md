# CoDesk：3个新双 Agent Case 设计卡

审计后仅 K2 保留为一次符合目标的候选（1/3）；S1 因任务目标互斥且实际加载了过期 Oracle 而不合格，K1 三臂均 PASS、不符合目标。

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
该数值门还必须通过任务可共同达成（非 zero-sum）和 evaluator 版本一致性审计。初始模型结果表面为 2/3；严格质量审计后，只有 K2 保留为 1/3。


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

- **S1 SHELTER-INTAKE1：no-go，不能当作合格 FAIL。** MA-ID 两任务通过；共享臂中 Agent A 明确发现 Agent B 已关闭唯一能容纳四人 H-103 的 CR-201，并正确报告当前目标不可行。A 被禁止改变房间状态；B 被要求必须封房。因其余房间容量均不超过 3，两个任务在共享状态下没有共同可行解。它违反本套件“协调后双方可成功、非 zero-sum”的设计门；观察到的共享失败是目标互斥，不是合格的共享桌面干扰效应。run 输出的 0.5 还来自过期的已安装 Oracle，不能作为有效评分。
- **K1 COURT-SERVICE1：no-go。** 三臂双方全 PASS。Shared 臂有较高 GUI 调用数和耗时，但成本增加不是任务失败；不能声称达标。其 active-docket 设计也与 Case 3/A-01 上下文机制近邻，不建议简单调参继续救。
- **K2 ROUTE-RECON1：首轮符合。** MA-ID 完整通过。Shared 中共享 GUI 焦点在路线草稿与 WO-503 客户改期页间反复变化，两边均部分失败。Shared+Lock 中客服任务全通过，但路线仍包含已 Deferred 的 WO-503，故路线 oracle 0.8571；锁没有跨工作流版本事务。
- 九个有效 arm 均 `error=null`，没有将 infrastructure-invalid 计作 FAIL。累计约 12,955,536 input tokens（11,356,725 cached）、44,495 output tokens，elapsed 总和约 5,492 秒（91.5 分钟）。run IDs 与逐次完整日志位于相应 RAID run directories，见 handoff。
- 初始准备阶段的 Guest timeout、NTFS Codex HOME、旧 key 额度错误仍作为 infra-invalid 历史保留，不能与上述有效结果混算。

结论（审计修正）：本批只有 **1/3 首轮保留**（K2）；S1 和 K1 均 no-go。S1 是目标互斥的 zero-sum 任务并存在 Oracle 版本漂移；K1 是全臂 PASS。需要补出两个新候选并先通过共同可行性与 evaluator 语义门；不改写或删除历史 run。


## 2026-11-12 质量审计修正（覆盖本文件较早的 S1 判定）

S1 原始 run 文件仍保留，原始运行状态不是 API/Guest infra-invalid；但不能把它计作成功的 benchmark triplet。

1. **目标没有共同解。** Intake 要求四人 Chen 家庭 H-103 留在同一间房，且 Oracle 检查该房间当前开放、容量足够。CR-201 是唯一容量为 4 的房间；Facilities 任务则要求把 CR-201 关闭并将容量设为 0。其他房间容量为 2 或 3；Intake prompt 禁止改房间状态，Facilities prompt 禁止改 placement。因此两任务无法同时通过，不论操作顺序、锁或 Agent 能否协调。
2. **真实轨迹印证结构性不可能。** Shared 与 Shared+Lock 中 Agent A 的 INFEASIBLE 文件都记录了唯一四人房已被关闭、其他房间最多三人；Shared A 的原话还明确说它没有权限解开这个冲突。这不是误路由或未恢复，而是合理的不可行性报告。
3. **Oracle 实际加载了旧副本。** runner 的 PYTHONPATH 解析到 OSWorld checkout 下的 evaluation_examples/task_class/pg_shelter1_oracle.py。该文件 SHA-256 为 82dc5de1de8cb1c788aa45846b83b4177182bfaaf25ce289670116af95dd51b3；分支真源 tasks/paragui/pg_shelter1_oracle.py SHA-256 为 fc7ee04e230aa8ec3fec54019b9aa253f172462a6c6550105ac5db632eee552a。已安装旧版没有 no-op 防护：零 assignment 仍因空集合容量检查为真得到 intake score 0.5；当前分支 Oracle 修复版应给该状态 0.0。该错误不反转 FAIL/PASS，但证明实验加载的 evaluator 未与冻结源一致。
4. **判定修正。** 保留九臂原始 run 与原始 0.5 记录，仅将其标记为历史原始输出；S1 不算目标合格案例，也不算有效的机制失败证据。不能通过只修分数或重跑同一互斥 fixture“救活”；若将来重做，必须提供替代的四人可行房间，让两任务存在共同 PASS 解，再冻结、同步并校验实际导入 evaluator，并从 MA-ID 起完整重做 triplet。

Run IDs:
- MA-ID: cdesk3-s1-ma-id-20261112T063914Z-866997
- Shared: cdesk3-s1-shared-20261112T065201Z-873251
- Shared+Lock: cdesk3-s1-shared-lock-20261112T071251Z-882842

这会覆盖文中早先将 S1 计入 2/3 的描述；表格分数仍作为原始 result.json 输出，不应再解释为冻结 Oracle 下的规范评分。
