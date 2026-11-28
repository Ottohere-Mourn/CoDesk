# BC-09–BC-16 Blind Concurrency Batch — Detailed Design v1

**状态：** 设计稿，待人工审核；本文件不包含 Case 实现代码、Guest 素材或 Oracle 实现。  
**范围：** 仅覆盖 BC-09 至 BC-16。BC-05–BC-08 以 `C:\Users\33114\Downloads\blind_concurrency_batch_2_upgraded_bc_05_bc_08_v2.md` 为既有设计来源，本文件不重复复制或修改它们。BC-04 改用 GIMP 的议题不在本批处理范围内。  
**设计依据：** `case_work/20261126-shared-case-pipeline-v1/templates/blind_task.md`、同目录 `README.md`、仓库级 `docs/AUDIT_SENIOR_ALIGNMENT.md`、`docs/BC_ENVIRONMENT_PROBE_20261126.md` 与 BC-05–BC-08 设计稿。  
**证据边界：** 本文件只使用已探测 Guest 的 Google Chrome（可执行名 `google-chrome`）、LibreOffice、GIMP、Git、VS Code、Python 3.10.12、PyYAML、sqlite3、Pillow 与 `pdftotext`。不依赖 Chromium 命令、Inkscape、openpyxl、pypdf、pdfplumber 或 PyMuPDF；所有 Excel OOXML 需求使用标准库 `zipfile` / `xml.etree.ElementTree` 或 LibreOffice。步数仅为负载设计目标，不写入 Runner 限制，也不作为任务倒计时。

## 0. 批次级设计契约

### 0.1 盲态、输入隔离与可解性

- 每个 Episode 仅为 `shared`，Actor A 与 Actor B 各收到单独的英文 Prompt；不运行 Isolated 对照。
- 任何运行时 Prompt 不告知有同伴、共用桌面、他人操作、焦点争抢、共享文件或对方进度。文档下文的冲突分析属于作者规格，不注入 Prompt。
- 每个角色只获得其分配的输入材料、账号/凭据和输出路径。运行器不把对方 Prompt、凭据、私有输入目录或 Oracle 挂入该角色的 Guest CLI 挂载。私有输入以 Actor UID 做目录权限隔离；可共同编辑的主文件放在双方均有 Guest workspace 写权限的项目目录。Local web UI 如有登录，以角色独立凭据登录且每份 Prompt 只出现本角色凭据。
- 输入隔离不等于依赖对方操作：任一 Actor 独自获得其材料时即可完成自己的目标；对方任务未开始、失败或尚未保存均不得成为单侧完成的前置条件。
- 如果正式 Runner 无法提供彼此独立的 Guest CLI UID / role-private mount，则不应把此批规格直接实现或声称满足“账号/凭据/输入严格隔离”；先在实现准入审查中补齐该能力。

### 0.2 Runner 与归档契约

| 项 | 本批全部 Case 的设计值 |
|---|---|
| 模式 | `shared` only；一台 Guest 上两个 Actor |
| 步数 / CUA 调用上限 | 不设；`max_cua_calls = None` |
| 外层超时 | `>= 7200s`；不向 Agent 注入倒计时 |
| GUI / Guest CLI | 两者都开启；CLI 在 Guest workspace 有读、写、执行能力；可任意 GUI、CLI 或混用 |
| 显示与权限 | `Xvfb -auth <auth-file>`；禁止 `-ac`；Non-YOLO；不挂载 Oracle、真值、控制面、宿主机 Shell 或原始 X11/AT-SPI socket |
| 权限审计 | 每角色 episode 后写 `permission-audit-verified.json`，核验实际 UID、role-private mount、sandbox、approval 和 `turn_context` |
| 轨迹 | 双 Actor `actions.jsonl`、`codex_events.jsonl`、共享 `shared_timeline.json`、`grade.json`、`report.json` 与 manifest |

运行时通用英文工具说明（每条 Prompt 均包含，不含共享桌面/同伴陈述）：

> You may choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.

### 0.3 统一连续评分口径

各 Case 表中的 `subchecks_a`、`subchecks_b`、`subchecks_joint` 分别写入脚手架 `grade.json` 的 `subchecks.actor_a`、`subchecks.actor_b`、`subchecks.joint`。每侧个人权重精确合计 `1.000`；阈值 `0.80`。每个 personal required 检查通过条件须全部满足且加权分达到阈值，才令 `pass_a` / `pass_b=true`。`score_a`、`score_b` 为个人连续加权分，`mean_score=(score_a+score_b)/2`。Joint 子项全部 `required=true`，统一判定：

`joint_pass = pass_a AND pass_b AND all(subchecks_joint.passed)`。

不得用均分掩盖任一方失败。Optional 子项只贡献连续分，不改变个人 required 门槛。Oracle 留在宿主机，只读取回收产物与 Runner 提供的只读服务快照。

---

# BC-09 — Q4 路演 KPI 精算与共享演示文稿

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | LibreOffice Impress（ODP）、SQLite、CSV、Pillow、PDF / `pdftotext` |
| 复杂度目标 | 每角色约 60–90 个有效操作：脏数据筛选和财务/产品指标推导、多图生成、演示文稿内容与备注编辑、PDF 双重校验 |
| 单人可解性 | 财务源数据与产品源数据、规则和目标页彼此独立；Actor 单独执行不需另一人的输入或产物 |
| 核心冲突 | Impress 内存态覆盖磁盘 ODP；相同 ODP ZIP 包全量写回；页导航/焦点交错；LibreOffice 单实例 Profile 锁与并发 PDF 导出 |

## 2. 初始环境、路径与数据

Guest 主目录 `~/workspace/board/`。运行开始时 Impress 已打开 `q4_board_deck.odp`（8 页：封面、Executive Summary、Revenue by Region、Margin Bridge、Cohort Retention、Service Reliability、Product Summary、Appendix）；图表页均有明确占位框。Chrome 不预开。文件结构：

| 路径 | 内容 |
|---|---|
| `~/workspace/board/q4_board_deck.odp` | 有效 8 页 ODP，现有主题、母版和页脚须保留 |
| `~/workspace/board/private/actor_a/transactions.db` | `transactions(txn_id,date,region,currency,gross_amount,cost_amount,txn_type,status,is_test,reference_id)` 与 `fx_rates(currency,usd_rate,valid_from,valid_to)`；含重复导入、退款/冲红、测试和 VOID 干扰项 |
| `~/workspace/board/private/actor_b/cohort_events.csv` | `user_id,cohort_month,event_date,event_name,is_test,source_tag`；含机器人、测试账号、重复事件与预注册未激活用户 |
| `~/workspace/board/private/actor_b/api_telemetry.csv` | `sample_id,timestamp,service,latency_ms,status_code,environment`；含 synthetic、错误响应和缺测行 |
| `~/workspace/board/private/actor_a/metric_rules.pdf`、`~/workspace/board/private/actor_b/metric_rules.pdf` | 分别说明财务口径与产品指标/图表规则；不向另一角色注入 |
| `~/workspace/board/out/finance_metrics.json`, `finance_chart.png`, `finance_brief.pdf` | Actor A 交付 |
| `~/workspace/board/out/product_metrics.json`, `product_chart.png`, `product_brief.pdf` | Actor B 交付 |

数据生成必须固定种子、固定日期窗与 FX 有效区间，使宿主 Oracle 可独立重算。财务规则定义：只取目标 Q4 日期内、正式入账且非测试的 sale/refund/reversal；冲销以符号方向折算；按交易日期匹配有效 FX，金额转 USD 并四舍五入至分；按规则 PDF 定义的区域汇总净收入、净成本和毛利率。产品规则定义 cohort 分母、D7/D30 活跃窗口与分位数采用 nearest-rank；只纳入有效 production 用户、成功响应和非 synthetic 遥测。Prompt 不给出统计答案，只指向相应私有来源与规则。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Revenue and Margin Analyst

**职责边界：** 负责财务数据过滤、FX 折算、区域营收/毛利率、finance 图表、演示文稿第 2–4 页的财务内容与讲者备注，以及财务 PDF / JSON。不得改主题母版、产品页或附件页。

**Prompt 原文：**

```text
You are preparing the Q4 revenue and margin section of ~/workspace/board/q4_board_deck.odp, which is open in LibreOffice Impress.

Read ~/workspace/board/private/actor_a/metric_rules.pdf and query ~/workspace/board/private/actor_a/transactions.db. Apply the document's Q4 date, posting-status, test-record, refund/reversal-sign, and FX-effective-date rules. Calculate net USD revenue, net USD cost, and gross-margin percentage for every required region. Record the filter counts, per-region results, rounding method, and source transaction IDs in ~/workspace/board/out/finance_metrics.json.

Create a clear region-comparison chart as ~/workspace/board/out/finance_chart.png using the calculated results. Update the financial KPI text, chart placeholder, and speaker notes on slides 2–4 of q4_board_deck.odp. Preserve the deck's existing theme, page order, and material outside the financial section. Save the presentation, export the financial pages as ~/workspace/board/out/finance_brief.pdf, and verify the PDF text and chart are readable.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Product Cohort and Reliability Analyst

**职责边界：** 负责有效用户 cohort 留存与 production API 延迟指标、产品图表、演示文稿第 5–7 页的产品内容与讲者备注，以及产品 PDF / JSON。不得改主题母版、财务页或附件页。

**Prompt 原文：**

```text
You are preparing the Q4 product retention and reliability section of ~/workspace/board/q4_board_deck.odp, which is open in LibreOffice Impress.

