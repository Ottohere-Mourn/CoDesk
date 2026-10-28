# Lite v2 B 提前结束：三次旧运行的对齐审计

审计对象：2026-10-27 的 Isolated 小预算 Pilot、Shared 正式和 Isolated 正式。原始 `runs/` 保留；本文件不修改旧评分或任务语义。时间均为 UTC。

| 运行 | B 结束 | A revision 1 | A 交接消息 | B 读到消息 | B 桌面调用 / 上限 | B 模型请求 | B 终态 |
|---|---|---|---|---|---:|---:|---|
| Isolated Pilot | 15:22:53 | 15:17:23 | 15:18:16、15:19:23 | 是，首次消息 | 11 / 15 | 29 | `turn.completed`、退出码 0、Harness `done`；Oracle PASS |
| Shared 正式 | 15:43:50 | 15:46:43 | 15:47:05、15:47:41 | 否 | 4 / 25 | 21 | `turn.completed`、退出码 0、Harness `done`；B Oracle FAIL |
| Isolated 正式 | 16:10:39 | 16:10:03 | 16:10:45 | 否 | 4 / 25 | 14 | `turn.completed`、退出码 0、Harness `done`；B Oracle FAIL |

三次 B 的模型 HTTP 请求均为 200。两次正式的最终回复都是“仍在等 A”，与角色指令 `Do not finish before A's handoff` 冲突；没有 `declare_infeasible`、模型超时、桌面步数耗尽或 Harness 强制杀进程。`CommandHarness.run` 在 Codex 正常退出后只根据退出码与调用数标记 `done`，不认识未满足的外部依赖。`desktop.wait` 只是计时并返回截图，需要模型再次轮询；它并非消息等待或唤醒原语。协作 API 原先只有即时 `read_messages`/`list_saved_artifacts`，没有等待订阅。Shared 中 A 的交接比 B 结束晚 195 秒；Isolated 中 A 早于 B 36 秒保存文件，但消息比 B 结束晚 6 秒，B 最后一次读消息为空后便结束。该 6 秒不是同步桥延迟：A revision 1 已传输验证，差距在 A 发消息与 B 会话结束的时序。

因此直接错误是 B 模型过早给出终局回复；系统缺口是协调器把尚待交接的正常退出当作不可恢复的完成。Pilot 的 B 恰好持续轮询到 A 的消息，之后 GUI 编辑并发布，所以通过。现有 Prompt 已明确要求等待；仅再强化文字不能建立可靠的异步生命周期。

本轮修复只在显式启用 `--handoff-lifecycle` 的协作 v2 模型运行生效。若 B 返回 `done` 时 A 尚未同时具备公开消息和 revision 1，且 B 自身尚无新 revision，协调器记录暂停、停止 B 模型调用；两项公开条件到达后用同一 Actor 私有 Codex 会话恢复。恢复提示仅要求用协作工具检查更新，不含结果内容、Gold 或 Oracle。全程保持原桌面调用预算与统一墙钟上限，没有 GUI 输入锁；两种拓扑使用同一代码和角色 Prompt。如果 B 在交接已到后仍提前结束，仍按模型失误记录，不由协调器反复重试。
