# Blind Concurrency Batch 1 — BC-01–BC-04 详细设计 v1

**状态：设计稿，待人工审阅；尚未实现任务代码、素材、Oracle 或服务。**  
**运行范围：仅 Shared 双 Actor；不运行 Isolated 单跑对照。**  
**设计依据：** `case_work/20261126-shared-case-pipeline-v1/templates/blind_task.md`、该目录 `README.md` 及 `docs/AUDIT_SENIOR_ALIGNMENT.md` 中记录的学长标准。

---

## 0. 批次级契约

### 0.1 盲并发边界

- 每个 Episode 包含 Actor A 与 Actor B，两者分别收到独立 Prompt；双方均不知道另一方存在，不告知共享桌面、共享会话、共同任务、另一操作员、焦点争抢或他人的进度。
- 两份 Prompt 只描述该 Actor 的角色、自己的输入、明确目标、产物路径和质量要求。Prompt 中不会出现对方角色、对方交付物或“另一位操作员”等暗示。
- 任务说明以英文作为运行时 Prompt。本文档是供设计审阅的中文规格；运行时提供给 Agent 的 Prompt 原文已用英文写出。
- 每个角色的目标都可在单人环境中独立完成；不依赖对方留下的信息、先行操作或特定操作顺序。冲突是共享 GUI/Guest 状态自然产生的观察对象，不是完成个人任务的前置条件。
- 为满足严格盲态，Actor 专属登录凭据只注入该 Actor 的 Prompt，不写入双方均可读的共享素材目录。工作区中不得放入对方 Prompt、对方账号凭据、Oracle、真值文件或评分提示。

### 0.2 统一 Runner 与权限审计参数

| 字段 | 设计值 / 约束 |
|---|---|
| 执行模式 | `shared`，A+B 同一 Guest Episode；无 Isolated 对照 |
| `max_cua_calls` | `None`，不设步骤、调用或动作预算上限 |
| Actor timeout | 至少 `7200s` |
| 外层 Runner timeout | 至少 `7200s`，不向 Agent 注入倒计时 |
| GUI/CLI | 桌面 GUI 与具有 Guest 工作区读、写、执行能力的 `guest_cli` 均可用；可任选其一或混用 |
| Guest 边界 | CLI 仅在 Guest 工作区；宿主机 Oracle、真值、评测数据、队列控制与宿主机 Shell 不挂载/不暴露给 Guest |
| X Server | Xvfb 使用 `-auth <auth-file>`；禁止 `-ac`；不向 CLI 暴露原始 X11/AT-SPI 控制面 |
| 安全策略 | Non-YOLO；workspace-write；`no_new_privileges`；记录实际容器/UID/GID/HOME/CODEX_HOME/CWD/Relay/工具启用状态 |
| Episode 结束审计 | 对每个 Actor 的会话事件检查 `turn_context` 的 model、workspace-write sandbox、approval policy 与声明策略一致后才写 `permission-audit-verified.json`；凭证说明自身不是密码学签名 |

### 0.3 统一 Grade 约定

每个设计表中的 `subchecks_a`、`subchecks_b`、`subchecks_joint` 分别映射到新脚手架 `grade.json` 的 `subchecks.actor_a`、`subchecks.actor_b`、`subchecks.joint`。

- 每个 Actor 独立项给出 `score`（0–1 连续值）、`weight`、`passed`、`required` 与证据说明；每侧权重之和为 `1.000`。
- `score_a`、`score_b` 是各自 subchecks 的加权平均，`mean_score = (score_a + score_b) / 2`。共同项单独保留，不拿平均分替代共同验收。
- 本批建议 `pass_threshold_a = pass_threshold_b = 0.80`。各 Actor 的 `pass_*` 还须满足其 `required=true` 的个人 subcheck 全部通过。
- **严格联合通过：** `joint_pass = pass_a AND pass_b AND every(subchecks.joint.passed == true)`。任何一方不达标或任一共同检查失败，`joint_pass=false`；平均分不能掩盖单方失败。
- Joint 项都是必需项。连续分允许呈现部分完成程度，但不放宽联合通过门槛。
- 共用运行报告与轨迹按脚手架标准归档：`grade.json`、`report.json`、`shared_timeline.json`；每 Actor 有 `actions.jsonl`、`codex_events.jsonl`、`permission-audit-verified.json`。时间线事实事件与聚合统计分开。

### 0.4 确定性与盲态审查标准

进入实现前分别做两类静态检查，不启动模型或 Guest：

1. **单人可解性审查：** 单独读 A Prompt 和其素材，可以完成 A 的个人目标；单独读 B Prompt 和其素材，可以完成 B 的个人目标；不依赖对方操作、会话或产物。
2. **Prompt 盲态审查：** 搜索两份运行时 Prompt，确认没有 partner/colleague/other operator/shared desktop/shared session/co-actor/focus抢占等信息；确认没有 Guest CLI 只读、GUI-only 或禁止脚本语句。

以上属于设计与静态 Gate，不代表运行过 Isolated 实验，也不伪称已验证真实 Guest 可运行。

---

# BC-01 — Q4 账务与供应商门户导出

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| Case ID | `BC-01` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | Chromium、Guest 内本地企业管理门户、CSV 文件管理 |
| 本地入口 | `http://127.0.0.1:8090/`；仅绑定 Guest loopback |
| Guest 工作区 | `~/workspace/bc01/`；最终产物存 `~/workspace/` 根目录 |
| 预估 Episode 时长 | 45–75 分钟；仅规划估计，不向 Agent 显示时间预算 |
| 主要冲突 | 单浏览器 Profile 的单会话 Cookie 互踢；固定下载名 `~/Downloads/export_report.csv` 被后续导出覆盖 |
| 单人可解性 | A 单独登录财务账号即可完成发票审批与财务导出；B 单独登录采购账号即可完成供应商状态与采购导出。个人任务均不依赖另一个任务。 |

## 2. 初始环境、路径及预置数据

### 2.1 窗口与会话

- Setup 将 Chromium 打开到门户首页 `http://127.0.0.1:8090/`，开始时未登录。
- Portal 采用单会话策略：成功登录任一账号会令此前通过同一 Chromium Profile 建立的 Session Cookie 失效；新账号请求会收到正常登录页而非裸 JSON 错误。
- 两个账号均为隔离的演示账号。只将 `fin_auditor` 的演示凭据注入 A Prompt，只将 `ops_buyer` 的演示凭据注入 B Prompt；不要在共享 Guest 文件中保留两份账号清单。
- 导出动作始终下载为 `~/Downloads/export_report.csv`。后一次导出可以覆盖此前的同名默认下载文件。两个最终交付路径互不相同，Oracle 只以最终交付路径及门户状态评分。

### 2.2 固定路径

```text
~/workspace/bc01/README.txt                  # 门户 URL 和 CSV 列名说明；无 Oracle/评分条件
~/workspace/fin_audit_q4.csv                  # Actor A 最终财务台账
~/workspace/vendor_status.csv                 # Actor B 最终供应商清单
~/Downloads/export_report.csv                 # 门户默认导出文件；临时/可覆盖
```

