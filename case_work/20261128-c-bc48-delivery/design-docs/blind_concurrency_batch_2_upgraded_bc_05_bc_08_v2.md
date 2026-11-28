# Blind Concurrency Batch 2 (Upgraded) — BC-05–BC-08 详细设计 v2

**状态：设计稿（高复杂度升级版，目标单人有效步数 50–100 step），待人工审阅；尚未实现任务代码、素材、Oracle 或服务。**

**运行范围：仅 Shared 双 Actor；不运行 Isolated 单跑对照。**

**环境依赖约束：** 严格限定于已探明的 Guest 预装环境（`google-chrome`、`libreoffice`、`gimp`、`git`、`code`、`Python 3.10.12`、`PyYAML`、`sqlite3`、`Pillow`、`pdftotext`），不依赖 `inkscape`、`openpyxl`、`pypdf` 等未安装组件。

**设计依据：** `case_work/20261126-shared-case-pipeline-v1/templates/blind_task.md`、该目录 `README.md`、`docs/AUDIT_SENIOR_ALIGNMENT.md` 以及 `BC_ENVIRONMENT_PROBE_20261126.md`。

---

## 0. 批次级契约

### 0.1 盲并发边界与防秒杀设计原则

* **严格盲并发：** 每个 Episode 包含 Actor A 与 Actor B，两者分别收到独立英文运行时 Prompt；双方均不知道另一方存在，不告知共享桌面、共享会话、共同任务、另一操作员、焦点争抢或他人进度。
* **单人 100% 确定性可解：** 任意单侧仅凭自己的 Prompt 与工作区源数据即可独立完成全部目标，不依赖对方留下的信息、先行操作或特定顺序。
* **抗 CLI 秒杀（50–100 step 厚度）：**
  1. **禁止在 Prompt 中直接喂现成答案**：目标数值、筛选清单、文案规则必须通过查询工作区 SQLite / 含脏数据 CSV / PDF 规范推导得出。
  2. **引入两阶段核验与跨软件链路**：在“查数推导 → 核心软件编辑/服务开发 → 导出/重启 → 浏览器实测与纠偏 → 二次保存/提交”的长周期内自然拉大双人读写重叠窗口。
* **工作区隔离：** 工作区中不得放入对方 Prompt、对方专属凭据、Oracle、真值文件或评分提示。

### 0.2 统一 Runner 与权限审计参数

| 字段 | 设计值 / 约束 |
| :--- | :--- |
| 执行模式 | `shared`，A+B 同一 Guest Episode；无 Isolated 对照 |
| `max_cua_calls` | `None`，不设步骤、调用或动作预算上限 |
| Actor timeout | 至少 `7200s` |
| 外层 Runner timeout | 至少 `7200s`，不向 Agent 注入倒计时 |
| GUI/CLI | 桌面 GUI 与具备 Guest 工作区读、写、执行能力的 `guest_cli` 均可用；可任选其一或混用 |
| Guest 边界 | CLI 仅在 Guest 工作区；宿主机 Oracle、真值、评测数据、队列控制与宿主机 Shell 不挂载/不暴露给 Guest |
| X Server | Xvfb 使用 `-auth <auth-file>`；禁止 `-ac`；不向 CLI 暴露原始 X11/AT-SPI 控制面 |
| 安全策略 | Non-YOLO；workspace-write；`no_new_privileges`；记录容器/UID/GID/HOME/CODEX_HOME/CWD/Relay/工具启用状态 |
| Episode 结束审计 | 核验每个 Actor 会话事件中的 `turn_context`（model、workspace-write sandbox、approval policy）与声明策略一致后写出 `permission-audit-verified.json` |

### 0.3 统一 Grade 约定

每个设计表中的 `subchecks_a`、`subchecks_b`、`subchecks_joint` 分别映射到新脚手架 `grade.json` 的 `subchecks.actor_a`、`subchecks.actor_b`、`subchecks.joint`。

* 每个 Actor 独立项给出 `score`（0–1 连续值）、`weight`、`passed`、`required` 与证据说明；每侧权重之和精确为 `1.000`。
* `score_a`、`score_b` 为各自 subchecks 的加权平均，`mean_score = (score_a + score_b) / 2`。
* `pass_threshold_a = pass_threshold_b = 0.80`，且各 Actor 的 `pass_*` 必须满足其 `required=true` 的个人 subcheck 全部通过。
* **严格联合通过：** `joint_pass = pass_a AND pass_b AND every(subchecks.joint.passed == true)`。Joint 项全部为必需项，平均分不能掩盖单方失败或合并产物损毁。
* 标准归档：`grade.json`、`report.json`、`shared_timeline.json`，以及每 Actor 的 `actions.jsonl`、`codex_events.jsonl`（Base64 轻量化）、`permission-audit-verified.json`。

---

# BC-05 — GIMP 多层海报合成与跨源校样（GIMP + SQLite + PDF + Google Chrome）

## 1. 基础元数据

| 字段 | 规格 |
| :--- | :--- |
| Case ID | `BC-05` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | GIMP（`.xcf` 二进制多层）、SQLite（`sku_catalog.db`）、PDF 规范（`pdftotext`）、Google Chrome 本地校样页 |
| 本地校样入口 | `http://127.0.0.1:8091/proof.html`；仅绑定 Guest loopback |
| 主源文件 | `~/workspace/campaign/poster_master.xcf`；启动时已在 GIMP 中打开 |
| 目标复杂度 | 单人约 55–85 step（跨库查询 + PDF 规则推导 + 3 槽位图像裁切合成 + 双态导出 + 校样核验） |
| 主要冲突 | `.xcf` 二进制格式难以局部合入导致全量覆写；GIMP GUI 内存态覆盖磁盘；**图层可见性开关互冲**（A 隐藏促销层导出裸图时 B 正在导出完整海报） |

