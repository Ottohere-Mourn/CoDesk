# V7–V10 Dual-Agent 模型试验结果（2026-11-13）

分支：`codex/all-codesk-cases-20261113`。这是四个新 workflow 各一次真实 GUI 三臂 pilot；只计固定版本/种子的一次 screening 命中，不是重复性或因果强度证明。

## 协议与正控

- Codex CLI 0.165.0、GPT-6-Sol/high，GUI-only harness；本轮没有 CLI/MCP 工具。
- MA-ID：任务各在独立 Guest/reset；Shared：同一 Guest；Shared+Lock：同一 Guest，对每个 GUI action 加互斥锁。
- 每个 Actor 每臂最多 60 GUI calls/steps；同一任务版本、Fixture、模型、预算，变化的是桌面拓扑/锁。Oracle 检查各自三条目标记录。
- 21 个相关 Oracle/control tests passed。四个真实 Guest scripted joint positive controls 均 A/B=1/1：
  - V7 `cdesk3-v7-scripted-joint-20261113T112700Z-1655427`
  - V8 `cdesk3-v8-scripted-joint-20261113T113024Z-1657020`
  - V9 `cdesk3-v9-scripted-joint-20261113T113355Z-1658760`
  - V10 `cdesk3-v10-scripted-joint-20261113T113717Z-1660426`
- 12 个模型 run API/Guest error 均为 null，Oracle state 均可读，评分来自最终持久状态，不把 infra-invalid 当 task FAIL。

## 三臂结果

分数顺序均为 Actor A / Actor B；目标：MA-ID 两方 PASS，Shared 至少一方 FAIL，Shared+Lock 至少一方仍 FAIL。

| Case / A + B 任务 | MA-ID | Shared | Shared+Lock | 一次 tuple |
|---|---:|---:|---:|---|
| V7 LAB-WATER1：样品 custody intake / bench result | 1 / 1 | 1 / 0 | 0.6667 / 0 | 是 |
| V8 CITY-PERMIT1：permit review-routing / fee receipt | 1 / 1 | 1 / 0 | 0 / 0 | 是 |
| V9 FIELD-SERVICE1：technician scheduling / parts reservation | 1 / 1 | 1 / 0 | 0 / 0.6667 | 是* |
| V10 CARE-TRANSITION1：follow-up plan / equipment dispatch | 1 / 1 | 0 / 1 | 0 / 0 | 是 |

**4/4 一次达到所需分数组合。** V9 的 Shared+Lock 失败混有 60-call 截止因素，不应单独归因于锁。

### Run ID 与成本

| Case | MA-ID run (calls) | Shared run (calls) | Shared+Lock run (calls) | 三臂 run time |
|---|---|---|---|---:|
| V7 | `cdesk3-v7-ma-id-20261113T114113Z-1662193` (84) | `cdesk3-v7-shared-20261113T120337Z-1672537` (72) | `cdesk3-v7-shared-lock-20261113T122830Z-1682173` (91) | 1.19 h |
| V8 | `cdesk3-v8-ma-id-20261113T125441Z-1691978` (63) | `cdesk3-v8-shared-20261113T131202Z-1700720` (60) | `cdesk3-v8-shared-lock-20261113T132945Z-1707880` (51) | 0.80 h |
| V9 | `cdesk3-v9-ma-id-20261113T134459Z-1714219` (75) | `cdesk3-v9-shared-20261113T135950Z-1720708` (77) | `cdesk3-v9-shared-lock-20261113T142205Z-1729398` (85) | 1.05 h |
| V10 | `cdesk3-v10-ma-id-20261113T145137Z-1740106` (72) | `cdesk3-v10-shared-20261113T150657Z-1747536` (62) | `cdesk3-v10-shared-lock-20261113T152649Z-1754618` (48) | 0.92 h |

run time 为 result.json `total_s` 三臂相加。合计约 **4.0 run-hours**、840 GUI calls、**28,407,677 input / 45,256 output tokens**。Input 包含模型报告的 cached input，不是费用估算。

### 失败及 Oracle 明细

MA-ID 四案的每个任务均 3/3 records correct。

- **V7** Shared：A custody 3/3、B bench 0/3；B 报告 Instrument 交互后 form 反复切回 “Sample accession”。Shared+Lock：A 2/3、B 0/3；B 报告编辑 WQ-611 时 work area 跳至 WQ-613。Oracle 可读、无 API/Guest error。
- **V8** Shared：A review 3/3、B fee 0/3；B 报告 fee-posting 表单在字段交互中切回 Application review。Shared+Lock 双方 0/3；B 报告收据表单反复 reset/navigate。
- **V9** Shared：A dispatch 3/3、B parts 0/3；B 报告 reservation form 点击/输入会切回 Technician dispatch。Shared+Lock：A 0/3、B 2/3；B 已保存 WO-8170/8224，但剩余交互预算不足以为 WO-8318 选择 RESERVED 并保存，因此这是有效未完成结果、但受 60-call 截止混杂。
- **V10** Shared：A follow-up 0/3、B equipment 3/3；A 报告界面切至 Equipment work area，clinic selections 不保留。Shared+Lock 双方 0/3；A 报告表单切换且无法可靠录入，B 未能确认 dispatch saves。

完整 `INFEASIBLE` 原因、动作与截图见对应 run artifact；最终 PASS/FAIL 仍由 Oracle 决定，而不是由模型自述。

## 解释边界

- 这些任务字段正交、终态可共存；独立模型控与 scripted joint control 均证明两边能解。
- 四案都暴露同一类 browser active-work-area/form/record context 切换，是同一 shared active-context/input-routing 机制的不同业务工作流，**不是四种新机制**。V9 也接近先前 W2 概念。
- Shared+Lock 是每次 GUI action 串行化，不会把表单输入至保存变成事务。锁没有维持一个工作流期间的 active form。各案锁臂日志总 lock wait：V7 10.27s、V8 3.69s、V9 5.96s、V10 3.61s。
- 遥测缺口：事件日志中 OS-window `focus_switch_action` 四案均为 0；logger 不追踪应用内部 tab/panel/form context。上文切换证据来自 Agent 的屏幕观察/描述和 Oracle 终态，而不是独立 DOM/app-level counter。要作强机制归因，下一版应新增语义级 panel/record telemetry；不要把本结果写成通用 OS 焦点抢占证据。
- 每案仅一颗种子/一次三臂，无重复。保留所有结果，不按结果调参。

## 复现与 artifacts

- Cards: `docs/FOUR_NEW_DUALAGENT_CASES_V7_V10_20261113_ZH.md`
- Wrapper: `scripts/run_new_case_arm.sh v7|v8|v9|v10 ma-id|shared|shared-lock`
- RAID artifacts: `/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/<run-id>/`，含 `result.json`、actions/events、Agent traces 和 screenshots。
- run 中 oscombo 为 `937c6e87ccf8785f655a1b26f3807d1b1385aab1+dirty`；OSWorld 为 `3d778a3c9a34a079316f70df023b166700445792+dirty`。External OSWorld worktree/runtime 不随 CoDesk branch 镜像。
- Overlay copy 到 RAID FUSE 有 chmod not permitted warning；结果、事件、动作、截图目录仍在 RAID。不要声称所有 VM overlays 均已归档。API key 不在 Git。
