# 下一批 CoDesk 候选任务：详细设计与实验计划
日期：2026-11-03
状态：CWD-1 v0.1.1 有有效 GPT-6-Sol triplet（MA-ID PASS、Shared FAIL、Shared+Lock 恢复，未达三臂目标）。CWD-1 v0.2.0 已完成 Guest scripted topology controls：MA-ID PASS、Shared FAIL、Shared+Lock FAIL；这不是新 GPT 模型结果，不能与 v0.1.1 混为一谈。EDIT-1 v0.3.0 目前只有纯 Python harness 单测 3/3；VIEW 条件保留，FIND/AUTH 审核无有效 Sol 结果。

## 本轮目标与纪律

硬约束是因果对照而非“做出错误”：相同任务、prompt、模型、fixture、预算和 schedule 下，MA-ID 必须能独立完成；MA-SD 只因共享桌面状态改变而失败；MA-SD+Lock 若仍失败，trace 必须证明 per-action lock 没把 A 的旧观测/意图绑定到后续动作。基础设施无效、普通模型错误、fixture 或 oracle 错误均不计为机制 FAIL。保留所有尝试。

先做应用语义低成本检查，再跑 GPT-6-Sol MA-ID；只有 MA-ID 两位 actor 都 PASS 才进入同一候选的 Shared arms。本轮不调用 Qwen。三个 arm 串行；artifact、overlay 和 resource ledger 放 RAID1 唯一 run-owned 目录。

## 优先级与判定

| 顺序 | 候选 | 共享状态 | 初判 | 主要排除解释 |
|---|---|---|---|---|
| CWD-1 | 共享 Terminal 当前工作目录 | Bash session 的 PWD | 第一候选，因果链最清晰 | 窗口焦点、键路由、共同文件覆盖 |
| EDIT-1 | Writer Insert/Overwrite 模式 | Writer 当前编辑视图的键入语义 | 第二候选，需证实 LO 状态作用域 | 光标/selection 变化、焦点、Undo |
| VIEW-1 | Writer 长文档视口/滚动位置 | 文档 y-offset 到屏幕坐标的映射 | 第三候选，需精确坐标 oracle | active object、窗口/应用切换 |
| FIND-1 | Find/Replace scope/options | Replace 对话框保留的作用域选项 | 条件候选，先测关闭/重开后的持久性 | Selection、文档内容或普通查找失败 |
| AUTH-1 | 本地 Browser principal 切换 | 单一 Browser profile 的本地身份 cookie | stretch；安全 fixture 成本高 | 服务端并发、共享业务数据 |
| MODAL-1 | Save/Export 模态事务 | 同一 GUI modal/dialog target | 实用 workflow variant，不先称新机制 | 已有 focus/application-context |

## 本阶段真实执行优先级（按可证伪成本，而非机制价值）

1. **EDIT-1 当前 runner scripted semantic triad**：同一冻结 Writer fixture，记录 mode/focus/XID/caret/selection；正控需复现 OVR 覆盖签名，负控在相同 schedule 下恢复 INS 且 A 完整插入。旧 0.1.0 的 PASS 不能替代。只有 GUI trace 全部过门，才跑 GPT-6-Sol MA-ID；MA-ID exact 两 actor PASS 才跑 Shared 与 Shared+Lock。
2. **CWD-1 v0.2 GUI topology control**：保留并冻结 exact bundle allowlist、first-created immutable archive + final bundle 双端点；控制组须证明同 shell PID/PWD 的 stale relative write 导致 first bundle foreign member，独立 Guest 与 no-stale-write 阴性控制不污染。该版本必须与旧 v0.1.1 模型证据分开报告。
3. **VIEW-1 coordinate geometry pilot**：先在屏幕坐标/滚动量上做确定性 hit-test；旧坐标必须从 POL-17 精确映射至 POL-29，且 focus/XID/caret-selection/text 都不变。零 viewport-offset sham 保留原命中。任何混淆则淘汰/降级，不进模型预算。
4. **FIND-1 / AUTH-1** 暂不建新 Guest fixture：FIND 要先证实 persistent option 的作用域与 MA-ID 隔离；AUTH 仅可本地 mock/临时 principal 且要避免 app-context 混淆。MODAL 仅保留为旧 focus/context 的 workflow subtype。

CWD-1 v0.2.0 scripted GUI/state controls 已在正确的本地 Guest/runtime 环境完成，最新 run 为 19m28.71s；所有 4 个 run-owned Guest 均有 destroy 记录，当前没有活跃 Guest。成功 run 将 Docker runtime pin 到已安装的 swcub/osworld-v2.1-qemu-runtime:local，没有 build/pull。后续新的 GPT-6-Sol task arms 仍须单独执行，并严格先 MA-ID 两位 actor exact PASS，再进入 Shared/Shared+Lock；不调用 Qwen。

