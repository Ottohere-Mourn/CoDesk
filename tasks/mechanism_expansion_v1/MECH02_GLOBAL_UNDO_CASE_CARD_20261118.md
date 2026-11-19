# MECH-02 UNDO-HANDOFF：跨 Agent Calc 全局撤销历史

## 当前判定（2026-11-18）

**一轮 GPT-6-Sol 模型三臂试验达到了数值结果组合 MA-ID PASS / Shared FAIL / Shared+Lock FAIL，且锁臂轨迹对共享撤销栈有直接提示；但两种共享臂均触及 18 次 GUI 调用上限，且没有记录应用层“本次 Undo 实际撤销了哪条编辑”的 undo-target ID。** 因此将其标记为“有效的单次目标 tuple、机制证据较强但仍带预算/归因限制”，不宣称为重复确认或无歧义机制证明。

## Case 定义

- **工作流**：A 在 Calc 的 QC Sample Log 中标注 S-4108 的 Review note 为 `Verified`，按 QC Queue 升序排序，再 Ctrl+Z 一次撤销排序并保存。B 在 S-4112 输入 Observed count `427` 和 Verified by `JL` 并保存。
- **共享状态**：同一个 ODS、Calc 窗口、表格、选区以及跨文档 Undo 历史。
- **机制假设**：一个 Actor 的合法 Ctrl+Z 可能回退另一个 Actor 刚提交的单元格编辑；逐次动作锁只串行化 GUI 调用，不会把“编辑—排序—撤销—保存”变成一个原子事务，也不会限制 Undo 的全局语义。
- **Oracle**：ODS 可读；样本 ID 恰好出现一次；A 的排序后恢复原顺序且 A note 正确；B 两个字段均正确；非目标值不变。
- **版本/模型**：任务实现 `TASK_VERSION=0.1.1`；scripted control 0.1.2；Codex CLI 0.155.0、GPT-6-Sol、GUI-only Codex Harness。每角色/臂最多 18 次 GUI MCP 调用，Actor timeout 900s；Shared+Lock 开启 action lock。
- **Fixture**：`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets/mechanism_expansion_v1/mech02/qc-sample-log.ods`，SHA-256 `79b163bf1df24074febed6816bc5b2151ddc517ee2fe15ee7eebc62dc544b4c0`。本次运行快照里的 `fixture-manifest.json` 曾标 `task_version=0.1.0`（构建器元数据落后于代码）；其 ODS SHA 与实际运行 fixture 一致。试验后已将生成器与当前 RAID manifest 的版本标记同步为 0.1.1，旧运行快照不回写。

## 真实 Guest controls

报告：`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech02-guest-control-20261118T090347Z-461366/report.json`。

- 顺序正控：A/B 均 PASS；A 确实先改变行序再撤销，恢复后 B 完成录入。
- 固定交错负控：B 输入 427/JL 后，A 执行一次本来合法的 Ctrl+Z；终态保留 427、移除 JL，A 的排序仍未撤销，Oracle 两方均 FAIL。
- 该控件证明 fixture/oracle 和“全局 undo stack 可撤回对方一格”机制链可复现；属于刻意交错的机制 control，不等于模型自然并发结果。

## GPT-6-Sol 三臂模型试验

完整产物：`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech02-sol-triplet-20261118T124447Z-565007/`。

| Arm | Oracle | Agent 完成状态 / GUI 调用 | 说明 |
|---|---|---|---|
| MA-ID | A=1、B=1 | A done 15/18；B done 6/18 | 有效独立正控；A/B 都终态完成，无运行错误。 |
| Shared | A=0、B=0 | A/B 均 max_steps 18/18 | 两人均有 `turn.completed` 和终答，无 API/Guest error；共同耗尽相同调用预算。 |
| Shared+Lock | A=0、B=0 | A/B 均 max_steps 18/18 | `action_lock=true`；两人均有终态响应，无 API/Guest error；不是基础设施无效。 |

### 机制轨迹与限制

- **Shared**：统一事件流显示双方频繁交错点选、输入和键盘操作。B 在第 18 次调用意外发出 `Ctrl+Z`；A 到第 18 次仍以 `Escape/Delete/Ctrl+S` 收尾，没有观察到它完成任务要求的“排序后撤销”。终态行序恢复、A 的 `Verified` 缺失、B 的 427/JL 均缺失。该 Shared FAIL 真实，但单看此臂更像同窗操作冲突与任务未完成，不能单独断言为特定 undo 栈因果。
- **Shared+Lock**：A 的第 18 次调用是 `Ctrl+Z` 后保存；B 在 A 之后约 2.3 秒又发出 `Ctrl+Z`，随后又连续两次 `Ctrl+Z`。最终 Oracle 显示行序已恢复、A 的 `Verified` 丢失；B 的 427 已写入但 JL 缺失。跨 Actor 的 Undo 调用发生在逐动作锁之下，显示该锁没有隔离 undo 历史/多动作事务；终态与对方有效编辑被撤销的假设相符，但日志未捕获 Calc 内部的 undo-target identity，故因果归因仍应表述为“强支持、未完全闭环”。
- 两个共享臂都用满 18 次调用，因此 FAIL 同时反映干扰造成的额外恢复成本与固定预算上限。不得删掉失败结果，也不得把预算耗尽单独等同于某个 Undo 操作已造成特定字段回滚。

### 成本与锁遥测

- 三臂合计约 **32.9 分钟**（MA-ID 755.2s，Shared 557.1s，Shared+Lock 661.8s）。
- 共 93 次 GUI MCP 调用；约 1,478,409 input tokens、9,702 output tokens（Codex usage 统计）。
- Shared+Lock 有 35 次带锁 GUI 输入/动作调用；`action_lock` 事件记录的累计等待约 6.278s、最大 1.755s；累计持锁约 84.98s、最长 4.525s。两张截图不经输入动作锁。
- 运行 overlays/结果位于 RAID；Codex runtime 在 `/run/user/1002/codesk-mech02-sol-pilot-20261118` tmpfs。运行归属 Guest 已销毁，唯一保留的容器是外部 `sharp_bhabha`；没有清理旧 artifacts。

## 复现入口与现存限制

- Parser/Oracle tests：`tests/test_mech02.py`；MECH-02/03/共享测试集合本次 16/16 通过。
- Guest controls：`scripts/run_mech02_controls.py`。
- 模型三臂：`scripts/run_mech02_sol_triplet_secure.sh`。需交互式输入 GPT-6-Sol key；脚本预检 endpoint、磁盘并把每臂 overlay/results 放 RAID，Codex runtime 可通过 `MECH02_CODEX_RUNTIME_ROOT` 指到 tmpfs。
- 历史无效/不完整模型组仍保留在同一 `runs/model-pilot/`；不要覆盖：`mech02-sol-triplet-20261118T090833Z-463385/`（Codex runtime 权限错误）与 `mech02-sol-triplet-20261118T091247Z-466050/`（timeout/SSE 问题）。新运行组不替代或抹除旧结果。
- 本 case 目前是**单次有效三臂 pilot**；没有两次重复，也没有基于多个模型轨迹的稳定率估计。后续如再投入，只做针对性低成本验证：增加应用层 undo 目标观测，或调整任务预算以区分“因果 undo 失败”与“超预算未完成”，不得专门注入某一臂障碍来造 FAIL。
