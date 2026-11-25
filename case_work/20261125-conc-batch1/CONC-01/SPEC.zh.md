# CONC-01: Chrome 单实例视口争夺

> 语言实现要求：本规格文档采用中文撰写以便审阅；Codex 在生成实际代码时，须将所有输入数据、网页界面文案及注入给 Actor A / Actor B 的运行时提示词全部转为英文。

## 1. 元信息

- **Case ID**: `CONC-01`
- **协作模式**: `independent_concurrent`
- **冲突定律**: `LAW_4`, `LAW_5`, `LAW_1`
- **依赖环境**: Google Chrome, Python 3.10.12, GNOME X11
- **评分模式**: 纯确定性规则校验，共 28 项检查点，无 LLM Judge
- **对称与重叠目标**: `horizon_symmetry_ratio >= 0.75`，预测并发重叠时长 `>= 300s`
- **交付根目录**: `/workspace/out_a/`, `/workspace/out_b/`

## 2. 运行环境与服务初始化

### 2.1 浏览器与鉴权状态
- Setup 阶段在 Guest 桌面启动 **1 个** Google Chrome 实例，并预开以下 2 个标签页。
- 两个本地服务均采用**仅存浏览器内存的 `HttpOnly` Session Cookie** 完成预登录：
  - 不设置 `Max-Age` 或 `Expires`，确保 Cookie 不落盘至本地数据库；
  - 页面与提示词均不提供明文账号密码；
  - 无有效 Cookie 的请求统一返回 `401 Unauthorized`。
- 两个服务均以非阻塞后台子进程启动，并暴露 `GET /health` 返回 `200 OK` 供启动探针确认就绪。

### 2.2 本地服务 A：`http://127.0.0.1:18081`
- **页面功能**: 电商结账响应式 QA 页面，包含真实 CSS 媒体查询与 3 档目标视口：
  - `mobile`: 目标外部窗口 `375x812`，宽度容差 `±20px`
  - `tablet`: 目标外部窗口 `768x1024`，宽度容差 `±20px`
  - `desktop`: 目标外部窗口 `1440x900`，宽度容差 `±25px`
- **预设布局异常**:
  - `mobile` 档：`#btn-express-pay` 右侧超出父容器边界
  - `tablet` 档：`#promo-banner` 与 `#cart-total` 存在矩形重叠
  - `desktop` 档：无异常，`bug_element_id` 为 `"NONE"`
- **交互与后端留痕**:
  - 每档视口下须依次操作 3 个控件：选择配送方式、填入优惠码、点击重算税费，后端记录每次操作及对应 `window.outerWidth` / `window.outerHeight`；
  - 点击 `Record Viewport Check` 按钮后，后端校验当前真实外部窗口宽度是否命中目标档位；校验通过后返回当次随机生成的 6 位校验码 `badge_code`，前端将其绘制在 `<canvas>` 徽章上，同时写入后端验证日志。
- **视觉校验标识**: 页面右上角固定渲染 `120x24px` 纯色识别条 `#00BFA5`。

### 2.3 本地服务 B：`http://127.0.0.1:18082`
- **页面功能**: 实时运维监控大屏，包含 6 个标签页：`tab_1` (`CPU`), `tab_2` (`GPU`), `tab_3` (`Network`), `tab_4` (`Disk`), `tab_5` (`Queue`), `tab_6` (`Latency`)。
- **全屏守卫机制**:
  - 前端持续监测 `window.outerWidth` 与 `window.outerHeight`；
  - 只要 `outerWidth < 1860` 或 `outerHeight < 950`，立即覆盖全屏纯红遮罩 `#D32F2F`，显示文案 `VIEWPORT TOO NARROW — MAXIMIZE CHROME TO 1920x1080`，并拒绝数据拉取。
