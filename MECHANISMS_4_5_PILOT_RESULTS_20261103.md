# 机制 4、5 三臂试验结果（2026-11-03）

## 结论

本轮各选一个早期机制锚点，使用同一任务/fixture 和 Qwen3-VL-30B-A3B-Instruct，按 MA-ID、MA-SD、MA-SD+Lock 各执行一次有效模型运行。两个机制都达到目标组合：

| 机制 | MA-ID / 独立 | MA-SD / 共享 | MA-SD+Lock / 共享+锁 | 结论 |
|---|---|---|---|---|
| #4 Selection / Active Object（S-01） | PASS | FAIL | FAIL | 达标 |
| #5 Undo/Redo History（U-01） | PASS | FAIL | FAIL | 达标 |

这里的 FAIL 是任务状态/精确 oracle 不满足，不是基础设施无效。六个计入结果的运行均为真实 Qwen GUI 运行，protocol_valid、valid_model_run、reset_success 均为 true。没有把 setup-invalid、protocol-invalid 的尝试算成失败结果。

## 协议和实现

- 环境：HealthCare 上的 OSWorld V2.1 Guest、LibreOffice Calc；使用既有 Qwen endpoint 和 runner。
- Shared 流程：捕获 A 的原生 GUI 操作计划，在 B 完成其操作后，不让 A 重新观察/推理，继续派发 A 已计划的操作；这使共享的活动单元格或 Undo 历史成为被测的共享 GUI 状态。
- MA-SD+Lock 使用 PerActionLock。锁只覆盖单次 GUI act，不覆盖模型观察/思考，也不把更早观察到的选择状态/Undo 历史与后续计划原子绑定。因此这是对现有“每个 GUI 操作加锁”策略的检验，不代表更强的事务锁。
- 计分以最终工作簿的精确目标单元格/值为准；mechanism exposure 和运行有效性另行记录。

## #4 — Selection / Active Object（S-01）

任务核心：A 将值写到 B2，B 将值写到 C3；共享时验证焦点/活动单元格变化会不会使 A 的预先计划输入落到错误单元格。

- MA-ID PASS — s01-ma_id-qwen30b-held-20261103-03：有效运行；A 的 B2=A-7319、B 的 C3=B-2042，达成目标。墙钟 767.428 秒。
- MA-SD FAIL — s01-ma_sd-qwen30b-held-20261103-05：有效运行且 mechanism exposure=true。A 的写入在 B 完成任务之后才发出；B 在 C3 输入并按 Enter 后，Calc 自然把活动单元格移动到了 C4，故 A 的已计划键入落在 C4。最终 B2 仍是 seed、C3=B-2042、C4=A-7319，精确 oracle 失败。墙钟 438.237 秒。
- MA-SD+Lock FAIL — s01-ma_sd_lock-qwen30b-held-20261103-06：同样的有效暴露与最终错位状态，目标失败。墙钟 431.040 秒。锁记录：启用；14 次 GUI act；最大并发 1；累计等待 0.061 ms；累计持锁 40.437 秒。每动作串行没有恢复跨任务切换后的焦点/活动单元格上下文。

## #5 — Undo/Redo History（U-01）

任务核心：A 在 B2 写入临时值并计划撤销；B 在共享 Calc 历史中完成 C3 更新。验证 A 的 Ctrl+Z 是否会撤销共享历史中最近的 B 操作，而不是 A 自己原先看到的操作。

- MA-ID PASS — u05-ma_id-qwen30b-held-20261103-01：有效运行；A 的临时 B2 编辑被撤销恢复 seed，独立文档 B 的 C3=B-2042，目标达成。墙钟 774.122 秒。
- MA-SD FAIL — u05-ma_sd-qwen30b-held-20261103-02：有效运行且 mechanism exposure=true。A 的 A-TEMP 写入 B2 并保存后，B 更新并保存 C3；A 再发出预先计划的 Ctrl+Z，撤销了共享 Undo 栈顶的 B 更新。最终 B2=A-TEMP、C3 仍是 seed，两个目标均不满足。墙钟 452.257 秒。
- MA-SD+Lock FAIL — u05-ma_sd_lock-qwen30b-held-20261103-03：同样的有效暴露及最终状态，目标失败。墙钟 466.172 秒。锁记录：启用；16 次 GUI act；最大并发 1；累计等待 0.049 ms；累计持锁 46.768 秒。每动作锁未隔离共享 Undo 栈，也没有把观察到的历史与后续撤销绑定。

## 时间、无效尝试与资源

计入的六个模型运行墙钟时间合计 **55 分 29 秒**：S-01 合计 27 分 17 秒，U-01 合计 28 分 13 秒；不包含无效运行、设计/工程及本报告整理时间。

以下尝试保留在 runs 中，但不计入三臂结果：

- s01-ma_id-qwen30b-held-20261103-01（271.462 秒）：Calc 已显示正确工作簿，但旧 title-only readiness 检查得到 null，Qwen 未运行，setup-invalid。旧 setup 异常曾遗留一个本 run 创建的 Guest；之后通过校验精确 container ID、owner/run labels 和创建 ledger 后清理了该 Guest。注意：该运行的原始 report 是清理前快照，故其 all_containers_have_destroy_record=false；清理事件追加在 resource-events ledger 中。overlay 和证据均保留。
- s01-ma_id-qwen30b-held-20261103-02（860.948 秒）：初始 prompt 不够明确，尾随输入/目标没有完成，protocol-invalid；不计入，也未据此运行 shared arm。之后收紧为 Ctrl+Home + 方向键导航并重新执行。
- s01-ma_sd-qwen30b-held-20261103-04（497.699 秒）：观察到活动单元格错位，但 runner gate 错误要求 Enter 后仍精确停留在 C3；LibreOffice 的正常行为是移动至 C4，所以被旧 gate 标为 protocol-invalid。没有事后篡改该 report；修正判据为“原计划目标是 B2，B 的操作后活动单元格离开 B2”后，使用新 run 05 重跑并纳入结果。

最终有效运行的 reset 成功；运行后检查没有活跃 Guest 容器。未清理旧 runs/overlays，也没有因得到期望结果而选择性删除尝试。

## 文件与交接状态

- 本机制 runner：scripts/run_calc_mechanism_qwen_v1.py、scripts/run_calc_mechanism_qwen_v1.sh。支持 selection|undo、ma_id|ma_sd|ma_sd_lock，Shared 条件要求同提示词/模型/任务的 MA-ID baseline；代码已 py_compile 并检查 --help。
- 有效运行证据：/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/<run-id>/，每个目录含 report、轨迹和资源记录。
- 本报告为新文件。没有提交或 push；也没有改动/重置此前机制 1–3 的工作区修改。
- 按当前请求只做每机制一组三臂；不追加第二次重复，也不扩成十个案例。