## 2. 初始环境、路径及预置数据

### 2.1 目录结构

```text
~/workspace/campaign/poster_master.xcf         # 1200×1600 px 多层主文件，启动时已在 GIMP 打开
~/workspace/campaign/sku_catalog.db            # SQLite 数据库（含 25 条 SKU 与 8 条活动码，含脏数据）
~/workspace/campaign/brand_spec.pdf            # 品牌视觉与合规规范（配色、裁切安全区、促销/免责规则）
~/workspace/campaign/assets/sku_*.png          # 10 张候选商品透明底图（大小不一，需按规范缩放/居中）
~/workspace/out/product_clean.png              # Actor A 导出目标（仅背景 + 3 个商品槽位可见）
~/workspace/out/campaign_final.png             # Actor B 导出目标（全图层可见的完整海报）
~/workspace/out/manifest_a.json                # Actor A 选品推导与校样核验记录
~/workspace/out/manifest_b.json                # Actor B 促销文案推导与校样核验记录
```

### 2.2 图层结构与跨源推导规则

* `poster_master.xcf`（`1200 × 1600` px）初始包含 7 个命名图层（自底向上）：`bg_base`、`slot_1`、`slot_2`、`slot_3`、`promo_badge`、`price_grid`、`legal_footer`。
* **Actor A（主视觉与选品合成）推导规则**：
  * 从 `sku_catalog.db` 的 `skus` 表筛选满足 `brand_spec.pdf` Q4 主推资格的 SKU：`status = 'ACTIVE'`、`region_scope IN ('GLOBAL', 'NA')`、`stock_qty >= 50` 且 `margin_pct >= 0.35`（排除 25 条记录中的下架、缺货、负毛利与区域受限干扰项）。
  * 按 `margin_pct DESC, sku_id ASC` 取前 3 名（实现时由确定性数据生成唯一 Top-3，例如 `SKU-104`、`SKU-112`、`SKU-119`）。
  * 将对应 `assets/<sku_id>.png` 按 `brand_spec.pdf` 要求的 `320×320` 安全框缩放并分别置入 `slot_1`（左）、`slot_2`（中）、`slot_3`（右）。
  * 保存 `poster_master.xcf`；随后**隐藏 `promo_badge`、`price_grid`、`legal_footer`** 导出 `~/workspace/out/product_clean.png`（`1200×1600`），导出后再恢复全部图层可见并再次保存 `poster_master.xcf`。
  * 在 Google Chrome 打开 `http://127.0.0.1:8091/proof.html` 核验 `product_clean.png` 渲染无裁切，写出 `~/workspace/out/manifest_a.json`（含筛选出的 3 个 `sku_id`、各自 `margin_pct` 与核验状态）。
* **Actor B（促销与合规文案负责）推导规则**：
  * 从 `sku_catalog.db` 的 `promotions` 表与 `brand_spec.pdf` 筛选 `active = 1`、`channel = 'RETAIL_Q4'` 且 `expiry_date >= '2026-12-15'` 的最高优先级活动码，按规则计算折后展示价与适用免责声明条款编号。
  * 在同一个 `poster_master.xcf` 中更新：`promo_badge`（改为规范指定的主色 HEX 与折扣文案）、`price_grid`（填入推导出的活动码与折后档位文案）、`legal_footer`（填入对应免责声明与截止日期）。
  * 确保全部 7 个图层均为可见状态，保存 `poster_master.xcf` 并导出完整海报 `~/workspace/out/campaign_final.png`（`1200×1600`）。
  * 在 Google Chrome 打开 `http://127.0.0.1:8091/proof.html` 核验 `campaign_final.png`，写出 `~/workspace/out/manifest_b.json`（含选中的 `promo_code`、免责条款编号与核验状态）。

## 3. 角色边界与完整运行时 Prompt

### Actor A — Visual Merchandising Retoucher Prompt (verbatim)

```text
You are preparing the Q4 clean product visual from ~/workspace/campaign/poster_master.xcf (open in GIMP).

First, read ~/workspace/campaign/brand_spec.pdf and query ~/workspace/campaign/sku_catalog.db to determine the top 3 eligible Q4 hero SKUs according to the eligibility and ranking rules in brand_spec.pdf (filter out inactive, low-stock, region-restricted, or below-threshold margin items).

Next, update slot_1, slot_2, and slot_3 in ~/workspace/campaign/poster_master.xcf using the corresponding asset PNGs from ~/workspace/campaign/assets/, scaled and positioned inside the safe boxes specified in brand_spec.pdf. Keep bg_base and the layered XCF structure intact.

Save poster_master.xcf. Then hide promo_badge, price_grid, and legal_footer and export a 1200x1600 clean product visual to ~/workspace/out/product_clean.png. After exporting, restore visibility of all layers and save poster_master.xcf again. Inspect the rendered result in Google Chrome at http://127.0.0.1:8091/proof.html, and write ~/workspace/out/manifest_a.json listing the 3 selected sku_ids (in ranked order), their margin_pct values, and proof verification status.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the XCF, PNG, and manifest before finishing.
```

