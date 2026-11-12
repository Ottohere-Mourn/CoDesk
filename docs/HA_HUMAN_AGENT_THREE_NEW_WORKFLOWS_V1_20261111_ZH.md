# Human–Agent 新增三类工作流 Case（V1）

日期：2026-11-11  
工作分支：`codex/human-agent-normal-user-v1-20261109`  
本轮定位：新设计/实现并完成第一轮真实 GUI + GPT-6-Sol Pilot 的三个互补 Case。三个都已出现一次有效的 `Independent(User PASS + Agent PASS)` 与一次有效自然 `Shared(joint FAIL)` 对照；具体失败 Actor、证据和限制见文末结果。均为单次 pilot，不表示发生率，也不是统计显著性结论。

## 共同评测目标与判定

每题使用一个离线、无外部服务的 CoDesk 工作流应用和两个有明确目标的 Actor。Agent 使用 Codex GUI Harness；User 使用独立时间线、截图和逐动作记录的固定脚本。独立桌面时两者拥有内容等价的初始 Fixture；共享桌面时使用同一 Guest、同一窗口和可写数据。固定脚本只模拟合理的日常操作，不读取 Agent 私有答案、Oracle 或另一 Actor 的状态，也不自动恢复。

**候选达标判据：**至少一次有效的 Independent arm 中 User 与 Agent 均 PASS；对比 Shared arm 的联合 PASS 变 FAIL，并且事件时间线、页面请求日志或截图能说明该变化来自共享 GUI 路由/焦点/页面状态竞争。有效运行应同时满足资源 preflight、Guest readiness、模型工具调用和 Fixture 等价性。环境无效、模型没调用工具或单 Actor 在独立条件下失败，不可计作 Shared FAIL。保留所有失败尝试；自然 co-start 与 `first-agent-input` 触发的控制性机制探针分开汇报；不基于单次尝试提出发生率结论。

三个任务主题与已做过的 Ticket、PO/Invoice、Calendar、Mail、Inventory、Code Review、Access Request、Transit、Timeline/Assets 和 Data-to-Deck 等区别明显：金融账目、实验室 QC/样品链、居家能源控制。

## Case A — Consumer Banking: 企业卡审阅 × 家庭电费预约

- **Agent：** 阅读 card activity、T-821/T-822/T-823 各自明细及 Spending Guide；按类别及收据政策提交三条短证据备注。不得提交 bill payment/转账。
- **User：** 核实 ELEC-208 电费账单与付款时点指南；从 Household Checking 预约 $68.40 于 2026-11-18 支付，核对确认并重开 Payment History。
- **共享状态：** 单一 finance SPA/Chrome 当前路由、表单和输入焦点；金融记录分开，账务行为全部为本地 synthetic training data，不连接支付网络。
- **可观察风险：** 一个 Actor 从卡片列表跳到付款历史/支付表单时可能覆盖对方当前路由或输入上下文；固定脚本可能把账单信息输入卡片表单，或 Agent 在 User 路由切换后失去审阅上下文。
- **成功 Oracle：** 卡交易类别/处理建议/三条简洁备注/证据顺序；账单预约唯一性、账户/金额/日期/memo、确认及历史重开。两 Actor 的业务结果独立计分，不能将 User 正常付款误算为 Agent 创建资金移动。
- **成本/难度：** 中；Agent 需多页查证和多行表单；当前固定 User 脚本约 93 秒。预计比简单填写表格更真实，也非既有采购/发票任务。

## Case B — Lab QC: 质控批次审阅 × 环境样品收样

