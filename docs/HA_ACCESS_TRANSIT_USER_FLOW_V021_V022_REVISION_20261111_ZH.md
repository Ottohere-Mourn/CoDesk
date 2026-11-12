# Access Review / Transit Itinerary：User 工作流扩展与模型并发验证

日期：2026-11-11（HealthCare）
工作树：`/home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109`
分支：`codex/human-agent-normal-user-v1-20261109`（保留未提交状态）
结果根：`/mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/novel-3-cases-20261111/user-flow-revisions/`
相关代码：`oscombo/human_apps/access_review.py`、`oscombo/human_apps/transit_planner.py`、`oscombo/human_agent_novel_case_runner.py`

## 结论先行

之前担心 User 会在 Agent 第一次桌面操作前就结束，是合理的任务设计问题。现在 Access Review 与 Transit Itinerary 都有带页面阅读、跨页导航、填写/保存和再打开验证的 10–13 步 User 流程。三案现版本的 User-only 正控时长约 **65–84 秒**；两案自然 Shared 的 Agent 第一次输入型 GUI 工具调用分别比 User 第一个 GUI 动作晚约 **12.4 秒**与 **15.8 秒**，此时 User 流程尚未结束。自然 Shared 与独立触发 Shared 都有实际同 Guest GUI 调用区间重叠与 App route 竞争证据，已不再是“User先做完，模型才开始”的空并发样本。

- **Code Review v0.2.2**：User-only 与双 Guest Independent PASS；Natural Shared、first-agent-input Shared 均为双方 FAIL，已有报告 [`HA_USER_FLOW_V022_REVISION_20261111_ZH.md`](HA_USER_FLOW_V022_REVISION_20261111_ZH.md)。
- **Access Review v0.2.1**：User-only、Agent-only PASS。Natural Shared 与 first-agent-input Shared 均为双方 FAIL，并观察到同 Chrome route 被反复切换；两次 current-version Independent 尝试都在模型调用前因 Chrome 网络服务/页面就绪失败而判为 infrastructure-invalid，故本版暂无有效双 Guest 正控。
- **Transit Itinerary v0.2.2**：User-only、Agent-only PASS。Natural Shared 与 first-agent-input Shared 均为双方 FAIL，且都观察到同一 Guest 的页面导航和输入竞争。该版本没有补跑 Independent 双 Guest；旧 v0.1.3 Independent PASS 不可替代当前版本证据。

这些是每个条件一次左右的真实 GPT-6-Sol pilot，可证明特定轨迹下任务可解/发生失败，并提供并发干扰机制证据；**不是**共享桌面必然失败、自然干扰发生率或统计显著性的估计。两位 Actor 的失败与 Shared 机制一致，但不能把全部模型任务失败都仅归因于共享，尤其 Agent 有固定 GUI-call 上限。

## 为什么这次 User 任务长度不同

这次加的不是只等待的空操作；脚本必须通过可见 GUI 路由到信息页，停留阅读/检查，再回到目标页面填写/保存并验证。scheduled dwell 是阅读与思考停留时间，仍存在但不参与 Agent 与 User 的对齐/抢占；自然条件无预先固定的 Actor 动作次序。User 不读取 Agent 的私有提示/答案或 Oracle，也没有为了让 Agent 失败而注入错误输入。

| Case / 版本 | User 工作流（简述） | 步数 | 计划阅读/思考停留 | User-only实际 Actor wall | 首次 GUI 输入相对 User 开始（Natural Shared） |
|---|---|---:|---:|---:|---:|
| Code Review v0.2.2 | PR-031 → staging smoke checklist → RC-2 handoff → 回 PR-031 填 QA note/设 Ready for QA/核验 | 10 | 58.0s | 75.2s | Agent 晚约 11.7s 开始；User 尚需约 63s |
| Access Review v0.2.1 | 打开本人安全档案 → 阅读 recovery / sign-in alert 指引 → 修改并保存 → 重开档案核验 | 10 | 49.8s | 65.74s | Agent 晚约 12.36s 开始；User 尚需约 53s |
| Transit Itinerary v0.2.2 | 查看线路 → 服务中断 → Riverside Park 站无障碍说明 → 收藏 Personal → 看确认并重开 Saved Places 核验 | 13 | 66.8s | 83.96s | Agent 晚约 15.77s 开始；User 尚需约 68s |

