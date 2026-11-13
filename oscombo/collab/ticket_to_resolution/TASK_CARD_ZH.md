# CDD-TTR-001：Ticket-to-Resolution

版本：`0.1.0`<br>
状态：首个离线实现；Guest Gate 结果见 `IMPLEMENTATION_REPORT_ZH.md`。本任务是本地合成售后系统，不连接真实客户、订单或支付服务。

## 研究问题

在同一实时桌面上，独立 GUI Agent 能否通过核验、交易和工单关闭完成一个可审计售后结果？相对独立桌面，实时桌面状态是否增加可观测的干扰和恢复成本？本任务将 GUI 控制面与业务 backend 分开：三个条件的每个 episode 都使用一个同版本、同初始快照、由本 episode 独占的业务服务和数据库；MA-ID 只拆分桌面，不拆分 backend。

本 Case 不预设 MA-SD 必然失败。只有窗口/输入/页面上下文与服务端动作存在证据链时才归因于桌面干扰；纯业务判断错误、通信错误、backend 拒绝和没有 exposure 的失败分别统计。

## 固定 fixture 与 Gold Answer

`T-1042` 关联已付款订单 `O-2048`（客户 `C-551`）。订单有一台正常的 24-inch monitor（商品 `$120.00`、行税 `$12.00`）和一个有送达损坏证据的 USB-C dock（`O-2048-L2`，商品 `$80.00`、行税 `$8.00`）；运费 `$15.00`。订单总额 `$235.00`，送达后第 1 天录入损坏证据，政策 `POLICY-RET-4` 允许 30 天内退受影响商品和对应行税，不退部分退款的运费，不退未受影响商品。损坏证据 ID 为 `DELIVERY-EV-77`。

正确结果：dock 商品 `$80.00` + 行税 `$8.00` = **`$88.00`**；monitor 与运费不退；订单 `PARTIALLY_REFUNDED`，余额 `$147.00`；工单 `RESOLVED`，解决码 `PARTIAL_REFUND_DAMAGED_ITEM`，工单引用成功退款交易 ID。初始状态无 Review、无退款、工单 `OPEN`、订单 `PAID` revision 1。Fixture 还包含两个无关客户、订单与工单作为完整性负控。所有身份和数据均为合成内容。

Fixture schema 为 `instance_schema.json`。初始化结果 manifest 保存隐藏基线快照与 SHA-256；运行中演员只能经 Web GUI 和协作消息接口交互，不能读取 DB、manifest、凭据或 Oracle 文件。

## 角色与权限

两个协作角色拥有相同原始事实读取权限，使用各自运行凭据和各自浏览器 profile/session：

- **A — Order Verifier**：检查工单、订单行、客户陈述、送达证据与政策；形成带内容哈希、保存时间、版本和订单 revision 的 Case Review。不得退款或关闭工单。
- **B — Support Processor**：独立查看同一原始资料和 A 的 Review，核对 Review 的行、证据、政策、金额和状态版本；按合规 Review 退款，再完成工单处置。不得改写订单行或无关业务记录。
- **S — Single-Agent**：获得 A+B 合并职责，使用同一初始快照、一个桌面、总预算等于两个角色预算之和。可独立保存 Review、退款和关闭工单。

完整起始指令是 `spec.py` 中的 `ACTOR_A_INSTRUCTION`、`ACTOR_B_INSTRUCTION`、`SINGLE_AGENT_INSTRUCTION`。指令允许按需使用 `send_message/read_messages` 和附件；不指定消息数量、交接时间或窗口抢占。B 有权查看所有事实，Review 是应用的公开审计前置要求，并不证明实质协作已经发生。

## GUI、浏览器会话与共享状态

应用以本机 Web 服务运行。A/B 使用分开的 Chrome profile 和独立登录 session；两人身份、权限与服务端行为在 MA-ID 和 MA-SD 中一致。各自页面 route/tab 状态分别属于浏览器 profile；二者并不共享浏览器 session 或全局 selected-order 状态。MA-SD 共用的是同一 Guest 的桌面显示、窗口层级、活动窗口、键鼠输入路由和 OS clipboard；MA-ID 有两个 Guest，二者仍连接到同一个 episode backend 和消息服务。应用记录 actor、route、ticket/order/review/refund context、请求结果和 DB revision。动作前后窗口采样来自 OSWorld 可用观测；与输入提交非原子时一律标为相关性证据，不声称精确因果。

