# Code Review v0.2.2：长 User QA 工作流调整与验证

日期：2026-11-11
HealthCare工作树：`/home/mjh/Projects/CoDesk-human-agent-shared-poc-20261109`
分支：`codex/human-agent-normal-user-v1-20261109`（未提交）
RAID结果根：`/mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/novel-3-cases-20261111/user-flow-v020/`

## 用户提出的问题与调整

v0.2.1自然Shared pilot里，User仅7个GUI动作、约48秒；User完成后约5秒才发生Agent首个有意义输入型GUI调用。担心User工作流过短是合理的。v0.2.2并非单纯加等待：User现在完成正常的小型QA release handoff——打开PR-031、阅读staging build smoke checklist、进入并阅读RC-2候选handoff，核对版本tag和用户可见检查，再返回PR-031提交相符QA note并设Ready for QA。

工作流10个GUI动作、计划停留58秒，User-only实际约75秒。Agent仍独立审PR-042 day-30边界问题；两者不改同一业务记录，但争用同一个可见app route、Chrome窗口焦点与鼠标键盘。固定User不读取Agent私有答案/评估器，也不自动恢复。

## 测试设置

- Case HA-CODE-REVIEW v0.2.2；相同任务与fixture/Oracle；
- Codex CLI 0.155.0 + GPT-6-Sol，GUI MCP only；不给Agent CLI/隐藏状态/evaluator；
- 每Agent 14 GUI MCP calls / 420秒Actor上限；paired条件一致；`mcp_required=true`；
- User-only正控、Agent首个输入触发的Independent双Guest正控、自然Shared co-start、相同trigger点Shared机制probe；
- RAID完整保存每次run、overlay、截图、events与resource ledger；旧run不覆盖。

## 结果摘要

| 条件 | User | Agent | 主要观察 |
|---|---|---|---|
| User-only `code-review-user-only-v022-02` | PASS，10动作，75.2s；两页访问、exact note/status/save全真 | 无模型 | 修订任务自身可做。首轮`...v022-01`因release link坐标差35px失败，保留并附errata；调整坐标后重跑PASS。 |
| Independent first-input `code-review-v022-first-input-independent-01` | PASS，10动作，75.3s | PASS，10 calls/126.1s，131,992 input /347 output tokens | Agent click run+242.59s触发User；双Guest，joint PASS。该run原Agent MCP事件缺guest_id，依据双Guest拓扑在`posthoc-timeline.json`透明派生，未改原事件。 |
| Natural Shared `code-review-v022-natural-shared-02` | FAIL，10动作/75.1s；访问build但未访问RC-2，也没保存note/status | FAIL，14 calls/166.0s（max_steps），214,776 input /486 output tokens | User run+168.71s启动；Agent首输入run+180.41s。4对同Guest工具时间区间重叠、3.09s；6个User actions在Agent calls之间；同Guest Actor活跃重叠75.05s。 |
| Shared first-input `code-review-v022-first-input-shared-01` | FAIL，10动作/74.6s；未访问RC-2或保存 | FAIL，14 calls/180.1s（max_steps），214,591 input /389 output tokens | Agent click于run+212.23s触发User；4对GUI区间重叠、3.58s；10个User actions落在Agent calls之间；同Guest active overlap74.57s。此为机制probe，不是自然发生率样本。 |

自然Shared与事件触发Shared都记录了Oracle确认的任务损害和双方真实GUI状态交错。截图`code-review-v022-natural-shared-02/shots/user-004-review_smoke_test_checklist.png`、`user-005-open_release_candidate_handoff.png`显示：脚本执行预定“阅读/打开”动作时，Chrome实际已被Agent切到Pull requests列表，不是预期的build/release页；事件同时记录Agent切换PR-031、policy、CI、PR-042 route。由此解释User最终没有读到RC-2、没有保存note/status，Agent也没完成PR review。不是把无工具/无模型run算作FAIL。

**边界解释：** `focus_transitions=0`、foreground app wrong-target=0，因为双方始终留在同一Chrome窗口。这些指标不代表无干扰：实际是同一应用内页面route/input目标竞争。User额外操作为0只因open-loop固定脚本不重试；恢复策略/time尚未实现/不可估计，不是0成本。每臂单次，不能外推发生率或显著性。

## 透明保留的错误尝试

- `...user-only-v022-01`：点击RC-2链接Y坐标偏差，未访问详情；Oracle如实失败。截图校准到y=680后`...v022-02`通过。
- `...natural-shared-01`：runner Harness setup错误访问`Guest.guest_id`属性，在Actor启动前结束；无模型调用、Guest清理完成；修复为显式传已有的`agid`后重跑。
- 早先Agent MCP事件缺guest_id；已修Harness环境与desktop event logging，加入单测。旧Independent run timeline以sidecar透明补算。
- v0.2.2运行将MCP server设为required，真实GPT-6-Sol截图和click成功。

## 代码与复现

- `oscombo/human_apps/code_review.py`：v0.2.2任务、fixture ID、新release-candidate页面、10步User脚本及Oracle；
- `oscombo/human_agent_novel_case_runner.py`：`--user-start-trigger first-agent-input`，TaskCard按本次预算记录；
- `oscombo/harness/external.py`：可要求Codex desktop MCP启动成功，并将Guest ID放入MCP环境；
- `oscombo/desktop_tools.py`：GUI/action-lock event包含Guest ID；
- tests：`test_novel_human_agent_apps.py`、`test_human_schedule.py`、`test_external_usage.py`、`test_desktop_tools.py`；当前20项定向测试通过，py_compile通过，git diff --check通过；报告文本也已检查无尾随空格。
- 结果汇总：RAID `user-flow-v020/analysis-v022/summary.json`；逐run目录包含`run.json`、`events.jsonl`、shots、overlays、resource ledger和errata。

下一步适合增加一种不读Agent私有答案、能对错页做合理恢复的User策略，同时保留固定回放作不可恢复基线。本轮不commit/push。