User GUI 输入本身约 16–19 秒，其余部分主要是明确编入脚本的页面阅读/思考 dwell。它们是持续约一分钟以上的桌面工作而不是很长的办公会话；因此本次解决的是“先于 Agent 完成”的明显缺陷，后续若要评估长时段真人体验仍须提高自然变异和恢复策略，而不是把等待继续拉长。

## 协议与可比性

- 真实 Agent：GPT-6-Sol，经 Codex CLI 0.155.0 / 现有 GUI MCP，仅操作 Guest Chrome 可见应用；无 Guest shell、Oracle/数据库或隐藏答案权限。GUI MCP 设为 required，MCP 未暴露的 run 不算任务失败。
- 每 case 同版本 User-only、Agent-only、Natural Shared 使用相同任务目标与 fixture basis；配对 Agent 臂预算不变：Access Review **24 GUI calls / 600s**，Transit **28 GUI calls / 600s**。User-only 与 Agent-only分别提供此版本 User/Agent 可解正控。
- Natural Shared 是双方同时启动的观察；`first-agent-input` Shared 在真实 Agent 首个输入型 GUI 事件发生后释放 User Actor，是可复现的并发机制 probe，不是自然发生率样本。其后 User 并无锁或串行动作次序。
- fixture basis：Access Review User-only/Agent-only/Natural Shared 均为 `3b5811c31111c6d0913600c17c49e623c851b932ea9317d533d72465c295f840`。Transit User-only/Agent-only/Natural Shared/trigger Shared 均为 `9bcc9ed9a92116370a23c4e12449dc006b62cd65dcc13c7704fd9cd53efa914b`。
- App 数据及截图/evaluation 只在实验结束后由 evaluator 读取。两个 Shared actor 使用同一 Guest、同一 Chrome 窗口、同一 SPA 当前路由与输入设备；Independent 是两个独立 Guest。
- 固定脚本是 open-loop：`extra_operations=0` 表示脚本没有自动恢复重试，不代表受影响后恢复成本为零。当前没有估计恢复时长；该成本记为“未实现/不可测”。本轮没有 Shared+Lock arm。

## Access Review v0.2.1

User 需要查看 SAM 自己当前的恢复邮箱/提醒状态，阅读 Security Profile 指引，再将恢复邮箱改为 `sam.backup@example.test`、启用 sign-in alerts、保存，重开档案核验。Agent 审 AR-771，读取申请、员工目录、Role Catalogue 与 PRIV-4，保存 30 天、`REPORT_VIEWER`、最小权限理由的待二次审批建议；禁止实际 provision。两者业务记录独立但竞争单个 SPA 路由/Chrome 输入状态。

| 条件 / run | User | Agent | 交叠与结果 |
|---|---|---|---|
| User-only `access-review-user-only-v021-long-01` | 10 步 / 65.74s，profile、guide、保存确认、重开核验全部 PASS；GUI action 15.896s；无输入错误 | 未调用 | 当前 User 脚本正控 PASS |
| Agent-only `access-review-agent-only-v021-01` | 未运行 | PASS；19 MCP calls，202.0s Agent wall；343,964 input / 587 output tokens；申请/角色/期限/策略/理由/证据及“不 provision”全通过 | 当前 Agent 任务正控 PASS |
| Natural Shared `access-review-natural-shared-v021-01` | 10 步/65.38s，FAIL：初始档案和指引确实查看，但设置未保存；DB仍为旧邮箱、alerts=0/revision=0 | 24/24 calls，236.1s，FAIL（max_steps）；501,629 input / 620 output；四类证据页访问，但没有提交审查 | 3 对字面 GUI action 时间重叠 / 0.953s；9 个 User 动作发生在 Agent GUI calls 间；同 Guest Actor 活跃重叠 65.38s。首个 Agent 输入较 User 首动作晚约 12.36s。 |
| Shared first-input `access-review-shared-trigger-v021-01` | 10 步/62.40s，FAIL，profile DB 未改变 | 24/24 calls，298.1s，FAIL（max_steps）；500,960 input / 563 output；没有 review | trigger 在 run+197.676s 的首个 Agent click；3 对 GUI overlap / 1.410s，8 个 User 动作落在 Agent calls 间；Actor overlap 62.40s。是机制 probe。 |

