# CoDesk Data-to-Deck Lite v1 实验报告

状态：2026-10-27 完成 Lite v1 开发、正负控、真实 Guest scripted 正控、一次有效小预算 Pilot 和各一次完整 Shared/Isolated 双模型运行。**两条件的模型任务均未通过**；正式运行的后处理 GUI 重开均有基础设施错误，故“模型任务得分”和“整轮生命周期通过”分列。

## 版本与任务

独立 Case `CDD-LITE-001` v1.0.0，工作分支 `experiment/codesk-lite-v1-20261027`。原版 Task Card、Fixture、Gold、Oracle、已有运行记录未覆盖。Lite 的公开输入是六行 Q2/Q3 区域 Sales/Costs、KPI 定义、空白 Findings，以及一页有误的 Impress 草稿。A 在 Calc 核验 Q3 gross margin 与 West Q3−Q2 operating-profit change，填入数值和源单元格依据；B 可并发准备草稿，但最终必须使用 A 的最新已保存版本，修订利润方向、幅度、promotion 增量和因果限定，并引用该 ODS 的真实 SHA-256 前 12 位。公开任务卡见 `oscombo/collab/data_to_deck_lite_v1/TASK_CARD_ZH.md`，完整设计契约见 `DESIGN.md`。

隐藏 Gold 在 `private/gold.py`，Oracle 在 `oracle.py`，只供宿主评分与脚本正控。Oracle 检查 A 的正确数值、单位、Sales/Costs 来源地址及原始表保护；检查 B 的一页最终语义、错误因果纠正、标题和对 A 最终字节的摘要引用。模型实际是否阅读 A 的版本由消息、revision、GUI 轨迹另行审计，摘要字符串本身不算交接证据。

## 环境与验证层级

- 152 vCPU、约 1 TiB RAM；`/data3` 可用空间约 115 GiB。`/dev/kvm` 不可供当前用户使用，运行 rootless Docker 中的 QEMU TCG；每 Guest 配置 8 vCPU、8 GiB RAM。基础镜像 `osworld-v2-ubuntu-x86.qcow2` SHA-256 为 `28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a`，归档 SHA 已按发布清单核验，`qemu-img check` 0 错误。OSWorld Provider 固定提交 `3d778a3c9a34a079316f70df023b166700445792`，运行镜像固定 `sha256:4696860fc79a4a6815f61f2a063f473eb8df33534aef3107d126199cb3f2a116`。
- 离线 pytest：181 passed、1 skipped。Lite 独立正负控包括正确 ODF、错误数值、无关 Evidence、错误方向、未限定因果、伪造/过期摘要、源表改动、损坏文件和等价措辞。
- 真实 scripted Shared：`cdd-lite-v1-scripted-shared-20261027T000001Z`，Oracle A/B/联合均通过；真实 Calc/Impress 输入、保存、文件回收、两份文件重开、1 Guest reset 均通过。
- 真实 scripted Isolated：`cdd-lite-v1-scripted-isolated-20261027T080800Z`，Oracle A/B/联合均通过；A revision 1 约 1.17 秒传入 B Guest 并读回一致，双方各自重开及对方只读打开同一 SHA，2 Guest reset 通过。A→B 消息与附件经过真实接口验证，接口权限的双向行为另有离线测试。
- 强模型接口：`gpt-6-astra` 对真实桌面截图和强制函数调用返回 HTTP 200、可解析用量；密钥仅存 Git 外权限 0600 文件，由 coordinator/loopback relay 使用，Actor 只拿 run 专属本机令牌。模型运行目录扫描未发现提供商密钥。

## 模型运行及公平性

同一模型、公开输入字节、角色指令字节、40 次/角色桌面工具调用上限、1200 秒/角色超时、消息与附件工具、SavedArtifactBridge 和 Oracle。Shared 是双模型 Actor 并发控制同一桌面，无跨 Agent 输入锁；Isolated 是双模型 Actor 并发控制两个独立 Guest，桥同步完整保存的产物并记录 immutable revision/ownership。两条件的三份公开 Fixture SHA 和 A/B `instruction.txt` 已逐字节比较相同。环境 setup、Actor 执行、模型请求、GUI 动作和截图、QEMU 进程资源分别采样。

