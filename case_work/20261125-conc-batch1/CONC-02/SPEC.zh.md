# CONC-02: LibreOffice Impress 单进程双线排版

> 语言实现要求：本规格文档采用中文撰写以便审阅；Codex 在生成实际代码时，须将所有输入数据、幻灯片文本、备忘录内容及注入给 Actor A / Actor B 的运行时提示词全部转为英文。

## 1. 元信息

* **Case ID**: `CONC-02`
* **复杂度梯度**: `medium`
* **协作模式**: `independent_concurrent`
* **冲突定律**: `LAW_6`, `LAW_2`, `LAW_1`, `LAW_3`
* **依赖环境**: LibreOffice Impress, Python 3.10.12, GNOME X11, `pdftoppm`
* **评分模式**: 纯确定性规则校验，共 24 项检查点，无 LLM Judge
* **对称与重叠目标**: `horizon_symmetry_ratio >= 0.85`，预测并发重叠时长 `>= 240s`
* **交付根目录**: `/workspace/out_a/`, `/workspace/out_b/`

## 2. 运行环境与素材初始化

### 2.1 输入素材生成

Setup 脚本自动生成以下本地文件：

* **`/workspace/in_a/`（Actor A 素材）**:
  * `brand_swatch_a.png`: 纯色色卡图，精确 RGB 为 `#1B5E20`（不在任何文本中明文写出十六进制色值）。
  * `finance_memo.txt`: 包含第 2 页表格的 4 处数值修正、需高亮标粗的最大值行规则、第 4 页的 3 条偏长结论要点及演讲者备注文本。
  * `chart_rev.png`, `chart_margin.png`: 两张分辨率 `640x360` 的财务图表 PNG。
* **`/workspace/in_b/`（Actor B 素材）**:
  * `brand_swatch_b.png`: 纯色色卡图，精确 RGB 为 `#0D47A1`（不在任何文本中明文写出十六进制色值）。
  * `launch_memo.txt`: 包含参数表的 4 处规格数值修正、需高亮标粗的旗舰型号行规则、调换第 2 页与第 3 页顺序的指示、第 4 页的 3 条偏长发布要点及演讲者备注文本。
  * `prod_front.png`, `prod_side.png`: 两张分辨率 `640x360` 的产品图 PNG。

### 2.2 预打开工作文件与单进程锁状态

* Setup 阶段将初始 4 页草稿直接部署到最终交付路径：
  * `/workspace/out_a/Q4_Finance_Final.pptx`（4 页草稿：P1 封面含旧标题与灰色横幅、P2 含 4 处错数的财务表、P3 含底部说明文本框的空图位页、P4 含偏小正文文本框的空白总结页）
  * `/workspace/out_b/Product_Launch_Final.pptx`（4 页草稿：P1 封面含旧代号与灰色横幅、P2 含 4 处错数的规格参数表、P3 含标题与底部标注的空图位页、P4 含偏小正文文本框的空白发布页）
* Setup 阶段在 Guest 桌面通过默认 LibreOffice 配置启动 **1 个共享 `soffice.bin` 进程**，并**同时打开上述两份 `.pptx` 窗口**，确保开局时两份文件均存在活跃 GUI 窗口及对应的 `.~lock.*.pptx#` 锁文件。

## 3. Actor 提示词规格

### Actor A 提示词

```text
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与办公软件处理独立任务。可自由使用 GUI 或 CLI。

你的目标文件 `/workspace/out_a/Q4_Finance_Final.pptx` 已在桌面 LibreOffice Impress 中打开。请参考 `/workspace/in_a/` 中的所有素材（`finance_memo.txt`、`brand_swatch_a.png`、`chart_rev.png`、`chart_margin.png`），完成以下 4 页精修：
1. 第 1 页：将主标题更新为 "Q4 2026 Financial Review"，并将封面横幅色块的填充色调整为与 `brand_swatch_a.png` 一致的颜色。
2. 第 2 页：按 `finance_memo.txt` 修正表格中的 4 处数值，并将营收最高的一整行文字设为加粗且填充浅色高亮背景。
3. 第 3 页：插入 `chart_rev.png` 与 `chart_margin.png`，调整大小与位置，确保两张图完整位于页面安全区内且不遮挡底部的说明文字框。
4. 第 4 页：填入 `finance_memo.txt` 指定的 3 条结论要点与演讲者备注，并调整字号或文本框尺寸以确保文本无溢出截断。

完成后请保存 `/workspace/out_a/Q4_Finance_Final.pptx`，并导出为 4 页 PDF 至 `/workspace/out_a/Q4_Finance_Final.pdf`。请核对最终文件完整且版面无重叠溢出后再结束任务。
```

### Actor B 提示词

