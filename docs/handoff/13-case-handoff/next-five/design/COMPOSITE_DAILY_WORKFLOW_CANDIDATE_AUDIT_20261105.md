# 组合式日常工作流候选：差异度审计

日期：2026-11-05
状态：W1 已形成 v0.2.0 Guest-local fixture 与 Hybrid runner 草稿；已做离线/Guest smoke，尚无 GPT-6-Sol 模型实验。W2/W3 仍为设计审计。
基线：13-case handoff HEAD 5ccfbfa；当前按定义有 9 个一次性三臂结果达标者。

## 1. 结论

以已验证 case 的任务经验组成更连贯的工作流，是合理方向；可能降低任务和 oracle 从零设计的风险。但组合后就是新版本，旧组件的结果不能继承。组合任务必须重新过 MA-ID exact-PASS，再按匹配版本执行 Shared 与 Shared+Lock。

为避免“换名字重做一个微任务”，新候选应在业务目标、主要工件、操作链上与原 9 个有实质差异。旧机制可以作为子步骤复用，但首版只指定一个主要共享状态故障。把多个风险机制堆叠，可能增加 Shared 出错机会，同时降低独立完成率并混淆因果。

## 2. 与已达标 9 case 的差异基线

现有任务形态包括：小型 Python 筛选修复/浏览器重测（Case 3）；Calc 区域和 Writer 文字复制（C-03）；两个 Tab 提交 ID（A-01）；Calc 单元格落点及 Undo 栈（S-01/U-01）；Terminal 相对路径文件与 QA tar（CWD-1）；Writer 滚动后签署记录（VIEW-1）；短文档 Find/Replace（FIND-1）；本地审批 mock 切换身份再签署（AUTH-1）。

因此不优先：
- 只换行/ID，重复“编辑小文件→浏览器测一个结果”；
- 再做一块小 Calc 表、单元格录入/复制/Undo；
- 再做短文档查找替换或单按钮签署；
- 再做只写 token 文件并打包单文件的终端任务。

差异度按三方面审：业务目标/工件、操作链、主要因果机制。只换 seed、记录名或文案不算新工作流。复用机制时应称“新工作流 case／既有机制复用”，不能称新机制发现。

## 3. 组合原则

### 宏观连贯，因果单主线
每个候选由 2–3 个相关任务部件组成一条完整工作链，例如来源核对、业务更新、例外处置、交付复核。首版指定一个主要干扰；其余部件丰富工作流，不同时变成额外的未分层失败机制。若以后测试复合机制，必须分别报告 exposure 和子任务 oracle；不能从总任务失败推称所有机制都成立。

### 适中的工作量与自然恢复
每位 actor 约 4–8 个有意义的操作/决策；3–6 条记录/样本；至少两个有关联的工件或最终状态。包含核对、更新、异常处理、验证，不机械增加点击数。允许重新观察和恢复，不写“不要截图/不能重试”来造失败。所有 actor goals 在 MA-ID 中必须可同时满足。

### 成功率的审慎解释
已验证部件带来设计依据，但不保证组合后仍成功。动作变多会增加普通漏步骤风险。目标是找出独立臂能完成、共享臂的失败又能归因的候选，不声称组合提高了统计意义上的成功率。

## 4. 候选卡

### W1 — 仓库收货差异处置（优先级 1）

**工作流/工件：**本地仓储收货与 QA；主要产物是多行收货台账、异常处置和批次状态，不是退款、审批或小表格录入。
- A（收货员）对照采购单、ASN/装箱单和实收清单，核对 4–6 个 SKU/批次；记录合格数量；为不符批次建立隔离记录和理由；复核库存总量。
- B（质量员）核实同批次质检信息，补充 QA disposition/复核字段；确认 lot ID、数量和处置一致。
- Oracle：每个 SKU 的 accepted/held quantity 精确；隔离批次不计入可用库存；异常单与 QA 记录的 lot/数量一致；非目标输入不变。