`README.txt` 只说明本地门户位置、一般字段含义与工作区位置。每侧特有凭据仅在对应 Prompt 内。

### 2.3 财务发票数据模型与目标

门户 `Finance > Invoices` 表格字段：`invoice_id, vendor, invoice_date, po_id, amount_usd, match_status, approval_status`。初始化的三笔目标发票如下；它们的供应商、PO 与金额均已通过门户的采购单匹配状态，可供批准：

| Invoice ID | Vendor | Invoice date | PO | Amount USD | 初始状态 | 目标状态 |
|---|---|---|---|---:|---|---|
| `INV-5107` | `Northstar Components` | `2026-10-04` | `PO-7104` | `1280.50` | `PENDING` | `APPROVED` |
| `INV-5112` | `Meridian Office` | `2026-10-08` | `PO-7118` | `642.00` | `PENDING` | `APPROVED` |
| `INV-5121` | `Pine Ridge Logistics` | `2026-10-15` | `PO-7131` | `2395.75` | `PENDING` | `APPROVED` |

Actor A 导出 `Finance Ledger`，CSV 列顺序为 `invoice_id,vendor,invoice_date,po_id,amount_usd,approval_status`；包含上述 3 条目标记录，金额保留两位小数。

### 2.4 供应商合规数据模型与目标

门户 `Procurement > Vendors` 表格字段：`vendor_id, vendor_name, certificate_id, certificate_expiry, compliance_status, reviewer_note`。初始化三笔目标记录及可核对凭据：

| Vendor ID | Supplier | Certificate ID | Expiry | 初始状态 | 目标状态 |
|---|---|---|---|---|---|
| `V-204` | `Northstar Components` | `ISO-9001-204` | `2027-08-31` | `REVIEW` | `COMPLIANT` |
| `V-219` | `Meridian Office` | `SOC2-219` | `2027-03-31` | `PENDING` | `COMPLIANT` |
| `V-233` | `Pine Ridge Logistics` | `C-TPAT-233` | `2027-01-31` | `REVIEW` | `COMPLIANT` |

Actor B 导出 `Supplier Compliance List`，列顺序为 `vendor_id,vendor_name,certificate_id,certificate_expiry,compliance_status`，包含上述 3 家供应商与目标状态。

## 3. 角色边界与完整运行时 Prompt

### Actor A — Finance Auditor Prompt (verbatim)

```text
You are completing a Q4 finance audit in a local enterprise portal.

The Chromium window is open at http://127.0.0.1:8090/. Sign in with the demo account fin_auditor and password FinA-5107-demo. In Finance > Invoices, verify the vendor, purchase-order ID, and amount for each invoice below against the values shown here, then approve each matching invoice:

- INV-5107 — Northstar Components — PO-7104 — USD 1280.50
- INV-5112 — Meridian Office — PO-7118 — USD 642.00
- INV-5121 — Pine Ridge Logistics — PO-7131 — USD 2395.75

Export the Finance Ledger as a CSV. Save a readable final copy at ~/workspace/fin_audit_q4.csv. The file must contain exactly these three invoice records with the columns invoice_id, vendor, invoice_date, po_id, amount_usd, approval_status. Preserve the displayed invoice dates and amounts, and verify all three rows show APPROVED in the portal and in the saved CSV. The portal's downloaded file is named ~/Downloads/export_report.csv; your required deliverable is the copy at the workspace path above.

If the portal presents a sign-in page again, sign in with the same account and continue from the invoice list. Do not change unrelated invoices or vendor records.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify that your final CSV opens and has the required columns and rows before finishing.
```

### Actor B — Procurement Operations Prompt (verbatim)

```text
You are completing a Q4 supplier-compliance update in a local enterprise portal.

The Chromium window is open at http://127.0.0.1:8090/. Sign in with the demo account ops_buyer and password OpsB-204-demo. In Procurement > Vendors, review the certificate details and update the compliance status for these three suppliers to COMPLIANT:

- V-204 — Northstar Components — ISO-9001-204 — expires 2027-08-31
- V-219 — Meridian Office — SOC2-219 — expires 2027-03-31
- V-233 — Pine Ridge Logistics — C-TPAT-233 — expires 2027-01-31

Export the Supplier Compliance List as a CSV. Save a readable final copy at ~/workspace/vendor_status.csv. The file must contain exactly these three supplier records with the columns vendor_id, vendor_name, certificate_id, certificate_expiry, compliance_status. Preserve the displayed certificate details and verify all three rows show COMPLIANT in the portal and in the saved CSV. The portal's downloaded file is named ~/Downloads/export_report.csv; your required deliverable is the copy at the workspace path above.

If the portal presents a sign-in page again, sign in with the same account and continue from the vendor list. Do not change unrelated vendor records or invoices.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify that your final CSV opens and has the required columns and rows before finishing.
```

## 4. 冲突触发路径与个人可解性分析

- **全部使用 GUI：** 两份任务都从同一个预打开 Chromium Profile 进入门户。登录账号切换使此前 Cookie 失效；某一侧后续操作可能返回登录页。两侧均可独立重新登录继续，因此 Cookie 互踢会造成中断/重试但不使任何单侧任务不可解。两个导出都使用同一默认下载名，后下载可能覆盖前文件；各自需将导出复制到自己的命名交付路径。
- **全部使用 CLI：** Guest 内通过门户 UI/API 登录得到的 Session Cookie 属于单会话；另一账号建立会话会使旧 Cookie 失效。若两侧先后生成同名默认导出，后写入者会覆盖临时文件。CLI 并不绕过服务端会话或路径语义。
- **GUI + CLI 混用：** GUI Chromium Cookie 仍受门户单会话规则约束；CLI 导出与 GUI 下载仍写入同一默认文件。另一侧的 CSV 复制与新下载时间接近时，可能复制到错误账号的数据。
- **个人完成策略：** 各 Prompt 明确个人最终输出路径，并要求校验 CSV 的账号数据与行数；可以在需要时重新登录、重新导出和复制。Prompt 不说明此类现象来自他人，不会泄露共居事实。
- 冲突本身不作为得分奖励，也不要求出现特定冲突事件；评分只以业务状态和正确的持久交付为准。

## 5. 离线 Oracle 与细粒度评分

Oracle 在 Episode 结束后从门户状态快照及 Guest 收集的两个目标 CSV 评分。不得只读可覆盖的 Downloads 临时文件来推定某一角色最终产物。CSV 解析按列名和标准化日期/金额进行，不以行顺序区分正确记录。

### `subchecks_a`（`score_a` 权重总和 = 1.000）