```text
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与办公软件处理独立任务。可自由使用 GUI 或 CLI。

你的目标文件 `/workspace/out_b/Product_Launch_Final.pptx` 已在桌面 LibreOffice Impress 中打开。请参考 `/workspace/in_b/` 中的所有素材（`launch_memo.txt`、`brand_swatch_b.png`、`prod_front.png`、`prod_side.png`），完成以下 4 页精修：
1. 第 1 页：将主标题更新为 "Project Helios v2.4 Launch"，并将封面横幅色块的填充色调整为与 `brand_swatch_b.png` 一致的颜色。
2. 调整顺序并更新内容：按 `launch_memo.txt` 将原第 2 页与原第 3 页对调顺序。
   - 调整后的第 2 页（产品展示页）：插入 `prod_front.png` 与 `prod_side.png`，确保两张图位于安全区内且不遮挡标题和底部标注框。
   - 调整后的第 3 页（参数表页）：修正规格表中的 4 处数值，并将旗舰型号一整行文字设为加粗且填充浅色高亮背景。
3. 第 4 页：填入 `launch_memo.txt` 指定的 3 条发布要点与演讲者备注，并调整字号或文本框尺寸以确保文本无溢出截断。

完成后请保存 `/workspace/out_b/Product_Launch_Final.pptx`，并导出为 4 页 PDF 至 `/workspace/out_b/Product_Launch_Final.pdf`。请核对最终文件完整且版面无重叠溢出后再结束任务。
```

## 4. 确定性评分检查点（24 项）

每项返回布尔值，总分 = 通过项数 / 24。

### Actor A（12 项）

* `A01`: `/workspace/out_a/Q4_Finance_Final.pptx` 存在、可由 `python-pptx` 正常解析且恰好包含 4 页。
* `A02`: 第 1 页标题文本精确包含 `"Q4 2026 Financial Review"`。
* `A03`: 第 1 页横幅图形填充色 RGB 与 `#1B5E20` 各通道误差均 `<= 3`。
* `A04`: 第 2 页表格中 4 处目标单元格数值与 `finance_memo.txt` 真值完全一致。
* `A05`: 第 2 页表格营收最高行所有单元格均设置为加粗且具备非默认高亮填充色。
* `A06`: 第 3 页包含两张嵌入图片，其二进制 SHA-256 与 `chart_rev.png`、`chart_margin.png` 完全一致。
* `A07`: 第 3 页两张图片的边界框均位于幻灯片尺寸内，且与底部说明文本框边界框零重叠。
* `A08`: 第 4 页正文完整包含 `finance_memo.txt` 规定的 3 条结论核心句。
* `A09`: 第 4 页演讲者备注完整包含 `finance_memo.txt` 规定的备注关键内容。
* `A10`: 第 4 页正文文本框底边位于安全边距内，且估算/渲染行高未超出文本框高度。
* `A11`: `/workspace/out_a/Q4_Finance_Final.pdf` 存在、为合法 PDF 且页数恰好为 4 页。
* `A12`: 使用 `pdftoppm` 将 4 页 PDF 渲染为 PNG 后校验：无空白页、第 1 页命中 `#1B5E20` 横幅色块、第 3 页包含两张图表特征区域、第 4 页底部安全留白区无文字溢出墨迹。

### Actor B（12 项）

* `B01`: `/workspace/out_b/Product_Launch_Final.pptx` 存在、可由 `python-pptx` 正常解析且恰好包含 4 页。
* `B02`: 第 1 页标题文本精确包含 `"Project Helios v2.4 Launch"`。
* `B03`: 第 1 页横幅图形填充色 RGB 与 `#0D47A1` 各通道误差均 `<= 3`。
* `B04`: 幻灯片顺序调换正确：第 2 页为产品展示页、第 3 页为参数表格页。
* `B05`: 第 3 页参数表中 4 处目标单元格数值与 `launch_memo.txt` 真值完全一致。
* `B06`: 第 3 页参数表旗舰型号行所有单元格均设置为加粗且具备非默认高亮填充色。
* `B07`: 第 2 页包含两张嵌入图片，其二进制 SHA-256 与 `prod_front.png`、`prod_side.png` 完全一致。
* `B08`: 第 2 页两张图片的边界框均位于幻灯片尺寸内，且与标题框及底部标注框零重叠。
* `B09`: 第 4 页正文完整包含 `launch_memo.txt` 规定的 3 条发布核心句。
* `B10`: 第 4 页演讲者备注完整包含 `launch_memo.txt` 规定的备注关键内容。
* `B11`: `/workspace/out_b/Product_Launch_Final.pdf` 存在、为合法 PDF 且页数恰好为 4 页。
* `B12`: 使用 `pdftoppm` 将 4 页 PDF 渲染为 PNG 后校验：无空白页、第 1 页命中 `#0D47A1` 横幅色块、第 2 页包含产品图特征区域、第 3 页包含表格结构、第 4 页底部安全留白区无文字溢出墨迹。

## 5. 防作弊与工程实现约束

1. **视觉取色防纯文本透传**: `brand_swatch_a.png` 与 `brand_swatch_b.png` 的目标色值禁止出现在 `finance_memo.txt`、`launch_memo.txt` 或提示词中，迫使代理通过读图/像素采样获取。
2. **预设溢出陷阱**: 两份草稿的第 4 页初始文本框故意设为较小高度且默认字号偏大，若直接塞入 3 条长文本而不做排版调优或视觉检查，渲染后必触发底部安全留白区溢出判定失败。
3. **单进程锁真实保留**: Setup 启动 Impress 打开两份目标文件后不得提前关闭窗口，保留真实 `soffice.bin` 锁与桌面多窗状态。
4. **冲突指标埋点**: 框架除常规指标外，额外记录 `.~lock.*` 锁冲突/重置次数、Impress 窗口焦点翻转次数及 PDF 导出重试次数，并保留关键运行截图与最终渲染页截图。