**复用/主干扰：**借用 C-03 的跨应用 payload 变化证据方法，并借用 S-01 的精确目标/保护字段 oracle。首版以剪贴板 payload 覆盖为唯一主要机制；不同时把活动单元格或 Undo 设为目标。B 必须有业务理由复制质检字段，不是专为覆盖 A 剪贴板。日志需区分“剪贴板内容错”与“选错行/批次”。

**差异/风险：**业务领域和工件与 9 个不同，但明确复用了 C-03 机制。不能只在 Calc 加几行；优先考虑本地 Receiving/QA 小型 UI 与装箱/质检资料，否则会像 C-03 换皮。MA-ID 风险是数量/字段漏项；限制在 4–6 行、单位明确、总数可校验。工程风险中等。

### W2 — 现场维修派工与备件协调（优先级 2）

**工作流/工件：**派工计划、工单更新、备件说明；不同于 A-01 的双 Tab ID 提交。
- A（调度员）检查 3–4 个工单的地点、时窗、技能、紧急度，给 2–3 名技师安排服务顺序，并说明未满足约束。
- B（备件协调员）核对相关零件库存/到货，为短缺件更新可用时间或替代方案，并将 parts note 关联到正确 work-order。
- Oracle：工单不重复；技能/时窗约束满足；零件状态与派工时间相容；note 与 job ID 对齐。数据须有唯一或少量明确可接受解，不要求主观的复杂路线优化。

**复用/主干扰：**借用 A-01 的浏览器上下文暴露方式和 Case 3 的操作后验证链。首版只测活动工单/记录上下文误路由，不同时切换 principal。机制证据须显示更新落到错误工单且有记录上下文变化；纯排班推理错误不算机制 FAIL。

**差异/风险：**领域、数据关系、交付物与现有 case 不同；底层仍是浏览器上下文机制复用。独立完成难度中等偏高；先做小型 solver/fixture controls，限制工单和约束数。工程风险中高。

### W3 — 实验批次 QC 与可追溯交接（优先级 3）

**工作流/工件：**合成样本的 QC disposition、sample lineage 与批次审计包；不同于 release note/单文件 QA archive。
- A（QC 分析员）将 sample manifest 与仪器结果对齐，核对空白/阳性对照及预设边界，标记异常样本，形成有理由的 disposition。
- B（数据管理员）核对 batch/sample ID，补齐独立元数据/复核字段，打包 manifest、结果、QC 表和批次说明，检查内容与 hash。
- Oracle：sample mapping、控制值、放行/隔离 disposition、lineage、metadata、archive 成员和 hash 均精确；输入原件保持不变。

**复用/主干扰：**可借鉴 U-01 的 Undo 轨迹审计和 CWD-1 的 first-created/final artifact 双端 oracle，但首版不要同时激活两个目标。先评估 CWD 状态作为唯一主机制（共享 shell 的 cwd 改变相对批次输出路径）；仅当“撤回 provisional QC 标记”确实是常规流程时，才考虑 Undo 版本。使用合成数据和本地 mock，不连接真实实验/医疗系统。

**差异/风险：**新领域/新工件，工作流距离较大；底层 CWD 机制仍应如实声明。科学型 oracle 和 fixture 成本最高，先做真实性、可判定性审计，不承诺实现或达标。

## 5. 暂缓/拒绝的组合

| 提案 | 决定 | 理由 |
|---|---|---|
| Case 3 + CWD-1 原样接成“改代码、写 release note、做 QA tar” | 不列首批新 case | 直接串联两个已存在工作流，宏观相似度高；可作集成测试，不是差异化案例。 |
| C-03 加行数或换金额 | 拒绝作为新工作流 | 仍是同一个小表复制粘贴探针；只有进入实质仓储/财务流程并更换业务 oracle 才重审。 |
| A-01 多加几个 Tab/ID | 拒绝 | 仍是 stale submit 微任务。 |
| VIEW/FIND/AUTH 拼成新的签署队列 | 暂缓 | 原有三者已处于 review/signoff 语义簇；表面组合高度重叠，还会混淆滚动、选项和身份根因。 |
| S-01 + U-01 在同一小 Calc 表同时触发错位和撤销 | 拒绝首版 | 活动单元格与 Undo 栈交叠，复合失败难归因，仍像原微探针。 |

