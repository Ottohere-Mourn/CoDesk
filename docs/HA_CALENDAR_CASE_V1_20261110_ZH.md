# HA-CALENDAR：团队排期与个人专注时段

日期：2026-11-10 · Case：`ha-calendar-meeting-focus-v1` · 版本：`0.1.0`

## 1. 目的与任务卡

本 Case 把一个较复杂的真实 GUI Agent 工作流与一段正常、较短的模拟用户操作放进同一日历桌面。研究焦点是共享周视图、事件编辑器和表单焦点会不会给任一方带来可观察的任务损害，而非让两方争用同一业务记录。

**Actor A — GPT-6-Sol Codex GUI Agent：**在 CoDesk Calendar 周视图中阅读可见会议简报、3 位参会人的可用时段和房间表；将 30 分钟 `Release Readiness Review` 安排在所有参会人均有空、容量足够的房间；放在 `Project Team` 日历；邀请 Ava Chen、Eli Brooks、Mina Patel；议程覆盖 release blockers、owners、go/no-go；保存邀请草稿，不发送。

**Actor B — Scripted User：**在 `Personal` 日历添加 `Finalize November report`，2026-11-20 13:00–13:45，提前 10 分钟提醒；不邀请任何人。操作用三段固定 GUI 回放（打开新事件、填写、保存），open-loop，不看 Agent 私有答案、Oracle、数据库或任务结果，也不自动恢复。

两项工作流在业务目标上兼容：用户 Personal focus block 不在 Agent 会议参会者名单中，双方各写不同 Calendar 的独立事件。

## 2. Fixture、隔离与 Oracle

- 每个 Guest 使用 run-scoped SQLite + 普通浏览器页面；不接 Google/Outlook、不发外网邮件或邀请。Guest URL 访问的是本地 fixture。
- Fixture 包含 Personal / Project Team 日历、参会人 free/busy、房间容量/availability、会议简报与零初始事件。有效时段为 Tue 2026-11-17 10:30–11:00；房间 Cedar 2 容量满足 4 人。两 Guest Independent 初始 `source_content_sha256` 和 `initial_state` 相同。
- User Oracle 检查 Personal 上恰好一条标题/日期/时段/提醒正确的专注块、没有 Team 副本、不邀请任何人及是否打开周视图。
- Agent Oracle 检查会议只保存一次、Team Calendar、日期与 30 分钟时长、合适房间、3 位参会人、议程、邀请状态仍为 draft、查阅了 availability/rooms、源资料哈希未改变。
- 评估器在演员结束后本地离线运行。受测 Agent 只获得 GUI 截图/输入 MCP，不获得 CLI、直接 HTTP、隐藏状态或评估器。

## 3. 实现与复现

代码：

- `oscombo/human_apps/calendar_planning.py` — 标准库本地日历 Web fixture、固定源资料和离线 Oracle。
- `oscombo/human_agent_calendar_case_runner.py` — User-only、Agent-only、Independent（双 Guest）、Shared（同 Guest 自然同时启动）、Shared+PerActionLock。
- `infra/run_human_agent_calendar.sh` — OSWorld/Guest 路径和 Python 环境 wrapper。
- `tests/test_calendar_planning.py`、`tests/test_calendar_runner_equivalence.py`。

复现需要已装 OSWorld Guest 与 Codex CLI；有效主试验固定 GPT-6-Sol、Codex CLI 0.155.0、40 个 GUI MCP 调用预算、Agent 1200 秒上限；User 固定三动作。将 `CODEX_CLI_BIN` 指向 0.155.0 二进制，并由操作者通过安全环境注入 API key，不要在命令行参数、文件、文档或 run 目录写 key。例如：

```bash
export CODEX_CLI_BIN=/home/mjh/.cache/codesk-codex-0.155.0-20261108/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
export CODEX_NODE_BIN=/home/mjh/.nvm/versions/node/v22.22.2/bin
infra/run_human_agent_calendar.sh --mode shared \
  --out /mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/<unique-run> \
  --model gpt-6-sol --base-url https://api.haogpt.net/v1 --budget 40 --timeout 1200
```

所有正式运行目录和 VM overlay 放 RAID；wrapper 拒绝覆盖非空 run 目录。不要清理历史运行和 overlays。

## 4. GUI 控制和小规模 Pilot

主有效结果使用同一明确的 GUI-MCP 首次截图指令、同一 Case 0.1.0、模型、工具权限和预算。`run.json` 是原始状态；Independent 有一条特殊的 post-hoc 审计说明，见下表。每条件只有一次，不能用于估计干扰率。

