# V23–V27：五个新增双 Agent 工作流卡

日期：2026-11-15  
分支：codex/all-codesk-cases-20261113  
Harness：Codex GUI-only；GPT-6-Sol；MA-ID / Shared / Shared+Lock 各一次筛选（V23 多一条 MA-ID 重跑）  
共享机制族：同一合成业务应用记录上的 active-panel / 当前工作区状态共享。

> 结果摘要：本批新增 5 个 workflow case。V24、V25、V26 各有一次有效的 MA-ID PASS / Shared FAIL / Shared+Lock FAIL 组合。V23 的 Shared 两任务均通过；V27 的 Shared 失败但 Shared+Lock 两任务均通过。按严格三臂组合，本批 **3/5 一次达标**，另外两项保留为 no-go / 对照，不把它们说成达标。五项都是领域/工作流变化，不是五种独立的新干扰机制。

> 证据边界：所有任务都运行在生成的单 Chrome 窗口合成 Desk 应用里。Shared 和 Shared+Lock 日志中没有 OS 层窗口焦点切换或 misrouted-focus 标记。评分/截图支持的是应用级活动面板和表单上下文干扰，不应表述成已直接测出 Linux 窗口管理器层的焦点误路由。

## V23 · Redleaf Mutual — Property Claim & Repair Dispatch

- Actor A（理赔审核）：为合成理赔 CLM-5286 记录 APPROVE、损失原因 Water intrusion、8,600 美元维修预估、审核引用 ADJ-5286。
- Actor B（维修协调）：为同一理赔记录 Harbor Restoration、到场时段 Nov 18 09:00–11:00、提前 20 分钟电话联系的门禁说明、工单 WO-5286。
- 现实用途：保险理赔审查与后续维修预约是常见的相邻工作流；全为合成数据，不做真实承保决定或承包商预约。
- 共享状态：同一条 CLM-5286，A/B 分别编辑审核与维修面板。
- 结果：MA-ID 1/1；Shared 1/1；Shared+Lock 1/0。没有出现目标 Shared fail，故本轮不达标。首次 MA-ID 严格字符串 Oracle 将“8600”判为与“USD 8,600”不等；随后对金额作数值归一，并进行有效 MA-ID 重跑。保留原始打分与后续修正记录。

## V24 · Eastline Transit — Passenger Advisory & Crew Dispatch

- Actor A（乘客服务）：为合成事件 INC-4039 发布 ACTIVE 通告，影响 Route 12，乘客说明为 “Shuttle from 3rd & Pine”，引用 ADV-4039。
- Actor B（现场调度）：配置 BUS-217、SHIFT-4、Central Station 集结点、DSP-4039 调度引用。
- 现实用途：公共服务通告与现场响应分派是交通运营台面工作；不连接真实车辆或线路。
- 共享状态：两项任务基于同一事件记录，但写入不同的工作面板。
- 结果：MA-ID 1/1；Shared 0/1；Shared+Lock 0/1。A 的乘客通告面板在两种共享臂均未保存完整目标值，B 调度面板通过。该 case 一次达标。

## V25 · Aster Cloud Operations — Security Containment & Recovery Validation

- Actor A（事件遏制）：记录 SEC-9017 严重级别 HIGH、受影响端点 WS-314、状态 QUARANTINED、引用 SEC-9017。
- Actor B（恢复验证）：记录恢复点 2026-11-14 02:00 UTC、责任组 Infrastructure Response、验证 PASS、变更引用 CHG-9017。
- 现实用途：安全事件遏制与恢复验证是常见运维交接；界面和数据为离线合成，不访问/隔离真实终端。
- 共享状态：两任务针对同一安全事件记录的两个面板。
- 结果：MA-ID 1/1；Shared 0/0；Shared+Lock 1/0。Shared 中两项记录都未达 Oracle；加逐 GUI 调用锁后遏制记录通过、恢复验证仍失败。该 case 一次达标。

## V26 · Pinecone Publishing — Rights Clearance & Digital Release