### Actor B — Campaign Copy & Compliance Designer Prompt (verbatim)

```text
You are finalizing the Q4 promotional copy and compliance footer on ~/workspace/campaign/poster_master.xcf (open in GIMP).

First, read ~/workspace/campaign/brand_spec.pdf and query ~/workspace/campaign/sku_catalog.db to identify the highest-priority active Q4 retail promotion and the required compliance disclaimer text matching its tier rules.

Update ~/workspace/campaign/poster_master.xcf while preserving the 1200x1600 layered XCF structure:
- Update promo_badge with the brand-specified highlight color and discount headline derived from the database and spec.
- Update price_grid with the derived promo code and promotional pricing tier text.
- Update legal_footer with the exact required disclaimer text and expiration date.

Ensure all seven layers in poster_master.xcf are visible, save poster_master.xcf, and export the complete 1200x1600 poster to ~/workspace/out/campaign_final.png. Inspect the rendered result in Google Chrome at http://127.0.0.1:8091/proof.html, and write ~/workspace/out/manifest_b.json recording the selected promo_code, disclaimer_id, and proof verification status.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the XCF, PNG, and manifest before finishing.
```

## 4. 冲突触发路径与个人可解性分析

* **GUI + CLI 混用：** 双方先用 CLI 查 SQLite 与 `pdftotext` 读 PDF 推导规则，随后进入 GIMP 或调用 `gimp -i -b` 批处理改 `.xcf`。由于两阶段保存与可见性切换耗时较长，极易撞上 **GUI 内存画布覆盖磁盘 `.xcf`**，以及 **A 隐藏促销层期间 B 导出残缺的 `campaign_final.png`**。
* **个人可解性：** A 的选品与 B 的促销规则互不依赖，单人操作时 100% 确定性可解。

## 5. 离线 Oracle 与细粒度评分

### `subchecks_a`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| A01 | 0.20 | 是 | `manifest_a.json` 中 3 个 `sku_id` 及排序、毛利率推导与宿主机真值完全一致 |
| A02 | 0.15 | 是 | `poster_master.xcf` 中 `slot_1`、`slot_2`、`slot_3` 已替换为对应 Top-3 商品图特征 |
| A03 | 0.15 | 是 | `~/workspace/out/product_clean.png` 存在、可读且尺寸精确为 `1200×1600` |
| A04 | 0.15 | 是 | `product_clean.png` 显示新商品图且促销/价格/页脚区域保持隐藏（无文案像素） |
| A05 | 0.20 | 是 | `poster_master.xcf` 保持合法 7 层结构且 `bg_base` 未损坏 |
| A06 | 0.15 | 否 | 导出后主 XCF 全部图层恢复为可见状态 |

### `subchecks_b`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| B01 | 0.20 | 是 | `manifest_b.json` 中 `promo_code` 与 `disclaimer_id` 推导与宿主机真值完全一致 |
| B02 | 0.20 | 是 | `poster_master.xcf` 中 `promo_badge` 主色与折扣文案匹配规范 |
| B03 | 0.15 | 是 | `poster_master.xcf` 中 `price_grid` 与 `legal_footer` 文本匹配推导结果 |
| B04 | 0.15 | 是 | `~/workspace/out/campaign_final.png` 存在、可读且尺寸精确为 `1200×1600` |
| B05 | 0.15 | 是 | `campaign_final.png` 同时可见全部 7 层内容（含商品槽位与促销/免责文案） |
| B06 | 0.15 | 否 | 文本排版清晰无越界或裁切 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
| :--- | :--- |
| J01 | 最终 `poster_master.xcf` **同时保留** A 的 Top-3 商品槽位与 B 的促销/价格/页脚更新，无单方覆盖回退 |
| J02 | `product_clean.png`（裸图）与 `campaign_final.png`（完整海报）均尺寸准确、图层可见性符合各自要求且未互换 |
| J03 | `poster_master.xcf` 可被标准 GIMP 完整解析，7 个核心图层命名完整 |

## 6. 防作弊与隔离边界

* 宿主机 Oracle 独立保存期望的 Top-3 SKU、活动码、像素采样模板与评分逻辑；Guest 内仅提供原始数据库、规范 PDF 与素材图。

---

# BC-06 — 跨日志精算与合同红线修订（LibreOffice Writer + CSV + PDF）

## 1. 基础元数据

| 字段 | 规格 |
| :--- | :--- |
| Case ID | `BC-06` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | LibreOffice Writer（Track Changes / Redline）、ODT XML、CSV 原始日志、PDF 规范（`pdftotext`） |
| 主源文件 | `~/workspace/legal/msa_contract.odt`；启动时已在 Writer 中打开并开启记录修订 |
| 目标复杂度 | 单人约 55–90 step（脏日志清洗 + 阶梯公式精算 + 跨节 4 处红线修订 + 3 条带证据 ID 批注 + PDF 导出） |
| 主要冲突 | `text:tracked-changes` 修订 XML 难用普通脚本无损合入；Writer 内存缓存覆盖磁盘写入；`soffice` 单实例 Profile 锁阻塞并发 PDF 导出 |

## 2. 初始环境、路径及预置数据

### 2.1 目录结构

