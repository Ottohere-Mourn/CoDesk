# V13–V15 模型实验结果与审计记录

日期：2026-11-14
分支：codex/all-codesk-cases-20261113
实验轨：GPT-6-Sol + Codex GUI-only harness；Codex CLI 0.165.0；effort high；每 Actor GUI 调用上限 60；单臂 timeout 2400 秒。

## 结论

V13（研究数据治理）、V14（制造 NCR/返工核验）、V15（访客门禁/入场培训）各完成一组三臂结果，均在这次一次性筛选中满足：

- MA-ID/独立：双方 Oracle 均 PASS；
- Shared：至少一个任务 Oracle FAIL；
- Shared+Lock：至少一个任务 Oracle FAIL。

这只是每案一次有效的模型观察，不是重复性/概率证据。Shared+Lock 使用每个 GUI action 的互斥锁，不会把一整段表单流程事务化。三案复用了同一个合成 intranet app 的活动面板/当前记录上下文，因此是三个日常工作流实例，不应称为三种不同机制。

## 精确结果

A/B 对应任务见任务卡。GUI 调用和 input/output token 来自 Codex run usage；input 包含 provider 报告的 cached input。秒数是 agent 活跃秒数，不是整个 Guest 准备到 teardown 的总墙钟时间。

| Case / arm | Actor A：分数 / 状态 / GUI 调用 / 秒 / input→output tokens | Actor B：分数 / 状态 / GUI 调用 / 秒 / input→output tokens | Run ID |
|---|---|---|---|
| V13 MA-ID | Catalog 1.0 / done / 11 / 240.1 / 179679→388 | Access 1.0 / done / 21 / 832.1 / 456751→1059 | cdesk3-v13-ma-id-20261114T071916Z-2160282 |
| V13 Shared | Catalog 0.0 / done / 30 / 644.1 / 813182→1428 | Access 1.0 / done / 52 / 1254.2 / 2129336→2489 | cdesk3-v13-shared-20261114T073710Z-2167537 |
| V13 Shared+Lock | Catalog 1.0 / done / 33 / 748.1 / 954172→2190 | Access 0.0 / fail / 21 / 580.1 / 532436→1342 | cdesk3-v13-shared-lock-20261114T080121Z-2177045 |
| V14 MA-ID | Disposition 1.0 / done / 13 / 372.1 / 226508→500 | Rework 1.0 / done / 17 / 370.1 / 338333→757 | cdesk3-v14-ma-id-20261114T081720Z-2183057 |
| V14 Shared | Disposition 0.0 / fail / 20 / 350.1 / 430186→1492 | Rework 1.0 / done / 25 / 772.1 / 607735→1479 | cdesk3-v14-shared-20261114T082735Z-2188500 |
| V14 Shared+Lock | Disposition 0.0 / done / 23 / 488.1 / 529844→1293 | Rework 1.0 / done / 38 / 802.1 / 1209261→1994 | cdesk3-v14-shared-lock-20261114T084358Z-2196211 |
| V15 MA-ID | Badge 1.0 / done / 13 / 204.1 / 227526→594 | Induction 1.0 / done / 15 / 234.1 / 278471→680 | cdesk3-v15-ma-id-20261114T090059Z-2205162 |
| V15 Shared | Badge 1.0 / done / 30 / 634.1 / 818110→2022 | Induction 0.0 / done / 20 / 400.1 / 426744→1240 | cdesk3-v15-shared-20261114T090941Z-2210281 |
| V15 Shared+Lock | Badge 1.0 / done / 50 / 950.1 / 1987835→4551 | Induction 0.0 / fail / 41 / 748.1 / 1386964→2587 | cdesk3-v15-shared-lock-20261114T092355Z-2216385 |

