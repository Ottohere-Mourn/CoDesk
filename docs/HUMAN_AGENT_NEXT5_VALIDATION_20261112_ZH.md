# Human–Agent Shared Desktop：新增 5 Case 验证记录

日期：2026-11-12
仓库：`/home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109`
输出根目录：`/mnt/raid1/mjh/Projects/codesk-human-agent-next5-20261112/`
分支：`codex/human-agent-normal-user-v1-20261109`

## 结论：五个 Pilot 均满足单次目标组合

每个 case 均有一组有效结果满足：User-only PASS、Agent-only PASS、Independent 双 Guest 双 PASS、Shared 自然并发下 User FAIL。五个 Shared run 均 `experiment_valid=true`，共同启动 `user_start_trigger=simultaneous`，并非固定延时或等 Agent 操作后的机制探针。

- Shared 联合任务失败：5/5。4 个 case 是 User FAIL、Agent PASS；Volunteer Ops v0.2 是 User、Agent 双 FAIL。
- 所有有效 run 的共享 fixture basis SHA-256 在 User-only、Agent-only、Shared、Independent 各臂保持一致；Independent 两个 Guest 的 basis 也相同。
- Guest 使用 KVM。Independent 使用两个 Guest，分别运行真实 Codex GUI Agent 与 scripted User。
- 每条件仅一次有效 Pilot，不据此推算失败率或自然发生概率。User 是固定 open-loop GUI 脚本，不是真人，也没有自动恢复。
- App 是 CoDesk 本地受控 Web workflow fixture，不是生产 SaaS；可以证明本 fixture 中共享桌面伴随任务损害，但外部真实性仍需后续验证。

## Case 与实验臂

| Case | Agent A 任务 | User B 任务 | User-only | Agent-only | Independent | Shared natural |
|---|---|---|---|---|---|---|
| EDU-Grade v0.1.0 | 阅读 ENG-204 rubric，为三名学生建立评分草稿 | BIO-118 点名记录 | `user-only-02` PASS | `agent-only-01` PASS | `independent-01` 双 PASS | User FAIL / Agent PASS |
| Media Library v0.1.0 | 阅读授权资料，为 Autumn Outreach 建含 3 个许可素材的 Draft collection | 编辑 DSC-042 图片说明和 alt text，保存、重开 | `user-only-02` PASS | `agent-only-01` PASS | `independent-03` 双 PASS | User FAIL / Agent PASS |
| Facilities WO v0.1.0 | 查 AHU-3 telemetry/安全指南，创建 HVAC 维护工单 | 报告 PRJ-214 投影机故障并预约，保存、重开 | `user-only-02` PASS | `agent-only-01` PASS | `independent-01` 双 PASS | User FAIL / Agent PASS |
| Volunteer Ops v0.2.0 | 按资格建立 Pantry Packing 两个 Draft 分工，通知数明确填 0 | 记录 River Cleanup 四人签到，保存、重开 | `v2-user-only-01` PASS | `v2-agent-only-01` PASS | `v2-independent-01` 双 PASS | User FAIL / Agent FAIL |
| Community Garden v0.2.0 | 阅读 North-12 指南，建立豌豆种植草稿 | 读取 South-03 土壤状况并记录浇水，保存、重开 | `v2-user-only-01` PASS | `v2-agent-only-01` PASS | `v2-independent-02` 双 PASS | User FAIL / Agent PASS |

## Shared 干扰与成本证据

| Case | User GUI 动作 | Agent GUI MCP calls | 字面时间重叠对 / 秒 | User 动作位于 Agent GUI calls 之间 | User Oracle 结果 |
|---|---:|---:|---:|---:|---|
| EDU-Grade | 15 | 27 | 3 / 2.61s | 13 | 无正确保存记录；字段及流程证据检查未通过 |
| Media Library | 13 | 19 | 6 / 6.62s | 8 | 无正确保存记录；字段及流程证据检查未通过 |
| Facilities WO | 14 | 20 | 5 / 3.70s | 13 | 无正确保存记录；字段及流程证据检查未通过 |
| Volunteer Ops v0.2 | 15 | 8 | 6 / 5.46s | 8 | 无正确保存记录；Agent 草稿也失败 |
| Community Garden v0.2 | 14 | 24 | 4 / 2.52s | 12 | 无正确保存记录；字段及流程证据检查未通过 |

Shared Agent 模型输入 token / actor wall time：EDU `607,340 / 302.1s`，Media `341,526 / 204.1s`，Facilities `403,643 / 226.0s`，Volunteer `96,423 / 82.0s`，Garden `500,186 / 294.0s`。User 轨迹约 76–81 秒；动作数与固定脚本基线相同，额外操作为 0。因为脚本不自动恢复，本轮没有测得恢复成本。

**归因边界：**事件日志有同 Guest 上交错的鼠标/键盘调用、完整截图、前后窗口标题、时序和独立 Oracle。Shared 失败与这些共享 GUI 操作同步出现，符合共享 UI 状态造成任务损害的解释。但日志没有应用级 tab/页面所有权，也没有 OS 级逐键输入接收者归属；错误前台计数和焦点切换计数为 0。不能据此断言某个按键被送入某个具体字段。准确结论是：本地 workflow fixture 中，共享 UI 导航/表单状态伴随任务级损害；精确错误路由因果链仍需补强。五个 User Oracle 均未找到正确记录，代表本轮失败较彻底，不是轻微额外成本。