Read ~/workspace/board/private/actor_b/metric_rules.pdf, ~/workspace/board/private/actor_b/cohort_events.csv, and ~/workspace/board/private/actor_b/api_telemetry.csv. Apply the stated cohort eligibility, D7/D30 observation windows, duplicate/test-user filters, production-only filter, valid-response filter, and percentile convention. Calculate the required cohort sizes, D7 and D30 retention percentages, and production latency percentile metrics. Record filter counts, calculation conventions, and source identifiers in ~/workspace/board/out/product_metrics.json.

Create a clear retention/reliability chart as ~/workspace/board/out/product_chart.png using your calculated results. Update the product KPI text, chart placeholder, and speaker notes on slides 5–7 of q4_board_deck.odp. Preserve the deck's existing theme, page order, and material outside the product section. Save the presentation, export the product pages as ~/workspace/board/out/product_brief.pdf, and verify the PDF text and chart are readable.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** 一方用 Pillow/SQLite 处理数据时，另一方可在 Impress 修改同一 ODP；各自保存时 ODP ZIP 包可能按较旧磁盘快照全量替换。页签切换可让输入落入另一页；一方的 `soffice --headless` 导出也会争用 LibreOffice Profile。
- **全 GUI：** 两边在同一个多页 ODP 中跳页、插入图表和保存，会触发内存态覆盖与焦点漂移；范围导出对话框也会被另一侧的保存/导出打断。
- **全 CLI：** SQLite/CSV 计算很容易并行，但 ODP 包仍需完整改写或经 LibreOffice 转 PDF；并发全量改包仍然会丢失另一页的内容，且两个 headless LibreOffice 导出可能共享实例/Profile。CLI 不能消除共享文件的写入竞争。

## 5. 离线 Oracle 与 `grade.json` 检查点

个人子项权重均合计 `1.000`；个人阈值 `0.80`。Oracle 从 Guest 回收 ODP/PDF/PNG/JSON，独立重算 SQLite/CSV 指标；以 ODP package/XML 文本、notes、嵌入图像、PDF 页文本与 PNG 尺寸/可读性核验交付。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | `finance_metrics.json` 的清洗计数、FX 日期、区域净收入/净成本/毛利率及交易引用均符合 Oracle 重算 |
| A02 | 0.18 | 是 | 第 2–4 页财务标题、数值/单位、区域标签和必要口径注释正确 |
| A03 | 0.16 | 是 | 财务图像 PNG 可读，区域系列/图例与 JSON 数值一致；未使用无关产品数值 |
| A04 | 0.18 | 是 | ODP 对应财务页包含讲者备注且关键信息与指标 JSON 一致 |
| A05 | 0.18 | 是 | `finance_brief.pdf` 有效，含目标页文本及完整图表页；可由 `pdftotext` 检出必要标签/指标 |
| A06 | 0.10 | 否 | ODP 可正常解析；主题、封面和第 8 页附件内容未损坏 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | `product_metrics.json` 的有效 cohort、D7/D30 留存、p95 等结果由 Oracle 独立重算一致 |
| B02 | 0.18 | 是 | 第 5–7 页 cohort / reliability 文字、数值、单位和样本口径正确 |
| B03 | 0.16 | 是 | 产品图像 PNG 可读，cohort / latency 序列与 JSON 一致 |
| B04 | 0.18 | 是 | ODP 产品页含讲者备注且与指标 JSON 及规则一致 |
| B05 | 0.18 | 是 | `product_brief.pdf` 有效，含目标页、图表与可提取的指标标签 |
| B06 | 0.10 | 否 | 产品图例、坐标轴和注释无明显越界、重叠或缺字 |

### `subchecks_joint`（全部 required）

| ID | 权重 | 判定 |
|---|---:|---|
| J01 | 1.000 | 最终 ODP 同时保留 A 的第 2–4 页与 B 的第 5–7 页更新，底稿和第 8 页仍完整 |
| J02 | 1.000 | 两份独立 PDF、图像和 JSON 均存在、有效且内容没有互换 |
| J03 | 1.000 | 最终 ODP ZIP、content.xml、notes 与嵌入图像可解析；关键数值、备注和图像跨产物一致 |

## 6. 防作弊与隔离边界

Actor A 的交易库/财务规则与 Actor B 的 cohort/telemetry/产品规则分属 role-private mount；不向任何 Guest 暴露另一侧输入、完整双侧 Prompt、Oracle 或真值。共享 ODP 仅作为最终工作产物；Oracle 独立从宿主机私有 fixture 重算目标值。Actor CLI 可读写其分配的 Guest workspace，不可读写宿主机评测目录、Runner 或控制面。

---

# BC-10 — 邮件线程清洗与两阶段会议室排期

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | `google-chrome` 本地 Maildesk/Calendar、`.ics`、SQLite、CSV、规则 PDF、JSON |
| 本地入口 | `http://127.0.0.1:18110/`；Chrome 已打开 Calendar 首页 |
| 复杂度目标 | 每角色约 55–85 个有效操作：筛邮件线程、辨别取消/改期、按时区和设备要求匹配房间、预览冲突、纠正后确认并校验 |
| 单人可解性 | 两组邮件线程与目标会议互不依赖；每组均存在符合全部规则的房间/时间方案 |
| 核心冲突 | `.ics` 整文件替换造成 VEVENT 丢失；热门房间槽位同时被预订；Phase 1 token/revision 过期；Chrome Calendar 视图/焦点争用 |

## 2. 初始环境、路径与数据

Guest 项目根为 `~/workspace/calendar/`；Calendar 服务只绑定 `127.0.0.1:18110`，提供 `/mail`, `/calendar`, `/preview`, `/confirm` 与 `/health` 页面/API。服务启动时读取 ICS 与 DB；预览后返回与 ICS revision 绑定的 opaque token，确认必须使用该 token。token 无倒计时或短 TTL；若文件 revision 改变，服务返回明确的 stale-revision 错误并允许刷新后再次预览。该设计避免长推理时间让 token 自然过期。

| 路径 | 数据/用途 |
|---|---|
| `~/workspace/calendar/team_schedule.ics` | 基础既有会议 VEVENT，存 UTC DTSTART/DTEND、UID、ROOM、ATTENDEE 与摘要 |
| `~/workspace/calendar/rooms.db` | `rooms(room_id,capacity,features,building)`、`reservations(uid,room_id,start_utc,end_utc,status,owner_ref)`、`preview_tokens(token,revision,status)` |
| `~/workspace/calendar/private/actor_a/mail_threads.csv` | A 专属客户评审邮件线程，含原邀、取消、较新改期、时区说明及无效草案 |
| `~/workspace/calendar/private/actor_b/mail_threads.csv` | B 专属培训/支持排期线程，含取消、确认、改期与冲突偏好 |
| `~/workspace/calendar/private/actor_a/room_policy.pdf`、B 对应规则 PDF | 容量、会议室设备、可用时段、显式 UTC offset 换算表、通知与保留政策 |
| `~/workspace/calendar/out/calendar_audit.json`、`calendar_export_a.ics` | A 的会议核验摘要与独立导出 |
| `~/workspace/calendar/out/calendar_b_audit.json`、`calendar_export_b.ics` | B 的会议核验摘要与独立导出 |

每侧邮件源有约 24 封消息，含 3 个目标会议和多封干扰消息；对每个 thread 以最新非取消版本为准。日期使用 2026-12 月固定时区偏移表，避免依赖未探测的第三方时区库。两侧每人最终安排 3 个事件，1 个事件至少要根据容量或设备在两个合规房间之间选择。Phase 1 在不提交预约的情况下返回冲突/可选房间和当前 revision token；Actor 重新确认完整 3 项后 Phase 2 才写入 reservations 与 `.ics`。双方单独运行时均有唯一规则可推导的合规安排；共享运行中可按服务器实时结果改选替代房间。

## 3. 角色目标与完整 Prompt

### Actor A — Customer Review Scheduler

```text
You are scheduling the Q4 customer review meetings in the local calendar at http://127.0.0.1:18110/.

Read ~/workspace/calendar/private/actor_a/room_policy.pdf and ~/workspace/calendar/private/actor_a/mail_threads.csv. For each requested meeting, use the latest non-cancelled message in its thread, resolve the stated local time to UTC using the supplied offset table, and select an available room satisfying the required capacity and equipment. Ignore superseded, cancelled, draft, and test messages.

Enter the three valid meetings in Calendar and submit a Preview. Review the returned availability or validation findings, correct the schedule when needed, and submit Confirm against the current preview token. Verify that the confirmed events appear with the intended UTC time, room, attendee, and duration. Save ~/workspace/calendar/out/calendar_audit.json with the three source thread IDs, chosen rooms, UTC intervals, and final confirmation IDs, and export the confirmed events to ~/workspace/calendar/out/calendar_export_a.ics.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Training and Support Scheduler

```text
You are scheduling the Q4 training and support sessions in the local calendar at http://127.0.0.1:18110/.

Read ~/workspace/calendar/private/actor_b/room_policy.pdf and ~/workspace/calendar/private/actor_b/mail_threads.csv. For each requested session, use the latest non-cancelled message in its thread, resolve the stated local time to UTC using the supplied offset table, and select an available room satisfying the required capacity and equipment. Ignore superseded, cancelled, draft, and test messages.