Run-level result.json 里各 run 的 infrastructure error 为 null；失败任务的评分由应用状态和精确字段 Oracle 得到，不把 API/Guest 错误当作任务失败。V15 Shared+Lock 的 induction Actor 明确报告任务 UI 在录入中跳回 badge 表单，induction 未保存；run result 对应 records_correct 为 0/1。其 Agent status 为 fail，但 exit_code=0，属于任务失败而非进程/传输异常。V14 Shared 与 V13 Shared+Lock 的失败分数同样有可读 state 与 0/1 record Oracle 证据。

### Scripted Guest 正控

每个最终 Fixture 在一个真实 Guest 中由 scripted 双方完成后，两方 Oracle 都为 1.0：

- V13：cdesk3-v13-scripted-joint-20261114T071306Z-2157595
- V14：cdesk3-v14-scripted-joint-20261114T065516Z-2147656
- V15：cdesk3-v15-scripted-joint-20261114T071547Z-2158896

这验证当前 Fixture、保存路径与 Oracle 可用；脚本正控不等于模型行为证据。

## Lock 与状态干扰解释

每动作锁能避免同时发出同一 GUI action，但 action 返回截图后，另一 Actor 可在后续 action 前切换应用内活动面板。它不锁定 “打开目标表单 → 连续填写 → 保存” 整个事务。

锁事件日志位于各 Shared+Lock run 的 locks/agent-action-lock-events.jsonl。每次 action 的平均持锁时间约 2.35–2.41 秒；平均等待依 actor 与运行而异，约 0.03–0.43 秒，观测最大等待约 2.71 秒。V15 锁臂合计记录 83 次 action-lock 事件；锁没有阻止 induction 表单上下文失效。

限定证据口径：这些日志和应用数据支持“共享活动面板/表单上下文变化导致任务未落库”这一应用内 GUI 状态干扰解释；浏览器窗口本身没有切换，因此不声称已证明不同操作系统窗口之间的焦点切换/键盘误路由。未来若需要把窗口级焦点作为机制主张，应另加 OS 窗口焦点遥测。

## Fixture 迭代和排除项

最终比较均使用每 Actor 一个目标记录：V13 DS-4102、V14 VALVE-8021、V15 VIS-7304。V13/V15 日期字段在最终版本统一改为提示 YYYY-MM-DD 的文本输入。

保留但不纳入三臂成绩：
- V13 两记录 MA-ID：cdesk3-v13-ma-id-20261114T060332Z-2122526。Catalog 受预算/超时影响，非最终任务版本。
- V13 原生 date 控件的单记录 MA-ID：cdesk3-v13-ma-id-20261114T070209Z-2152018。它促成对所有臂一致的文本日期可用性修复，不属于最终版本。
- 早期多记录 scripted 控制：cdesk3-v13-scripted-joint-20261114T064822Z-2143699。仅为初版诊断。
这些不是 cherry-picked 的最终 Shared 结果：最终版在重新构建 fixture、通过 scripted 双方正控后才按 MA-ID → Shared → Shared+Lock 顺序完成三臂。

V15 Shared+Lock 收尾时包装脚本报告 tmpfs overlay archive 的 chmod “operation not permitted / could not archive tmpfs overlay” 警告。Guest 已正常 teardown，run 有完整 result.json、双方轨迹/日志、锁事件及 Oracle；因此只记录为 overlay archive warning，不将完整的模型 run 重分类为 infra invalid，也没有清理 RAID 或根盘数据。

## 复现与原始证据

任务卡：docs/THREE_NEW_DUALAGENT_CASES_V13_V15_20261114_ZH.md
任务定义与 Fixture：tasks/paragui/v456_data.json 中 v13/v14/v15；构建入口 tasks/paragui/build_v456.py；Oracle：tasks/paragui/pg_v456_oracle.py。
运行入口：scripts/run_new_case_arm.sh v13|v14|v15 ma-id|shared|shared-lock
RAID 根目录：/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/
模型完整原始日志、screenshots、events.jsonl、result.json 与 Guest overlay archive 均留在 HealthCare RAID；不把 API key 放入仓库或文档。