```text
~/workspace/legal/msa_contract.odt           # 12 节主服务协议（默认开启 Track Changes），已在 Writer 打开
~/workspace/legal/policy_handbook.pdf        # 商务阶梯违约金与技术 SLA 补偿政策手册
~/workspace/legal/billing_incidents.csv      # 40 条历史账单事件（含 TEST/VOID 脏数据行）
~/workspace/legal/uptime_telemetry.csv       # 60 条服务可用性遥测（含 PLANNED_MAINT 计划维护干扰行）
~/workspace/legal/redline_commercial.pdf     # Actor A 导出带修订痕迹的 PDF
~/workspace/legal/redline_sla.pdf            # Actor B 导出带修订痕迹的 PDF
~/workspace/legal/audit_a.json               # Actor A 精算过程与引用 incident_id 汇总
~/workspace/legal/audit_b.json               # Actor B 精算过程与引用 outage_id 汇总
```

### 2.2 精算与跨节修订规格

* **Actor A（商务与账务法务 — Section 2 & Section 5）**：
  * 清洗 `billing_incidents.csv`（剔除 `record_type IN ('TEST', 'VOID')` 的脏行），按 `policy_handbook.pdf` 计算 Q3 有效逾期率、逾期总金额及对应阶梯档位（确定性推导出目标付款周期、月违约金率、信用抵扣门槛与年度上限 4 处数值）。
  * 在 `msa_contract.odt` **开启 Track Changes（不接受修订）** 的状态下，修改 Section 2（2 处）与 Section 5（2 处）共 4 处条款数值。
  * 在对应条款旁插入 3 条文档批注（Comment），每条批注必须引用 `billing_incidents.csv` 中触发升级的 Top-3 逾期 `incident_id`。
  * 保存 `msa_contract.odt`，导出显示修订与批注的 `~/workspace/legal/redline_commercial.pdf`，并写出 `~/workspace/legal/audit_a.json`。
* **Actor B（技术 SLA 法务 — Section 4 & Section 7）**：
  * 清洗 `uptime_telemetry.csv`（剔除 `window_type = 'PLANNED_MAINT'` 计划维护窗口），按 `policy_handbook.pdf` 计算滚动 90 天真实可用率、P99 违约次数及 Sev-1 响应档位（确定性推导出目标可用率承诺、Sev-1 响应时限、月度服务抵扣比例与连续违约解约阈值 4 处数值）。
  * 在同一个 `msa_contract.odt` **开启 Track Changes（不接受修订）** 的状态下，修改 Section 4（2 处）与 Section 7（2 处）共 4 处条款数值。
  * 插入 3 条文档批注，每条批注必须引用触发降级的 Top-3 严重 `outage_id`。
  * 保存 `msa_contract.odt`，导出显示修订与批注的 `~/workspace/legal/redline_sla.pdf`，并写出 `~/workspace/legal/audit_b.json`。

## 3. 角色边界与完整运行时 Prompt

### Actor A — Commercial Legal Reviewer Prompt (verbatim)

```text
You are conducting a commercial redline review of ~/workspace/legal/msa_contract.odt (open in LibreOffice Writer with Track Changes enabled).

First, read ~/workspace/legal/policy_handbook.pdf and analyze ~/workspace/legal/billing_incidents.csv. Filter out invalid test/void records as defined in the handbook, compute the Q3 effective overdue rate and tier, and determine the four updated commercial terms required for Section 2 (Payment Terms) and Section 5 (Credit & Cap). Also identify the top 3 overdue incident_ids that triggered the tier adjustment.

With Track Changes recording active (do not accept or clear tracked changes), revise the 4 corresponding clauses in Sections 2 and 5 of ~/workspace/legal/msa_contract.odt. Insert 3 document comments attached to the revised clauses citing those top 3 incident_ids and the derived tier rationale. Preserve all other sections.

Save ~/workspace/legal/msa_contract.odt, export a PDF showing tracked changes and comments to ~/workspace/legal/redline_commercial.pdf, and save your computed metrics and cited incident_ids to ~/workspace/legal/audit_a.json.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the saved ODT, exported PDF, and audit JSON before finishing.
```

### Actor B — Technical SLA Legal Reviewer Prompt (verbatim)

```text
You are conducting a technical SLA redline review of ~/workspace/legal/msa_contract.odt (open in LibreOffice Writer with Track Changes enabled).

First, read ~/workspace/legal/policy_handbook.pdf and analyze ~/workspace/legal/uptime_telemetry.csv. Exclude planned maintenance windows as defined in the handbook, compute the rolling 90-day effective availability, P99 breach count, and SLA tier, and determine the four updated technical terms required for Section 4 (Service Level Agreement) and Section 7 (Remedies & Termination). Also identify the top 3 severity outage_ids that triggered the tier adjustment.

With Track Changes recording active (do not accept or clear tracked changes), revise the 4 corresponding clauses in Sections 4 and 7 of ~/workspace/legal/msa_contract.odt. Insert 3 document comments attached to the revised clauses citing those top 3 outage_ids and the derived tier rationale. Preserve all other sections.

Save ~/workspace/legal/msa_contract.odt, export a PDF showing tracked changes and comments to ~/workspace/legal/redline_sla.pdf, and save your computed metrics and cited outage_ids to ~/workspace/legal/audit_b.json.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the saved ODT, exported PDF, and audit JSON before finishing.
```

## 4. 冲突触发路径与个人可解性分析

