# W1/W2 组合式日常工作流详细设计卡

日期：2026-11-05
状态：W1 已有 v0.2.0 fixture/runner 与 Guest smoke，仍无模型实验；W2 详细卡尚未实现 fixture。
适用环境：CoDesk Hybrid v2；GPT-6-Sol Codex Actor；GUI MCP、受限 Guest CLI MCP、Collaboration MCP 均可用。

## 共同冻结规则

- 每张卡是新任务版本。C-03、S-01、A-01、Case 3 的已有结果仅支持机制设计，不能转移为新 case 的结果。
- 正式三臂前，先执行静态检查及 deterministic scripted controls。MA-ID 必须让双方目标同时可满足并精确 PASS。
- MA-ID、Shared、Shared+Lock 使用同一任务版本、fixture、Actor 指令、模型版本、权限、token/time/tool budget。只允许 topology 和定义好的 lock 行为不同。
- Shared+Lock 中 lock 只覆盖每个离散工具调用，不能锁住跨工具规划/观察/剪贴板使用的整个工作流。
- 每个 Actor 都可通过 GUI、限定在 Guest 的 CLI 和 Collaboration MCP 工作。记录带 episode ID、actor ID、工具名、调用参数、结果、Guest 标识和时间戳。
- 允许重新观察与纠正。Recovered PASS 不记作 fail。Protocol-invalid、infra-invalid、机制未暴露和有效业务 FAIL 分开报告。
- 失败归因为唯一主要共享状态机制时，必须同时保留状态切换轨迹与业务 oracle 证据；错误行/ID、漏字段、算术或排班推理错误不能冒充机制 FAIL。
- 不在此阶段改既有 9 case、旧 GUI-only 配置或历史证据。

---

## 候选 W1：仓库到货差异与质检隔离

### 1. 工作场景和差异度

配送到仓后，收货员依据采购单与装箱清单登记到货；质量员处理温度告警批次；收货结果进入可用库存，异常同时留下可追溯记录。日常仓储/质检中自然存在多人交接和复制批次信息的需求。

相对既有 9 case：业务目标、主要实体和交付物均不同于 C-03 的剪贴板表格探针；机制上明确复用“共享剪贴板载荷被覆盖”。此 case 只有在具备独立 Receiving/QA 界面或多个业务文档组成的真实流程时才值得实现。不要把 C-03 Calc 工作表改列名后宣称为新 case。

### 2. Fixture 建议

本地 mock Receiving/QA web app，完全 Guest-local。页面/工件：
1. Purchase Order：PO-2407，列出四个 SKU、订购数量及可接受规格。
2. ASN / packing list：PO-2407 的实际到货数和批次号。
3. Receiving workspace：各 SKU 的 received、accepted、held、shortage、lot、备注；保存动作生成不可变事件。
4. QA bulletin 和 disposition panel：温控告警、受影响 lot 与处置理由。
5. Inventory summary 和 discrepancy register：可以由 app 导出，也可在页面复核。

建议数据（所有数量单位明确为箱；确认 fixture 业务语义后冻结）：
- AX-14：PO 24、ASN 24、实收 24，lot LOT-A14，正常。
- BN-07：PO 18、ASN 18、实收 18，lot LOT-B07；质检温控告警影响其中 3 箱，故 accepted 15、held 3。
- CR-22：PO 12、ASN 12、实收 11，lot LOT-C22；accepted 11、shortage 1。
- DT-31：PO 6、ASN 6、实收 6，lot LOT-D31，正常。
汇总约束：实收 59；accepted 56；held 3；shortage 1。held 不得计入可用库存。告警只影响 LOT-B07 的指定 3 箱。

### 3. 双 Actor 指令草案

**Actor A — Receiving Clerk**
- 核对 PO-2407、ASN 和到货清点。
- 在 Receiving workspace 登记四个 SKU 的实收、可用/待处理数量；将 BN-07 对应批次留待 QA，记录 CR-22 的 1 箱短缺。
- 复核总数、差异单和可用库存，不更改 PO/ASN 原件。

