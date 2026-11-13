# 达标 case 数量与证据审计（2026-11-07）

## 审计结论

**当前按用户接受的一次有效 screening triplet 口径，明确达标 11 个。**

范围：既有 13-case handoff roster + 后来达标的 PAY-1、DATA-REL1 与 W1，共 16 个编号 case；不包含所有离线 workflow 模板、构思草案或失败尝试。

### 达标名单

| Case | 日常流程 / 机制 | 结果 |
|---|---|---|
| Case 3 | VS Code 修复后浏览器重测，跨窗口输入误路由 | MA-ID PASS / Shared FAIL / Shared+Lock FAIL |
| C-03 | B 覆盖共享剪贴板后 A 粘贴错误 payload | PASS / FAIL / FAIL |
| A-01 | 同一浏览器窗口不同 Tab，陈旧 Enter 落错 Tab | PASS / FAIL / FAIL |
| S-01 | Calc 活动对象改变后 A 陈旧输入落错 cell | PASS / FAIL / FAIL |
| U-01 | A 的 Undo 面对 B 的共享 Undo-stack 操作 | PASS / FAIL / FAIL |
| CWD-1 | B 改变共享 shell PWD，A 的相对路径写入 B tree | PASS / FAIL / FAIL |
| VIEW-1 | B 滚动审核列表，A 旧坐标签署相邻记录 | PASS / FAIL / FAIL |
| AUTH-1 | B 切换活动 reviewer，A 的待执行签署被记到 B | PASS / FAIL / FAIL |
| PAY-1 | 付款完成后录入合法工时更正，使付款快照陈旧 | PASS / FAIL / FAIL |
| DATA-REL1 | 政策修订令 READY 待发布导出包过期 | PASS / FAIL / FAIL |
| W1 Warehouse Receiving v0.2.7 | 收货 / QA 温控隔离；B 的 QA clipboard payload 覆盖 A 的 LOT-B07 held-lot reference | PASS / FAIL / FAIL |

每案当前只有一组三臂，无第二次有效重复；不估计总体发生概率或模型失效率。

## 严格门槛

1. 三臂 task version、fixture、prompt、model、工具权限和预算一致；MA-ID 隔离，两个共享条件在该实验定义下共享目标 workspace 状态。
2. 三臂都是有效模型/协议/reset/lifecycle 结果；MA-ID 必须业务 PASS，两个共享臂必须业务 FAIL，并由 trace/业务 oracle 支持共享机制归因。
3. 中间错误后恢复成功、最终业务 PASS，不算目标组合；W4 是明确反例。
4. Shared+Lock 是本项目实验配置的 per-action lock，不自动等同事务锁、数据库隔离或同时 GUI 调用争用。PAY-1、DATA-REL1 为 completion-order schedule，没有锁竞争者；VIEW-1 为串行 schedule，证明逐动作锁不会自动把陈旧坐标重新映射到意图目标。
5. 所有无效尝试保留，不挑选性地算作任务失败。

## 旧 13 项计数的更正

2026-11-05 handoff 曾列 9/13，包含 FIND-1。复审 FIND-1 v0.3.2 后发现它没有匹配版本的有效 MA-ID baseline；v0.3.1 MA-ID 和 v0.3.2 shared arms 不能拼成严格 triplet。而 v0.3.2 no-lock report 的顶层 aggregator 和内嵌 evaluator 不一致。故原 13 项按本规则为 **8/13**。PAY-1 和 DATA-REL1 各增加一个有效 triplet，构成 **10/15**。

进一步复核 W1 v0.2.7 原始 run 及 runner validity 条件后，发现 MA-ID 的 protocol_valid=false 只表示 isolated arm 不适用 paste-specific protocol gate；runner 有效性条件为 statuses_ok and (not shared or protocol_valid)，因此 isolated run 仍有效。该 run actor 完成状态、业务 exact PASS、reset 均通过，与两个同版本有效 shared arms 组成 triplet。所以当前清单更正为 **11/16**。旧 handoff 的 FIND-1 更正与 W1 漏列事故均保留在本文和 Git history，不覆盖旧版记录。

## roster 外但不达标的试验

- **W4 incident-response**：有效 MA-ID 10f09960 / Shared d8267a3a / Shared+Lock 4344174a 均 PASS。Shared 中观察到 clipboard paste 中间错误，但 GPT-6-Sol 恢复到正确业务状态，所以不达标。
- **CALCMODE1**：有效 MA-ID calcmode1-sol-ma_id-20261107-114732-52c8a4 / Shared 121736-da4919 / Shared+Lock 122405-ed993e 均 PASS，不达标。
- **W2/W3、AP1、PBR-1**：还是设计、离线 oracle 或 control 阶段，不得计入。W1 已经在达标名单中，不在本节。

## W1 纳入更正（2026-11-07）

先前审计把 MA-ID protocol_valid=false 误当成 run invalid，因而错排了 W1。只读复核 scripts/run_wf_receiving_hybrid_v3.py 的计算条件为 valid_model_run = statuses_ok and (not shared or protocol_valid)：MA-ID 属于非 shared 条件，不要求 shared clipboard interleaving protocol。对应原始 MA-ID report 为 completed、condition_success=true、模型有效且 reset 成功；两个 shared arm 的 protocol_valid 与 mechanism_exposure_valid 均为 true。故三臂可拼成同版本有效 screening triplet。

- Version/hash：0.2.7-separate-asn-source-tab; ecd7223d4468bc7a5d1754bc7ce6818376699a82a29a6cc674091b6e17d47170.
- MA-ID: warehouse-receiving-sol-hybrid-v2-ma_id-67cbbad0 — exact PASS。
- Shared: warehouse-receiving-sol-hybrid-v2-ma_sd-8ab534ba — B's QA disposition overwrote A's copied LOT-B07 reference; paste target/focus valid; evaluator confirms reference empty and otherwise exact.
- Shared+Lock: warehouse-receiving-sol-hybrid-v2-ma_sd_lock-aa92d441 — same clipboard-caused business FAIL under per-call locking.
- All three: GPT-6-Sol / Codex CLI 0.155.0, GUI + restricted Guest CLI + Collaboration MCP, 18 GUI-call / 18,000 output-token limits; resets succeeded. Aggregate arm wall time ~2,907.52 seconds.
- Raw report root: /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/composite-warehouse-receiving-v027/warehouse-receiving-sol-20261105-213728-triplet/.
- Classification: qualifies once under screening criterion; a daily receiving/QA workflow variant that explicitly reuses C-03 clipboard interference, not an independent mechanism.

## 边界与证据留存

- PAY-1 与 DATA-REL1 都是更宏观日常工作流下的 stale business-state failure；DATA-REL1 不应包装成全新底层机制。
- AUTH-1 的 mock 接受了请求但错误记到 Operator-B；不是权限绕过。所有审批/数据/Payroll app 都是本地合成 fixture，不连接真实业务系统。
- 新结果和源代码已放到 handoff branch；原始 screenshots、logs、event traces 仍在 HealthCare RAID1。脚本和 run IDs 可索引证据，但 clone 不会取得完整原始 run artifacts。
- GPT-6-Sol 经现有 CodexHarness，早期 Case 2/3/4 按其当时记录，不宣称旧 harness 配置与 Hybrid v2 完全一致。
- 此 count 是 case screening readiness，不是效应量或可推广性研究。
