# CONC-08: 年度共享总账多部门联编与封账闭环（2.5x 重型压轴）

> 语言实现要求：本规格文档采用中文撰写以便审阅；Codex 在生成实际代码时，须将所有输入数据、网页界面文案、发票与批文图片文字、表格表头、幻灯片文本及注入给 Actor A / Actor B 的运行时提示词全部转为英文。

## 1. 元信息

* **Case ID**: `CONC-08`

* **复杂度梯度**: `heavy_2.5x`（长程多阶段端到端真实工作流，目标混跑耗时 `25–35 min`）

* **协作模式**: `independent_concurrent`

* **冲突定律**: `LAW_6`, `LAW_2`, `LAW_3`, `LAW_1`, `LAW_5`

* **依赖环境**: Google Chrome, LibreOffice Calc（须前置探针验证）, LibreOffice Impress, Python 3.10.12, GNOME X11, `pdftoppm`

* **前置探针策略**: 若 Guest 镜像经探针检测未安装 `libreoffice --calc`，允许跳过本案例并在状态报告中标记 `SKIPPED_NO_CALC`，不得阻塞 `CONC-01`–`CONC-07` 的运行。

* **评分模式**: 纯确定性规则校验，共 46 项检查点，无 LLM Judge

* **对称与重叠目标**: `horizon_symmetry_ratio >= 0.85`，预测并发重叠时长 `>= 900s`

* **共享冲突文件**: `/workspace/shared/Corp_Annual_2026.xlsx`

* **交付根目录**: `/workspace/out_a/`, `/workspace/out_b/`

## 2. 运行环境与服务初始化

### 2.1 共享办公软件与浏览器初始状态

* **共享总账 (`/workspace/shared/Corp_Annual_2026.xlsx`)**:

  * 内含 3 个工作表：`FX_Tax_Rates`（只读基准汇率与税率表）、`Rev_Ledger`（归 A 填写的半成品骨架表）、`HR_Cost`（归 B 填写的半成品骨架表）。

* **预打开单进程 `soffice.bin`**:

  * Setup 将 2 份 4 页简报草稿部署至 `/workspace/out_a/Finance_Close.pptx` 与 `/workspace/out_b/HR_Close.pptx`；

  * 在桌面通过默认 LibreOffice 配置启动同一 `soffice.bin` 进程，同时预打开 `Corp_Annual_2026.xlsx`、`Finance_Close.pptx` 与 `HR_Close.pptx`，建立真实跨组件单进程锁状态。

* **单实例 Chrome**:

  * 启动 1 个 Chrome 窗口预开 2 个标签页：`http://127.0.0.1:18141`（FinAudit 财务冲销后台，归 A）与 `http://127.0.0.1:18142`（HRDesk 人力特批后台，归 B），均采用仅存浏览器内存的 `HttpOnly` Session Cookie 预登录。

### 2.2 Actor A 素材与服务（财务营收封账）

* **本地素材 (`/workspace/in_a/`)**:

  * `sales_q1.csv` 至 `sales_q4.csv`（每份 10 行，含混合币种 `USD`/`EUR`/`GBP`、2 行重复单号与 1 行负向退单，需去重清洗）；

  * `/workspace/in_a/credit_memos/`: 4 张程序生成的正规电子红字冲销发票 PNG（`CM-01` 至 `CM-04`），每张图面包含 **16 位发票校验码**（格式 `FIN-XXXX-XXXX-XXXX`）与精确红字税额调整值（仅存在于光栅图内）；

  * `close_spec_a.txt`: 规定 `Rev_Ledger` 活公式要求、趋势图插入及 4 页 `Finance_Close.pptx` 的字段布局规范。

* **本地服务 `18141` (`FinAudit`)**:

  * 提供 4 笔异常冲销单录入表单（含长串校验码输入框、**失焦自动收起**的税务类别下拉菜单、原生 `<input type="file">` 上传发票 PNG 入口）；后端记录提交明细并做跨角色串台检测。

### 2.3 Actor B 素材与服务（人力薪酬封账）

* **本地素材 (`/workspace/in_b/`)**:

  * `payroll_q1.csv` 至 `payroll_q4.csv`（每份 10 行，含重复打卡记录与不同加班倍率，需去重清洗）；

  * `/workspace/in_b/allowances/`: 4 张程序生成的正规电子特批补贴单 PNG（`ALW-01` 至 `ALW-04`），每张图面包含 **16 位批文校验码**（格式 `HRD-XXXX-XXXX-XXXX`）与精确补贴金额（仅存在于光栅图内）；

  * `close_spec_b.txt`: 规定 `HR_Cost` 活公式要求、超预算行条件高亮规则及 4 页 `HR_Close.pptx` 的字段布局规范。

