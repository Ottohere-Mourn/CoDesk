# Naive Shared 失败机制分析

## 范围与证据

分析对象是 Qwen3VLAgent + ScriptedWriterActor 的五个真实 OSWorld V2.1 Guest episode，任务为 `SWCUB-BROWSER-WRITER-PAIR-001`。每个 episode 的 `report.json`、`events.jsonl`、`model_trace.jsonl` 和截图位于：

`/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/first-model-comparison/active-window-v2/runs/naive-shared/run-01` 至 `run-05`

下文事件序号来自对应 `events.jsonl`；模型步数来自 `model_trace.jsonl`。截图是 `model_trace.jsonl` 中 `screenshot_sha256` 对应的实际输入图像，而不是按文件名猜测的帧。证据等级分为：**观测**（事件、程序评分或截图直接记录）、**归因**（由时间顺序和对照支持，但不是单独的因果证明）。

## 总览

| 机制 / 结果 | 证据 | 频次 |
|---|---|---:|
| 焦点冲突 | Qwen 轮次的目标 Chrome 多次不是活动窗口；Writer 动作也会把桌面切到 Writer | 5/5 episode |
| 输入路由错误 | 文本或键盘动作落在另一 Actor 的应用；由活动窗口事件、动作来源和最终文件状态共同确认 | 4/5 episode；指标计数合计 10 个动作 |
| 过期观察 | 未发现。每步模型 trace 带本轮截图与最新 `observed_revision`；未发现另一个 Actor 在观察之后、动作之前插入操作 | 0/5 已确认 |
| 调度问题 | 逐步 `GUI, Writer` 交替，没有焦点所有权保护；Qwen 需在被抢焦点后自行恢复。Focus-aware 采用同一交替任务，但每个 turn 前激活目标应用 | 机制出现在 5/5；Focus-aware 5/5 联合成功作参照 |
| 联合任务失败 | 程序化 evaluator 检查 Browser 与 Writer 两个目标 | 5/5 |

这些计数是同一事件链的重叠标签，不是互斥样本，也不能相加成独立错误率。Focus 与误输入指标是事件派生的操作性定义。尤其 `focus_mismatch` 包括明确的 Alt+Tab 和目标应用切换动作；不能把它直接当作有害误操作数。

## 逐次时间线与动作分歧

### run-01 — 输入从 Writer 路由到 Chrome，Browser 随后偏离任务

- **开始与焦点切换（观测）**：初始截图 `observation-refresh-02-orchestrator.png` 是 Browser review 页面；Qwen step 1 在 revision 6 点击目标输入框。Writer Actor 随后执行 Alt+Tab 和 Writer dock 点击（事件 18、20）。下一轮 Qwen 的目标窗口检查显示 Chrome 不在前台，而活动窗口是 Writer；Qwen step 2 点击 Chrome dock（事件 26）。
- **误输入与页面转移（观测）**：Writer 下一轮在 Chrome 的 New Tab 前台时执行 `Ctrl+A`、输入 `Approved by GUI actor`、`Ctrl+S`（事件 29–31），三项均记为 mis-input。截图从 `observation-06-gui_actor.png` 的空 Writer 文档转到 `observation-07-gui_actor.png` 的 Chrome 保存网页对话框，之后 `observation-11-gui_actor.png` 显示 Google 搜索结果和 `ERR_CONNECTION_RESET`。Qwen 输入了 Browser 目标文本，但落在搜索/地址上下文，随后反复点击 Reload。
- **终态（观测）**：Qwen 用满 20 步仍未完成 Browser 目标；Writer 文档保持 `Quarterly status report`。双方 evaluator 均失败。
- **归因**：首要机制是焦点冲突及 Writer 键入路由到 Chrome；Google 搜索和 Reload 循环是可见的任务路径偏离。没有证据表明 Qwen 使用了旧截图。

### run-02 — Qwen 在 Writer 窗口重复处理错误目标

