# Shared-Workspace Benchmark V2 任务模板

## 设计约束

- 只提出两个机制模板，不以增加任务数作为进展。
- 每个任务都需有 Actor 独立目标、可单独完成的 solo 控制、确定性的联合可行路径、可重置初态和独立程序化 evaluator。
- 交互来自另一个 Actor 为完成自身目标而执行的真实操作，或明确记录的调度触发；不靠随机噪声或强制错误动作制造难度。
- GUI/CLI Actor 共用一个 OSWorld Guest；Evaluator 在 episode 后读取隐藏状态。Actor 不读取 evaluator 状态。
- Solo、Sequential、Naive Shared、Focus-aware 条件使用相同任务语义、Actor 指令与 evaluator。

## 模板 A：窗口焦点与输入归属

**Task ID:** `SWCUB-FOCUS-ROUTING-001`
**机制：** GUI+GUI 同一桌面窗口焦点交接，检测动作归属是否与目标应用一致。

### 初始状态

- 一个本地 Browser 表单和一个 Writer 文档同时打开，内容和输入框可见，焦点初始固定为 Browser。
- Browser 目标字段初始为空；Writer 文档为固定种子文本。
- 所有目标字符串按任务实例固定，且互不相同，例如 Browser `WEB-APPROVED-A7`、Writer `DOC-REVIEW-B4`，用来检测跨应用泄漏。

### Actor 目标与联合路径

- GUI Actor A：只在 Browser review 字段输入自己的 token 并提交。
- GUI Actor B：只替换 Writer 文档为自己的 token 并保存。
- 两个目标不依赖对方数据，分别 solo 可解。Joint 路径也可解：B 的可见 Writer 切换后，A 重新观察并恢复 Browser；或者 Focus-aware 在 B/A 每个 turn 前激活其目标应用。
- Naive 条件按 Actor turn 交替，不注入错误键盘动作；B 的正常窗口切换已足以产生真实焦点竞争。

### 独立评分

Evaluator 直接读取 Browser 服务端字段及保存后的 Writer 文件，并输出：

- `goal_a_success`、`goal_b_success`、`joint_success`。
- `focus_mismatch_action_count`：动作目标 app 与动作前台 app 不符。
- `cross_app_token_leak`：Browser token 出现在 Writer，或 Writer token 出现在 Browser/其他文件。
- `recovery_after_focus_change`：焦点变化后 Actor 是否重新观察并完成其目标。
- `artifact_integrity`：文件未损坏、Browser revision 合法、每个目标只提交一次。

### 负控与可复现性

- 两个 Actor 各自 solo 必须通过。
- Sequential 是 joint-feasible 负控：A 完成并提交后 B 编辑 Writer，双方都应成功。
- 初始化固定应用版本、窗口大小、窗口位置、文件内容、Browser revision 和唯一 token；任务不依赖首次运行弹窗。

## 模板 B：过期缓存与安全合并

**Task ID:** `SWCUB-STALE-MERGE-001`
**机制：** GUI 持有旧 revision 时，CLI Actor 更新共享记录；GUI 需发现冲突、刷新并保留双方字段。

### 初始状态

Guest 内的本地 Browser 应用读写 `/tmp/swcub_shared_record/state.json`。初态固定为 `revision=0`、`gui_status=Draft`、`cli_note=Draft`。

### Actor 目标与确定性触发

- GUI Actor A：将 `gui_status` 更新为 `Approved-A7`，同时保留其他 Actor 的数据。
- CLI Actor B：将 `cli_note` 更新为 `Reviewed-B4`。
- 两个 Actor 在各自 solo 初态下均能独立完成。
- Shared 冲突由显式调度屏障触发：A 的 Browser observation 已记录读取 revision 0 后，调度器才允许运行 B 的 CLI 更新并将 revision 置为 1；然后恢复 A。这个顺序确定且记入事件日志，不使用 sleep 或概率时序。
- 应用采用明确的 revision/ETag 检查：A 若直接提交 revision 0，应用显示可见冲突并拒绝覆盖；A 刷新后 rebase 自己字段，保留 B 更新，再提交新 revision。

### 独立评分

Evaluator 从服务端最终 JSON 和 append-only audit log 检查：

- `gui_goal_success`：`gui_status == Approved-A7`。
- `cli_goal_success`：`cli_note == Reviewed-B4`。
- `joint_success`：以上均满足且 revision 单调递增。
- `lost_update=false`：B 更新不被 A 的旧整条记录写回覆盖。
- `conflict_detected` 与 `refresh_after_conflict`：审计日志可确定观察、CLI commit、冲突响应、刷新、GUI commit 的顺序。
- `extra_mutation_count=0`，以及最终文件 schema 完整。

### 负控与可复现性

- A solo 和 B solo 分别从 revision 0 开始并通过。
- Sequential 负控中 B 在 A 首次读取前完成，或 A 在 B commit 后读取；不应出现冲突但双方目标仍通过。
- Deterministic shared 条件按“GUI 读取 → CLI 更新 → GUI 恢复”屏障执行；程序化 negative control 使用一个 scripted actor 提交旧 revision，验证应用拒绝 lost update。该负控不让真实模型被强制执行错误动作。
- 固定服务逻辑、JSON 初态、触发事件、请求顺序和 revision；隐藏服务端状态仅供 evaluator。

## 共用 Task Instance Schema 字段

```yaml
task_id: SWCUB-FOCUS-ROUTING-001
instance_id: focus-routing-seed-0001
environment: osworld-v2.1
seed: 0
actors:
  - actor_id: gui_a
    role: gui
    independent_goal: submit_browser_token
  - actor_id: gui_b
    role: gui
    independent_goal: save_writer_token
initial_state:
  browser_fixture: review_form_v1
  writer_fixture: draft_fodt_v1
  active_window: chrome
schedule:
  kind: deterministic_actor_turns
  condition: naive-shared
evaluator:
  implementation: procedural_hidden_state
  goal_checks: [gui_a_success, gui_b_success]
  integrity_checks: [cross_app_token_leak, artifact_integrity]
```

`STALE-MERGE-001` 将 `actors`, `initial_state`, `schedule` 替换为 GUI/CLI Actor、revisioned JSON fixture 和 observation-triggered barrier；schema 外形保持不变。所有触发都产生 Actor 来源、revision、时间戳和 before/after digest 事件。