* **本地服务 `18142` (`HRDesk`)**:

  * 提供 4 笔特批补贴录入表单（含长串批文码输入框、**失焦自动收起**的部门下拉菜单、原生 `<input type="file">` 上传批文 PNG 入口）；后端记录提交明细并做跨角色串台检测。

## 3. Actor 提示词规格

### Actor A 提示词

```
你正在共享的 Ubuntu 桌面环境中执行年度财务封账闭环，另一位代理会并发编辑同一总账文件并使用同一桌面、浏览器与 LibreOffice 进程处理独立的人力封账任务。可自由使用 GUI 或 CLI。

请完成以下 4 阶段财务封账任务：
1. 【清洗与读图】清洗 `/workspace/in_a/sales_q1.csv` 至 `sales_q4.csv`（按单号去重），并查看 `/workspace/in_a/credit_memos/` 下的 4 张红字冲销发票图片，提取每张发票的 16 位校验码与税额调整值。
2. 【共享总账活公式建模】在共享文件 `/workspace/shared/Corp_Annual_2026.xlsx` 的 `Rev_Ledger` 工作表中填入清洗后的季度明细、4 笔红字调整及年度汇总。所有折算本币与汇总单元格必须使用引用 `FX_Tax_Rates` 的真实 Excel 活公式（严禁写死计算结果），不得破坏或覆盖同一工作簿内的 `HR_Cost` 工作表；生成年度营收趋势图保存为 `/workspace/out_a/rev_trend.png`，并将 `Rev_Ledger` 导出为 `/workspace/out_a/Rev_Ledger.pdf`。
3. 【后台冲销录入】在 Chrome 的 FinAudit（http://127.0.0.1:18141）逐一录入全部 4 笔红字冲销单（准确填入 16 位校验码、金额、选择税务类别并上传对应发票 PNG）。
4. 【封账简报与交付】更新桌面已打开的 `/workspace/out_a/Finance_Close.pptx`（填入与总账完全一致的最终汇总数字、插入 `rev_trend.png` 且无遮挡、补齐风控页与备注防溢出），导出 4 页 PDF 至 `/workspace/out_a/Finance_Close.pdf`，并输出 `/workspace/out_a/finance_close.json`。
```

### Actor B 提示词

```
你正在共享的 Ubuntu 桌面环境中执行年度人力封账闭环，另一位代理会并发编辑同一总账文件并使用同一桌面、浏览器与 LibreOffice 进程处理独立的财务封账任务。可自由使用 GUI 或 CLI。

请完成以下 4 阶段人力封账任务：
1. 【清洗与读图】清洗 `/workspace/in_b/payroll_q1.csv` 至 `payroll_q4.csv`（去重并核算加班），并查看 `/workspace/in_b/allowances/` 下的 4 张特批补贴单图片，提取每张批文的 16 位校验码与补贴金额。
2. 【共享总账活公式建模】在共享文件 `/workspace/shared/Corp_Annual_2026.xlsx` 的 `HR_Cost` 工作表中填入季度明细、4 笔特批补贴及年度总成本。所有个税社保与汇总单元格必须使用引用 `FX_Tax_Rates` 的真实 Excel 活公式（严禁写死计算结果），对超预算部门行应用高亮格式，且不得破坏或覆盖同一工作簿内的 `Rev_Ledger` 工作表；生成成本分布图保存为 `/workspace/out_b/hr_cost_chart.png`，并将 `HR_Cost` 导出为 `/workspace/out_b/HR_Cost.pdf`。
3. 【后台特批录入】在 Chrome 的 HRDesk（http://127.0.0.1:18142）逐一录入全部 4 笔特批记录（准确填入 16 位校验码、金额、选择归属部门并上传对应批文 PNG）。
4. 【封账简报与交付】更新桌面已打开的 `/workspace/out_b/HR_Close.pptx`（填入与总账完全一致的最终人力成本数字、插入 `hr_cost_chart.png` 且无遮挡、补齐说明页与备注防溢出），导出 4 页 PDF 至 `/workspace/out_b/HR_Close.pdf`，并输出 `/workspace/out_b/hr_close.json`。
```

## 4. 确定性评分检查点（46 项）

评测脚本先以独立临时 `-env:UserInstallation` 调用 LibreOffice 重算 `/workspace/shared/Corp_Annual_2026.xlsx`，再执行全部 46 项布尔校验；总分 = 通过项数 / 46。

### Actor A（23 项）

* `A01`: `Corp_Annual_2026.xlsx` 完整可解析，且 `Rev_Ledger`、`HR_Cost`、`FX_Tax_Rates` 三表同时存活。

* `A02`: `Rev_Ledger` 关键折算与汇总单元格均为合法公式字符串（以 `=` 开头且引用 `FX_Tax_Rates`），无硬编码。

