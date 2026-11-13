# CoDesk Human–Agent Shared Desktop：新增 3 类低重合 Case

日期：2026-11-11
实现工作树：`/home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109`，分支 `codex/human-agent-normal-user-v1-20261109`（未提交）。
历史 Agent task-card 基线：HA-CODE-REVIEW v0.1.6、HA-ACCESS-REVIEW v0.1.5、HA-TRANSIT-ITINERARY v0.1.3。现行 User-flow revisions：Code Review v0.2.2、Access Review v0.2.1、Transit Itinerary v0.2.2。User脚本及最新实验须以 [`HA_ACCESS_TRANSIT_USER_FLOW_V021_V022_REVISION_20261111_ZH.md`](HA_ACCESS_TRANSIT_USER_FLOW_V021_V022_REVISION_20261111_ZH.md) 和 [`HA_USER_FLOW_V022_REVISION_20261111_ZH.md`](HA_USER_FLOW_V022_REVISION_20261111_ZH.md) 为准；下方0.1.x细节保留为历史。
结果索引与逐 run 目录见 `HUMAN_AGENT_3_NEW_CASES_HANDOFF_20261111_ZH.md`。

## 与既有工作去重

三案均是离线的日常工作流 app，由真实 GPT-6-Sol Codex GUI Actor 与 scripted normal User 并发执行。场景不是把旧任务换字段：

| Case | Agent 的实际工作 | User 的正常工作 | 与已运行 HA-TRIAGE、PO-ARCHIVE、CALENDAR、MAIL、INVENTORY 等差异 |
|---|---|---|---|
| HA-CODE-REVIEW | 阅读 PR patch、退货政策和 CI 边界测试；在 changed line 留行级评论并 request changes | 更新另一个 PR 的 QA note 与状态 | 软件工程代码审查；非服务分诊、文档/发票审阅或普通列表管理 |
| HA-ACCESS-REVIEW | 交叉核验访问请求、组织目录、角色目录、PII 策略；保存有期限的最小权限建议但不实际授予 | 修改本人恢复邮箱、安全提醒 | 身份治理/最小权限决策；无真实账号或权限变更 |
| HA-TRANSIT-ITINERARY | 综合无障碍线路、服务中断、换乘与步行时间；保存未订票的无障碍行程草稿 | 将常用站点保存至个人收藏 | 出行网络约束与服务中断规划；不是日历排期或采购物流 |

这是基于任务结构、共享 UI 状态、Oracle 和 Actor 工作目标的定性去重，不宣称统计独立。其他候选（CMS、Sprint board、采购报销、阅读清单）因与 Writer、列表/筛选、PO/Invoice、证据简报重合度较高而未选。

## 最终 Task Cards 与 Oracle

### HA-CODE-REVIEW v0.2.2（User 工作流扩展版）
- Agent：在离线 CoDesk Code Review app 中审 PR-042 “Inclusive returns window”；读取 RET-30 与 PR-042 CI 边界测试；检查 patch；在唯一违反要求的 changed line **20** 留一条可执行评论，`request_changes`，说明“交付后第 30 天仍符合退货资格”的包含边界；不得批准或合并。只用可见 GUI。
- User：打开 PR-031，阅读 staging checklist 与 release-candidate RC-2 handoff 两页，再回到 PR-031，添加精确文字 `Staging 2026.11.09-rc2 verified: session refresh and profile-save checks passed; ready for QA.`，设为 Ready for QA 并确认。
- Oracle：Agent 恰有一条 PR-042 / line 20 / request_changes review；理由语义解释 day-30 inclusive boundary；要求页、CI 页已访问；PR-042 仍 open。User Oracle 同时要求 PR-031 note/status 精确、staging 与 RC-2 页均访问、确认已保存。
- 纯离线合成 PR 网站；不连 GitHub，不修改真实代码。

### HA-ACCESS-REVIEW v0.1.5
- Agent：审 AR-771；检查申请、Dana Brooks 的组织/岗位信息、Role Catalogue 和 PRIV-4；保存仅供二次审批的 `REPORT_VIEWER`、30 天、聚合分析不需要 PII 的 scoped 建议；不 provision。
- User：仅在 SAM 自己的安全档案把恢复邮箱设为 `sam.backup@example.test`，开启 sign-in alerts，并验证保存。
- Oracle：请求、decision、role、期限、策略、最小权限/无 PII 理由和证据访问记录正确；provisioned 必须为 0。User 值与开关准确。
- 纯离线合成 Identity Console，无真实用户或权限系统。