- **开始与焦点切换（观测）**：`observation-03-gui_actor.png` 显示 Browser 表单；Qwen step 1 点击 GUI Agent 输入框。Writer 首轮切换后，Qwen 观察到的是 Writer 文档和通知横幅（`observation-06-gui_actor.png`），不是 Browser。
- **重复动作（观测）**：Qwen step 2–20 持续点击同一屏幕坐标 `(1837,223)`，模型文字将其解释为关闭 Writer 通知横幅。截图内容是当前 Writer 窗口；每次预测都有新的 observation revision，部分截图像素相同，因为界面没有改变。Writer 最终文档保持原文，Browser 目标为空。
- **终态（观测）**：20-step 上限导致 Qwen actor 报 `OSWorld agent did not terminate within 20 steps`；双方目标失败。日志记 20 个 focus mismatch、19 个 unintended focus，但没有文本/键盘 mis-input。
- **归因**：这是焦点丢失后的视觉 grounding/恢复失败和预算耗尽，不是 stale screenshot。其模型动作跟随了当前 Writer 画面，却没有回到 Browser 任务，也没有成功恢复焦点。

### run-03 — Qwen 恢复 Browser；Writer 的目标输入去了 Chrome

- **窗口状态改变（观测）**：起始模型截图 `observation-refresh-01-orchestrator.png` 是 Writer 文档，Chrome 目标未在前台。Qwen step 1 点击 Writer 内容区，step 2 点击 Writer 的关闭按钮（事件 14、25）。
- **Actor 输入被改道（观测）**：Writer Actor 的下一轮到来时，焦点检查显示 Chrome 前台、Writer 不可见；Writer 发出 `Ctrl+A`、目标文本和保存快捷键（事件 28–30），三步都被记录为 mis-input。对应的 `observation-06-gui_actor.png` 是 Browser 页面上方的保存对话框。
- **模型恢复与终态（观测）**：Qwen step 3 取消对话框；`observation-07-gui_actor.png` 回到 Browser review 页面，随后 step 4 输入目标、step 5 提交、step 6 报 DONE。Browser evaluator 通过，Writer 文件仍为原文，故联合 evaluator 失败。
- **归因**：焦点冲突和输入路由错误破坏 Writer 目标；Qwen 通过当前截图恢复了自己的 Browser 目标。模型自身 Browser 能力不是本次联合失败的限制因素。

### run-04 — run-03 的同一轨迹复现

- **动作/截图复现（观测）**：事件序列、Qwen 七步、Writer 输入、截图转换与 run-03 几乎相同：起始 `observation-refresh-01-orchestrator.png` 为 Writer；Qwen 关闭 Writer 后出现 Browser 保存对话框（`observation-06-gui_actor.png`）；取消后回到 Browser 页面（`observation-07-gui_actor.png`），再输入并提交。Writer 的三项输入再次出现在 Chrome 活动窗口中。
- **终态（观测）**：Qwen Browser 目标通过，Writer 文件不变，联合失败；记录 5 个 focus mismatch、3 个 mis-input。
- **归因**：与 run-03 一致。两次相同轨迹说明当前初始化和调度可重复地产生此焦点路径，但不能把两次重复当成不同机制。

### run-05 — Writer 前台导致 Qwen 进入 Writer 表单菜单并污染文档

- **焦点转移（观测）**：起始 `observation-refresh-02-orchestrator.png` 是 Browser review 表单，Qwen step 1 点击目标字段。Writer turn 把 Writer 放到前台；Qwen step 2 的输入截图 `observation-06-gui_actor.png` 已是 Writer 文档。
- **动作分歧与视觉状态（观测）**：Qwen step 2–5 选择 Writer 的 `Form` 菜单、`Text Box`，并拖出文本框；step 6 将 `Approved by GUI actor` 键入 Writer。截图 `observation-08-gui_actor.png` 显示 Form 菜单，`observation-11-gui_actor.png` 显示 Writer 文档已含错误串 `Ved by GUI actorQuarterly status report` 和新建文本框。Qwen 后续进入 Form Properties/Macro Selector，并重复点击同一确认坐标到 20-step 上限；Browser 目标仍为空。
- **终态（观测）**：Browser、Writer 两目标均失败，Writer 文件被真实修改并污染；一个文本输入被记录为 mis-input。
- **归因**：主因是焦点冲突将模型带入 Writer 工作流，随后输入路由错误破坏 Writer 文件；缺乏焦点回收/任务识别使错误应用内的动作循环持续。这里不应把 Writer 文件污染误报成外部任务噪声。