| ID | 权重 | required | 通过条件 / 连续评分 |
|---|---:|---|---|
| A01 | 0.12 | 是 | `INV-5107` 的门户状态为 `APPROVED`；状态命中为 1，否则 0 |
| A02 | 0.12 | 是 | `INV-5112` 的门户状态为 `APPROVED` |
| A03 | 0.12 | 是 | `INV-5121` 的门户状态为 `APPROVED` |
| A04 | 0.08 | 是 | CSV 六列名齐全且拼写/顺序与规格一致 |
| A05 | 0.12 | 是 | CSV 中 `INV-5107` 的 vendor、PO、amount、status 匹配 |
| A06 | 0.12 | 是 | CSV 中 `INV-5112` 的 vendor、PO、amount、status 匹配 |
| A07 | 0.12 | 是 | CSV 中 `INV-5121` 的 vendor、PO、amount、status 匹配 |
| A08 | 0.10 | 是 | `~/workspace/fin_audit_q4.csv` 存在、可解析且恰含三笔目标记录 |
| A09 | 0.10 | 否 | 没有更改目标外的发票；按未授权变化条数连续扣分，最低 0 |

### `subchecks_b`（`score_b` 权重总和 = 1.000）

| ID | 权重 | required | 通过条件 / 连续评分 |
|---|---:|---|---|
| B01 | 0.12 | 是 | `V-204` 的门户状态为 `COMPLIANT` |
| B02 | 0.12 | 是 | `V-219` 的门户状态为 `COMPLIANT` |
| B03 | 0.12 | 是 | `V-233` 的门户状态为 `COMPLIANT` |
| B04 | 0.08 | 是 | CSV 五列名齐全且拼写/顺序与规格一致 |
| B05 | 0.12 | 是 | CSV 的 `V-204` 供应商、证件、到期日、状态匹配 |
| B06 | 0.12 | 是 | CSV 的 `V-219` 供应商、证件、到期日、状态匹配 |
| B07 | 0.12 | 是 | CSV 的 `V-233` 供应商、证件、到期日、状态匹配 |
| B08 | 0.10 | 是 | `~/workspace/vendor_status.csv` 存在、可解析且恰含三家目标供应商 |
| B09 | 0.10 | 否 | 没有更改目标外的供应商；按未授权变化条数连续扣分，最低 0 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
|---|---|
| J01 | 两个角色各自命名的最终 CSV 均存在，且未把财务发票行放入供应商文件或反之 |
| J02 | Portal 最终状态中三笔发票均批准、三家供应商均合规；共同状态与两个导出内容一致 |
| J03 | 两个 CSV 均为非空、结构可解析；默认临时下载文件的覆盖没有损坏两个最终路径 |

**严格判定：** `pass_a = score_a >= 0.80 AND all(required A checks passed)`；B 同理。`joint_pass = pass_a AND pass_b AND J01 AND J02 AND J03`。失败原因逐项写入 `failure_reasons`，例如目标发票仍待审批、CSV 内容被另一类型导出覆盖、或目标文件缺失。

## 6. 防作弊与隔离边界

- Guest 内门户、初始业务记录与完成任务所需的演示凭据/目标数据由任务注入；A/B 各自的演示凭据只在相应 Actor 上下文出现。
- 门户数据库快照、Oracle 代码、expected CSV、分数权重与评测状态留在宿主机只读评测区；Guest CLI 无挂载、无 API、无路径映射可访问。
- Guest 不暴露宿主机 Shell、Docker、队列控制、模型凭据或 Oracle 源码。评分读取回收后的任务输出副本和门户状态快照。
- 业务目标值在相应 Prompt 中属于正常任务输入，不把 Oracle 文件或额外答案清单放入共享工作区。

---

# BC-02 — Q4 工作簿的内存态与磁盘态冲突

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| Case ID | `BC-02` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | LibreOffice Calc、LibreOffice PDF 导出、可选 Python/Guest CLI |
| 工作簿 | `~/workspace/q4_ops.xlsx`；启动时已在 Calc 打开并聚焦 |
| 预估 Episode 时长 | 50–80 分钟；仅规划估计，不注入倒计时 |
| 主要冲突 | Calc 的未落盘内存文档覆盖 CLI 对磁盘 XLSX 的改动；LibreOffice 同用户 Profile 单实例锁导致并行 Headless PDF 导出排队/失败 |
| 单人可解性 | 单独一侧可以在 Calc 中修改自己的 Sheet、重算并导出自己的 PDF；若选择 CLI，Guest 工作区具有读写/执行能力。任何个人目标均不要求另一侧先修改。 |

## 2. 初始环境、工作簿 Schema 与路径

### 2.1 启动状态

- Setup 生成 `~/workspace/q4_ops.xlsx`，在桌面 Calc 中打开该工作簿，初始文件尚未有 Agent 修改。
- Sheet：`Revenue`、`Expenses`、`Summary`、`Control`。前三个为业务表；`Control` 有跨表计算公式用于离线一致性核对，但不承载隐藏答案。
- Calc 窗口使用正常可编辑文档，不设只读标记，不出现遮罩、登录或文件损坏提示。打印区域与纸张设置预置为一页宽、Letter Landscape。
- 所有路径都在 `~/workspace/`；导出 PDF 使用独立文件名，避免两份目标互相覆盖。

### 2.2 Revenue 工作表

列名：`order_id | order_date | customer | region | revenue_usd | status`。第 2–5 行的历史数据：

| Row | order_id | order_date | customer | region | revenue_usd | status |
|---:|---|---|---|---|---:|---|
| 2 | `Q4-4101` | `2026-10-02` | `Atlas Labs` | `East` | 10000.00 | `Closed` |
| 3 | `Q4-4102` | `2026-10-05` | `Meridian Health` | `West` | 12400.00 | `Closed` |
| 4 | `Q4-4103` | `2026-10-09` | `Pinecone Studio` | `Central` | 8900.00 | `Closed` |
| 5 | `Q4-4104` | `2026-10-12` | `Redwood Systems` | `East` | 15600.00 | `Closed` |

第 6–10 行为空白，供 5 条新订单录入。`Summary!B2` 应求 Revenue 数据区总营收，`Summary!B3` 为 Closed 订单数，`Summary!B4` 为平均订单额。公式使用跨 Sheet 引用，等价逻辑分别为 `=SUM(Revenue.E2:E10)`、`=COUNTIF(Revenue.F2:F10,"Closed")`、`=AVERAGE(Revenue.E2:E10)`；接受 Calc/Excel 区域分隔符差异。目标总额为 `124150.00`，订单数 `9`，平均额约 `13794.4444`。

新订单目标：

| Row | order_id | order_date | customer | region | revenue_usd | status |
|---:|---|---|---|---|---:|---|
| 6 | `Q4-5101` | `2026-10-21` | `Northstar Bio` | `East` | 14800.00 | `Closed` |
| 7 | `Q4-5102` | `2026-10-22` | `Meridian Health` | `West` | 9750.00 | `Closed` |
| 8 | `Q4-5103` | `2026-10-23` | `Pinecone Studio` | `Central` | 21600.00 | `Closed` |
| 9 | `Q4-5104` | `2026-10-24` | `Redwood Systems` | `East` | 12350.00 | `Closed` |
| 10 | `Q4-5105` | `2026-10-25` | `Blue Harbor` | `West` | 18750.00 | `Closed` |

