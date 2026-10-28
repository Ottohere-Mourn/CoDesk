# CoDesk Data-to-Deck Lite v2：交接生命周期修复与新对照

日期：2026-10-28。分支 `experiment/codesk-lite-v2-lifecycle-20261028`。本轮只修改 Lite v2 的运行协调机制；原版、v1、其他六题及旧运行均未覆盖。冻结的正式协议见 [PROTOCOL.md](PROTOCOL.md)，三次旧运行的逐项审计见 [ROOT_CAUSE.md](ROOT_CAUSE.md)。

## 为什么旧 Pilot 成功、两次正式失败

旧 Pilot 的 B 连续轮询到 A 的已保存 revision 和结果消息，实际读取后改写并保存 Impress，因此联合 PASS。旧 Shared/Isolated 的 B 分别在 A 消息前约 195 秒/6 秒，以“仍在等待”为最终回复正常退出；它们只用了 4/25 次桌面调用，模型请求均 HTTP 200，没有超时、步数耗尽或强制终止。Isolated 中 A 文件已提前保存且同步，A 发消息却比 B 结束晚 6 秒。直接行为原因是 B 模型提前结束；Harness 缺陷是把这类正常退出无条件视为终局 `done`。现有 `desktop.wait` 只是延时截图，需要继续消耗桌面调用和模型轮次，不具备等待消息并唤醒的生命周期。

## 修复与验证

Case spec 只声明公开的 `B` 依赖 `A`；协调器若发现 B 正常退出但自己尚无新产物，且 A 的保存版次/消息未同时到达，或最新消息尚未出现在 B 的 `read_messages` 结果中，则记录暂停。A 的公开 revision 和消息都到达后，用 B 自己的私有 Codex 会话恢复；提示只要求检查协作工具，不传答案。暂停期间不调用 B 模型或桌面，原步数计数和同一个角色墙钟上限继续生效。Shared/Isolated 均启用同一开关，未加输入锁；交接已读后 B 若仍放弃，按模型错误计。Gold/Oracle 仍只在评分端。

离线全仓测试：`192 passed, 1 skipped`。离线生命周期测试覆盖先消息后文件、提前退出后暂停/唤醒、消息恰在最后一次读取后到达的竞态，以及原 Codex 会话恢复命令。真实 Isolated 诊断 Pilot `cdd-lite-v2-life-pilot-isolated-20261028T083300Z` 使用 15 次桌面调用和 720 秒/角色：A 正确保存，B 在真实 Impress GUI 输入正确结论，但 720 秒刚好截断了 B 的 `ctrl+s` 工具，未形成 B revision 1，冻结 Oracle 联合 FAIL。该轮没有触发提前退出后的暂停；它校准出 720 秒过短，记录被完整保留，不作为拓扑正式得分。随后冻结正式预算为 25 次桌面调用和 1200 秒/角色。

独立的最小真实模型会话恢复探针 `cdd-lite-v2-resume-compat-20261028T100100Z` 在**无 Guest、不参与 Benchmark 评分**的条件下完成两个 Codex 回合，两个 `thread.started` ID 相同、两次 `turn.completed`、桌面调用 0。它验证真实 CLI 与模型端点可以恢复同一私有会话；它不等于真实 Guest 里的 B 曾被唤醒。

## 冻结协议下的正式配对

| 指标 | Shared（单 Guest） | Isolated（双 Guest） |
|---|---:|---:|
| 冻结 Oracle：A/B/联合 | 通过/失败/失败 | 通过/通过/通过 |
| 等价表达次级审计：A/B/联合 | 通过/通过/通过 | 通过/通过/通过 |
| 桌面调用 A/B | 10/9 | 9/9 |
| 模型总 token A/B | 186,974/207,881 | 232,259/300,386 |
| setup 至 Actor 起步 | 336 秒 | 665 秒 |
| Actor 阶段 | 730 秒 | 784 秒 |
| 双 Actor 活动重叠（不含挂起） | 398 秒 | 346 秒 |
| 模型请求重叠 | 266 秒 | 237 秒 |
| GUI 输入动作重叠 | 0 秒 | 0 秒 |
| B 挂起/唤醒 | 无/无 | 无/无 |
| QEMU 同时 RSS 峰值 | 4.987 GiB | 9.854 GiB |
| QEMU CPU 采样增量 | 3301 秒 | 6753 秒 |
| 总墙钟（含 setup/后处理） | 1330 秒 | 1905 秒 |

