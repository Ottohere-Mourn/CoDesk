# COMMUNITY-PANTRY1 — 模型三臂结果（2026-11-13）

## 判定

**一次完整、未重复的 GPT-6-Sol 三臂初筛满足目标组合：MA-ID 双任务 PASS；Shared FAIL；Shared+Lock FAIL。** 这是当前三新工作流批次中第 2 个一次性目标组合（另一个为 VIDEO-REVIEW1）；WAREHOUSE-LABEL1 全臂 PASS，为 no-go。没有声称重复稳定性，也没有 push。

这是一个社区食品储藏室志愿者服务站工作流：Agent A 把 6 名志愿者安排到指定站点/班次并确认；Agent B 按 $0.67/英里处理同 6 人的里程报销（金额、审批/复核、标准备注）。两个任务可共同完成，既有六组完全正确的联合状态；不是零和设计。应用是本地确定性的单窗口 kiosk 原型，不代表商用 SaaS，也不声称发现新机制。其可测试的共享状态是全局 volunteer 与 work-area 选择器，以及一个共用窗口的提交表单。

## 三臂结果

Harness 三臂相同：Codex CLI 0.165.0、GPT-6-Sol / high effort、GUI-only、每个 Actor 60 次 GUI MCP 调用上限、2400 秒 timeout、同一任务提示/fixture/oracle/reset；MA-ID 使用两个独立 Guest，Shared 与 Shared+Lock 使用同一 Guest/窗口。Shared+Lock 使用现有的 **per-MCP-action** 锁，不跨多步表单事务持锁。

| Arm | Agent A：班次 Oracle | Agent B：里程 Oracle | A/B GUI calls | A/B agent seconds | Arm elapsed seconds |
|---|---:|---:|---:|---:|---:|
| MA-ID | **1.000 (6/6)** | **1.000 (6/6)** | 48 / 49 | 608.1 / 828.2 | 1009.2 |
| Shared | **0.000 (0/6)** | 0.833 (5/6) | 9 / 60 | 238.0 / 410.1 | 559.2 |
| Shared+Lock | **0.000 (0/6)** | 0.667 (4/6) | 24 / 60 | 328.1 / 1106.1 | 1263.1 |

三个 run 的 result.json 均为 error=null、Oracle state_readable=true，非基础设施失败；全臂使用相同预算。Shared 与 Shared+Lock 中 Agent B 到达 60 次调用上限，这是受共享任务中增加的页面/上下文切换影响的有效结果，不改叫 infra-invalid。分臂 GUI/tool trace、截图与资源 ledger 均保留。

### 共享干扰证据

- **Shared：** Mileage Agent 保存首条 claim 后，共享页面计数由 0/6 变成 1/6。Shift Agent 看到这个变化后仅用了 9 次调用便 declare_infeasible，原话是它认为“leave mileage claims unchanged”的要求已无法满足，于是没有保存任何班次。Oracle 为 0/6。这里是 Agent 把“我不能处理报销”误读成“其他 Actor 也不能处理报销”；这是受到并发状态影响的模型判断，不是应用强制的硬约束。另一 Actor 在同一屏正常完成了 5/6 里程记录。
- **Shared+Lock：** Shift Agent 在站点选择与输入班次窗口之间，看到 work-area 多次转到 Mileage claims，于是判断 UI 不保留交互状态并 declare_infeasible，24 次调用后退出，班次仍为 0/6。另一个 Actor 已进行正常的里程录入。轨迹显示 Agent A 的点击/键盘事件发生在 B 切换 panel 后；PerActionLock 保证单次 GUI action 串行，但不能把多步表单上下文固定住，也不能防止另一个合法 Actor 随后改变共享 active panel。
- 这不是人为注入障碍或人为交错调度：两个任务提示对称使用正常 GUI，提交提示/预算一致，另一 Actor 所做的正是它被要求完成的日常工作。失败由共享运行中的原始轨迹和可读 Oracle 共同佐证。

