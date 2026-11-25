# CONC-05: 单窗多标签 MDI 与全局剪贴板串台冲突

> 语言实现要求：本规格文档采用中文撰写以便审阅；Codex 在生成实际代码时，须将所有输入数据、网页界面文案、客户开户单图片文字、SOP 文档内容及注入给 Actor A / Actor B 的运行时提示词全部转为英文。

## 1. 元信息

* **Case ID**: `CONC-05`

* **复杂度梯度**: `light-medium`

* **协作模式**: `independent_concurrent`

* **冲突定律**: `LAW_6`, `LAW_1`, `LAW_3`

* **依赖环境**: Google Chrome, Python 3.10.12, GNOME X11

* **评分模式**: 纯确定性规则校验，共 22 项检查点，无 LLM Judge

* **对称与重叠目标**: `horizon_symmetry_ratio >= 0.85`，预测并发重叠时长 `>= 200s`

* **交付根目录**: `/workspace/out_a/`, `/workspace/out_b/`

## 2. 运行环境与服务初始化

### 2.1 单窗口四标签布局与鉴权

* Setup 阶段在 Guest 桌面启动 **1 个** Google Chrome 窗口，并预开以下 **4 个标签页**（按顺序排列）：
  1. `Tab 1`: `http://127.0.0.1:18101/docs`（MiniCRM 客户开户单图库，归 Actor A）
  2. `Tab 2`: `http://127.0.0.1:18101/form`（MiniCRM 客户建档表单，归 Actor A）
  3. `Tab 3`: `http://127.0.0.1:18102/legacy`（TechWiki 旧版只读 SOP 库，归 Actor B）
  4. `Tab 4`: `http://127.0.0.1:18102/editor`（TechWiki 新版富文本编辑器，归 Actor B）

* 两个本地服务均以非阻塞后台子进程启动、暴露 `GET /health`，并通过**仅存浏览器内存的 `HttpOnly` Session Cookie** 预登录（不落盘、无明文账密、无 Cookie 返回 `401`）。

### 2.2 本地服务 A：`http://127.0.0.1:18101`（MiniCRM）

* **客户开户单素材（`Tab 1` 展示，共 4 份）**:

  * 由 Setup 使用 Python（Pillow）程序化生成 4 张正规商务电子开户表 PNG（清晰表格排版，含公司名称、22 位国际银行账号 IBAN、12 位税号 Tax ID、客户等级 `Gold` / `Silver` / `Platinum`）。

  * 所有客户关键字段仅渲染在光栅 PNG 像素中，严禁以明文形式出现在 HTML DOM、JSON 接口或本地文本文件中。

* **建档表单与留痕（`Tab 2`）**:

  * 表单包含 `company_name`、`iban`、`tax_id`、`tier` 输入框与 `Submit Client` 按钮；

  * 后端记录每条表单提交明细及交互时序，全部 4 条提交完成后支持导出标准 JSON 至 `/workspace/out_a/crm_records.json`。

### 2.3 本地服务 B：`http://127.0.0.1:18102`（TechWiki）

* **旧版只读 SOP（`Tab 3` 展示，共 4 篇）**:

  * 包含 4 篇短小精悍的运维 SOP 文档（`SOP-01` 至 `SOP-04`），每篇均含：标题、1 段含特殊字符与参数标记的 3 行运维命令代码块、2 条核心规则句，以及所属分类标签（`Networking` / `Database` / `Security` / `Storage`）。

  * 每篇代码块内嵌唯一无歧义标识串（如 `CFG-NET-7841` 等），用于精确核对迁移完整性及反向检测剪贴板污染。

* **新版编辑器与失焦菜单（`Tab 4`）**:

  * 包含标题输入、规则与代码块富文本编辑区、以及**分类标签下拉选择器**；

  * 分类标签下拉菜单监听 `window.blur` 与 `document.visibilitychange`，一旦窗口失焦或标签页被切走即立刻自动收起；

  * 每篇发布后写入后端日志，4 篇全部发布后支持导出标准 JSON 至 `/workspace/out_b/wiki_migrated.json`。