首个诊断 Pilot 因协作 MCP 审批配置错误，已标 `EXCLUDE_INFRA_MCP_APPROVAL`；错误与修复均保留。修复后有效 8 次/角色 Pilot：B 的版本列表和 A 的消息读取工具实调成功，A/B 均因小预算未完成任务；执行区间重叠 462 秒，模型请求重叠 292 秒，GUI 动作重叠 2.5 秒。

完整 Shared `cdd-lite-v1-model-shared-20261027T091100Z`：A/B 各达到 1200 秒超时，分别 21/14 次桌面调用；初始 output 文件未产生新 revision，独立 Oracle A/B/联合均失败。A/B 执行区间重叠 1200 秒，模型请求重叠 931 秒，GUI 动作重叠 9.0 秒；模型 token A 395,220、B 342,500。QEMU 采样峰值 RSS 5.069 GiB，CPU 时间增量约 11,150 秒。模型结束后的 GUI 重开被未保存 `Save Document?` 弹窗挡住，故整轮 runner 标记基础设施错误且未完成 reset；这发生在独立文件回收和 Oracle 评分之后，须与模型任务得分分列。后处理已修补为保留弹窗截图、标记重开不完整、继续 reset；不为追求得分重跑 Shared。

Shared 有两条直接可见的干扰链：B 在 Impress 打开文件对话框后，A 激活 Calc，B 的路径文本进入 Calc 的 Sales!A1；随后 A 编辑 Findings!B2 公式时，B 点击同一 Calc 的 Findings!A2，公式末尾插入 `A2`，A 提交后显示 `Err:509`。两条分别由动作时间戳和连续截图支持，见运行目录 `focus_event_shared_001.json` 与 `focus_event_shared_002.json`。A 后来尝试把数值改回屏幕显示的 `45%`，但没有保存新的 ODS。B 曾向 A 询问指标，A 未读取该消息，双方没有可证实的最终版本交接。错误数值与未完成保存可能同时受桌面干扰和模型普通 GUI 能力影响，不能把最终失败全归因于焦点。

完整 Isolated `cdd-lite-v1-model-isolated-20261027T093906Z`：A/B 各执行 1200 秒至超时，分别 25/18 次桌面调用。A 的 Calc 屏幕曾显示 `45%%` 与错误的 `-10`，证据列仍空白；最后一次保存的 ODS 实际 Findings 数值和 Evidence 均为空。B 在自己的 Impress 中多次尝试通过 Open 对话框打开 A 的 ODS，结束时仍停在对话框；最终 ODP 是初始版本。独立 Oracle 复评与运行内结果完全一致：A/B/联合均失败，三张受保护工作表完好。A 保存的 revision 1（SHA-256 `e902adca2ed4baaeabc96be45914c519b93e918559e79b1f17cdbce313856c76`）在 1.27 秒内传到 B Guest，并由桥在目标 Guest 读回核验；桥报告 0 个同步错误。B 没有成功在 GUI 中读到这一版，因而没有有效信息交接。B 的 `list_saved_artifacts` 和 `read_messages` 调用成功；后续一次错误的 `read_mcp_resource` 参数是模型工具选择失误。两 Guest 没有共享焦点，B 的阻滞属于普通 GUI 文件打开操作，A 的数值/保存缺口属于模型与 GUI 操作链，均不能归咎于桌面竞争。