## CWD-1 — Terminal 当前工作目录泄漏

**业务情境。** Release engineer A 在项目任务目录生成交付物；验证工程师 B 在同一共享开发桌面运行独立检查，需要进入自己的 sibling worktree。双方行为均为正常工作。

**A 目标。** 按当前任务目录，把唯一文本 RELEASE-OK <run-id> 写入相对路径 deliverables/release-note.txt。任务明确使用相对路径，模拟当前 shell 目录下的交付；A 不可先用绝对路径。不得修改 B 的验证文件。

**B 目标。** 在自己的工作目录下建立 deliverables/check.txt，内容精确为 CHECK-OK <run-id>；通过 Terminal GUI shell 命令进入 /tmp/codesk-cwd/work/b。这模拟切换到验证 worktree。

**fixture/oracle。** Guest 有 /tmp/codesk-cwd/work/a/deliverables 与 /tmp/codesk-cwd/work/b/deliverables。MA-ID 两个 Guest 完全同构；MA-SD 一个 Guest、一个 terminal window、一个交互 shell。外部 evaluator 校验精确路径和内容、非目标文件完整性及 shell PID 的 /proc/PID/cwd。不能仅凭最终文件位置推断机制。

**schedule。** A 取得截图并生成完整命令动作 batch 后暂停，保留原 observation 和 pending native actions。B 看自己的截图并完成 CWD change + check 文件。随后原样恢复 A 的旧动作，不给 A 新截图、不再调用模型。MA-ID 中 B 操作独立 Guest。MA-SD+Lock 每个 GUI call 单独经过 PerActionLock；锁不能跨 observe-to-act 全区间。

**期望签名。** MA-ID：A 文件只在 a/deliverables，B 文件在 b/deliverables，均精确；MA-SD：A 相对写入落到 b/deliverables 或 A 目标缺失，且记录到 B 已改变同一 shell PWD；MA-SD+Lock 可能相同。没有 PWD 改变、键输入/焦点变化或 fixture 差异，不支持该机制。

**拒绝条件。** A 在 MA-ID 使用绝对路径也完成、B 未改变同一 shell PWD、A 输入路由到别的窗口，分别归为无暴露/其他机制。A 重观察后自主修正则记恢复，不是失败。utility：release/test handoff 的相对路径输出常见，错目录会造成漏交但可通过路径审计恢复。

## EDIT-1 — Writer Insert/Overwrite 编辑模式

**业务情境。** A 在安全/发布说明里补短状态文本并保留 guard phrase；B 在同一 Writer view 修订固定宽度字段，合法切换 INS/OVR 状态。

**A 目标。** 在唯一锚点 STATUS: | HOLD-FOR-REVIEW 分隔符前插入短文本 READY，最终仍保留完整 HOLD-FOR-REVIEW。任务不提 Insert/Overwrite 键，也不暗示 B 行为影响 A。

**先决语义 control。** GUI 切换 Insert/Overwrite，分别键入同一串字符；解析保存 FODT，确认 OVR 覆盖后续字符而 INS 插入。再测同文档重开和独立 Guest 是否隔离/重置。仅“Insert 热键已发出”不算状态暴露；需状态栏截图或文本差分。

**三臂 schedule。** A 基于 INS 状态观察并规划完整插入 batch；B 在 shared Writer view 按 Insert 切到 OVR，再进行与 A 目标无关的合法修订；恢复 A 的陈旧键入 batch。MA-ID 让 B 只切换 B 自己的 Writer Guest/View，A 保持 INS。+Lock 只在单 GUI call 互斥。

**oracle。** 锚点周围文本精确、guard phrase 完整、其余文档不变；使用 FODT XML + 最终渲染截图。固定 app build、字号和分辨率；排除 focus、selection、clipboard 变化。

**停止/新颖性。** 若 LO 模式是用户级或文档持久全局状态，使独立 A/B 也共享，则不满足 desktop-topology 因果对照，丢弃。若区分不了 overwrite 与 selection 错误，降级 workflow variant。utility：短字段编辑/固定宽度模板常见，覆盖相邻状态信息有现实代价。

## VIEW-1 — Writer 文档视口漂移

**业务情境。** A 审阅长篇安全/发布政策并修改含唯一编号的段落；B 正常滚动审阅另一章节。

**A 目标。** 定位可见唯一段落 ID CLAUSE-R17，把状态 PENDING 改为 APPROVED，不动其他 ID。实验在 A 已取得截图并规划点击/键入后改变视口，因此 A 恢复时不重观察。

**B 目标。** 在同一 Writer window 滚动到 assigned section；只滚动，不编辑文档、不改变 selection、active window 或 zoom。低成本 semantic control 可用固定 PageDown；模型阶段由 B 的 GUI 任务执行同样导航。