### HA-TRANSIT-ITINERARY v0.1.3
- Agent：为 2026-11-19 从 Oak Wharf 前往 Civic Museum 规划全程 step-free 行程，10:15 前到；检查线路、Central Station lift 中断 D-711 和无障碍指引；保存 `Museum visit - accessible route` 草稿，不订票。
- User：把 Riverside Park 加入 Personal Saved Places，并验证收藏。
- Oracle：恰一份未订票、日期/起终点正确的行程；step-free R4-R5，09:15 出发、步行后不晚于10:15，避开 Central lift outage，且 network/alert/guidance 三项都读取。Oracle 接受 “lift” 或 “elevator” 表述；这只是词汇等价修正，不放宽路线和停运要求。User 收藏必须恰好一项且属于 Personal。
- 纯离线合成交通规划器，无真实交通 API、行程或支付。

## 透明修正与历史版本

- Code Review v0.1.1 将 changed line 错标为 18；最终核实可疑比较在 patch line 20。旧运行保留，不作为 v0.1.6 的最终正控。v0.1.1 Oracle 曾只接受比较运算符，误拒 GPT 以“include day 30 / at most 30”说明的正确评论；v0.1.2 后改为接受普通英语等价表述并拒绝相反方向。Agent-only v0.1.5 成功。v0.1.6 task card 禁止生硬的比较符号并明确边界。
- Access Review v0.1.1/0.1.2 脚本坐标与邮箱替换问题导致 User 控失败；v0.1.3 修复后 User-only 通过。Agent v0.1.3 的页面缺少进入 review 的路径；v0.1.4 补上可见链接后 Agent 提交了正确建议，但 Oracle 对理由中的 “customer identifiers” 词汇过窄；v0.1.5 接受 PII / identifiers / personal information 等等价说法。`access-review-agent-only-02` 经留档的 v0.1.5 posthoc Oracle 重评通过，非一次全新模型重跑。
- Transit Planner v0.1.1 的 User 点击位置错；v0.1.2 修正。v0.1.2 Oracle 把 “lift” 当错而只认 “elevator”；v0.1.3 接受两者但仍要求 Riverside route + Central outage。旧 Agent run 经保留原始产物的 v0.1.3 posthoc 重评通过，不应冒充独立复现。
- 任一 Oracle 修正都只新增 posthoc 评估文件/说明；原始 run、响应和首次评分保留。

## 通用实验协议

- 五模式：User-only、Agent-only、Independent（两个等价但独立 Guest）、Shared（同一 Guest）、Shared+PerActionLock。
- Independent 初始 fixture basis hash 应一致；分别报告 User/Agent 与 joint success。
- Codex CLI 0.155.0 + GPT-6-Sol GUI MCP-only；每模型臂 40 GUI calls / 1200s。各对照使用相同任务、fixture、脚本和预算。该批是 GUI-only 测试，不使用 CLI 工具。
- App SQLite / Oracle 留在宿主；Agent 仅操作 Guest Chrome 可见页面；评分只在 Actor 结束后读取。
- RAID 结果根：/mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/novel-3-cases-20261111/。每次运行独立保存 Guest overlay、截图、events、usage、resource ledger 和 Oracle。
- User 是 open-loop，不含自动恢复；未实现恢复时恢复成本是不可估计，不可记为零。
- 自然 Shared 与固定启动偏移 probe 分开报告；单样本只能证明具体轨迹，不能估计发生率或显著性。






## Code Review v0.2.2：User 工作流时长与共享路由试验（2026-11-11）

v0.2.1 的自然 Shared Pilot 中，User 7步、约48秒；在那次运行里，User Oracle通过后Agent第一个有意义的输入型GUI call才发生，约晚5秒。v0.2.2因此不是简单增加sleep：User正常阅读staging smoke checklist，再进入release-candidate handoff核对RC-2 tag与主要用户可见检查，最后回到PR-031发布匹配证据的QA note。