| 单次完整运行 | Shared | Isolated |
|---|---:|---:|
| Oracle A / B / 联合 | 失败 / 失败 / 失败 | 失败 / 失败 / 失败 |
| Guest 数 | 1 | 2 |
| setup 至 Actor 启动 | 398 秒 | 585 秒 |
| 双 Actor 同时存活 | 1200 秒 | 1200 秒 |
| 模型请求实际重叠 | 931 秒 | 774 秒 |
| GUI 动作实际重叠 | 9.0 秒 | 0 秒 |
| 桌面调用 A / B | 21 / 14 | 25 / 18 |
| 模型 token A / B | 395,220 / 342,500 | 497,359 / 367,731 |
| GUI 动作耗时 A / B | 59.1 / 40.0 秒 | 91.8 / 66.6 秒 |
| 截图耗时 A / B | 74.7 / 50.6 秒 | 111.1 / 82.2 秒 |
| QEMU RSS 采样峰值合计 | 5.069 GiB | 9.583 GiB |
| 运行总墙钟（含后处理报错） | 1606 秒 | 1952 秒 |

两次均用同一 `gpt-6-astra`、字节相同的角色指令和 Fixture、40 次/角色桌面调用上限、1200 秒/角色时限、同一 Oracle。桌面调用上限未触及，实际先撞到时间上限。运行总墙钟包含不同的 Guest setup 和后处理耗时，不能解释为桌面拓扑造成的任务效率差；QEMU CPU 采样 Shared 约 11,150 秒、Isolated 两进程合计约 5,681 秒，但两边模型/GUI 活动不同，亦不能直接当成隔离节省 CPU 的结论。Isolated 的两 Guest 内存峰值约为 Shared 的 1.9 倍。

两次正式模型运行均已从真实 Guest 回收文件、生成 Oracle，并由评分侧对回收产物独立复评；没有任何条件取得成功。Shared 在重开时被模型遗留的 `Save Document?` 阻塞；Isolated 在重开 A 文件时 Guest shell 3 次重试失败。两次在此后跳过了 reset，finally 均按各自 run_id 精确删除了自己的容器；这是后处理生命周期未通过，不改变已回收文件的任务评分。此前 scripted Shared/Isolated 正控均完成了文件重开和 reset。后处理代码现已改为在模型运行遇到重开错误时保留截图/错误并继续尝试 reset，离线 181 项测试通过；**该补丁尚无新的真实模型运行验证**。

原始证据保存在各自的 `runs/<run_id>/`：`actor_runs/A/A` 与 `actor_runs/B/B` 下有真实截图、逐步动作和完整模型会话；`artifacts/` 有回收的 ODS/ODP，`oracle.json` 是评分，`model_metrics.json` 是时间/token/资源汇总。Shared 的 `focus_event_shared_001.json`、`focus_event_shared_002.json` 指向干扰截图，`collaboration/events.jsonl` 记录消息。Isolated 的 `workspace_versions/events.jsonl`、`current.json` 和 `workspace_sync_result.json` 记录 ownership、revision、目标 Guest 字节回读；两次 `audit_decision.json` 均明确区分模型任务评分与后处理错误。Actor 环境没有 Gold/Oracle，密钥没有进入这些记录。

## 与原版比较及后续建议

原版是三页和更长的调和链；Lite 为两项 Calc 核验加一页 PPT 的三处业务修订与来源行。原版 Shared scripted 正控有 30 个 GUI 动作，Lite 为 22 个，约减少 27%；但同一 TCG 环境下完整 Guest 启动、重开与 reset 占大头，脚本总墙钟时间没有同比下降。Lite 完整模型执行在 20 分钟预算内仍失败：A 的证据填写/保存和 B 的跨文件 GUI 打开显著消耗时间。它保留真实信息依赖，并在 Shared 中捕获了可复核的焦点/编辑状态干扰；但本组 **0/1 对 0/1** 不支持隔离提高成功率，也不能估计成功率差异。

建议把“只保留必要协作链、版本化且独立评分”的设计原则用于后续候选题，但先别照搬 Lite v1 的界面步骤或据此扩展六题。下一版若要降低无关 GUI 阻力，应另建版本，针对 Open 对话框、Findings 可编辑性及时间预算作拓扑对称的预注册修改，重新完成两条件正负控后再实验。此轮按用户要求停止在首题，不修改另外六题，也不为刷成功率重跑原版或 Lite v1。
