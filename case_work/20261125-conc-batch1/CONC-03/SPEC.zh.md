# CONC-03: 同名文件选择框与失焦自隐菜单并发冲突

> 语言实现要求：本规格文档采用中文撰写以便审阅；Codex 在生成实际代码时，须将所有输入数据、网页界面文案、报销单文字、幻灯片模板文本及注入给 Actor A / Actor B 的运行时提示词全部转为英文。

## 1. 元信息

* **Case ID**: `CONC-03`
* **复杂度梯度**: `light`（低重复体力、高频弹窗与菜单碰撞）
* **协作模式**: `independent_concurrent`
* **冲突定律**: `LAW_2`, `LAW_3`, `LAW_1`
* **依赖环境**: Google Chrome, LibreOffice Impress, Python 3.10.12, GNOME X11, `pdftoppm`
* **评分模式**: 纯确定性规则校验，共 20 项检查点，无 LLM Judge
* **对称与重叠目标**: `horizon_symmetry_ratio >= 0.85`，预测并发重叠时长 `>= 180s`
* **交付根目录**: `/workspace/out_a/`, `/workspace/out_b/`

## 2. 运行环境与素材初始化

### 2.1 本地服务 A：`http://127.0.0.1:18085`（ProcureHub 报销审批台）

* **鉴权与启动**: 非阻塞后台子进程启动并提供 `GET /health`；Setup 阶段在 Chrome 中预打开该页面，并通过**仅存浏览器内存的 `HttpOnly` Session Cookie** 完成预登录（不落盘、无明文账密、无 Cookie 返回 `401`）。
* **待审单据（3 条）**:
  * `EXP-401`: 申报金额 `$420.00`，规则允许上限 `$500.00`
  * `EXP-402`: 申报金额 `$315.00`，规则允许上限 `$500.00`
  * `EXP-403`: 申报金额 `$185.00`，规则允许上限 `$500.00`
* **交互机关（强制弹窗与自隐菜单）**:
  * 每条单据行右侧有一个 **失焦即自动收起** 的操作下拉菜单（监听 `window.blur` 与 `document.visibilitychange`，窗口失焦立刻关闭菜单）。
  * 菜单内包含 `Upload Receipt`（触发原生 `<input type="file">` 弹出 GTK 系统文件选择框）与 `Submit Decision` 入口；只有先完成该单据的附件上传，才解锁审批提交按钮。
  * 全部 3 条单据提交完成后，解锁 `Export Approval CSV` 按钮，点击生成标准摘要 CSV（或保存至 `/workspace/out_a/approval_summary.csv`）。
* **本地凭证素材（`/workspace/in_a/receipts/`）**:
  * 由 Setup 使用 Python（Pillow/ReportLab）生成 3 张仿真商务电子报销单 PNG（含抬头、单号、明细表、合计金额、审核红章）：
    * `receipt_EXP-401.png`: 图面合计 `$420.00`，盖有清晰红色 `VERIFIED` 印章（应批准 `APPROVED`）
    * `receipt_EXP-402.png`: 图面合计 `$395.00`（与申报金额 `$315.00` 不符），盖有印章（应驳回 `REJECTED`，驳回码 `ERR_AMOUNT_MISMATCH`）
    * `receipt_EXP-403.png`: 图面合计 `$185.00`，盖有清晰红色 `VERIFIED` 印章（应批准 `APPROVED`）
  * 金额不符事实仅存在于光栅 PNG 图像中，不以任何文本形式写入网页或本地文本文件。

### 2.2 本地素材 B 与 Impress 预打开状态

* **本地素材（`/workspace/in_b/`）**:
  * `safety_spec.txt`: 规定 3 页安全海报的精确标题、页脚编号（`SAF-01`、`SAF-02`、`SAF-03`）、每页对应图标文件名及摆放安全区要求。
  * `/workspace/in_b/icons/`: 3 张 `320x320` 高对比度扁平矢量风安全图标 PNG：`icon_helmet.png`、`icon_hazard.png`、`icon_exit.png`。
* **预打开目标文件**:
  * Setup 将 3 页草稿部署至 `/workspace/out_b/Safety_Brief.pptx`（每页含占位标题、正文提示框与底部页脚框），并启动桌面 LibreOffice Impress 预打开该文件。

## 3. Actor 提示词规格

### Actor A 提示词

```text
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与办公软件处理独立任务。可自由使用 GUI 或 CLI。

已打开的 Google Chrome 中已登录 ProcureHub 报销审批台（http://127.0.0.1:18085），当前共有 3 条待审报销单（EXP-401、EXP-402、EXP-403）。对应的凭证图片位于 `/workspace/in_a/receipts/`。

请对每条报销单依次完成以下操作：
1. 查看本地对应的凭证 PNG 图片，核对图面显示的实付总金额是否与页面申报金额一致，以及是否盖有红色 VERIFIED 印章；
2. 在网页上为该单据上传对应的凭证图片文件；
3. 若金额一致且印章完整，选择 `APPROVED` 并提交；若金额不符，选择 `REJECTED` 并填写驳回码 `ERR_AMOUNT_MISMATCH`；若缺章，填写 `ERR_MISSING_STAMP`。

全部 3 条审核完成后，导出审核汇总 CSV 并确保其保存至 `/workspace/out_a/approval_summary.csv`（列头：`claim_id,status,reason_code,uploaded_filename`）。请确认结果准确后再结束任务。
```

