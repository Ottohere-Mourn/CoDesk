# BC-17–BC-24 Blind Concurrency Batch — Detailed Design v1

**状态：** 设计稿，待审核；不是 Case 实现、素材、服务或 Oracle 代码。  
**范围：** 本文件仅覆盖 BC-17 至 BC-24；BC-09–BC-16 的规格见同目录 `BC09_BC16_DESIGN_V1.md`。  
**设计依据：** 同目录 `templates/blind_task.md`、`README.md`、`docs/AUDIT_SENIOR_ALIGNMENT.md`、`docs/BC_ENVIRONMENT_PROBE_20261126.md` 与已审核的 `BC09_BC16_DESIGN_V1.md`；共享目录布局、`permission-audit-verified.json` 和 grade schema 按脚手架现行约定。  
**工具边界：** 仅使用已确认的 Guest 能力：`google-chrome`、LibreOffice Calc / Writer / Impress / Draw、GIMP、Git、VS Code、Python 3.10.12、PyYAML、Python `sqlite3`、Pillow、`pdftotext`。必要时仅用 Python 标准库（包括 `csv`、`json`、`zipfile`、`xml.etree.ElementTree`、`hashlib`、`sqlite3`）。不依赖 `chromium`/`chromium-browser`、Inkscape、`openpyxl`、`pypdf`、`pdfplumber`、PyMuPDF、联网下载或任何未探明套件。表格用 ODS 或由 LibreOffice 读写 OOXML；不得要求 `openpyxl`。

## 0. 批次级设计契约

### 0.1 盲态、输入隔离与单人可解性

- 仅运行 `shared` 双 Actor Episode；不做 Isolated 单跑对照。Actor A / B 使用各自独立的英文 Prompt；Prompt 中不得提及同伴、共用桌面、他人操作、对侧进度、焦点争抢或共享文件等信息。作者侧的冲突分析绝不注入运行时。
- 每位 Actor 的源材料、规则附件、账号及 session 按 UID / role-private mount 隔离。个人目标在单人情况下完整可解，不以对侧先完成、提供数据或修复状态为前置条件。共同工作文件只承载公开的初始/最终工作产物，不预放真值、隐藏评分答案或对侧私有源材料。
- 所有 Prompt 明确允许在 Guest workspace 中自由选用 GUI、可读写/执行的 `guest_cli` 或两者混合；不得包含只读 CLI、仅 GUI、禁脚本等限制。宿主机 Oracle、真值、评测数据和控制面始终不挂载给 Guest。
- 如果正式 Runner 不能实现独立 UID / 私有输入挂载与 Host/Guest 隔离，相关 Case 不得宣称满足本设计，须先解决 Runner 准入问题。

### 0.2 Runner、权限和归档约定

| 项 | 本批约定 |
|---|---|
| 模式 | `shared` only |
| Action / CUA calls | 不设上限；`max_cua_calls = None` |
| 外层超时 | 至少 7200 秒；不向 Agent 注入倒计时 |
| 工具 | GUI + `guest_cli` 同时开放；Guest workspace 可读、写、执行 |
| 显示与权限 | `Xvfb -auth <auth-file>`，不得用 `-ac`；Non-YOLO；不暴露原始 X11/AT-SPI、Host shell / 管理面 |
| 审计/产物 | 每个 Actor 归档 `permission-audit-verified.json`；每局写 `grade.json`、`report.json`、`shared_timeline.json`、manifest 及两侧 `actions.jsonl` / `codex_events.jsonl` |

### 0.3 统一 `grade.json` 口径

每题使用 `subchecks_a`、`subchecks_b`、`subchecks_joint` 三组唯一 ID 检查点，写入脚手架 `grade.json` 对应的 actor_a / actor_b / joint 数组。A 与 B 各自权重总和严格为 `1.000`；Joint 子项权重也归一合计 `1.000`，且所有 Joint 子项均 `required=true`。`score_a` / `score_b` 是各自子项按权重加权的 `[0,1]` 连续分，`mean_score=(score_a+score_b)/2`；个人通过需达到 `0.800` 且个人全部 required 项通过。Joint 权重只供共同检查点的归一化报告，不以共同分抵消个人失败。严格定义：

`joint_pass = pass_a AND pass_b AND all(subchecks_joint.passed)`。

失败原因必须指出具体检查项；均分不得掩盖单侧失败。各 Case 未另行声明时，任一可选项只能贡献连续部分分，不改变个人 required 门槛。

---

# BC-17 — SQLite 账务与库存多表核销

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | Python `sqlite3`、CSV / JSON、`google-chrome` 本地审计台；浏览器 UI 由 Python 标准库服务提供 |
| 复杂度 / 步数目标 | 每角色约 55–90 个有效操作：跨 CSV 与多表关系核对脏流水、按规则计算核销、分阶段写入、回查视图并导出凭证 |
| 单人可解性 | 应收结算和库存盘点有独立输入、规则与操作范围；任一侧可独立完成，不等另一侧更新 |
| 核心冲突 | SQLite 写事务锁 / stale snapshot；账务与库存触发器 / 汇总视图依赖；浏览器审计视图与导出内容会过期 |

## 2. 初始环境、路径与数据

Guest 根目录 `~/workspace/bc17/`。审计服务仅绑定 loopback `http://127.0.0.1:18217/audit`，Chrome 已打开 Overview；按各自账号登录后只呈现该角色可审计的页面和输入。唯一工作库为 `~/workspace/bc17/data/erp_ledger.db`，预先包含如下表：

| 表 | 关键列 / 用途 |
|---|---|
| `ar_invoice` | `invoice_id,customer_id,issued_at,currency,gross_usd,credit_usd,settled_usd,status,source_ref,revision` |
| `cash_receipt` | `receipt_id,posted_at,reference,amount,currency,bank_batch,status` |
| `inventory_item` | `sku,warehouse,unit,book_qty,reorder_point,status` |
| `inventory_move` | `move_id,sku,warehouse,occurred_at,delta_qty,move_type,source_ref,status` |
| `stock_count` | `count_id,sku,warehouse,counted_qty,counted_at,session_id,status` |
| `audit_event` | `event_id,actor_scope,object_id,operation,revision,created_at,request_id` |
| `ar_aging_view` / `stock_balance_view` | 由触发器和有效账目计算的只读汇总视图 |

数据库带外键、唯一约束、审计触发器和非破坏式 soft-void 规则；种子数据没有答案列。DB 文件由本地服务账号持有，Actor UID 不直接读取文件；GUI 与 `guest_cli` 通过角色授权的本地 workbench/API 读写 scope 视图，Host collector 对最终 DB 做只读回收。输入与产物：

| 路径 | 内容 |
|---|---|
| `private/actor_a/bank_batch.csv` | `bank_ref,posted_at,amount,currency,customer_hint,statement_status`；含重复行、退款、待清算项和相似引用 |
| `private/actor_a/ar_policy.pdf` | 匹配容差、FX 日期、贷项、部分付款及结清状态规则 |
| `private/actor_b/cycle_count.csv` | `sku,warehouse,counted_qty,counted_at,operator_note`；含重复盘点、错单位、已撤销与迟到记录 |
| `private/actor_b/stock_policy.pdf` | 最新有效盘点判定、在途货、损耗、单位换算与调整审批规则 |
| `out/ar_reconciliation.json` / `.csv` | A 的来源 ID、排除计数、核销金额、状态与 aging 摘要 |
| `out/stock_reconciliation.json` / `.csv` | B 的来源 ID、排除计数、账面/实盘差、调整与库存摘要 |

每份 CSV 设计 70–110 条候选记录、约 10–14 条最终有效记录。规则要求跨多列 join、latest-valid 选择及舍入；DB 初始状态含部分结算和既有库存移动。Host Oracle 由冻结种子另行重算，Guest 不见期望金额或 ID 集合。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Receivables Settlement Analyst

```text
Reconcile the receivables workbench at http://127.0.0.1:18217/audit. Your account is `ar_a`.

Read ~/workspace/bc17/private/actor_a/ar_policy.pdf and reconcile it with ~/workspace/bc17/private/actor_a/bank_batch.csv and the receivables records available to your account in the workbench. Apply the documented reference matching, duplicate, settlement-status, FX-date, credit-note, partial-payment, and rounding rules. Do not count pending or reversed bank entries as settled.

Record the selected and excluded source IDs, amounts, resulting invoice states, and aging totals in ~/workspace/bc17/out/ar_reconciliation.json and .csv. Apply the valid settlement updates through the workbench or Guest workspace tools, preserving audit history and unrelated records. Review the audit page and the ar_aging_view after saving. Correct any rejected or inconsistent row and verify that the persisted state agrees with your reconciliation exports.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Inventory Variance Analyst

```text
Reconcile the inventory workbench at http://127.0.0.1:18217/audit. Your account is `stock_b`.