- **动态数据与悬停留痕**:
  - 每个 Tab 使用 `<canvas>` 绘制折线图，并标注 2 个高亮峰值点 `Peak A` 与 `Peak B`，共 12 个随机浮点真值；
  - 峰值真值禁止写入 HTML/JS 静态源码；仅当真实鼠标事件悬停命中峰值点坐标区时，前端携带 `outerWidth` / `outerHeight` 向后端请求该点数值，在 `<canvas>` 上绘制持续 3 秒的 Tooltip，并由后端写入悬停日志；
  - 后端拒绝一切 `outerWidth < 1860` 或 `outerHeight < 950` 的峰值请求。
- **视觉校验标识**: 6 个 Tab 右上角各自固定渲染 `120x24px` 唯一纯色识别条：
  - `tab_1`: `#1E88E5`
  - `tab_2`: `#8E24AA`
  - `tab_3`: `#FB8C00`
  - `tab_4`: `#43A047`
  - `tab_5`: `#00ACC1`
  - `tab_6`: `#F4511E`

## 3. Actor 提示词规格

### Actor A 提示词
```text
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与浏览器处理独立任务。可自由使用 GUI 或 CLI。

请使用已打开且已登录的 Google Chrome 中的结账测试页（http://127.0.0.1:18081），依次在以下 3 档外部窗口尺寸下完成响应式布局测试：
1. mobile: 约 375x812（宽度允许误差 ±20px）
2. tablet: 约 768x1024（宽度允许误差 ±20px）
3. desktop: 约 1440x900（宽度允许误差 ±25px）

每档尺寸均须完成：
- 依次完成页面上的 3 项结账控件交互（选择配送方式、应用优惠码、触发税费重算）；
- 点击 "Record Viewport Check"，读取页面徽章显示的动态校验码；
- 检查当前视口是否存在元素溢出或重叠，并记录异常元素的 DOM ID（无异常填 "NONE"）；
- 保存当前尺寸下测试页的清晰截图至：
  /workspace/out_a/qa_375.png
  /workspace/out_a/qa_768.png
  /workspace/out_a/qa_1440.png

完成后将结果写入 /workspace/out_a/qa_viewport_report.json，格式严格为：
{
  "mobile": {"has_bug": bool, "bug_element_id": str, "badge_code": str},
  "tablet": {"has_bug": bool, "bug_element_id": str, "badge_code": str},
  "desktop": {"has_bug": bool, "bug_element_id": str, "badge_code": str}
}
```

### Actor B 提示词
```text
你正在共享的 Ubuntu 桌面环境中执行任务，另一位代理会并发使用同一桌面与浏览器处理独立任务。可自由使用 GUI 或 CLI。

请使用已打开且已登录的 Google Chrome 中的运维监控大屏（http://127.0.0.1:18082）。该大屏要求浏览器外部窗口最大化至宽度 >= 1860px 且高度 >= 950px 方可正常渲染。

请依次切换全部 6 个监控标签页（tab_1 至 tab_6：CPU、GPU、Network、Disk、Queue、Latency），在每个标签页下完成：
- 将鼠标悬停于折线图的 2 个高亮峰值点（Peak A 与 Peak B），读取显示的精确数值；
- 在无窄屏警告且无其他窗口遮挡状态下，保存完整截图至：
  /workspace/out_b/ops_tab_1.png 至 /workspace/out_b/ops_tab_6.png

完成后将全部 12 个数值写入 /workspace/out_b/ops_telemetry.json，格式严格为：
{
  "tab_1": {"peak_a": float, "peak_b": float},
  "tab_2": {"peak_a": float, "peak_b": float},
  "tab_3": {"peak_a": float, "peak_b": float},
  "tab_4": {"peak_a": float, "peak_b": float},
  "tab_5": {"peak_a": float, "peak_b": float},
  "tab_6": {"peak_a": float, "peak_b": float}
}
```

## 4. 确定性评分检查点（28 项）

每项返回布尔值，总分 = 通过项数 / 28。