Shared+Lock 锁遥测（汇总双方日志）：79 个带锁 GUI 动作；lock wait 合计 5.3525 秒，held 合计 182.7505 秒，最大单次 wait 1.9266 秒。锁在每个操作后释放，不能覆盖模型思考和后续 GUI 操作。

## 控件、修正与有效性

- Offline tests：tests/test_v3_oracle.py tests/test_v3_app.py **6 passed**。覆盖 seed 负控、联合完整状态双 PASS、错误记录/面板/缺项评分。
- 真实 Guest scripted GUI joint positive：run cdesk3-v3-scripted-joint-20261113T032751Z-1433698，A/B 都通过浏览器 GUI 写入 6 条，两个 Oracle 都为 1.0。CDP 启动有 3 次 socket-hang-up 重试，随后 Guest 浏览器成功打开、操作与评估完成；这是 readiness retry，不是模型 run 失败。
- 最终三臂 fixture manifest SHA-256 均相同：dc13fae13be0ffb85edff6291588b53837c20e0faac56442001062908fe62636；source manifest SHA-256 均相同：ca1f357da71aa1fc9c58e74a86375fd5b66b62b0b765c292d60a27097cdf15cb。模型所用 expected.json 已与提示里的精确备注（末尾句点）一致。
- 最终 Guest overlay 已保存在 RAID，并逐个与 tmpfs 原件 cmp 相同。runner 的 cp 在 RAID 兼容挂载上报告“设置权限不允许”，但目标文件完整，内容校验通过；没有清理旧 runs/overlays。

## API 用量和重现实验

| Arm | 总输入 tokens（cached input） | output tokens | Run ID |
|---|---:|---:|---|
| MA-ID | 3,486,711 (2,765,132) | 6,432 | cdesk3-v3-ma-id-20261113T033134Z-1435452 |
| Shared | 966,312 (754,177) | 5,382 | cdesk3-v3-shared-20261113T034951Z-1443495 |
| Shared+Lock | 4,064,929 (3,280,595) | 12,853 | cdesk3-v3-shared-lock-20261113T040006Z-1448452 |

每个 run 的完整证据路径为：
/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/<RUN_ID>/
（result.json、fixture/source manifest、两 Actor 的 instruction/actions/stdout/stderr/screenshots、resource ledger）；Guest overlay 同名目录在 /mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays/。本地 run 驱动脚本：scripts/run_new_case_arm.sh v3 <ma-id|shared|shared-lock>；任务卡：tasks/paragui/spec_v3.md。

## 保留的前置校准尝试（不纳入三臂判定）

早一轮 cdesk3-v3-ma-id-20261113T030907Z-1425007 使用 45 次调用预算，两位 Actor 都触及 max_steps（班次 5/6，里程 0/6）。审计发现两点：45 不足以自然完成 6 行多字段表单；而任务提示要求 note Verified from signed slip.，旧 expected.json 忘了句点，导致里程 Oracle 6 条全部 false。原始 run 和 fixture manifest 保留，不纳入有效三臂。随后将 MA-ID/Shared/Shared+Lock 一律设为 60 次相同预算、统一 expected 字符串，重跑完整 triplet，并用新 fixture manifest。60-call MA-ID 的 48/49 calls 双 PASS 证实正控足够，同时 Shared 两臂仍有实际额外操作造成触顶。

## 定性和限制

- 判定为**一次性初筛达标候选**，不能说稳定或机制普适。
- 这是社区志愿者排班 + 里程报销这一实用工作流，但底层 active-record/work-area 状态与既有 application-context 类机制相近；作为新业务流程/跨域任务扩展可以，不能宣称新机制。
- Shared+Lock 失败不是“锁系统坏了”：它按设计锁住了 79 次单独动作，但锁边界不跨越从选志愿者、改 panel、填字段到保存的事务。