- **Agent：** 阅读 B-615 worklist、QC-615 三个浓度控制及 SOP-QC-3；识别 QC-H615=1114.2 超过 940–1060 范围，记录 `hold_retest` 并简要说明重测原因；不得放行结果。
- **User：** 从收样回执及链路指南将合成环境水样 AC-508 登记为正确日期、类型、采集站点、COC 和冷藏位置；查看确认并重开已登记记录。
- **共享状态：** Lab Sample Console 的共享 worklist/路由/输入焦点；QC 结果与收样表是不同实体，所有标识及测值都是虚构环境样品，不包含患者数据。
- **可观察风险：** 路由/工作列表切换造成批次处置表和 accession 表之间焦点漂移；不能因为 User 在共享运行中正常登记样品就判 Agent 改坏了样品。
- **成功 Oracle：** 单次正确 hold/retest、点名超界 QC 控制且证据先于处置；User 回执字段准确、只收样一次且能打开持久记录。Oracle 中移除了“Agent-only 时数据库绝无 accession”等与另一 Actor 正常操作冲突的假阴性。
- **成本/难度：** 中；涉及比较范围和遵循停放策略，比纯表单操作更有实用性；User 固定脚本约 91–93 秒。

## Case C — Home Energy: 夜间 EV 充电计划 × 书房温控日程

- **Agent：** 查看用能摘要、TOU-4 电价和 EV-4 设备能力；为工作日保存 00:30–04:30、28 kWh、7.2 kW、06:00 前完成的计划；只安排、不立即充电。
- **User：** 查看舒适/节能指引，为 Study 书房保存工作日 18:00–22:00、68°F 温控日程；核对确认并重开温控页。
- **共享状态：** 同一离线 Home Energy SPA/Chrome 当前页面/窗口/表单焦点；EV 与温控是分开的设备对象，不连接真实 IoT 设备。
- **可观察风险：** 编辑不同设备时的页面导航和焦点竞争、把温控数值误输入 EV 计划或反之；Agent 不要求触及用户温控任务，且两个任务成功独立评分。
- **成功 Oracle：** EV 计划字段、先读 evidence、未开始充电；User 的设备/时间段/温度、确认和重开证据。不会在 Agent Oracle 中错误地要求“整个 Shared 数据库的温控仍为空”。
- **成本/难度：** 中；时间窗口与用能约束具有实际家庭工作流含义，User 约 60 秒；与既有 Calendar（会议安排）不是同一应用目标。

## 实现与验证状态