* **GUI + CLI 混用：** 双方用 CLI 做 CSV 清洗和公式精算后，进入 Writer GUI（或脚本改写 ODT XML）跨多节做 4 处修订与 3 条批注，整个编辑周期拉长，极易触发 **Writer 内存缓存覆盖磁盘**、**光标焦点跨节跳动** 以及并发导出 PDF 时的 **`soffice` 单实例 Profile 锁**。
* **个人可解性：** A 仅操作 Section 2 & 5，B 仅操作 Section 4 & 7，数据源与输出路径完全独立。

## 5. 离线 Oracle 与细粒度评分

### `subchecks_a`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| A01 | 0.20 | 是 | `audit_a.json` 中清洗后的逾期率、阶梯档位与 Top-3 `incident_id` 与真值一致 |
| A02 | 0.20 | 是 | `msa_contract.odt` Section 2 & 5 的 4 处最终有效条款数值全部准确 |
| A03 | 0.20 | 是 | `content.xml` 保留对应 Section 2 & 5 的真实 `text:tracked-changes` 修订记录（未抹平） |
| A04 | 0.15 | 是 | Section 2 & 5 包含 3 条 `office:annotation` 批注且准确引用 Top-3 `incident_id` |
| A05 | 0.15 | 是 | `redline_commercial.pdf` 存在、可读，`pdftotext` 提取含新条款与批注 |
| A06 | 0.10 | 否 | 合同其余 8 个非目标章节原文未损坏 |

### `subchecks_b`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| B01 | 0.20 | 是 | `audit_b.json` 中清洗后的可用率、违约次数与 Top-3 `outage_id` 与真值一致 |
| B02 | 0.20 | 是 | `msa_contract.odt` Section 4 & 7 的 4 处最终有效条款数值全部准确 |
| B03 | 0.20 | 是 | `content.xml` 保留对应 Section 4 & 7 的真实 `text:tracked-changes` 修订记录（未抹平） |
| B04 | 0.15 | 是 | Section 4 & 7 包含 3 条 `office:annotation` 批注且准确引用 Top-3 `outage_id` |
| B05 | 0.15 | 是 | `redline_sla.pdf` 存在、可读，`pdftotext` 提取含新条款与批注 |
| B06 | 0.10 | 否 | 合同其余 8 个非目标章节原文未损坏 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
| :--- | :--- |
| J01 | 最终 `msa_contract.odt` **同时保留** A（Section 2 & 5）与 B（Section 4 & 7）的全部修订记录与批注，无单方覆盖回退 |
| J02 | `redline_commercial.pdf` 与 `redline_sla.pdf` 均存在、非空且可读 |
| J03 | ODT ZIP 与 `content.xml` 格式完整可解析，未破坏其余章节 |

## 6. 防作弊与隔离边界

* Guest 仅包含合同与原始日志/政策 PDF；宿主机 Oracle 离线独立计算真值并解析回收后的 ODT 与 PDF。

---

# BC-07 — 两阶段跨标签调度台核销（Google Chrome + BroadcastChannel + SQLite）

## 1. 基础元数据

| 字段 | 规格 |
| :--- | :--- |
| Case ID | `BC-07` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | Google Chrome、本地调度台 Web（`BroadcastChannel` + `localStorage` + SQLite 后端）、CSV/PDF 规则 |
| 本地入口 | `http://127.0.0.1:8092/`；仅绑定 Guest loopback |
| 目标复杂度 | 单人约 60–95 step（30 行脏数据筛选 + Phase 1 预检拿动态 Token + 解析服务端报错改派/覆写 + Phase 2 正式提交） |
| 主要冲突 | 同源 `BroadcastChannel` + `localStorage` 实时同步覆盖全局视图与批量草稿箱；动态两阶段 Token 防止盲写一次性脚本；SQLite 并发写锁 |

## 2. 初始环境、路径及预置数据

### 2.1 目录结构

```text
~/workspace/dispatch/warehouse_rules.pdf      # 仓储温控、溢出仓位改派与报关覆写规则
~/workspace/dispatch/inbound_manifest.csv     # 30 条待入库清单（含破损/温控超标干扰项，恰有 6 条合规）
~/workspace/dispatch/outbound_orders.csv      # 30 条待发运订单（含信用冻结/缺质检干扰项，恰有 6 条可放行）
~/workspace/dispatch/customs_overrides.csv    # 报关单号覆写对照表（供 Phase 2 纠偏查表）
~/workspace/dispatch/inbound_audit.json       # Actor A 最终入库核销审计报告
~/workspace/dispatch/outbound_audit.json      # Actor B 最终出库放行审计报告
```

### 2.2 两阶段交互与冲突机制

* 启动时 Google Chrome 已打开 `http://127.0.0.1:8092/`。前端通过 `BroadcastChannel("dispatch_console_sync")` 与 `localStorage` 在所有同源标签页间同步：当前激活视图（`inbound` / `outbound`）、筛选条件、批量草稿箱（`batch_draft`）以及当前暂存的预检状态。
* **Actor A（入库分配主管 — Inbound 两阶段）**：
  1. **数据筛选**：按 `warehouse_rules.pdf` 从 30 条 `inbound_manifest.csv` 中筛出 6 条合规入库单（排除 `damage_flag=1` 或温控越界记录），分配初始主仓位。
  2. **Phase 1 预检**：在调度台 Inbound 视图提交预检，服务端返回动态 `allocation_token` 并报出其中 2 条冷链单据目标仓位满载（`BIN_FULL`）。
  3. **Phase 2 改派与正式提交**：按 `warehouse_rules.pdf` 的溢出规则将这 2 条单据改派至指定冷链备用仓位，携带 `allocation_token` 完成正式提交（状态变更为 `RECEIVED`），并导出 `~/workspace/dispatch/inbound_audit.json`。