不强制同时编辑同一窗口，不加入故意抢焦点、全局订单选择器或模态弹窗。没有实际 exposure 时不得记作 observed interference。

## 条件定义与公平性

| 条件 | 桌面 | Browser profile/session | Backend |
|---|---|---|---|
| `single_agent` | 一个桌面、S | S 单一 session | 一个 run-scoped backend/DB |
| `collaborative_isolated` | A、B 各一 Guest | A/B 各自独立 profile 与凭据 | 两 Guest 指向同一个 run-scoped backend/DB |
| `collaborative_shared` | A、B 共用一个 Guest 的实时桌面 | 同一 Guest 中 A/B 各自独立 profile、窗口与凭据 | 同一类型、版本、快照的一个 run-scoped backend/DB |

各条件保持任务、规则、初始数据、读事实权限、每 Actor 模型/提示/消息能力、评分语义不变。Single-Agent 的总步骤/token 预算为两个角色各自预算之和；不得把两套独立数据库的 MA-ID 与共享数据库 MA-SD 做因果比较。条件间使用独立 run ID 与等哈希 fixture，不跨条件复用被修改的 DB。

## 可审计协作与事务规则

Review 必须记录 ticket/order、订单 revision、决定、商品行、证据、政策、商品金额、行税、运费金额、总退款、理由、作者、保存时间、版本及内容 SHA-256。B 可以在正常 GUI 中打开并阅读 Review。业务 outcome、Review 被实际引用、消息/附件反馈、Review 修订分别输出；引用 Review 不能单独作为双向协作证据。

退款 API/GUI 使用固定幂等键和由 run ID 确定的 transaction ID。同一幂等键、同一请求只返回原交易，不重复扣减；同一商品行不得有第二笔成功退款。退款前验证 Review 最新、哈希完整、仍对应当前订单 revision、证据/政策/商品对象一致，并且 request 的各金额与 Review 完全一致。退款插入、订单余额/revision 更新和工单 `REFUND_PENDING` 标记在一个 SQLite 事务内提交；之后可以重试工单关闭，而不重复退款。所有接受、拒绝、幂等重试、工单修复动作写入 append-only audit log。

## Oracle 与判分

独立 Oracle 从隐藏 manifest 基线和数据库真实状态评分，不相信界面成功 banner。主要二元指标：

1. `review_pass`：存在完整、未篡改、版本最新且基于原订单 revision 的正确 Review。
2. `refund_pass`：恰好一笔 `$88.00` 成功退款，line/item/tax/shipping 正确，处理角色正确。
3. `ticket_state_pass`：目标工单 `RESOLVED`、解决码和 transaction ID 正确，备注非空。
4. `cross_reference_pass`：refund 指向 Review、订单和 ticket；Review 事件先于退款，退款先于解决事件。
5. `protected_state_pass`：非目标 customer/order/ticket、目标订单行、政策和证据与初始快照一致。
6. `joint_business_success`：上述业务状态、引用、序列和完整性全部为真。

过程指标分列：Review 引用、消息反馈、Review 版本修订、退款拒绝/重试、窗口/route exposure、具证据的 interference、自主 recovery 与 outcome。终态成功与“发生实质双向协作”是不同结论。

## reset 与复现

每个 run 建立独立目录、SQLite fixture、隐藏 manifest、随机运行凭据、`ownership.json`、配置模板和 append-only `resource_actions.jsonl`。`reset` 仅在 case/run/path ownership 全部匹配时把当前 DB 先快照到 `pre_reset/`，再重建相同业务初始快照；不清除旧审计文件或其他资源。SQLite 初始状态哈希和 schema 固定；交易时间戳/事件 UUID 以及 run-scope transaction ID 随 run 变化，业务字段保持确定。

## 范围边界

此首个 Case 验证本地合成售后 GUI 与事务 Oracle 的可执行性。Scripted GUI smoke 只验证 UI/应用/Oracle 链路，不能算模型成功。单 Guest 顺序脚本不能冒充 MA-ID；Guest 资源不足时 Gate 3 标记 `BLOCKED_RESOURCE`。本 Case 暂不验证真实支付、真实客服系统、自然冲突成功率或强模型表现。
