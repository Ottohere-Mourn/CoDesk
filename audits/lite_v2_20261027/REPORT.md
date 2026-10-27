# CoDesk Data-to-Deck Lite v2 实验报告

日期：2026-10-27。分支 `experiment/codesk-lite-v2-20261027`。本轮只改造 Data-to-Deck；原版、v1、其他六题及其运行记录未覆盖。

## v1 轨迹审计与 v2 设计

v1 原脚本 22 次关键 GUI 操作（原版约 30 次）。v1 的两项财务指标跨 Sales/Costs/Definitions/Findings 四张表，B 要做四处 Impress 文本替换并填写最终文件哈希。修补后 Shared 模型运行中，B 的 `Alt+F4` 关闭/干扰 A 的 Calc，出现 `Save Document?`；A 后续把 `51.33%` 输入发到弹窗前台，构成直接的共享焦点证据。但 A 的数值本身也错误，两人没有保存新 revision。Isolated 中 B 读到 A 的初始空白 Findings 并催问，随后在 A 首次发布前结束；A 的最终数值与证据错误，桥传输约 1.9 秒且无错误。详见 [v1 修复报告](../lite_v1_20261027/REPAIR_REPORT.md)。

v2 保留一项真正需要核算的 West Q3 减 Q2 营业利润变动，A 在一张 Calc 表填 B6 数值和 D6 输入单元格依据；B 同时可查看一页草稿，收到 A 保存版本和消息后只改一个结论框。两种条件仍由两个独立模型 Actor 并发运行。Shared 共用桌面且不加输入锁；Isolated 各有桌面，消息和已保存产物通过原有桥共享。B 的 Prompt 没有答案，行为审计要求其采用 A 保存后的交接，而不只看来源字符串。原版/v1 的多表、第二指标、多处文本、哈希页脚及文件导航已去掉。最终脚本路径是 A 7 次、B 6 次，共 13 次 GUI 调用；模型预算 25 次/角色是余量，不是任务目标。

公开任务、角色指令、Fixture、隐藏 Gold 和 Oracle 分别见 [Task Card](../../oscombo/collab/data_to_deck_lite_v2/TASK_CARD_ZH.md)、[设计说明](../../oscombo/collab/data_to_deck_lite_v2/DESIGN.md)、[角色 spec](../../oscombo/collab/data_to_deck_lite_v2/spec.py)、[Fixture](../../oscombo/collab/data_to_deck_lite_v2/fixtures.py)、[Gold](../../oscombo/collab/data_to_deck_lite_v2/private/gold.py)、[Oracle](../../oscombo/collab/data_to_deck_lite_v2/oracle.py)。Gold/Oracle 留在评分端；Actor 的宿主 shell 和内建工具关闭，只能经桌面及协作 MCP 调用。Oracle 从原始行重新计算期望值，核对 A 数值、B3:E4 依据、源数据保护、B 的方向/金额/来源及 B 与 A 实际保存值的一致性。允许等价英文表达。消息与 revision 的真实时序另审计，不由单个引用字符串宣称协作成立。

## 工程控件

离线全仓测试：`186 passed, 1 skipped`。`gpt-6-astra` 最小真实截图加受控工具调用返回 HTTP 200，工具名 `report_visible`，见 `api_compat_probe.json`；此探针不等于端到端可解性。

首次 Shared 真实 scripted 正控 `cdd-lite-v2-scripted-shared-pos-20261027T140300Z` 为 PASS：Calc GUI 公式得出正确带符号变动，Impress GUI 保存结论，独立 Oracle A/B/联合均通过，A/B saved revision 1，两个文件 GUI 关闭重开 SHA 不变，单 Guest reset 通过。该轮使用最初的固定坐标脚本，共 12 次任务 GUI 调用。

首次 Isolated 真实 scripted 正控 `cdd-lite-v2-scripted-isolated-pos-20261027T141620Z` 的 A 通过，A revision 1 约 2 秒传到 B Guest 并核验为只读 `0444`；B 由于新 Guest 的 LibreOffice 提示横幅使画布下移，固定坐标点击误选标题，Oracle 正确拒绝。保存、回收、双方 GUI 重开和双 Guest reset 通过。该轮是 Adapter 无效控件，不计为模型失败。修复改为在 Impress 中按唯一草稿原文查找替换一处结论；模型 Actor 仍可看图直接编辑。

