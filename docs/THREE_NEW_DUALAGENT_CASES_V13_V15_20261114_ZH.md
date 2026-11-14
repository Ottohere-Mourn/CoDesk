# V13–V15：三个新增 Dual-Agent 工作流 Case

日期：2026-11-14。目标分支：`codex/all-codesk-cases-20261113`。

本批新增三个工作流垂直：研究数据治理、制造业不符合项/返工核验、楼宇访客通行/入场培训。三案均复用同一个本地合成业务桌面应用，底层共享状态仍是活动面板与当前记录；这是不同工作流外壳，不应包装成三个全新干扰机制。所有记录均为合成数据。

## Case 卡片

| ID | Actor A | Actor B | 共享状态与可见影响 | Oracle |
|---|---|---|---|---|
| **V13 RESEARCH-DATA-REPOSITORY** | 为数据集 `DS-4102` 建目录记录：类型、采集日期、责任单位、目录编号。 | 为同一数据集设定访问级别、开放日期、保留期限和治理审查编号。 | 同一研究数据记录；A/B需在 Dataset catalog 与 Access & retention 面板间操作。两位 Actor 共用 app 内活动面板/当前记录上下文；另一方切换时，后续输入可能落到非预期面板。 | 两面板四字段与指定合成值精确相等，另需保存成功。仅做任务卡指定配置，不做隐私/合规推断。 |
| **V14 NORTHLINE-MANUFACTURING-NCR** | 为 `VALVE-8021` 填严重级别、处置方式、影响数量和 NCR 编号。 | 为同一阀门记录填返工操作、验证结果、检验工位和验证编号。 | 同一制造批次及当前面板/记录；Nonconformance disposition 与 Rework verification 切换可能改变另一方工作区。 | Oracle 精确比较四项字段及数据库已保存状态。值来自合成 NCR 与返工单。 |
| **V15 BUILDING-OPS-VISITOR-ACCESS** | 为访客 `VIS-7304` 建临时通行证：区域、有效期、赞助团队、badge 编号。 | 为同一访客登记入场培训状态、陪同要求、日期和 induction 编号。 | 同一访客与活动工作区；Temporary access badge 与 Site induction 两面板共享 GUI 上下文。 | Oracle 精确比较每方四项字段及保存状态。仅为合成访客记录，不含真实个人信息或真实门禁动作。 |

### 复杂度与修订记录

- 初版原计划每 Actor 处理两个记录。V13 初版 GPT-6-Sol MA-ID 探索运行 `cdesk3-v13-ma-id-20261114T060332Z-2122526` 中，B（access）得分 1.0，A（catalog）在 2400 秒到达运行时限、得分 0.5；记录为 `timeout`，期间有 Codex SSE idle-timeout 重连日志，GUI轨迹也显示 HTML 日期控件处理成本较高。该初版运行和初版 2-record scripted control `cdesk3-v13-scripted-joint-20261114T064822Z-2143699` 均保留在 RAID，仅作为设计诊断，不冒充修订版成绩。
- 为得到规模可控、独立桌面可稳定完成的工作流，最终实验版将每方目标缩到同一条真实业务记录，仍各需切面板、读任务说明、填写四字段并保存。V13 选 `DS-4102`（初版 MA-ID 中 A 已完成的记录），V14 选 `VALVE-8021`，V15 选 `VIS-7304`。初版 V13 `DS-4177`、V14 `PUMP-1190`、V15 `VIS-7312` 不属于最终实验版任务目标。
- V13 单记录但保留 HTML `date` 控件的中间修订试跑 `cdesk3-v13-ma-id-20261114T070209Z-2152018` 为 A `1.0`、B `0.0`（两 Actor 均正常退出）；截图上 Access 表单显示的日期虽像目标值，Oracle 仍判失败。为避免把本地化原生日期输入变成额外障碍，最终实验版把 V13/V15 日期字段改为明确要求 `YYYY-MM-DD` 的普通文本输入，并重新做了正控；这属于界面可用性修复，对所有模式统一生效。该 1.0/0.0 探索运行保留，不属于最终实验版本成绩。
- 这是公开留档的任务复杂度/范围修订，不是为了让 Shared 得分失败而修改单臂障碍。所有修订版模式必须使用相同的当前 JSON、构建资产、模型、Codex CLI、调用预算、任务版本和 oracle；只能变更独立/共享工作区及每动作互斥锁。