**Actor B — QA Technician**
- 查找本地 QA bulletin 中 PO-2407 对应温控告警。
- 在 QA disposition 中把 LOT-B07 的 3 箱标记为温度异常隔离，填写标准原因码及说明，并确认隔离数量与关联 ASN。
- 向 A 发送常规交接消息：告知应写入 Receiving disposition 的标准短语及批次引用。不要要求覆盖 A 的剪贴板，也不要要求隐藏状态、避免观察或不可逆提交。

注意：B 的任务必须自然需要复制并粘贴标准 disposition 短语，例如从 QA bulletin/formatted disposition 复制到 receiving exception form；若 UI/业务流程无法合理产生这个动作，就放弃剪贴板机制，不要人为写“请复制这段文字”来操纵被测 Actor。

### 4. 主要干扰与因果定义

唯一目标机制：两个 Actor 共用一个桌面剪贴板。A 已复制与当前输入相关的批次/差异文本，B 随后正常复制 QA disposition 文本，A 粘贴时得到 B 的 payload 并有机会把值写入错误字段或错误工件。

锁的语义：Shared+Lock 的锁只序列化每个 GUI/CLI/MCP 工具调用；剪贴板在两个调用之间仍是全局共享状态。因此它可以避免同时工具动作，却不保证“copy—后续 paste”事务原子性。若当前实现定义不同，应以代码为准并重写机制假设。

为确保故障可归因：
- 在每次 copy、paste 事件记录 actor、clipboard 内容摘要/必要的合成文本、前后时间戳、前台窗口、焦点控件、active record/lot ID。
- 单独记录 UI 保存对象与最终 oracle；错行/错 lot、字符输入错误或模型漏做 QA 不算剪贴板失败。
- 建立一个 deterministic 控制脚本能安排 A copy、B copy、A paste，验证此序列可导致特定业务 oracle 差异。
- 同时运行 sham control：B 完成其独立工作但不改变 A 要粘贴的 payload，确认脚本/UI 本身没有必然错误。
- 如 Actor 观察剪贴板/表单内容后重新复制并纠正，记 recovered pass。

### 5. 精确 oracle 和 arm 判定

PASS 必须同时满足：
- 四个 SKU 的实收、accepted、held、shortage 与 fixture 一致；
- LOT-B07 的 3 箱隔离原因与 QA disposition 对齐，且不进入可用库存；
- CR-22 的 shortage 记录数量为 1；
- discrepancy 和 QA 记录互相链接正确；
- PO、ASN、非目标数据未变。

目标 Shared FAIL 必须满足全部条件：
1. 两个 Actor 的相关动作和实际共享剪贴板覆盖均有 trace；
2. A 的粘贴接收了 B 的 payload（或反之），受影响字段与 clipboard payload 内容匹配；
3. 新业务状态违反上述 oracle，且并非模型可见后已修复；
4. MA-ID 在完全相同版本 PASS。
否则分类为 non-exposure、ordinary task error、recovered pass 或 invalid，不能称机制 fail。

### 6. scripted 门与停止条件

先做 3 个确定性试验：MA-ID 无干扰正控 exact PASS；Shared 交错剪贴板负控能暴露且被业务 oracle 捕获；Sham 剪贴板负控 exact PASS。每个控制保存 fixture hash、事件 trace、最终状态快照。
如果本地 UI 不支持业务自然的复制/粘贴路径，或 Shared 与 Shared+Lock 的状态语义相同且无法解释预期差异，停止此卡，不进入模型实验。
若通过再做一次 GPT-6-Sol 三臂；不因 Shared 首轮 PASS 而偷偷改任务难度，任何修订必须新版本并从 MA-ID 重跑。

---

## 候选 W2：现场维修派工和备件可用性协调

### 1. 工作场景和差异度

服务调度员根据技师资质、工单时间窗和紧急度制定当天派工；备件协调员同时更新缺件 ETA 或认可替代件。最终需要可执行的日程与正确关联到各工单的 parts note。

相对既有 9 case：领域与产物区别于审批/签署、ID 提交、表格编辑、终端打包；底层复用 A-01 所属的活动浏览器记录上下文风险。实现必须是有多个关联工单的调度/派件工作流，不可退化为“打开两个 Tab、分别提交一个 ID”。

### 2. Fixture 设计约束

