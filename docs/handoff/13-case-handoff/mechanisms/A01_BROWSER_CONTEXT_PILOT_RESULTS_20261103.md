# A-01 Application Context（浏览器 Tab 上下文）LLM Pilot 结果（2026-11-03）

## 结论

A-01 在修正共同提示（明确要求先点击未聚焦输入框）后，完成一个有效 Qwen3-VL-30B 三臂 triplet：

- **MA-ID / Isolated：PASS**
- **MA-SD / Shared：FAIL**（两个目标值最终都在，但 A 的延迟 Enter 错派到 B 的 Tab，造成 B 的重复提交；非目标完整性 oracle 因此失败）
- **MA-SD+Lock：FAIL**（A 的延迟 Enter 在 B 的 Tab 派发，A 的目标未提交；B 通过）

三个正式 arm 均为 `status=completed`、`valid_model_run=true`、`protocol_valid=true`、`reset_success=true`。这是每臂一次的机制筛查结果，不是重复实验，也不代表对其他任务族的总体发生率。

## 冻结设计 / 臂间一致性

任务在一个 Chromium 顶层窗口中使用两个本地 Tab。Actor A 应在 Tab A 提交 `CTX-A-04100`，Actor B 应在 Tab B 提交 `CTX-B-08200`。协调器先让 A 输入精确值并暂停其已规划的 Enter，再规范化到 Tab B 让 B 完成；随后不替 A 切回 Tab A，恢复 A 的预先规划 Enter。Oracle 检查各自目标、非目标状态、Tab/window 变化及页面提交事件。

- 任务版本：`1.0.0-rc6-llm-pilot`
- schedule：`A-01-rc6b-explicit-click-held-submit-role-tab-normalized`
- 三臂的 manifest SHA、Actor A/B prompt SHA、模型均一致：
  - manifest SHA-256：`282e12d61a6bf48fe602b2311ea849c979787b3a7e7e300a135194d015f83b69`
  - Actor A prompt SHA-256：`0ca0f889bf4ab46911797965f620c2e47095af2d522cf5fefab3745e508af44e`
  - Actor B prompt SHA-256：`56b7d31e3cadd18405be391c5d8e1a66c98d17bf6853e08d70264a7b1c48c692`
  - `Qwen3-VL-30B-A3B-Instruct`；本地 loopback worker，BF16/SDPA、无量化/卸载；温度 0、top-p 0.9、每 actor 最多 20 个决定。
- Shared 与 Shared+Lock 的区别只有每次 GUI act 是否套用一个 per-action lock。lock 范围为单次 GUI act；不覆盖 observation、推理/turn 间隔或协调器 Tab 切换。固定 schedule 是串行的，因此锁等待为零是合理的；这不是并发压力测试。

## 正式结果

| condition / run | 模型结果 | 关键证据 | wall |
|---|---|---|---:|
| MA-ID / `a01-context-ma_id-qwen3vl30b-rolectx-v1-explicit-click-20261103-05` | **PASS**；A=true、B=true；protocol/reset 均有效 | 两个隔离 Guest 分别在其目标 Tab 提交准确值；非目标 Tab 保持 revision 0 | 679.868 s（11.3 min） |
| MA-SD / `a01-context-ma_sd-qwen3vl30b-rolectx-v1-explicit-click-20261103-06` | **FAIL**；condition/joint success=false；protocol/reset 均有效 | A 计划的 `pyautogui.press('enter')` 目标是 Tab A，但 dispatch 前后活跃 Tab 都是同一窗口的 Tab B；B 已先提交 revision 1，A 的错派 Enter 令 B revision=2。服务端记录两次 Tab B `goal_committed`。A 随后恢复到 Tab A 并完成，所以最终 A/B 的目标值都正确；但 actor B 非目标完整性失败且 `cross_tab_contamination=true`，按预先固定 oracle 判 FAIL。 | 392.678 s（6.5 min） |
| MA-SD+Lock / `a01-context-ma_sd_lock-qwen3vl30b-rolectx-v1-explicit-click-20261103-08` | **FAIL**；A=false、B=true；protocol/reset 均有效 | 错派 Enter 的计划目标为 Tab A、实际 dispatch 为同一窗口的 Tab B；最终 Tab A goal 仍空、Tab B 保持 B 的值且 revision=2。wrong-page action 与跨 Tab contamination 均由 evaluator 支持。 | 367.004 s（6.1 min） |

Shared+Lock 的 lock 指标：enabled=true，6 次 GUI act，max concurrent=1，累计等待约 0.025 ms；每次 act 都实际获得/释放锁。但协调器先把当前 Tab 改为 B，随后 A 才持锁发送 Enter，所以锁住输入调用并没有恢复 A 的应用上下文。该结果支持“per-action lock 仍不足以保护浏览器 active-tab 上下文”的机制结论。

> 解释边界：MA-SD 的 FAIL 是一次有证据的**重复提交/非目标完整性失败**，不是 A 最终目标缺失。报告中的 `protocol_gate.wrong_tab_task_effect_observed=false` 只表示 A 自身目标未达成（一个偏窄的旧字段）；同一报告的 `evaluation.wrong_page_action_supported=true`、`cross_tab_contamination=true`、Tab B revision=2 及两条提交事件证明错 Tab 副作用实际发生。不要只看这个 false 字段而把 Shared 重标为 PASS。

## 排除项与更改记录

- `a01-context-ma_id-qwen3vl30b-rolectx-v1-20261103-04` 是一个有效模型 episode，但旧 prompt 错误声称输入框“already-focused”；实际页面未聚焦，A 未输入目标值。它是先前候选的有效任务 FAIL，不是当前 rc6b 三臂之一，不能混入该 triplet。随后在**所有条件统一**把 prompt 改成先点击输入框，再输入并提交；修订后 MA-ID 通过。
- Shared+Lock 的 `...-07` 在调用 LLM 前 setup-invalid：两个 URL 和 route body 可达，但 Guest 中 Chrome 页面白屏、Tab 标题为 Untitled，readiness 15 次未满足。该 attempt 保留但不计作 task FAIL；后续 `...-08` 重新 Guest setup 成功并为有效 FAIL。
- 更早的编译/接线无效运行及 scripted preflight 均不计入这组三臂模型结果；所有日志、截图、report、provenance、overlay 和 append-only resource ledger 均保留，未清理旧 runs。

## 工程验证与路径

- 两个目标测试文件：15 passed（`tests/test_browser_context_workflow_v1.py`、`tests/test_osworld_agent_actor.py`）。
- `py_compile` 与 `git diff --check` 通过。
- 正式 artifacts：`/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/<run_id>/`。
- 三个有效臂合计 wall time 1,439.550 s（约 24.0 min），串行运行。
- 结果文件不改写任何原始 report，也不声称重复复现或压力测试结果。