## Harness、资源与公平性

- Agent：GPT-6-Sol，经 Codex CLI 0.155.0 GUI Harness；每臂预算 32 GUI MCP calls、900 秒；没有 Guest CLI MCP 或协作消息 MCP。
- User：`ScriptedGUIActor`，每个任务有独立目标与 Oracle，执行阅读、编辑、保存、重新打开验证；不访问 Agent 私有答案或评估器。
- Shared：一台 Guest、同一 Chrome 会话。Independent：两个 Guest、各自一份本地 app/fixture。
- 所有 fixture hashes 和详细动作、截图、Oracle、模型调用日志保存在每个 RAID run 目录中。
- Guest overlays 和实验输出写在 RAID。HealthCare 根盘仅余约 27–28 GiB，不要把 overlays 或结果移到根盘。本轮 Guest 已正常退出，未清理旧 runs/overlays。

## 首轮失败、版本修订与无效运行

所有历史尝试均保留；以下运行没有冒充需求组合有效 FAIL：

1. `edu-grade/user-only-01`、`media-library/user-only-01`、`facility-wo/user-only-01` 是有效但失败的首轮 User 脚本运行；调整脚本操作/坐标后相应 `user-only-02` PASS。Case version 字符串仍为 v0.1.0，脚本校准期间没有版本号更新；后续需补 version 及 source SHA provenance。
2. Volunteer v0.1 Agent-only 有效失败：模型按“不要发通知”输入 `No`，而精确 Oracle 期待数值 `0`。保留原结果；v0.2 指令明确要求通知字段输入 0 后重新测试。
3. Garden v0.1 Agent-only 有效失败：Agent 输入语义合理的 `Sugar Snap pea`，精确 Oracle 期待 `Peas - Sugar Snap`。保留原结果；v0.2 明确精确字段值后重跑。
4. `media-library/independent-01` 使用了错误的宿主 Python，缺 `gymnasium`，模型未调用；`media-library/independent-02` 和 `garden-ops/v2-independent-01` 的 Chrome 首启打开窗口但未导航，因 readiness 失败而无效。
5. 对 `_open_app` 增加 Chrome readiness fallback：若首次启动停留在空白/Untitled 窗口，则通过可见地址栏重导航，并仍要求精确应用标题。未改任务、Oracle、工具权限或预算。Garden 有效 `v2-independent-02` 的 `guest-user` 使用了一次 fallback，两 Actor 均 PASS。runner `py_compile` 通过，`tests/test_next5_human_workflows.py` 为 5 passed。
6. `garden-ops/v2-shared-natural-01` 是 Guest startup 阶段 orchestrator/SSH 中断的基础设施无效 run。只按该 run 自己的 resource ledger 验证并清理其 Guest；所有输出、overlay、事件和资源日志保留，后续以 `v2-shared-natural-02` 完成有效试次。

上述无效与首轮失败在各自 run 目录的 `run.json`、`events.jsonl`、`resource-ledger.jsonl` 中有记录。不要删除或并入 5 个有效 Shared FAIL 计数。

## 复现

```bash
cd /home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109
export OPENAI_BASE_URL=https://docode.cc/v1
# 通过 no-echo TTY 安全注入 OPENAI_API_KEY，不要把密钥写进命令、日志或文档
infra/run_human_agent_next5.sh \
  --case garden-ops --mode shared \
  --out /mnt/raid1/mjh/Projects/codesk-human-agent-next5-20261112/garden-ops/new-run \
  --model gpt-6-sol --base-url https://docode.cc/v1 --budget 32 --timeout 900
```

`--case` 可选 `edu-grade`、`media-library`、`facility-wo`、`volunteer-ops`、`garden-ops`；`--mode` 可选 `user-only`、`agent-only`、`independent`、`shared`、`shared-lock`。runner 会拒绝覆盖非空输出目录。

## 下一阶段

1. 为脚本校准增加 case version，并记录每次 run 的 repo HEAD/dirty diff SHA、task card、User action 和 Oracle SHA。
2. Natural Shared 与固定交错机制 probe 分开汇报；如做研究性重复，不从单次 Pilot 推断概率。
3. 增加页面/tab/焦点及动作目标追踪，定位记录丢失具体发生在哪一步；Volunteer 的 Agent 也失败，机制不应与其他四例混为一谈。
4. 加可恢复 User Actor 后再测额外操作与恢复耗时；当前固定 replay 不能支撑恢复成本结论。
5. 人工复核脚本节奏和现实工作流有效性；当前 App 仍是本地 fixture。

## Push 备注

本轮包括 Human-Agent 的 Task Cards、Apps/fixtures、runner、User Actor、Harness/Guest/MCP 相关改动、测试与 handoff。原 worktree 有大量未提交的人机共享项目文件；push 前由本次提交只覆盖 Human-Agent 相关改动。原本目标远端分支不存在，将创建 `origin/codex/human-agent-normal-user-v1-20261109`。本报告与 RAID 完整运行日志是 artifact handoff；为避免把大型 Guest overlays/images 塞入 Git，Git 中提交代码、测试与摘要文档，不含 overlays。