### Actor B 提示词

```text
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与办公软件处理独立任务。可自由使用 GUI 或 CLI。

你的目标文件 `/workspace/out_b/Safety_Brief.pptx` 已在桌面 LibreOffice Impress 中打开。请参考 `/workspace/in_b/safety_spec.txt` 与 `/workspace/in_b/icons/` 中的 3 张安全图标，完成 3 页海报编辑：
1. 按规范更新第 1–3 页的主标题与底部页脚编号（SAF-01、SAF-02、SAF-03）；
2. 将 `icon_helmet.png`、`icon_hazard.png`、`icon_exit.png` 分别插入第 1、2、3 页指定的右侧图标区，调整大小与位置，确保图标完整位于页面边界内且不遮挡标题、正文框及页脚框；
3. 保存 `/workspace/out_b/Safety_Brief.pptx`，并导出为 3 页 PDF 至 `/workspace/out_b/Safety_Brief.pdf`。

请核对两份输出文件完整且版面无遮挡后再结束任务。
```

## 4. 确定性评分检查点（20 项）

每项返回布尔值，总分 = 通过项数 / 20。

### Actor A（10 项）

* `A01`: 服务 A 后端记录 `EXP-401` 状态为 `APPROVED`。
* `A02`: 服务 A 后端记录 `EXP-402` 状态为 `REJECTED` 且驳回码精确为 `ERR_AMOUNT_MISMATCH`。
* `A03`: 服务 A 后端记录 `EXP-403` 状态为 `APPROVED`。
* `A04`: 服务 A 后端接收的 `EXP-401` 上传文件 SHA-256 与 `receipt_EXP-401.png` 完全一致。
* `A05`: 服务 A 后端接收的 `EXP-402` 上传文件 SHA-256 与 `receipt_EXP-402.png` 完全一致。
* `A06`: 服务 A 后端接收的 `EXP-403` 上传文件 SHA-256 与 `receipt_EXP-403.png` 完全一致。
* `A07`: 后端交互日志确认全部 3 条单据均经过网页下拉菜单展开与文件上传状态流转。
* `A08`: `/workspace/out_a/approval_summary.csv` 存在、编码正常且列头严格为 `claim_id,status,reason_code,uploaded_filename`。
* `A09`: CSV 包含全部 3 条单据记录且每行状态与驳回码均与真值完全一致。
* `A10`: CSV 中 `uploaded_filename` 字段与实际上传文件名精确一致，无空值或乱码。

### Actor B（10 项）

* `B01`: `/workspace/out_b/Safety_Brief.pptx` 存在、可由 `python-pptx` 正常解析且恰好包含 3 页。
* `B02`: 第 1–3 页主标题均与 `safety_spec.txt` 规定文本精确匹配。
* `B03`: 第 1–3 页页脚均分别包含 `SAF-01`、`SAF-02`、`SAF-03`。
* `B04`: 第 1 页嵌入图片 SHA-256 与 `icon_helmet.png` 一致。
* `B05`: 第 2 页嵌入图片 SHA-256 与 `icon_hazard.png` 一致。
* `B06`: 第 3 页嵌入图片 SHA-256 与 `icon_exit.png` 一致。
* `B07`: 第 1 页图标边界框位于幻灯片内且与标题、正文、页脚文本框零重叠。
* `B08`: 第 2–3 页图标边界框均位于幻灯片内且与各自文本/页脚框零重叠。
* `B09`: `/workspace/out_b/Safety_Brief.pdf` 存在、为合法 PDF 且页数恰好为 3 页。
* `B10`: 使用 `pdftoppm` 渲染 3 页 PDF 为 PNG 后校验：无空白页且 3 页右侧目标图标区均检测到对应图标特征颜色像素，无异常溢出。

## 5. 防作弊与工程实现约束

1. **视觉逼真度规范**: `ProcureHub` 网页采用简洁现代企业后台 CSS 排版；3 张报销单 PNG 须包含真实感商务布局（公司抬头、编号、明细行、总计栏与高对比度红色印章图形），确保视觉检查与论文配图观感自然。
2. **失焦菜单与凭证防透传**: 下拉菜单必须监听真实窗口失焦事件自动收起；凭证金额差异仅渲染于 PNG 像素内，不得在 HTML/JSON 接口泄露正确审批结论。
3. **冲突指标埋点**: 除基础框架指标外，服务 A 额外记录下拉菜单因失焦被迫关闭重开的次数（`popover_dismiss_count`），并保留运行期关键桌面快照与最终渲染图供人工验收。