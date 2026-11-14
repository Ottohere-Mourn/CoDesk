# V11–V12 GPT-6-Sol 三臂结果（一次性 Pilot）

日期：2026-11-14。分支：`codex/all-codesk-cases-20261113`。模型：GPT-6-Sol；Codex CLI 0.165.0；endpoint 为 `https://api.haogpt.net/v1`。每 Actor GUI budget=60；Fixture、任务文本、模型、工具权限一致。Independent/MA-ID 使用两个独立 Guest；Shared 和 Shared+Lock 使用同 Guest。Shared+Lock 只序列化每次 GUI action，不持有 task-wide lock。评分依据 task Oracle，不把 API/SSH 错误当成任务失败。

Token 数是 run result 对两个 Actor 的汇总，input 包含 cached input；耗时为每 Actor 活跃秒数 A/B。每格的 task 分数顺序均与该 case 的 A/B 对应。

## V11 — LIBRARY-CIRCULATION1

| Arm | Run ID | A score / status / GUI calls | B score / status / GUI calls | 合计 calls | 合计 input / output tokens | A/B agent 秒 |
|---|---|---|---|---:|---:|---:|
| MA-ID | `cdesk3-v11-ma-id-20261113T165646Z-1782729` | 1.0 / done / 48 | 1.0 / done / 37 | 85 | 3,518,289 / 5,314 | 1102.1 / 728.1 |
| Shared | `cdesk3-v11-shared-20261114T034313Z-2065458` | 0.0 / fail / 18 | 0.3333 / done / 34 | 52 | 1,391,907 / 3,332 | 446.1 / 682.1 |
| Shared+Lock | `cdesk3-v11-shared-lock-20261114T035740Z-2071138` | 0.0 / done / 25 | 0.0 / done / 23 | 48 | 1,134,131 / 3,448 | 520.1 / 472.1 |

**判定：一次有效 tuple。** Shared 中 Hold 任务 0.0、Returns 仅完成 1/3；Shared+Lock 两个 task 均 0.0。所有三个有效 run 的顶层 `error=null`，Codex Actor exit code 均为 0；模型主动终止/提交结果不等于 Oracle 成功。第一次 Shared 尝试 `cdesk3-v11-shared-20261113T171928Z-1791769` 在 SSH 会话中断时没有保存顶层结果 JSON，虽有部分轨迹，故作 interrupted/invalid，不用于 tuple。

## V12 — CIVIC-RECORDS1

| Arm | Run ID | A score / status / GUI calls | B score / status / GUI calls | 合计 calls | 合计 input / output tokens | A/B agent 秒 |
|---|---|---|---|---:|---:|---:|
| MA-ID | `cdesk3-v12-ma-id-20261114T040931Z-2077091` | 1.0 / done / 40 | 1.0 / done / 41 | 81 | 2,701,943 / 3,363 | 844.1 / 804.1 |
| Shared | `cdesk3-v12-shared-20261114T042723Z-2084176` | 1.0 / done / 45 | 0.0 / fail / 19 | 64 | 2,200,328 / 3,650 | 1054.1 / 334.1 |
| Shared+Lock | `cdesk3-v12-shared-lock-20261114T050707Z-2099521` | 1.0 / max_steps / 60 | 0.0 / fail / 20 | 80 | 3,214,487 / 4,715 | 1762.2 / 342.1 |

**判定：一次有效 tuple，带预算标注。** Shared 和 Shared+Lock 的 Intake B 都是 0.0；锁臂的 Review A 已由 Oracle 得到 1.0，但 runner 到 60 GUI calls 才停止并记 `max_steps`，故这是调用预算耗尽后的已完成高成本 Actor，而不是其任务失败。Intake Actor 在日志中报告表单输入后 app active panel 被切回 Disclosure review、字段不能稳定保留；该 Actor `exit_code=0`、run 顶层 `error=null`。按“每臂任一任务低于 1.0”的预注册筛选口径，lock arm 仍有有效 Shared-task failure；对预算耗尽 caveat 单列，不隐藏。

### 无效运行（保留，不计数）

- V12 首次 Shared+Lock：`cdesk3-v12-shared-lock-20261114T044805Z-2091479`。Codex SSE stream disconnect / idle timeout，两个 Agent 未启动，随后人工中止，无结果 JSON；**infra/API invalid，不是 task fail**。重跑同一 endpoint、任务和 budget 后获得上表有效 run。
- 最终 V12 Shared+Lock run 的任务结果、tool event、screenshots、fixture/source hashes 均已写入 RAID。runner 归档 tmpfs overlay 到 RAID 时受到文件系统 chmod 限制，出现 `could not archive tmpfs overlay` 警告；Guest 已停止，评分和运行日志完整，但那个 Guest overlay 的长期副本没有成功归档。其他已有数据没有删除。

## 成本与限制

- 同一质量标准下，V11 MA-ID 共 85 次、V11 Shared 52 次、V11 lock 48 次 GUI calls；V12 三臂分别 81 / 64 / 80 次。V12 lock 单 Actor 用尽 60-call 上限、实际 agent 时间约 29.4 分钟，提醒这类三记录表单任务较慢。
- 两案完整有效 tuple 数：**2/2 一次性命中**；不要求两次重复，本轮也没有做第二有效重复。
- 这是新增工作流覆盖，不是两种新的故障机制。V11 的 active panel/record switching 与 V12 的 active panel/record switching 均落入现有 shared application-context/input-routing 家族。界面没有单独的语义 panel-switch telemetry；因果证据主要来自 Model-visible UI/tool logs、失败原因和 Oracle state，因此结论仍是有限的实验室 Pilot。
- 所有运行代码来源快照见每个 run 的 `source.sha256`；Fixture hashes 见 `fixture.sha256`。原始 screenshots、events 和 codex stdout/stderr 留在 RAID run ID 目录，不放进 Git。不要拿无效尝试的部分输出填补有效结果。
