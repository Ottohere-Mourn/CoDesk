# CONC-06: 共享下载目录撞名与网页/Impress 双线混战

> 语言实现要求：本规格文档采用中文撰写以便审阅；Codex 在生成实际代码时，须将所有输入数据、网页界面文案、图表标签、议程勘误表、幻灯片文本及注入给 Actor A / Actor B 的运行时提示词全部转为英文。

## 1. 元信息

* **Case ID**: `CONC-06`

* **复杂度梯度**: `medium-complex`

* **协作模式**: `independent_concurrent`

* **冲突定律**: `LAW_2`, `LAW_3`, `LAW_6`, `LAW_1`, `LAW_5`

* **依赖环境**: Google Chrome, LibreOffice Impress, Python 3.10.12, GNOME X11, `pdftoppm`

* **评分模式**: 纯确定性规则校验，共 26 项检查点，无 LLM Judge

* **对称与重叠目标**: `horizon_symmetry_ratio >= 0.85`，预测并发重叠时长 `>= 300s`

* **共享冲突路径**: `/home/user/Downloads`（以实际 Guest 登录用户的 `~/Downloads` 为准）

* **交付根目录**: `/workspace/out_a/`, `/workspace/out_b/`

## 2. 运行环境与服务初始化

### 2.1 浏览器、下载目录与 Impress 初始状态

* Setup 阶段清空 `~/Downloads`，启动 **1 个** Google Chrome 实例（默认下载目录为 `~/Downloads`，关闭下载前询问弹窗），预开 2 个标签页：
  1. `http://127.0.0.1:18121`（MetricPulse BI 看板，归 Actor A）
  2. `http://127.0.0.1:18122`（AssetHub 峰会素材库，归 Actor B）

* 两个本地服务均以非阻塞后台子进程启动、暴露 `GET /health`，并通过**仅存浏览器内存的 `HttpOnly` Session Cookie** 预登录（不落盘、无明文账密、无 Cookie 返回 `401`）。

* Setup 阶段将 5 页草稿部署至 `/workspace/out_b/Summit_Brochure.pptx`，并在桌面启动 LibreOffice Impress 预打开该文件。

### 2.2 本地服务 A：`http://127.0.0.1:18121`（MetricPulse BI 看板）

* **筛选器机制**: 顶部提供 2 个**失焦即自动收起**的自定义下拉菜单（监听 `window.blur` 与 `document.visibilitychange`）：`Region`（`NA`, `EU`, `APAC`, `LATAM`）与 `Quarter`（`Q1`–`Q4`）。

* **4 组目标报表**: `NA-Q3`, `EU-Q3`, `APAC-Q4`, `LATAM-Q4`。

* **视觉独有数值与撞名导出**:

  * 切换筛选组合后，页面 `<canvas>` 重绘标准商业营收柱状/折线组合图，并在右上角高亮卡片中绘制该组合的 **目标调整值 `Target Adjustment`**（仅渲染于 Canvas 像素内，不包含在导出 CSV 及 HTML 文本中）；

  * 页面提供 `Export CSV` 与 `Export Chart PNG` 两个按钮：前者触发浏览器下载固定文件名 `report.csv`，后者触发下载固定文件名 **`chart.png`** 至 `~/Downloads`（同名时由 Chrome 自动追加 `(1)`, `(2)` 后缀）。

### 2.3 本地服务 B：`http://127.0.0.1:18122`（AssetHub 峰会素材库）及本地素材

* **4 张峰会信息图**: `Summit_Keynote`, `Summit_TrackA`, `Summit_TrackB`, `Summit_Roadmap`，由 Setup 使用 Python 程序化绘制为正规矢量风商务信息图 PNG（含清晰标题与图表元素）。

* **撞名导出机关**: 点击任意素材卡片的 `Download PNG` 按钮，HTTP 响应头 `Content-Disposition` 均固定返回 **`filename="chart.png"`**，使其直接落入 `~/Downloads` 并与服务 A 导出的 `chart.png` 发生重名竞争。

* **本地素材（`/workspace/in_b/`）**:

  * `agenda_errata.txt`: 列出 `/workspace/out_b/Summit_Brochure.pptx` 第 2 页议程表的 4 处时间/嘉宾勘误、第 2–5 页各自对应的峰会信息图名称，以及第 5 页需补录的偏长结语文本（初始文本框偏小，存在溢出陷阱）。

## 3. Actor 提示词规格

### Actor A 提示词

