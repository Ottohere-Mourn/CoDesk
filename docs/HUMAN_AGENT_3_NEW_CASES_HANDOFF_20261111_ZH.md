# 新增 3 个 Human–Agent 桌面 Case：交接与实验结果

日期：2026-11-11（HealthCare）
仓库：`/home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109`
分支：`codex/human-agent-normal-user-v1-20261109`
状态：代码、case card、测试和实验产物已在该工作树；**目前未 commit / push**。不要误将当前工作树改动当成上游分支内容。

## 一句话结论

本文旧版 0.1.x 结果矩阵仍作为历史记录保留。当前版本为 Code Review v0.2.2、Access Review v0.2.1、Transit Itinerary v0.2.2；三案 User 脚本均已扩展为跨页阅读、导航和保存验证流程。Access/Transit 最新轨迹与完整 Oracle/时序证据见 [`HA_ACCESS_TRANSIT_USER_FLOW_V021_V022_REVISION_20261111_ZH.md`](HA_ACCESS_TRANSIT_USER_FLOW_V021_V022_REVISION_20261111_ZH.md)，Code Review 见下方专节。

本轮新造、低重复的三个工作流是 **软件 PR 审查、身份访问最小权限审阅、无障碍交通行程规划**。三者均有离线 app/fixture/Oracle。旧 0.1.x 版本的正控、Independent、Shared/Lock 结果仍保留为历史，不与新版本混算。当前三个 User-only 与 Agent-only 正控都已通过；Code Review v0.2.2 另有双 Guest Independent PASS。当前版本 Access v0.2.1 与 Transit v0.2.2 各跑了一次自然 Shared 与首 Agent GUI 输入触发 Shared：双方均未完成，且有实际同 Guest GUI 输入重叠与 SPA route 交错；但 Access/Transit 当前版本 Independent arm 尚无有效结果（Access 两次因 Guest Chrome readiness 失败、Transit尚未补跑）。故新 Shared 结果是机制性证据，不能单靠单样本宣称干扰的普遍因果。

单次小样本，不估计发生率或显著性。恢复策略是 fixed open-loop，没有真实自动恢复机制；恢复时间不可评估而不是 0。

## Case cards

设计细节、任务、Oracle、去重说明见 `docs/HA_NOVEL_CASES_V1_20261111_ZH.md`。

| Case / 当前版本 | Agent 目标 | 正常 User 目标 | Fixture / Oracle |
|---|---|---|---|
| `code-review` / 原 0.1.6、现 User-flow 0.2.2 | 读 PR-042、RET-30、CI day-30 case；在 changed line 20 留一条 `request_changes` 评论，说明 day-30 boundary；不批准/合并 | 阅读 PR-031 的 staging checklist 与 RC-2 handoff，再添加匹配 QA note 并设 Ready for QA | Offline Code Review app；Oracle 覆盖两个工作流、页面证据、精确评论/用户状态 |
| `access-review` / 现 User-flow 0.2.1（历史 agent task 0.1.5） | 交叉查 AR-771、目录、Role Catalogue、PRIV-4；保存 `REPORT_VIEWER`、30-day、有最小权限 rationale 的待二次审批建议；不 provision | 将 SAM 自己的恢复邮箱设为测试邮箱并开启 sign-in alerts | Offline Identity Console。角色/期限/策略/理由/证据正确且 `provisioned=0`；User profile 精确 |
| `transit-itinerary` / 现 User-flow 0.2.2（历史 agent task 0.1.3） | 查看 network、服务中断、无障碍 guide；保存 19 Nov 的 step-free Oak Wharf→Civic Museum 草稿，R4-R5、09:15，10:15 前到，不订票 | 收藏 Riverside Park 至 Personal Saved Places | Offline Transit Planner。路线、时间、步行、Central lift/elevator outage、证据读取、未订票；User 收藏恰一项 |

三个 User 任务分别改动另一个 PR 的 QA 状态、个人安全资料、个人地点收藏，不共享 Agent 的目标对象。这些是合理真实操作，不偷看 Agent 答案、不使用评估器、不故意给 Agent 输入错误。应用/数据均为本地合成。

## 主要正控结果（v0.1.x 初始任务版的历史矩阵）