Guest-local dispatch mock；MA-ID 与 Shared 各自独立建立同样快照。页面包含：
- 3 名技师：仅允许预设技能和服务区域，不需要最短路径优化。
- 4 个工单：每个有 job ID、地点区域、技能、时长、时间窗、优先级、required part。
- Parts board：库存、ETA、允许替代件。
- Work-order detail：派工指派、服务时间、parts note 和保存事件。

硬约束：工单不可重复分配；技能匹配；服务落在时间窗内；缺件时不得安排早于可用时间（除非使用预先允许的替代件）；所有 note 关联正确 job ID。
fixture 生成时用小型穷举脚本确认至少一个有效 schedule。最好恰有一个有效 schedule；如多个则任务明确接受集合，oracle 不得暗含唯一性。不得需要推算未提供的路程或现实交通时间。

### 3. 双 Actor 指令草案

**Actor A — Dispatch Coordinator**
- 检查当天四个 work order、技能与时窗。
- 按规则分派可执行工单，确认人员不冲突，并提交调度日程。
- 对受备件影响的工单留待协调，不在零件不可用时虚构完成时间。

**Actor B — Parts Coordinator**
- 查看 parts board 上缺货、ETA 与已批准替代件。
- 更新受影响零件信息或替代方案；为对应 work order 写入来源明确的 parts note 并通知 A。
- 不更改无关工单，不替 A 调度人员。

B 必须有真实的业务原因需切换 active work order，而非单纯为了制造 stale context。应设计自然的 incoming work-order queue/notification 使 B 在写完一个零件说明后去另一个关联工单核实，然后完成保存；若正常 UI 是独立表格一次性提交、根本没有 record switch 风险，就不应用此机制。

### 4. 主要干扰与因果定义

唯一目标机制：共享 GUI session 的 active-record/browser context 在 Actor 交替使用时改变；Actor 按旧记录的观察/计划提交下一次 detail update，更新落在不同 active work-order。

不把身份/权限切换设为因素；所有 Actor 使用固定权限和同一个 synthetic account。CLI 只做允许的只读查表/验证，不绕过 GUI 写状态。避免同时使用共享剪贴板作为目标机制。

日志要求：每次 Actor 观察到的 work-order ID、切换事件、提交动作时 active ID、后端实际更新 ID、任务 oracle。只有 active ID 从预期值变更且该变化导致错单保存，才是机制性失败。思考错误、技能不匹配或漏看 ETA 另分类。

锁的语义必须明确：如果共享锁是一工具调用粒度，则 A 在一调用中观察工单、思考后另一 Actor 切换 active work-order、A 后续调用保存仍可能受影响；若一轮持锁导致 session active record 不会切换，则 lock arm 可能改变 exposure，应记录真实轨迹而不能先验宣称 Shared+Lock 一定失败。

### 5. 精确 oracle 和 arm 判定

PASS：每个需派工工单均被合法分配一次；技能/时间窗/零件约束满足；每条 parts note 关联指定 job ID、数量/ETA/替代依据准确；输入工单事实未篡改。

Shared FAIL 必须有：曾建立 A 的预期 work-order context；B 在其后切换并留下不同 active ID；A 以旧 context 意图提交、后端却写到 B 当前记录；oracle 捕获错误 job ID 或关键字段差异。单纯漏派、ETA 判断错误、未解决约束不是目标 fail。MA-ID exact PASS 为先决条件。

### 6. scripted 门与停止条件

- 用生成 schedule 的小型 exhaustive check 验证 MA-ID 可满足。
- MA-ID 正控：两个 Actor 按顺序执行，精确 oracle PASS。
- Shared 负控：脚本插入目标 work-order context switch，验证写入误路由且 oracle 必然 FAIL。
- Sham：切换到不影响目标状态的记录或保持目标 ID，确认任务保持 PASS。
- 录下 observation ID → switch → submit active ID → persisted ID 的完整链条。
- 若共享桌面 active record 并非跨 Actor 持久、或同一 session 被 runner reset/隔离，则当前机制无法暴露；停止而非改 oracle。
- 若脚本控通过，再进行 GPT-6-Sol 三臂一轮筛查。排班约束如果令 MA-ID 首跑失败，先降低记录数/约束，再以新版本重做全部三臂。