| v0.2.2条件 | User | Agent | 可观察时序 / 结果 |
|---|---|---|---|
| User-only正控 `code-review-user-only-v022-02` | 10 GUI actions，75.2s，Oracle PASS（两页均已读、exact note/status/confirmation） | 未调用 | 证明修订后User任务本身可解。首轮`...v022-01`因点击release link高度差约35px失败，已保留且有erratum；校准后重跑通过。 |
| Independent，Agent首次GUI输入后启动User `code-review-v022-first-input-independent-01` | 10 actions，75.3s，PASS | Codex 10 calls，126.1s；131,992 input /347 output tokens；PASS | 首个Agent click在run+242.59s释放User；User和Agent分别处于guest-user/guest-agent，联合PASS。旧run Agent MCP event最初缺guest_id，按run.json双Guest topology透明补算，原始events未改。 |
| Natural Shared `code-review-v022-natural-shared-02` | 10 actions，75.1s，FAIL；未读到RC-2页，note/status未保存 | Codex用满14 calls，166.0s；214,776 input /486 output tokens，FAIL（未提交review） | User+Agent同时启动；User首GUI action run+168.71s，Agent首个输入run+180.41s；4个同Guest GUI区间重叠对、合计3.09s；6个User actions处于Agent调用间；同Guest Actor活跃重叠75.05s。 |
| Shared，Agent首次GUI输入事件后启动User `code-review-v022-first-input-shared-01` | 10 actions，74.6s，FAIL | Codex用满14 calls，180.1s；214,591 input /389 output tokens，FAIL | `first-agent-input`由Agent click释放（run+212.23s）；4对同Guest调用区间重叠（3.58s），10个User actions落在Agent calls间；同Guest Actor活跃重叠74.57s。此为机制probe，不等于自然发生率。 |

解释限制：两类Shared都在同一个Chrome window，窗口焦点始终留在Chrome，所以`focus_transitions=0`、按前台app标题统计的wrong-foreground为0；观察到的损害来自应用内页面/route竞争，而不是切换到另一应用。截图与`window_before/window_after`显示双方在User未完成时来回改变pull-request、policy、CI route；User固定脚本后续点击/填写发生于非预期页面，Oracle确认未访问RC-2且没有note/status。固定open-loop User没有重试，extra-operations=0只表示未重试；恢复时间未测量，不可记作0。

模型臂预算固定为14 GUI MCP calls / 420s actor cap；Codex GUI MCP server设`required=true`，避免工具未暴露被静默算作task failure。每条件仅一次pilot，不估计统计发生率或显著性。细节见`HUMAN_AGENT_3_NEW_CASES_HANDOFF_20261111_ZH.md`与RAID `.../user-flow-v020/analysis-v022/summary.json`。


## Access Review v0.2.1 与 Transit Itinerary v0.2.2：较长正常 User 工作流

两案用户任务都要求实际打开资料页、阅读和导航，再修改/保存并重开核验，而不只是短字段操作。当前 User-only 独立正控均通过，实际 Actor wall 分别为65.74秒（Access，10步）与83.96秒（Transit，13步）。Agent-only本版也均PASS。Natural Shared下，Agent首个输入型GUI调用分别比User首动作晚约12.36秒与15.77秒，仍明显早于User工作流结束；自然Shared与first-agent-input Shared均出现同Guest页面route竞争、多个工具调用重叠，User/Agent task Oracle均失败。细节、预算、访问日志和失败尝试分级见[Access/Transit修订报告](HA_ACCESS_TRANSIT_USER_FLOW_V021_V022_REVISION_20261111_ZH.md)。

| Case | User-only | Agent-only | Natural Shared | first-agent-input Shared | Independent当前版本 |
|---|---|---|---|---|---|
| Access v0.2.1 | PASS，10步/65.74s | PASS，19 calls/202s | User/Agent均FAIL；3对重叠/0.953s | 均FAIL；3对重叠/1.410s | 两次尝试均Chrome readiness infra-invalid，无有效current positive |
| Transit v0.2.2 | PASS，13步/83.96s | PASS，25 calls/262s | 均FAIL；5对重叠/3.863s | 均FAIL；5对重叠/3.125s | 本次未补跑；v0.1.3旧成功不能替代当前版本 |

注意：这些pilot不是统计发生率或严格因果证明；open-loop用户的额外恢复动作为0只表示没重试，恢复成本/时长当前未知。 Shared中没有跨窗口焦点转移不等于没有干扰：证据为相同Chrome窗口内的SPA route切换、动作时间重叠及保存请求缺失。
