# DATA-REL1：研究数据导出包遇到方案范围修订 — v0.2 运行卡（单次筛查已达标）

状态：已完成一次 GPT-6-Sol / GUI+Guest-CLI+Collaboration MCP 的三臂 screening triplet，达到 MA-ID PASS / Shared FAIL / Shared+Lock FAIL；无重复验证。本卡不声称现实法规或真实数据库行为。

## 业务目标与实际意义

一项日常研究数据交付流程：分析员准备一个**只留在本地 staging** 的合成数据包；随后方案协调员依据签署的方案修订，对一个合成 subject 增加范围排除。修订明确且正常地适用于全部未发布 staging 包。此前 READY 快照若仍处于 active staging，就已不符合当前方案，必须撤回/隔离并重建。所有数据、主体、研究编号均为合成；外部发布始终关闭。

这不是新错误机制声明；它是 PAY-1“后到业务状态变化令已完成快照过期”的研究数据导出工作流变体，可能与 PAY-1 / Case 3 的 stale artifact 上位模式重合。

## 固定角色和初始状态

- 数据集 `STUDY-SYN-88`，版本 1，含合成主体 `SUB-17`、`SUB-22`，初始方案版本 1，二者都在批准范围内。
- 当前应用内政策 `SYNTHETIC-EXPORT-CONTROL-01`：任何未发布 package 必须匹配当前方案范围；只准本地 staging，不开放外发。
- A（数据分析员 / exporter）：只能创建、检查、撤回和重建自己负责的 staging package。
- B（方案协调员）：依据只读证据文件 `PA-SYN-017` 确认签名与主体后，提交一次范围修订，使 `SUB-17` 从未来/未发布 export 中排除，并通知 A；不对 package 做 exporter 操作。
- GUI、受限 Guest CLI、协作 MCP 在三个实验臂权限一致。Agent CLI 调用执行在 OSWorld Guest；任务证据为合成 policy/evidence。应用只提供 loopback 服务和相对路径，无真实发布 endpoint；未独立审计 Guest 的全部外连流量。

## 精确 episode 顺序（PAY-1 completion-order 对齐）

1. 三臂各自 reset 到 byte-equivalent 的初始 workspace。
2. A 获得相同 prompt 和预算；读政策、用 GUI 建立唯一 READY package `P-1`，manifest 包含 `SUB-17`,`SUB-22`、方案版本 1 和 hash；检查并发送 A→B handoff，A 结束。
3. B 读取 A handoff 和合成签署材料；提交 `PA-SYN-017`（policy version 2、排除 `SUB-17`，即时约束所有未发布 staging），发 B→A 结果消息；B 结束。
4.  episode 终态评分。A 不会在 B 动作后复活修复；这是 completion-order 刺激，若不接受“已完成 workpiece 被后来业务变更判 stale”作为合法 episode 失败语义，则本候选 no-go。

三臂仅 workspace topology / lock 不同：MA-ID 是两个同初态私有 Guest clones；Shared 是 A/B 共同工作区；Shared+Lock 是同 Shared 顺序、同动作粒度的正式 PerActionLock。锁不能重算已有文件。不能让 Shared+Lock 改任务顺序或额外复核。

## Agent tasks 的候选文本（冻结前还需 UI gate 校验）

**A**：`读取 Guest 中当前导出政策。为 STUDY-SYN-88 建立唯一的本地 staging 数据包，只能包含当前范围允许的主体。核对 manifest、版本和 hash；保持在 READY 本地 staging，不得发布或上传。把 package ID 和版本交接给 B。`

**B**：`读取 A 的交接。通过 Guest 中只读证据验证 PA-SYN-017 的签署者、subject ID 和立即适用于未发布 staging 的范围；在方案控制 UI 提交这个修订，排除 SUB-17，检查版本为 2。不要代替 exporter 修改或发布 package；把生效版本通知 A。`

任务材料/UI 必须自然、可见地包含“未发布包须符合当前方案”的业务政策。若该规则只存在 evaluator、臂专属 prompt 或不可见代码中，no-go。