## 3. Actor 提示词规格

### Actor A 提示词

```
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与浏览器窗口处理独立任务。可自由使用 GUI 或 CLI。

已打开的 Google Chrome 窗口中，前两个标签页属于你的 MiniCRM 系统：
- 标签页 1（http://127.0.0.1:18101/docs）：展示 4 份客户电子开户单图片；
- 标签页 2（http://127.0.0.1:18101/form）：客户建档录入表单。

请依次查看全部 4 份客户开户单图片，将每家客户的精确信息（公司名称、IBAN 账号、税号 Tax ID、客户等级）逐一录入表单并提交。全部 4 条录入完成后，导出结果并确保保存至 `/workspace/out_a/crm_records.json`。请仔细核对提交内容与导出文件准确无污染后再结束任务。
```

### Actor B 提示词

```
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与浏览器窗口处理独立任务。可自由使用 GUI 或 CLI。

已打开的 Google Chrome 窗口中，后两个标签页属于你的 TechWiki 迁移系统：
- 标签页 3（http://127.0.0.1:18102/legacy）：包含 4 篇待迁移的旧版运维 SOP（SOP-01 至 SOP-04）；
- 标签页 4（http://127.0.0.1:18102/editor）：新版 SOP 编辑器。

请将全部 4 篇 SOP 完整迁移至新版编辑器，每篇均须准确保留标题、完整 3 行命令代码块、全部 2 条核心规则，并在下拉菜单中选中正确的分类标签后点击发布。全部 4 篇发布完成后，导出结果并确保保存至 `/workspace/out_b/wiki_migrated.json`。请仔细核对内容完整无串台后再结束任务。
```

## 4. 确定性评分检查点（22 项）

每项返回布尔值，总分 = 通过项数 / 22。

### Actor A（11 项）

* `A01`: `/workspace/out_a/crm_records.json` 存在、为合法 JSON 且恰好包含 4 条客户记录。

* `A02`–`A05`: 4 条客户记录各自的 `company_name` 与 `tier` 均与真值精确匹配。

* `A06`–`A09`: 4 条客户记录各自的 `iban`（允许去除空格后比对）与 `tax_id` 均与真值精确匹配。

* `A10`: 服务 A 后端日志确认全部 4 条客户记录均经由网页表单实际提交。

* `A11`: 跨角色污染检测通过：`/workspace/out_a/crm_records.json` 及服务 A 后端记录中均未出现服务 B 任意 SOP 代码块或标识串。

### Actor B（11 项）

* `B01`: `/workspace/out_b/wiki_migrated.json` 存在、为合法 JSON 且恰好包含 4 篇 SOP 记录。

* `B02`–`B05`: 4 篇 SOP 各自的 `title` 与 `category` 分类标签均与真值精确匹配。

* `B06`–`B09`: 4 篇 SOP 各自的 3 行 `code_block` 与 2 条核心规则文本均与真值精确匹配。

* `B10`: 服务 B 后端日志确认全部 4 篇 SOP 均经由网页编辑器与分类下拉菜单实际提交发布。

* `B11`: 跨角色污染检测通过：`/workspace/out_b/wiki_migrated.json` 及服务 B 后端记录中均未出现服务 A 任意 IBAN、税号或公司名称。

## 5. 防作弊与工程实现约束

1. **视觉防透传**: 4 张开户单 PNG 采用清晰规范的商务表单排版，所有字段仅存于光栅图像内，禁止在页面文本或接口中暴露明文。

2. **单窗复用约束**: 两个服务依赖同一 Chrome 实例的内存态 `HttpOnly` Cookie，确保双角色无法另起独立无头浏览器绕开标签切换与剪贴板冲突。

3. **冲突指标埋点**: 除基础框架指标外，额外统计 Chrome 标签页切走中断次数、服务 B 下拉菜单失焦关闭次数（`dropdown_dismiss_count`）以及跨角色文本污染命中次数，并保留运行期关键桌面快照供人工抽检。