Shared 真实 GUI 负控 `cdd-lite-v2-scripted-shared-neg-20261027T142025Z` 故意在 A 的 Calc B6 保存错误值，B 仍保存正确结论。最终版 Oracle 重评后 A/B/联合均失败，B 的 `matches_saved_analysis_value=false`；两个文件仍可重开、reset 通过。此控制证明数值和跨产物一致性是评分门槛。

修复后的 Shared 正控 `cdd-lite-v2-scripted-shared-pos-v2-20261027T143400Z` 为最终 PASS：13 次任务 GUI 动作，A/B/联合 Oracle 真，双文件 GUI 重开、单 Guest reset 均通过。修复后的 Isolated 正控 `cdd-lite-v2-scripted-isolated-pos-v2-20261027T143730Z` 亦为最终 PASS：A/B/联合 Oracle 真，A/B 各发布 revision 1，双向传输与对方只读 `0444` 已核验，自己与对方文件均经 GUI 打开，双 Guest reset 通过。两组最终评分采用同一版 Oracle。包括 setup、执行与后处理在内的墙钟分别约 845 秒与 1387 秒；Isolated 多一台 Guest，不能把差值解释为桌面隔离的纯执行代价。

## 强模型 Pilot 与正式配对

冻结协议见 [PROTOCOL.md](PROTOCOL.md)。模型只用 `gpt-6-astra`、medium、同角色 Prompt/公开 Fixture/工具/Oracle，完整条件 25 次桌面调用及 900 秒/角色。最小真实截图加工具调用的 API 探针已先通过。

Isolated 小预算 Pilot `cdd-lite-v2-model-pilot-isolated-20261027T150120Z`（15 次桌面调用/角色，600 秒/角色）为最终 PASS：A/B/联合 Oracle 全真，9/11 次桌面调用，Actor 执行约 390/582 秒，活动重叠 390 秒；A/B 总 token 233,449/358,167。A 在 Calc 保存正确值和 `B3:E4` 后发布 revision 1，桥约 1.6 秒传到 B Guest，A 发消息，B 的模型日志确实读到该消息，然后通过 Impress GUI 修改结论并发布 revision 1；严格交接审计为真。GUI 重开与两台 Guest reset 通过。Pilot 的宿主 QEMU 进程采样器没有启动，CPU/RSS 缺测；rootless cgroup CPU 为零不能解释为真实零。

正式 Shared `cdd-lite-v2-model-shared-20261027T153100Z` 已完整运行一次，A/B/联合 Oracle 为通过/失败/失败。A 用 16 次桌面调用，在数次窗口切换后于 Calc B6/D6 填入正确值与依据，保存 revision 1 并发消息。B 在 A 保存前（执行约 390 秒）以“仍在等 A”作为最终回复并退出，只用了 4 次桌面调用（截图、三次等待）；没有 B revision 1。A 后来在约 700 秒完成。严格交接审计为假。两人的 GUI 输入重叠为 0 秒；没有观察到跨 Agent 焦点抢占或误路由。A 的额外窗口定位消耗时间，但 B 过早结束是直接失败环节，不能把此次失败写成焦点干扰。两份最终文件可在同一 Guest 关闭重开，单 Guest reset 通过，无桥错误。

正式 Isolated `cdd-lite-v2-model-isolated-20261027T155400Z` 也只运行一次，A/B/联合 Oracle 为通过/失败/失败。A 使用 8 次桌面调用，在 16:10:03 UTC 保存正确的 `-11` 与 `B3:E4`，revision 1 已在 B Guest 传输并校验；A 于 16:10:45 发出结果消息。B 使用 4 次桌面调用（截图、三次等待），还尝试用错误的 MCP resource 入口找协作消息；正确的 `read_messages` 调用发生在消息发出之前并返回空。B 于 16:10:39 结束，距 A 发消息仅 6 秒，没有后续编辑，也没有 B revision 1。严格交接审计为假。A 的正确产物在 B Guest 以只读方式 GUI 重开成功，B 的原始草稿也可重开；工作区桥无同步错误，两个 Guest reset 成功。B 提前结束及工具入口误用属于 Actor 的协作流程失误；A 在保存后到发消息之间约 42 秒的模型/工具处理延迟也促成了错过交接。它们不属于普通 Calc/Impress 编辑失败，也没有证据指向同步桥故障。

两组正式运行的 A/B 角色指令字节一致；A/B 初始保存 revision 0 的 SHA-256 也分别相同。两组均用同一 `gpt-6-astra`、medium、25 次桌面调用和 900 秒/角色预算、同版 Fixture/Oracle。Shared 使用单 Guest、Isolated 使用双 Guest；没有输入锁。正式运行期间未更改任务或按结果重跑。Actor 宿主 shell 关闭，模型只见公开指令与桌面/协作工具；凭据文件位于仓库外，文本代码与运行日志扫描未发现密钥明文。

