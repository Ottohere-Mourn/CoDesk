# VIDEO-REVIEW1 — GPT-6-Sol 三臂结果与审计（2026-11-12）

## 判定摘要

这是第一轮有效三臂。MA-ID 两个任务 Oracle 均为 1.0；Shared 两任务均低于 1.0；Shared+Lock 两任务也均低于 1.0。模型/API、Guest、reset、评估器状态均有效，因此此候选**一次 triplet 达到目标组合**。尚无第二次独立重复；应报告为一次筛查结果，不外推稳定通过率。

## 冻结一致性与有效性

三臂使用 `v2/pgv1safety` / `v2/pgv1maint`、GPT-6-Sol、Codex CLI 0.165.0、high effort、GUI-only MCP、每 Actor 45 次 GUI 调用上限及同一任务指令。MA-ID 是两个彼此隔离的同初始 Guest；Shared/Shared+Lock 是同一 Guest、同一个 Chrome tab 与业务数据库。三臂 fixture 中 `app_v1.py`、`expected.json`、`seed.db` 的 SHA-256 分别完全一致；三份 `source.sha256` 文件摘要相同（`d19e89aba3a3ac1fc3415058e82471be8ebf8c4c82b07b1f98186df240955f3b`）。无一臂有 API/Guest/evaluator error；所有 evaluator `state_readable=true`。

## 结果

| Arm | Run ID | Safety / Maintenance | GUI 调用 A/B | 总输入 tokens（cached） | 输出 tokens | Wall time |
|---|---|---:|---:|---:|---:|---:|
| MA-ID | `cdesk3-v1-ma-id-20261112T145415Z-1062817` | 1.00 / 1.00 | 29 / 37 | 2,419,045 (2,168,230) | 4,692 | 837.1s |
| Shared | `cdesk3-v1-shared-20261112T150911Z-1070500` | 0.25 / 0.40 | 41 / 44 | 3,925,980 (3,538,761) | 10,619 | 1,147.1s |
| Shared+Lock | `cdesk3-v1-shared-lock-20261112T152938Z-1078225` | 0.00 / 0.60 | 28 / 45 | 2,709,655 (2,387,662) | 8,027 | 864.0s |

三臂合计 9,054,680 input tokens（8,094,653 cached）、23,338 output tokens、2,848.2 wall seconds。Shared 比 MA-ID 多 19 次 GUI 调用（85 vs 66）且 wall time 多 310s。Shared+Lock 共 73 次调用，Maintenance 达到 45 次上限；Safety 在第 28 步以有效的模型 `declare_infeasible` 结束，非 infra-invalid。

## Oracle 细节

- MA-ID：Safety frames 2/4/6/8 全部在预期时间有 observation + note；Maintenance frames 3/5/7/9/11 全部正确。
- Shared：Safety 仅 frame 6 正确（0.25）；Maintenance 仅 frame 3、5 正确（0.40）。
- Shared+Lock：Safety frames 2/4/6/8 均没有正确 observation；Maintenance 的 frame 3/5/7 正确，9/11 缺失（0.60）。结束截图中共享表单显示当前 frame 7，Recent observations 只有 Maintenance 的 frame 3、5、7 三条；与 Oracle 一致。

## 机制证据与边界

任务需要反复“定位片段 → 选择 worklist → 写观察 → 提交”。浏览器共享单一时间游标；提交时应用读取当前播放帧为 observation timestamp。两个 worklist 内容彼此独立，frames 互不重叠，且程序没有容量上限或互斥业务规则。MA-ID 正控证明双方任务各自可完成。

Shared+Lock 的 Safety Actor 日志留下 `agentA/INFEASIBLE`：它报告正在复核 frame 2 时页面被反复导航到 frame 3、worklist 变成 Maintenance、输入笔记被清空，因无法验证 Safety 标注而停止。同期时间排序后的日志显示 60 个受锁 GUI 动作确实逐动作串行；累计 lock wait 9.068s、持锁 145.934s。但锁只覆盖单个 GUI 调用，不覆盖上述多步“定位—填写—提交”事务，两个 Agent 能在两次工具调用之间把同一游标/表单改掉。Shared+Lock 仍因此得到 0.00/0.60，而不是锁本身失效或 Guest 问题。Shared 臂也记录到大量重复导航和错误/未保存标注。

**边界：** 目前是 13 帧 timecoded storyboard，不是真实视频解码器或商业 review 产品；效应只支持“同一 Web clip-review session 的全局帧游标/表单状态”机制，不证明所有多媒体软件表现相同。失败包括实际观察到的跨 Agent GUI 状态干扰和共同 45-call 预算耗尽；不能单独把预算耗尽说成误路由机制。没有人工屏障或臂特定障碍。

## 产物

- Case: `tasks/paragui/spec_v1.md`, `app_v1.py`, `pg_v1.py`, `pg_v1_oracle.py`, `task_pgv1safety.py`, `task_pgv1maint.py`
- Fixture builder: `build_v1.py`
- Scripted/reset/setup 与 Oracle controls: `tests/test_v1_oracle.py`, `tests/test_v1_setup.py`
- Runs、动作 traces、agent stdout、screenshots、result.json：`/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/<run-id>/`
- 每次 Guest overlay 都有 RAID archive 副本（约 657 MiB）；cp 的文件模式权限警告未影响数据复制。未清理旧 run/overlay。

## 决定

**本候选：一次有效三臂达到预期组合（1/1 初筛），可暂列“符合一次目标组合”，尚不能称重复稳定。** 需要保留 no-go 条件：若今后加入第二 triplet 时模式切换解决共享游标、或者失败只是普通打字失误而缺少跨 actor 时序证据，则应下调资格。本结果不补算两次重复，也不构成其它两项新 case 的验证。