Enter the three valid sessions in Calendar and submit a Preview. Review the returned availability or validation findings, correct the schedule when needed, and submit Confirm against the current preview token. Verify that the confirmed events appear with the intended UTC time, room, attendee, and duration. Save ~/workspace/calendar/out/calendar_b_audit.json with the three source thread IDs, chosen rooms, UTC intervals, and final confirmation IDs, and export the confirmed events to ~/workspace/calendar/out/calendar_export_b.ics.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** 一方在 Calendar 页面预览并保留旧 revision，另一方提交 `.ics` 全量更新后前者 token 被拒；若通过 CSV/CLI 生成全新 ICS，仍会覆盖既有 UID 或他人的 VEVENT。Chrome 日历日期/房间视图也会随导航刷新。
- **全 GUI：** 两边编辑日期、切视图、预览和确认，抢同一热门槽位；刷新时一个人的本地草稿可能被新的服务端 revision 替代。
- **全 CLI：** 可用标准库解析 CSV/ICS 并调用本地 HTTP，但 token 由当前服务状态签发且确认检查 SQLite 中房间容量、禁用时段和数据库冲突；一次性静态脚本不能跳过实时预览/提交，也可能遇到 stale revision 与 ICS 全量覆盖。

## 5. 离线 Oracle 与 `grade.json`

Oracle 解析回收 ICS、audit JSON、host-collected token/confirmation ledger 与只读 rooms DB 快照；重算所有邮件版本、UTC 换算、room requirements 及事件状态。

### `subchecks_a`（合计 `1.000`）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | 识别 3 个有效 thread 最新版本；取消/旧稿/测试线程未被提交 |
| A02 | 0.20 | 是 | 3 个 DTSTART/DTEND UTC 换算、时长及 attendees 正确 |
| A03 | 0.20 | 是 | rooms.db 最终记录满足容量、设备、空闲与状态条件 |
| A04 | 0.15 | 是 | 3 项均经过真实 Phase 1 token 与 Phase 2 confirmation，token 对应最终 ICS revision |
| A05 | 0.15 | 是 | audit JSON 和导出 ICS 包含准确 source thread、room、UTC interval、UID / confirmation ID |
| A06 | 0.10 | 否 | 未修改非目标基础会议；iCalendar 格式和时区标识可解析 |

### `subchecks_b`（合计 `1.000`）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | 识别 3 个有效 thread 最新版本；取消/旧稿/测试线程未被提交 |
| B02 | 0.20 | 是 | 3 个本地时间到 UTC 的换算、时长及 attendees 正确 |
| B03 | 0.20 | 是 | rooms.db 最终记录满足容量、设备、空闲与状态条件 |
| B04 | 0.15 | 是 | 3 项均有服务签发的 Phase 1 token 和 Phase 2 confirmation |
| B05 | 0.15 | 是 | audit JSON 和导出 ICS 内容与有效源邮件及 rooms DB 一致 |
| B06 | 0.10 | 否 | 不破坏非目标基础事件和 UID；导出可解析 |

### `subchecks_joint`（全部 required）

| ID | 权重 | 判定 |
|---|---:|---|
| J01 | 1.000 | 最终 `team_schedule.ics` 与 reservations DB 均保留 6 项目标事件并与两个审计 JSON 一致 |
| J02 | 1.000 | 所有事件无非法时段/房间双重预约，无取消项复活、重复 UID 或错误时区 |
| J03 | 1.000 | A/B 导出各自目标事件集合且保留原始有效基础日历事件；ICS 与 DB 同步 |

## 6. 防作弊与隔离边界

邮件 CSV / policy PDF 及登录信息分别位于 role-private mount；本角色 local web session 仅允许打开其 mail thread collection。服务不得在静态页面或未鉴权 API 暴露对侧邮件。Oracle、固定答案、隐藏 token ledger 与数据库真值不挂载至 Guest；公开给 Guest 的 Phase 1 token 只为流程 nonce，并非评分答案。Host collector 只读拷贝最终状态与服务端 token ledger。

---

# BC-11 — 有状态计算内核与 Q4 分析工作台

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | Guest Python 3.10 标准库持久内核、`google-chrome`、CSV、JSON、PDF / `pdftotext` |
| 本地入口 | `http://127.0.0.1:18111/`；Chrome 预开 Pipeline Workbench |
| 复杂度目标 | 每角色约 55–85 个有效操作：多源脏数据整理、定义分析步骤、在持久命名空间运行/复核 cell、保存 pipeline 与指标 JSON |
| 单人可解性 | Revenue 与 retention 输入隔离；任何一侧都能独立运行其分析，不依赖其他 cell 作者或特定执行顺序 |
| 核心冲突 | 两侧代码运行于一个长期存活的 Python namespace，通用变量名可能污染；内核重启清空运行态；`q4_pipeline.json` 全量保存引起 Lost Update |

## 2. 初始环境、路径与数据

工作根 `~/workspace/pipeline/`。WorkBench service 用 Python 标准库 `http.server` + `code.InteractiveConsole` 实现，不依赖 Jupyter、pandas 或额外 notebook package。服务启动一次建立单一持久 `namespace`；所有 cell 请求在该进程中依次执行，Notebook 中保存的 cell 和 kernel 变量是两种不同状态。`POST /cell/run` 返回 stdout/stderr、cell ID、时间戳和 process-generation ID；`POST /pipeline/save` 全量写 `q4_pipeline.json`；`/kernel/status` 显示运行代数及已执行 cell 条数；`kernelctl restart` 会重置内存 namespace，但保留最后写盘 pipeline。

| 路径 | Schema / 行为 |
|---|---|
| `~/workspace/pipeline/q4_pipeline.json` | 保存 `workbook_title`、`cells`、各 cell 的 source/output、`revenue_summary` / `retention_summary` 两个面板与保存 revision |
| `~/workspace/pipeline/private/actor_a/orders.csv` | 约 100 行订单；`order_id,date,region,amount,cost,status,kind,is_test,import_batch`；含重复导入、VOID、refund、日期格式噪声 |
| `~/workspace/pipeline/private/actor_a/finance_rules.pdf` | 日期清洗、记录优先级、退款方向、区域毛利计算与金额舍入规则 |
| `~/workspace/pipeline/private/actor_b/users.csv` | 用户及 signup/cohort 日期、实验标记、首个合格活动日；含机器人/测试账号/重复 ID |
| `~/workspace/pipeline/private/actor_b/activity.csv` | 约 150 行行为日志；含重试、重复事件、时区偏移和失效事件 |
| `~/workspace/pipeline/private/actor_b/retention_rules.pdf` | cohort 纳入/排除、Day-14 活跃定义、窗口右删失处理及分母规则 |
| `~/workspace/pipeline/out/revenue_analysis.json` | A 输出各区域有效销售、退款、净营收、净毛利和过滤计数 |
| `~/workspace/pipeline/out/retention_analysis.json` | B 输出 cohort size、Day-14 retained/users/rate、过滤计数与 cohort 月份 |
| Runner 回收的 `kernel_receipts.jsonl` | host collector 从 Workbench 事件侧导出 cell ID、执行顺序、stdout hash、process-generation；不含 Oracle 答案 |

WorkBench 只负责 cell 执行、结果显示和 `q4_pipeline.json` 的 task artifact 持久化；它不嵌入任务目标值。Role-private 资料各自挂载。每组数据由固定 seed 构造，日期格式和异常值规则在本角色 PDF 中定义；Oracle 从宿主机独立 fixture 重算。单侧最低交付需包含：过滤/规范化、分组汇总、sanity-check 与导出等至少 4 个有意义 cell；不规定变量名或强制照写的 cell 顺序，给 Agent 留下自选 pandas 替代方式（标准库）及分解方法。

## 3. 角色目标与完整 Prompt

### Actor A — Revenue Reconciliation Analyst

```text
You are preparing the Q4 revenue reconciliation in the Pipeline Workbench at http://127.0.0.1:18111/.

Read ~/workspace/pipeline/private/actor_a/finance_rules.pdf and ~/workspace/pipeline/private/actor_a/orders.csv. Normalize the supported date formats, resolve duplicate imports according to the stated record-priority rules, exclude test and void records, and apply the prescribed signed treatment for refunds. Calculate valid transaction counts, net revenue, net cost, and gross margin for each required region.

Use Pipeline Workbench to build and run an understandable set of analysis cells. Review the results and execution status, save the pipeline, and write ~/workspace/pipeline/out/revenue_analysis.json with the filter counts, per-region measures, rounding convention, and source order IDs needed to reproduce the totals. Verify that the saved pipeline and JSON agree and that the Workbench reports successful cell executions.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Cohort Retention Analyst

```text
You are preparing the Q4 customer retention analysis in the Pipeline Workbench at http://127.0.0.1:18111/.

Read ~/workspace/pipeline/private/actor_b/retention_rules.pdf, ~/workspace/pipeline/private/actor_b/users.csv, and ~/workspace/pipeline/private/actor_b/activity.csv. Apply the stated user eligibility, duplicate identity, test/robot, event-validity, observation-window, and right-censoring rules. Calculate eligible cohort sizes and Day-14 retained users and rates for every required cohort month.

Use Pipeline Workbench to build and run an understandable set of analysis cells. Review the results and execution status, save the pipeline, and write ~/workspace/pipeline/out/retention_analysis.json with the filter counts, cohort measures, rate denominator, time-window convention, and source IDs needed to reproduce the results. Verify that the saved pipeline and JSON agree and that the Workbench reports successful cell executions.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** 某 Actor 在浏览器/CLI cell 调用中定义 `records` / `clean` 等通用变量，另一 Actor 的 cell 将其重新绑定，第一侧后续检查可能使用已替换变量；任何一次 kernel restart 会同时使已有内存结果失效。两侧保存 notebook 时都全量序列化可能擦除对方尚未落盘的 section。
- **全 GUI：** 两边在同一工作台操作编辑框、运行状态和 Save 按钮，后一次 save 可回写旧 notebook 快照；重启服务会丢失两边内存命名空间。
- **全 CLI：** CLI 可以直接计算数据，但评分要求输出与服务侧成功运行 receipt 和 pipeline cell source/output 一致；直接手写 JSON 不足以完成核验。CLI 通过 Workbench API 执行仍会共享持久 process namespace，并竞争 pipeline 全量保存。