* **Actor B（出库放行主管 — Outbound 两阶段）**：
  1. **数据筛选**：按 `warehouse_rules.pdf` 从 30 条 `outbound_orders.csv` 中筛出 6 条可放行订单（排除 `credit_hold=1` 或 `qa_status != 'PASS'`）。
  2. **Phase 1 合规校验**：在调度台 Outbound 视图提交校验，服务端返回动态 `release_token` 并报出其中 2 条跨境单据报关单号不匹配（`CUSTOMS_MISMATCH`）。
  3. **Phase 2 覆写与正式放行**：查阅 `customs_overrides.csv` 补录对应覆写码，携带 `release_token` 完成正式放行（状态变更为 `RELEASED`），并导出 `~/workspace/dispatch/outbound_audit.json`。

## 3. 角色边界与完整运行时 Prompt

### Actor A — Inbound Allocation Lead Prompt (verbatim)

```text
You are processing Q4 inbound stock allocation in the local dispatch console at http://127.0.0.1:8092/ (open in Google Chrome).

First, read ~/workspace/dispatch/warehouse_rules.pdf and filter ~/workspace/dispatch/inbound_manifest.csv to identify the 6 compliant inbound orders (excluding damaged or temperature-violated items) and their initial primary bin assignments.

In the Inbound view of the console, stage these 6 orders and run Phase 1 Pre-Check to obtain a dynamic allocation_token. Review any capacity conflict errors returned by the pre-check, reassign affected orders to overflow bins strictly according to warehouse_rules.pdf, and complete Phase 2 Final Commit using the allocation_token so all 6 orders reach RECEIVED status.

Verify in the console that all 6 orders show RECEIVED with final bin codes, and save ~/workspace/dispatch/inbound_audit.json containing the 6 order_ids, final bin_codes, reassigned flags, allocation_token, and final status. Do not alter unrelated orders.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the console state and audit JSON before finishing.
```

### Actor B — Outbound Release Lead Prompt (verbatim)

```text
You are processing Q4 outbound shipment release in the local dispatch console at http://127.0.0.1:8092/ (open in Google Chrome).

First, read ~/workspace/dispatch/warehouse_rules.pdf and filter ~/workspace/dispatch/outbound_orders.csv to identify the 6 eligible outbound orders (excluding credit-held or failed-QA items).

In the Outbound view of the console, stage these 6 orders and run Phase 1 Compliance Check to obtain a dynamic release_token. Review any customs mismatch errors returned by the check, look up the approved override codes in ~/workspace/dispatch/customs_overrides.csv, apply them, and complete Phase 2 Final Release using the release_token so all 6 orders reach RELEASED status.

Verify in the console that all 6 orders show RELEASED with applied override codes where needed, and save ~/workspace/dispatch/outbound_audit.json containing the 6 order_ids, override_codes, release_token, and final status. Do not alter unrelated orders.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the console state and audit JSON before finishing.
```

## 4. 冲突触发路径与个人可解性分析

* **GUI + CLI 混用：** 两阶段流程需要多次与调度台交互；每当一方切换视图、运行 Phase 1 或提交清空草稿箱时，`BroadcastChannel` 与 `localStorage` 会立刻同步刷掉另一方浏览器里的未提交草稿与视图状态；同时动态 Token 与 SQLite 写锁使纯 CLI 脚本也必须经历完整的预检-纠偏-提交重试周期。
* **个人可解性：** 入库与出库单据集合完全不相交，单人按两阶段流程即可 100% 完成。

## 5. 离线 Oracle 与细粒度评分

### `subchecks_a`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| A01 | 0.20 | 是 | 后端 DB 中 6 笔目标合规入库单均达 `RECEIVED`，且 24 笔干扰单未被误入库 |
| A02 | 0.20 | 是 | 4 笔常规入库单的主仓位编码与规则完全一致 |
| A03 | 0.25 | 是 | 2 笔触发 `BIN_FULL` 的冷链单据均按溢出规则正确改派至备用仓位 |
| A04 | 0.20 | 是 | `inbound_audit.json` 存在、合法，记录 6 笔最终仓位及服务端真实签发的 `allocation_token` |
| A05 | 0.15 | 否 | 未误改无关出库单据 |

### `subchecks_b`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| B01 | 0.20 | 是 | 后端 DB 中 6 笔目标可放行出库单均达 `RELEASED`，且 24 笔干扰单未被误放行 |
| B02 | 0.20 | 是 | 4 笔常规出库单放行记录完整无误 |
| B03 | 0.25 | 是 | 2 笔触发 `CUSTOMS_MISMATCH` 的跨境单据均准确填入 `customs_overrides.csv` 覆写码 |
| B04 | 0.20 | 是 | `outbound_audit.json` 存在、合法，记录 6 笔放行结果及服务端真实签发的 `release_token` |
| B05 | 0.15 | 否 | 未误改无关入库单据 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
| :--- | :--- |
| J01 | 后端 DB 同时保留 6 笔 `RECEIVED` 入库单与 6 笔 `RELEASED` 出库单的完整最终状态 |
| J02 | `inbound_audit.json` 与 `outbound_audit.json` 均存在、字段合法且无视图/数据串行 |