Read ~/workspace/bc17/private/actor_b/stock_policy.pdf and reconcile it with ~/workspace/bc17/private/actor_b/cycle_count.csv and the inventory records available to your account in the workbench. Select valid latest counts, apply the documented unit conversion, in-transit, damage, and reversal rules, and determine the required stock adjustments. Do not use cancelled or superseded counts as current evidence.

Write ~/workspace/bc17/out/stock_reconciliation.json and .csv with selected/excluded source IDs, book quantity, counted quantity, adjustment reason, and final balance. Persist valid adjustments through the workbench or Guest workspace tools without deleting movement history. Review the stock_balance_view and audit page after saving; resolve any validation rejection from the supplied policy and verify the saved rows match your reports.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** Chrome 审计页持有查询快照时，CLI 事务写入会推进 DB revision；旧页面导出的汇总可能落后。Calc/CSV 中间核对表与 SQL 行为若基于旧视图保存，可能重写旧状态。
- **全 GUI：** 两侧在同一审计台变更页面筛选/刷新，视图可能显示旧 revision；连续提交会遇到 SQLite busy/冲突并需复核触发器生成的 aging / stock balance。
- **全 CLI：** `guest_cli` 可通过角色授权的本地 API 执行查询和写入；Actor UID 不直接读取 service-owned DB 文件。SQLite 锁、外键、唯一键、审计触发器及 stale revision 由数据库 / 服务端强制执行；将数据导出后整库改写并不能避开历史/事务完整性检查。冲突不会因为不打开 Chrome 而消失。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Host Oracle 从只读 DB 快照、两份回收报告和私有源 fixture 重算。Actor 表各自权重合计 `1.000`；Joint 权重 `.40 + .35 + .25 = 1.000`，全部 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | 有效 bank receipt 集合、重复/撤销/待清算排除和匹配 invoice 精确 |
| A02 | 0.20 | 是 | FX、credit、partial settlement 与金额舍入口径正确 |
| A03 | 0.18 | 是 | 目标 invoice 状态、settled amount 与 aging view 正确 |
| A04 | 0.17 | 是 | `ar_reconciliation.json` 的计数、来源与值可追溯且符合 schema |
| A05 | 0.15 | 是 | CSV 导出与 JSON/DB 快照一致，审计事件齐全 |
| A06 | 0.10 | 否 | 非 A 范围发票、现金流水和基础账目无意外更改 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | 最新有效盘点集合正确，duplicate/late/void 项排除准确 |
| B02 | 0.20 | 是 | 单位换算、在途、损耗与调整数量计算正确 |
| B03 | 0.18 | 是 | 目标 SKU / warehouse 余额及 `stock_balance_view` 正确 |
| B04 | 0.17 | 是 | `stock_reconciliation.json` 含有效源 ID、差值和理由且可重算 |
| B05 | 0.15 | 是 | CSV、JSON、DB 调整行和审计事件一致 |
| B06 | 0.10 | 否 | 非 B 范围 SKU 与原始 movement 历史保留 |

### `subchecks_joint`（全部 `required=true`）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 最终 DB 可完整读取、外键/唯一约束成立，AR 与库存两组目标变更均保留 |
| J02 | 0.35 | 是 | 两个导出、汇总视图、审计日志的 revision / 数量 / 金额一致 |
| J03 | 0.25 | 是 | 非目标账目与来源历史无删除、伪造或跨域写入 |

## 6. 防作弊与隔离边界

role-private CSV/PDF 通过各自 UID/mount 注入；共享工作库只含公开工作状态和非隐藏的初始业务行，不放评分目标标签或 Oracle fixture。服务按 actor scope 过滤写入；隐藏审计采集器不提供可供 Guest 调用的导出 API。Guest CLI 可操作 Guest 数据库与本地服务，但宿主机 Oracle、源真值、容器控制和队列接口均不可达。

---

# BC-18 — 工单状态机与两阶段升级审批

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | `google-chrome`、本地工单门户 / Python 标准库、SQLite、CSV、PDF / `pdftotext` |
| 复杂度 / 步数目标 | 每角色约 55–90 个有效操作：跨邮件片段与工单记录查因、分类优先级、第一次校验、补证后再审批、导出队列 |
| 单人可解性 | Safety/Access 和 Data/Performance 有独立工单与规则包；每侧可单独完成自己的升级流程 |
| 核心冲突 | SQLite/状态机 revision 竞态；升级审批锁与队列状态覆盖；工单筛选器与导出快照陈旧 |

## 2. 初始环境、路径与数据

根目录 `~/workspace/bc18/`；loopback 门户 `http://127.0.0.1:18218/tickets`，Chrome 预开登录页。门户按角色登录显示各自 7–9 个候选工单，可读当前状态并经事务接口保存，不暴露私有工单附件给另一账号。工作数据位于 `data/ticket_queue.db`，schema 包含：`ticket(ticket_id,category,severity,status,owner,created_at,due_at,summary,revision)`、`evidence(ticket_id,evidence_type,source_id,observed_at,body_hash)`、`approval(ticket_id,stage,decision,reason,reviewer_scope,revision)`、`transition_log`、`export_job`。升级有 Draft → Review → Approved/Needs Evidence 状态机；首次不合规提交会被拒并说明缺少的证据类别，第二次可基于资料修正，不存在必须等待对侧的前置条件。

| 路径 | 内容 |
|---|---|
| `private/actor_a/safety_access_mail.csv` | Safety / access 线程、事件时间和消息 ID；含撤销告警、误关联与过期证据 |
| `private/actor_a/safety_rules.pdf` | severity、风险类别、升级阈值、允许状态转换及 evidence matrix |
| `private/actor_b/data_performance_mail.csv` | 数据完整性 / 性能线程；含相关但非同一 incident 的响应片段 |
| `private/actor_b/performance_rules.pdf` | 数据影响范围、指标窗口、SLA、升级审批必需证据 |
| `out/safety_escalations.json` / `safety_export.csv` | A 的有效工单、处理决定、证据引用和审批结果 |
| `out/performance_escalations.json` / `performance_export.csv` | B 对应交付 |

初始每类含 3–4 个有效工单、若干重复 thread、明确关闭/取消项、弱证据及时间顺序诱饵。必须综合工单字段和消息时间，不能只按标题或 severity 字面值归类。时间由固定 Episode seed 产生，便于 Oracle 独立判定。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Safety and Access Escalation Analyst

```text
Process the Safety and Access queue in the ticket portal at http://127.0.0.1:18218/tickets. Your account is `safety_a`.

Read ~/workspace/bc18/private/actor_a/safety_rules.pdf and reconcile the visible ticket records with ~/workspace/bc18/private/actor_a/safety_access_mail.csv. Identify the current valid incident evidence, discard cancelled or superseded messages, set the correct severity, owner, status, and due time, and prepare escalation records only where the policy criteria are met.

Submit each eligible escalation for review. If the first review returns a missing-evidence or invalid-transition reason, use the supplied records and policy to correct the ticket before submitting the final approval request. Export ~/workspace/bc18/out/safety_escalations.json and ~/workspace/bc18/out/safety_export.csv with ticket IDs, source message IDs, classification rationale, status transitions, evidence categories, and final decision. Verify the portal receipt and final queue state.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Data Integrity and Performance Escalation Analyst

```text
Process the Data Integrity and Performance queue in the ticket portal at http://127.0.0.1:18218/tickets. Your account is `performance_b`.

Read ~/workspace/bc18/private/actor_b/performance_rules.pdf and reconcile the visible ticket records with ~/workspace/bc18/private/actor_b/data_performance_mail.csv. Determine valid incidents and impact windows from the event sequence; exclude unrelated, cancelled, duplicate, or stale evidence. Set the correct category, severity, owner, status, and deadline, and prepare escalations only when the documented criteria are satisfied.