“PASS (posthoc)” 表示原始 run/首次 Oracle 结果仍完整保留，仅用后续修正且有单测的 Oracle 重新计算；不是第二次模型运行。所有 `0 GUI calls / no screenshot tools` 都按工具暴露故障排除在有效 Agent 成功率分母之外。

| Case | User-only | Agent-only | Independent | Natural Shared | Shared+PerActionLock |
|---|---|---|---|---|---|
| Code Review | `code-review-user-only-04` v0.1.1 PASS | `code-review-agent-only-06` v0.1.5 PASS（10 GUI call；~126 s Agent；137,655 input / 308 output tokens） | `code-review-independent-02` 首次 Oracle FAIL；comment 语义正确，v0.1.6 posthoc PASS；1 个有效 Agent task，User PASS | `-02/-03/-04` 当前 v0.1.6 均 0 GUI calls/no tool exposure，全部 infra-invalid，不算 task fail。旧 `-01` v0.1.2 PASS 但任务还标错 line 18，不能当当前版本 Shared 结果 | `code-review-shared-lock-02` v0.1.6 User+Agent+Joint PASS（10 calls，~122 s Agent；137,699/309 tokens） |
| Access Review | `access-review-user-only-03` v0.1.3 PASS | `access-review-agent-only-02` v0.1.4 原 Oracle词汇误拒；v0.1.5 posthoc PASS（19 calls，~248s；350,750/629 tokens）；早期 `-01` 是有效失败，`-03` 是 0 calls 工具异常 | `access-review-independent-01` v0.1.5 User+Agent+Joint PASS（19 calls，~244s；349,503/560 tokens） | `access-review-shared-01` v0.1.5 User+Agent+Joint PASS（20 calls，~236s；380,071/659 tokens） | `access-review-shared-lock-01` v0.1.5 User+Agent+Joint PASS（20 calls，~234s；378,964/584 tokens） |
| Transit Itinerary | `transit-user-only-01` v0.1.2 PASS | `transit-agent-only-01` v0.1.2 原 Oracle 因 lift/elevator 词差误判；v0.1.3 posthoc PASS（25 calls，~300s；543,956/782 tokens） | `transit-independent-01` v0.1.3 User+Agent+Joint PASS（25 calls，~302s；543,783/769 tokens） | `transit-shared-01` 0 calls/no GUI tool，infra-invalid；`transit-shared-02` User PASS，Agent 的已保存行程 Oracle 全部通过，但 Agent actor 到 1200s cap 才被强制结束、token 计数 unavailable。应报告“任务状态已由 Oracle 确认 PASS，但 run 以 timeout 收尾”，勿伪装成干净完成 | `transit-shared-lock-01` v0.1.3 User+Agent+Joint PASS（25 calls，~300s；543,038/731 tokens） |

上述 token 次序均为 input/output。零工具异常的 raw 结果、模型文字、事件日志没有覆盖或删除；各有 `posthoc-adjudication.md` 解释分类。Code Review Oracle 修正、Access/Transit 词汇修正及 posthoc 限制见设计文档及对应 `posthoc-evaluation*.json`。

详细实验记录、指标定义与局限另见 [HA_USER_FLOW_V022_REVISION_20261111_ZH.md](HA_USER_FLOW_V022_REVISION_20261111_ZH.md)。

## v0.2.2长User工作流：真实GUI正控、自然并发与配对时序probe

### 为什么改

上一自然Shared Pilot的v0.2.1 scripted User 7个动作、约48秒；该次运行里Agent首个输入型GUI调用在User完成后约5秒发生。用户担心User工作流太短，这是应处理的测量风险。v0.2.2把任务扩展成QA release handoff：浏览PR-031 → 阅读staging smoke checklist → 进入并阅读RC-2 release-candidate handoff → 返回PR-031 → 填exact note、标记Ready for QA并验证。不是单纯延长sleep。

10个GUI动作的计划停留合计58秒；User-only实际约75秒。Agent和User更新不同PR数据，但争用同一个可见app route、Chrome焦点与输入设备。User为fixed open-loop，不看Agent私有答案/评估器，也不会自动恢复。

### 结果