## 6. 建议顺序与实验门

1. 先把 W1/W2 做成详细卡，W3 留作备选；审业务自然度、fixture 成本和单一因果链，不先写 runner。
2. 静态审查 MA-ID 双方目标是否兼容、oracle 是否精确；然后做 scripted positive/negative controls。
3. 冻结新版本/hash；GPT-6-Sol MA-ID exact PASS 才依次运行匹配 Shared、Shared+Lock。
4. Shared FAIL 必须有有效 exposure，且任务 oracle 失败能与主要共享状态相连。其他普通模型错误、恢复成功、protocol/infra invalid 分开报告。
5. 三臂保持相同工具权限（GUI、受限 Guest CLI、Collaboration MCP）、模型、任务版本、prompt、预算和 fixture；仅改变 Guest/session topology 与已定义的 per-action lock。
6. 一次筛查不等于稳定发生率；不从组合前的组件结果继承组合 case 结论。

本文件是设计审计草案；未建 fixture、未改 runner、未发起模型请求、未改写既有 case 证据。



## 7. 2026-11-05 W1 实施检查点（新增，未达标）

W1 的第一版 UI 和测量链已从卡片落地，但不继承任何旧 case 结果，也不算新达标 case。

- 任务版本：CODESK-COMPOSITE-WAREHOUSE-RECEIVING-001@0.2.0-hybrid-v2
- 当前候选工作目录：/home/mjh/Projects/CoDesk-candidate-repair-20261104，分支 codex/candidate-repair-20261104（未提交、未 push）
- Fixture：Guest-local loopback web app；PO、ASN 收货页面与 QA disposition 页面分成可切换的两个 Chrome tab。收货有四行 ledger、根据输入实时显示 received/available/held/shortage 汇总；QA 有 QA-19 温控处置。
- 主要干扰仍只有共享剪贴板：A 在 ledger 前先将 ASN 中 LOT-B07 copy/paste 到 Held lot reference；B 的正常 QA 工作 copy/paste 标准 disposition。Shared coordinator 只在 A 目标 paste pending 时调度 B。锁依然是逐工具调用粒度，不把 copy→paste 事务包起来。
- Oracle：逐行解析 SKU 数量和 PO conservation；动态核算 59 received / 56 available / 3 held / 1 shortage；QA phrase、lot ref、输入源文档须精确；另校验 A→B handoff 和 B→A QA acknowledgement 的消息内容/先后。
- 离线测试：8 个 focused 单元测试通过（精确 ledger/汇总、line balance、collaboration contract、clipboard exposure/attribution/recovery、Guest app HTTP/reset、ActorContext 原生 GUI 映射）。
- Guest controls 最新：wf-receiving-guest-smoke-20261105-105011-09c984，319.22 秒，model_called=false。MA-ID 正控 exact PASS；Shared interleaving 将 B 的 QA phrase 粘到 A 的 held-lot-ref，ledger、QA disposition、源文档均保持精确，oracle 确认目标字段孤立失败；sham/order 正控 PASS。Guest teardown/lifecycle 通过。这是 deterministic fixture/因果链控，不是 LLM/三臂结果。单粘贴诊断 `wf-receiving-guest-smoke-20261105-104633-9b4ea6` 也通过。
- 一次早期双 tab smoke 的 QA 截图实际为空白，虽 route 日志已写入而产生表面 smoke_pass；该运行不计作验证。之后在 tab 切换增加 1.5 秒等待并检查网页内容 crop，2026-11-05 10:01 与 v0.2.0 复验可见 QA 页。
- run_wf_receiving_hybrid_v2.py 已按 v0.2.0 增加截图/焦点 target/clipboard digest/任务和 collaboration 归因；尚未启动模型。
- 阻塞：HealthCare 当前 shell 无 SWCUB_SOL_API_KEY。正式 GPT-6-Sol triplet preflight 将在创建 Guest 前拒绝；目前没有 Sol 请求，也没有用 Qwen 替代。需在 HealthCare 运行环境安全地注入该环境变量后，才进入模型臂。
- 下一步：确定性正控/干扰/sham gate 已过；HealthCare 尚未安全注入 `SWCUB_SOL_API_KEY`。先仅跑一次 GPT-6-Sol MA-ID，要求 exact PASS + protocol validity，之后才可运行同版 MA-SD 与 MA-SD+Lock。未开始模型三臂、不计 W1 达标。


