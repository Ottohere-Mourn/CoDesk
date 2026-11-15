# V28–V30 GPT-6-Sol 三臂结果审计

日期：2026-11-15
范围：三个新工作流，一次 scripted positive control + 一次 MA-ID / Shared / Shared+Lock 模型 triplet；仅作筛选，无重复。模型为 GPT-6-Sol，Codex CLI 0.165.0，high effort；每 Actor 60 GUI tool call ceiling。每个 Actor 有独立任务和 Oracle，但 Shared/Shared+Lock 中都操作同一 Guest GUI。
代码 HEAD 基线：CoDesk 3b00213；OSWorld 3d778a3c。source tree 在各次运行时有对应未提交的新 case 文件（result.json SHA/provenance 保留），故标为 pilot rather than release-stable replication。 每个 triplet 的三臂 fixture.sha256 内容相同（V28 hash-list digest b50fd3e7；V29 af921f0f；V30 ba88dc87），因此同一 Case 内任务/fixture 版本保持一致。

## Fixture/控制有效性

| Case | Scripted joint positive control | Oracle |
|---|---|---|
| V28 | cdesk3-v28-scripted-joint-20261115T084709Z-2850337 | inspection 1/1；schedule 1/1 |
| V29 | cdesk3-v29-scripted-joint-20261115T084958Z-2851710 | screening 1/1；interview 1/1 |
| V30 | cdesk3-v30-scripted-joint-20261115T085245Z-2850336 | handoff 1/1；training 1/1 |

三项脚本正控均 error=null，Fixture/readable state 正常，未发生 form retry。setup 曾报告 Playwright CDP socket hang-up retries，之后重新连接、Guest screenshot 与 state 检查均成功；不是模型试验的 invalid 条件。

## 三臂结果

下表的 A/B 分数依任务 Oracle 给出；GUI 是该 Actor 实际 MCP GUI 调用数；Token 列为该 Actor 的 input/output token。所有九个模型 arm 的 top-level error 均为 null，Oracle state 均可读。更完整的 events.jsonl、actions.jsonl、screenshots、stdout、result.json 留存于 RAID，未删减。

| Case | Arm / run ID | A / B | GUI calls A/B | Input tokens A/B | Output tokens A/B | 关键判定 |
|---|---|---:|---:|---:|---:|---|
| V28 | MA-ID cdesk3-v28-ma-id-20261115T085914Z-2855763 | 1/1 | 14/15 | 249,646 / 276,018 | 824 / 576 | baseline pass |
| V28 | Shared cdesk3-v28-shared-20261115T090602Z-2861193 | 0/0 | 60/60 | 3,044,095 / 3,087,621 | 7,916 / 8,443 | 两 Actor 都用尽 60-call ceiling；budget-confounded Shared 失败 |
| V28 | Shared+Lock cdesk3-v28-shared-lock-20261115T093811Z-2871356 | 1/1 | 59/49 | 2,839,295 / 1,969,937 | 6,608 / 6,214 | 锁后恢复，故不符合要求 |
| V29 | MA-ID cdesk3-v29-ma-id-20261115T101536Z-2882435 | 1/1 | 14/13 | 250,306 / 224,882 | 735 / 444 | baseline pass |
| V29 | Shared cdesk3-v29-shared-20261115T102228Z-2886117 | 1/1 | 38/34 | 1,288,089 / 1,052,618 | 2,829 / 2,152 | no-go: Shared all-pass |
| V29 | Shared+Lock cdesk3-v29-shared-lock-20261115T103626Z-2890895 | 1/1 | 20/32 | 426,882 / 933,994 | 738 / 1,683 | all-pass |
| V30 | MA-ID cdesk3-v30-ma-id-20261115T105201Z-2895943 | 1/1 | 14/14 | 252,144 / 252,438 | 490 / 486 | baseline pass |
| V30 | Shared cdesk3-v30-shared-20261115T110009Z-2901072 | 1/1 | 50/47 | 2,041,983 / 1,851,954 | 3,011 / 3,212 | no-go: Shared all-pass |
| V30 | Shared+Lock cdesk3-v30-shared-lock-20261115T113337Z-2910234 | 1/0 | 18/28 | 368,013 / 740,428 | 1,812 / 1,523 | lock 1/2, but Shared did not fail; no target tuple |

## 事件与归因边界

事件来自 events.jsonl。Shared 机制运行中的计数：

| Run | GUI events | Logged focus-switch flag | Misrouted-focus-before | Window-title transitions |
|---|---:|---:|---:|---:|
| V28 Shared | 120 | 0 | 0 | 0 |
| V28 Shared+Lock | 108 | 0 | 0 | 6 |
| V29 Shared | 72 | 0 | 0 | 3 |
| V29 Shared+Lock | 52 | 0 | 0 | 0 |
| V30 Shared | 97 | 0 | 0 | 4 |
| V30 Shared+Lock | 46 | 0 | 0 | 0 |

Window-title transitions 主要在 app Chrome 与 New Tab/Incognito tab 之间；日志没有 focus_switch_action 或 misrouted_focus_before 证据。因此不把结果说成 OS-level focus/input misrouting。V28 Shared 任务围绕同一 fixture 的两种表单数据竞争，0/2 在锁臂恢复，但两 Actor 都恰好打满 GUI-call ceiling，不能排除过度尝试/预算的影响。V29 的浏览器窗口切换没有带来 Oracle 失败。V30 Shared+Lock B 的单任务 fail 缺乏可归因的焦点/误路由事件，且 Shared 全通过，不能用来满足目标。

Per-action lock 的 GUI action 等待（仅统计 GUI action 行，非重复的 lock event 汇总）：
- V28 Shared+Lock：95 个正等待事件；总 lock wait 9.081 秒；单次最大 2.346 秒。
- V29 Shared+Lock：35 个正等待事件；总 lock wait 7.950 秒；单次最大 2.817 秒。
- V30 Shared+Lock：40 个正等待事件；总 lock wait 12.079 秒；单次最大 6.424 秒。

这些试验没有真人参与，额外操作成本不能解释为人类恢复时间；Token/GUI call 只做工具预算与运行成本留档。

## 最终判定

- MA-ID/Independent PASS：3/3。
- Shared 严格 FAIL：只有 V28 0/2，但达到双 Actor 60/60 call ceiling，因此预算混杂。
- Shared+Lock FAIL：仅 V30 1/2 有一项 Oracle failure；V28、V29 均 2/2 pass。V30 Shared 全通过，锁臂 failure 不能满足完整 tuple。
- 全部 triplet 组合严格满足 MA-ID PASS + Shared FAIL + Shared+Lock FAIL：**0/3**。
- 此轮新增三类真实工作流外观，但机制家族仍是合成应用的 active-panel/current-record 上下文。当前实验结果不支持将它们算作新增达标 case 或独立机制。

## 运行数据位置

/mnt/raid1/mjh/Projects/codesk-next5-20261115/runs/triplets/ 下保留上表 run ID 对应的 result.json、events.jsonl、每 Actor 的 actions/shots/stdout/stderr、fixture/source hashes；/mnt/raid1/mjh/Projects/codesk-next5-20261115/assets/v28..v30/ 为现场生成的 GUI app/fixture/expected DB。不要清理覆盖这些证据。