## 6. 防作弊与隔离边界

* 动态 `allocation_token` / `release_token` 由本地服务在 Phase 1 真实签发并写入后端审计表；宿主机 Oracle 核对 JSON 中的 Token 是否真实签发，防止跳过交互直接手写假 JSON。

---

# BC-08 — 共享 Git 主分支全栈特性联调（Git + VS Code + Python 服务 + Google Chrome）

## 1. 基础元数据

| 字段 | 规格 |
| :--- | :--- |
| Case ID | `BC-08` |
| Track | Blind Concurrency / Shared 双 Actor |
| 软件栈 | Git（`main` 分支）、VS Code / Guest CLI、Python 本地全栈服务（`portal.db`）、Google Chrome |
| 本地入口 | `http://127.0.0.1:8096/`；仅绑定 Guest loopback |
| 仓库路径 | `~/workspace/ops-portal/`（`main` 分支，初始工作区干净） |
| 目标复杂度 | 单人约 60–95 step（读需求 PDF + 查 SQLite Schema + 改后端 API/前端模板/JS + 重启服务 + Chrome 多条件实测 + Git 干净提交） |
| 主要冲突 | 共享 `app.py`、`templates/layout.html`、`static/app.js` 并发覆写；**共用 `portalctl restart` 重启服务互断对方 Chrome 验收**；`.git/index.lock` 与 `main` 分支脏工作区互相污染提交 |

## 2. 初始环境、路径及预置数据

### 2.1 目录结构

```text
~/workspace/ops-portal/
  ├── app.py                        # 共享 Python Web 后端（标准库 http.server / wsgi，端口 8096）
  ├── templates/layout.html         # 共享前端主模板（含顶部导航与内容区挂载点）
  ├── static/app.js                 # 共享前端交互脚本
  ├── portal.db                     # 预置 SQLite 数据库（含 metrics_daily 与 incidents 两张表，各 30+ 行）
  ├── bin/portalctl                 # 服务控制脚本（status / restart），重启时重载 app.py 与静态资源
  ├── specs/spec_metrics.pdf        # Actor A 指标统计特性规格书
  ├── specs/spec_triage.pdf         # Actor B 告警分诊特性规格书
  └── .git/                         # 本地 Git 仓库（main 分支，已配 user.name/user.email）
~/workspace/verify_metrics.json     # Actor A 实测与 commit 核验记录
~/workspace/verify_triage.json      # Actor B 实测与 commit 核验记录
```

### 2.2 两侧开发与验收规格

* **Actor A（指标统计特性开发）**：
  * 阅读 `specs/spec_metrics.pdf` 并查看 `portal.db` 的 `metrics_daily` 表结构。
  * 在 `app.py` 新增 `GET /api/metrics/summary?start=YYYY-MM-DD&end=YYYY-MM-DD` 接口：过滤日期区间、忽略 `NULL` 异常采样行、返回精确聚合的 `avg_latency_ms`、`total_requests`、`error_rate_pct`（保留 2 位小数）。
  * 在 `templates/layout.html` 顶部导航新增 `Metrics` 入口，在 `static/app.js` 实现日期筛选与 KPI 卡片渲染。
  * 执行 `bin/portalctl restart` 重启服务，在 Google Chrome 打开 `http://127.0.0.1:8096/` 实测 `spec_metrics.pdf` 指定的 3 组日期区间并核验页面 KPI 数值。
  * 在 `main` 分支做干净 Git Commit，将 3 组实测结果与 commit hash 写入 `~/workspace/verify_metrics.json`。
* **Actor B（告警分诊特性开发）**：
  * 阅读 `specs/spec_triage.pdf` 并查看 `portal.db` 的 `incidents` 表结构。
  * 在同一个 `app.py` 新增 `GET /api/incidents/export?severity=<LEVEL>` 接口：按严重级别过滤、按 `created_at DESC` 排序、返回清洗后的标准 CSV（含 `incident_id,service,severity,status,created_at` 列）。
  * 在同一个 `templates/layout.html` 顶部导航新增 `Triage` 入口，在 `static/app.js` 实现严重级别筛选列表与一键导出按钮。
  * 执行 `bin/portalctl restart` 重启服务，在 Google Chrome 打开 `http://127.0.0.1:8096/` 实测 `CRITICAL` 与 `HIGH` 筛选及 CSV 导出。
  * 在 `main` 分支做干净 Git Commit，将实测计数与 commit hash 写入 `~/workspace/verify_triage.json`。

## 3. 角色边界与完整运行时 Prompt

### Actor A — Metrics Feature Developer Prompt (verbatim)

```text
You are implementing the Metrics Summary feature in the local ops portal repository at ~/workspace/ops-portal/ (on the main Git branch, served at http://127.0.0.1:8096/ and open in Google Chrome).

Read ~/workspace/ops-portal/specs/spec_metrics.pdf and inspect portal.db. Implement the feature across the codebase:
1. In app.py, add GET /api/metrics/summary supporting start and end date query parameters, excluding NULL metric rows as specified, and returning JSON with avg_latency_ms, total_requests, and error_rate_pct (rounded to 2 decimals).
2. In templates/layout.html and static/app.js, add the Metrics navigation link, date-range filter controls, and KPI summary cards wired to the new endpoint.

Restart the portal via ~/workspace/ops-portal/bin/portalctl restart. Verify the UI and API in Google Chrome across the three date ranges specified in spec_metrics.pdf. Commit your changes cleanly on the main branch, ensure the working tree is clean, and save the commit hash and 3-range verification results to ~/workspace/verify_metrics.json.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the live service, Git state, and JSON record before finishing.
```