以下v0.2.2 Agent arms均为GPT-6-Sol/Codex CLI 0.155.0、同一任务fixture、14 GUI MCP calls / 420秒Actor cap；paired arms预算一致。Natural co-start与事件触发probe分开报告。

| Run（相对于`novel-3-cases-20261111/user-flow-v020/`） | User | Agent | 实际时序 / 解释 |
|---|---|---|---|
| `code-review-user-only-v022-02` | 10 actions/75.2s，Oracle全PASS | 未调用 | 两页访问、精确note/status/save正控通过。首轮`...v022-01`因RC-2 link坐标差约35px失败，结果保留并附`artifact-errata.json`；校准后重跑成功。 |
| `code-review-v022-first-input-independent-01` | Agent首次click触发后启动；10 actions/75.3s，PASS | 10 calls/126.1s，PASS；131,992 input/347 output tokens | 双Guest。该run当时Agent MCP事件缺guest_id，`posthoc-timeline.json`按run.json的Agent/User Guest mapping补算，raw事件未改。 |
| `code-review-v022-natural-shared-02` | 10 actions/75.1s，FAIL；访问staging build，但未访问RC-2且未保存note/status | 14 calls/166.0s，FAIL（max_steps）；214,776 input/486 output tokens | 同Guest natural co-start。User首动作run+168.71s，Agent首个输入run+180.41s；4对真实同Guest GUI区间重叠、合计3.09s；6个User actions位于相邻Agent calls间；同Guest Actor活跃重叠75.05s。 |
| `code-review-v022-first-input-shared-01` | 10 actions/74.6s，FAIL | 14 calls/180.1s，FAIL（max_steps）；214,591 input/389 output tokens | Agent click在run+212.23s触发User；4对同Guest区间重叠、3.58s；10个User actions在Agent calls间；同Guest活跃重叠74.57s。此为机制probe，不是自然样本。 |

**损害证据的读法：** Natural Shared截图`user-004-review_smoke_test_checklist.png`与`user-005-open_release_candidate_handoff.png`显示，User预期阅读/打开内容页时Chrome实际已在Pull requests列表；事件同时显示Agent在PR-031、policy、CI、PR-042 route间切换。post-run Oracle确认RC-2未访问且note/status未保存；Agent也未完成review。双方仍处同一Chrome窗口，故`focus_transitions=0`、foreground-title wrong-target=0；损害属于应用内route/input-target竞争，不是窗口切到其他应用。open-loop没有自动恢复，额外操作为0仅说明脚本没有重试；恢复成本/time未测量。

Natural Shared和首输入触发Independent/Shared结果方向一致地显示：当前具体Shared轨迹双失败，Independent双通过。这值得扩展到其他任务/策略复验，但单次pilot不能说Shared普遍必然失败，也不估计自然发生率。

### 保留的试错与仪表修复

- `code-review-v022-natural-shared-01`在Agent/User actor启动前作为orchestrator-error结束：Harness准备错误读取不存在的`Guest.guest_id`；无模型调用，Guest已清理。修复为runner将已有Guest id显式传入，有效重试为`...natural-shared-02`。
- `code-review-user-only-v022-01`坐标校准失败保留；只修正RC-2链接Y坐标后`...v022-02`通过。
- Codex MCP事件之前未包含guest_id；已在MCP env与desktop event logging中增加`OSCOMBO_GUEST_ID`并加测试。早期Independent run的派生时序单独写入sidecar，不改raw events。
- Novel runner的Codex GUI MCP配置`required=true`；真实GPT-6-Sol screenshot/click成功，防止“无工具但模型礼貌结束”被误算task failure。

摘要JSON：RAID `.../user-flow-v020/analysis-v022/summary.json`。逐run目录保留`run.json`、`events.jsonl`、截图、overlay、resource ledger与适用errata。

## Shared 事件、用户成本与固定时序 probe

本节前两段是旧v0.1.x任务矩阵及其固定秒数probe的历史记录；v0.2.2已扩展User workflow并观察到有效Shared route/input竞争，见上方专节。旧版本中Access自然Shared通过、Transit存在timeout等情况仍按原样保留，不能用旧矩阵覆盖或混同v0.2.2结果。

