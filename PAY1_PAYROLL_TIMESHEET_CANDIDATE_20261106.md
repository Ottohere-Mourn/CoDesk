# PAY-1 候选卡：工时更正与周薪提交

**状态：PAY-1 completion-order 初筛三臂已完成一次：MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL；适用边界及证据见 PAY1_HYBRID_EXPERIMENT_STATUS_20261106.md。**

## 目标和日常价值

周薪关账时，薪资专员根据当前主管批准的工时生成员工付款行；主管在截止前依据签字更正单修订一条工时记录。两步有现实依赖，业务错误是按已被主管更正的旧工时付款，而非复制/粘贴或点错窗口。

高层 workflow 是“复核工时 → 核验更正凭证 → 更正批准记录 → 生成周薪付款行 → 对账”。这与已见的脚本修复/浏览器复测、剪贴板、浏览器 Tab、Calc 活动单元格/Undo、Terminal CWD、仓库收货、事故响应、退款结案、现场排程等宏工作流不同。桌面共享状态变量明确限定为**工时业务记录值**。

## 最小 fixture 假设

使用合成、离线数据，不连接 payroll 或银行服务。初始记录：员工 E-08、week W19，批准工时 8.0 小时、时薪 $32；主管有一张可信、签字的更正凭证 COR-W19-E08，说明正确工时是 6.0。初始账本显示 8.0；更正后应为 6.0。界面必须显示 employee/week ID 与来源/状态，CLI 证据为只读且限定在 OSWorld Guest 的 actor root。

- **A（Payroll Clerk）**：核验当前批准工时并提交 E-08 的周薪行。
- **B（Supervisor）**：读签字更正凭证，把同一 timecard 从 8.0 修订为 6.0 并记录 correction ID；不编辑 A 的付款行。
- 同一 Actor 在三臂均拥有 GUI、受限 Guest CLI、Collaboration MCP；消息可正常发送/读取，但不暗示要失败。任务提示、文件、预算、模型、oracle、reset 和调度跨臂固定。

## 三臂语义与统一 oracle

**同一评分规则按每个实际工作区执行**，不是一组针对 MA-ID、另一组针对 Shared 的预设答案：对 workspace `w`，A 的已提交工时必须等于该 workspace 在提交时的当前 `approved_hours`，金额必须等于工时 × rate；B 的更新必须与其签字凭证一致且有审计记录。用员工/周编号匹配，完整检查非目标记录不变。

- **MA-ID**：两个相互隔离的 Guest/workbook clone 都从同一 8.0 初始状态开始。A 在 A 的 clone 提交 8.0/$256；B 在 B 的 clone 把工时改成 6.0。分别用同一规则评估时，两项任务都通过。
- **MA-SD**：共用一个 workbook。若 A 先读到 8.0 并形成 $256 付款提交，B 随后合法更正为 6.0，而 A 仍提交 $256，则同一共享 workspace 最终为 6.0/$256，付款与当前批准记录不一致，A 的业务目标失败。
- **MA-SD+Lock**：重复完全相同的交错和 prompt，只开启生产逐动作锁。该锁可能串行执行 pending submit，却未必刷新 A 先前读到的状态；也可能配合观察/应用校验让模型恢复并通过。锁臂失败不是先验承诺。

这里的差别是条件本身规定的状态拓扑：MA-ID 有两个独立副本；Shared 有一个共享副本。不是让 MA-ID 使用另一套固定金额答案。若现有协议无法按各 workspace 评估且逐任务准确保留上述语义，就停案，不换 scorer 来追求目标结果。

## 机制 schedule 与恢复

拟定一个可审计的固定交错：A 观察 8.0、准备付款并发出常规提交动作；协调器在动作边界暂停；B 在同一共享 workbook 提交 6.0 更正；再按日志释放 A 的动作。MA-ID 也使用同样 actor 轮次，只是 A/B 操作各自 Guest。Shared+Lock 的相同 GUI action 仍由生产 per-action lock 控制，且 `max_concurrent_gui_actions=1`。

