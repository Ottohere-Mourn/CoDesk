# CDD-BV-001 Build-and-Verify：实现报告

## 状态

首版确定性 Case 已实现并离线验证。**本轮未启动 Guest/QEMU、未启动本机浏览器、未调用模型或 GPU，也未做资源预检。** 因此真实 Guest、Solo Agent、MA-ID 与 MA-SD 当前均为 `NOT_VERIFIED`；这不是资源失败结论。

## 本轮内容

- 唯一任务卡：[`TASK_CARD_ZH.md`](TASK_CARD_ZH.md)
- 确定性项目模板：`template/workspace/`
- 运行入口、条件计划、ownership、provenance、reset：`runner.py`
- 小型本地 Web app 与动态加载编辑后的过滤逻辑：`webapp.py`
- 隐藏代码/浏览器回归 Oracle：`oracle.py`
- 复用 Data-to-Deck 消息/附件 API 的绑定：`integration.py`
- 实例 schema：`instance_schema.json`
- 离线回归：`tests/test_build_and_verify.py`

App 采用 8 条固定合成订单。初始缺陷为：查询文本一旦存在就提前返回、丢掉所选状态；Enter 原生提交没有使用 Apply 的过滤逻辑。修复必须满足查询与状态的交集、trim/case-insensitive 搜索、Enter 与按钮使用同一 submit 路径、Clear/空状态和结果 live region。fixture、需求、HTML、CSS 与公开测试计划均受哈希保护。

## 条件实现边界

三个配置共用同一版本的订单 fixture、源代码模板、消息协议、服务代码和 per-episode 应用服务语义。协作两条件中的 A/B 使用同一可变项目工作区；其内容变化并非共享桌面特有效应。差异只定义为桌面数与输入控制面：Single 1 桌面/合并预算，MA-ID 2 独立桌面，MA-SD 1 共享桌面。MA-ID/MA-SD 的真实 Guest 连接编排尚未完成或验证。

App 服务对每次请求记录 actor、route、查询、状态、可见订单 ID 和当前过滤源哈希。Oracle 另外统计消息方向、附件、最终代码修订下的 B（Single 为 S）浏览器测试覆盖。没有消息不会自动判成业务失败，也不据此声称双向协作。服务端 telemetry 不证明真实 GUI 输入；正式 Guest 需与 OSWorld 截图、动作轨迹、窗口采样关联。窗口采样非原子，不能单独因果归因。

## Oracle 正负控

正控使用正确 conjunctive Python predicate、共享 submit handler，并由 B 在 app HTTP 界面记录状态单筛选、组合筛选、Enter、Apply、无结果和 Clear。Oracle 检查隐藏 acceptance vectors、浏览器/服务端结果一致、keyboard event contract、最终 source revision、fixture 与所有 protected files。

负控包括原始缺陷、错误 OR 逻辑、数据 fixture 篡改、未完成最终 revision 回归。初始缺陷不通过 Python filter 与 keyboard UI contract；错误 OR 和篡改 fixture 不通过最终 Oracle。

浏览器键盘交互由 Node 22 的 fake-DOM event harness 检查，HTTP app 用 cookie session 和实际本地请求做接口回归。这两项都不是 Firefox/Chrome 实际浏览器运行，也不是 OSWorld GUI evidence。

## 测试结果

- Case 离线测试：**6 passed**。
- Case 测试覆盖：确定性初始化与条件拓扑、正确修复正例、初始 bug 负例、错误逻辑与 fixture 篡改负例、角色登录和 app HTTP 测试事件、复用消息/附件 API 双向交接、reset 快照与恢复。
- `python -m py_compile oscombo/collab/build_and_verify/*.py`：通过。
- 全仓回归：**100 passed**；未启动任何 Guest 或模型。

执行命令：

```bash
python -m py_compile oscombo/collab/build_and_verify/*.py
python -m pytest -q tests/test_build_and_verify.py
python -m pytest -q
git diff --check
```

## 与其他 Case 的边界

新增代码完全位于 `oscombo/collab/build_and_verify/` 和 `tests/test_build_and_verify.py`。没有修改 Data-to-Deck、Ticket-to-Resolution、OSWorld Combo 或既有实验产物。Build-and-Verify 是代码/应用功能修复任务；共享文件目录是所有条件的等价固定资源，文件冲突单列为非桌面机制；开发服务热加载和普通错误也不归因于桌面共享。

当前只准备 Case CLI、HTTP 应用、协议 API、条件配置和 Oracle；没有实现启动两个 CodexHarness Actor 的正式 episode coordinator。不得声称已有真实 A/B GUI agent 执行。

候选 `filtering.py` 会由 app server 与 Oracle 执行；本地原型不是恶意代码沙箱。当前仅对受控合成模板和离线测试执行。接入不受信任的模型编辑前，必须保证候选代码只在隔离 Guest/受限执行环境中运行，不能把 host-local server 暴露到共享网络。

## 真实运行状态与准入

| 项目 | 状态 |
|---|---|
| 本地服务/HTTP 接口 | 离线自动测试通过；未启动交互浏览器 |
| Node fake-DOM 键盘 contract | 离线模拟通过；不是实际浏览器 |
| OSWorld Guest readiness / GUI 编辑器 / Browser GUI | **本轮未运行** |
| Single-Agent solvability | **未验证** |
| MA-ID 双桌面同 workspace/service | 配置定义；**未验证** |
| MA-SD 共享桌面 | 配置定义；**未验证** |
| 模型 pilot | **未调用** |

后续准入依赖：在获准资源窗口做单 Guest GUI editor + browser smoke，确认代码热加载、Enter/按钮路径、server events、截图/动作 provenance、Oracle 和 reset；再分别完成 Solo solvability。Solo 通过后才能做同 workspace/service 的 MA-ID 与 MA-SD。模型结果前需明确 GUI actions 与 app telemetry 的关联方法，且不能把 HTTP/API 测试计为 browser GUI 动作。