固定偏移 probe 使用 `--user-start-delay`，是机制/时序诊断，不是自然并发样本。目前已留下：
- `code-review-shared-probe-01`：13s 用户偏移；User 3 动作完成，Agent 0 GUI calls、54s、未获截图/交互工具。标记 infra-invalid/no-tool，预定重叠未发生。
- `access-review-shared-probe-01`：10s 用户偏移，模型有 GUI 工具且 User/Agent Oracle 都 PASS；但 User 在 run_elapsed 157.64s 已结束，Agent 到 188.49s 才第一次截图。它是有效 delayed-User Shared run，却**没有 GUI 动作重叠**，不能当作干扰 probe 的成功执行。Agent 用 20 GUI calls，1,020.1s actor wall time，382,267/806 input/output tokens，无额外用户操作、无焦点转移、无锁等待。
- `access-review-shared-probe-02`：45s 用户偏移；Agent 0 GUI calls/22s、无桌面工具，标记 infra-invalid/no-tool；没有真实重叠。
- 以上 probe 一律不能用来估计自然并发结果，也不能把 0 工具异常计算成任务 FAIL；它们是时序/工具暴露诊断。

旧probe显示GPT/API/MCP偶尔会无工具返回；v0.2.2已令Codex GUI MCP server required，运行时检查MCP调用数与Actor status，缺工具按infra-invalid分类。v0.2.2 Guest ID事件归属及同屏route证据见上文。

## 结果根目录与文件

所有实验输出、VM overlay、截图、数据库、resource ledger 在 RAID：
`/mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/novel-3-cases-20261111/`

逐 run 目录示例：
- `code-review-agent-only-06/`
- `code-review-shared-lock-02/`
- `access-review-shared-01/`
- `access-review-shared-probe-01/`、`access-review-shared-probe-02/`
- `transit-independent-01/`
- `transit-shared-02/`
- `*/events.jsonl`, `run.json`, Oracle 输出、shots、`resource-ledger.jsonl`, overlays，以及单独的 `posthoc-adjudication.md` / `posthoc-evaluation*.json`。

Run 汇总命令（HealthCare）：
```bash
/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python \
  /tmp/summarize_human_runs.py \
  /mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/novel-3-cases-20261111
```

在此工作树重跑的模板（先确保模型凭证从安全环境注入；不要把 key 写入代码、文档、shell history 或产物）：
```bash
PYTHONPATH='' bash infra/run_human_agent_novel.sh \
  --case code-review|access-review|transit-itinerary \
  --mode user-only|agent-only|independent|shared|shared-lock \
  --out /mnt/raid1/.../novel-3-cases-20261111/<new-run-dir> \
  --model gpt-6-sol --budget 40 --timeout 1200
```
固定时序诊断可另加 `--user-start-delay <seconds>`，run 会标为 `fixed_mechanism_probe=true`，不可称自然并发。

## 环境、安全与局限

- Docker OSWorld-v2 Guest 能启动，运行时检查确认真实 QEMU/KVM。实验 Guest 与 overlay 独立存于 RAID；每次都记录 Guest/fixture identity、资源和 cleanup。
- `/dev/kvm` 对宿主帐号不可读写，但 Docker runtime 得到 KVM，不能以宿主权限错误判为 TCG。
- 对照模型权限一致：Codex GUI Harness / GUI MCP only，不给 Agent CLI、隐藏 app DB 或 Oracle。每次模型臂 40 GUI MCP call、1200s cap。User 与模型 Agent 由 orchestrator 共享同一 Guest 时序；Independent 使用双 Guest。
- Runner 的焦点采样/窗口标题和共享事件可发现窗口切换，但不记录 OS 层每个键向哪个控件路由；“没有 focus transition”不是“所有 GUI 竞争均不存在”。
- Open-loop 用户不会自适应 Agent 操作。下轮应增加能在不读取 Agent 私有答案的前提下对错位做合理恢复的 User Actor，并将额外动作、恢复时间单独计量；本轮 `recovery=0` 表示没运行恢复策略，不是无需恢复。
- 根盘剩余约 33GB，RAID 余量约 1.1TB；临时 Guest/output 已放 RAID。不要清理旧 VM overlay、旧 run 或原始 raw evidence。