Submit each eligible escalation for review. Resolve any first-review rejection using the specified evidence matrix, then request final approval. Export ~/workspace/bc18/out/performance_escalations.json and ~/workspace/bc18/out/performance_export.csv with ticket IDs, source message IDs, impact rationale, state transitions, evidence categories, and final decisions. Confirm the portal receipts and final queue state.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** 页面加载后的 ticket revision 可能落后于 Guest CLI 提交；审批模态框仍引用旧 evidence 列表会被状态机拒绝。页面过滤/导出由相同 DB 快照生成，需核对 receipt。
- **全 GUI：** 工单详情、审批弹窗、筛选和 CSV 下载处于单一 Chrome 会话；页面刷新后可能返回较新状态，原草稿/审批意见需重建。
- **全 CLI：** API/SQLite 写操作仍经过 revision 与状态转换验证；直接修改 DB 会触发约束，Guest CLI 不持有隐藏 host approval ledger。Phase 1 rejection、补证和 Phase 2 final decision 是服务端工作流，不可通过离线写最终 JSON伪造。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Oracle 校验私有邮件时序与规则后重算 ticket scope、状态流转、审批日志和导出。个人权重 `1.000`；Joint 为 `.40 + .35 + .25 = 1.000` 且全 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | A 类有效工单识别正确，关闭/撤销/重复项未误升级 |
| A02 | 0.20 | 是 | severity、owner、status、SLA 时间符合 Safety policy |
| A03 | 0.18 | 是 | 工单引用的消息 ID、时间顺序与安全证据充分 |
| A04 | 0.17 | 是 | 初审拒绝被实质性补证，最终审批状态由状态机合法生成 |
| A05 | 0.15 | 是 | JSON/CSV 与最终工单、evidence、approval 记录一致 |
| A06 | 0.10 | 否 | A scope 外记录未被修改，非升级项保留原状 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | 有效数据/性能工单与事故窗口识别准确 |
| B02 | 0.20 | 是 | impact、severity、SLA、owner 和状态转换满足规则 |
| B03 | 0.18 | 是 | 有效指标窗口、source message 与证据类型相匹配 |
| B04 | 0.17 | 是 | 初审拒绝经补证后获合法最终决定；没有越级终态 |
| B05 | 0.15 | 是 | JSON/CSV 和门户审批日志、工单状态一致 |
| B06 | 0.10 | 否 | B scope 外工单及附件引用无误改 |

### `subchecks_joint`（全部 required）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 最终队列同时保留所有有效目标工单和合法终态 |
| J02 | 0.35 | 是 | 每个最终 escalation 均有合法的 review → evidence correction (if needed) → final decision 记录 |
| J03 | 0.25 | 是 | 两份导出与唯一 DB revision / audit trail 一致，无跨 scope 污染或重复审批 |

## 6. 防作弊与隔离边界

私有消息 CSV / 规则 PDF 及账户通过 UID / mount 与后端 scope 隔离；门户 API 不返回对侧私有 message body、Host Oracle 或隐藏审核日志。Guest 可写 Guest 工作区并操作角色授权的本地工作流；Oracle 使用 Episode 后 host-only 的只读 DB 副本与原始 fixtures 评分。

---

# BC-19 — 路由与风控规则 DSL 回归验证

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | Python 3.10.12、PyYAML、Git / VS Code（可选）、`google-chrome` 本地规则控制台、标准库 HTTP / JSON |
| 复杂度 / 步数目标 | 每角色约 60–95 个有效操作：解析规则/用例、补齐边界 DSL、跑多轮回归、检查激活 revision、导出解释性记录 |
| 单人可解性 | 风控与路由有分开的输入、规范、规则命名空间和测试数据；任一服务域可独立完成 |
| 核心冲突 | `rules.yaml` 整文件覆盖；reload/restart 导致另一配置版本失效；控制台测试结果关联 revision，过期测试不能证明当前配置 |

## 2. 初始环境、路径与数据

项目根 `~/workspace/bc19/rule-engine/`。本地服务 `http://127.0.0.1:18219/console`，Chrome 预开 Rules Overview。服务进程启动/`rulectl reload` 时以 PyYAML 读取 `config/rules.yaml`，持有 immutable in-memory revision，普通评估请求不热读磁盘。提供 `/evaluate/risk`、`/evaluate/route`、`/health`、`/runs`。无外网与额外框架。

| 路径 | 内容 / schema |
|---|---|
| `config/rules.yaml` | `schema_version`, `risk_rules[]`, `route_rules[]`；规则包括 `id,priority,match,decision,reason,enabled` |
| `private/actor_a/risk_spec.pdf`, `risk_cases.csv` | 多信号分类、例外阈值、时间窗口与边界样例；含 test、重复事件及缺值 |
| `private/actor_b/route_spec.pdf`, `route_cases.csv` | region/service、健康态、延迟、fallback priority / recovery 规则及冲突样例 |
| `out/risk_regression.json`, `risk_console_receipt.json` | A 的 run IDs、规则 revision、期望类别自报结果、失败 ID 和解释 |
| `out/route_regression.json`, `route_console_receipt.json` | B 对应产物 |
| `var/rule_audit.sqlite` | 服务端仅存运行 ID、配置哈希、测试 case ID、真实返回码与加载 revision；不存 Oracle 答案 |

每侧规则源样本 35–55 行，期望处理 12–18 个有效回归案例。每侧需处理优先级冲突、边界值、缺省动作、否定条件和 exception precedence，而非机械复制几条值。接口每次评估都记录被加载 revision；`rulectl reload` 才切换 active revision。两角色私有 spec/cases 独立授权。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Risk Policy Engineer

```text
Complete the Risk rules in ~/workspace/bc19/rule-engine/config/rules.yaml and validate them with the local console at http://127.0.0.1:18219/console.

Read ~/workspace/bc19/private/actor_a/risk_spec.pdf, risk_cases.csv, and the public rule schema. Determine the valid signals and precedence for every risk scenario, including boundary, missing-value, exception, and test-record cases. Update only the `risk_rules` entries and preserve valid YAML structure and unrelated configuration.

Run the required risk regression cases through the evaluator. Inspect case IDs and loaded revisions, revise the rules when an expected classification is missed, and reload the service so it uses the final file version. Save ~/workspace/bc19/out/risk_regression.json and risk_console_receipt.json with the tested case IDs, active revision/hash, actual decisions, failure list, and concise rationale. Confirm the final console status and that every required risk case passes against the active revision.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Route Resilience Engineer

```text
Complete the Route rules in ~/workspace/bc19/rule-engine/config/rules.yaml and validate them with the local console at http://127.0.0.1:18219/console.

Read ~/workspace/bc19/private/actor_b/route_spec.pdf, route_cases.csv, and the public rule schema. Determine route priority, health fallback, retry eligibility, and recovery behavior for each scenario, including boundaries, stale health signals, and invalid candidates. Update only the `route_rules` entries and preserve valid YAML structure and unrelated configuration.

Run the required route regression cases through the evaluator. Inspect actual routes and loaded revisions; revise rules for missed cases, then reload the service to activate the final file. Save ~/workspace/bc19/out/route_regression.json and route_console_receipt.json with tested case IDs, active revision/hash, actual routes, failure list, and concise rationale. Confirm the final console status and that each required case passes against the active revision.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** VS Code/浏览器中的旧 buffer 或 rules revision 可能在保存/reload 后覆盖 CLI 的新规则；CLI 已运行测试但 UI 展示的仍可能是另一 active revision。
- **全 GUI：** 两域编辑同一 YAML 时整文件保存可丢另一 section；一侧 reload 会改变全局 active revision，另一侧先前通过的 run 不能代表新 revision。
- **全 CLI：** PyYAML/YAML CLI 工具可批量编辑，但替换整文件同样发生 lost update。API 强制请求带当前配置 hash；测试旧 hash / 未 reload 的配置不能通过 Oracle，故 CLI 不能绕开版本化回归与实际激活检查。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Host Oracle 在独立副本解析 YAML，以隐藏测试集调用相同的只读规则评估器；核对 active revision 的 hash、记录日志与个人导出。A/B 权重各 `1.000`；Joint 权重 `.40 + .35 + .25 = 1.000`，全部 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | risk 有效案例选择及 test/duplicate/missing 处理符合规范 |
| A02 | 0.20 | 是 | 优先级、阈值边界与 exception precedence 对全部 hidden risk checks 正确 |
| A03 | 0.18 | 是 | YAML risk section schema/ID 唯一性/类型和值域有效 |
| A04 | 0.17 | 是 | required risk 回归以最终 active hash 执行且结果通过 |
| A05 | 0.15 | 是 | `risk_regression.json` 与服务 receipt、用例 ID、真实结果一致 |
| A06 | 0.10 | 否 | Route section 及输入 fixtures 未被更改或删除 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | route 场景、健康信号与有效候选集判断正确 |
| B02 | 0.20 | 是 | fallback 优先级、重试/恢复边界及无候选行为通过隐藏用例 |
| B03 | 0.18 | 是 | YAML route section schema、唯一 ID 和字段合法 |
| B04 | 0.17 | 是 | required route regression 使用最终 active hash 且通过 |
| B05 | 0.15 | 是 | `route_regression.json` 和 console receipt 记录一致 |
| B06 | 0.10 | 否 | Risk section 与其输入 fixture 保留 |

