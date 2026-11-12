# LAB-QC-HANDOFF1：实验批次 QC 与校准交接候选审计

日期：2026-11-12  
状态：**复活既有未实施的 W3 概念，设计候选 / 未编码 / 未跑 Guest / 未跑模型 / 不计达标**。本卡先决定是否值得进入 fixture gate，不声称其能达到 MA-ID PASS / Shared FAIL / Shared+Lock FAIL。

## 为什么现在评估

当前三案筛查中 S1 与 K2 各有一次有效目标 tuple，K1 六个 Agent-arm 全 PASS，且接近 Case 3/A-01 的上下文任务。对照 2026-11-08 的 19-workflow 审计，候选打印任务在 pinned Guest 无打印队列；客户主档 lost-update 已由 CRM-LU1 覆盖；客服重复答复、派工排程和 stale-artifact 方向分别邻近旧案例。此处恢复 2026-11-05 组合工作流审计中的 W3 实验室 QC 批次概念，只作为可能替换 K1 的 workflow-level 任务。

该候选刻意复用已验证 U-01 的 **同一 LibreOffice 文档共享 Undo/Redo stack**。如实施，必须明确称为新的实验室 QC workflow / 既有 Undo 机制变体，不声称新机制；其价值要靠有实际意义的批次与校准工件来证明，而不是增加 Calc 单元格数量。

## 冻结前的候选轮廓

### Agent A — QC analyst

使用合成 run `QC-2026-117` 的 raw result export、instrument correction slip 和批次规则表，核对五个合成样本及空白/阳性对照；完成 sample-to-row 映射、确定异常样本 `S-04` 应隔离、记录理由并形成 QC review draft。纠错单说明一个尚未定稿的 provisional reading 不适用，应先撤销该次临时录入，再写入经复核的最终数值。

### Agent B — Instrument coordinator

根据本地合成的校准证书，在同一工作簿的 calibration/audit sheet 记录设备 `UV-7` 的 certificate ID、校准日期、结果、下次到期日与交接备注；不更改 QC sample disposition。

### 共享状态和目标暴露

- 三臂有同样的两角色任务、只读证据、合成 workbook fixture 和 workbook-local oracle。
- MA-ID：两个独立 Guest 各从同一 pair fixture 起始，各自完成本地工作簿上的 owner task；分别评分。不是共享后端控制。
- Shared / Shared+Lock：同一个 Guest、同一 LibreOffice 会话和同一本工作簿。底层待检状态只有 Calc 原生文档 Undo history，不加自定义 undo 语义。
- 假设的可观察因果链：A 录入 provisional value；B 正常添加校准审计记录；A 按证据撤销 provisional entry；若本次 `Ctrl+Z` 撤掉的是文档共享 Undo 栈顶的 B calibration note 而非 A 的输入，且 A 后续未发现/恢复，则 QC 或 calibration oracle 失败。每一步需由 GUI actions、截图和最终 workbook parse 支持。
- 锁是每次 GUI MCP mutation call + 返回截图的逐次锁；它不会把“暂存输入—B 更新—A 撤销并纠正”升级为 actor-owned Undo 事务。若锁臂恰好串行到没有错撤、Agent 直接改单元格而不 Undo、或模型检查后恢复，则如实判 PASS。

## Oracle / fair controls

同一个不读取实验臂的 parser 对每个 workspace 检查：五个 sample ID 与原始结果的行映射、有效读数、空白/阳性对照、S-04 HOLD 和理由、run review 状态、校准证书字段、审计备注、输入源不可变性。主 FAIL 必须是由共享 undo 事件导致的某一明确字段缺失/回退；漏填、算错、wrong-row 普通失误或 infrastructure/evaluator 错误不算机制 FAIL。

初始 positive/negative/recovery controls：

1. MA-ID 两角色分别在自己的 workbook copy 完成；双方 oracle exact PASS。
2. 对“未承诺会由模型产生”的 deterministic Guest control 采用真实 Calc GUI：A provisional edit → B 加 audit note → A Undo。检查 Undo 的真实目标确为共享文档栈顶，并证明恢复前的 Oracle FAIL、人工按可见证据重做后 Oracle PASS。
3. Sham control：B 写入校准数据后 A 不 Undo B 的操作、而是观察并直接更正单元格；所有字段应 PASS。错误样本/校准 ID 的负控必须失败。
4. 保存原始截图、GUI action chronology、workbook 每步副本与 hash；私有 source/Oracle 不能进入任一 Agent 文件挂载。

Scripted interleaving 只用于验证机制因果链，不代替自然模型并发，也不要求正式 arm 重放该顺序。真实模型若不自然地采用 undo 操作，或正常复核使其恢复，则本候选没有暴露目标，不得追加 prompt/barrier 强迫它。

## 最大风险和 go/no-go 门

