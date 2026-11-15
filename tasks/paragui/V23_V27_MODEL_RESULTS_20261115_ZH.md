# V23–V27 GPT-6-Sol 单次三臂实验与 Oracle 审计

日期：2026-11-15  
Harness：Codex CLI 0.165.0，GUI-only；GPT-6-Sol，高 effort。每臂每个 Actor 上限 60 GUI 调用。每个 case MA-ID / Shared / Shared+Lock 各一次有效模型 triplet；V23 多一次 MA-ID 重跑。运行期间运行产物与 overlay 均定向到 HealthCare RAID。凭据未写入代码或报告。

## 结论

| Case | MA-ID A/B | Shared A/B 原始记录 | Shared A/B 复核后 | Shared+Lock A/B | 严格三臂组合 |
|---|---:|---:|---:|---:|---|
| V23 | 1/1 | 1/1 | 1/1 | 1/0 | 未达标：Shared 两项均通过 |
| V24 | 1/1 | 0/1 | 0/1 | 0/1 | 一次命中 |
| V25 | 1/1 | 0/0 | 0/0 | 1/0 | 一次命中；Shared 接近调用预算上限 |
| V26 | 1/1 | 0/0 | 0/0 | 1/0 | 一次命中 |
| V27 | 1/1 | 0/0 | 0/1 | 1/1 | 未达标：锁臂恢复两项 |

分数顺序均为 Actor A / Actor B。合格筛选模式要求：MA-ID 双方通过，Shared 至少一个 Actor 失败，Shared+Lock 至少一个 Actor 失败。此标准仅为单次筛选命中，不是重复性或概率结论。

所有模型臂的 result.json 顶层 error 均为 null；Agent 运行期间没有 top-level Guest、API、SSH 错误。除了初次 V23 金额格式 Oracle 失配（见下文）和 V27 日期表示重判（见下文），Oracle 读取均有效。没有隐藏或删除任何一臂。

## Run ID 与性能数据

每格含：分数 A/B；GUI MCP 调用 A/B；Agent 活动秒 A/B；输入 token A/B；输出 token A/B。Agent 活动秒为各自运行时长，并发时不可相加视作墙钟时间。运行 ID 全部位于：

/mnt/raid1/mjh/Projects/codesk-next5-20261115/runs/triplets

| Case / arm | Run ID | A/B 分数 | GUI calls A/B | Agent 秒 A/B | 输入 tokens A/B | 输出 tokens A/B |
|---|---|---:|---:|---:|---:|---:|
| V23 MA-ID（主） | cdesk3-v23-ma-id-20261115T051349Z-2750468 | 1/1 | 12/15 | 160.1/270.1 | 201,607/276,258 | 515/589 |
| V23 Shared | cdesk3-v23-shared-20261115T052938Z-2759321 | 1/1 | 22/36 | 382.1/716.2 | 501,726/1,099,097 | 3,429/2,181 |
| V23 Shared+Lock | cdesk3-v23-shared-lock-20261115T054414Z-2765067 | 1/0 | 43/28 | 814.2/514.2 | 1,538,967/712,674 | 5,774/1,505 |
| V24 MA-ID | cdesk3-v24-ma-id-20261115T060036Z-2772673 | 1/1 | 12/15 | 156.1/222.1 | 201,866/275,880 | 536/589 |
| V24 Shared | cdesk3-v24-shared-20261115T060737Z-2776677 | 0/1 | 38/50 | 742.1/1,032.1 | 1,217,475/1,980,198 | 4,482/4,009 |
| V24 Shared+Lock | cdesk3-v24-shared-lock-20261115T062731Z-2783638 | 0/1 | 19/31 | 402.1/728.1 | 394,330/877,880 | 1,266/1,832 |
| V25 MA-ID | cdesk3-v25-ma-id-20261115T064212Z-2789462 | 1/1 | 12/21 | 168.3/324.4 | 200,781/459,823 | 424/1,371 |
| V25 Shared | cdesk3-v25-shared-20261115T065049Z-2794486 | 0/0 | 48/48 | 1,476.3/1,462.3 | 1,856,421/1,888,093 | 4,954/5,487 |
| V25 Shared+Lock | cdesk3-v25-shared-lock-20261115T071816Z-2806173 | 1/0 | 31/23 | 474.1/346.1 | 852,436/528,993 | 1,728/2,155 |
| V26 MA-ID | cdesk3-v26-ma-id-20261115T072856Z-2812034 | 1/1 | 12/13 | 130.1/144.1 | 203,351/227,832 | 493/624 |
| V26 Shared | cdesk3-v26-shared-20261115T073428Z-2817800 | 0/0 | 22/20 | 262.1/226.1 | 497,460/431,976 | 2,238/1,423 |
| V26 Shared+Lock | cdesk3-v26-shared-lock-20261115T074130Z-2821683 | 1/0 | 39/29 | 562.2/392.2 | 1,293,062/783,285 | 3,543/3,012 |
| V27 MA-ID | cdesk3-v27-ma-id-20261115T075328Z-2826368 | 1/1 | 15/16 | 302.1/348.1 | 275,972/302,797 | 557/559 |
| V27 Shared（原始记录） | cdesk3-v27-shared-20261115T080234Z-2832040 | 0/0 | 18/31 | 540.1/906.1 | 361,071/868,103 | 1,199/1,618 |
| V27 Shared+Lock | cdesk3-v27-shared-lock-20261115T082030Z-2839141 | 1/1 | 19/24 | 358.1/562.1 | 393,004/565,478 | 941/1,220 |