* `A03`: 独立重算后 `Rev_Ledger` 全表无 `#REF!`、`#VALUE!`、`#NAME?`、`#DIV/0!` 错误。

* `A04`–`A07`: 4 个季度本币净营收重算值均与真值精确匹配（误差 `< 1e-2`）。

* `A08`–`A09`: 4 笔红字调整总额与年度最终净营收重算值均与真值精确匹配。

* `A10`: `/workspace/out_a/Rev_Ledger.pdf` 存在、合法且包含非空表格渲染内容。

* `A11`–`A14`: `FinAudit` 后端 4 条冲销记录的 16 位校验码、金额、税务类别均与真值精确匹配。

* `A15`: `FinAudit` 后端接收的 4 份发票附件 SHA-256 与原图完全一致。

* `A16`: 剪贴板防污染检测通过：`FinAudit`、`Rev_Ledger` 与 JSON 中均不含 `HRD-` 前缀码或 B 部门专有文本。

* `A17`: `/workspace/out_a/Finance_Close.pptx` 存在、可解析且恰好 4 页。

* `A18`: PPTX 中引用的年度汇总数字与 `Rev_Ledger` 重算真值完全一致。

* `A19`: PPTX 嵌入的趋势图 SHA-256 与 `/workspace/out_a/rev_trend.png` 一致且与文本框零重叠。

* `A20`: PPTX 备注与风控说明完整且无底部溢出。

* `A21`: `/workspace/out_a/Finance_Close.pdf` 存在、合法且恰好 4 页，`pdftoppm` 校验无空白页与溢出。

* `A22`: `/workspace/out_a/finance_close.json` 存在、合法且核心数字与总账、PPTX 三方一致。

* `A23`: 共享总账保护核验：`Rev_Ledger` 写入后未对 `FX_Tax_Rates` 造成篡改。

### Actor B（23 项）

* `B01`: `Corp_Annual_2026.xlsx` 中 `HR_Cost` 存活且未被 Actor A 覆写清空。

* `B02`: `HR_Cost` 关键税费与汇总单元格均为合法公式字符串（以 `=` 开头且引用 `FX_Tax_Rates`），无硬编码。

* `B03`: 独立重算后 `HR_Cost` 全表无 `#REF!`、`#VALUE!`、`#NAME?`、`#DIV/0!` 错误。

* `B04`–`B07`: 4 个季度人力成本重算值均与真值精确匹配（误差 `< 1e-2`）。

* `B08`–`B09`: 4 笔特批补贴总额与年度最终总人力成本重算值均与真值精确匹配，且超预算行具备高亮格式。

* `B10`: `/workspace/out_b/HR_Cost.pdf` 存在、合法且包含非空表格渲染内容。

* `B11`–`B14`: `HRDesk` 后端 4 条特批记录的 16 位校验码、金额、归属部门均与真值精确匹配。

* `B15`: `HRDesk` 后端接收的 4 份批文附件 SHA-256 与原图完全一致。

* `B16`: 剪贴板防污染检测通过：`HRDesk`、`HR_Cost` 与 JSON 中均不含 `FIN-` 前缀码或 A 发票专有文本。

* `B17`: `/workspace/out_b/HR_Close.pptx` 存在、可解析且恰好 4 页。

* `B18`: PPTX 中引用的年度人力总成本与 `HR_Cost` 重算真值完全一致。

* `B19`: PPTX 嵌入图表 SHA-256 与 `/workspace/out_b/hr_cost_chart.png` 一致且与文本框零重叠。

* `B20`: PPTX 备注与说明页完整且无底部溢出。

* `B21`: `/workspace/out_b/HR_Close.pdf` 存在、合法且恰好 4 页，`pdftoppm` 校验无空白页与溢出。

* `B22`: `/workspace/out_b/hr_close.json` 存在、合法且核心数字与总账、PPTX 三方一致。

* `B23`: 共享总账保护核验：`HR_Cost` 写入后未对 `FX_Tax_Rates` 造成篡改。

## 5. 防作弊与工程实现约束

1. **同簿失写严检**: 必须同时验证 `Rev_Ledger` 与 `HR_Cost` 存活；任何一方在未合并情况下覆写保存 `Corp_Annual_2026.xlsx` 将直接导致另一方全量得分归零并被记录为 `lost_update_event`。

2. **真实公式强制重算**: 评分阶段必须使用独立配置目录的 LibreOffice 重新求值后读取缓存值，严禁仅信任文件原有缓存数字。

3. **冲突指标埋点**: 额外统计 `.~lock.*` 冲突次数、共享工作簿覆写回滚次数、剪贴板串台命中次数及单进程 `soffice.bin` 焦点翻转次数，保留关键阶段截图供次日验收。