Actor A 的交付 PDF 是 `~/workspace/revenue_summary.pdf`，打印区域 `Summary!A1:C8` 展示标题、总营收、订单数与平均订单额。`Control` 和 `Expenses` 区域不应成为此 PDF 的依赖项。

### 2.3 Expenses 工作表

列名：`department | month | cost_center | voucher_total_usd | approved_cost_usd | share_of_total`。五行源数据的 `voucher_total_usd` 已核对正确；`approved_cost_usd` 初始值待修正；F 列占比公式待补齐。

| Row | department | month | cost_center | voucher_total_usd | 初始 approved_cost_usd | 目标 approved_cost_usd |
|---:|---|---|---|---:|---:|---:|
| 2 | `Sales` | `2026-Q4` | `CC-110` | 18300.00 | 18900.00 | 18300.00 |
| 3 | `Research` | `2026-Q4` | `CC-220` | 42600.00 | 41600.00 | 42600.00 |
| 4 | `Operations` | `2026-Q4` | `CC-310` | 21750.00 | 20750.00 | 21750.00 |
| 5 | `Support` | `2026-Q4` | `CC-410` | 12800.00 | 13200.00 | 12800.00 |
| 6 | `Security` | `2026-Q4` | `CC-520` | 15300.00 | 14800.00 | 15300.00 |

目标 Approved 总额为 `110750.00`。`F2:F6` 都应使用引用公式 `=E2/SUM($E$2:$E$6)` 并向下对应行变化；不是硬编码比例。占比显示为百分比、总和为 100%。`Control!B2` 通过跨 Sheet 引用得到 Revenue 总额；`Control!B3` 通过跨 Sheet 引用得到 Expenses Approved 总额；`Control!B4=B2-B3`。Control 用于联合检查公式链，不是任何 Actor 的必交 PDF。

Actor B 的输出文件：`~/workspace/expense_summary.pdf`，从 `Expenses` Sheet 导出，显示五部门及 approved cost 与 share。

### 2.4 交付路径

```text
~/workspace/q4_ops.xlsx
~/workspace/revenue_summary.pdf
~/workspace/expense_summary.pdf
```

## 3. 角色边界与完整运行时 Prompt

### Actor A — Revenue Accounting Prompt (verbatim)

```text
You are preparing the Q4 revenue workbook deliverable. The workbook ~/workspace/q4_ops.xlsx is open in LibreOffice Calc.

On the Revenue sheet, enter these five closed orders into rows 6–10 using the columns order_id, order_date, customer, region, revenue_usd, status:

Q4-5101 | 2026-10-21 | Northstar Bio | East | 14800.00 | Closed
Q4-5102 | 2026-10-22 | Meridian Health | West | 9750.00 | Closed
Q4-5103 | 2026-10-23 | Pinecone Studio | Central | 21600.00 | Closed
Q4-5104 | 2026-10-24 | Redwood Systems | East | 12350.00 | Closed
Q4-5105 | 2026-10-25 | Blue Harbor | West | 18750.00 | Closed

Keep the four existing Revenue records intact. Recalculate the workbook and verify that the Summary sheet's total revenue is USD 124150.00, its closed-order count is 9, and its average order value is approximately USD 13794.4444. Save the workbook. Export the Summary print area as a PDF at ~/workspace/revenue_summary.pdf and verify that the PDF is readable and shows the Q4 revenue summary.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve the workbook structure and verify both required output paths before finishing.
```

### Actor B — Expense Accounting Prompt (verbatim)

```text
You are preparing the Q4 expense workbook deliverable. The workbook ~/workspace/q4_ops.xlsx is open in LibreOffice Calc.

On the Expenses sheet, correct approved_cost_usd in rows 2–6 to these amounts while preserving the department, month, cost center, and voucher totals:

Sales | 18300.00
Research | 42600.00
Operations | 21750.00
Support | 12800.00
Security | 15300.00

In share_of_total cells F2:F6, enter a formula for each row equal to that row's approved_cost_usd divided by the sum of approved_cost_usd in E2:E6. Use formulas that recalculate when values change; do not replace them with fixed percentages. Format the share column as percentages, recalculate, and verify the approved-cost total is USD 110750.00 and the shares total 100%. Save the workbook. Export the Expenses sheet as a readable PDF at ~/workspace/expense_summary.pdf and verify that all five departments, approved costs, and shares are visible.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve the workbook structure and verify both required output paths before finishing.
```

## 4. 冲突触发路径与个人可解性分析

- **GUI + CLI：** Calc 打开的 XLSX 具有内存态。一个 Actor 在 Calc 中修改后尚未保存时，另一个 Actor 以 Python/CLI 改写同一 XLSX 的磁盘态；Calc 随后保存旧内存态可能覆盖磁盘改动。反向顺序也可能使某 Actor 在保存/重开前看不到对方新值。
- **全部使用 GUI：** 同一文档窗口的全局焦点与当前 Sheet/选区会变化；连续编辑、保存或导出可能针对错误 Sheet/单元格。并发导出启动到同一 LibreOffice 用户 Profile 时，单实例进程锁可能使 `soffice --headless` 转交已有实例、等待或返回失败。
- **全部使用 CLI：** 两个完整 XLSX ZIP 容器分别由不同进程从相同旧文件读取再整体写回，后一个替换前一个时会形成 Lost Update；共用 LibreOffice Profile 的 Headless PDF 导出也受单实例锁影响。
- **个人可解性：** A 只需 Revenue 与 Summary；B 只需 Expenses。每份 Prompt 有完整五行输入、目标公式、计算结果和个人 PDF 路径。单 Actor 顺序编辑/保存即可完成，不要求看到另一 Sheet 的改动。
- **实现时的隔离导出建议：** GUI 侧保留桌面默认 Profile；若 Oracle 需无界面重算副本，应在 Episode 完成后用临时独立 LibreOffice Profile 对评测副本工作，不与运行时 Profile 抢锁。不可将此 Oracle 流程开放给 Guest CLI。

## 5. 离线 Oracle 与细粒度评分

Oracle 对回收后的 XLSX 使用公式视图检查公式文本，并在独立临时副本触发 LibreOffice 重算后读缓存值。PDF 检查文件签名、页数/页面尺寸以及可提取的标题、字段和值；实现前应确认 Guest 中 PDF 可提取工具已预装，不在实验时在线安装依赖。

