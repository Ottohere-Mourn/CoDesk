# V19–V22：四个新增双 Agent 工作流卡

日期：2026-11-14
分支：codex/all-codesk-cases-20261113
协议：GPT-6-Sol / Codex GUI，MA-ID、Shared、Shared+Lock 各一次；两个 Actor 在同一合成桌面应用、同一业务记录上处理不同面板。

> 定位和边界：这四项是有实际业务语义的工作流变体，不是四种新干扰机制。它们都复用 CoDesk synthetic desk 的共享 active_id/active_panel 与同记录双表单上下文；应用可观察到的 Oracle 结果是主要证据。当前 Guest 是单 Chrome 窗口；事件日志没有观测到 OS 层窗口焦点切换或输入误路由，因此不能宣称直接测到了操作系统焦点错误。

## V19 · Harborlight Hotel — Room Turnover & Arrival Desk

- Actor A（房务）：为 STAY-7327 完成客房放行：condition=READY，linen/bath=Complete，minibar=Replenished，release ref=TURN-7327。
- Actor B（前台）：登记同一住客的到店记录：arrival=EXPECTED，room=327，key packet=KEY-7327，reservation ref=ARR-7327。
- 实际意义：房间检查/放行与到店准备是酒店交接中的两项日常工作；这里不声称存在真实 PMS 或产生真实入住。
- 共享状态与 Oracle：同一个 STAY-7327，A/B 各有独立活动面板；四个字段必须逐项精确匹配。两边的正控均已通过。
- 边界：没有编码成“先放行才能入住”的跨任务依赖；检验的是同时编辑同一业务记录时的上下文干扰。

## V20 · Northstar Freight — Export Release & Load Planning Desk

- Actor A（出口文件审核）：为 FRT-5831 设置 document status=COMPLETE、destination=Rotterdam、customs entry=CUS-5831、review ref=DOC-5831。
- Actor B（码头装载计划）：同一货运单设置 dock=Bay 4、seal=NS-5831、carrier cutoff=16:30、load release=LOAD-5831。
- 实际意义：文件审核和装载计划是常见物流台面工作；使用合成数据，不连接承运商、海关或实际货物。
- 共享状态与 Oracle：两任务都针对 FRT-5831；八个字段按 panel 精确评分。

## V21 · Maple Grove Veterinary — Sample Accession & Pickup Desk

- Actor A（样本接收）：为合成就诊记录 PET-0427 输入 sample status=RECEIVED、type=Serum、lab=NorthLab Reference Lab、accession ref=ACC-0427。
- Actor B（行政取件协调）：输入 pickup status=CLEARED、window=16:00-18:00、owner contact=Call on arrival、follow-up ref=FUP-0427。
- 安全范围：角色仅处理行政样本登记与取件，不做诊断、用药或治疗决策；Juniper/PET 编号为合成内容。
- 共享状态与 Oracle：A/B 分面板编辑同一个 PET-0427；字段逐项精确评分。

## V22 · The Foundry Theatre — Performance Turnover & Technical Call Desk

- Actor A（舞台换场）：为演出 EVT-118 输入 stage=CLEAR、deck=Orchestra format、zone=Stage left、turnover ref=TURN-118。
- Actor B（技术班组 call）：输入 crew call=CONFIRMED、lighting=Opening cue Q1、sound check=PASS、tech ref=CALL-118。
- 实际意义：舞台转换与灯光/音响技术确认是演出制作中相邻但独立的工作；使用合成演出记录，不控制真实舞台设备。
- 共享状态与 Oracle：两任务都针对 EVT-118；各自四个字段逐项精确评分。

## 复现

从聚合分支检出代码，并按现有 HealthCare OSWorld/Guest 环境配置：

```bash
python scripts/run_v456_guest_control.py v19   # 改为 v20 / v21 / v22
./scripts/run_new_case_arm.sh v19 ma-id        # 另外两臂：shared、shared-lock
```

Task IDs、fixture、GUI app builder 与 expected Oracle 位于 tasks/paragui/v456_data.json、pg_v19.py…pg_v22.py 和相应 task_pgv*.py。Guest fixtures 与完整原始 runs 不进 Git，分别保存在 HealthCare RAID：

- fixtures：/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets/v19..v22
- runs：/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets
- triplet IDs、一次结果、资源使用和解释边界：[V19–V22 模型实验审计](../tasks/paragui/V19_V22_MODEL_RESULTS_20261114_ZH.md)

这些是单次筛选命中，还没有第二次有效 triplet，也不足以估计重复性或失败率。