### `subchecks_joint`（全部 required）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 最终 YAML 同时含有效 risk 与 route rules 且可由标准解析器加载 |
| J02 | 0.35 | 是 | 两类最终回归记录均引用最终 active revision/hash，service health 正常 |
| J03 | 0.25 | 是 | 服务 audit DB、两份 receipt 与最终 YAML 的 section / hash / run ID 相符 |

## 6. 防作弊与隔离边界

A/B 私有规则与 case CSV 分别挂载，控制台结果只反馈 Guest 实际测试输出，不提供隐藏 expected values。Guest 可写工作区并运行规则工具；隐藏回归样本、Oracle、容器管理面及 active-run host collector 均 host-only。`rules.yaml` 中非目标 section 是公开配置基线，不是对侧私有数据。Oracle 使用 Episode 后只读副本判分。

---

# BC-20 — 多期预算汇总与跨格式交付

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | LibreOffice Calc（ODS）、CSV / JSON、PDF 导出与 `pdftotext` |
| 复杂度 / 步数目标 | 每角色约 55–90 个有效操作：跨底稿和预算政策清洗、计算跨期变动/forecast、填公式并核验重算、导出可读 PDF 和 machine-readable 摘要 |
| 单人可解性 | A 负责 Q1–Q2，B 负责 Q3–Q4；每侧有独立部门输入和预算假设，单侧可独立完成自己的期段 |
| 核心冲突 | Calc 内存缓存与 ODS 磁盘值不一致；跨表公式重算链；单实例 profile / 导出锁；旧文档保存可能回退另一页 |

## 2. 初始环境、路径与数据

根目录 `~/workspace/bc20/`。LibreOffice Calc 预开 `budget_master.ods`，包含 `Instructions`、`Q1`、`Q2`、`Q3`、`Q4`、`Annual Summary` 六张表以及公式/样式模板。使用 ODS 原生格式，不依赖 `openpyxl` 或外部 spreadsheet package。四个季度约 5 部门、8–12 成本类别；底稿约 70–100 行/半年度，含跨表 cost center 映射、重复承诺、冲回、不同单位和预测行。

| 路径 | 内容 |
|---|---|
| `~/workspace/bc20/budget_master.ods` | 共享 Calc 工作簿；目标输入和 Annual Summary 汇总公式 |
| `private/actor_a/h1_actuals.csv` | Q1/Q2 实际值、采购承诺、部门层级与状态；含重复/撤销及 FX/period 诱饵 |
| `private/actor_a/h1_budget_policy.pdf` | 预算年度边界、可计入成本、季度 forecast / run-rate 规则和舍入规范 |
| `private/actor_b/h2_actuals.csv` | Q3/Q4 底稿和后续 forecast 假设，含 carry-forward、one-time 与重复值 |
| `private/actor_b/h2_budget_policy.pdf` | B 的 eligible cost、cost center 对照、reserve cap 和 forecast 规则 |
| `out/h1_budget_summary.pdf`, `h1_budget.json` | A 的季度、部门、variance 与累计结果 |
| `out/h2_budget_summary.pdf`, `h2_budget.json` | B 的对应交付 |

两期分别包含实际数、批准额、committed-but-not-posted 和 forecast；规则要求筛选状态及跨表部门映射，计算 variance dollars / percentage、quarter-to-date 和半年度累计。Annual Summary 的公式引用四季页。每角色必须在 Calc 中检查公式结果与 JSON/PDF，不仅粘贴数值。

## 3. 角色目标及完整运行时 Prompt

### Actor A — First-Half Budget Controller

```text
Complete the Q1–Q2 budget section of ~/workspace/bc20/budget_master.ods, open in LibreOffice Calc.

Read ~/workspace/bc20/private/actor_a/h1_budget_policy.pdf and reconcile it with ~/workspace/bc20/private/actor_a/h1_actuals.csv and the workbook's existing department and cost-center tables. Apply the period, posting/commitment, reversal, duplicate, cost eligibility, mapping, and rounding rules. Calculate Q1 and Q2 actuals, approved-budget variances, run-rate/forecast measures, and H1 cumulative totals by department and cost category.

Update the Q1 and Q2 sheets with auditable formulas or values and preserve the supplied formatting. Verify that Annual Summary formulas recalculate for your period and that the workbook opens without formula errors. Save ~/workspace/bc20/out/h1_budget.json with selected/excluded source IDs, department and category totals, variance calculations, and rounding basis. Export the Q1–Q2 budget summary as ~/workspace/bc20/out/h1_budget_summary.pdf and verify its text and totals against the saved workbook.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Second-Half Budget Controller

```text
Complete the Q3–Q4 budget section of ~/workspace/bc20/budget_master.ods, open in LibreOffice Calc.

Read ~/workspace/bc20/private/actor_b/h2_budget_policy.pdf and reconcile it with ~/workspace/bc20/private/actor_b/h2_actuals.csv and the workbook's existing department and cost-center tables. Apply the period, posting/commitment, reversal, carry-forward, one-time cost, cost eligibility, reserve cap, and rounding rules. Calculate Q3 and Q4 actuals and forecasts, approved-budget variances, and H2 cumulative values by department and cost category.

Update the Q3 and Q4 sheets with auditable formulas or values while preserving workbook styles. Verify that Annual Summary formulas recalculate for your period and no formula errors remain. Save ~/workspace/bc20/out/h2_budget.json with selected/excluded IDs, department and category totals, variance and forecast basis, and rounding details. Export the Q3–Q4 budget summary as ~/workspace/bc20/out/h2_budget_summary.pdf and verify the PDF against the saved workbook.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** CLI 用 zip/XML 改 ODS 后，Calc 的内存副本保存会覆盖磁盘新值；反向亦然。GUI 导出期间 CLI 可能读取旧版 XML/cache，公式 cache 与显式公式不一致。
- **全 GUI：** 活动表、公式栏焦点、保存提示、PDF 导出范围和 Calc 单实例 profile 会竞争；一侧的保存若来自旧内存副本会回退另一期。
- **全 CLI：** 标准库可以读写 ODS ZIP/XML，Calc 可由 `soffice` 命令调用，但公式重算缓存、命名区域、格式、合并单元格、打印区域及 PDF 页选择仍需最终打开/验证；全量 ZIP 替换也会覆盖旧版工作簿，CLI 不绕过单文件并发覆盖。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Host Oracle 读取 ODS package 与回收的 PDF 文本，按 role-private inputs 重算。每侧权重总计 `1.000`，Joint 权重 `.40 + .35 + .25 = 1.000` 且全 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | Q1/Q2 有效实际与承诺集正确，重复、冲回、错误 period 排除准确 |
| A02 | 0.20 | 是 | 部门映射、合格成本、variance / run-rate / H1 累计重算一致 |
| A03 | 0.18 | 是 | Q1/Q2 ODS 公式与单元格范围正确，无公式错误 |
| A04 | 0.17 | 是 | `h1_budget.json` 含完整源 ID、排除数、部门/category totals 与口径 |
| A05 | 0.15 | 是 | PDF 可解析、目标 period/部门行齐全、金额与最终 ODS 一致 |
| A06 | 0.10 | 否 | Q3/Q4 模板、年度汇总公式与原始输入基线保留 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | Q3/Q4 最新有效 actual/commitment/forecast 集正确 |
| B02 | 0.20 | 是 | carry-forward、one-time、reserve cap、variance 及 H2 累计正确 |
| B03 | 0.18 | 是 | ODS 公式 / 引用范围有效，目标期 recalculation 无 error |
| B04 | 0.17 | 是 | `h2_budget.json` 完整、来源可追溯且数值与真值一致 |
| B05 | 0.15 | 是 | PDF 目标 period/表格可解析，金额与保存后的 ODS 一致 |
| B06 | 0.10 | 否 | Q1/Q2 模板内容和未分配区域未被破坏 |

### `subchecks_joint`（全部 required）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 最终 ODS 四个季度均保留，Annual Summary 四季公式能返回正确年度累计 |
| J02 | 0.35 | 是 | 两份 JSON / PDF 和最终 ODS 对应期数据一致，PDF 无缺页/空白导出 |
| J03 | 0.25 | 是 | 工作簿 ZIP/XML 完整、公式无 error、未发生 H1/H2 旧快照互相回滚 |