## 5. 离线 Oracle 与 `grade.json`

Host Oracle 独立清洗原始 inputs 后比较分析 JSON；同时核验回收的 pipeline artifact 与服务端 `kernel_receipts.jsonl`。宿主机采集是附加只读输入，Guest 中不得提供 Oracle 参考答案。

### `subchecks_a`（合计 `1.000`）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.22 | 是 | 去重、日期、test/void、退款符号及过滤计数与 Oracle 规则一致 |
| A02 | 0.22 | 是 | 所有区域净营收、净成本、毛利率与宿主机重算值一致 |
| A03 | 0.18 | 是 | revenue JSON 有效、引用源 order IDs 可追溯，字段/舍入口径完整 |
| A04 | 0.18 | 是 | Pipeline 中存在 Revenue 分析 cell 且成功执行 receipt 的输出值与 JSON 一致 |
| A05 | 0.10 | 是 | pipeline 保存成功、目标 revision 存在且页面/JSON 都可解析 |
| A06 | 0.10 | 否 | 所有分析步骤有解释性标题或说明，错误输出已清理而未篡改 receipt |

### `subchecks_b`（合计 `1.000`）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.22 | 是 | cohort 用户去重、资格、test/robot、事件过滤与右删失处理正确 |
| B02 | 0.22 | 是 | 每月 cohort size、Day-14 retained count 和 retained rate 与 Oracle 重算一致 |
| B03 | 0.18 | 是 | retention JSON 有效，包含分母、日期窗口、过滤计数及 source IDs |
| B04 | 0.18 | 是 | Pipeline 中存在 Retention 分析 cell；执行 receipt 输出与 JSON 一致 |
| B05 | 0.10 | 是 | pipeline 保存成功且对应页/JSON 可解析 |
| B06 | 0.10 | 否 | 分析步骤说明易读、结果没有错误/旧状态片段 |

### `subchecks_joint`（全部 required）

| ID | 权重 | 判定 |
|---|---:|---|
| J01 | 1.000 | 最终 `q4_pipeline.json` 同时保留 Revenue 与 Retention sections/cells，任一 section 未回退 |
| J02 | 1.000 | 两个 JSON、pipeline cell 输出与独立宿主 Oracle 重算一致 |
| J03 | 1.000 | A 与 B 成功执行 receipt 可证明二者在同一 process-generation 中运行；服务状态/receipt 来自 host collector |

## 6. 防作弊与隔离边界

角色私有 CSV/PDF 通过独立 UID / mount 只提供给对应 Actor。通用 Workbench service 不包含指标目标或 Oracle；执行 receipts 不携带期望答案。Host-only fixtures、评分代码、活动队列状态与控制面不挂入 Guest。`kernel_receipts.jsonl` 应由受信 host bridge 从服务日志采集，不从 Agent 自报 JSON 直接采信。

---

# BC-12 — 图像批处理与两阶段 QA 发布台

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | Python 3.10 + Pillow、`google-chrome` 本地 QA 页面、YAML（PyYAML）、PNG |
| 本地入口 | `http://127.0.0.1:18112/`；Chrome 预开 QA dashboard |
| 复杂度目标 | 每角色约 55–90 个有效操作：跨图像源筛选、尺寸/宽高比检查、生成多张成品、QA 拒绝分析、修正元数据/图像后发布 |
| 单人可解性 | Storefront 与 App Promo 是独立素材批、输出 profile 和 QA 规则，任一批均可独立处理 |
| 核心冲突 | `asset_manifest.yaml` 全量覆盖；`tmp/qa_preview.png` 与中间 JSON 默认同名；QA 单槽位预览 revision 竞争；Chrome 状态切换 |

## 2. 初始环境、路径与数据

项目根 `~/workspace/assets/`；只用 Guest 已探测的 Pillow / PyYAML / Chrome，无第三方安装。

| 路径 | 内容 |
|---|---|
| `~/workspace/assets/private/actor_a/storefront/raw/` | 10 张商品图片，其中含损坏文件、低分辨率、错误比例、alpha/色彩差异等噪声；每批有多个合规源图 |
| `~/workspace/assets/private/actor_b/promo/raw/` | 10 张活动图片，类似干扰类型但分辨率/安全区规则不同 |
| 各自 `contact_sheet.png` | 初始候选拼图含不符合规则的候选；在 QA 页可读出发现项 |
| 各自 `image_policy.pdf` | 图像目标宽高、裁切/留白/色彩模式、安全区、英文水印短语、透明度与命名规则 |
| `~/workspace/assets/asset_manifest.yaml` | 可编辑主 manifest；根字段含版本和两个产品组节点，双方全量写回可能丢失另一更新 |
| `~/workspace/assets/tmp/qa_preview.png`、`qa_receipt.json` | QA 服务单槽位预览，不提供跨角色操作说明 |
| `~/workspace/assets/out/storefront/`、`~/workspace/assets/out/promo/` | 每侧各 4 张最终 PNG 与 `qa_audit.json` / `qa_b_audit.json` |

规则 PDF 为每侧规定 4 项输出 PNG 尺寸、缩放模式（contain 或 center-crop）、安全边距、水印位置、输出 RGB/RGBA 模式及文件名格式。输入资产的有效性由宽高、图像解码、alpha/色彩通道和 PDF 明定的产品属性共同决定；Oracle 从 host fixture 重算允许源图，不以文件名作为充分证据。QA dashboard 提供 `preview` 与 `publish` 两态：preview 返回机器可读及可视警告并要求校正；publish 对最终图像解码、尺寸、manifest 源图 ID、水印/边距检查后返回完成 receipt。Preview token 绑定 revision，无短 TTL。初始联系表的测试资产至少有一项不满足目标 profile，保证 QA 浏览/拒绝路径有实际内容；Prompt 只要求解决 QA findings，不给出哪张图错误。

## 3. 角色目标与完整 Prompt

### Actor A — Storefront Image Production

```text
You are preparing the Q4 Storefront image package in ~/workspace/assets/.

Read ~/workspace/assets/private/actor_a/image_policy.pdf and inspect the candidate images in ~/workspace/assets/private/actor_a/storefront/raw/. Review the supplied contact sheet in the QA dashboard at http://127.0.0.1:18112/. Select valid source images using the policy's decode, dimensions, aspect, and safe-area requirements. Generate the four required final storefront PNGs with the prescribed canvas, fit/crop method, background, watermark, color mode, and filename. Do not use a corrupted or ineligible source.

Record the source image IDs, transformation dimensions, output paths, and QA findings in the storefront section of ~/workspace/assets/asset_manifest.yaml. Submit a Preview, review its result, correct any reported issue, and submit the final package for Publish. Save ~/workspace/assets/out/storefront/qa_audit.json with the four source/output mappings, validation results, and publish receipt. Reopen or inspect each final PNG and verify it satisfies the policy before finishing.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Mobile Promotion Image Production

```text
You are preparing the Q4 mobile promotion image package in ~/workspace/assets/.

Read ~/workspace/assets/private/actor_b/image_policy.pdf and inspect the candidate images in ~/workspace/assets/private/actor_b/promo/raw/. Review the supplied contact sheet in the QA dashboard at http://127.0.0.1:18112/. Select valid source images using the policy's decode, dimensions, aspect, and safe-area requirements. Generate the four required final mobile PNGs with the prescribed canvas, fit/crop method, background, watermark, color mode, and filename. Do not use a corrupted or ineligible source.

Record the source image IDs, transformation dimensions, output paths, and QA findings in the mobile promotion section of ~/workspace/assets/asset_manifest.yaml. Submit a Preview, review its result, correct any reported issue, and submit the final package for Publish. Save ~/workspace/assets/out/promo/qa_b_audit.json with the four source/output mappings, validation results, and publish receipt. Reopen or inspect each final PNG and verify it satisfies the policy before finishing.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** Pillow batch 处理可以在 CLI 后台进行，一方随时可把新图写进 `tmp/qa_preview.png`；另一人浏览器中 preview 可能立即变成后写版本。Manifest 使用整文件 YAML 写回，双方分别读旧 revision 后保存会丢掉对方节点。
- **全 GUI：** Chrome 预览的单槽位当前图片会因另一侧刷新而改变；选择文件、缩放结果和 QA 页面可被导航/焦点切换覆盖。
- **全 CLI：** Pillow 直接处理图像仍会竞争同名 tmp、主 manifest 的 revision 及 QA server 唯一 preview slot；直接编写 audit JSON 不能替代 server publish receipt 与服务侧最终图像检查。

## 5. 离线 Oracle 与 `grade.json`

Oracle 使用 Pillow 解码回收 PNG、解析 YAML、核对可追溯 source IDs 与 host QA receipt；像素差异按尺寸、alpha、色彩模式、水印安全区和主要颜色区域计算，不将 Guest 自报 `passed=true` 作为唯一证据。

### `subchecks_a`（合计 `1.000`）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.18 | 是 | 4 个所选 storefront 源图均通过独立解码/有效性规则，无损坏或不合格输入 |
| A02 | 0.22 | 是 | 4 个 PNG 尺寸、色彩模式、fit/crop 与安全边距符合财务外观 policy |
| A03 | 0.18 | 是 | 水印文本和位置/可见性符合 policy 像素区域检查 |
| A04 | 0.18 | 是 | manifest storefront 部分列出准确 source ID、输出路径和转换参数 |
| A05 | 0.14 | 是 | 服务侧 preview/findings 与 final publish receipt 均存在且绑定最终 manifest revision |
| A06 | 0.10 | 否 | 无关目录资产未删除；四张成品可解码且无全透明/空白画布 |

