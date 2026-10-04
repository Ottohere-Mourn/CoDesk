# Next Phase Experimental Plan

## 本阶段边界

本轮只完成已有 Naive Shared 数据分析和任务设计，不接入模型、不启动新的 Guest episode、不增加重复数。现有五次结果用于提出机制假设，不能当作一般化结论。

## P0 — 固定失败证据与机制定义

1. 将五次 Naive 的 `report.json`、`events.jsonl`、`model_trace.jsonl`、截图和资源 ledger 路径固定在 `FAILURE_ANALYSIS.md`。
2. 指标按 Actor 目标分开记录：Qwen goal、第二 Actor goal、joint goal；另记焦点、输入误路由、状态完整性、恢复和 step-budget failure。
3. 保留事件派生指标的定义，不把 focus mismatch 等同有害输入；stale observation 在本批标为“未观察到”。

## P1 — 实现两个 V2 task fixture

按 `TASK_DESIGN_V2.md` 实现 `FOCUS-ROUTING-001` 和 `STALE-MERGE-001` 的 fixture/reset/trigger/evaluator。每个 evaluator 只读取 episode 后的隐藏状态；Actor 只能读取任务说明、GUI observation、自己的动作回执。

启动模型前的验收条件：

- Actor A solo 与 Actor B solo 都由真实 Guest GUI/CLI 行为达成各自目标。
- 单机同 Guest 的 deterministic joint episode 可解，且 evaluator 分别证明两方成功。
- 负控能确认旧 revision 被拒绝、cross-app token 被发现，且负控失败本身不会污染下一次 reset。
- 事件日志能重建触发顺序、焦点变化、动作来源、读取 revision、提交 revision 和最终文件摘要。

## P2 — 小样本 scripted 机制校验

先用 scripted actors，仅对两个模板各运行：A solo 1 次、B solo 1 次、sequential joint 1 次、触发式 shared joint 1 次和程序化负控 1 次。总量控制在 10 个短 episode；每次干净 reset。若任何 solo 或 joint feasible 路径失败，先修任务/adapter，不接模型。

校验点：

- FOCUS 模板中 only focus handoff condition 改变；两方各自 token 只能到目标应用。
- STALE 模板的日志严格符合 GUI-read(rev0) → CLI-commit(rev1) → stale conflict → GUI-refresh/rebase → GUI-commit(rev2)；两字段都保留。
- reset 后 Browser、Writer、Guest 文件和 revision 回到声明的初态。

## P3 — 机制级结果审阅

对每个模板先查看轨迹/评分后再决定是否值得做模型 smoke。继续使用固定 OSWorld V2.1 Qwen3VLAgent 与现有 Qwen 权重；先每个条件最多 3 次探索，失败也保留。不得改 evaluator 或任务语义来改善成功率；不得把 3 次结果作显著性结论。

先回答：

1. Qwen solo 是否维持任务可解性？
2. Naive 失败是否伴随目标应用焦点丢失、cross-app 输入或 stale revision 冲突？
3. Focus-aware/refresh-rebase 机制是否让双方最终状态完整？
4. Actor 自身失败与共享机制失败能否从事件时间线和 evaluator 中区分？

## 退出条件

如果重置不干净、solo 目标不独立、共同目标不可解、evaluator 泄露状态给 Actor，或失败归因只能靠主观判读，则暂停模型 episode 并修复 fixture/观测记录。只有两套模板通过 scripted 验收后，才启动小规模固定模型 smoke；当前不需要新模型或更大样本。