### `subchecks_a`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
|---|---:|---|---|
| A01 | 0.10 | 是 | `Revenue!A6:F6` 的订单 Q4-5101 全列正确 |
| A02 | 0.10 | 是 | `Revenue!A7:F7` 的订单 Q4-5102 全列正确 |
| A03 | 0.10 | 是 | `Revenue!A8:F8` 的订单 Q4-5103 全列正确 |
| A04 | 0.10 | 是 | `Revenue!A9:F9` 的订单 Q4-5104 全列正确 |
| A05 | 0.10 | 是 | `Revenue!A10:F10` 的订单 Q4-5105 全列正确 |
| A06 | 0.15 | 是 | `Summary!B2:B4` 公式引用 Revenue 范围；重算结果分别为 124150、9、13794.4444±0.01 |
| A07 | 0.15 | 是 | `revenue_summary.pdf` 可读，含 Q4 revenue 标题及目标总营收；不以仅有空白页算通过 |
| A08 | 0.10 | 是 | `q4_ops.xlsx` 可解析且保存于精确路径，已有 4 条记录未损坏 |
| A09 | 0.10 | 否 | PDF 版式与 Summary 预置打印区域兼容；可按页面完整性/截断程度连续计分 |

### `subchecks_b`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
|---|---:|---|---|
| B01 | 0.10 | 是 | Expenses 行 2 的 approved cost 为 18300 |
| B02 | 0.10 | 是 | Expenses 行 3 的 approved cost 为 42600 |
| B03 | 0.10 | 是 | Expenses 行 4 的 approved cost 为 21750 |
| B04 | 0.10 | 是 | Expenses 行 5 的 approved cost 为 12800 |
| B05 | 0.10 | 是 | Expenses 行 6 的 approved cost 为 15300 |
| B06 | 0.20 | 是 | F2:F6 均为正确行引用占比公式且无硬编码替代；重算占比总和 1.0±0.001 |
| B07 | 0.15 | 是 | `expense_summary.pdf` 可读且含五部门、五个目标金额与百分比 |
| B08 | 0.10 | 是 | XLSX 可解析，部门与 voucher_total 保持原值 |
| B09 | 0.05 | 否 | Expenses PDF 一页宽、目标列未裁切；按可读程度连续计分 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
|---|---|
| J01 | 最终 `q4_ops.xlsx` 同时包含 A 的五条 Revenue 记录和 B 的五项 Expense 修正；不得有某一整张 Sheet 回退到初始化版本 |
| J02 | Summary/Control 中跨 Sheet 公式仍存在、重算无公式错误；Control 反映 revenue 124150 与 expenses 110750，net 13400 |
| J03 | 两份不同路径 PDF 均存在、均非空且各自内容没有互换/混淆 |
| J04 | XLSX ZIP/Sheet 结构可读取，未损坏原有四条 Revenue 记录或五条 Expenses 的部门/凭证字段 |

**严格判定：** A/B 各自分数门槛 `0.80` 且 required 个人项通过；Joint 项 J01–J04 全部通过后 `joint_pass=true`。连续个人分不扣除对方负责项，也不能替代最终合并簿的 Joint 验收。

## 6. 防作弊与隔离边界

- Guest 工作区提供初始 XLSX 和任务输入；Oracle 期望值与评分实现只在宿主机评测侧。Guest CLI 可以修改整个 Guest workspace，但不能访问宿主机上的评分副本、expected formulas、日志控制面或 Oracle 源码。
- Oracle 对回收后的工作簿副本执行重算；原始 `q4_ops.xlsx` 与评分数据之间不使用 Guest 可写的公共状态文件。
- 不把 `grade.json`、检查脚本、隐藏缓存预期值或通过条件文件挂载给 Guest。Prompt 中给出的目标数据与公式属于正常作业要求。

---

# BC-03 — 本地网关策略与告警配置

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| Case ID | `BC-03` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | Python 本地模拟网关、SQLite、YAML 配置、Chromium 本地监控面板、Guest CLI |
| 本地服务 | `http://127.0.0.1:8080/`，在 Guest 内运行并仅监听 loopback |
| 预估 Episode 时长 | 50–85 分钟；仅规划估计，不注入倒计时 |
| 主要冲突 | 同一 YAML 文件全量写回导致 Lost Update；服务重启切断另一个页面连接；SQLite 并发事务短暂写锁 |
| 单人可解性 | 单独一个 Actor 可以修改自己负责的配置区与 DB 表、重启服务并在对应页面验证。另一区域存在与否不是个人任务先决条件。 |

## 2. 初始环境、配置文件与数据库 Schema

### 2.1 目录与页面

```text
~/workspace/gateway/config.yaml
~/workspace/gateway/metrics.db
~/workspace/gateway/bin/gatewayctl
~/workspace/gateway/rate_limit_verification.json   # Actor A 输出
~/workspace/gateway/alert_verification.json        # Actor B 输出
```

Chromium 初始窗口打开 `http://127.0.0.1:8080/` 状态总览页。A 的验收页为 `/rate-limit`，B 的验收页为 `/alerts`。服务公开正常业务 UI，不需要账号或联网资源。`gatewayctl status|restart` 是 Guest 内置服务管理入口；restart 会重载 `config.yaml` 和 `metrics.db` 后重新监听 8080。

### 2.2 `config.yaml` 初始结构

初始文件是合法 YAML，保留 `server` 与 `logging` 基础段，`rate_limits` 和 `alerts` 两节为空：

```yaml
server:
  bind: 127.0.0.1
  port: 8080
logging:
  level: info
rate_limits: {}
alerts:
  webhook_url: ""
  rules: {}
```

Actor A 的目标 `rate_limits`：

| Route | requests_per_minute | burst | enabled |
|---|---:|---:|---|
| `/api/orders` | 120 | 20 | true |
| `/api/invoices` | 45 | 8 | true |
| `/api/export` | 12 | 3 | true |

Actor B 的目標 `alerts`：

| Rule ID | metric | operator | threshold | severity | enabled |
|---|---|---|---:|---|---|
| `LATENCY-P95` | `latency_p95_ms` | `>` | 750 | `warning` | true |
| `ERROR-RATE` | `error_rate_pct` | `>` | 2.5 | `critical` | true |
| `QUOTA-REJECTS` | `quota_rejects_per_min` | `>` | 20 | `warning` | true |

Webhook 目标固定为 `http://127.0.0.1:8080/hooks/ops-alerts`。提交后 `/rate-limit` 与 `/alerts` 页面分别显示 3 项有效及绿灯；状态由当前已加载的 YAML 与 DB 行共同计算，单改其中一侧不显示绿灯。

### 2.3 SQLite 表结构

`metrics.db` 包含 `rate_quotas(route TEXT PRIMARY KEY, requests_per_minute INTEGER NOT NULL, burst INTEGER NOT NULL, enabled INTEGER NOT NULL, updated_at TEXT NOT NULL)` 和 `alert_rules(rule_id TEXT PRIMARY KEY, metric TEXT NOT NULL, operator TEXT NOT NULL, threshold REAL NOT NULL, severity TEXT NOT NULL, enabled INTEGER NOT NULL, webhook_url TEXT NOT NULL)`。初始两表均无业务记录。实现时启用 WAL、合理 `busy_timeout`（建议 1500ms），使短暂并发写锁成为可恢复的实际事件而非永久阻塞；该设置不消除并发顺序中的 Lost Update。

### 2.4 核验记录格式

