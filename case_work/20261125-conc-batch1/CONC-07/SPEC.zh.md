# CONC-07: 企业双部门月结端到端闭环（2.5x 重型长程并发）

> 语言实现要求：本规格文档采用中文撰写以便审阅；Codex 在生成实际代码时，须将所有输入数据、网页界面文案、质检单与图表文字、数据库字段注释、幻灯片文本及注入给 Actor A / Actor B 的运行时提示词全部转为英文。

## 1. 元信息

* **Case ID**: `CONC-07`

* **复杂度梯度**: `heavy_2.5x`（长程多阶段端到端真实工作流，目标混跑耗时 `25–35 min`）

* **协作模式**: `independent_concurrent`

* **冲突定律**: `LAW_1`, `LAW_2`, `LAW_3`, `LAW_4`, `LAW_5`, `LAW_6`（全定律复合触发）

* **依赖环境**: Google Chrome, LibreOffice Impress, SQLite3, Python 3.10.12, GNOME X11, `pdftoppm`

* **评分模式**: 纯确定性规则校验，共 44 项检查点，无 LLM Judge

* **对称与重叠目标**: `horizon_symmetry_ratio >= 0.85`，预测并发重叠时长 `>= 900s`

* **共享冲突资源**: 单实例 Chrome、`/workspace/shared/enterprise_ops.db`、`~/Downloads`、单进程 `soffice.bin`

* **交付根目录**: `/workspace/out_a/`, `/workspace/out_b/`

## 2. 运行环境与服务初始化

### 2.1 共享基础设施初始化

* **SQLite 数据库 (`/workspace/shared/enterprise_ops.db`)**:

  * 显式设置为默认 Rollback Journal 模式（`PRAGMA journal_mode=DELETE;`），禁止开启 WAL，预建两张独立业务表：
    * `supplier_settlements(supplier_id TEXT PRIMARY KEY, gross_amount REAL, deduction REAL, net_payable REAL, has_dispute INTEGER, batch_code TEXT)`
    * `campaign_audits(channel_id TEXT PRIMARY KEY, spend REAL, revenue REAL, roi REAL, alert_flag INTEGER, lock_code TEXT)`

* **单实例 Chrome 与预登录**:

  * 启动 1 个 Chrome 窗口并预开 2 个标签页：`http://127.0.0.1:18131`（SupplyPortal，归 A）与 `http://127.0.0.1:18132`（AdPulse，归 B），均采用仅存浏览器内存的 `HttpOnly` Session Cookie 预登录。

* **共享 `soffice.bin` 进程**:

  * 预部署 2 份 7 页草稿至 `/workspace/out_a/Q4_Supplier_Review.pptx` 与 `/workspace/out_b/Promo_Postmortem.pptx`，并在桌面同一 `soffice.bin` 进程下同时打开两份文档。

### 2.2 Actor A 业务环境（供应链月结闭环）

* **本地服务 `18131` (`SupplyPortal`)**:

  * **宽屏守卫**: 仅当 `window.outerWidth >= 1600` 时解锁操作栏与下载按钮，窗口过窄时显示红色提示并禁用交互；

  * 提供 6 家供应商（`SUP-01` 至 `SUP-06`）的对账明细 CSV 下载，以及 3 张交付准时率趋势图 PNG 下载（固定下载文件名 **`figure.png`** 至 `~/Downloads`）；

  * 提供异常供应商申诉模块：每行含**失焦自动收起**的操作下拉菜单，内含原生 `<input type="file">` 上传质检佐证图入口；全部 6 家写入数据库且 2 家异常单上传佐证后，点击 `Finalize Batch` 触发服务端持锁 `2.0s` 的 SQLite 写事务校验，成功则返回动态随机 `batch_code` 并回填校验表。

* **本地素材 (`/workspace/in_a/`)**:

  * `brand_swatch_a.png`（纯色 `#2E7D32`，不写明文色值）；

  * `/workspace/in_a/qc_sheets/`: 6 张程序生成的正规商务电子质检单 PNG（其中 `SUP-02` 与 `SUP-05` 图面印有明确的扣款金额与 `DEFECT DEDUCTION` 红章，其余 4 家无扣款；扣款额仅存于光栅图内）；

  * `review_spec_a.txt`: 规定 7 页 `Q4_Supplier_Review.pptx` 的封面标题、6 家汇总表结构、3 张趋势图对应页码及安全区、2 家整改说明页及第 7 页偏长结语/备注（含溢出陷阱）。

### 2.3 Actor B 业务环境（大促营销复盘闭环）

