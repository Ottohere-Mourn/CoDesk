# CDD-TTR-001 实现与 Smoke 阶段报告

## 状态摘要

本轮已交付一个可离线运行的合成售后 Case：固定工单、订单、证据与政策；浏览器 GUI 表单；Review 校验；幂等、事务化退款；工单关闭和恢复；隐藏状态 Oracle；数据重置；Single / MA-ID / MA-SD 条件配置；以及调用现有 Data-to-Deck 消息/附件协议的接入点。

**离线实现与回归：PASS。真实 Guest：BLOCKED_RESOURCE，未启动。真实模型：未运行。** 因此本报告不声称真实 GUI、Agent 或完整双桌面对照已经验证。

## 设计修订与实现结构

唯一整合后的任务卡为 [`TASK_CARD_ZH.md`](TASK_CARD_ZH.md)。旧任务草案和风险稿保持原样。

- `spec.py`、`instance_schema.json`：固定合成事实、金标准、A/B/S 指令和实例 schema。
- `database.py`：fixture、角色业务规则、Review 内容哈希/订单 revision 校验、退款事务、append-only audit log。
- `webapp.py`：本地售后 GUI，含工单队列、订单/证据/政策、Case Review、退款、工单处置和审计历史页面。
- `oracle.py`：独立读取隐藏基线与数据库状态，不采信前端成功提示。
- `runner.py`：`prepare / plan / configure / serve / collab-serve / evaluate / reset / guest-smoke` 独立入口。
- `integration.py`：复用 Data-to-Deck 的 `send_message/read_messages` 与附件协议，并把 actor 身份绑定到现有 CodexHarness MCP 配置；没有新建 planner/harness。
- `guest_smoke.py`：单 Guest、有界 scripted GUI smoke；会保留本轮 Guest、GUI动作、截图、应用/后端日志和评分证据，且仅按精确 run ownership 清理其运行容器。
- `tests/test_ticket_to_resolution.py`：离线状态机、Oracle、协议、HTTP readiness 和资源门槛测试。

### 交易与评分语义

- 金标准：目标行 `O-2048-L2` 的 `$80.00` 商品价加 `$8.00` 行税，共 `$88.00`；monitor 和 `$15.00` 运费不退款。订单余额应为 `$147.00`，状态 `PARTIALLY_REFUNDED`；工单最终 `RESOLVED`，解决码 `PARTIAL_REFUND_DAMAGED_ITEM`。
- Review 包含订单 revision、目标行、证据、政策、各分项金额、总额、理由、作者、版本和内容 SHA-256。退款时重新核验当前订单 revision、Review 内容与退款请求逐字段一致。
- 退款、退款记录、余额扣减、订单 revision 和工单 `REFUND_PENDING` 在单个 SQLite 事务中提交。幂等重放返回原交易；同商品行不能重复成功退款。工单关闭失败可在退款后恢复，不重复退款。
- 成功、拒绝、幂等重试、消息、页面访问、Review 修订、退款及工单处置分别留痕。业务终态、Review 实际引用、消息反馈、版本修订是不同指标；仅引用 Review 不算已证明双向协作。

### 条件与共享状态边界

`single_agent` 使用一个 S 身份和一张桌面，预算等于双角色预算之和。`collaborative_isolated` 使用 A/B 两个 Guest；`collaborative_shared` 使用一个 Guest 的实时桌面。所有条件均为每个 episode 一个相同版本、相同初始快照、run 专属的 backend；MA-ID 不拆分数据库。A/B 的浏览器身份、profile、权限、消息能力一致。桌面焦点、键鼠路由与窗口共享只存在于 MA-SD；route/tab/session 仍按角色隔离。窗口/动作采样不能证明原子因果，日志对此标注。

## 离线验证

**新 Case 定向测试：23 passed。整个仓库测试：94 passed。** Python 模块编译及 `git diff --check` 通过。测试由离线测试代码调用数据库/API；这不是 Agent GUI 操作证据。

定向覆盖：

- 正例 `$88.00` 正确退款、工单解决及完整交叉引用。
- 错误金额 `$80 / $95 / $235`、错商品、重复退款、缺失/过期/篡改/过时 Review、金额与 Review 不匹配、错误解决码/交易引用均被拒绝或被 Oracle 判失败。
- 退款已成功但工单未关闭时，Oracle 判未完成；随后单独完成关闭，不产生第二笔退款。
- 幂等重试、非目标客户/工单/订单/证据/政策完整性、追加日志不可更新/删除、reset 基线恢复。
- Review 实际引用、消息与附件反馈分别计量；Single 正例和三条件 backend 拓扑一致性。
- HTTP 应用 readiness、B 可通过 GUI route 读取 Review、角色绑定和已有消息/附件协议。
- 资源门槛失败不会启动 Guest，也不会创建 overlay。

复跑命令：

```bash
python -m py_compile oscombo/collab/ticket_to_resolution/*.py
python -m pytest -q tests/test_ticket_to_resolution.py
python -m pytest -q
```

## Guest Smoke Gate