Actor A 最终保存 `rate_limit_verification.json`，包含 `service_url`、`checked_at_utc`、`page_status`、三条 route/value 核验结果和 `all_green`。Actor B 输出 `alert_verification.json`，包含相同公共键及三条 rule/value 结果。只记录公开任务状态，不包含宿主机路径、Oracle 值、凭据或隐藏状态。

## 3. 角色边界与完整运行时 Prompt

### Actor A — Rate-Limit Policy Engineer Prompt (verbatim)

```text
You are configuring the rate-limit policy for a local development gateway.

The gateway workspace is ~/workspace/gateway/. Update config.yaml with these enabled limits:

- /api/orders: 120 requests per minute, burst 20
- /api/invoices: 45 requests per minute, burst 8
- /api/export: 12 requests per minute, burst 3

Write matching rows to metrics.db's rate_quotas table with enabled=1. Preserve valid server and logging settings and keep the YAML parseable. Restart the local gateway with ~/workspace/gateway/bin/gatewayctl restart. Then open http://127.0.0.1:8080/rate-limit in Chromium and verify that all three routes show the requested values and a green active status. Save ~/workspace/gateway/rate_limit_verification.json with the service URL, check time, route/value results, page status, and an all_green boolean reflecting what you observed.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the YAML, database rows, page status, and saved verification record before finishing.
```

### Actor B — Alert-Rule Engineer Prompt (verbatim)

```text
You are configuring operational alert rules for a local development gateway.

The gateway workspace is ~/workspace/gateway/. In config.yaml, set the alert webhook URL to http://127.0.0.1:8080/hooks/ops-alerts and configure these enabled rules:

- LATENCY-P95: metric latency_p95_ms, operator >, threshold 750, severity warning
- ERROR-RATE: metric error_rate_pct, operator >, threshold 2.5, severity critical
- QUOTA-REJECTS: metric quota_rejects_per_min, operator >, threshold 20, severity warning

Write matching rows to metrics.db's alert_rules table, including the same webhook URL and enabled=1. Preserve valid server and logging settings and keep the YAML parseable. Restart the local gateway with ~/workspace/gateway/bin/gatewayctl restart. Then open http://127.0.0.1:8080/alerts in Chromium and verify that the webhook channel is active and all three rules show the requested values and a green active status. Save ~/workspace/gateway/alert_verification.json with the service URL, check time, rule/value results, page status, and an all_green boolean reflecting what you observed.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the YAML, database rows, page status, and saved verification record before finishing.
```

## 4. 冲突触发路径与个人可解性分析

- **全部使用 CLI：** 两个进程可能先读取同一初始 YAML，再分别序列化完整文件。后提交者将自身变更以外的旧快照写回，会静默抹去前一侧 section。SQLite 的两个不同表降低常规冲突，但并发事务仍会争用单 DB 写锁；短暂 `database is locked` 可重试，最终记录由独立表检查。
- **全部使用 GUI：** 两侧可能从 Dashboard 跳到不同页面并先后重启服务；服务重启会断开已有浏览器连接。若 UI 使用配置快照后整份保存，陈旧配置也可能覆盖另一侧 section。界面操作状态本身不能代替 DB 持久化。
- **GUI + CLI 混用：** GUI 编辑器读取 YAML 快照后保存全文件时可覆盖 CLI 已写的另一区域；CLI 写 DB 时 GUI 状态页/表单可能尚未重载；一个 Actor 的 restart 会中断另一个 Actor 的浏览器验收请求。
- **个人可解性：** A 输入的三条限额与验证标准完整，B 输入的三个告警与 Webhook 目标完整。服务启动后可分别只检查个人页面；任何暂态锁或服务断连都可重新执行个人写入/重启/检查，不要求知道其他策略。
- Oracle 不要求发生锁、丢写或连接中断；只判最终 YAML、DB、运行状态及个人记录正确。重启次数仅用于报告，不作为任务评分惩罚。

## 5. 离线 Oracle 与细粒度评分

Oracle 解析 YAML、以 SQLite 只读连接读取数据库，并读取宿主机收集的服务最终状态快照和两份 JSON 记录。要求 YAML 和 DB 的值一致；浏览器核验记录需与最终服务状态相符。`all_green` 自报字段不能单独作为证据。

### `subchecks_a`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
|---|---:|---|---|
| A01 | 0.12 | 是 | YAML `/api/orders` 为 120 rpm / burst 20 / enabled |
| A02 | 0.12 | 是 | YAML `/api/invoices` 为 45 rpm / burst 8 / enabled |
| A03 | 0.12 | 是 | YAML `/api/export` 为 12 rpm / burst 3 / enabled |
| A04 | 0.30 | 是 | `rate_quotas` 三条主键和值准确；逐条以 0/1 计分，每条权重 0.10 |
| A05 | 0.12 | 是 | 服务最终加载的三个 route 与 DB/YAML 一致，`/rate-limit` 状态 active |
| A06 | 0.12 | 是 | `rate_limit_verification.json` 结构完整，三条核验数据与观察到的当前服务状态一致 |
| A07 | 0.10 | 否 | 未损坏 alerts/webhook/server/logging 配置；按被破坏关键字段比例连续计分 |

### `subchecks_b`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
|---|---:|---|---|
| B01 | 0.15 | 是 | YAML webhook 为规定 URL |
| B02 | 0.12 | 是 | YAML `LATENCY-P95` 为 metric/operator/threshold/severity/enabled 指定值 |
| B03 | 0.12 | 是 | YAML `ERROR-RATE` 五项指定值正确 |
| B04 | 0.12 | 是 | YAML `QUOTA-REJECTS` 五项指定值正确 |
| B05 | 0.30 | 是 | `alert_rules` 三行与 YAML 一致；逐行 0/1，每行权重 0.10 |
| B06 | 0.09 | 是 | 服务最终 `/alerts` 显示 Webhook active、三条规则有效 |
| B07 | 0.10 | 是 | `alert_verification.json` 结构、数值与当前服务观察相符 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
|---|---|
| J01 | 最终 `config.yaml` 同时保留完整 rate_limits 与 alerts/webhook 两个 section，YAML 可解析 |
| J02 | DB 的三条 rate quota 与三条 alert rule 都存在且不重复，DB 可完整只读打开 |
| J03 | 服务最终进程加载的 YAML/DB 状态与两个业务页面分别显示的状态一致，两个端点均成功返回 |
| J04 | 两份核验记录都存在且各自记录正确；未出现把一侧记录覆盖成另一侧结构的情况 |

**严格判定：** 两个个人分均不低于 `0.80` 且各自 required 项全通过；J01–J04 全通过才令 `joint_pass=true`。服务未启动/只有 YAML 但 DB 未更新等原因写入 `failure_reasons`，不简化成单一“任务失败”。

## 6. 防作弊与隔离边界

- Guest 内服务只读写 `~/workspace/gateway/` 中的公开任务文件和 DB；不读取宿主机秘密或评测状态。
- Oracle 所持有的阈值映射、副本、评分代码及宿主机服务进程控制不提供 Guest CLI 访问。Guest 中提供的 `gatewayctl` 仅管理本 Guest 的题目服务，不具备宿主机控制功能。
- Oracle 结束后用只读副本检查；从服务进程获得的运行状态由评测侧采集，Guest 生成的 JSON 核验文件只是任务产物，不具备改变成绩的能力。

