# DATA-REL1 实验记录与结果审计（2026-11-06）

## 判定摘要

已完成**一次**同版本三臂 screening triplet，目标组合准确达成：

| 条件 | Agent A | Agent B | aggregate | 有效/目标机制暴露 |
|---|---|---|---|---|
| MA-ID | PASS | PASS | PASS | valid baseline；两份独立初始 Guest clone |
| Shared | A 在 B 开始前 PASS；B 后 A 变 FAIL | PASS | FAIL | valid；A 终态包包含已排除主体且 policy version 过期 |
| Shared+Lock | A 在 B 开始前 PASS；B 后 A 变 FAIL | PASS | FAIL | valid；同一 completion-order，PerActionLock 开启 |

**这是一次性 screening 结果，不是重复验证。** DATA-REL1 是 PAY-1 stale artifact 上位模式的研究数据导出工作流变体，不 claim 新错误机制，也不能外推到真实企业共享后端或任意应用。Shared+Lock 的动作顺序仍然串行，故结果证明 per-action lock 不会自动重新校验既有业务快照；并未测试锁竞争。

## 固定任务/状态语义

- 初始 Guest state：研究数据集 `STUDY-SYN-88` v1，允许合成主体 `SUB-17` 与 `SUB-22`，policy v1；外部发布关闭。
- A 使用 GUI exporter 创建 READY 本地包 `PKG-A-001`，清单含 SUB-17、SUB-22，manifest hash 正确；发 handoff 后结束。
- B 从只读合成 `PA-SYN-017` 验证签署/适用范围，经 GUI 提交方案 version 2，排除 SUB-17；发通知。政策明文规定该修订立即适用于**全部未发布 staging package**。
- MA-ID 各 actor 拥有私有但同源 Guest clone；A 的包与 B 的修订不传播，所以两者的 actor-local 目标分别通过。
- Shared / Shared+Lock 中，两者在一个 Guest workspace 操作；B 后 package 仍 READY/active、policy v1、含 SUB-17，因此 A 的最终 actor-local oracle FAIL，B 的 amendment oracle PASS。撤回隔离并按 v2 重建后，两角色可恢复 PASS。
- 评分 oracle `evaluate_actor(workspace, role)` 不读取实验 arm；episode 仅用 actor→workspace 映射。全部工件合成、loopback-only app、不调用外部发布 endpoint。

## 运行、权限与时间

固定模型为 GPT-6-Sol，经既有 CodexHarness/Codex CLI 0.155.0；三个条件权限均为 GUI MCP、restricted Guest CLI MCP、Collaboration MCP；每 Actor 步数预算 18、输出 token budget 18,000。模型调用使用 `https://docode.cc/v1`；API key 由隐藏交互 prompt 临时输入，不写进脚本/报告。

| 条件 | run ID | 报告相对位置 | wall time | 有效结果 |
|---|---|---|---:|---|
| MA-ID | `data-rel1-sol-ma-id-20261106-200855-214b9e` | `.../data-rel1-model-v1/<run-id>/report.json` | 660.17s（11.0m） | PASS |
| Shared | `data-rel1-sol-ma_sd-20261106-202524-d0ad31` | 同上 | 588.12s（9.8m） | FAIL，机制暴露有效 |
| Shared+Lock | `data-rel1-sol-ma_sd_lock-20261106-203612-361464` | 同上 | 313.14s（5.2m） | FAIL，机制暴露有效 |

形式 triplet 合计 1,561.43s（约 26.0 分钟）；Shared 两臂分别启动全新初始 Guest，三臂串行运行。三个 run 的 Guest/container lifecycle ledger 均确认容器有 destroy record，active container 在结束后为 0。Guest overlay artifacts 保留作证，没有清理历史资源。

Agent 工具调用计数（按 actors/*/actions.jsonl）：
- MA-ID：A 7 次（screenshot 1、Guest CLI 1、click 1、key 3、message 1）；B 8 次（screenshot 1、Guest CLI 4、click 1、read message 1、message 1）。
- Shared：A 10 次（screenshot 1、Guest CLI 1、click 1、key 5、drag 1、message 1）；B 7 次（screenshot 1、Guest CLI 3、click 1、read message 1、message 1）。
- Shared+Lock：A 同 Shared 为 10 次；B 5 次（screenshot 1、Guest CLI 1、click 1、read message 1、message 1）。

实际任务日志确认 Guest CLI 的 `execution_site=osworld_guest`。Agent 能通过普通操作/刷新恢复 stale artifact；+Lock 不封锁这个路径。三臂 outcome 仍一致是因为当前 completion-order 设定在 A 结束后才开始 B，A 不会被再次唤回。工具计数的 key/drag 中含不必要的 GUI 尝试，但没有改变最终判定。

## Scripted gates / Guest smoke

- `tests/test_data_rel1_fixture_v1.py`：15 tests；`tests/test_data_rel1_app_v1.py`：6 tests；共 21/21 pass。
- 有效 no-model Guest smoke：`data-rel1-guest-smoke-20261106-200250-f05c43`，报告位于 `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/data-rel1-guest-smoke-v1/<run-id>/report.json`；可见截图为 `setup/exporter-page.png`。UI header/policy 在 Guest Chrome 中可见；测试 Shared-style stale transition、恢复、reset；container 销毁校验通过。
- 之前一个 Guest smoke 的截图为空白，虽 API contract 通过，但后经人工视觉审计判不可作为 GUI 证据；后续增加等页面 title/截图 header 检查并完成上述有效 smoke。另一个 `ma_sd` 初始化尝试在模型前错误地把 app 的 `events` 运行日志当作业务 state 比较，未调用模型；原因已修正。它们均未纳入正式三臂结果。
- Guest app 仅绑定 Guest loopback，不配置真实数据/发布服务。浏览器后台网络已禁用，**Guest 全部外连流量没有独立抓包审计**，因此不把“没有任何外连包”作为结论。

## 有效性边界 / 下一步

1. Case task contract 明确采用“completion-order 终态仍需有效”的语义。若用户研究要求每名 Agent 退出就独立冻结评分、不得被后续任务改变 verdict，则该 outcome 应改为 system/workflow stale-state metric，而不是 A Agent 个人错误。
2. immediate-for-unreleased-package 是可见、合成、任务文件和 UI 共用的明确政策，不是现实 GDPR/consent 法律主张；若业务领域 review 不接受该政策，no-go。
3. 该 app 和实验是 workspace-local harness；并未测试中央后端广播，不能泛化为所有“共享桌面”产品。
4. 不追求第二次重复；作为一次筛查，当前目标 tuple 成功。后续新候选应改错误签名（优先 CRM-LU1 lost-update 语义 gate），避免继续加一串 stale-export variant。

源文件均在当前 HealthCare 分支工作目录，但本轮没有 commit/push。工作区还有多个并行未跟踪文件，未对其进行归并或清理。