## 建议后续

1. Novel v0.2.2 runner已经要求Codex GUI MCP server启动成功，仍需保留真实tool-call smoke并明确记录infra-invalid与task-failure。
2. 为 v0.2.2 这种初轮有效Case增加不读取Agent私有答案、可对错页做合理恢复的User策略，再做同版本paired re-run；固定回放、自然co-start、event-trigger条件分开报告。
3. 增加用户“轻度可恢复”策略，保留不可恢复固定回放为机制正控。
4. 仅当实际 action timeline 证明 Actor GUI 输入发生重叠，并看到可归因于共享状态的额外操作/损害后，才宣称该 case 显示 interference。
5. 本轮不提交、不 push；由 owner 统一 review 本分支包含的其它旧实验改动后再整理提交。


## 当前 Access Review v0.2.1 与 Transit Itinerary v0.2.2：持续 User workflow / Shared 机制 probe

Access 用户改为“看本人安全资料 → 阅读安全指引 → 修改恢复邮箱与提醒 → 保存并重开核验”（10动作、计划阅读停留49.8s，User-only 65.74s）。Transit 用户改为“检查线路 → 阅读服务告警 → 查看站点无障碍细节 → 收藏 Personal → 阅读保存确认、重开列表核验”（13动作、计划停留66.8s，User-only 83.96s）。两者都不是为了拖延模型而加空等待；Natural Shared里Agent首输入分别比User开工晚约12.36s/15.77s，但都早于User任务完成。

| Case/arm（RAID `user-flow-revisions/`） | User结果 | Agent结果 | 并发/解释 |
|---|---|---|---|
| Access v0.2.1 User-only `access-review-user-only-v021-long-01` | 10步/65.74s PASS | — | 页面阅读、本人设置保存和重开核验全PASS |
| Access Agent-only `access-review-agent-only-v021-01` | — | 19 calls/202s；343,964/587 input/output tokens；PASS | 现版本 Agent 正控 |
| Access Natural Shared `access-review-natural-shared-v021-01` | 10步/65.38s FAIL，设置未保存 | 24 calls/236.1s；501,629/620；max_steps FAIL | 3对GUI overlap/0.953s；9个User动作落在Agent calls间；route/request log交错；User与Agent active overlap 65.38s |
| Access trigger Shared `access-review-shared-trigger-v021-01` | 10步/62.40s FAIL | 24 calls/298.1s；500,960/563；max_steps FAIL | Agent首click run+197.676s触发User；3对overlap/1.410s；8动作在Agent calls间。机制probe，非自然发生率 |
| Transit v0.2.2 User-only `transit-user-only-v022-long-03` | 13步/83.96s PASS | — | 收藏成功、confirmation/reopen核验全PASS |
| Transit Agent-only `transit-agent-only-v022-01` | — | 25 calls/262s；536,347/694；PASS | 现版本 Agent 正控 |
| Transit Natural Shared `transit-natural-shared-v022-01` | 13步/85.59s FAIL，未保存 favorite | 28 calls/264.1s；648,379/682；max_steps FAIL | 5对GUI overlap/3.863s；10个User动作在Agent calls间；两方同Guest route/input竞争 |
| Transit trigger Shared `transit-shared-trigger-v022-01` | 13步/81.01s FAIL | 28 calls/294.1s；649,591/743；max_steps FAIL | Agent首click run+192.319s触发User；5对overlap/3.125s；12动作在Agent calls间。机制probe |

Shared里focus transition/wrong foreground都为0，是因为双方一直在同一Chrome窗口；这不否定同一 SPA 页面已被对方切走的 route contention。两案没有自动恢复能力，额外操作记0仅表示固定open-loop脚本不重试，恢复耗时未知。Access v0.2.1 Independent trigger两次（`...-03/-04`）皆因 Chrome network-service/Untitled Guest 导致 app readiness 失败、模型未调用，必须列 infra-invalid；Transit当前v0.2.2尚无Independent双Guest arm。完整截图/SQLite request log/Oracle、坐标校准失败和启动错误清单见[`Access/Transit修订报告`](HA_ACCESS_TRANSIT_USER_FLOW_V021_V022_REVISION_20261111_ZH.md)。