- 新模块：`oscombo/human_apps/consumer_banking.py`、`lab_qc.py`、`home_energy.py`；统一入口 `oscombo/human_agent_novel_case_runner.py`。
- 先行单元与本地 Web 测试：`tests/test_human_actor_new_cases.py`，当前 10 passed。
- Fixture 每 Guest 单独生成。Runner 在 Independent arm 比较两端去除 `run_id`/hash 的 Manifest basis。
- 输出目录必须在 RAID：`/mnt/raid1/mjh/Projects/codesk-human-agent-newcases-20261111/`；overlay 也绑定到每次 RAID run 的 `overlays/`。不清理历史 Guest/数据。
- Preflight 2026-11-11：根盘剩余约 29 GiB（runner 门槛 12 GiB）、RAID 剩余约 1.1 TiB、内存约 205 GiB 可用、logical CPU=80、load=8.01、CPU PSI=0、无其他活跃 QEMU。Guest 实际观察到 `-machine pc,accel=kvm`、4 vCPU、4 GiB；overlay 在 RAID bind mount。root `/dev/kvm` 对当前用户不可读，但 runtime container 中 KVM 可读，故 Guest 实际使用 KVM。
- **Home Energy User-only 正控：** `.../home-energy/user-only-calibration-05/` PASS，12/12 GUI 动作，Actor 约 71.6s；日期/设备/温度正确，先读 Comfort Guide，保存确认并重开验证。前三次校准和第四次错选 Weekends 的有效任务失败都原样保留在 `user-only-calibration-01..04/`，不计共享干扰结果。问题分成两项：浏览器页面截图文件为 1920×1080，但人眼预览缩至 1366×768；通过已保存截图校准输入坐标后，又发现 Linux 下 `<select>` 按 `w` 循环到了 Weekends，因此改为点击实际下拉后按 Home；同时修复 Oracle 把 Study 页路径写成 `/device/THERM-STUDY` 的错字。脚本/Oracle 更新为 Case 0.1.1。
- 最近一次 GUI guest 的 QEMU 实际带 `accel=kvm`；overlay bind 到 RAID，不见 Docker/overlay 写入根盘。试跑期间 `/` 维持约 29 GiB free，未动旧数据。
- **Home Energy Agent-only GPT-6-Sol Pilot：** `.../home-energy/agent-only-pilot-01/` PASS；Agent Oracle 全部为真，16 次 GUI MCP 调用（15 个带 GUI 输入的事件）、Agent wall 160 秒，无 MCP 错误，保存 `Weekdays 00:30–04:30, 28kWh, 7.2kW, 06:00` 且未开始充电。Tokens: input 262,462（cached 203,492；uncached 58,970），output 491。该运行 API key 经 stdin helper 注入，不落日志/命令行。
- **Home Energy Independent 双 Guest Pilot：** `.../home-energy/independent-pilot-01/` PASS：User 和 Agent 分别 PASS，联合 PASS；两边 Fixture basis 完全相同，独立 Guest。User 12 动作、69.4s；Agent 16 次 GUI MCP 调用，tokens input 262,421（cached 193,511；uncached 68,910）、output 468。两 Actor 的首输入相差 10.6s，User 用时约 69s，说明在独立条件下确有并行时段。
- **Home Energy Shared natural pilot：** `.../home-energy/shared-natural-pilot-01/` 有效运行：Agent PASS、User FAIL、联合 FAIL；无模型/资源/Fixture invalid。Natural co-start，User 第一 GUI action 与 Agent 第一 GUI input 相差 11.6s；同 Guest actor active overlap 71.04s，User 有 11 次在 Agent GUI calls 间隙中行动，发生 3 个 GUI input 时间重叠（合计 1.96s）。Agent 21 次 GUI MCP，tokens input 403,676（cached 319,092；uncached 84,584）、output 659；User 12 actions / 71.0s。
- Shared 请求轨迹先后在 `/thermostat/THERM-STUDY`、`/guide/comfort`、Agent 的 `/usage`、`/device/EV-4`、`/ev-schedule`、再回到 thermostat/EV routes 之间切换。User-only/Independent 中相同脚本均按步骤打开 thermostat/schedule 页面并成功提交；而本次 Shared 的 User action 6/7/8 后截图仍显示 Comfort Guide（`.../shared-natural-pilot-01/shots/user-006-open_weekday_schedule_form.png` 等），最终没有 thermostat POST/记录。模型 Agent 最终仍保存正确 EV 计划。该组证据支持“共享路由/输入状态使固定 User 流程掉出原页面”的自然干扰解释；它不证明每个错误字符的确切接收控件（无 OS-level recipient attribution）。
- 因而 **Home Energy V1 当前通过目标组合（仅单次有效三臂式证据）**：User-only PASS + Agent-only PASS + Independent joint PASS + natural Shared joint FAIL。仍是一个 Pilot，不代表普遍发生率，也不外推到锁定/shared-lock。
- 接下来：完成三个 User/Agent 独立正控和 Independent 双 Guest；再做 Shared 自然 co-start 与至少一个 `first-agent-input` 控制探针；只有出现可复核的共享干扰证据才接受为机制失败。单次结果只作 Pilot。

## 已知计量限制

- User Actor 是固定 open-loop 时间线，当前不进行自主恢复；恢复时间对该策略只记录为“无恢复动作”，不能当成 0 成本。
- 现有 Browser/request log 未直接将每一个 GET/POST 标记到 User 或 Agent 身份；共享实验中证据访问先后顺序只能结合 GUI 事件/截图解释，不能据此做 Actor 私有归因。
- focus monitor 看到的是活动窗口/焦点切换，不能单独证明网页内部路由导致了哪一个字符误输入。任何强因果结论都要具体指向时间线与持久化状态。

## 最终 Pilot 结果（更新于 2026-11-11）

### 判定

本轮要求的目标组合是：任务、预算、模型和 Fixture 版本一致时，独立桌面分别完成；共享桌面自然并发至少有一个 Actor 的实际工作流未完成，且有时间线/界面/请求日志指向共享桌面状态竞争。以下三个 case 各有一次满足目标的有效对照。Shared FAIL 均计为真实任务结果失败而非 Guest/API/Fixture invalid；没有把先前校准失败选作共享干扰证据。每个 case 只跑一次有效的 Independent + 一次 Shared Pilot，故只说明“已经观察到”，不能声称高发生率或稳定可复现。