V23 MA-ID 复核重跑：cdesk3-v23-ma-id-20261115T052237Z-2755081，A/B=1/1，13/15 GUI calls，214.1/216.1 Agent 秒。它是额外重复，不用于替换其他 arm。

## Scripted Guest 正向控制

最终版本的双 Actor 固定动作 Guest positive control 都能把两边数据写完整，并且 Oracle=1/1：

- V23：cdesk3-v23-scripted-joint-20261115T044955Z-2737737，表单重试 [0,1]。
- V24：cdesk3-v24-scripted-joint-20261115T045248Z-2739075，重试 [0,0]。
- V25：cdesk3-v25-scripted-joint-20261115T045538Z-2740443。
- V26：cdesk3-v26-scripted-joint-20261115T045833Z-2741799。
- V27：cdesk3-v27-scripted-joint-20261115T050122Z-2737736。

早期控制尝试仍保留在 RAID：V23 cdesk3-v23-scripted-joint-20261115T042813Z-2727366（维修表单不完整）、V24 cdesk3-v24-scripted-joint-20261115T043124Z-2728794（服务通告表单不完整）。之后脚本增加了输入读回和最多三次表单写入重试；中间与最终控制日志均未删除。V25/V26/V27 的首次 scripted control 已通过。

## Oracle 修订审计（不覆盖原始记录）

### V23 货币数值

第一次 MA-ID run cdesk3-v23-ma-id-20261115T050547Z-2746083 的初始字符串精确匹配不接受模型输入“8600”对预期“USD 8,600”的格式差异，因此 review 记为 0/1。当前 Oracle 对 reserve_amount / recommended_award 只在对应字段上抽取数值并比较；新增正向/错误金额单测防止金额错误也被当作通过。后续 MA-ID 与其它 arms 在此修订后的 Oracle 下评分。原 run 与原始 score 仍保留，不计入合格臂。

### V27 日期区域格式

原 Shared result 的 strict ISO date Oracle 报为 0/0。但末次 Guest 截图中，B（付款计划）四个字段均已填写；日期显示 12/01/2026，与任务指定的 2026-12-01 在美国日期格式下等价。Actor A 的最后一个截图则显示其焦点落在 Draft disbursement schedule 面板，且目标表单为空。随后 Oracle 添加严格格式集合（ISO YYYY-MM-DD、美国 MM/DD/YYYY、YYYY/MM/DD）下的日期语义比较，并有等价格式通过、错误日期失败的回归测试。因此报告的复核值为 Shared A=0/B=1，而不是把格式差异当任务失败。原始 result.json 及原始 0/0 未被改写。即使重判，V27 仍因 Shared+Lock=1/1 而不符合目标三臂 tuple。

