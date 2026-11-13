# Data-to-Deck Collaborative Reconciliation V0.2.1

## 目标与边界

两名 GUI Agent 核验并修订一份季度销售汇报：Calc 工作簿是权威数据源，Impress 草稿是待修订产物。Agent A 负责补充可追溯分析；Agent B 负责审查并完成三页管理层汇报。两者都能读取全部原始资料，不通过隐藏真相制造协作。A 是分析 ODS 的唯一写入者，B 是汇报 ODP 的唯一写入者。Shared 条件允许直接看见对方实时 GUI，但不要求共同编辑同一个文件。

版本整合了 v0.2 Task Card 及“Reconciliation 修订”两项最终决定：保留 Sales、Costs、KPI Definitions 和基础季度汇总；将 Q2→Q3 区域利润桥、成本异常拆解及证据边界留给 A 完成；明确双方读取/查看/写入权限。旧设计文档原样保留。

## 固定资料和初始状态

`python -m oscombo.collab.data_to_deck prepare <directory>` 确定性生成：

- `quarterly_authority.ods`：`Sales`、`Costs`、`Quarterly_Summary`、`KPI_Definitions` 预填；`Reconciliation` 留空。
- `management_draft.odp`：三页草稿，含 R1/R2/R3 三处已知待发现不一致，同时含需保留的正确内容。
- `case_brief.md`：应用访问与权威来源说明。
- `fixture_manifest.json`：文件 SHA-256 和 case version。
- `instance_schema.json`：固定 case/fixture/condition/预算/输出路径的 JSON Schema；fixture manifest 与运行配置在同一结构内可校验。

金额单位是千美元。Sales 记录每季度各区域收入；Costs 记录 COGS、履约和促销费用。季度利润定义为 Revenue − COGS − Fulfillment − Promotion；Gross Margin 定义为 (Revenue − COGS) / Revenue；Operating Margin 定义为 Operating Profit / Revenue。

### A 应完成的增量分析

至少补齐 Reconciliation 表中的 Q2→Q3 收入、成本分项、总成本、营业利润变化；收入/营业利润增长率；营业利润率变化百分点；North/South/West 营业利润变化；West 收入、促销费用、营业利润变化；以及“相关性不构成因果证据”的结论。逐项带有可追溯来源标记。数值 gold answer 在 `oracle.py` 中由 fixture 数据计算；Oracle 不向 Actor 暴露。

固定关键值：Q2→Q3 收入 `+30`，COGS `+17`，履约 `+4`，促销 `+14`，总成本 `+35`，营业利润 `−5`（千美元）；营业利润率由 `98/270` 降至 `93/300`；区域营业利润变化 North `+2`、South `+4`、West `−11`；West 收入 `+15`、促销费用 `+14`、营业利润 `−11`（千美元）。数据不支持“促销活动导致利润下降”的因果结论。

### Impress 草稿中的三类不一致

| ID | 草稿问题 | 正确结果 |
|---|---|---|
| R1 数字誊录 | Slide 1 与 Slide 2 将 Q3 revenue 写为 `$310k` | 两处均改为 `$300k`，保留正确的 Q4 `$330k` |
| R2 指标口径 | Slide 2 将 Q3 Gross Margin 标为 `31%` | Gross Margin 为 `45%`；Operating Margin 才是 `31%` |
| R3 超出证据归因 | Slide 3 声称 West discount campaign 导致 Q3 利润下降 | 删除因果断言；报告可观测变化，并明确因果关系未被这些数据确立 |

Slide 3 还应包含 Q2→Q3 收入、总成本和营业利润桥接，以及 West 区域变化。其他正确文本及正确数字应保留。

## Actor 初始指令

### Actor A — Data Verifier

> 权威输入是 `quarterly_authority.ods`。检查 Sales、Costs 和已提供的季度汇总。将工作簿复制到你的输出位置，只编辑 `Reconciliation` 工作表：补充 Q2→Q3 区域营业利润桥、成本分项变化、毛利率与营业利润率区别，以及数据能否支持因果结论；每项给出可追溯的工作表/季度/区域依据。你可以读取 `management_draft.odp`，但不得编辑或保存 Impress 交付文件。将已核实分析的 ODS 或摘要通过消息/附件接口发布，并在需要时回答具体证据问题。可以分批交付；没有固定消息次数或交接时刻。不要改权威输入，不要声称数据未支持的因果关系。

### Actor B — Report Editor

> `quarterly_authority.ods` 是权威来源；`management_draft.odp` 是未完成草稿，错误没有标注。你可读取所有原始资料和工作簿，是最终 Impress 文件的唯一写入者。核验并修正草稿，保留正确内容，完成三页管理层汇报，尤其补齐 Slide 3 的 Q2→Q3 区域与成本解释。区分 Gross Margin 与 Operating Margin，不作超出数据的因果断言。你可自行核验、读取 Data Verifier 发布的分析修订，或针对不清楚的证据提问。最终汇报注明使用的分析 revision/hash。题目不规定消息次数、交接时间、GUI 碰撞或具体动作。