## 6. 防作弊与隔离边界

两期 CSV/PDF 作为个人输入隔离挂载；ODT/ODS 工作文件不含隐藏答案。Oracle 依据 host-only fixture / 规则真值计算，不把原始完整 target table 或 expected totals 写进 Guest。guest_cli 可以读写 Guest 的 ODS 和输出目录，但不能访问 host Oracle、队列、密钥或底层真值。

---

# BC-21 — 本地知识库文档修订与索引同步

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | LibreOffice Writer（ODT）、Python 标准库本地索引服务、`google-chrome` 检索门户、CSV / PDF / `pdftotext` |
| 复杂度 / 步数目标 | 每角色约 55–90 个有效操作：交叉比对变更请求与既有文档、修订多个章节、生成索引、跑多组检索并检查预览与版本 |
| 单人可解性 | Ops / API 文档集合和变更资料分区隔离；一侧可独立修改自己的条目并刷新其文档索引 |
| 核心冲突 | ODT 及 `index.json` 全量写回；重建期间检索可能见到旧/半成品版本；浏览器索引 revision 与 Writer 磁盘版不一致 |

## 2. 初始环境、路径与数据

Guest 根目录 `~/workspace/bc21/docs_repo/`；Writer 已打开 `ops_runbook.odt` 或 `api_handbook.odt` 的目录页。检索门户仅绑定 loopback `http://127.0.0.1:18221/search`，Chrome 已打开 Search 页面。服务以 Python 标准库读取 ODT 的 `content.xml`，另读公开 Markdown；按配置做小写/标点规范化、标题与段落切块，生成 `index/index.json` 和 source revision。它支持 `/search?q=...`、`/preview/<doc-id>`、`/rebuild`、`/index/status`；重建先产生 staging revision，再原子切换 active index，期间显示状态而不是返回隐藏真值。

| 路径 | 内容 |
|---|---|
| `docs_repo/ops_runbook.odt` | Ops 章节、启动检查表、监控术语；含旧版本步骤及待补变更 |
| `docs_repo/api_handbook.odt` | API 接口、错误码、恢复指引；含旧 endpoint 名和交叉引用 |
| `docs_repo/oncall_faq.md` | 公开 FAQ / 术语页，版本固定 |
| `private/actor_a/ops_change_requests.csv` | `request_id,section,old_text,new_fact,source_id,effective_date,status`；含撤回/重复请求 |
| `private/actor_a/ops_revision_rules.pdf` | A 的版本优先级、术语规范、步骤内容和检索验收要求 |
| `private/actor_b/api_change_requests.csv` | API/error-code 接口变更和有效期，含 deprecated / test request |
| `private/actor_b/api_revision_rules.pdf` | B 的兼容策略、错误码、示例及查询短语要求 |
| `out/ops_revision.json`, `api_revision.json` | 变更 IDs、变更前后章节锚点、排除记录及索引核验 receipt |

每个 role-private 资料含 10–14 个有效要求、若干需判定版本优先级的干扰项。每个角色更新至少 3 个文档章节/条目，并验证 4–6 个指定查询的 top results / preview 文本；检索短语与答案不直接一一匹配。索引不可跳过实际刷新步骤：服务端记录 active source revision 与每个 actor 关联的 query receipt。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Operations Runbook Maintainer

```text
Maintain the Operations documents in ~/workspace/bc21/docs_repo/ using LibreOffice Writer and the local search portal at http://127.0.0.1:18221/search.

Read ~/workspace/bc21/private/actor_a/ops_revision_rules.pdf and reconcile it with ~/workspace/bc21/private/actor_a/ops_change_requests.csv. Apply only current, approved requests; resolve duplicates, withdrawn requests, effective dates, and terminology from the supplied rules and source IDs. Update the relevant Operations runbook sections while preserving document styles, headings, cross-references, and unrelated content.

Save ~/workspace/bc21/out/ops_revision.json with applied/excluded request IDs, updated section IDs, normalized terms, and source revision. Rebuild the local document index after saving. Use the documented Operations search phrases to verify each result points to the current section and that the preview contains the revised text. If a result is stale or missing, inspect the source/index revision, correct the document or rebuild, and save the final portal receipt in the JSON. Verify the saved ODT and search previews.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — API and Error-Reference Maintainer

```text
Maintain the API and error-reference documents in ~/workspace/bc21/docs_repo/ using LibreOffice Writer and the local search portal at http://127.0.0.1:18221/search.

Read ~/workspace/bc21/private/actor_b/api_revision_rules.pdf and reconcile it with ~/workspace/bc21/private/actor_b/api_change_requests.csv. Apply current supported interface changes and error-code definitions, excluding deprecated, withdrawn, test, or out-of-window entries. Update the relevant API handbook sections and examples with correct version labels, request/response field names, and cross-references. Preserve Writer styles and unrelated document content.

Save ~/workspace/bc21/out/api_revision.json with applied/excluded request IDs, changed section IDs, normalized interface names, and source revision. Rebuild the local document index after saving. Verify all documented API search phrases return the current section and the preview includes the revised error guidance. If the index is stale or incomplete, resolve it by checking document and index revisions, then save the final search receipt. Verify the saved ODT and portal previews.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** Writer 内存文档保存会覆盖 CLI 更新的 ODT；索引服务可能在旧文件被 Writer 保存前构建，造成 index revision 对应过时文档。另一个 rebuild 可让浏览器搜索暂时见到 staging/旧 active 版。
- **全 GUI：** 两侧通过 Writer 打开文档时会竞争窗口/页面状态；门户重建后 search page 当前结果/过滤条件会刷新，之前的预览不能证明最终索引。
- **全 CLI：** 标准库 ZIP/XML 可修改 ODT、CLI 可触发 rebuild 与 HTTP 检索，但仍受 ODT 全包覆盖、index revision、原子切换和 source hash 约束。只改页面文本或直接伪造 `ops_revision.json` 不会产生服务端 query receipt。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Host Oracle 解析回收 ODT 内容，按私有变更请求与规则核对章节，再比对 index/search 的只读服务回执。个人权重各 `1.000`；Joint `.40 + .35 + .25 = 1.000` 且全 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | 当前有效 Ops request 集合与撤销/重复排除正确 |
| A02 | 0.20 | 是 | Writer 中所有指定 Ops 事实、术语、日期与章节锚点更新准确 |
| A03 | 0.18 | 是 | `ops_revision.json` 的 source IDs、排除数与文档变化可追溯 |
| A04 | 0.17 | 是 | Ops 查询结果关联最终 source revision，preview 含新段落 |
| A05 | 0.15 | 是 | 文档和索引均为有效可解析版本，查询覆盖率满足要求 |
| A06 | 0.10 | 否 | FAQ、非目标条目、Writer 样式及引用未意外改变 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | 当前受支持 API/error changes 选择及过期版本排除准确 |
| B02 | 0.20 | 是 | handbook 的接口字段、错误码、示例及兼容说明正确 |
| B03 | 0.18 | 是 | `api_revision.json` 与有效 source request / 文档锚点一致 |
| B04 | 0.17 | 是 | API 查询返回最终 revision 的正确段落和 preview 内容 |
| B05 | 0.15 | 是 | 所有 required 查询有效，索引切换成功且可解析 |
| B06 | 0.10 | 否 | FAQ、Ops 文档和模板样式未被破坏 |

### `subchecks_joint`（全部 required）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 所有最终文档 source hash 与 active index source revision 一致 |
| J02 | 0.35 | 是 | 两侧 query receipt 都来自最终 active index，查询无陈旧/半成品结果 |
| J03 | 0.25 | 是 | 两份变更记录、ODT 内容与服务 index 同步，文档页/索引基线结构完整 |

## 6. 防作弊与隔离边界

变更 CSV/PDF 分别按 role UID / private mount 隔离；Search API 只索引/返回公开工作文档，不索引私有请求或 Host Oracle。有效 request IDs、目标文本真值及评分权重仅存于 host oracle fixture。Guest CLI 可写 docs_repo 与触发本地索引服务，但不能调用 Host 采集器或队列控制面。

---