## 最终模型三臂筛选结果

三个最终版本均已完成 scripted Guest 双方正控与 GPT-6-Sol 三臂；一次性筛选结果均满足 MA-ID 两方 PASS、Shared 至少一方 FAIL、Shared+Lock 至少一方 FAIL。精确 run ID、分数、调用/Token/秒数与解释边界见[模型结果审计](../tasks/paragui/V13_V15_MODEL_RESULTS_20261114_ZH.md)。

| Case | Scripted joint positive control | MA-ID | Shared | Shared+Lock | 一次筛选 |
|---|---|---|---|---|---|
| V13 数据治理 | cdesk3-v13-scripted-joint-20261114T071306Z-2157595；1/1 + 1/1 | Catalog 1 / Access 1 | Catalog 0 / Access 1 | Catalog 1 / Access 0 | 命中 |
| V14 NCR/返工 | cdesk3-v14-scripted-joint-20261114T065516Z-2147656；1/1 + 1/1 | Disposition 1 / Rework 1 | Disposition 0 / Rework 1 | Disposition 0 / Rework 1 | 命中 |
| V15 访客门禁/培训 | cdesk3-v15-scripted-joint-20261114T071547Z-2158896；1/1 + 1/1 | Badge 1 / Induction 1 | Badge 1 / Induction 0 | Badge 1 / Induction 0 | 命中 |

注意：这是同一合成 intranet app 的三种日常工作流实例，共享状态仍属 active-panel/current-record 家族，并非三种新机制。尤其不能将 case-card 中“窗口失焦/切换”泛化为已证明 OS 窗口级焦点切换；本轮证据是 app 内当前面板上下文及 Oracle 记录。V15 induction 失败时 Agent 观察到界面跳回 badge 表单，Oracle 为 0/1。Per-action lock 未锁整个表单事务。

## Fixture、Oracle、Guest 控制与复现

- 唯一任务定义/预期字段：`tasks/paragui/v456_data.json` 的 `v13`、`v14`、`v15`。UI/SQLite Fixture 由 `tasks/paragui/app_v456_template.py` 和 `tasks/paragui/build_v456.py` 生成；端口依次为 8148、8149、8150。
- task setup/evaluator：`tasks/paragui/pg_v13.py`、`pg_v14.py`、`pg_v15.py`；通用精确 Oracle：`tasks/paragui/pg_v456_oracle.py`。OSWorld task ID：`pgv13catalog` / `pgv13access`、`pgv14disposition` / `pgv14rework`、`pgv15badge` / `pgv15induction`。
- Guest scripted joint positive control：python scripts/run_v456_guest_control.py v13|v14|v15。三版真实 Guest 双方任务 Oracle 均为 1.0。最终正控 run ID 分别为 V13 cdesk3-v13-scripted-joint-20261114T071306Z-2157595、V14 cdesk3-v14-scripted-joint-20261114T065516Z-2147656、V15 cdesk3-v15-scripted-joint-20261114T071547Z-2158896。
- GPT-6-Sol Codex 三臂入口：`bash scripts/run_new_case_arm.sh v13|v14|v15 ma-id|shared|shared-lock`。运行时固定 Codex CLI 0.165.0、GPT-6-Sol、每 Actor 最多 60 次 GUI 调用、超时 2400 秒；token usage 以 provider 返回日志为准（并非每臂都保证提供）。Shared+Lock 是每次 GUI action 的锁，不是事务级锁。密钥仅以受控 stdin 注入，不存进源文件、文档或 result。
- RAID 上大体资产/结果目录为 `/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets/` 与 `/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/`；本地临时 Guest overlay 在 `/dev/shm/codesk-next3/overlays/`。执行时需继续留意根盘余量；不要删除既有 run 或 archive。

## 解释边界

V13–V15 已各自完成一组 MA-ID、Shared、Shared+Lock，并在一次筛选中满足目标分数组合；不是重复性证据。Guest 正控验证 Fixture 和 Oracle，不等于模型证据。Oracle 精确比较字段与保存状态，不等于真实业务质量评估。详细调用、Token、活跃秒数、事件/锁轨迹、失败边界与旧版本排除项见模型结果审计。本批都是 app 内 active-panel/current-record 上下文变化；没有独立操作系统窗口焦点遥测，因此不应表述成已证明跨 OS 窗口键鼠误路由。
