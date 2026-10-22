# CDD-BV-001：Build-and-Verify — OrderDesk Filter Repair

版本：`0.1.0`。本文件是该 Case 唯一任务卡。它定义一个离线合成订单应用，不连接真实订单、部署环境或外部服务。

## 研究目标

两个 GUI Agent 围绕同一既有 Web 项目完成一个功能修复和回归验证。A 通过 GUI 代码编辑器修改订单过滤实现；B 通过浏览器实测并反馈可复现结果。两者可以同时检查代码、需求、测试计划和应用。自然依赖来自测试反馈帮助定位边界条件，以及修复后的回归验证；不要求固定消息数量、消息轮次、等待时点或同时操作同一窗口。

本 Case 不预设共享桌面一定降低成功率。它区分 GUI 焦点/键盘误路由、共享代码工作区文件冲突、开发服务状态变化和普通代码错误。没有桌面输入轨迹与应用上下文佐证的失败不得归因为共享桌面。

## 任务场景与初始缺陷

Northstar OrderDesk 是一个已有的本地订单队列 Web 应用。页面显示 8 条合成订单，具备搜索字段、状态选择器、Apply 和 Clear 控件。初始实现有两个可复现的过滤缺陷：

1. 输入搜索词时，后端过滤函数提前返回，忽略状态选择器；查询和状态不能按 AND 合并。
2. Apply 只有点击事件处理器；按 Enter 提交表单会触发浏览器原生导航/重载，而不使用相同的过滤流程。

页面已提供可见 label、常规尺寸控件、键盘焦点样式、结果计数 live region 和空结果提示。修复不得故意削弱这些可用性条件。

## 固定公开数据与 Gold 行为

数据文件 `data/orders.json` 是 A/B 均可读的权威公开 fixture。金额用整数美分保存。

| Order | Customer | Region | Status | Total |
|---|---|---|---|---:|
| NW-2401 | Avery Chen | North | Processing | $129.00 |
| NW-2402 | Dana Ruiz | West | Shipped | $87.50 |
| NW-2403 | Dana Ruiz | West | Processing | $43.10 |
| NW-2404 | Mira Patel | South | Delivered | $222.00 |
| NW-2405 | Noah Kim | West | Processing | $61.99 |
| NW-2406 | Dana Ruiz | North | Delivered | $100.00 |
| NW-2407 | Avery Chen | West | Shipped | $147.50 |
| NW-2408 | Mira Patel | West | Processing | $39.00 |

修复后的行为：文本对 order ID、客户名、地区做 `strip + case-insensitive substring`；若 status 不是 All，则结果还必须满足精确状态匹配；两类条件同时存在时取交集。Enter 与 Apply 应执行相同过滤，不发生文档导航。Clear 恢复空搜索、All 状态和全部 8 行；结果计数由 live region 更新，无匹配时显示空状态。

关键 Gold 集合：

| Query | Status | Expected IDs |
|---|---|---|
| `  dAnA ` | Processing | NW-2403 |
| `west` | Processing | NW-2403, NW-2405, NW-2408 |
| `NW-2402` | Processing | 空 |
| 空 | Shipped | NW-2402, NW-2407 |
| `no-such-order` | All | 空 |
| Clear | All | 全部 8 个，按 fixture 顺序 |

隐藏评分清单不出现在 Actor 工作区中。Actor 可用公开数据和需求自行推导结果。

## 角色与完整初始指令

### A — Developer

> You are A, the OrderDesk developer. Repair the existing order-list filter in the supplied project. Search text and selected status must combine conjunctively; search is trimmed and case-insensitive across order ID, customer, and region. Applying with the visible button or Enter must use the same filters without navigating away. Keep the provided data, page structure, and unrelated files intact. You can read the task requirements and test plan, and can inspect the running application. B is responsible for browser validation and may send concrete observations or a regression request. Make a focused change, then tell B what changed when useful. Do not edit the fixture or the evaluator.

A 的职责是检查和修改 `filtering.py` 与 `static/app.js`，必要时根据 B 的可复现反馈继续修复。A 不负责篡改 fixture 或 oracle。

### B — Browser QA Analyst

> You are B, the browser QA analyst. Use the visible OrderDesk browser interface to test the order filters against the requirements and public test plan. You may inspect the same source and data as A. Check status-only, combined search+status, case/whitespace handling, no matches, and keyboard submission with Enter as well as the Apply button. Report reproducible observations and any regression to A through the shared message/attachment interface; after a code change, rerun relevant browser checks and report whether they pass. Do not edit application source or fixture data. Do not infer a pass from a success banner alone: compare the rows shown with the visible records and requirements.

B 的职责是通过浏览器执行 `tests/public_test_plan.json` 所列检查，记录真实可见结果，并提供具体重现步骤或修复后回归结论。B 与 A 都可读取全部需求、代码、fixture 和公开测试计划。

### S — Single-Agent

> You are S, responsible for both development and browser QA. Repair the order filters so text and status combine, search is trimmed/case-insensitive, and both Enter and Apply work without page navigation. Inspect the supplied source/data, implement a focused fix, run the public test plan through the app, and preserve all non-target files. No hidden evaluator state is available.

## 自然协作与应用访问