# BC-22 — 定时任务调度配置与本地执行窗口

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | Python 标准库、PyYAML、CSV / JSON、`google-chrome` 本地 monitor；无外部 scheduler package |
| 复杂度 / 步数目标 | 每角色约 55–90 个有效操作：多源任务依赖/窗口/配额推导，编辑配置、dry-run 修正，再触发执行并核对日志及配额 |
| 单人可解性 | Ingest/Clean 与 Report/Archive 作业及规则分属角色输入；各自可独立排期、dry-run、执行并提交报告 |
| 核心冲突 | `schedule_config.yaml` 整份写回；全局 worker slot/quota；重载与执行并行；monitor revision 和 job attempt 日志覆盖/过期 |

## 2. 初始环境、路径与数据

工作根 `~/workspace/bc22/scheduler/`；监控 UI `http://127.0.0.1:18222/monitor`，Chrome 预开 Queue Status。Python 标准库 daemon 从 `config/schedule_config.yaml` 加载时区为 UTC 的窗口、任务依赖、重试和资源配额；普通 request 不热读文件，调用 `schedctl reload` 才推进配置 revision。`schedctl dry-run <scope>` 返回冲突原因，`schedctl trigger <job-id>` 在本地确定性模拟器中生成小型文件和执行日志；不触发外网、系统计划任务或破坏性操作。

| 路径 | 内容 |
|---|---|
| `config/schedule_config.yaml` | `timezone,windows,quotas,jobs[]`，每 job 含 `id,scope,depends_on,cron_like,window,priority,retry,max_runtime_s,enabled` |
| `private/actor_a/ingest_job_matrix.csv` | 采集/清洗 job 依赖、数据到达时间、有效窗口、配额；含重复/过期任务 |
| `private/actor_a/ingest_schedule_policy.pdf` | UTC 转换、依赖先后、错峰、每日 quota、retry 和 SLA 规则 |
| `private/actor_b/report_job_matrix.csv` | 报表生成/归档 job、输入 ready times、保留期限和下游条件 |
| `private/actor_b/report_schedule_policy.pdf` | 报表窗口、归档顺序、峰值限制、重试/保留规则 |
| `var/execution_log.sqlite` | `job_run,resource_slot,output_artifact,config_revision`；不可由 Prompt 写入的 host Oracle 字段除外 |
| `out/ingest_schedule_report.json`, `archive_schedule_report.json` | 每侧计划、dry-run / trigger IDs、执行记录和最终监控值 |

每侧 7–10 个候选作业，其中有 dependency chain、冲突时间窗、资源配额边界、过期源和一个合法但非首选解。worker 同时执行容量固定为 2；约束检查由 dry-run 返回诊断，后续可编辑和再次验证。作业运行仅产生 Guest 内确定性小文件。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Data Ingest Scheduler

```text
Configure and validate the Ingest/Clean jobs in ~/workspace/bc22/scheduler/config/schedule_config.yaml. Use the local monitor at http://127.0.0.1:18222/monitor.

Read ~/workspace/bc22/private/actor_a/ingest_schedule_policy.pdf and reconcile it with ~/workspace/bc22/private/actor_a/ingest_job_matrix.csv. Determine valid job versions, UTC execution windows, dependencies, priorities, daily quota, and retry limits. Update the Ingest/Clean schedule settings while preserving valid YAML and unrelated configuration.

Reload the scheduler, run a dry-run, and resolve any dependency, window, or quota conflicts based on the policy. Trigger each required eligible job only after the dry-run validates the schedule. Review execution logs, produced artifacts, retry counts, and monitor revision. Save ~/workspace/bc22/out/ingest_schedule_report.json with source job IDs, excluded rows, final schedule values, dry-run receipt, trigger IDs, output paths, and observed run results. Verify the final active config and monitor state.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Reporting and Archive Scheduler

```text
Configure and validate the Report/Archive jobs in ~/workspace/bc22/scheduler/config/schedule_config.yaml. Use the local monitor at http://127.0.0.1:18222/monitor.

Read ~/workspace/bc22/private/actor_b/report_schedule_policy.pdf and reconcile it with ~/workspace/bc22/private/actor_b/report_job_matrix.csv. Determine valid job versions, readiness dependencies, UTC report windows, archive ordering, retention, retry, and peak resource limits. Update the Report/Archive schedule settings while preserving valid YAML and unrelated configuration.

Reload the scheduler, run a dry-run, and correct any dependency, slot, time-window, or quota warnings using the supplied rules. Trigger each required eligible job after validation. Review execution logs, artifact paths, retention metadata, and the active config revision in the monitor. Save ~/workspace/bc22/out/archive_schedule_report.json with source IDs, exclusions, schedule values, dry-run receipt, trigger IDs, outputs, and observed results. Verify the final schedule and monitor status.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** monitor 页面显示一个 active revision，而 CLI 写盘后未 reload，dry-run 仍基于旧值；另一侧保存 YAML 可覆盖前一版本尚未合入的配置区。
- **全 GUI：** 编辑 YAML 文本、选择 scope、reload、dry-run 与 trigger 时的页面状态会交错；worker slot / resource quota 是进程级共享状态，独立页面不能互相隔离。
- **全 CLI：** Python/PyYAML 可写文件或 HTTP API，但 scheduler 的依赖、UTC 窗口、配额与单一 worker pool 是服务端强制。直接改 SQLite 执行日志无效，Host Oracle 只采信服务端签发的 run receipt 和产物 hash。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Oracle 按私有 job matrix / policy 重算可运行计划，并核对 active YAML、dry-run / run receipts、产物和 monitor revision。A/B 权重各 `1.000`；Joint `.40 + .35 + .25 = 1.000` 且全 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | 有效 ingest jobs、版本选择与 stale/duplicate 排除准确 |
| A02 | 0.20 | 是 | UTC windows、dependencies、priority、daily quota / retry 符合 policy |
| A03 | 0.18 | 是 | YAML schema 合法、Ingest 配置能由 active revision 加载 |
| A04 | 0.17 | 是 | dry-run 所有 required job 无违规，触发集合准确 |
| A05 | 0.15 | 是 | ingest report 与服务端 receipt、执行产物 / revision 对应 |
| A06 | 0.10 | 否 | Report/Archive 配置与原始公共 job registry 保持有效 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | 有效 report/archive jobs、依赖和保留期限正确 |
| B02 | 0.20 | 是 | 窗口、quota、slot、重试/归档顺序通过规则 |
| B03 | 0.18 | 是 | YAML Report/Archive section 完整并已加载 |
| B04 | 0.17 | 是 | 所有 required jobs dry-run 合格，最终 trigger 集正确 |
| B05 | 0.15 | 是 | archive report 和服务 receipt / 产物 / revision 一致 |
| B06 | 0.10 | 否 | Ingest 规则、非目标 job 与 baseline 没有被破坏 |

### `subchecks_joint`（全部 required）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 最终 schedule 同时包含所需两类任务且依赖 DAG 无环/缺依赖 |
| J02 | 0.35 | 是 | worker 容量/时窗/配额无冲突，真实执行日志符合最终配置 revision |
| J03 | 0.25 | 是 | 两份报告、所有服务 receipts 与保留的任务产物相互一致，无伪造 run |

## 6. 防作弊与隔离边界

Actor 私有矩阵与规则按 UID / mount 隔离；公开 scheduler 只暴露配置校验和 guest 内模拟任务，不含评分真值、hidden quota ledger 或 Host control。执行日志由服务端追加并在 Host 回收快照时只读采集。Guest CLI 不可访问 Host scheduler、队列控制器或 Oracle。

---

# BC-23 — GIMP 视觉资产与发布清单双端核验

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | GIMP、Python 3.10.12 / Pillow、标准库 `zipfile` / `hashlib`、`google-chrome` 本地发布台 |
| 复杂度 / 步数目标 | 每角色约 55–95 个有效操作：从多份素材/版本表筛选、制作/整理视觉或包产物、进行两阶段发布校验、修订清单并复核 hash / 状态 |
| 单人可解性 | Client visual 与 Server configuration package 为分离责任域，各有独立规则和输入；每侧能独立通过发布流程 |
| 核心冲突 | `release_manifest.json` 全量保存丢失字段；共享 build/check 输出目录覆盖；QA 状态与 manifest revision 失配 |

## 2. 初始环境、路径与数据

Guest 根 `~/workspace/bc23/release/`；GIMP 打开 `assets/client/launch_source.xcf` 的默认素材版本；Chrome 打开本地 QA 页 `http://127.0.0.1:18223/release`。QA 服务由 Python 标准库实现，只能绑定 loopback。`release_manifest.json` 含 schema version、release ID、client/server artifact list、dimensions / MIME / SHA-256、source revision、validation status 和 approval receipt。服务的 Phase 1 Validate 可拒绝缺字段、尺寸 / checksum / metadata 不匹配项；修正后 Phase 2 Finalize 才会生成 Guest 内 publish receipt。没有外网上传或真实凭据。