* **本地服务 `18132` (`AdPulse`)**:

  * **移动端巡检子页 (`/mobile-check`)**: 要求将 Chrome 外部窗口缩至 **`375x812` (`±20px`)** 检查 2 个大促落地页（`LP-1`, `LP-2`），点击校验按钮验证真实 `outerWidth` 并获取 2 张移动端巡检截图（`mobile_lp_1.png`, `mobile_lp_2.png`）；

  * **宽屏看板子页 (`/dashboard`)**: 要求窗口宽度 **`>= 1600px`**，包含 6 个投放渠道（`CH-01` 至 `CH-06`）的 Canvas 转化曲线，每个渠道有 1 个须鼠标真实悬停方可读取的隐藏 `Peak ROI` 数值（同时记录预算超支告警条件），并提供 3 张渠道汇总图 PNG 下载（固定下载文件名 **`figure.png`** 至 `~/Downloads`）；

  * 提供备案提交模块：通过**失焦自动收起**下拉菜单 + 原生 `<input type="file">` 上传上述 2 张移动端巡检图；6 渠道写入 `campaign_audits` 且备案图上传后，点击 `Lock Report` 触发服务端持锁 `2.0s` 的 SQLite 写事务校验，返回动态随机 `lock_code`。

* **本地素材 (`/workspace/in_b/`)**:

  * `brand_swatch_b.png`（纯色 `#1565C0`，不写明文色值）；

  * `campaign_spend.csv`: 6 个投放渠道的基础花费与预算上限；

  * `postmortem_spec_b.txt`: 规定 7 页 `Promo_Postmortem.pptx` 的封面标题、第 3 与第 4 页对调指示、6 渠道效果表、3 张渠道图对应页码、移动端异常页及第 7 页偏长复盘要点/备注（含溢出陷阱）。

## 3. Actor 提示词规格

### Actor A 提示词

```
你正在共享的 Ubuntu 桌面环境中执行端到端月结任务，另一位代理会并发使用同一桌面、浏览器、下载目录、数据库文件及办公软件处理独立任务。可自由使用 GUI 或 CLI。

请完成以下 4 阶段供应链月结闭环：
1. 【采数与看图】在 Chrome 的 SupplyPortal（http://127.0.0.1:18131，要求窗口宽度 >= 1600px）下载全部 6 家供应商（SUP-01 至 SUP-06）的对账 CSV 与 3 张交付趋势图 PNG（下载至 Downloads，注意甄别同名 figure.png）；逐张核对 `/workspace/in_a/qc_sheets/` 下的 6 张质检单图片，识别存在扣款的 2 家供应商及其精确扣款金额。
2. 【入库与申诉】计算 6 家净应付额，写入共享数据库 `/workspace/shared/enterprise_ops.db` 的 `supplier_settlements` 表（注意并发写锁重试与完整性校验）；在 SupplyPortal 为 2 家扣款供应商上传对应质检单 PNG 提交申诉，随后点击 "Finalize Batch" 获取批次校验码并更新至数据库。
3. 【7 页简报精修】参照 `/workspace/in_a/review_spec_a.txt` 与 `brand_swatch_a.png`，更新桌面已打开的 `/workspace/out_a/Q4_Supplier_Review.pptx`（封面改色、6 家核对表、插入 3 张正确趋势图且无遮挡、整改页、第 7 页要点与备注防溢出）。
4. 【导出与交付】保存 PPTX，导出 7 页 PDF 至 `/workspace/out_a/Q4_Supplier_Review.pdf` 并检查排版无重叠溢出；输出汇总报告 `/workspace/out_a/settlement_audit.json`（含 6 家明细、2 家异常列表与 `batch_code`）。
```

### Actor B 提示词

```
你正在共享的 Ubuntu 桌面环境中执行端到端复盘任务，另一位代理会并发使用同一桌面、浏览器、下载目录、数据库文件及办公软件处理独立任务。可自由使用 GUI 或 CLI。

请完成以下 4 阶段大促营销复盘闭环：
1. 【窄屏巡检与宽屏采数】在 Chrome 的 AdPulse（http://127.0.0.1:18132）：先将窗口调至约 375x812（±20px）完成 `/mobile-check` 下 2 个落地页巡检并保存无遮挡截图至 `/workspace/out_b/mobile_lp_1.png`、`/workspace/out_b/mobile_lp_2.png`；再将窗口调至宽度 >= 1600px，在 `/dashboard` 逐一悬停读取 6 个投放渠道（CH-01 至 CH-06）的 Canvas 峰值 ROI，并下载 3 张渠道汇总图 PNG（下载至 Downloads，注意甄别同名 figure.png）。
2. 【入库与备案】结合 `/workspace/in_b/campaign_spend.csv` 计算 6 渠道营收与超支告警标志，写入共享数据库 `/workspace/shared/enterprise_ops.db` 的 `campaign_audits` 表（注意并发写锁重试）；在 AdPulse 上传上述 2 张移动端巡检图完成备案，随后点击 "Lock Report" 获取锁定校验码并更新至数据库。
3. 【7 页复盘精修】参照 `/workspace/in_b/postmortem_spec_b.txt` 与 `brand_swatch_b.png`，更新桌面已打开的 `/workspace/out_b/Promo_Postmortem.pptx`（封面改色、按要求对调第 3 与第 4 页、6 渠道效果表、插入 3 张正确渠道图且无遮挡、第 7 页要点与备注防溢出）。
4. 【导出与交付】保存 PPTX，导出 7 页 PDF 至 `/workspace/out_b/Promo_Postmortem.pdf` 并检查排版无重叠溢出；输出汇总报告 `/workspace/out_b/campaign_summary.json`（含 6 渠道明细与 `lock_code`）。
```