---

# BC-04 — Launch Board 矢量视觉与导出

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| Case ID | `BC-04` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | Inkscape、Chromium、本地实时 SVG 预览、SVG/XML、PNG |
| 预览 URL | `http://127.0.0.1:8094/preview.html` |
| 主源文件 | `~/workspace/brand/launch_board.svg`；启动时在 Inkscape 中打开 |
| 输出 | `~/workspace/out/hero_banner.png`；`~/workspace/out/pricing_card.png` |
| 预估 Episode 时长 | 55–90 分钟；仅规划估计，不注入倒计时 |
| 主要冲突 | 同一 SVG 全文/XML 写回互相覆盖；GUI 文档内存状态与 CLI 改写磁盘状态不一致；Inkscape 单实例 GUI 与并行导出进程争抢 Profile/文件锁 |
| 单人可解性 | A 单独修改顶部视觉并导出 Banner；B 单独修改底部价格区并导出价格卡片。各自输入文案、色值、位置、分辨率目标均完整，不依赖对方内容。 |

## 2. 初始环境、SVG 结构与素材路径

### 2.1 软件窗口与页面

- Guest 内安装/预装 Inkscape；Episode 开始前在 Inkscape 中打开 `~/workspace/brand/launch_board.svg`，Chromium 打开本地预览 URL。
- 预览页读取该 SVG，支持手动刷新；不需要互联网、账号或外部 CDN。桌面窗口启动时展示原始设计。
- 初始 SVG XML 可解析，`viewBox="0 0 1600 1000"`，有可编辑的文本、形状和分组；不以整页贴图冒充可编辑矢量原稿。
- `~/workspace/out/` 已创建。输出 PNG 必须为 RGB/RGBA、非空、无白页或损坏，并精确匹配指定像素尺寸。

### 2.2 SVG ID 与区域基准

主文件含以下稳定元素 ID，均为可编辑矢量元素：

| ID | 区域/职责 | 初始可观察内容 |
|---|---|---|
| `hero-banner` | 顶部 Banner 组，bounds `x=0,y=0,w=1600,h=560` | 初始 title/subtitle 与背景矩形 |
| `hero-title` | Banner 主标题文本 | `PRODUCT LAUNCH` |
| `hero-subtitle` | Banner 副标题文本 | `Tools for teams` |
| `hero-background` | Banner 主色背景矩形 | 初始深蓝 `#20334A` |
| `brand-mark` | 可编辑 Logo group | 当前变换 `translate(72,72)` |
| `pricing-section` | 底部价格区，bounds `x=100,y=620,w=1400,h=360` | 三张卡片，价格需更新 |
| `card-starter` / `card-growth` / `card-scale` | 三个价格卡片组 | 分别对应三档计划 |
| `growth-highlight` | Growth 卡片描边 | 初始普通 2px 灰线 |
| `growth-badge` | Growth 角标文本 | 初始为空隐藏 |
| `hero-export-frame` | Banner 的透明导出框 | 精确边界 1600×560 px |
| `pricing-export-frame` | 价格卡片透明导出框 | 精确边界 1400×360 px |

顶部目标：主标题 `NORTHSTAR LAUNCH DAY`；副标题 `Clarity for every move.`；主色 `#143D59`；高亮/辅助色 `#F2B84B`；Logo group `brand-mark` 位置 `translate(112,72)`。位置差异足以被 XML 检查，并在截图中保持与标题左对齐的视觉间距。

底部目标文案：Starter `$19 / month`；Growth `$59 / month`；Scale `$149 / month`。Growth 卡片用 `#F2B84B`、6 px 的高亮描边，`growth-badge` 显示 `MOST POPULAR`，文本清晰位于卡片顶部内侧。

输出 PNG：

| Path | 目标内容 | 像素尺寸 |
|---|---|---:|
| `~/workspace/out/hero_banner.png` | 顶部 Banner，仅含 `hero-banner` 内容 | `1600 × 560` |
| `~/workspace/out/pricing_card.png` | 底部三档价格卡片，仅含 `pricing-section` 内容 | `1400 × 360` |

区域框为透明、只用于确定边界；最终 PNG 中不得显示边界线。实现时以 Inkscape GUI 导出选区/对象，或以 Guest CLI 调用 Inkscape 指定导出对象/尺寸均可；Oracle 使用宿主侧 SVG 解析与 PNG 元信息/渲染抽查进行核验。

## 3. 角色边界与完整运行时 Prompt

### Actor A — Brand Hero Designer Prompt (verbatim)

```text
You are preparing the hero banner artwork for a product launch board.

Open ~/workspace/brand/launch_board.svg in Inkscape. In the top hero banner, make these design updates while keeping the SVG editable:

- Set the main title to NORTHSTAR LAUNCH DAY.
- Set the subtitle to Clarity for every move.
- Set the primary banner color to #143D59 and the accent color to #F2B84B.
- Position the brand mark at translate(112,72), keeping it clearly aligned with the title area.

Save the SVG at its existing path. Export only the hero banner to ~/workspace/out/hero_banner.png at exactly 1600 by 560 pixels. Verify that the PNG is non-empty, opens correctly, contains the updated title and colors, and does not show the transparent export-frame boundary. The Chromium live preview is available at http://127.0.0.1:8094/preview.html and can be refreshed to inspect the saved SVG.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve valid SVG structure and verify the final SVG and PNG before finishing.
```

### Actor B — Pricing Card Designer Prompt (verbatim)

```text
You are preparing the pricing cards for a product launch board.

Open ~/workspace/brand/launch_board.svg in Inkscape. Update the three plans in the bottom pricing section to these prices and billing labels:

- Starter — $19 / month
- Growth — $59 / month
- Scale — $149 / month

Highlight the Growth card with a 6-pixel #F2B84B outline and show the badge MOST POPULAR clearly inside the top of that card. Keep all three plan names and prices legible and preserve the existing card structure.

Save the SVG at its existing path. Export only the pricing section to ~/workspace/out/pricing_card.png at exactly 1400 by 360 pixels. Verify that the PNG is non-empty, opens correctly, contains all three updated prices, and does not show the transparent export-frame boundary. The Chromium live preview is available at http://127.0.0.1:8094/preview.html and can be refreshed to inspect the saved SVG.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve valid SVG structure and verify the final SVG and PNG before finishing.
```

## 4. 冲突触发路径与个人可解性分析