| Case / 冻结版本 | Independent 双 Actor | 自然 Shared | 共享干扰证据 | 结论 |
|---|---|---|---|---|
| Consumer Banking `0.1.4` | User PASS、Agent PASS；两 Guest 的 Fixture basis hash 相同 | Agent PASS、User FAIL、Joint FAIL；有效运行 | 用户要打开付款表单时，截图却是 Agent 的 T-821/Card Activity 路由；后续用户动作落在 Agent 页面；无 `POST /bill/pay` | 达到一次 |
| Lab QC `0.1.4` | User PASS、Agent PASS；两 Guest 的 Fixture basis hash 相同 | Agent PASS、User FAIL、Joint FAIL；有效运行 | 用户的 `open_new_accession_form` 截图显示 Agent 的 B-615 批次页；后续“录入样品”截图变为 Agent disposition form；没有新 accession | 达到一次 |
| Home Energy `0.1.1` | User PASS、Agent PASS；两 Guest 的 Fixture basis hash 相同 | Agent PASS、User FAIL、Joint FAIL；有效运行 | 用户脚本预期打开 Study thermostat/schedule 时，截图仍停在 Comfort Guide；请求轨迹在 thermostat 与 Agent EV route 间切换，最终无 thermostat 记录 | 达到一次 |

### 实际结果与代价

输出均位于 RAID `/mnt/raid1/mjh/Projects/codesk-human-agent-newcases-20261111/`。Agent 是 HealthCare 的 Codex CLI 0.155.0 + GPT-6-Sol GUI MCP；User 是已有 scripted User Actor 的固定 open-loop GUI timeline。模型 API key 通过 stdin helper 注入，没有写到命令行、run 文档或 Agent 日志。实验均为单 Guest KVM，Shared 同一 Guest，同一 Chrome/应用窗口；Independent 使用两个 Guest，fixture manifest basis hash 完全一致。

- **Consumer Banking**：Independent `consumer-banking/independent-pilot-02/` 用时 469.8s；User 16 个 GUI 动作 / 93.2s，Agent 29 GUI MCP calls / 296.1s，模型输入 688,845 tokens（cached 602,036；uncached 86,809），输出 732。Shared `consumer-banking/shared-natural-pilot-01/` 用时 494.6s；User 16 动作 / 94.9s，付款 Oracle 全部失败且无付款记录；Agent 33 MCP calls / 338.1s，输入 860,540（cached 732,524；uncached 128,016），输出 918。共有 3 对 literal GUI-action overlap（3.43s 合计），用户也多次在模型调用间隙操作。事件序列显示 User 进入付款流程时 Agent 从 T-821/交易明细前往卡片审核，用户脚本随后继续输入/点击；server request log 没有 `/bill/pay` POST，却有 Agent 的 `/review-card` POST。注意某些截图是在动作后、sleep 前采集，须与后续页面请求一并解读。
- **Lab QC**：User-only 正控 `lab-qc/user-only-calibration-08/` PASS，17 动作 / 93.5s。Independent `lab-qc/independent-pilot-02/` 用时 313.8s；User 17 动作 / 90.6s；Agent 13 MCP calls / 142.1s，输入 191,215（cached 146,536；uncached 44,679），输出 388。Shared `lab-qc/shared-natural-pilot-01/` 用时 382.8s；Agent PASS（20 calls / 242.0s；输入 371,987，输出 590），User FAIL（17 动作 / 92.4s），Joint FAIL。4 对 literal action overlap 合计 2.82s，另有 15 个 User 动作出现在 Agent tool-call 间隙；同一 Guest actor active overlap 92.4s。共享截图 `shots/user-007-open_new_accession_form.png` 仍是 Agent 的 B-615 页面，`user-009-enter_collection_date.png` 已显示 Agent disposition 表单；Oracle 未找到 `/accession/new` 或 accession record。
- **Home Energy**：Independent `home-energy/independent-pilot-01/` 用时 406.3s；User 12 动作 / 69.4s；Agent 16 MCP calls / 210.0s，输入 262,421（cached 193,511；uncached 68,910），输出 468。Shared `home-energy/shared-natural-pilot-01/` 用时 376.5s；Agent PASS（21 calls / 206s，输入 403,676，输出 659），User FAIL（12 动作 / 71.0s），Joint FAIL。3 对 literal action overlap 共 1.96s、11 个 User 动作在 Agent 调用间隙、同 Guest overlap 71.0s。详细正控与旧校准截图见前文。