Natural Shared 的用户事件实际跨越 `My Security Profile`、`Account security guide`、Agent 的 access queue/evidence/review 页面；随后用户固定坐标操作发生时，同一个 Chrome 已被 Agent 改到其他业务路由。SQLite request log 保留了交错的 `GET /settings/security`、`GET /guide/security-profile`、Agent `/request/AR-771`、`/directory/D-148`、`/roles`、`/policy/PRIV-4` 和 `/review/AR-771`，但没有 User 保存所需的 POST；档案最终值不变。first-input Shared 同样反复在 profile、guide、AR-771 与 Agent 证据路由间切换，且没有保存/ review 记录。所有工具调用错误为 0，User `misrouted_focus_before=false`，`focus_transitions=0`；因为双方始终在同一 Chrome，当前 instrumentation 不会将“同窗内 SPA 页面切换”标记为 OS 窗口焦点错误。

这支持同页路线竞争导致 User 脚本后半段目标页面丢失的机制解释；但 Access current-version 双 Guest Independent 正控因下述基础设施错误未成功，而且单轮 Agent budget 有限，因此这里应称“强机制证据/与干扰一致”，不写成严格单因果证明。

## Transit Itinerary v0.2.2

User 查看线路、服务告警及 Riverside Park 的 step-free 站台/入口/help-point 信息，将车站放入 Personal Saved Places，阅读保存确认，再重开列表核验。Agent 综合线路、Central lift outage 和 step-free guide，规划并保存 Oak Wharf → Civic Museum 行程；Oracle 要求 2026-11-19、R4–R5、09:15、10:15 前到达、不订票。业务数据对象独立但争用一个 SPA 路由与输入设备。

| 条件 / run | User | Agent | 交叠与结果 |
|---|---|---|---|
| User-only `transit-user-only-v022-long-03` | 13 步/83.96s PASS，所有顺序阅读、收藏、确认和重开 Oracle checks 为真；计划 dwell 66.8s，GUI action 17.08s | 未调用 | 当前 User 正控 PASS；截图验证列表显示 `Riverside Park – Personal` |
| Agent-only `transit-agent-only-v022-01` | 未运行 | PASS；25 calls / 262.0s；536,347 input / 694 output tokens；行程/时间/路线/中断/步行/未订票全通过 | 当前 Agent 正控 PASS |
| Natural Shared `transit-natural-shared-v022-01` | 13 步/85.59s，FAIL；没有 favorite/确认/重开持久记录 | 28/28 calls，264.1s，FAIL（max_steps）；648,379 input / 682 output；查看了证据页但未保存行程 | 5 对字面 GUI overlap / 3.863s；10 个 User 动作发生在 Agent GUI calls 间；同 Guest 活跃重叠 85.59s。首个 Agent 输入晚于 User 首动作约15.77s。 |
| Shared first-input `transit-shared-trigger-v022-01` | 13 步/81.01s，FAIL，无 Personal 收藏 | 28/28 calls，294.1s，FAIL（max_steps）；649,591 input / 743 output | 首个 Agent click 于 run+192.319s 触发 User，User 首动作约在 run+196.51s；5 对字面 GUI overlap / 3.125s；12 个 User 动作处于 Agent calls 间；Actor overlap 81.01s。 |

两个 Shared backend SQLite request logs 都保留 network/service alert/step-free/收藏相关 GET 与 Agent 的 trip navigation；没有任何新增 favorite 或 itinerary。Natural Shared Oracle 标记双方所有目标状态/提交失败，但 `all_evidence_viewed` 和 User 的 `research_pages_reviewed_in_order` 为真。事件与截图表明双方在不同步骤把 SPA 页面切至对方的页面/用户操作目标；因此失败不是“User在Agent开始之前早已完成”。自然 Shared 中 Agent first GUI click 前 User 已开始约16秒且整个User工作流跨越85.6秒；事件触发 Shared 则 User 在 Agent 首个 GUI click 后约4.2秒开始。两边都观察到多次真实 GUI 区间交叠。