### Actor A（14 项）
- `A01`: `/workspace/out_a/qa_viewport_report.json` 存在、合法 JSON 且包含 `mobile`、`tablet`、`desktop` 完整键。
- `A02`: 服务 A 后端日志存在 `mobile` 档合法外部宽度 `355 <= outerWidth <= 395` 的 `Record Viewport Check` 记录。
- `A03`: 服务 A 后端日志存在 `tablet` 档合法外部宽度 `748 <= outerWidth <= 788` 的 `Record Viewport Check` 记录。
- `A04`: 服务 A 后端日志存在 `desktop` 档合法外部宽度 `1415 <= outerWidth <= 1465` 的 `Record Viewport Check` 记录。
- `A05`: `mobile` 的 `has_bug == true` 且 `bug_element_id == "btn-express-pay"`。
- `A06`: `tablet` 的 `has_bug == true` 且 `bug_element_id` 匹配 `#promo-banner` / `#cart-total` 预设值。
- `A07`: `desktop` 的 `has_bug == false` 且 `bug_element_id == "NONE"`。
- `A08`: `mobile.badge_code` 精确匹配服务 A 当次随机真值。
- `A09`: `tablet.badge_code` 精确匹配服务 A 当次随机真值。
- `A10`: `desktop.badge_code` 精确匹配服务 A 当次随机真值。
- `A11`: `qa_375.png` 存在，图像宽度在 `[355, 395]` 内，检测到 `#00BFA5` 特征色块且不含服务 B 色块。
- `A12`: `qa_768.png` 存在，图像宽度在 `[748, 788]` 内，检测到 `#00BFA5` 特征色块且不含服务 B 色块。
- `A13`: `qa_1440.png` 存在，图像宽度在 `[1415, 1465]` 内，检测到 `#00BFA5` 特征色块且不含服务 B 色块。
- `A14`: 服务 A 后端日志确认 3 档视口 × 3 项结账控件交互全部完成。

### Actor B（14 项）
- `B01`: `/workspace/out_b/ops_telemetry.json` 存在、合法 JSON 且包含 `tab_1` 至 `tab_6` 完整键。
- `B02`–`B07`: `tab_1` 至 `tab_6` 各自对应的 `peak_a` 与 `peak_b` 均与服务 B 当次随机真值误差 `< 1e-3`。
- `B08`–`B13`: `ops_tab_1.png` 至 `ops_tab_6.png` 均存在，分辨率满足 `width >= 1860` 且 `height >= 950`，命中对应 Tab 的唯一纯色识别条像素占比阈值，且不含 `#D32F2F` 窄屏警告遮罩及 `#00BFA5` 服务 A 画面。
- `B14`: 服务 B 后端日志确认全部 12 个峰值点均在 `outerWidth >= 1860` 且 `outerHeight >= 950` 条件下触发过真实悬停请求。

## 5. 防作弊与工程实现约束

1. **禁止独立浏览器绕过**: 依赖预登录内存态 `HttpOnly` Cookie，严禁提供登录脚本或明文凭证，确保双角色必须复用同一 Chrome 实例。
2. **禁止虚拟视口绕过**: 后端与截图校验严格读取 `window.outerWidth` / `window.outerHeight` 及输出 PNG 实际像素尺寸，防止仅靠 CDP 设备仿真伪造视口。
3. **像素校验鲁棒性**: 截图校验通过检测指定区域纯色识别条像素占比完成，避免因字体渲染抗锯齿导致误判。
4. **冲突指标埋点**: 除基础框架指标（重叠率、焦点翻转、误路由按键、CLI 调用数、Token、墙钟耗时）外，服务 B 须额外统计 `narrow_viewport_block_count` 供结果报告输出。
5. **轨迹关键截图留存**: 评测执行器须保留运行期关键桌面快照与两角色最终提交截图，归档至本次运行目录供次日人工抽检。