| 指标 | Isolated Pilot（小预算） | Shared 正式 | Isolated 正式 |
|---|---:|---:|---:|
| A/B/联合 Oracle | 通过/通过/通过 | 通过/失败/失败 | 通过/失败/失败 |
| 桌面调用 A/B | 9/11 | 16/4 | 8/4 |
| 模型总 token A/B | 233,449/358,167 | 397,469/280,717 | 124,805/112,567 |
| setup 到 Actor 起步 | 712 秒 | 402 秒 | 736 秒 |
| Actor 阶段 | 582 秒 | 700 秒 | 300 秒 |
| Actor 活动重叠 | 390 秒 | 390 秒 | 278 秒 |
| 模型请求重叠 | 192 秒 | 191 秒 | 128 秒 |
| GUI 输入动作重叠 | 0 秒 | 0 秒 | 0 秒 |
| QEMU RSS 同时峰值 | 缺测 | 5.075 GiB | 9.877 GiB |
| QEMU CPU 采样增量 | 缺测 | 4241 秒 | 6315 秒 |
| 总墙钟（含 setup/后处理） | 1714 秒 | 1361 秒 | 1462 秒 |

计时和 token 详见各运行目录的 `model_metrics.json`；逐步截图、动作、模型调用、消息、版本事件、最终文件、Oracle、重开和 reset 证据均留在对应 run_id 下。QEMU CPU 是采样区间的进程累计增量，包含 setup/后处理，非纯 Actor 执行成本；Isolated 的双 Guest 峰值和总 CPU 更高，不能把墙钟差值直接归因于桌面隔离。Pilot 未启动 QEMU 采样器，表中缺测是真正缺数据，不是零用量。

直接复核入口：Shared 的 [运行结果](../../runs/cdd-lite-v2-model-shared-20261027T153100Z/result.json)、[最终 Calc](../../runs/cdd-lite-v2-model-shared-20261027T153100Z/artifacts/A/verified_analysis.ods)、[最终 Impress](../../runs/cdd-lite-v2-model-shared-20261027T153100Z/artifacts/B/final_management_brief.odp)、[A 桌面动作](../../runs/cdd-lite-v2-model-shared-20261027T153100Z/actor_runs/A/A/actions.jsonl)；Isolated 的 [运行结果](../../runs/cdd-lite-v2-model-isolated-20261027T155400Z/result.json)、[最终 Calc](../../runs/cdd-lite-v2-model-isolated-20261027T155400Z/artifacts/A/verified_analysis.ods)、[最终 Impress](../../runs/cdd-lite-v2-model-isolated-20261027T155400Z/artifacts/B/final_management_brief.odp)、[交接审计](../../runs/cdd-lite-v2-model-isolated-20261027T155400Z/handoff_audit.json)；Pilot 的 [运行结果](../../runs/cdd-lite-v2-model-pilot-isolated-20261027T150120Z/result.json) 与 [交接审计](../../runs/cdd-lite-v2-model-pilot-isolated-20261027T150120Z/handoff_audit.json)。各 Actor 的 `shots/` 按桌面动作编号存放真实截图。`runs/` 由实验机保留并被 Git 忽略，因此仓库提交只包含代码和报告，复核原始证据需保留本机工作区。

## 结论与适用边界

v2 已把脚本任务路径从 v1 的 22 次压到 13 次 GUI 调用（约减少 41%）；真实 GUI 正控、负控、文件传输、重开与 reset 均有独立证据。Isolated Pilot 的 A/B/联合通过说明当前版本具有真实模型可解性。正式配对却是双方联合失败，根因均是 B 在 A 交接前结束；Isolated 仅差约 6 秒，因此仍未达到“Isolated 较高完成可能”的实证标准。由于 B 在两组正式运行都没有 GUI 输入，v2 本次没有观察到共享焦点干扰，不能用 v1 的旧证据替代本次机制证据，也不能从一组配对推断拓扑导致成功率差异。

Lite 的一表一结论、保存版本交接、真实 GUI 正负控、行为时序审计适合作为其余六题将来精简时的**设计模板**；v2 当前不宜作为能够区分 Shared 与 Isolated 的成熟评分案例。后续若改善“等待交接”的角色流程，应新建 v2.1、对两种条件同时采用相同改动，重做正负控和预注册配对，而不能用此次两组分数定向修改 v2。本轮依约停止，不改其他六题，不运行原版或 v1 的模型实验。