Shared 轨迹：A 从前台 Impress 切回 Calc，在正确窗口填写并保存 `-11` 与 `B3:E4`，发布 revision 1 并发消息；B 模型实际读到消息后切回 Impress，编辑一处结论、保存并发布 revision 1。B 的第一次键鼠输入发生在 A 结束 **37 秒后**，两人 GUI 输入动作没有重叠，因此本轮未观察到焦点抢占或误路由。冻结 Oracle 的 A 成功、B 失败仅由金额表达 `11 USD thousands` 未匹配正则导致；其余 B 检查均通过。独立的、明确标为**事后**的等价表达敏感性审计只增加这一财务报表单位顺序，Shared A/B/联合均通过。该次级复核不覆盖正式 Oracle，也对 Isolated 产物以同一规则运行。

Isolated 轨迹：A 在自己的 Calc 中输入公式，09:43:04 保存并通过桥传输 revision 1，09:44:52 发出核验消息；B 的 `read_messages` 结果确实包含该消息，随后在自己的 Impress 中输入 `$11 thousand`，09:48:32 保存 revision 1。冻结 Oracle A/B/联合均通过，严格行为交接审计也通过。A、B 自己的文件和对方只读副本均通过真实 GUI 重开，双 Guest reset 成功，桥无同步错误。B 首次键鼠输入发生在 A 结束 91 秒后，因此无跨 Agent GUI 输入重叠。

两次正式运行的 A/B 角色指令字节一致，三个公开 Fixture 文件的 SHA-256 也逐一相同；模型均为 `gpt-6-astra` medium，角色时限与桌面步数相同，且都启用同一生命周期开关。两组均没有 `actor_lifecycle.jsonl` 暂停事件，故无法从这两组估计挂起时节省的 token，也不能说自动唤醒是本次成功的原因。双 Actor 的模型请求有真实时间重叠，键鼠输入却没有重叠；Shared 的 B 首次输入比 A 结束晚 37 秒，未观察到焦点抢占、输入误路由或恢复行为。旧 v1 曾有焦点干扰，本轮不能借旧证据归因。

**回答研究问题：**旧 Pilot 成功而旧正式失败，是 B 的不同停止时机遇上缺少异步生命周期；Prompt 已要求等待，模型仍会给出过早终局，Harness 原先把正常退出当完成。新逻辑对这类退出可暂停并恢复，离线状态测试和真实 CLI 双回合探针通过；本组模型恰好都主动等到交接，故“B 总能可靠等待”的端到端统计结论仍需更多预注册运行。两种桌面的基本任务均形成了正确保存产物和真实交接；冻结 Oracle 的表面差异由 Shared 的单位表达正则遗漏造成，不能解释为桌面隔离效果。Shared 本次没有自然焦点干扰证据。正式两条件各只运行一次，不筛选样本。宿主无 KVM、Guest 使用 QEMU TCG；Isolated 两台 Guest 的 setup 和资源成本不能按桌面隔离的纯执行耗时解释。

原始证据保存在本机唯一 run_id 目录；为方便远端复核，本次 Pilot 和两组正式运行的最终文件、逐步真实截图/动作/模型事件、消息、版次、Oracle 与指标还复制到了版本化的 [evidence](evidence) 目录（约 23 MiB），扫描未发现提供商密钥或运行期协作 token。直接入口：[Shared 结果](evidence/shared/result.json)、[Shared 最终 Calc](evidence/shared/artifacts/A/verified_analysis.ods)、[Shared 最终 Impress](evidence/shared/artifacts/B/final_management_brief.odp)、[Isolated 结果](evidence/isolated/result.json)、[Isolated 最终 Calc](evidence/isolated/artifacts/A/verified_analysis.ods)、[Isolated 最终 Impress](evidence/isolated/artifacts/B/final_management_brief.odp)、[Pilot 结果](evidence/pilot_isolated/result.json)。运行器完整的 Guest 资源采样和 reset 日志仍在被 Git 忽略的本机 `runs/` 下；清理已按 run_id 完成。