A 可先检查源代码并实现可疑过滤路径；B 可并行查看应用、fixture 与需求并运行浏览器检查；B 发现组合过滤、键盘提交或空结果问题时可发送具体反馈；A 可根据反馈调整并提示 B 回归。双方可以自由决定何时通信、何时继续各自工作。消息不是业务成功的代理指标，Oracle 单独报告消息方向、应用测试行为和最终代码结果。

A 在代码编辑器中编辑 `filtering.py`/`static/app.js`，B 在浏览器中测试同一个 OrderDesk 服务。二者通常使用不同顶层应用窗口。A/B 浏览器登录身份独立，但连至同一 episode 服务。应用的静态订单事实和源工作区在所有条件下相同。

## 条件协议

| 条件 | 桌面数 | Workspace / service / fixture | 差异 |
|---|---:|---|---|
| `single_agent` | 1 | 一个 episode 项目目录、一个服务、同一 fixture | S 独立完成实现与验证；预算为 A+B 预算之和 |
| `collaborative_isolated` | 2 | 两桌面连接同一个项目工作区、同一服务与 fixture | A/B 桌面控制面独立 |
| `collaborative_shared` | 1 | 同一项目工作区、服务与 fixture | A/B 共用实时桌面焦点、键鼠路由和窗口层级 |

每个条件从相同模板及 `workspace` 初始哈希启动；每个 episode 使用独立 run ID，但服务代码/配置、数据 schema、通信 API、角色、任务、评分和每 Actor 预算相同。A 的代码变更由同一服务热加载，故 B 可在所有条件下测试同一份当前代码。MA-ID 和 MA-SD 不使用不同 backend。未来 Guest adapter 必须使两条件连到同一逻辑 workspace 和服务语义；本轮未实现或验证 Guest 挂载。

条件计划中的探索预算为每个协作角色 160 GUI steps / 10,000 model tokens，Single-Agent 为 320 / 20,000。该预算只是配置占位，尚未模型校准；正式模型 Pilot 前需要 Solo 验证可解性并固定预算。

## 干扰归因边界

- **共享桌面输入路由**：只有外部动作轨迹能证明 B 切换到浏览器后，A 的键盘输入落入浏览器或反之，才计为可归因的焦点/输入干扰。窗口采样非原子，单次切换不够。
- **共享代码文件冲突**：工作区哈希变化、覆盖/并发编辑属于源文件协作问题；两条件都共享相同工作区，因此不单独算桌面控制效应。
- **开发服务变化**：热加载、重启、请求读取了新 source hash 属应用服务状态变化；需记录时间和 revision。两条件保持同一服务实现。
- **普通代码错误**：错误 predicate、语法错误、漏掉 Enter 处理、错误空状态均为实现/任务失败，不归因为共享桌面。
- **模型/Agent 协作**：没有交接或误解需求按协作过程记录。通信消息、Review 数量或窗口切换本身不证明干扰。

## 自动化 Oracle 与负控

Oracle 检查：

1. 项目 fixture 与隐藏初始 manifest 完全一致。
2. 当前 `filter_orders` 对隐藏查询集返回精确、有序 ID 集合，且无重复/外来 ID。
3. Node fake-DOM contract 验证 Enter 与 Apply 共用表单 submit handler、阻止原生导航、更新结果计数并发出测试事件。该项不是浏览器或 Guest 证据。
4. 工作区保护文件（README、需求、订单 fixture、HTML、CSS、公开测试计划）哈希保持不变。
5. QA 角色（协作条件 B，Single 条件 S）在最终 `filtering.py` revision 下完成状态单筛选、组合过滤、错误状态排除、无匹配和 clear 的浏览器/API 记录；client 显示 ID 必须与 server 重新计算一致。
6. 独立报告消息/附件、测试者、修复 revision、应用 route/context 和服务端日志。消息为空不抹掉业务成绩，但不声称发生实质反馈。

负控包含初始 buggy 实现、忽略状态的 query-only、错误 OR 逻辑、fixture 篡改、浏览器 client/server 结果不一致、缺 Enter 或原生导航、B 未在最终代码 revision 回归等，均须失败。

应用事件是服务端 telemetry，不单独证明物理 GUI 操作；真实 Guest 实验需和 OSWorld action trace、截图及窗口采样关联。若证据时钟/事件并非原子，明确标成相关性证据。

## 实现边界及验证状态

入口和实现位于 `oscombo/collab/build_and_verify/`，离线测试为 `tests/test_build_and_verify.py`。本轮实现不修改其他 Case 或 OSWorld Combo。

- 确定性网页项目、订单 fixture、缺陷、需求与公测计划：离线实现。
- 正/负 Oracle、HTTP app、角色登录、消息/附件、condition config、provenance/reset：离线实现与测试。
- Node fake-DOM contract、Python API/HTTP 回归：离线模拟测试，不等同真实浏览器。
- OSWorld Guest、真实 GUI、Solo Agent、MA-ID、MA-SD：**尚未验证**。

## 首次模型 Pilot 门槛

先在安全资源窗口完成真实 Guest readiness、单窗 GUI Editor 修改和 Browser GUI smoke；逐步验证 A/B profile、代码热加载、UI Enter 与 button、事件/动作轨迹、Oracle、reset。然后各做一次 Solo 可解性 Pilot；通过后再做 MA-ID/MA-SD，严格维持同工作区/服务/fixture/budget。不得把 scripted/API 测试或共享桌面窗口切换表述为 Agent 干扰证据。