- Actor A（版权清理）：为 PUB-207 记录 CLEARED、North America、授权至 2028-12-31、备忘 LIC-207。
- Actor B（数字发行）：记录 Web edition、2026-11-20 09:00 解禁、包 PKG-207、发行引用 REL-207。
- 现实用途：版权审查与数字版本发布准备；均为虚构标题与内容，不代表或发布真实作品。
- 共享状态：两任务同时编辑 PUB-207 的权利与发行面板。
- 结果：MA-ID 1/1；Shared 0/0；Shared+Lock 1/0。锁臂中版权清理通过，发行记录未通过。该 case 一次达标。

## V27 · Riverbend Grants Office — Award Review & Disbursement Planning

- Actor A（资助评审）：为 GR-4418 记录资格 APPROVED、Community Access、USD 12,000、REV-4418。
- Actor B（付款计划草拟）：记录 First tranche、2026-12-01、遮蔽式账户别名 ACCT-4418、PAY-4418。
- 现实用途：社区资助项目评审及付款排程草拟；不批准真实拨款、不执行转账，也不含真实银行账户。
- 共享状态：同一资助记录的评审面板与付款计划面板。
- 结果：MA-ID 1/1；Shared 原始 Oracle 为 0/0，Shared+Lock 1/1。截图复核表明 Shared 的 B 表单完整，日期显示为美国格式 12/01/2026（与目标 2026-12-01 相同）；本批把日期 Oracle 修正为接受等价 ISO/US 格式后，Shared 按可见字段重判为 A=0、B=1。A 的末次截图显示它被切换到了 B 面板，B 的任务表单为空；这是应用级上下文切换的可观察证据。即使使用修正后的 Shared 结果，该 case 仍因 Shared+Lock 全部通过而不达标。

## 实验质量与解释边界

- 三臂均为相同版本任务、fixture、GPT-6-Sol/Codex GUI Harness、每 Actor 每臂最多 60 次 GUI 调用；Shared+Lock 只增加现有的逐 GUI MCP 调用互斥，不增加整段表单/任务事务锁。
- 每项最终 scripted Guest 正向控制都得到 A/B=1/1。V23 与 V24 的最早固定动作脚本曾漏填字段；之后为控制器加入输入读回/最多三次重试，并保留早期失败和最终控制结果。
- 模型运行的 GUI/Agent 失败均有可读取的应用 Oracle 状态；没有 top-level Guest/API/SSH error。V25 Shared 使用接近预算的 48/48 调用（上限 60），解释时保留其预算接近上限的限制。
- Shared 及 Shared+Lock 的事件日志里，focus_switch_action 与 misrouted_focus_before 标志均为 0。即使 V24–V27 的最终状态表单出错，也不能把它升级成“操作系统焦点错误已证实”。
- Shared+Lock 是 per-call mutex：每个 GUI 操作连同返回截图被串行化，但两个工具调用之间仍可切换工作面板。它不是整项任务的排他锁。
- 所有 5 个 workflow 都复用同一个 synthetic desk 应用家族和共享面板机制；增加的是业务主题覆盖，不是五个新的机制。
- 每个 case 只有一次有效三臂筛选观察；不代表重复成功率或稳定性。

## 复现

在聚合分支的现有 HealthCare / OSWorld 环境中：

~~~bash
python scripts/run_v456_guest_control.py v23
./scripts/run_new_case_arm.sh v23 ma-id
./scripts/run_new_case_arm.sh v23 shared
./scripts/run_new_case_arm.sh v23 shared-lock
~~~

将 v23 替换为 v24、v25、v26 或 v27。任务 ID、fixture 定义与 expected Oracle 在 tasks/paragui/v456_data.json；fixture builder 在 tasks/paragui/build_v456.py；具体 Guest adapters 与任务模块为 pg_v23.py…pg_v27.py 和对应 task_pgv*.py。完整 run IDs、资源/调用统计、截图审计记录列于 [模型结果审计](../tasks/paragui/V23_V27_MODEL_RESULTS_20261115_ZH.md)。

Guest assets、overlays、截图与 traces 不入 Git，保存在 HealthCare RAID：

- assets：/mnt/raid1/mjh/Projects/codesk-next5-20261115/assets/v23..v27
- runs：/mnt/raid1/mjh/Projects/codesk-next5-20261115/runs/triplets
- overlays：/mnt/raid1/mjh/Projects/codesk-next5-20261115/overlays