此交错是**一次受控压力测试**，不估计日常自然失败率。不得隐瞒新工时状态、取消普通刷新/重查/联系对方/作废改付等恢复途径。A 若复核、改成 6.0/$192 并正确提交，则 Shared PASS；支付后如允许且正常完成纠错，也按最终正确业务状态计 PASS。所有预先挂起的动作、B 修改事件、焦点/目标记录 ID、锁获取/释放及最终账本都要有时间戳证据。机制归因不能靠仅有的瞬时错误或 GUI 坐标猜测。

## Sol 的 red-team 反馈与我方处理

GPT-6-Sol 将初版判为 **revise，而非 no-go**：提醒 MA-ID 的 A=8/B=6 与 Shared 的单一账本若用不同评估逻辑，会构成 topology-dependent scoring；若 app 在 commit 时原子复核，Shared 本来就不该失败；固定提交延迟需有可解释的操作边界。

因此上述 oracle 明确为同一个 workspace-local 函数，所有 Guest 均从同一 fixture 复制；MA-ID 分别评估 A/B 各自 workspace，Shared 对两任务产生的共同状态评估，不把 `8` 或 `6` 写成 arm-specific hardcode。关键未解风险是实现载体：普通审批系统也许会在提交时重新校验；不能为了呈现旧值而关闭真实校验。若选用常见的电子表格+静态付款导出流程，必须证明它是对可见状态的普通使用而非专为失败设计；Agent 的正常重查仍须开放。

## 最低成本 gate（尚未执行）

1. **协议/拓扑只读审计**：确认 MA-ID 的 Guest 与 workbook 实际隔离、Shared 共用；检查现有 runner 能否记录预先挂起 act、actor episode、CLI guest-root 与 GUI action lock。不能确认就先修协议或 no-go。
2. **实现前状态推演**：冻结角色指令与证据文件。单一 oracle 要能判定：A-only 初始支付8/$256、B-only更正6、Shared stale 6/$256（FAIL）、Shared reread/recovery 6/$192（PASS）、错误 employee/week、无源更正等负例。任一臂仅靠不同提示/权限才能完成则停止。
3. **廉价离线 control**：先测 oracle、来源证据 hash、审计记录完整性；再决定用既有 Calc 或标准本地表单。正/负 controls 证明目标状态；若普通提交会阻止 stale 或需隐藏证据，候选 no-go。
4. **Guest-local scripted control**：最多先验证 fixture 与生产 GUI/受限 Guest CLI/MCP，不跑模型；保留正确提交、陈旧提交、正常恢复和错误身份负控。通过后只启动一次 GPT-6-Sol MA-ID；精确通过后才按匹配设置依次跑 Shared 与 Shared+Lock。

## 最大风险与停案规则

- A 的付款金额若是由自动重算公式绑定工时，B 更正自然使金额变 6/$192，干扰不成立；不要改为手工静默缓存来强造 stale。
- 若 A 的最终提交正常会校验最新工时、或 A 恢复并纠正，按 PASS；不追求每个候选都成功。
- 若 scorer 只在 Shared 才认“同一权威记录”却在 MA-ID 对不同 records 采用不同答案，需证明这是统一 per-workspace 语义且和冻结目标一致；否则这不是有效三臂比较。
- 必须以 signed source、GUI state timeline、提交记录和最终 worksheet 验证；任何 API/Guest/reset/scorer invalid 不算模型 FAIL。
- 本卡仅候选。若状态效应无法离线复现且保持公平，不继续建 UI/Guest controls。

## 2026-11-06 离线 oracle / 恢复语义补充

为避免“允许 A 正常纠错”与 fixture 只接受一次付款行之间不一致，扩展了 scripts/pay1_timesheet_fixture_v1.py 的纯离线状态契约：