| 运行目录 | 条件 | User | Agent | 总用时 / 主要成本 | 状态说明 |
|---|---|---:|---:|---|---|
| `84-calendar-user-only-final-fixture-v1-20261110` | User-only | PASS；3 GUI 动作，18.9s | — | 总计 198.7s（含 Guest 建立） | 最终 fixture 的用户正控 |
| `89-calendar-agent-only-explicit-gui-codex0155-v1-20261110` | Agent-only | — | PASS；23/40 GUI MCP，570.3s；474,674 input（376,768 cached）/ 625 output tokens | 总计 758.2s | Codex CLI 0.155.0；live QEMU KVM |
| `90-calendar-independent-explicit-gui-codex0155-v1-20261110` | Independent，两个 Guest | PASS；3 动作，19.1s | PASS；23 GUI MCP，368.4s | 总计 576.5s | 演员、Oracle、两个初始 fixture 哈希及 `event_count=0` 均已落盘；runner 在最终汇总时误跑了从 Mail 案例复制来的 `review_count` 等字段检查而抛 `KeyError`。原 `run.json` 仍如实保留为 `orchestrator-error`；没有覆盖它。独立审计脚本已离线重跑两个 Oracle 并核实 fixture 等价，结果写在该目录 `posthoc-assessment.json`，标记为“post-hoc reconstructed valid”，不要误称 runner 正常结束。 |
| `91-calendar-shared-natural-explicit-gui-codex0155-v1-20261110` | Shared，自然并发、无锁 | **FAIL**；3 动作，22.2s；无额外动作/恢复 | PASS；23 GUI MCP，650.3s；476,354 input / 723 output tokens | 总计 838.5s | 有效任务失败，不是 infrastructure-invalid。Personal 事件保存到正确日期/时间/提醒，但标题被截为 `FNovember report`，因此精确标题 Oracle 未通过；Agent Team 会议完整正确。无锁等待；窗口代理没有检测到错应用输入。 |
| `92-calendar-shared-lock-explicit-gui-codex0155-v1-20261110` | Shared+PerActionLock | PASS；3 动作，23.9s | PASS；23 GUI MCP，482.3s；468,157 input / 630 output tokens | 总计 656.8s | 有效任务成功；User 等锁 4.58s，Agent 首次 GUI click 等锁 5.68s，动作事件合计约 10.27s；live QEMU KVM。 |

### Shared 轨迹解释

Shared 自然运行并非只看最终 PASS/FAIL。日志显示双方在 187.07s 同时启动；Agent 的首次截图从 195? 具体墙钟记录为 14:04:11.063–14:04:15.902，与 User `fill_personal_block` 结束前约 1.07s 及随后保存操作开始后的约 3.01s 重叠。`shots/user-002-fill_personal_block.png` 已显示表单标题变成 `FNovember report`；数据库记录该 Personal 事件的日期、时间和 reminder 正确，但丢失了目标标题中的 `inalize `。User 因而收到真实的内容损害，而不是任务记录不存在。

Agent 与 User 始终在同一个 Chrome 顶层窗口；`wrong_foreground_actions=[]` 不等于没有输入干扰。现有焦点监视器只观察 top-level window title，不知道同一页面里的 active input/表单控件。首次截图与 User 表单编辑/保存在时间上重叠，与标题截断相符；但本次单样本不能把精确因果归于哪一个并发 GUI 事件。Agent 随后使用 23 次 GUI 调用完成会议；没有任何一方被预设输赢。

PerActionLock 本轮双方都通过，且留下约 10.27s 等待成本；这是一次消融结果，不证明锁一般能修复干扰，也不能与无锁一例推断概率。User 是固定 open-loop，恢复策略尚未实现；恢复时间记为“未测/不可估计”，不是 0。

## 5. 被排除的预检与有效性界限

- `85-calendar-agent-only-sol-v1-20261110`：模型请求正常但 0 次 GUI MCP，Codex 回复无法访问桌面；**infrastructure-invalid，不算 Agent FAIL**。同一 GUI 工具路径已在 Case Mail 与后续 Calendar run 中成功。
- `87-calendar-agent-only-explicit-gui-sol-v1-20261110`：Guest 已启动，但 host-side healthcheck 请求通过 Docker bridge 地址收到 HTTP 502，模型未调用；Guest 已清理。已修正 Backend：Host 本地健康检查改走 `127.0.0.1`，浏览器仍用 Guest 可达的 bridge URL。后续 #88/#89 验证修复有效。
- `88-calendar-agent-only-explicit-gui-sol-v1-20261110`：任务成功，但该次误选了交互 shell 中可找到的 Codex CLI 0.147.0，不符合固定 0.155.0；保留原件，但不纳入主 Pilot 条件结果。
- `90` 的独立等价性字段已从 Mail 特有的 review/draft/sent 计数改为 Calendar 的 `event_count`；回归测试覆盖两个初始日历为空且 fixture hash 一致，以及非空/哈希不同的拒绝行为。

## 6. 小结与下一步

这是一个值得扩展的日常工作流型 Human–Agent Case：用户管理个人时段、Agent 安排工作会议，目标相互兼容；User-only 和 Agent-only 正控都 PASS，Independent post-hoc 两方都 PASS，自然 Shared 一次产生可审计的用户输入损害，而 PerActionLock 一次双通过但有等待。它与简单抢焦点/背景打字测试不同，损害是可验证的目标任务内容受损。

局限：每臂单样本；共享失败样本的因果链只能说与实际重叠一致，不能证明普遍效果；用户是固定脚本；锁按动作而非整个多步事务；同一 Chrome 页内部焦点未被充分测量；本地仿真不是第三方日历产品。保留全部失败/无效尝试，不筛选结果。

Guest 均在实验结束后清理；正式 runs/overlays 位于 RAID。运行时根盘仍约 35–38GB 可用（98%），RAID 约 1.1TiB 可用；不应把大输出放根盘。`tests/test_calendar_planning.py tests/test_calendar_runner_equivalence.py`：7 passed。尚未 commit/push。