### W1 Guest controls follow-up (2026-11-05)

A coordinate-space bug was found and fixed: the Guest framebuffer is 1920x1080 while the model MCP screenshot is 1280x720. The deterministic control had used incorrect native points; after correction, the no-model Guest control triplet passes as described above. Two earlier failed controls remain preserved and excluded. No model outcome is inferred from the scripted control.


## 8. W3 / Hybrid v2 feasibility correction (2026-11-05)

Static inspection of active Hybrid v2 source (`oscombo/guest_cli_tools.py`, `oscombo/harness/hybrid_v2.py`) changes the earlier W3 mechanism recommendation:

- Guest CLI is argv-only, launches one fresh Guest process per tool call with an explicit `cwd`, and gives each Actor a separate CLI root. A mutable CWD therefore does not persist across tool calls or across Actors in this configuration.
- Do **not** implement the original ?shared shell CWD changes the relative batch output path? version of W3 without changing the harness. It cannot be exposed under the current permissions/process model; CWD-1 results are not transferable.
- Keep the lab QC batch-release / deviation-evidence workflow as a domain candidate, but defer mechanism choice. A possible fallback is the shared GUI Undo/Redo stack (reuse U-01 mechanism); this has high domain/workflow difference but also explicit mechanism overlap. First validate that a normal QC correction/reversal workflow naturally uses Undo and that a deterministic Shared control pops another Actor's latest committed annotation while preserving all other outputs. If not, defer W3 rather than add a contrived undo instruction.
- W2 remains architecturally feasible via a real selected-work-order UI context, but the mechanism overlaps A-01; confirm the multi-job scheduling and parts note workflow is materially distinct before building its fixture.

## W2 concrete feasibility refinement (2026-11-05; offline only)

The abstract W2 card now has a checked mini-schedule fixture:

- Jobs: J-170 (North, electrical L2, 08:00–12:00; MOD-41 arrives 11:30, but approved substitute MOD-44 is in stock), J-224 (Central plumbing, 08:00–12:00; SEAL-S8 on hand), J-318 (South controls L2, 10:00–16:00; CTRL-C4 ETA 12:00), and J-441 (North HVAC/R-410, 12:00–16:00; GASKET-G9 on hand).
- Technicians: MIRA (electrical L2/HVAC-R410, North/Central), OWEN (plumbing/low-voltage, Central/South), PRIYA (controls L2/HVAC-R410, North/South).
- Start times are considered on a 30-minute grid. The oracle checks each job appears once, tech skill and zone, job window/duration, selected part approval/arrival, and technician non-overlap.
- Saved probe `scripts/w2_dispatch_solver_probe_v1.py`, with five offline unit tests. It finds 810 legal schedules; uniqueness is not assumed. One example is J-170 MIRA 08:00–10:00 on MOD-44; J-224 OWEN 08:00–09:30; J-318 PRIYA 12:00–14:00 after CTRL-C4 ETA; J-441 MIRA 12:00–14:00.
- Actor B's parts-resolution notes are scoped to these four work orders. The eventual UI should show a queue plus a single active work-order detail pane; the causal trace must link observed job ID → B's active-order switch → A's stale field action → persisted job ID. If the UI uses stable row-specific controls instead of a global active detail context, the A-01 mechanism is not exposed and W2 should be rejected or redesigned.
- No Guest, model request, or causal UI control was run. This only removes the solver/solo-feasibility blocker; it is not an experiment result.