## 4. 确定性评分检查点（44 项）

每项返回布尔值，总分 = 通过项数 / 44。

### Actor A（22 项）

* `A01`: `enterprise_ops.db` 通过 `PRAGMA integrity_check` 且 `supplier_settlements` 恰好包含 6 行无丢失。

* `A02`–`A07`: 6 家供应商各自的 `gross_amount`、`deduction`、`net_payable`、`has_dispute` 与真值精确匹配。

* `A08`: `SUP-02` 与 `SUP-05` 在服务 A 后端的申诉记录均已提交且上传图片 SHA-256 与对应质检单一致。

* `A09`: 后端日志确认 `Finalize Batch` 成功执行且数据库与 JSON 中的 `batch_code` 精确匹配动态真值。

* `A10`: `/workspace/out_a/settlement_audit.json` 存在、合法且核心数值与数据库完全一致。

* `A11`: `/workspace/out_a/Q4_Supplier_Review.pptx` 存在、可解析且恰好 7 页。

* `A12`: PPTX 第 1 页标题准确且横幅填充色与 `#2E7D32` 各通道误差 `<= 3`。

* `A13`–`A14`: PPTX 供应商汇总表 6 行数值准确（拆分为前 3 家与后 3 家 2 项）。

* `A15`–`A17`: PPTX 嵌入的 3 张交付趋势图 SHA-256 精确匹配服务 A 真值图表（绝无混入 B 的渠道图）。

* `A18`: 3 张图表边界框均在安全区内且与同页文本框零重叠。

* `A19`: 异常整改页准确包含 `SUP-02` 与 `SUP-05` 的扣款金额与原因。

* `A20`: 第 7 页结语核心句与演讲者备注完整且无底部溢出。

* `A21`: `/workspace/out_a/Q4_Supplier_Review.pdf` 存在、合法且恰好 7 页。

* `A22`: `pdftoppm` 渲染 7 页 PDF 校验无空白页、第 1 页命中 `#2E7D32` 色块、图表页命中特征区域且第 7 页无溢出墨迹。

### Actor B（22 项）

* `B01`: `enterprise_ops.db` 通过 `PRAGMA integrity_check` 且 `campaign_audits` 恰好包含 6 行无丢失。

* `B02`–`B07`: 6 个渠道各自的 `spend`、`revenue`、`roi`、`alert_flag` 与真值精确匹配。

* `B08`: 服务 B 后端日志确认 2 个移动端落地页在 `355 <= outerWidth <= 395` 下完成真实校验，且 6 个渠道峰值均在 `outerWidth >= 1600` 下触发真实悬停。

* `B09`: `mobile_lp_1.png`、`mobile_lp_2.png` 存在且宽度符合窄屏范围、命中对应页面识别条，且服务 B 后端接收的备案附件 SHA-256 与两张截图一致。

* `B10`: 后端日志确认 `Lock Report` 成功执行且数据库与 JSON 中的 `lock_code` 精确匹配动态真值。

* `B11`: `/workspace/out_b/campaign_summary.json` 存在、合法且核心数值与数据库完全一致。

* `B12`: `/workspace/out_b/Promo_Postmortem.pptx` 存在、可解析、恰好 7 页且第 3 与第 4 页顺序对调正确。

* `B13`: PPTX 第 1 页标题准确且横幅填充色与 `#1565C0` 各通道误差 `<= 3`。

* `B14`–`B15`: PPTX 6 渠道效果表数值准确（拆分为前 3 渠道与后 3 渠道 2 项）。

* `B16`–`B18`: PPTX 嵌入的 3 张渠道图 SHA-256 精确匹配服务 B 真值图表（绝无混入 A 的供应链图）。

* `B19`: 3 张图表边界框均在安全区内且与同页文本框零重叠。

* `B20`: 第 7 页复盘核心句与演讲者备注完整且无底部溢出。

* `B21`: `/workspace/out_b/Promo_Postmortem.pdf` 存在、合法且恰好 7 页。

* `B22`: `pdftoppm` 渲染 7 页 PDF 校验无空白页、第 1 页命中 `#1565C0` 色块、图表页命中特征区域且第 7 页无溢出墨迹。

## 5. 防作弊与工程实现约束

1. **全链路复合冲突**: 两服务共享内存态 Chrome、共享 `~/Downloads/figure.png` 下载名、共享非 WAL SQLite 库、共享 `soffice.bin` 进程，确保在 25–35 分钟全流程中持续存在高密度并发争用。

2. **视觉数据隔离**: 质检单扣款额、品牌色卡、Canvas 悬停 ROI 均不以明文形式出现在 HTML 或文本素材中。

3. **冲突指标埋点**: 额外统计 `sqlite_busy_count`、视口宽度翻转次数、`~/Downloads` 重名覆盖次数、失焦菜单关闭次数及跨角色错图命中次数，全程保留关键阶段快照供次日验收。