### Single-Agent 指令

> 独自完成整个 Reconciliation case：核验权威 Calc 工作簿、补齐 Reconciliation 表、审查并修订 Impress 草稿、保留正确内容、保存两个规定产物。使用可追溯计算，区分两种 margin，谨慎表达因果，并记录 Deck 使用的分析 revision。评测隐藏状态不可见。

## 权限与协作协议

- 三种条件都提供同一份只读初始资料、同一消息与附件 API 能力、相同评分和总预算口径。
- A 可读两份初始资料、写 A 的 ODS 输出、发送/接收消息和附件；不能写 B 的最终 ODP。
- B 可读两份初始资料、写 B 的 ODP 输出、发送/接收消息和附件；不能写 A 的 ODS 输出。
- Collaborative-Shared 中，双方还可直接查看对方 live GUI；这不增加对方文件的写权限。
- 本轮模型校准将每个角色上限设为 240 个 runner step 与最多 12,000 model tokens；协作条件每角色各有此预算。Single-Agent 全任务预算为 A/B 两个角色预算之和（480 steps / 24,000 tokens），可依次承担两类职责。初始 60-step episode 全部因 max-steps 截停；240 是用于确认可解性的诊断上限，不代表已校准的充分预算。runner step 计数包含初始 screenshot 调用。
- Message event 记录 run、时间、sender、recipient、body、attachment IDs；附件记录字节数和 SHA-256。消息服务仅绑定 loopback，按 Actor token 区分来源。评分器的 gold state 不经 API 暴露。

## 对照条件

| 条件 | Guest / 桌面 | 信息交接 | 用途 |
|---|---|---|---|
| `single_agent` | 一个 Guest、一个 Actor | 同一 Actor 可用消息/附件接口记分析 revision | 单体完成基线；总预算与两角色预算合计相同 |
| `collaborative_isolated` | 两个独立 Guest；由同一 fixture hash 初始化 | 同一消息/附件服务；A 的产物需显式传递给 B | 隔离桌面协作对照 |
| `collaborative_shared` | 一个 Guest、同一 live desktop session | 同一消息/附件服务；允许直接看对方实时 GUI | 共享桌面处理条件 |

除 Guest/desktop topology 外，任务资料、actor prompts、角色预算口径、消息/附件能力和联合 Oracle 固定。文件交接通道在 Isolated 与 Shared 一致；不以共享文件系统差异冒充桌面效应。最终实现如无法保证这一条件，应标记为实验协议偏差，不做因果比较。

## Oracle 与归因

`oracle.evaluate()` 分别报告 A、B 与 joint success：

1. A：检查 Reconciliation 的精确数值、单位和来源依据；并逐单元格保护 Sales、Costs、Quarterly_Summary、KPI_Definitions，不允许非目标内容改变。
2. B：检查三页结构、R1 两处、R2 两个指标定义、R3 因果限定、Slide 3 桥接信息，以及草稿指定正确内容保留。
3. Joint success 要求双方各自目标均通过。
4. GUI 焦点/窗口事件只用于 failure attribution，不代替最终产物评分。

Agent 分工造成的计算/沟通不一致属于协作错误。只有可追溯的焦点、窗口或输入事件与错误动作/产物相结合时，才标为 shared-desktop-attributed；仅有任务失败不足以作此归因。当前 V0 还没有完整 OSWorld action/event adapter，窗口和焦点证据在其接入前属于未验证项。

## 可运行入口

```bash
python -m oscombo.collab.data_to_deck prepare /tmp/cdd-instance
python -m oscombo.collab.data_to_deck plan single_agent --check-live
python -m oscombo.collab.data_to_deck plan collaborative_isolated
python -m oscombo.collab.data_to_deck plan collaborative_shared
python -m oscombo.collab.data_to_deck protocol-smoke --output /tmp/cdd-protocol-smoke
python -m oscombo.collab.data_to_deck evaluate \
  --authority /tmp/cdd-instance/quarterly_authority.ods \
  --analysis /tmp/cdd-output/verified_analysis.ods \
  --draft /tmp/cdd-instance/management_draft.odp \
  --deck /tmp/cdd-output/final_management_brief.odp
```

`evaluate` 退出码 0 表示联合通过，2 表示未通过。Live Guest/Agent execution 尚未接通；环境 prerequisites、Guest smoke 与 GUI 事件归因均不能由上述离线命令替代。完整环境限制见同目录 `README.md`。