## 未通过的实验尝试与基础设施 errata

这些都完整留在 RAID 中，不删除、不改写为有效任务 FAIL：

- Transit User-only `transit-user-only-v022-long-01`：Chrome network-service 报错、`Untitled - Google Chrome`，应用未就绪；`infrastructure-invalid`。
- Transit User-only `...long-02`：首次 Guest raw/raster 坐标比例校准错误（1920×1080 raw、截图展示宽度不同），出现错误页面访问；这是脚本校准失败，不是共享干扰或 User 任务不可解。按真实 screenshot 修正坐标后，`...long-03` 正控 PASS。
- Access Independent trigger `access-review-independent-trigger-v021-03` 与重试 `...-04`：两 Guest 独立启动期间 Chrome network-service crash，浏览器保持 Untitled；`case app did not become visible`。均未调用模型、无任何 Agent/User 任务结果，标为 `infrastructure-invalid`；不可算 task failure。旧 Access v0.1.5 Independent PASS 是不同任务版本，不替代当前 v0.2.1 双 Guest 正控。
- 一次 Access Independent 启动的包装器 `...-02` 因 output-dir/console-log 同名的 `FileExistsError` 在运行前退出；无模型或任务调用，已单独留档。

反复尝试的根因属于 Guest Chrome readiness，不是任务需求或模型 endpoint；后续应单独排查/稳定 Guest Chrome，不能为了得到独立 PASS 而放宽 Oracle/选择性忽略失败。

## 结果目录与复现

本报告涉及逐 run 目录（皆有 `run.json`、`events.jsonl`、shots/screenshots、SQLite backend、RAID overlays 与资源账本）：

- Access: `access-review-user-only-v021-long-01`、`access-review-agent-only-v021-01`、`access-review-natural-shared-v021-01`、`access-review-shared-trigger-v021-01`、`access-review-independent-trigger-v021-03/-04`。
- Transit: `transit-user-only-v022-long-01/-02/-03`、`transit-agent-only-v022-01`、`transit-natural-shared-v022-01`、`transit-shared-trigger-v022-01`。
- 根路径：`/mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/novel-3-cases-20261111/user-flow-revisions/`。
- Codex GUI Agent 的预算参数、first-agent-input trigger 与模型凭证均由 `/tmp/run_human_agent_novel_secure.sh` 管理；重放前先确认 HealthCare 资源预检通过，模型 key 从 stdin 注入，不写入命令历史/产物。

## 本轮质量门

- 当前 Novel app / scheduler / Codex MCP / desktop tool 针对性测试：**23 passed**。
- 三个 app 与 Novel runner `py_compile`：通过。
- `git diff --check` 整仓发现 `README.md` 第216行一个已有新增尾空白/空行（README 是早先已有 dirty change，本轮没有改它）；本轮新增的报告/交接文本单独应检查 clean，不应借机覆盖 README 内容。
- 未提交、未 push；当前工作树本来就包含更多未提交 Case 代码与 docs，请在父分支统一 review。

## 建议

1. 先稳定 Guest 中 Chrome 的网络服务/启动 readiness，再为 Access/Transit 各取得同版本双 Guest Independent 正控；在此之前独立桌面结论限定为各自 User-only 与 Agent-only 正控。
2. 保存当前自然 Shared 与触发 Shared 的 fail，不要因其同向而删掉任何失败/infra-invalid，也不要把机制触发样本算自然发生率。
3. 下一步若评估真实用户损害/成本，另增不知 Agent 私有目标、只依据可见界面合理恢复的 scripted User 策略，和 open-loop 固定回放并行；当前额外操作为0、恢复时间未知，不足以量化恢复成本。
4. 不用继续拉长 User 等待时长来追求 Shared FAIL：三案 User 均能明显与首个 Agent GUI 动作并发。目前更重要的是在当前版本取得可靠 Independent 正控，并给有恢复能力的策略记录额外操作/恢复时长。