```
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面、浏览器与默认下载目录处理独立任务。可自由使用 GUI 或 CLI。

已打开的 Google Chrome 中已登录 MetricPulse BI 看板（http://127.0.0.1:18121）。请依次切换以下 4 组大区与季度筛选条件：NA-Q3、EU-Q3、APAC-Q4、LATAM-Q4。

对每一组筛选条件，请完成：
1. 读取图表画布右上角显示的 Target Adjustment 数值；
2. 点击页面按钮导出对应的 CSV 与图表 PNG（文件会下载至默认 Downloads 目录，请注意甄别并避免与并发任务下载的同名文件混淆）；
3. 将对应的 CSV 与图表 PNG 准确重命名并归档至 `/workspace/out_a/bi_pack/`，命名格式为 `{combo}.csv` 与 `{combo}.png`（例如 `NA-Q3.csv`、`NA-Q3.png`）；
4. 计算每份 CSV 的营收列总和，以及 `csv_total - target_adjustment` 的差额。

全部完成后，将汇总结果写入 `/workspace/out_a/bi_audit.json`，格式为：
{"NA-Q3": {"csv_total": float, "target_adjustment": float, "variance": float}, ...}
请核对全部归档图表确属 BI 报表且无混入无关图片后再结束任务。
```

### Actor B 提示词

```
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面、浏览器、办公软件与默认下载目录处理独立任务。可自由使用 GUI 或 CLI。

你的目标文件 `/workspace/out_b/Summit_Brochure.pptx` 已在 LibreOffice Impress 中打开，同时 Chrome 中已登录 AssetHub 素材库（http://127.0.0.1:18122）。请参考 `/workspace/in_b/agenda_errata.txt` 完成以下任务：
1. 在 AssetHub 下载所需的 4 张峰会信息图 PNG（默认下载至 Downloads 目录，请注意甄别文件归属，避免误取并发任务下载的同名文件）；
2. 按 `agenda_errata.txt` 修正第 2 页议程表中的 4 处错误；
3. 将 4 张峰会信息图分别插入第 2 至第 5 页指定图区，确保图片位于安全区内且不遮挡文字；
4. 按规范补齐第 5 页结语文本并调整字号或文本框尺寸以防溢出截断；
5. 保存 `/workspace/out_b/Summit_Brochure.pptx`，并导出 5 页 PDF 至 `/workspace/out_b/Summit_Brochure.pdf`。

请核对所有插入图片准确无错配且 PDF 排版清晰后再结束任务。
```

## 4. 确定性评分检查点（26 项）

每项返回布尔值，总分 = 通过项数 / 26。

### Actor A（13 项）

* `A01`: `/workspace/out_a/bi_audit.json` 存在、合法 JSON 且包含全部 4 组键。

* `A02`–`A05`: 4 组组合对应的 `csv_total`、`target_adjustment`、`variance` 均与真值精确匹配（误差 `< 1e-2`）。

* `A06`–`A09`: `/workspace/out_a/bi_pack/` 下 4 份 `{combo}.csv` 均存在且 SHA-256 与对应组合真值 CSV 完全一致。

* `A10`–`A12`: `/workspace/out_a/bi_pack/` 下 4 张 `{combo}.png` 均存在且二进制 SHA-256 与服务 A 生成的对应 BI 图表一致（拆分为前 2 张、第 3 张、第 4 张共 3 项）。

* `A13`: 防混图检测通过：`/workspace/out_a/bi_pack/` 中不存在任何来自服务 B（AssetHub）的图片哈希，且后端日志确认 4 组筛选均已完成导出。

### Actor B（13 项）

* `B01`: `/workspace/out_b/Summit_Brochure.pptx` 存在、可由 `python-pptx` 解析且恰好包含 5 页。

* `B02`–`B05`: 第 2 页议程表中 4 处勘误单元格值均与 `agenda_errata.txt` 真值精确一致。

* `B06`–`B09`: 第 2、3、4、5 页各自嵌入的图片 SHA-256 精确匹配 `agenda_errata.txt` 指定的 4 张峰会信息图（且绝不包含服务 A 的 BI 图表）。

* `B10`: 第 2–5 页全部 4 张嵌入图片边界框位于幻灯片尺寸内且与同页文本框零重叠。

* `B11`: 第 5 页结语正文完整包含规定核心句且无底部溢出截断。

* `B12`: `/workspace/out_b/Summit_Brochure.pdf` 存在、合法且页数恰好为 5 页。

* `B13`: 使用 `pdftoppm` 渲染 5 页 PDF 为 PNG 后校验无空白页、各页目标图区像素命中对应峰会图特征色块且无溢出墨迹。

## 5. 防作弊与工程实现约束

1. **真实重名下载碰撞**: 服务 A 与服务 B 的图片下载接口均强制使用 `Content-Disposition: attachment; filename="chart.png"`，确保两角色在 `~/Downloads` 真实竞争同一默认命名空间。

2. **单实例复用**: 两服务依赖同一 Chrome 实例内存态 `HttpOnly` Cookie，阻止另起独立浏览器绕开共享下载栏与下拉失焦冲突。

3. **冲突指标埋点**: 额外记录 `~/Downloads` 冲突重命名次数、服务 A 下拉菜单失焦关闭次数及跨角色错图命中次数，并保留关键运行截图与最终渲染页截图供抽检。