### `subchecks_b`（合计 `1.000`）

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.18 | 是 | 4 个所选 promo 源图通过独立解码/有效性规则 |
| B02 | 0.22 | 是 | 4 个 PNG 的正方形画布、center-crop/contain、alpha/颜色与 safe area 正确 |
| B03 | 0.18 | 是 | 活动水印文本/像素区域和指定位置正确 |
| B04 | 0.18 | 是 | manifest promo 部分的 source IDs、输出路径和转换参数正确 |
| B05 | 0.14 | 是 | Preview 和 final Publish receipt 与最终 revision、四个图像 hash 一致 |
| B06 | 0.10 | 否 | 不误删原始素材；所有输出为有效非空 PNG |

### `subchecks_joint`（全部 required）

| ID | 权重 | 判定 |
|---|---:|---|
| J01 | 1.000 | 最终 YAML 同时保留 storefront 和 promo 两个目标组，两个组的清单与磁盘 PNG 一一对应 |
| J02 | 1.000 | A/B QA publish receipt 均由宿主 collector 收集，绑定正确 image hash / manifest revision |
| J03 | 1.000 | 所有 8 张 PNG 可解码、无组间误置、无源图路径越权或错误尺寸 |

## 6. 防作弊与隔离边界

Storefront 与 Promo 原图、规则 PDF 按角色私有挂载，不把全量素材或另一份 policy 提供给对侧 CLI。公开给 Guest 的 QA 是任务服务，不含 Oracle expected hashes / hidden source eligibility map。Host-only eligibility table、像素参考、QA 验收真值与 grading 代码不挂载。服务 receipts 经 host collector 采集，Agent 写的 JSON 只作对照材料，不作唯一真实性证明。

# BC-13 — 双语键盘布局与 Writer 规范化记录

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | LibreOffice Writer（ODT / PDF）、Guest 桌面键盘布局选择器、CSV、`pdftotext` |
| 复杂度目标 | 每角色约 55–85 个有效操作：从多份术语/事件素材筛选记录，执行字符与日期规范化，完成有结构的 Writer 编辑、布局切换检查和 PDF 校验 |
| 单人可解性 | A、B 各有独立源 CSV、规则页和目标章节；每侧所需布局均预置，不依赖另一角色的输入或系统操作 |
| 核心冲突 | X11/XKB 当前输入源为桌面全局状态；同一 ODT 的内存态/磁盘态竞争；Writer 多页定位与 PDF 导出时的 GUI 焦点交错；LibreOffice 单实例 Profile / 导出锁 |

**实现准入前提（尚非已探测事实）：** Guest 镜像虽已确认安装 LibreOffice，但本轮依赖探测未核实 XKB 输入源切换 UI 是否预配置。实现前必须用只读方式确认桌面菜单里已有 `English (US)` 与 `German` 两种输入源；不得在线装包或假定 `setxkbmap`、GNOME 扩展可用。若缺任一布局，本规格暂停实现并回到设计审查，不得伪称环境已满足。

## 2. 初始环境、路径与数据

Guest workspace 为 `~/workspace/bc13/`。Writer 启动时打开 `bilingual_ops_notes.odt`，含封面、`North America Operations`（第 2–3 页）、`DACH Customer Support`（第 4–5 页）和留白附录。桌面状态栏允许从已预置的两种输入源间切换；默认输入源为 English (US)。A/B 可以分别打开自己有权限的输入源和规则文件。ODT 是两侧都要保留的同一个最终文档，但单个 Actor 可独自完成自己章节和交付。

| 路径 | 用途 / 结构 |
|---|---|
| `~/workspace/bc13/bilingual_ops_notes.odt` | 起始 ODT：固定页眉、样式、页码和章节锚点已建立；不得重置模板或删除未分配章节 |
| `~/workspace/bc13/private/actor_a/incident_terms.csv` | `case_id,occurred_at,market,raw_note,priority,valid_record`；有重复、撤销和测试行 |
| `~/workspace/bc13/private/actor_a/locale_rules.pdf` | A 的 English (US) 键位/标点规范、时间格式、必含术语及事件纳入条件 |
| `~/workspace/bc13/private/actor_b/customer_terms.csv` | `ticket_id,opened_at,locale,raw_quote,product,disposition`；有重复、引用文本和已关闭干扰行 |
| `~/workspace/bc13/private/actor_b/dach_rules.pdf` | B 的 German 键位/变音符、德语标点/日期规范、术语表与有效工单条件 |
| `~/workspace/bc13/out/na_appendix.pdf`, `na_records.json` | A 的章节 PDF 与机器可读核验记录 |
| `~/workspace/bc13/out/dach_appendix.pdf`, `dach_records.json` | B 的章节 PDF 与机器可读核验记录 |

初始样本数应大于目标记录数约 2 倍；每份数据必须含需跨列比对的有效标记/状态、相近日期及诱饵记录。规则 PDF 定义唯一纳入集合、词条正规拼写、时区/日期呈现与 Unicode 字符串。两种键位布局由 setup 预置而非 Agent 安装；两角色输入挂载分离。

## 3. 角色目标及完整运行时 Prompt

### Actor A — North America Operations Editor

**职责边界：** 处理有效 NA 事件、按规则整理英文条目并更新 ODT 第 2–3 页的 NA 章节，导出自己的 PDF / JSON。不得改封面、DACH 章节或模板样式。

**Prompt 原文：**

```text
Prepare the North America Operations section in ~/workspace/bc13/bilingual_ops_notes.odt, already open in LibreOffice Writer.

Read ~/workspace/bc13/private/actor_a/locale_rules.pdf and inspect ~/workspace/bc13/private/actor_a/incident_terms.csv. Determine which records qualify using every status, duplicate, date, and market rule. Normalize the selected event names, dates, punctuation, and required terms exactly as specified. Create ~/workspace/bc13/out/na_records.json with the selected source IDs, exclusion counts, normalized values, and a concise calculation/audit trail.

Complete the North America Operations section on pages 2–3 of the ODT. Include the required short summary, a legible structured event table, and the specified locale examples. Use the English (US) input source when entering text that depends on keyboard mapping, and confirm the resulting characters match the source rules. Preserve the template styles, page numbering, and content outside your section. Save the ODT, export your section as ~/workspace/bc13/out/na_appendix.pdf, and verify the saved document and PDF text.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — DACH Customer Support Editor

**职责边界：** 按德语规则整理有效支持记录并补全 DACH 第 4–5 页，使用 German 输入源处理 ä/ö/ü/ß 与德语标点，导出自己的 PDF / JSON；不得改动 NA 章节和模板结构。

**Prompt 原文：**

```text
Prepare the DACH Customer Support section in ~/workspace/bc13/bilingual_ops_notes.odt, already open in LibreOffice Writer.

Read ~/workspace/bc13/private/actor_b/dach_rules.pdf and inspect ~/workspace/bc13/private/actor_b/customer_terms.csv. Select valid records using the locale, product, disposition, duplicate, and status rules. Normalize German names, dates, punctuation, and required terminology exactly as specified. Create ~/workspace/bc13/out/dach_records.json containing selected ticket IDs, exclusion counts, normalized values, and a concise audit trail.

Complete the DACH Customer Support section on pages 4–5. Include the required German summary, a readable ticket table, and the required locale examples with correct umlauts, ß, quotation marks, and date format. Use the German input source when entering text that depends on keyboard mapping, then verify the characters in the document. Preserve the template styles, page numbering, and content outside your section. Save the ODT, export your section as ~/workspace/bc13/out/dach_appendix.pdf, and verify the ODT and PDF text.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** Writer 已载入 ODT 的旧文档树；CLI 以标准库 ZIP/XML 直接改 ODT 后，GUI 再保存会以旧内存副本覆盖包文件。桌面输入源切换是 X server 全局状态，即使 CLI 已计算出正确 Unicode，GUI 后续输入仍可能在另一个 layout 下产生不同字符。PDF 导出与自动保存也可能被同一 LibreOffice 实例排队。
- **全 GUI：** 两侧在不同章节间切页、选择样式、切换输入源和触发导出时，当前插入点/活动窗口是全局桌面状态；后保存的 ODT 包可能覆盖先保存的章节更改。
- **全 CLI：** CLI 可用标准库读取 CSV 与 ODT ZIP/XML、生成 JSON；它不能消除最终对同一 ODT 全包写入的丢失更新，也不会隔离 XKB 状态。直接生成最终文档虽可减少键盘布局冲突，但仍需保留正确 ODT 结构、模板样式、文本及 PDF 可读性，Oracle 会校验这些可观察交付物而非强制点击步骤。
- **冲突不是必然失败：** Oracle 按最终文档/两份个人交付评估，不因布局切换次数扣分；若最终 Unicode 内容符合规则，即视为内容正确。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Oracle 在宿主机抽取 ODT 的 `content.xml` / `styles.xml` 并用 `pdftotext` 检查两份 PDF；按私有源数据独立计算记录、术语和字符真值。A/B 个人权重各精确为 `1.000`，required 项全过且分数至少 `0.800` 才算个人通过。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | NA 有效事件集合、排除数量及源 ID 精确 |
| A02 | 0.20 | 是 | 金额/日期/事件字段按规则规范化；字符串与 Unicode 标点正确 |
| A03 | 0.20 | 是 | `na_records.json` schema、字段、审计计数和值与重算一致 |
| A04 | 0.18 | 是 | ODT 的 NA 标题、摘要和有效行数正确，位于指定章节 |
| A05 | 0.12 | 是 | PDF 可解析且文本/字符集合完整，未截断表格主体 |
| A06 | 0.10 | 否 | 模板页码、表格样式与章节外基线保留 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | DACH 有效工单集合、排除数量及 ticket ID 精确 |
| B02 | 0.20 | 是 | 德语术语、日期及要求的 ä/ö/ü/ß 字符逐项正确 |
| B03 | 0.20 | 是 | `dach_records.json` schema 和核验内容与真值重算一致 |
| B04 | 0.18 | 是 | ODT 的 DACH 标题、德语摘要和有效工单行正确 |
| B05 | 0.12 | 是 | PDF 文本可解析且特殊字符无替换符/乱码 |
| B06 | 0.10 | 否 | 页码、样式和 NA 章节基线未被破坏 |

