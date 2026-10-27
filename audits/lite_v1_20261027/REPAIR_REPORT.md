# Data-to-Deck Lite v1：工程修复与一次配对复验

日期：2026-10-27。工作分支 `experiment/codesk-lite-v1-20261027`，修复提交 `11ca4b5`。这是原 `CDD-LITE-001` v1.0.0 的适配器修复复验，保留前一组运行和结果。事先冻结的修复与一次配对停止规则见 `repair_protocol.json`。Task Card、Fixture 字节、Gold、Oracle、A/B 指令、模型、40 次/角色桌面调用上限和 1200 秒/角色时限均未改；新 Shared 与 Isolated 的三份公开 Fixture 及 A/B `instruction.txt` 已分别逐字节比对相同。

## 定位与修复

- 两个模型端点均可用。原 `api.haogpt.net/v1` 已完成完整运行；备用 `https://docode.cc/v1` 的同模型图像输入加强制函数调用返回 HTTP 200，约 10.5 秒，详见 `docode_compat_probe.json`。没有证据表明网址导致上一组失败，本组继续用原端点，避免改变实验因素。
- 旧 Isolated A 的动作 18 是删除后 `Ctrl+S`；它随后才重新输入数值，超时前未再次保存。所以“屏幕上有值、回收文件为空”是模型保存时序错误，不是桥丢失。
- 单 Guest 真实 GUI 复现：Impress 中 `Ctrl+O`、`Ctrl+L`、输入 A ODS 完整路径、Enter，可在 Calc 打开。旧 B 在路径输入后先切换只读复选框并反复点 Open；此流程卡住，不能据此判定目标文件不可读。脚本随后故意留下未保存修改，使 `Save Document?` 弹出，官方 reset 在 144.38 秒内换成干净的本轮 Guest。证据在 `runs/cdd-lite-v1-repair-gui-smoke-20261027T113500Z/`。
- 桥先前仅用 revision/hash 检测非 owner 改动，目标 Guest 中的对方文件仍可写。现在只对 Lite 的 Isolated 接收文件设 `0444`，初始副本及每次传输后核验；Shared 不增加输入锁，原版桥默认行为不变。模型启动前两台 Isolated 桌面都预打开 Calc 与 Impress，各角色自己的应用在前台，以匹配 Shared 已打开两份文档的可见性。预打开的 B 侧 A 文件标题明确为 `(read-only)`。
- 后处理 `Ctrl+W` 后立即识别未保存弹窗，保存截图、保留已评分字节并继续精确 reset。它不代替真正的 GUI 重开成功：Shared 本组标 `reopen_complete=false`，Isolated 本组重开通过。

离线 `pytest` 为 **182 passed、1 skipped**。修补后的真实双 Guest scripted 正控 `cdd-lite-v1-repair-isolated-scripted-20261027T114600Z` 为 PASS：A/B/联合 Oracle 均真，A/B 各传 revision 1，接收副本保持 `0444`，双向只读重开和两台 Guest reset 均通过，桥同步错误为零。原 Shared scripted 正控也仍保留并通过。

## 修补后真实双模型配对

| 指标 | Shared | Isolated |
|---|---:|---:|
| run_id | `cdd-lite-v1-repair-model-shared-20261027T121500Z` | `cdd-lite-v1-repair-model-isolated-20261027T124400Z` |
| 独立 Oracle A / B / 联合 | 失败 / 失败 / 失败 | 失败 / 失败 / 失败 |
| Agent A / B 状态 | 超时 / 超时 | 超时 / 提前结束 |
| 桌面调用 A / B | 28 / 22 | 25 / 11 |
| 模型 token A / B | 630,901 / 871,965 | 671,334 / 317,893 |
| 双 Actor 活动重叠 | 1200.1 秒 | 562.0 秒 |
| 模型请求重叠 | 725.3 秒 | 323.5 秒 |
| GUI 动作重叠 | 2.7 秒 | 6.5 秒 |
| setup 至 Actor 起步 | 376.3 秒 | 753.7 秒 |
| 总墙钟（含后处理） | 1765 秒 | 2367 秒 |
| QEMU RSS 采样峰值合计 | 5.087 GiB | 9.913 GiB |
| QEMU CPU 采样累计增量 | 4389 秒 | 8088 秒 |
| A/B 最终保存 revision | 0 / 0 | 2 / 0 |
| 重开 / reset | 未保存弹窗阻塞重开；1 Guest reset 通过 | 自己和对方文件重开通过；2 Guest reset 通过 |

两条件均用同一 `gpt-6-astra`、指令、公开文件、消息/附件工具、Oracle 与预算，真实模型请求并发。Isolated 的 B 提前结束，故执行重叠和 token 差异不等于隔离本身提高效率；setup 增加包括第二台 Guest 和预打开应用，总墙钟也不能解释为纯桌面拓扑成本。两次均无桥同步错误；最终文件在评分侧重跑 Oracle 与运行内结果一致。密钥只在 Git 外 coordinator/relay 文件，扫描本组日志与产物为零匹配。

## 失败归因

Shared 中，B 多次对 A 正在使用的 Calc 发送 `Alt+F4`，真实截图显示 A 工作簿的 `Save Document?` 弹窗。A 一次单元格点击及后续 `51.33%` 输入发生在该弹窗前台，后者没有成为已保存 Findings；A/B 后续有 Escape/取消等恢复尝试。直接证据见本轮 `focus_event_repair_shared_001.json` 和对应 `actor_runs` 截图。A 输入的 `51.33%` 本身也不正确；双方最终没有新保存版本，不能把全部失败归于焦点竞争。

Isolated 中，B 实际打开了自己 Guest 内的只读 A 工作簿，看到 revision 0 的空白 Findings，并在执行约 373 秒向 A 发出明确请求。但 B 在约 562 秒就结束；A 到约 649 秒才发布 revision 1，约 784 秒回复，约 1145 秒又发布 revision 2。桥把两版都在约 1.9 秒内传到 B Guest 并回读核验，但 B 模型进程已结束，没有消费最终版本，PPT 仍是初稿。A 的最终 ODS 中 gross margin Value 为空，West 值为错误的 `-9`，两项 Evidence 不满足来源要求；受保护原始表仍完好。详见本轮 `handoff_timeline.json`、`workspace_versions/events.jsonl` 和 `oracle.json`。这是模型的数值、证据与等待交接问题，不是同步桥或文件权限故障。

## 结论与边界

可确认修好了三个工程问题：Isolated 对方文件只读权限、两拓扑初始打开文档的可见性差异，以及模型留下未保存弹窗时后处理评分被异常吞掉且不 reset。真实 Guest 正控和本组正式运行给出了证据。**尚未修好模型完成任务的能力**：本组仍是 0/1 对 0/1，不能声称隔离提高成功率。若继续降低普通 GUI 导航负担或要求 B 在 A 交接前保持执行，应另建 Lite 新版本，冻结新 Prompt/预算/工具后重新做双拓扑正负控与配对实验；不在 v1 的这一组之后追分重跑。其他六题本轮未修改。
