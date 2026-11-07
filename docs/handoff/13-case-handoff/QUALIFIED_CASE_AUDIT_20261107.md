# 达标 case 数量与证据审计（2026-11-07）

## 审计结论

**当前按用户接受的一次有效 screening triplet 口径，明确达标 10 个。**

范围：既有 13-case handoff roster + 后来完成并达标的 PAY-1、DATA-REL1 两个具名任务，共 15 个编号 case；不是所有离线 workflow 模板、构思草案或失败的 setup 尝试。

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

每案当前只有一组三臂，无第二次有效重复；不估计总体发生概率或模型失效率。

## 严格门槛

1. 三臂 task version、fixture、prompt、model、工具权限和预算一致；MA-ID 隔离，两个共享条件在该实验定义下共享目标 workspace 状态。
2. 三臂都是有效模型/协议/reset/lifecycle 结果；MA-ID 必须业务 PASS，两个共享臂必须业务 FAIL，并由 trace/业务 oracle 支持共享机制归因。
3. 中间错误后恢复成功、最终业务 PASS，不算目标组合；W4 是明确反例。
4. Shared+Lock 是本项目实验配置的 per-action lock，不自动等同事务锁、数据库隔离或同时 GUI 调用争用。PAY-1、DATA-REL1 为 completion-order schedule，没有锁竞争者；VIEW-1 为串行 schedule，证明逐动作锁不会自动把陈旧坐标重新映射到意图目标。
5. 所有无效尝试保留，不挑选性地算作任务失败。

## 旧 13 项计数的更正

2026-11-05 handoff 曾列 9/13，包含 FIND-1。本次复审 FIND-1 v0.3.2：它没有匹配任务版本的有效 MA-ID baseline；v0.3.1 MA-ID 与 v0.3.2 shared arms 不能拼成严格 triplet。并且 v0.3.2 no-lock report 顶层 aggregator 与内嵌 evaluator 意见不一致。故旧 13 项按本规则为 **8/13**。PAY-1 和 DATA-REL1 各有一次同版本有效 triplet 达标，当前为 **10/15**。不覆盖旧 adjudication 文件，保留更正理由供审计。

## roster 外但不达标的试验

- **W4 incident-response**：有效 MA-ID 10f09960 / Shared d8267a3a / Shared+Lock 4344174a 均 PASS。完整 run ID 前缀为 w4-sol-hybridv2-ma_id、w4-sol-hybridv2-ma_sd、w4-sol-hybridv2-ma_sd_lock（目录 w4-sol-triplet-20261106-131701）。Shared 中观察到 clipboard paste 中间错误，但 GPT-6-Sol 恢复了正确业务状态。
- **CALCMODE1**：task version 0.1.0-hybrid-v2，fixture SHA 3da3591eb9b6a1c5bb28288cdd9d6ae82b72540bf923ad663118be2452b079b5；有效 MA-ID calcmode1-sol-ma_id-20261107-114732-52c8a4、Shared calcmode1-sol-ma_sd-20261107-121736-da4919、Shared+Lock calcmode1-sol-ma_sd_lock-20261107-122405-ed993e 都 PASS，没达标。
- **warehouse-receiving v0.2.7**：最近 MA-ID report 为 warehouse-receiving-sol-hybrid-v2-ma_id-67cbbad0，protocol_valid=false；Shared 8ab534ba / Shared+Lock aa92d441 虽 status completed，却不能同无效 baseline 拼成有效 triplet，故不达标。
- **W3、AP1、PBR-1**：仍处于设计、离线 oracle 或 control 阶段，不得计入。

## 边界与证据留存

- PAY-1 与 DATA-REL1 都是更宏观日常工作流下的 stale business-state failure；DATA-REL1 不应包装成全新底层机制。
- AUTH-1 的 mock 接受了请求但错误记到 Operator-B；不是权限绕过。所有审批/数据/Payroll app 都是本地合成 fixture，不连接真实业务系统。
- 新结果和源代码已放到 handoff branch；原始 screenshots、logs、event traces 仍在 HealthCare RAID1。脚本和 run IDs 可索引证据，但 clone 不会取得完整原始 run artifacts。
- GPT-6-Sol 经现有 CodexHarness，早期 Case 2/3/4 按其当时记录，不宣称旧 harness 配置与 Hybrid v2 完全一致。
- 此 count 是 case screening readiness，不是效应量或可推广性研究。