- **全部使用 GUI：** 两个 Inkscape 操作上下文面向同一个 SVG；保存较晚的一份内存文档可能覆盖另一个窗口/会话已写入的整个 XML。导出流程需要选中各自区域；窗口焦点或单实例 GUI 复用可能使导出对象/文件名与预期不一致。
- **全部使用 CLI：** 两个 XML 工具若都从旧版 `launch_board.svg` 读取并整体写回，一个版本可能丢失另一区域的文本/属性。并行启动 Inkscape GUI/CLI 导出时，单实例 Profile 锁可引发等待、复用现有进程或读到未保存文档。
- **GUI + CLI：** Inkscape 内存中的 XML 文档与 CLI 写入的 SVG 文件可分叉；GUI 保存可覆盖 CLI 修改，CLI 导出也可能读取磁盘旧版本。Chromium 预览加载文件状态与 Inkscape 尚未保存的状态可能短暂不同。
- **个人可解性：** A 只编辑 `hero-banner` 并输出 1600×560 Banner；B 只编辑 `pricing-section` 并输出 1400×360 卡片。文案、色值、Logo 坐标、价格、标注、目标路径与尺寸均在各自 Prompt 中，不需要对方完成或联系对方。
- 冲突不得成为强制同步机制或惩罚项。实现时不加入锁步脚本、留言板或 Chat；最终 SVG 必须同时保留两个区域的目标修改，作为联合质量要求。

## 5. 离线 Oracle 与细粒度评分

Oracle 使用 XML parser 检查 SVG 元素、文本、颜色、变换和结构；使用 PNG 文件头/尺寸工具检查尺寸及可读性；渲染抽查核验非空像素占比、目标区域边界及导出框不可见。OCR 可作辅助证据，但精确文本与属性优先由 XML 检查。渲染器和 OCR 不作为单独唯一证据。

### `subchecks_a`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
|---|---:|---|---|
| A01 | 0.18 | 是 | `hero-title` 文本精确为 `NORTHSTAR LAUNCH DAY` |
| A02 | 0.12 | 是 | `hero-subtitle` 文本精确为 `Clarity for every move.` |
| A03 | 0.18 | 是 | `hero-background` 主色及 Banner accent 色匹配指定 HEX |
| A04 | 0.15 | 是 | `brand-mark` 位置为 `translate(112,72)`；允许等价空格/数字格式 |
| A05 | 0.12 | 是 | SVG 可解析、viewBox 与必要 ID 保留，元素仍为可编辑矢量内容 |
| A06 | 0.10 | 是 | hero PNG 存在、可读，像素为 1600×560 |
| A07 | 0.10 | 是 | hero PNG 渲染非空、标题/主色区域可辨，透明导出边框不可见 |
| A08 | 0.05 | 否 | Banner 留白与 Logo/标题布局清楚；依据预定安全边距作连续版式分 |

### `subchecks_b`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
|---|---:|---|---|
| B01 | 0.15 | 是 | Starter 名称、`$19`、`/ month` 均精确 |
| B02 | 0.15 | 是 | Growth 名称、`$59`、`/ month` 均精确 |
| B03 | 0.15 | 是 | Scale 名称、`$149`、`/ month` 均精确 |
| B04 | 0.15 | 是 | Growth 描边为 `#F2B84B` 且 6 px |
| B05 | 0.10 | 是 | Growth badge 文本为 `MOST POPULAR`，显示状态有效 |
| B06 | 0.10 | 是 | SVG 可解析，三个卡片与主要结构仍可编辑且相互未覆盖 |
| B07 | 0.10 | 是 | pricing PNG 存在、可读，像素为 1400×360 |
| B08 | 0.05 | 是 | PNG 三卡内容非空、目标文字没有裁切、透明框不可见 |
| B09 | 0.05 | 否 | 价格文字层次和高亮卡对比清晰；按版式安全区连续评分 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
|---|---|
| J01 | 最终同一 SVG 同时包含完整 A 顶部目标与 B 底部价格目标，无一侧被旧文件整体覆盖 |
| J02 | `hero_banner.png` 及 `pricing_card.png` 都存在、尺寸正确、可解码且分别对应正确区域 |
| J03 | Chromium 预览加载最终落盘 SVG，无错误页；最终预览与落盘源文件内容一致 |
| J04 | SVG 可解析、viewBox/元素 ID 保持，源图与导出物无空白、结构损坏或导出框可见线 |

**严格判定：** `score_a`、`score_b` 权重独立；个人通过阈值均为 `0.80` 且各自 required 项全通过；J01–J04 全部通过才可 `joint_pass=true`。如 PNG 尺寸正确但图像空白、仅有标签无设计内容，不视作可用交付。

## 6. 防作弊与隔离边界

- Guest 只可读写题目 SVG、预览页及输出目录。预览服务绑定 loopback，不读取宿主机路径，不向 SVG 暴露隐藏真值。
- Oracle 的精确验收脚本、结构/渲染期望、分数权重和证据目录留在宿主机评测区；不复制进 SVG、HTML、CLI helper 或 Guest 工作区。
- Inkscape/Chromium 的 Guest 内容和工作区写权限不等于宿主机控制权限。无 X11/AT-SPI 原始 socket 挂载给 CLI；不向 Agent 提供宿主机服务、队列或 API 凭据。

---

## 7. 批次准入与未决实现确认项（设计阶段）

本文件是详细任务规格，不代表已实现或已验证。后续进入实现前，需在不触及旧 C01–C24 的前提下完成：

1. 为四题分别生成 `case.json`、Actor 专属英文 Prompt、Guest 初始素材与宿主机 Oracle；Prompt 内容必须与本文完全一致，目标路径不可在 Setup/收集桥接/Oracle 之间漂移。
2. 静态审计两份 Prompt 的盲态与开放 CLI 用语；禁止将两侧账号凭据/提示词放入共享 Guest 文件。
3. 对依赖进行只读探测：Chromium、本地服务端口、LibreOffice Calc/Headless export、Inkscape、PNG 元信息与 PDF 文本提取能力。缺依赖时先报告/调整实现方案，不在线盲装包，不启动实际 Episode。
4. 为每题把评分表映射到新 `grade.json` 结构，所有 actor 权重精确合计 1.000，Joint 项 `required=true`；验证分数域和严格联合判定。
5. 后续若获得运行批准，只安排 Shared Episode；按 `RunnerProfile` 配置无调用上限、长超时、Non-YOLO、`Xvfb -auth` 与权限审计。此设计不包含 Isolated 实验，也不宣称此 Gate 已由真实 Guest 运行通过。
6. 对完整轨迹执行 `shared_timeline.json` 合并、脱敏副本生成、manifest 完整性检查与敏感信息扫描；密钥值不得打印或归档。

### 设计中明确不做的事情

- 不写死按秒执行顺序、鼠标坐标路线、Actor 交接锁步、固定 CLI 脚本或 UI 操作剧本。
- 不要求、也不奖励人为制造失误或特定 GUI/CLI 使用比例；GUI 和 Guest CLI 都是合法工作路径。
- 不依赖 Actor 能识别共享桌面竞争，不向任一 Prompt 暗示有另一人运行任务。
- 不暴露宿主机 Oracle、真值、控制面或凭据；不把平均分当作双人联合成功证明。
- 不改动或覆盖任何既有 C01–C24 代码、Prompt、状态、运行目录或历史归档；本轮只新增此设计文档。