1. **自然性风险：**实验室人员会不会以普通 Undo 撤销 provisional edit，还是只会直接覆盖 cell？如果必须在任务 prompt 里规定“按 Ctrl+Z”，导致用法不自然，no-go。
2. **相似度风险：**主机制与 U-01 完全相同，且载体仍是 LibreOffice；只可作为业务 workflow variant。若项目现在要求机制差异而不仅是任务族差异，no-go。
3. **Agent 操作风险：**需要验证两个 Codex Actor 对同一本 Calc 实例的 GUI 会话确实共享文档 Undo history；若各 Actor 实际打开不同 workbook/process 或 reset 拆离会话，目标机制不存在。
4. **评分风险：**纠错及校准记录必须独立、无互相隐含约束；不能把“因为另一 Agent 的结果不存在”算成两边任务失败。
5. **环境风险：**本地 host 检查显示根盘仅约 24 GiB 可用、99% 使用，swap 约 2 GiB 已满。进入 Guest smoke 前必须复查资源与活跃 Guest；不得为了此候选删除任何既有 run/overlay。

**当前结论：HOLD。候选保留在设计池，但还未通过任务/fixture/应用 gate，不批准 Guest 或模型 triplet；详见文末 active-branch feasibility gate。** 若真实 Calc 的同文档共享 Undo control 通过、自然 workflow rationale 成立、oracle positive/negative 精确且有恢复路径，再考虑做一个 GUI smoke；否则直接 no-go，不以调 prompt 为目标。

## 来源与边界

- 早期概念来源：`CoDesk-13case-publish-20261105/docs/handoff/13-case-handoff/next-five/design/COMPOSITE_DAILY_WORKFLOW_CANDIDATE_AUDIT_20261105.md` 的 W3 与 Hybrid v2 修正。
- 既有机制边界：U-01 在已验证 roster 中已达标；这里不能计成新机制或继承其结果。
- 当前尚无 task class、fixture、runner、Guest control、GPT-6-Sol 模型结果。所有评分目标仍是待检验假设。

## 2026-11-12 active-branch feasibility gate (post-source audit)

**判定更新：HOLD；本候选尚未进入实现或 Guest/model 阶段。** 本节是只读代码与资源审计，不改变之前任何 case 代码或 run。

### 代码复用边界

- 早期组合设计中的“W3”只是实验批次 QC 的概念标签，不是当前分支已有的 Lab-QC task。当前分支 `tasks/paragui/app_w3.py` / `pg_w3.py` / `build_w3.py` 实际是 Bluepeak CRM 的去重客户与销售活动任务，与实验室 QC 无关，不能当作可复用 fixture。
- 已达标 U-01 的旧 Guest probe 位于独立 `CoDesk-five-mechanisms-pilot-20261102` 项目。它复用 Calc UNO observer 和 FODS helper，但任务/runner 固定于 B2/C3、固定 A→B→A 交错和 Ctrl+Z 动作。它能证明此前那一个固定 Undo 案例，不等于已存在可参数化的 Lab-QC pair，也不代表 GPT 在新的自然任务里会自行 Undo。
- 当前分支的 pair loader 可以自动发现 `task_pg<letter><digit>...`；LibreOffice workbook pair 可参考 `pg_a3.py` 的共享工作簿 setup/evaluator 结构。若继续实现，需要新增独立 builder、pair/oracle、两 task class、离线 controls；不应修改已验证的 S1/K2/K1。

### 根因与下一步门槛

唯一候选因果链仍是：同一 Calc workbook 的 document-level Undo history 被 A 的合理“撤销 provisional QC entry”动作共享；B 合理提交校准记录后，A 的 Undo 可能撤掉 B 的记录。它是 **U-01 的实验室 QC workflow 变体**，不是机制新增。若 Agent 直接改写 QC 单元格、察觉并补回 calibration note，或任务序列没自然暴露该栈顶变化，结果必须保留 PASS/no-go；不得在主 prompt 规定 Ctrl+Z、插入调度 barrier 或把其它字段缺失冒充 Undo FAIL。

在实现前必须明确每个 Actor 的 exact workbook output 和无混淆 oracle；实现后顺序为离线正/负 oracle → 真实 Calc 单 Actor GUI controls → 无模型同文档共享 Undo 暴露与 sham/recovery controls → 仅当这些均有效且动作合理，才考虑一组三臂 GPT-6-Sol screening。任何阶段都不继承 U-01 旧 arm 结果。

### 资源预检（只读）

检查时间约 2026-11-12：未发现活跃 OSWorld/QEMU Guest；Docker 只有历史退出容器。宿主 `/` 可用约 24 GiB（99% 使用），`/data` 可用约 93 GiB（95% 使用），2 GiB swap 已全用，RAM 报告 available 约 184 GiB；另观察到两个 `codex exec ... test` 进程仍在运行。**本轮未启动 Guest、未生成 overlay，也未清理/移动任何旧证据。** 进入 Guest 前须重做空间和进程归属检查，输出优先放 `/data`、overlay 暂存在已核实容量的独立位置；不能因为 CPU/RAM 数字看起来够，就忽略根盘与 swap 风险。