| 路径 | 内容 |
|---|---|
| `assets/client/launch_source.xcf` / `client_reference.png` | Client 海报源图、品牌色/安全区参考；参考图不全是最终尺寸 |
| `assets/server/package_inputs/` | Server 配置、版本说明、locale 文件和 build inventory |
| `private/actor_a/client_release_matrix.csv` | 有效 campaign、语言、target dimensions、文件名、色值和输出规范；含 superseded item |
| `private/actor_a/client_brand_rules.pdf` | GIMP 图层、crop、留白、色彩与 visual-release 核验标准 |
| `private/actor_b/server_release_matrix.csv` | 包含版本、平台、locale 和源文件要求；含旧包/重复文件/错误权限诱饵 |
| `private/actor_b/package_rules.pdf` | 文件清单、metadata、许可字段、expected archive layout 与 hash 规则 |
| `out/client/` | editable `.xcf`、标准尺寸 PNG exports、`client_release.json` |
| `out/server/` | 构建 ZIP、`server_release.json`、`checksums.sha256` |
| `release_manifest.json` | Guest 可见 release state；隐藏期望 hash / 检查答案留在 Host |

每边 10–16 个候选源项，需按版本状态筛到多个目标产物。A 必须在 GIMP 调整图层/画布或布局后导出多个尺寸版本，用 Pillow 校验 PNG dimensions/mode；B 用 stdlib 构建 archive 并核对每文件名/大小/哈希。两边均需在 QA 台处理 Phase 1 反馈，修正对应 manifest/artifact 后完成 Phase 2。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Client Visual Release Producer

```text
Prepare the Client visual release in ~/workspace/bc23/release/ using GIMP and the local release QA page at http://127.0.0.1:18223/release.

Read ~/workspace/bc23/private/actor_a/client_brand_rules.pdf and reconcile it with ~/workspace/bc23/private/actor_a/client_release_matrix.csv. Select current campaign variants, exclude superseded or invalid rows, and produce the required visual outputs at the specified dimensions, file names, and safe areas. Use the supplied XCF as an editable source, preserve useful layer structure, and save updated working art under ~/workspace/bc23/release/out/client/.

Export all required PNG sizes and use Pillow or the available desktop tools to verify dimensions, color mode, file integrity, and output names. Write client_release.json with selected source IDs, dimensions, output paths, and SHA-256 values; update only the client entries in release_manifest.json. Submit the release for QA validation, resolve any Phase 1 rejection based on the cited requirements, then finalize it. Save the final QA receipt and verify that the manifest matches the artifacts on disk.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Server Package Release Engineer

```text
Prepare the Server configuration package release in ~/workspace/bc23/release/ and validate it with the local release QA page at http://127.0.0.1:18223/release.

Read ~/workspace/bc23/private/actor_b/package_rules.pdf and reconcile it with ~/workspace/bc23/private/actor_b/server_release_matrix.csv. Identify current platform/version/locale inputs, exclude obsolete or duplicate files, and build the required archive with the documented paths, permissions metadata, version fields, and license notices. Use the provided Guest tools and Python standard library; do not add packages or fetch external content.

Write server_release.json and checksums.sha256 with the selected source IDs, archive members, sizes, and SHA-256 values. Update only the server entries in release_manifest.json. Submit the package for QA validation, correct any Phase 1 findings from the supplied rules, then finalize the release. Save the final QA receipt and verify the manifest, archive members, and checksum file against the package on disk.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** GIMP XCF 内存态保存可能覆盖 Pillow/CLI 对导出图的转换；QA 页面保留旧 manifest revision，CLI 写入新 hash 后旧页面提交可能把状态退回。Client/Server 使用同名临时 staging 时，后一轮可覆盖较早验证文件。
- **全 GUI：** GIMP 导出对话框的路径/格式选择与 Chrome 的验证/最终确认抢占桌面；浏览器基于先前 revision 的 Finalize 会拒绝或生成 stale receipt。
- **全 CLI：** Pillow 和 stdlib 可以生成、检查图像与包，仍无法绕过服务端 revision、Phase 1/2 状态机和 artifact hash 校验。整文件替换 manifest 可能丢失已写入字段；直接构造发布 JSON 没有有效 QA receipt。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Host Oracle 以私有矩阵/规范独立重建目标清单，核对 Client PNG 元数据/图面关键校验点、Server ZIP 内容与 hashes、QA audit ledger。Host 评分图像时只需其标准库 PNG header/结构检查及确定性像素/色块规则，不假设 Host 安装 Pillow。个人权重 `1.000`；Joint `.40 + .35 + .25 = 1.000`，全 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | Client current variant 选择、排除及 source ID 完整 |
| A02 | 0.20 | 是 | PNG 文件名 / exact dimensions / mode / integrity 满足每个 target |
| A03 | 0.18 | 是 | 视觉关键元素、safe area、品牌色和素材无破坏符合规则 |
| A04 | 0.17 | 是 | XCF 可解析且保留必要编辑图层，client JSON / manifest 的 hash 一致 |
| A05 | 0.15 | 是 | Phase 1 findings 已修正，Phase 2 client release receipt 成功 |
| A06 | 0.10 | 否 | Server package / 公共模板不被改动；client 产物无额外过期文件污染 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | Server variant / locale / version 选择与过期排除准确 |
| B02 | 0.20 | 是 | ZIP 成员路径、许可、版本字段与权限 metadata 完整且无多余文件 |
| B03 | 0.18 | 是 | `server_release.json` 和 checksums 与 archive 内容 hash 精确一致 |
| B04 | 0.17 | 是 | Phase 1 包校验 findings 修正，Phase 2 server release receipt 成功 |
| B05 | 0.15 | 是 | 目标输入 ID、文件尺寸和 archive layout 与规则重算一致 |
| B06 | 0.10 | 否 | Client artifacts / manifest fields 未被 Server 产出覆盖 |

### `subchecks_joint`（全部 required）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 最终 manifest 同时含完整 client/server 项目且 artifact hashes 均有效 |
| J02 | 0.35 | 是 | QA ledger 对两个 artifact 集分别基于最终 revision 记录成功 Finalize |
| J03 | 0.25 | 是 | 导出目录无文件错置/拍平、缺失产物或跨侧 hash / path 混淆 |

## 6. 防作弊与隔离边界

Client / Server inputs、brand/package rules 分别私有挂载。Guest 中没有 hidden target pixel map、expected package hash、评分检查条件或 Host oracle。QA 服务只对当前角色可写 scope 作结构检查，host collector 单独回收签发日志；Guest CLI 无法访问 Host 凭据、容器管理或评分真值。清单中任何“expected”字段均不得是隐藏评分答案。

---

# BC-24 — 跨软件结账核销与最终汇总

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 软件栈 | LibreOffice Calc（ODS）、Python `sqlite3`、`google-chrome` 本地对账台、CSV / JSON / PDF / `pdftotext` |
| 复杂度 / 步数目标 | 每角色约 60–100 个有效操作：清洗多个来源、追踪差异、修改 Calc 与 SQLite、刷新 dashboard、导出并三方互验 |
| 单人可解性 | Subscription / Fulfillment 两个业务线各有独立 inputs、规则和责任表；单侧可独立完成自己的核销和交付 |
| 核心冲突 | ODS 内存/磁盘覆写、SQLite 事务/并发锁、Chrome dashboard revision 与底层快照不同步；多介质存在旧状态回写 |

## 2. 初始环境、路径与数据

根目录 `~/workspace/bc24/closeout/`。Calc 已打开 `quarter_closeout.ods`（`Readme`, `Subscriptions`, `Fulfillment`, `Adjustments`, `Close Summary` 五个表），Chrome 已打开本地对账台 `http://127.0.0.1:18224/closeout`。服务由 Python 标准库实现并 loopback 绑定；SQLite 数据库 `data/closeout.db` 用 Python `sqlite3`；没有额外 browser framework 或第三方数据库 client。