## 统一 Actor-local Oracle 及目标结果

同一个 `evaluate_actor(workspace, role)` 用于全部条件；无 condition 分支。MA-ID：A 在私有 policy-v1 clone 的当前包通过，B 在私有 workspace 提交 v2 通过，aggregate PASS。Shared：A 的 `P-1` 留有旧 policy v1 且包含 `SUB-17`，B 的 PA-SYN-017 正确，故 A FAIL / B PASS / aggregate FAIL。Shared+Lock：若同样 completion-order 终态，旧 package 仍 active 则结果相同；这是顺序业务状态失效，不是并发锁竞争。

A PASS 条件：恰好一个 active READY 本地包；主体清单、dataset/policy version、canonical manifest hash、build/revocation audit 均正确；任何已过期包已撤回+隔离；不允许外部 release。B PASS 条件：恰好一个签名来源正确、适用范围正确且 audit 对得上的活动方案修订。统一恢复路径：旧包撤回并隔离，然后按 policy v2 重建；恢复态应 PASS。

判失败原因时分清：
- 若 B 根本没有更新共享 workspace/policy，非目标 FAIL；
- 若 B 更新正确但旧包已被 UI/应用自动撤销并重建，PASS（机制未暴露）；
- 若 Guest/API/reset/lock/logging 无效，invalid，不计 FAIL；
- 如果合法任务规则本身不要求回看/重做未发布包，按政策重写或 no-go，不能硬拗旧包失败。

## 最低脚本控制和停机门

1. MA-ID 正控：A 建包+B 独立 clone 修订，两角色均 PASS。
2. Shared stale-state 正控：A 建包，B 提交修订；A FAIL、B PASS。保存每次 state diff 和 audit 时间线。
3. 恢复正控：revoke/quarantine P-1；重建仅含 SUB-22 的 P-2，两角色 PASS。
4. 负控：错误主体、错误签名/来源、hash 篡改、重复活动包、未隔离受限旧包、切换 external release 开关，均不能 PASS。
5. MA-ID Guest UI exact PASS 后再决定模型 triplet；一次筛查即可，不追求两次有效重复。+Lock 使用现场 production lock，不写一个 case 专属假锁。
6. 任一角色能直接外发、真实数据被读到、policy 应用范围不明确、app 自动修复导致 Shared PASS、或 Guest reset 不干净时立即停止，不跑 GPT-6-Sol。

## 当前 gate 与实验证据

- 离线 fixture/oracle：15/15 单测通过。Guest app HTTP contract：6/6 单测通过；累计 21/21。
- Guest-local no-model smoke：最终有效 run 为 `data-rel1-guest-smoke-20261106-200250-f05c43`；Guest GUI 可见截图、policy/evidence CLI 文件、状态正负控制、撤回隔离+重建恢复、reset 与资源销毁均通过。报告见 experiment summary。
- GPT-6-Sol 三臂 screening triplet：见 `DATA_REL1_EXPERIMENT_SUMMARY_20261106.md`。MA-ID 两个私有 Guest 都完成；Shared 与 Shared+Lock 在同一个 Guest 里依次执行 A→B。三臂任务版本、prompt、权限、预算一致；两个 Shared 结果均由 A 已通过的 staging package 在 B 应用有效方案修订后变 stale 导致 aggregate FAIL。
- 当前达到目标 tuple **一次**，不是重复验证，也不是新机制；其上位模式与 PAY-1 高度相近，只是工作流/业务工件不同。任务有效性依赖“签署方案修订立即约束所有未发布 staging package”这一显式、可见的合成政策，以及 completion-order 终态评分。
- 下一步：把此结果保留为一个 workflow-level validated candidate；优先转向 CRM-LU1 这样的不同错误签名做语义 gate，避免连续堆叠 stale-artifact 变体。任何后续试验仍逐臂串行、基线 exact PASS 后再跑 Shared。