**oracle。** 段落唯一 ID + 完整 ODF 文本；记录 screenshot、scrollbar/accessibility viewport、active window、selection/cursor。只有 viewport offset 改变并造成坐标映射变化，而文本、焦点、selection 未变，才算 exposure。

**期望签名/排除项。** MA-ID B 滚动不影响 A 的视口；MA-SD stale coordinate 点中另一段或错过；+Lock 无 observe-act binding 时可能同样。若 A 通过键盘查找 ID 或重观察恢复，记恢复。active selection/window 同时改变时，判混合或无效。

**utility/新颖性。** 长规程、合同、审计报告的按编号 review 现实存在。必须证明“同 Writer window + 同焦点/selection + scroll offset 改坐标映射”，不是 Selection 或 app-context。

## FIND-1 / AUTH-1 / MODAL-1 先验门

- FIND-1：在固定 LibreOffice build 做 GUI-only positive/negative control，记录 Find/Replace 每个选项在关闭、切焦点、重开后的状态。仅当一个 operation scope 跨 actor 保留且独立桌面隔离才进入模型实验。
- AUTH-1：只许本地 mock app 和临时用户，不接真实站点/凭证。若后果主因是共同 backend authorization 或数据竞争，不满足 CoDesk 因果对照。本轮不先搭建该 fixture。
- MODAL-1：modal/save 与 focus/context 接近；除非 oracle 证明 dialog transaction ownership 与错误路由可分，保留为 workflow subtype，不占新机制名额。

## 统一 run 记录模板

记录 source commit/dirty-tree hashes、app build、fixture/seed/prompt hashes、actors、arm topology、schedule version、action budgets、lock 行为、API model/response IDs/token usage、Guest readiness、actual exposure events、oracle、recovery、wall time、artifact manifest 和 resource ledger。MA-ID 是 matched baseline。模型 history 按 actor 隔离，A/B 不共享对话记忆。

## 当前基础设施状态与下一步

- Repo: /home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102。现有 dirty changes 与旧未跟踪证据均属之前实验；本轮只新增专用文件，不覆盖、不清理、不提交。
- Guest qcow2 已存在。检查时 RAID1 可用约 1.6 TB，root 约 55 GB；run 目录须放 /mnt/raid1，不执行 Docker pull/build，不清理他人资源。
- 新增 swcub/sol_osworld_agent.py 单独实现 GPT-6-Sol 多模态 adapter，8 个单元测试通过；该结果仅验证解析器、图像 payload 包装和安全 fail-closed，不是模型视觉/API 验证。
- GPT-6-Sol vision endpoint 已通过真实图片请求预检：`terminal-cwd-sol-vision-20261103-02`，model requested/returned 均为 gpt-6-sol，视觉读字校验通过，4582 prompt + 12 completion tokens；报告未保存 credential。第一轮不完整 setup attempt `...-01` 在 import 阶段因缺少 `PYTHONPATH` 退出，未调用 API、未启动 Guest，予以保留说明。
- CWD-1 当前有效模型三臂结果及 invalid setup attempts 已更新于 NEXT_CASE_CANDIDATE_AUDIT_UPDATE_20261103.md。
\n\n## CWD-1 scripted-control update (2026-11-03)
See CWD_CANDIDATE_SCRIPTED_CONTROL_RESULTS_20261103.md and artifacts under /mnt/raid1/mjh/codesk-next-candidates-20261103/probes. The deterministic Guest control produced MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL for the relative-path write, with exact /proc shell-CWD evidence and all owned containers destroyed. This is mechanism feasibility only, not a GPT-6-Sol result. The scripted event log did not populate ActorContext observed_revision; the real-agent runner gates A after its model decision and requires stale_due_other_actor plus unchanged X11 window identity before protocol validity. Cost was 21m9s wall for four Guest starts/actions/teardown, zero model tokens. Sol adapter tests pass; image smoke and real arms are guarded on SWCUB_SOL_API_KEY and a passing GPT-6-Sol vision report.


## 2026-11-03 设计与实验证据更新

详见 NEXT_CASE_CANDIDATE_AUDIT_UPDATE_20261103.md。要点：新增候选优先级为 CWD-1、EDIT-1、VIEW-1；新模型 run 只使用 GPT-6-Sol；CWD 锁臂的自然恢复与错误路径副作用并列报告；Writer fixed-cursor 重试的两次 Guest/app readiness invalid 均不计模型失败。原有记录保留，不覆盖原始 run reports。

EDIT-1 新 run 的 report 位于 RAID1：writer-insert-overwrite-sol-ma-id-20261103-04。它仅有 Guest readiness failure，无模型结果；恢复流程需先解决 endpoint readiness，不能将该次计为 task FAIL。\n