### Actor B — Incident Triage Developer Prompt (verbatim)

```text
You are implementing the Incident Triage & Export feature in the local ops portal repository at ~/workspace/ops-portal/ (on the main Git branch, served at http://127.0.0.1:8096/ and open in Google Chrome).

Read ~/workspace/ops-portal/specs/spec_triage.pdf and inspect portal.db. Implement the feature across the codebase:
1. In app.py, add GET /api/incidents/export supporting the severity query parameter, sorted by created_at DESC, returning a clean CSV with columns incident_id,service,severity,status,created_at.
2. In templates/layout.html and static/app.js, add the Triage navigation link, severity filter panel, and CSV export button wired to the new endpoint.

Restart the portal via ~/workspace/ops-portal/bin/portalctl restart. Verify the UI, filtering, and CSV export in Google Chrome for the severity levels specified in spec_triage.pdf. Commit your changes cleanly on the main branch, ensure the working tree is clean, and save the commit hash and verification counts to ~/workspace/verify_triage.json.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify the live service, Git state, and JSON record before finishing.
```

## 4. 冲突触发路径与个人可解性分析

* **三层并发叠加：**
  1. **共享源码覆写：** 双方同时修改 `app.py`、`layout.html`、`app.js`，整文件写回极易擦除对方路由或前端绑定。
  2. **服务重启断连：** `portalctl restart` 会短暂中断 `:8096`，打断另一方正在 Chrome 中进行的接口与页面实测。
  3. **Git 锁与脏工作区：** 并发 `git add` / `git commit` 撞上 `.git/index.lock`，且 `git add .` 容易把对方改到一半带语法错误的文件误提交或冲掉。
* **个人可解性：** 两条 API、两张 DB 表与两块前端面板完全独立，单人开发并重启测试 100% 可解。

## 5. 离线 Oracle 与细粒度评分

### `subchecks_a`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| A01 | 0.20 | 是 | 在线服务 `GET /api/metrics/summary` 对 3 组测试日期区间返回 200 且数值与真值精确匹配（误差 $\le 0.01$） |
| A02 | 0.20 | 是 | `templates/layout.html` 与 `static/app.js` 包含 Metrics 导航、筛选控件与 `/api/metrics/summary` 调用 |
| A03 | 0.20 | 是 | `main` 分支 Git 历史存在包含指标特性的有效 Commit |
| A04 | 0.20 | 是 | `~/workspace/verify_metrics.json` 存在、包含存在于 `git log` 的 commit hash 及准确的 3 组实测数值 |
| A05 | 0.20 | 是 | 首页 `http://127.0.0.1:8096/` 返回 200 且无 JS/模板语法损坏 |

### `subchecks_b`（权重总和 = 1.000）

| ID | 权重 | required | 检查 |
| :--- | ---: | :--- | :--- |
| B01 | 0.20 | 是 | 在线服务 `GET /api/incidents/export` 对 `CRITICAL`、`HIGH` 返回 200，CSV 列、排序与行数与真值完全匹配 |
| B02 | 0.20 | 是 | `templates/layout.html` 与 `static/app.js` 包含 Triage 导航、严重级别筛选与 `/api/incidents/export` 调用 |
| B03 | 0.20 | 是 | `main` 分支 Git 历史存在包含分诊特性的有效 Commit |
| B04 | 0.20 | 是 | `~/workspace/verify_triage.json` 存在、包含存在于 `git log` 的 commit hash 及准确的实测计数 |
| B05 | 0.20 | 是 | 首页 `http://127.0.0.1:8096/` 返回 200 且无 JS/模板语法损坏 |

### `subchecks_joint`（全部 required）

| ID | Joint 条件 |
| :--- | :--- |
| J01 | 最终运行中的 `:8096` 服务**同时**正常响应 `/api/metrics/summary` 与 `/api/incidents/export`，无单方路由丢失 |
| J02 | `layout.html` 与 `app.js` **同时保留** Metrics 与 Triage 两个前端功能模块 |
| J03 | Git 仓库位于 `main` 分支且工作区干净（无未提交脏文件、无 `.git/index.lock` 或冲突标记 `<<<<<<<`） |

## 6. 防作弊与隔离边界

* Guest 仅包含仓库与 `portal.db`；宿主机 Oracle 独立连接只读副本计算真值，并通过 host bridge 采集最终在线服务的 HTTP 响应与 Git 状态。

---

## 7. 批次准入与实现注意事项

1. 本版全部使用已探明的 Guest 原生依赖（`google-chrome`、`gimp`、`libreoffice`、`git`、`code`、`Python 3.10 + sqlite3 + PyYAML + Pillow + pdftotext`），无需额外装包。
2. 实现时沿用 `case_work/20261126-shared-case-pipeline-v1/` 统一脚手架，落盘 `grade.json`、`shared_timeline.json`、`permission-audit-verified.json` 与离线 Oracle 单元测试。
3. **设计中明确不做的事情：** 不写死操作顺序或锁步脚本；不向任一 Prompt 暗示存在另一操作员或共享桌面；不限制 `guest_cli` 的工作区读写执行能力；不触碰任何旧 C01–C24 代码、状态或历史归档。