### `subchecks_joint`（全部 `required=true`）

| ID | 判定 |
|---|---|
| J01 | 最终 ODT 同时保留两章节正确内容，且源模板必要元素存在 |
| J02 | 两份独立 PDF 分别只含目标章节，页数/文本范围符合规范 |
| J03 | ODT 与 PDF 两种落盘状态内容一致；不存在空文件或损坏 ODT ZIP |

## 6. 防作弊与隔离边界

A 的 CSV / locale PDF 与 B 的 CSV / locale PDF 分别经 role-private mount 和 UID ACL 隔离；Prompt、源文件不包含另一侧材料。Guest 中不放 Oracle、字符真值表、完整有效记录 ID 清单或权重定义。宿主机从最终 ODT/PDF 和只读环境快照核验；不读取或修改 Writer 会话，不要求 Guest CLI 能访问 Host。公共目标 ODT 仅用于共同任务产物，不应含隐藏答案或另一侧私有输入副本。

---

# BC-14 — 全量快照状态看板与多维核销

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | `google-chrome`、本地状态看板、JSON / CSV、Python 3.10.12 标准库、规则 PDF / `pdftotext` |
| 复杂度目标 | 每角色约 55–85 个有效操作：跨源筛选工单、计算 SLA/优先级、在状态机中编辑多字段、处理拒绝后补证、保存与核验 |
| 单人可解性 | A/B 私有工单集合、规则附件和目标字段独立；不需要另一方处理、登录或提供信息 |
| 核心冲突 | `board_state.json` 全量快照写回导致 lost update；看板浏览器视图/过滤状态覆盖；旧 revision 保存可能回滚状态 |

## 2. 初始环境、路径与数据

项目根 `~/workspace/bc14/`；仅 loopback 服务 `http://127.0.0.1:18114/board`，Chrome 已打开 Board 首页。服务读写 `~/workspace/bc14/state/board_state.json`，采用 revisioned full-document save，不做字段级 merge。该行为公开可见于状态页的 revision 标签，但页面不揭示评分真值。`/actor-a` 与 `/actor-b` 的独立登录只返回该角色自己的工单集合、附件和目标导出路径。

| 路径 | 结构 / 作用 |
|---|---|
| `~/workspace/bc14/state/board_state.json` | `revision,cards[]`；每卡含 `ticket_id,queue,status,owner,priority,due_at,sla_class,acceptance_note,source_id,updated_at` |
| `~/workspace/bc14/private/actor_a/frontline_tickets.csv` | 客户端/一线缺陷工单源，含重复 reopen、过期 SLA、测试卡和错误优先级 |
| `~/workspace/bc14/private/actor_a/frontline_policy.pdf` | A 状态转换、SLA 时区、P1/P2 分级和验收依据 |
| `~/workspace/bc14/private/actor_b/platform_tickets.csv` | 后端任务、部署告警与依赖工单源，含 superseded 记录和缺证据案例 |
| `~/workspace/bc14/private/actor_b/platform_policy.pdf` | B 队列状态机、升级条件、所需证据字段和截止时间规则 |
| `~/workspace/bc14/out/frontline_queue.json`, `platform_queue.json` | 每侧筛选/核销结果，包含 IDs、字段变更、规则出处及排除统计 |
| `~/workspace/bc14/out/frontline_receipt.json`, `platform_receipt.json` | 服务端保存回执：revision、accepted/rejected 条数、时间戳；由本角色 session 读取 |

数据规则须定义确定性 UTC 时钟、SLA 起算点、相同优先级排序、可允许状态跃迁与必需 acceptance evidence。每侧目标约 8–10 张卡；原始 CSV 至少 2 倍候选项，含需联查 `ticket_id` / `event_id` / `resolution` 的干扰数据。保存采用“先校验草稿、后提交”两阶段状态：Phase 1 对缺少依据或无效跃迁返回拒绝项；角色依规则补齐后可提交 Phase 2。每个 actor 的页面、凭据、过滤器和导出位置彼此隔离。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Frontline Queue Auditor

```text
Process the Frontline queue in the local work board at http://127.0.0.1:18114/board. Your account is `frontline_a`; the board opens your assigned queue.

Read ~/workspace/bc14/private/actor_a/frontline_policy.pdf and reconcile the queue against ~/workspace/bc14/private/actor_a/frontline_tickets.csv. Apply the documented UTC/SLA, duplicate, severity, evidence, and valid-transition rules. Update only cards in your assigned Frontline scope. For each eligible card, set the correct status, owner, priority, due time, and concise acceptance evidence. Exclude cancelled, superseded, test, or unsupported items as directed.

Save a complete queue result to ~/workspace/bc14/out/frontline_queue.json, including selected source IDs, excluded-record counts, each final card field, and rule references. Use the board's review and commit workflow to validate and persist the final changes; if validation reports a missing item, resolve it from the policy/source data and submit the corrected result. Save the returned receipt as ~/workspace/bc14/out/frontline_receipt.json. Verify the saved board revision and exported data.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Platform Queue Auditor

```text
Process the Platform queue in the local work board at http://127.0.0.1:18114/board. Your account is `platform_b`; the board opens your assigned queue.

Read ~/workspace/bc14/private/actor_b/platform_policy.pdf and reconcile the queue against ~/workspace/bc14/private/actor_b/platform_tickets.csv. Apply the documented dependency, UTC/SLA, severity, evidence, superseded-record, and valid-transition rules. Update only cards in your assigned Platform scope. Set the correct status, owner, priority, due time, and acceptance evidence for each eligible card. Leave cancelled, superseded, or unsupported items unchanged and document their exclusion.

Save a complete queue result to ~/workspace/bc14/out/platform_queue.json with source IDs, exclusion counts, final card fields, and rule references. Use the board's review and commit workflow to validate and persist your changes. If validation returns a rejection, use the cited policy/source requirements to correct the draft and submit it again. Save the returned receipt as ~/workspace/bc14/out/platform_receipt.json. Verify the final board revision and exported data.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** Web 草稿在页面内持有完整旧快照；CLI 用 `json` 标准库改写 state 后，浏览器提交仍携带旧 revision 和旧 cards，可能拒绝或回滚。反过来，浏览器重新载入可覆盖 CLI 中尚未保存的草稿。
- **全 GUI：** 双侧在过滤器、卡片详情和确认页之间切换会刷新全量状态；一个旧 revision 的提交会被拒，需重新读取与核销，且浏览器单窗口视图被另一操作切换。
- **全 CLI：** 能直接生成完整 `board_state.json` 并调用本地 HTTP，但必须符合服务端 revision、状态机及角色凭据校验；整份 JSON 写回仍会丢掉基于旧快照未包含的字段。角色 scope、审计 receipt 和保存规则在后端执行，不依赖 GUI 点击。
- **隔离属性：** 前端可见状态不展示对侧源工单或账户信息；joint Oracle 只评估最终状态及保持不变的非目标卡。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

宿主机根据私有工单源和规则独立算出应处理/排除集合，读取最终 state、两份 JSON 和服务端只读保存日志。每侧六项权重合计 `1.000`。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | Frontline 合格卡集合精确，重复/撤销/测试项排除正确 |
| A02 | 0.20 | 是 | 状态跃迁合法，优先级、owner 与 UTC due/SLA 值正确 |
| A03 | 0.18 | 是 | 每卡 acceptance evidence 满足 policy 且指回有效 source ID |
| A04 | 0.17 | 是 | Phase 1 无效项被识别并在最终提交前修正，Phase 2 receipt 成功 |
| A05 | 0.15 | 是 | `frontline_queue.json` 与最终卡片/排除统计一致 |
| A06 | 0.10 | 否 | Frontline scope 外的卡片与原始字段保持不变 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | Platform 合格卡集合精确，superseded/测试记录处理正确 |
| B02 | 0.20 | 是 | 依赖顺序、状态跃迁、priority 与 UTC deadline 正确 |
| B03 | 0.18 | 是 | 验收证据完整且满足所需 dependency / deployment source |
| B04 | 0.17 | 是 | Phase 1 拒绝项经修正后 Phase 2 保存回执成功 |
| B05 | 0.15 | 是 | `platform_queue.json` 与最终状态、源 ID、排除统计一致 |
| B06 | 0.10 | 否 | Platform scope 外状态不被破坏 |

### `subchecks_joint`（全部 required）

| ID | 判定 |
|---|---|
| J01 | 最终 state 中双方目标卡均与各自 receipt / JSON 一致，revision 单调递增 |
| J02 | 未分配卡及基线字段无意外变化；无非法状态跃迁、重复 owner 或无效 due time |
| J03 | 服务端保存日志证明两侧最终有效提交均被接纳；旧 revision 拒绝不被误记为成功 |

## 6. 防作弊与隔离边界