预检命令已对一个新 run 实际执行；没有调用模型：

```bash
python -m oscombo.collab.ticket_to_resolution guest-smoke \
  --run-root runs/ticket_to_resolution/cdd-ttr-20261022-run01 \
  --run-id cdd-ttr-20261022-run01 \
  --base-image /mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2 \
  --provider runs/data_to_deck_guest_smoke/cdd-guest-smoke-20261020T144015Z/osworld-provider \
  --runtime-image swcub/osworld-v2.1-qemu-runtime:local \
  --condition collaborative_shared
```

`guest_smoke_report.json` 为 `BLOCKED_RESOURCE`：

| Gate | 结果 | 说明 |
|---|---|---|
| Gate 1：Guest 启动、浏览器/本地服务 readiness | **BLOCKED_RESOURCE** | 启动前资源保护条件不满足，没有启动 Guest |
| Gate 2：真实 GUI Review → 退款 → 关闭 → Oracle → reset | **BLOCKED_DEPENDS_GATE_1** | 未执行 GUI 操作 |
| Gate 3：两个独立 Guest 共用同一 backend | **NOT_RUN_RESOURCE_BLOCK** | 未用一个 Guest 冒充 MA-ID |

该次采样：80 逻辑 CPU；load 1/5/15 为 `155.66 / 135.24 / 155.94`；CPU PSI some avg10 `32.4%`；MemAvailable `171,750,686,720` bytes；SwapFree `184,320` bytes；当前用户无 `/dev/kvm` 读写权限。Provider 支持 TCG，因此 KVM 不可用本身不是绝对阻塞；但 TCG 会显著增加 CPU 负荷，且 load/PSI 远超预先设置的启动门槛。

基镜像、隔离 provider、Docker runtime image 均可读/可用。runtime 中 Guest 数为 0、QEMU 进程数为 0。此次预检未创建容器、Guest 或 overlay；旧 provider 的既有未提交补丁未被修改。Fixture、配置和 run ownership 证据保存在：

- `runs/ticket_to_resolution/cdd-ttr-20261022-run01/guest_resource_preflight.json`
- `runs/ticket_to_resolution/cdd-ttr-20261022-run01/guest_smoke_report.json`
- `runs/ticket_to_resolution/cdd-ttr-20261022-run01/ownership.json`
- `runs/ticket_to_resolution/cdd-ttr-20261022-run01/resource_actions.jsonl`
- 数据库 `db/case.sqlite3`、隐藏基线 `oracle/fixture_manifest.json`

上述目录含凭据和隐藏评分基线，不要公开或拷贝到报告附件。没有截图、GUI action trace、Guest provenance 或 GUI 评分结果，因为 Guest 未启动。

## 未验证与限制

- 本地 HTTP readiness 和 scripted/Oracle 组件通过离线测试；尚未在 Guest 中验证 LibreOffice/Chrome/窗口行为。
- `guest_smoke.py` 的键盘焦点流程、双 Chrome profile 窗口启动、Guest 到 host bridge URL 连通性、登录后表单序列和最终截图都尚未实机验证。首次有效 Guest 运行需要逐项检查这些证据；不能据本轮离线测试宣称 scripted GUI smoke 已通过。
- 当前可执行 Guest smoke 入口覆盖一个 `collaborative_shared` 单 Guest GUI 流程。MA-ID 的两个 Guest 同连 backend 的运行编排尚未实现/验证；只有配置计划与拓扑一致性有离线检查。
- Single-Agent 目前有合并职责指令、预算和配置，尚无独立真实 Agent episode；离线正例不是 Single-Agent 成功证据。
- 没有跑 Qwen 或付费模型；没有测自然 interference、双 Agent 协作真实性、恢复率或运行成本。
- 浏览器 profile 隔离在共享 Guest 内的实际执行身份与窗口切换日志待确认。共享 desktop 的焦点读数与输入事件非原子，不能单凭窗口切换归因失败。

## 证据分类

- **PASS — OFFLINE**：23 个 Case 测试、94 个仓库测试、Python 编译、diff 检查。
- **BLOCKED — GUEST**：Gate 1 资源门槛；Guest 尚未启动。
- **NOT RUN — MODEL**：无模型调用。
- **DESIGN/PLAN ONLY — MA-ID**：同 backend 的双 Guest 拓扑在配置中定义，但真实双 Guest 连接尚未执行。

## 后续进入真实模型 Solo 的准入条件

按顺序先恢复资源，并完成单 Guest Gate 1、Gate 2：确认本地应用在 Guest 可达，A/B 各自独立登录/profile，真实 GUI 轨迹能完成正确 Review、退款、关闭，数据库独立 Oracle PASS，reset PASS，且截图、动作、server event、audit 和 ownership provenance 齐全。另需完成 MA-ID 两 Guest 同 backend Gate，才能声称该对照可运行。之后才用模型做一个 Solo solvability episode；若 Solo 任务/GUI grounding 不通过，保留失败并停止扩展。任何模型成功都不得替代 Guest smoke，也不得从 scripted 路径推断模型表现。