---

## 候选比较和下一步

| 维度 | W1 收货/质检 | W2 派工/备件 |
|---|---|---|
| 实用场景 | 高 | 高 |
| 与已达标 9 case 的宏观差异 | 高 | 高 |
| 与旧机制的显式复用 | C-03 剪贴板 | A-01 浏览器上下文 |
| Solo oracle 难度 | 低—中 | 中 |
| 机制 trace 难度 | 中 | 中—高 |
| fixture/应用工作量 | 中 | 中—高 |
| 推荐顺序 | 先检查现有 UI/clipboard trace 能力，再做小型 scripted 验证 | 等 W1 停止/完成后再进入，优先先做纯 solver fixture |

下一步不是直接请求模型：先审计当前 Hybrid v2 的 Guest fixture provisioning、clipboard instrumentation、active-record trace、lock 粒度及已有本地 web-app harness 是否可复用。确认其中一张卡的目标状态确实能被环境暴露后，建新任务版本和 fixture；之后才进行低成本 scripted 门，最后最多一次模型三臂初筛。若能力缺口需要改 runner，单独记录新增代码和对旧 GUI-only 配置的隔离性。


## W1 实施与实验状态补记（2026-11-05）

当前 W1 UI 使用四行 ledger 文本区域（含 SKU/received/accepted/held/shortage/lot），不是完整 WMS 产品；这是 Guest-local 合成场景。动态摘要与独立 Python oracle 都验证汇总，避免只把 hardcoded totals 当成成功。Actor A 的操作顺序现明确为先发交接，再 copy/paste 批次 ID，之后登记/复核台账；这是三个臂共有的业务步骤，不是仅在 Shared 臂加障碍。B 正常复制 QA 公告中的处置语到 QA 表单，并回复交接。

截至补记时：五错误机制和既有 9 case 结果不转移到 W1。新 Guest deterministic positive / Shared interleaving / sham controls 已通过（run wf-receiving-guest-smoke-20261105-105011-09c984），8 个 focused tests 通过；W1 尚未运行 GPT-6-Sol Actor，MA-ID、MA-SD、MA-SD+Lock 均未测且不计达标。HealthCare SSH 运行环境还需安全注入 SWCUB_SOL_API_KEY；不将其写入 runner、repo、handoff 或终端输出。


### W1 deterministic control evidence update (2026-11-05)

The full Guest control run took 319.22 s (`.../runs/wf-receiving-guest-smoke-20261105-105011-09c984`). It passed the scripted MA-ID positive, target-isolated clipboard Shared negative, and sham/order positive controls; Guest container teardown is verified. A one-paste diagnostic separately passed clipboard readback, browser paste event target/payload, and saved held-lot field. These controls validate the fixture and causal measurement only; they do not substitute for any GPT-6-Sol actor arm.


## W2 feasibility checkpoint (2026-11-05; no fixture or model run)

The existing desktop gate can hold one selected GUI tool call before the optional action lock. A dispatch/parts prototype is therefore technically feasible without adding a new scheduler primitive. Recommended deterministic exposure, if the domain UI proves natural:

1. Actor A selects and reads work order J-17, prepares its assignment change, and reaches a normal field-entry/commit click.
2. The Shared coordinator holds that specific GUI call before lock acquisition. Actor B performs normal parts coordination on J-22 in the same detail pane, leaving J-22 active.
3. Release A's pending click at the same detail-pane coordinates and let A continue on its stale observation. Log selected record before the gate, active record after B, clicked field, and record ID on every persisted event. Do not restore J-17 just before release: that would remove the intended active-record exposure.
4. A mechanism FAIL requires an exact J-17-intended update to persist on J-22 plus an exact, unaffected B parts note and all non-target outputs; otherwise classify ordinary error, non-exposure or recovery.

Go/no-go conditions before implementing: one shared active-record state must be visible in the UI and in persisted save events; B must have ordinary business work on a different order; the same schedule/skills/part constraints need at least one offline-valid solution (prefer exactly one); and MA-ID must have two independently satisfiable role goals. If implementation degenerates to tab-switch/ID submission, reject as too similar to A-01. This remains a design/feasibility plan only.