两角色使用各自 session、role-private CSV/PDF 和 API scope；服务端查询接口只返回当前账户的队列。允许 Guest CLI 读写工作区和访问本地服务，但不挂载宿主机 Oracle、scope 真值、答案集合、服务私有快照或队列控制接口。页面不得通过静态资源或客户端 bundle 泄露对侧数据。Guest 可见的提交回执只说明接纳/拒绝和 revision，不包含评分答案。Host Oracle 对最终回收 state 和不可变服务日志做离线核验。

---

# BC-15 — Git 同分支微服务端点与运行态联调

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | Git、VS Code（可选）、Python 3.10.12 标准库、SQLite、`google-chrome` 本地状态页 |
| 复杂度目标 | 每角色约 60–95 个有效操作：查读指标需求与脏 fixture、修改服务实现/配置、跑多组回归、核验实时端点、提交 scoped change |
| 单人可解性 | Risk 与 Route 服务各有独立需求 PDF、源样本和代码文件；单服务可独立完成，不需要另一服务先提交 |
| 核心冲突 | 同一 `main` 工作树与 `.env` 共享配置的写入覆盖；restart 会终止另一端正在验证的进程；Git index/工作树锁及并发 commit 顺序 |

设计避免外部框架或在线安装：两服务由 Python 标准库 `http.server` 实现，数据记录用 `sqlite3`；本地控制脚本只管理 Guest 内开发服务。`.env` 仅含非敏感配置，不放真实凭据。

## 2. 初始环境、路径与数据

仓库 `~/workspace/bc15/service-hub/`，初始分支 `main`，工作树干净，Git 用户名/email 已由非敏感测试值配置。三个服务端点分别为 Risk `127.0.0.1:18115`、Route `127.0.0.1:18116` 和只读状态页 `127.0.0.1:18117/status`；Chrome 已打开状态页。`bin/servicectl` 支持 `restart risk|route|all`、`status`、`logs`；重启时读取 `.env` 和 Python 服务源码，服务不热读文件。

| 路径 | 作用 |
|---|---|
| `risk_service.py` / `route_service.py` | 两个 stdlib HTTP 服务，各有独立 `/health`、目标 API 和固定日志 |
| `config/risk.yaml`, `config/route.yaml`, `.env` | 两域配置及非敏感运行参数；role-private 需求只规定本侧项 |
| `tests/risk_cases.csv`, `tests/route_cases.csv` | 每侧多类正常/边界/异常样本，含噪声标签与近似重复 |
| `private/actor_a/risk_api_spec.pdf`, `risk_inputs.csv` | 风险字段、分类阈值、例外条件与期望响应 schema |
| `private/actor_b/route_api_spec.pdf`, `route_inputs.csv` | 路由优先级、健康回退、熔断恢复规则与回归指标定义 |
| `out/risk_verification.json`, `route_verification.json` | API 结果摘要、样本覆盖、失败用例、运行版本与 commit ID |

setup 在本地 SQLite 审计表预置服务重启记录、测试请求摘要和 commit 采集入口。服务不得模拟外网调用。各角色实际要从规则文档推导有效样本及阈值，再实现配置/行为并以 HTTP 回归测试，不得只把给定字面值粘贴到配置。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Risk Endpoint Engineer

```text
Implement and validate the Risk service in ~/workspace/bc15/service-hub/.

Read private/actor_a/risk_api_spec.pdf and reconcile its requirements with private/actor_a/risk_inputs.csv and tests/risk_cases.csv. Update risk_service.py, config/risk.yaml, and only the Risk-related non-sensitive settings in .env. Implement the required response schema and documented threshold/exception behavior using Python's standard library and the supplied SQLite audit store. Do not add network dependencies or modify the Route service files.

Run the supplied Risk regression cases, inspect failures, and correct the implementation until every required case returns the documented result. Use `bin/servicectl` to restart the Risk process so its configuration is loaded. Verify the live endpoint at http://127.0.0.1:18115/health and the Risk section of http://127.0.0.1:18117/status. Save ~/workspace/bc15/out/risk_verification.json with the tested case IDs, expected/actual classifications, service revision, restart receipt, and current Git commit. Commit your Risk-scoped changes on the existing `main` branch with a concise descriptive message, then verify the commit and working tree.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Route Resilience Engineer

```text
Implement and validate the Route service in ~/workspace/bc15/service-hub/.

Read private/actor_b/route_api_spec.pdf and reconcile its requirements with private/actor_b/route_inputs.csv and tests/route_cases.csv. Update route_service.py, config/route.yaml, and only the Route-related non-sensitive settings in .env. Implement the documented priority, health fallback, and recovery behavior using Python's standard library and the supplied SQLite audit store. Do not add network dependencies or modify the Risk service files.

Run the supplied Route regression cases, inspect failures, and correct the implementation until every required case returns the documented result. Restart the Route process with `bin/servicectl` so configuration is loaded, then verify http://127.0.0.1:18116/health and the Route section of http://127.0.0.1:18117/status. Save ~/workspace/bc15/out/route_verification.json with tested case IDs, expected/actual routes, service revision, restart receipt, and current Git commit. Commit your Route-scoped changes on the existing `main` branch with a concise descriptive message, then verify the commit and working tree.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** VS Code 仍持有旧的 `.env` / Python buffer 时，CLI 的写入会在保存时被 GUI 旧 buffer 覆盖；服务 restart 读取落盘文件，可能让页面显示的“待测配置”与当前进程版本不一致。浏览器状态页在重启瞬间可能显示短暂 unavailable 或过期健康状态。
- **全 GUI：** 两个编辑器窗口可切至同一 `.env` / service control 脚本；运行控制面板发起 restart 会中断正在浏览器检查的请求。共享 Git index 可能在 commit 阶段短暂被锁定。
- **全 CLI：** 并发 shell 编辑、测试、restart 和 `git add/commit` 仍作用于同一工作树、`.env`、index 和服务进程。CLI 不能规避 `.git/index.lock`、配置被另一版本重启加载或正在被验证的端点中断；actor-private scope 仍通过文件 ACL 和后端路由约束。
- **不强制工具顺序：** 检查点看最终代码、回归结果、运行版本、restart log、scoped commit 和核验 JSON；不要求 GUI 与 CLI 的特定比例或固定命令序列。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Host Oracle 在隔离副本中导入服务模块、重跑冻结回归集合，并对只读服务日志、Git commit/tree 和两份核验 JSON 进行核对。每侧个人权重合计 `1.000`。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | Risk 输入筛选和例外样本解释符合私有需求规范 |
| A02 | 0.22 | 是 | 响应 schema、阈值和异常/缺值行为通过冻结回归 |
| A03 | 0.18 | 是 | `risk.yaml` 与 `.env` 的 Risk 参数完整且格式有效 |
| A04 | 0.15 | 是 | 服务重启后 live endpoint 与 Chrome 状态页版本/状态正确 |
| A05 | 0.15 | 是 | `risk_verification.json` 覆盖用例、版本、期望与实际结果 |
| A06 | 0.10 | 否 | Risk-scoped commit 存在且不包含大体积/私密 fixture 或 Route 意外改动 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | Route 输入与有效性/优先级规则理解正确 |
| B02 | 0.22 | 是 | 路由回退、健康探测、恢复边界通过冻结回归 |
| B03 | 0.18 | 是 | `route.yaml` 与 `.env` Route 参数正确且合法 |
| B04 | 0.15 | 是 | restart 后 live endpoint 与状态页反映有效版本 |
| B05 | 0.15 | 是 | `route_verification.json` 覆盖案例和运行版本/结果 |
| B06 | 0.10 | 否 | Route-scoped commit 有效且不误改 Risk 私有输入或服务实现 |

### `subchecks_joint`（全部 required）

| ID | 判定 |
|---|---|
| J01 | 最终 `main` 历史包含 A/B 两个有效 scoped commit，且工作树中两侧目标文件均保留 |
| J02 | `.env` 语法有效、无凭据；Risk 与 Route 进程分别加载正确域配置且同时健康 |
| J03 | 全部 required 回归在最终提交版本重跑通过，两个 verification JSON 与 Git tree / live revision 一致 |

## 6. 防作弊与隔离边界

两个需求 PDF 与 CSV 以 UID/role-private mount 隔离；每个角色不接收对侧输入、Prompt 或测试 expected-output 文件。测试 expected values 与 host Oracle 保持隔离，Guest 内只放入可运行的输入 fixtures 和公开 schema；本地 SQLite 对 Guest 提供最小写入日志 API，不挂载 Host 原始审计库。`.env` 不含真实密钥。Guest CLI 能操作仓库和本地服务，但不能访问宿主机 Git 管理面、Oracle 或队列状态。仓库受控在 Guest workspace 内，Host 只回收最终快照。

---

# BC-16 — Draw 多页架构图与容量标注交付

## 1. 基础元数据

| 字段 | 规格 |
|---|---|
| 工具栈 | LibreOffice Draw（ODG / PDF）、CSV、PDF / `pdftotext` |
| 复杂度目标 | 每角色约 55–85 个有效操作：筛选节点/变更、推导容量标注、编辑多页矢量图、核验连接和标签、导出 PDF 并复查 |
| 单人可解性 | A/B 各有独立节点变更清单和规则附件、各自拥有明确页范围；任一侧可独立完成目标章节 |
| 核心冲突 | Draw 的内存文档与磁盘 ODG ZIP 包覆写；多页窗口导航/对象选择状态争抢；PDF 多页导出对同一 LibreOffice 实例/配置锁的竞争 |

## 2. 初始环境、路径与数据