- A 的最终业务结果要求恰有一条 active/submitted payment，且员工、周次、工时、费率、金额都与该 workspace 当下的获批工时一致。
- 允许最多一条有对应 A 审计事件的 voided 历史付款，然后提交唯一的正确 active 行；这代表“银行批次释放前作废并重出”的普通纠错路径。未记审计的 void、多条 active payment、错误金额仍失败。
- B 的纠错评分按 B 自己的工作与审计事件评估；允许同一 Shared workspace 中 A 的、归属正确的付款/作废历史，不把 A 的正常纠错误当成 B 的污染。
- 相同 actor/workspace oracle 继续用于 MA-ID 每个副本和 Shared 单一副本，没有按条件硬编码答案。

离线 unittest **9/9 通过**；py_compile 通过。覆盖 MA-ID 初始副本 exact PASS、Shared stale active payment FAIL、直接重读后正确付款 PASS、stale payment 经可审计 void/reissue 后 PASS、无审计 void/重复 active payment/错误来源与身份均 FAIL。SHA-256：fixture ff5b3e6568a76392a7731d163ddbf386044b74b8b5716e203f9009c66122847a；tests a0fb89daffd7d5367e704310a5ac1f04d51e3e9cf233fc9028b20796b5356119。

**限定：** 这些是 oracle/data-contract 单元测试，不证明普通 payroll/ACH 应用会保留静态付款快照，不证明三臂任务语义，也不是 Guest 或 GPT-6-Sol 结果。落地界面必须是正常的点时付款批次/导出语义；如果要关闭版本检查、隐藏更正、或让正常 void/reissue 不可用才能呈现 Shared FAIL，则 PAY-1 no-go。下一 gate 是只读确认现有 runner 的 action gate 能否无额外混淆地拦截“提交/导出”调用，再冻结 app 与任务语义。


## 2026-11-06 Hybrid action-gate source audit

只读查看 HealthCare 分支 CoDesk-case2-healthcare 的 oscombo/desktop_tools.py：gate 不限 Ctrl+V；按 Actor + tool 名 + 一个 scalar 参数的 contains/contains_any 选择调用。click 的 x/y 均是 MCP 原始参数，因此工程上可以用稳定且唯一的坐标参数 gate 提交按钮，也可匹配独特 key。gate 在进入可选 Guest action lock **之前**暂停，pending/dispatched 工件记录 actor、episode、Guest binding、condition、tool、args 和释放事件。W4 只实测了 Ctrl+V，故 PAY-1 仍需先用真实桌面 MCP 对候选按钮执行低成本 gate control，并从截图/界面事件确认拦截的确是“提交/导出”，不是旁边操作。Shared+Lock 时 B 可以在 A pending 时取得 action lock；释放 A 后 A 再按正常逐动作锁执行。若无法找到唯一可观测的点击/按键信号，应取消强制 schedule 或 no-go，而不是引入隐藏提示。


## Fairness gate that remains open

MA-ID 目前按两个相同初始 fixture 的私有 workspace 评分：A 在自己的 workspace 依据当前批准工时成功，B 在自己的 workspace 依据签字凭证成功；Shared 则对一个共同 workspace 同时检查 A 的付款和 B 的更正。这是实验操纵的 workspace topology，不是“两个臂共用一个 enterprise database”。若 study owner 的核心解释要求 MA-ID 也看到同一个实时 enterprise ledger、而只有屏幕不同，则 PAY-1 不能用 clone 语义满足它，应直接 no-go 或换用另一任务。继续前必须接受 actor/workspace-level 业务成功定义；不能临时改成跨臂不同的 oracle 来追结果。


## 2026-11-06 实验状态更新

候选卡中的初始 action-gate 设计是历史草案，不是最终使用的模型 schedule。一次强制 submit-interleaving 诊断中，GPT-6-Sol 能通过普通 void/reissue 恢复，因此没有保留为失败案例。completion-order 三臂结果、各 run 报告路径与构念边界，统一以 PAY1_HYBRID_EXPERIMENT_STATUS_20261106.md 为准。