V27 Shared 截图与原始 run logs 保留在同一 RAID run 目录（end.png、agentA/shots、agentB/shots）；Oracle 来源代码与测试分别在 tasks/paragui/pg_v456_oracle.py 和 tests/test_v7_v27_reference_controls.py。

## Scripted / Model 失败、干扰与预算

- 模型有效性：MA-ID 三个 Agent 对均通过；Shared 与 Shared+Lock 的每个 score 都来自可读状态；top-level result error 为 null。Shared 失败不是 API/Guest invalid-run。
- V24：Shared A、Shared+Lock A 均失败，B 两臂通过。
- V25：Shared 0/0；lock 下 A 通过、B 失败。Shared 两 Agent 都接近 60-call 上限（48/48），虽然未触顶，仍要作为预算接近上限的解释限制。
- V26：Shared 0/0；lock 下 A 通过、B 失败。
- V27：Shared经截图复核 A=0/B=1；锁臂双方通过，因此锁改善了本次三臂里表现；本 case不达标。
- V23：Shared 双方通过，尽管锁臂 B 失败；没有满足 Shared fail。
- V23–V27 的 Shared 和 Shared+Lock events.jsonl 中，focus_switch_action 和 misrouted_focus_before 事件计数均为 0。截图显示的是单应用页面内部 active-panel/work area 切换；没有证据称为 OS 层窗口焦点切换。
- “Shared+Lock”是 GUI MCP 单次调用加回图像的 per-action 互斥。各 Agent 仍可能在两个调用之间看到另一个面板、持有过期上下文继续输入；不保证一个完整表单或 task transaction 不被打断。

## 锁等待统计

锁事件按 action_lock 日志汇总：等待时间 A/B 合计。总 hold 是所有工具调用持锁秒数的总和。

| Case | Lock events | 总等待秒 | 平均等待秒 | 最大等待秒 | 持锁总秒 |
|---|---:|---:|---:|---:|---:|
| V23 | 64 | 16.310 | 0.255 | 2.407 | 155.504 |
| V24 | 46 | 5.980 | 0.130 | 2.380 | 116.297 |
| V25 | 47 | 11.512 | 0.245 | 2.713 | 116.320 |
| V26 | 63 | 14.383 | 0.228 | 3.190 | 151.276 |
| V27 | 33 | 3.839 | 0.116 | 2.905 | 83.613 |

## 证据局限

- Five distinct workflow domains, one shared-app mechanism family. This result provides case/workflow portfolio coverage, not five new interference mechanisms.
- No OS-level focus or window switch was detected; app-panel state telemetry and screenshots support in-app shared context changes only.
- One model triplet per case. One-shot screening hit should not be read as a stable rate; V23/V27 are preserved as no-go outcomes.
- V27's B pass is a post-run semantic Oracle re-adjudication supported by screenshot evidence; original result.json remains unchanged for reproducibility.
- Token usage above is the Codex run-reported API accounting. Tokens are not comparable to unique model work across cached context reuse; they are included for run/resource audit only.

## 复现

~~~bash
python scripts/run_v456_guest_control.py v24
./scripts/run_new_case_arm.sh v24 ma-id
./scripts/run_new_case_arm.sh v24 shared
./scripts/run_new_case_arm.sh v24 shared-lock
~~~

替换 case ID 即可运行其余项。完整模型 traces、screenshots、fixture manifests 与 RAID resource ledgers 不纳入 Git；用表中的 run ID 在 RAID 上检索。API credentials 需由执行环境安全注入，不要写进 shell history 或仓库文件。