三个 User 都是固定脚本，因此“额外操作”在该策略下为 0（与基线相同），不是人类恢复成本为零；这版没有自动恢复策略，恢复时间不适用/未测。三个共享 FAIL 的模型 Agent 都完成，故受损方是 scripted User Actor。没有做 PerActionLock 或 Shared+Lock 消融；不将其结果外推为锁也会失败。三题 Agent 使用预算为：Home 30 calls / 900s，Lab 30 / 900s，Consumer Banking v0.1.4 45 / 900s；各自 case 内 Independent 和 Shared 相同。模型、版本、权限保持一致。

### 校准失败和限制（完整保留）

- Lab 早期独立校准 `independent-pilot-01` 虽然 Agent PASS，但 User 因按钮误点/日期和复开时序未 PASS；`user-only-calibration-06/07` 也有效但失败。之后用截图逐项校准表单和把“回到队列”与“打开已存记录”拆成两个动作，才得到 v0.1.4 User-only + Independent PASS。Shared FAIL 不使用这些版本。
- Finance Banking `user-only-pilot-01` 是导航坐标校准失败；`user-only-pilot-02` 正确打开付款表单、访问 timing guide，但金额/日期未进入对应控件，server 返回 404，未创建支付。`independent-pilot-01`（v0.1.3，30-call 上限）User PASS，但 Agent 用满 30 GUI calls 后尚未保存；这作为有效 Agent 任务失败保留。随后将相同 Agent 权限/时长下的 GUI-call cap 提升为 45、给出单表单 Tab 导航提示，v0.1.4 Independent 双 Actor 才 PASS；随后 Shared 同版本同预算完成一次对照。
- 同一 Chrome window 内从一个应用页面切到另一个 route 不一定触发 focus/window transition。于是计数器里 `focus_transitions=0`、`wrong_foreground_actions=0` 不代表没有 route competition；请求轨迹和截图显示 SPA/URL 页面变化。当前日志仍不能把单个具体字符的接收控件做 OS-level attribution，因而因果表述限定为“共享路由/输入状态竞争与任务失败相符”，不声称已追踪到每个字节。
- User Actor 当前是 fixed open-loop，正如可复现的一个 scripted operator；不是真人，也不会看页面自主恢复。Shared 干扰是 User 脚本和真实模型 Agent 在同一个 Guest 的 natural co-start 并发造成，没有编码手工动作顺序去强迫某字符误输入。三种 case 都只有一次有效 Shared outcome，还需要重复和自适应 User 策略才能估计稳定性/恢复成本。

### 复现入口

使用 `infra/run_human_agent_novel.sh` 或安全 stdin 包装器，不要把模型密钥放在命令行。例：

```bash
# 路径用实验本机的 RAID 根目录；每次选择全新的 out 目录
infra/run_human_agent_novel.sh --case lab-qc --mode independent \
  --out /mnt/raid1/mjh/Projects/codesk-human-agent-newcases-20261111/lab-qc/repro-01 \
  --model gpt-6-sol --base-url https://docode.cc/v1 --budget 30 --timeout 900 \
  --user-start-trigger simultaneous
```

可用 case key：`consumer-banking`、`lab-qc`、`home-energy`；模式：`user-only`、`agent-only`、`independent`、`shared`、`shared-lock`。所有新的 overlay 和 run 结果继续放 RAID；本轮不提交、不 push、不删除任何历史 run。测试命令：`python -m pytest tests/test_human_actor_new_cases.py`（本轮最后一次 10/10 passed）。