Guest workspace `~/workspace/bc16/`。Draw 已打开 `system_topology.odg`，含 6 页：封面与范围（1）、Edge & Ingress（2）、Core Services（3）、Data Plane（4）、Capacity & Recovery（5）、Legend / Revision History（6）。预制图形使用稳定 `node_id` 标签字段，不能靠颜色或位置猜 ID；连线对象有 source/target 标识。每侧只改分配的页和规定的 footer revision，保持画布、图层、连接和其他页不变。

| 路径 | 作用 |
|---|---|
| `~/workspace/bc16/system_topology.odg` | 原生 6 页 Draw 文档，已有节点、连接、图例和页面尺寸 |
| `~/workspace/bc16/private/actor_a/edge_changes.csv` | `change_id,node_id,old_label,new_label,link_note,valid_from,record_status`，含撤回与重复变更 |
| `~/workspace/bc16/private/actor_a/edge_spec.pdf` | A 的节点纳入规则、大小写、连线说明、版本页脚和视觉可读性规则 |
| `~/workspace/bc16/private/actor_b/capacity_inventory.csv` | `asset_id,node_id,region,capacity,unit,observed_at,status,source_ref`，含旧观测、单位错配和测试资产 |
| `~/workspace/bc16/private/actor_b/recovery_spec.pdf` | B 的容量优先级、单位转换、目标余量百分比、恢复路径与标注规范 |
| `~/workspace/bc16/out/edge_topology.pdf`, `edge_changes.json` | A 负责第 2–3 页与核验清单 |
| `~/workspace/bc16/out/capacity_recovery.pdf`, `capacity_map.json` | B 负责第 4–5 页与核验清单 |

输入设计为足够候选项、版本交叉表和规则排除项；每侧需先识别 latest valid change / observation，再编辑图面。Oracle 可从 ODG 的 content.xml 和 Draw 页面节点关系核验关键标签/连线；导出 PDF 后通过 `pdftotext` 核验文本及页数。无需额外 Python 图像或 PDF 包。

## 3. 角色目标及完整运行时 Prompt

### Actor A — Edge Topology Editor

```text
Update the Edge & Ingress and Core Services pages in ~/workspace/bc16/system_topology.odg, already open in LibreOffice Draw.

Read ~/workspace/bc16/private/actor_a/edge_spec.pdf and reconcile ~/workspace/bc16/private/actor_a/edge_changes.csv. Select the latest valid change for each in-scope node; exclude withdrawn, duplicate, and out-of-window rows according to the specification. Update the assigned node labels, link annotations, and revision footer without changing node identity, connector endpoints, canvas size, or other pages. Save your selected IDs, exclusions, normalized labels, and link annotations in ~/workspace/bc16/out/edge_changes.json.

Export the required Edge & Ingress / Core Services pages to ~/workspace/bc16/out/edge_topology.pdf. Verify that node names, connector labels, page count, and footer revision are readable in both the saved ODG and PDF. Preserve the page layout and content outside your assigned pages.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

### Actor B — Capacity and Recovery Mapper

```text
Update the Data Plane and Capacity & Recovery pages in ~/workspace/bc16/system_topology.odg, already open in LibreOffice Draw.

Read ~/workspace/bc16/private/actor_b/recovery_spec.pdf and reconcile ~/workspace/bc16/private/actor_b/capacity_inventory.csv. Select the current valid observation for each in-scope node, apply the required unit conversions and reserve-capacity calculation, and exclude stale, test, invalid-unit, or retired assets as specified. Add the correct capacity, region, reserve, and recovery-path annotations while preserving node IDs, connector endpoints, page size, and other content. Save selected source IDs, exclusions, converted values, and calculated reserve figures in ~/workspace/bc16/out/capacity_map.json.

Export the required Data Plane / Capacity & Recovery pages to ~/workspace/bc16/out/capacity_recovery.pdf. Verify all labels, units, reserve figures, connectors, page count, and revision footer in the saved ODG and PDF. Keep the design legible and preserve content outside your assigned pages.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within your assigned Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Preserve files outside your assignment and verify your final deliverables.
```

## 4. 冲突触发路径与 CLI 绕过分析

- **GUI + CLI 混用：** CLI 改 ODG 包后，Draw 的旧内存图在自动保存/关闭时可能回写覆盖；Draw 保存后再 CLI 写入也可能丢掉未保存页面。一次导出生成的临时 PDF 若被另一份导出复用同名路径，会出现检查读到旧页集的竞态。
- **全 GUI：** 多页导航、对象选取和连接点编辑依赖活动窗口/当前页；另一侧改变当前页或对话框会使后续文本输入/删除落在错误对象。两次“保存”可能分别基于各自旧版本的文档模型。
- **全 CLI：** Guest CLI 可解压/检查 ODG 并生成所需交付，但 ODG 是完整容器文件，两个写回仍可能互相覆盖；基于 XML 的手工修改不能绕过 ODG 页面对象引用/连接关系校验与最终 PDF 可读性。共享输出文件名如采用临时转换目录亦可能相撞。
- **最终评估：** 评分看最终 ODG 内容与页面范围、PDF 文本/页数和节点/连接关系；不以具体 GUI 操作步骤作为唯一证据。

## 5. 离线 Oracle 与 `grade.json` 细粒度评分

Oracle 使用 Host 标准库只读解析 ODG ZIP/XML，独立按私有 CSV/PDF 规则重算选中对象与容量数值，再调用 `pdftotext` 验证交付 PDF。每侧权重精确 `1.000`。

### `subchecks_a`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| A01 | 0.20 | 是 | Edge 有效 change ID 与 withdrawn/duplicate 排除集合准确 |
| A02 | 0.20 | 是 | 节点名称、大小写、日期及 link annotation 与规则精确 |
| A03 | 0.18 | 是 | ODG 第 2–3 页节点 identity 与 connector endpoints 保持，目标标签已更新 |
| A04 | 0.17 | 是 | `edge_changes.json` 与 ODG 中内容、源 ID、排除计数一致 |
| A05 | 0.15 | 是 | PDF 可解析且目标页、图例/页脚和关键标签完整 |
| A06 | 0.10 | 否 | 未分配页面、画布大小和图层基线未被破坏 |

### `subchecks_b`

| ID | 权重 | required | 判定 |
|---|---:|---|---|
| B01 | 0.20 | 是 | Capacity 有效 observation 集合和过期/测试资产排除准确 |
| B02 | 0.20 | 是 | 单位转换、容量/余量比例与 recovery 标注按规范计算 |
| B03 | 0.18 | 是 | ODG 第 4–5 页节点/连接关系保留、值落在正确节点 |
| B04 | 0.17 | 是 | `capacity_map.json` 的来源、转换值、余量和图面内容一致 |
| B05 | 0.15 | 是 | PDF 页数及所有关键容量、单位、区域与页脚可读 |
| B06 | 0.10 | 否 | 非目标页面、图层与画布结构保持 |

### `subchecks_joint`（全部 required）

| ID | 判定 |
|---|---|
| J01 | 最终 ODG 同时含双方规定页面内容，所有被连接对象的 node ID 和端点关系完整 |
| J02 | 两份 PDF 只包含各自要求页集且与最终 ODG 的标签/标注一致 |
| J03 | 容器有效、6 页基线结构与共用图例/版本历史保留；无另一章节内容被旧版保存回滚 |

## 6. 防作弊与隔离边界

A/B 的 CSV 与规范附件分开私有挂载，Prompts 不暴露对方输入、输出或隐藏判分集合。Guest 内仅提供公开的初始拓扑 ODG 和两套个人工作区写路径；Host Oracle、期望节点映射、有效源行 ID 和隐藏检查数据均不放 Guest。Guest CLI 的读写/执行权限局限于 Guest workspace；宿主机只读回收最终 ODG、PDF、JSON 与运行器签名的文件清单。共享 ODG 不得预埋最终答案文字或隐藏对象标签。

---

## 批次准入摘要与实现前核验项

| Case | 应用/主题 | 关键共同状态 | 预计操作量/actor | 主要隐含前置项 |
|---|---|---|---:|---|
| BC-09 | Impress 路演 + 财务/产品 KPI | ODP、导出与 LibreOffice Profile | 60–90 | ODP 图表占位可编辑；主机有 `pdftotext` |
| BC-10 | 邮件推导 + 日历两阶段预约 | ICS、房间 DB、revision token | 55–85 | loopback 日历服务和私有邮箱 scope |
| BC-11 | 持久 Python 工作台 | 单进程 namespace、pipeline JSON | 55–85 | 同一持久内核有隔离 section 和可审计执行回执 |
| BC-12 | Pillow 图像流水线 + QA | manifest、tmp、两阶段发布 | 55–90 | 初始素材能在 Guest 本地解码；不引入 Pillow 以外图像依赖 |
| BC-13 | XKB + Writer 双语记录 | 全局输入源、ODT、PDF | 55–85 | 只读确认预置 English (US) 与 German 桌面输入源 |
| BC-14 | 状态看板核销 | revisioned 全量 JSON state | 55–85 | loopback 服务按 actor scope 鉴权并记录 commit receipt |
| BC-15 | Git + 双微服务联调 | `.env`、restart、index | 60–95 | 两服务使用 Python 标准库，非敏感配置与控制脚本准备就绪 |
| BC-16 | Draw 多页架构图 | ODG、PDF、节点/连线关系 | 55–85 | ODG 对象身份可由 Host Oracle 稳定核验 |

所有步数均是单人复杂度设计目标，不是执行上限、计时预算或成功保证。当前阶段不启动服务/Guest、不运行单测、不写任务实现。进入实现审查前，至少确认 BC-13 键盘输入源、各 Case role-private UID/mount 能力以及新脚手架对 Shared-only 的归档签名能力；这些均不得通过弱化盲态或把 Oracle 暴露给 Guest CLI 来规避。