## 根因分类

### Focus conflict — 已观察，5/5

`focus_events` 在每个 turn 记录目标应用与活动窗口。run-01、03、04、05 都有 Qwen 轮次开始时 Writer 前台；run-02 则从 Chrome 进入 Writer 后长期留在 Writer。Writer 的可见 GUI 操作会改写同一桌面的活动窗口。Focus-aware 对照在每个 Actor turn 前激活其目标应用，五次调度检查均无焦点交付失败，并取得 5/5 联合成功。该对照支持焦点协调机制的重要性，但当前样本不构成普遍因果结论。

### Stale observation — 未确认

五个 Naive episode 的 Qwen `model_trace.jsonl` 均保存本次截图哈希、`observed_revision` 和动作；`events.jsonl` 中其他 Actor 操作位于不同 turn，未见在 Qwen 同一 observe–predict–act 之间插入。Revision 随已提交 GUI 操作前进。run-02 的重复点击是对仍显示 Writer 横幅的当前画面持续采取无效动作；run-05 是看到 Writer 后确实操作了 Writer。现有证据指向焦点与 grounding/recovery，而不是过期截图或未观察到的并发写入。以后可专门构造 stale-state 任务，不能把本轮结果当成 stale-state 证据。

### Input routing error — 已观察，4/5

- run-01：Writer Actor 的文本和快捷键在 Chrome New Tab 前台执行，随后截图出现 Google 搜索/错误页。
- run-03、run-04：Writer Actor 的文本/保存动作落到 Chrome，Writer 文件没有更新。
- run-05：Qwen 的输入落到 Writer 文档/文本框，最终 Writer 内容被污染，Browser 目标空缺。
- run-02：错误窗口里的点击循环没有文本输入，因此未计为 mis-input；仍属于错误目标应用操作。

### Scheduling issue — 已观察，5/5 的机制条件

Naive 的确定性轮转每次给 Qwen 一步，随后给 Writer 一轮；Writer 首轮会执行真实窗口切换，第二轮不保证重新取得焦点。Orchestrator 没有按 Actor 的目标应用保护或在焦点变化后自动归还桌面。该协议把“每步可以重新观察”与“连续动作间窗口可被另一 Actor 改变”结合起来。Focus-aware 保持交替任务，但在 turn 前显式激活目标应用；这一调度条件在 5/5 episode 成功。这里的调度问题是交互机制，不是随机噪声。

### Task failure — 结果为 5/5 joint failure

Naive 的 Browser 成功为 2/5，Writer 为 0/5，联合成功为 0/5。run-01、02、05 的 Qwen 用满 20 步；run-03、04 的 Qwen 正确完成 Browser 目标并输出 DONE，但 Writer 独立目标未完成。应分别记录模型未完成目标与联合任务失败，不能用一个 joint-failure 标签抹掉个体差异。

## 复核结论

当前最有证据支持的链条是：**确定性 Actor 轮转 → 活动窗口被另一 Actor 改变 → Actor 动作落入错误应用，或 Qwen 在错误窗口里持续 grounding → 个体/联合目标失败**。本轮没有 stale observation 证据。V2 应把焦点协调/输入路由与 stale-state 更新拆成不同任务机制，并用隐藏状态程序化 evaluator 检查最终目标、交叉污染和恢复结果。