| 路径 | Schema / 内容 |
|---|---|
| `data/closeout.db` | `statement_line(line_id,business_line,period,ref,amount,currency,status,source_batch)`、`ledger_entry(entry_id,line_id,account,amount,period,source_ref,state)`、`reconciliation(line_id,decision,adjustment_id,reason,revision)`、`dashboard_revision` |
| `private/actor_a/subscription_statement.csv` | recurring charges、credits、refunds、billing events；含 retry duplicates、跨期账单、cancelled subscription |
| `private/actor_a/subscription_policy.pdf` | 有效计费日期、贷项应用、汇率/税项口径、matching tolerance 与差异处理规则 |
| `private/actor_b/fulfillment_statement.csv` | shipment、carrier proof、replacement、delivery credit；含 split delivery、void label、partial quantity |
| `private/actor_b/fulfillment_policy.pdf` | 交付确认、差异容限、return/replacement/credit 规则与期末状态 |
| `quarter_closeout.ods` | 各侧工作表含约 35 条原始行与核销区，Close Summary 跨表公式汇总差异数和金额 |
| `out/subscription_closeout.json`, `subscription_closeout.pdf` | A 记录匹配、拒绝/调整项目、合计与结账摘要 |
| `out/fulfillment_closeout.json`, `fulfillment_closeout.pdf` | B 的对应交付 |

各侧私有输入约 50–70 行，约 10–14 项需结案。工作流程先把 source lines 与 ODS 中间账核对，再通过角色授权的 closeout API 在 SQLite 中记录 accepted / adjusted / disputed 并附 reason，最后通过 dashboard 的 Preview → Commit 生成 revision 和 export。DB 文件由 service UID 持有，Actor UID 不直接读取数据库文件；Guest CLI 可调用角色授权 API。Preview 会指出不符合 policy 的条目；角色能从资料自行修正，不依赖另一侧。ODS sheet IDs 和 DB row IDs 稳定，Host Oracle 可作确定性 join。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Subscription Closeout Analyst

```text
Complete the Subscription business-line reconciliation in ~/workspace/bc24/closeout/quarter_closeout.ods and the local closeout desk at http://127.0.0.1:18224/closeout.

Read ~/workspace/bc24/private/actor_a/subscription_policy.pdf and reconcile it with ~/workspace/bc24/private/actor_a/subscription_statement.csv, the Subscriptions sheet, and the Subscription records available to your account in the closeout desk. Apply billing-period, duplicate retry, cancelled account, refund/credit, currency, tax, matching tolerance, and adjustment rules. Decide which lines are matched, adjusted, or disputed and record a reason supported by source IDs.

Update the Subscriptions and relevant Adjustments rows, persist the corresponding SQLite reconciliation entries, and save ~/workspace/bc24/out/subscription_closeout.json with selected/excluded IDs, decisions, amounts, reasons, and totals. Use the closeout desk Preview to identify policy or cross-source mismatches; correct them and commit the final Subscription closeout. Export ~/workspace/bc24/out/subscription_closeout.pdf and verify that the workbook, database result, dashboard revision, JSON, and PDF agree.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Fulfillment Closeout Analyst

```text
Complete the Fulfillment business-line reconciliation in ~/workspace/bc24/closeout/quarter_closeout.ods and the local closeout desk at http://127.0.0.1:18224/closeout.

Read ~/workspace/bc24/private/actor_b/fulfillment_policy.pdf and reconcile it with ~/workspace/bc24/private/actor_b/fulfillment_statement.csv, the Fulfillment sheet, and the Fulfillment records available to your account in the closeout desk. Apply split-shipment, proof-of-delivery, void-label, return/replacement, partial-quantity, credit, and close-period rules. Decide which lines are matched, adjusted, or disputed and provide a reason tied to source IDs.

Update the Fulfillment and relevant Adjustments rows, persist the corresponding SQLite reconciliation entries, and save ~/workspace/bc24/out/fulfillment_closeout.json with selected/excluded IDs, decisions, quantities/amounts, reasons, and totals. Use the closeout desk Preview to find mismatches, correct them using the supplied rules, and commit the final Fulfillment closeout. Export ~/workspace/bc24/out/fulfillment_closeout.pdf and verify the workbook, database records, dashboard revision, JSON, and PDF agree.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** Calc 旧内存副本保存可能覆盖 CLI 对 ODS 的核销；CLI DB 事务推进 revision 后，Chrome 的旧 Preview/Commit 会失效；服务重载报表时可能读取 Calc 尚未落盘的旧行。
- **全 GUI：** Calc 当前活动 sheet / 单元格、Chrome Preview 对话框、PDF 导出窗口竞争桌面；两侧对各自表页保存可能仍通过完整 ODS package 回写丢失另一页未落盘修改。
- **全 CLI：** CLI 可操作 ODS package 和角色授权服务 API；service UID 持有 SQLite 文件，Actor UID 不直接访问 DB。API 不能避开事务约束、dashboard revision token、跨介质 join 或全文件 ODS 覆写；直接写 JSON 不会生成 server commit receipt，不能证明三处状态一致。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Host Oracle 从隐藏输入真值重算匹配与调整规则，再只读核对 ODS、DB 快照、dashboard commit ledger、JSON / PDF。A/B 权重各 `1.000`；Joint `.40 + .35 + .25 = 1.000`，全部 required。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | Subscription source 选行和跨期/duplicate/cancelled exclusion 精确 |
| A02 | 0.20 | 是 | credit/refund/tax/currency/matching 处理及调整理由正确 |
| A03 | 0.18 | 是 | ODS Subscriptions/Adjustments 行和公式/汇总结果与 Oracle 一致 |
| A04 | 0.17 | 是 | SQLite reconciliation 状态、line IDs、amount 和理由完整 |
| A05 | 0.15 | 是 | JSON/PDF 与 ODS/DB/dashboard commit revision 内容一致 |
| A06 | 0.10 | 否 | Fulfillment rows、共享公式区域及非目标源数据保持 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | Fulfillment statement 与 split/void/partial/return 行筛选正确 |
| B02 | 0.20 | 是 | delivered / replacement / credit 的 decision 与数量金额正确 |
| B03 | 0.18 | 是 | ODS Fulfillment / Adjustments 与跨表 Close Summary 数值正确 |
| B04 | 0.17 | 是 | SQLite 行、source refs、状态、理由和 revision 准确 |
| B05 | 0.15 | 是 | JSON/PDF/DB/workbook 同一最终 commit snapshot，文本有效 |
| B06 | 0.10 | 否 | Subscription rows 和初始 source ledger 无非目标变化 |

### `subchecks_joint`（全部 required）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| J01 | 0.40 | 是 | 最终 ODS、SQLite 与 dashboard commit ledger 中 A/B 两个业务域均保留且数值匹配 |
| J02 | 0.35 | 是 | Close Summary 公式和所有 JSON/PDF 引用的同一最终 DB/dashboard revision 一致 |
| J03 | 0.25 | 是 | 所有源行恰当匹配/调整/争议，无重复结案、非法删除、跨域或旧 revision 回滚 |

## 6. 防作弊与隔离边界

订阅与履约 CSV/PDF 通过独立 UID / role-private mount 注入，Prompt 和账号互不泄露。共同 ODS、操作 DB 与 Dashboard 仅含工作所需公开状态，不内嵌 hidden classification / expected totals。Oracle 真值、标准答案、Host collector 与队列控制仅在宿主机；Guest CLI 可以读写自己的 Guest workspace，不能进入宿主机控制/评测面。

---

## 批次摘要与设计准入备注

| Case | 主题 / 已确认工具 | 目标步数 / actor | 主要耦合 |
|---|---|---:|---|
| BC-17 | SQLite 应收/库存核销 + Chrome | 55–90 | 多表事务、约束和汇总视图 |
| BC-18 | 工单状态机 + 两阶段审批 | 55–90 | revision、证据状态与队列导出 |
| BC-19 | PyYAML 规则 DSL + 服务回归 | 60–95 | YAML 整体保存和 active hash |
| BC-20 | Calc ODS 多期预算 + PDF | 55–90 | 公式、内存/磁盘态和导出 |
| BC-21 | Writer 文档 + 搜索/索引门户 | 55–90 | source/index revision 与重建 |
| BC-22 | PyYAML scheduler + monitor | 55–90 | 配置 reload、配额和 worker slot |
| BC-23 | GIMP/Pillow + 发布 QA | 55–95 | 多产物 hash、manifest、两阶段验证 |
| BC-24 | Calc + SQLite + Chrome 结账 | 60–100 | 三介质一致性与提交 revision |

步数均是任务负载设计目标，既非 Runner 限制也非实际步数承诺。设计完成不等于 Guest GUI、服务或真实 Agent 已验证。实现前仍须按新脚手架准入流程检查各端口、角色 UID / mount、权限证书及具体 Guest 启动适配；不得因静态规格通过而声称已完成运行时验证。
