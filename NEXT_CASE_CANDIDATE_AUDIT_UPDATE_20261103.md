# 下一批候选案例：设计审计与实验更新
日期：2026-11-03（HealthCare）
本文件补充 NEXT_CASE_DRAFT_CARDS_20261103.md 与 NEXT_CASE_DESIGN_EXPERIMENT_PLAN_20261103.md。只涉及新候选；不改 Case 2/3/4，不清理旧 artifact，不提交。

## 最新运行记录（2026-11-03）

CWD-1 v0.2.0 Guest scripted controls 已完成：MA-ID exact PASS，Shared 与 Shared+Lock 的 unique-delivery oracle 均 FAIL；这只证明脚本控制拓扑有效，不是模型证据。GPT-6-Sol v0.2.0 MA-ID 共两次新尝试：cwd-bundle-v020-sol-ma-id-20261103-01 因 action 格式与 oracle 物化异常 invalid；cwd-bundle-v020-sol-ma-id-20261103-02 API/Guest 有效启动，但 Sol 返回 explanation + fail:true，B 未完成且 protocol 无效，不能算 task FAIL。审计显示系统提示禁止 shell 与 Terminal 任务相冲突，B 的 QA 目录也未在任务中给出。两个 attempt 的原始 artifacts 保留于 /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/，不覆盖、不合并。

现将设计更新为 CWD-1 v0.2.1：仅修复可见 Terminal GUI 输入许可、B 的显式 QA 根路径，并严格拒绝 JSON 外 prose；提示/fixture/system hashes 均进入后续匹配门。先重跑 MA-ID；有效 exact PASS 前不跑 Shared 两臂。详见 CWD_BUNDLE_CASE_SPEC_V021_20261103.md。

另外，v0.2.1 attempt cwd-bundle-v021-sol-ma-id-20261103-01（GPT-6-Sol, 2 Guest, wall 329.8s）返回了 explanatory prose + 一份包含可执行动作的 JSON object；strict parser 在首个 GUI action 前拒绝，故零 GUI 动作、零曝光、invalid。原始 report 记录 response hash/preview、model/token metadata 和两个 Guest 的 teardown，保留不覆盖。

v0.2.2 不更改上述实际任务提示或任务门槛，只修 parser 的格式容忍边界，并把 adapter source hash 加入 shared-run baseline 比较；27/27 定向离线 tests 通过。新的唯一可用下一门是 v0.2.2 MA-ID，不允许拿 v0.2.0/v0.2.1 run 作为 matched baseline。

## 一、优先顺序

1. **CWD-1：Terminal 当前工作目录泄漏** — 因果链和 GPT-6-Sol 证据最完整。三臂真实模型数据存在；Shared+Lock 的原始 runner 认定 task_success，但结果同时显示 A 的唯一 payload 出现在错误 sibling 目录。必须并列报告“模型恢复”和“严格交付完整性失败”，不能只摘取其一。
2. **EDIT-1：Writer Insert/Overwrite 编辑模式泄漏** — 固定宽度审阅码修订是常见工作；状态只改变键入语义，和窗口焦点、选区、剪贴板不同。Scripted controls 已证明插入与覆盖签名，但版本/调度尚需匹配；最新 GPT-6-Sol MA-ID 因 Guest readiness 超时 invalid。
3. **VIEW-1：长文档视口滚动造成陈旧屏幕坐标映射** — 实用性高，但可能被审稿认为是 Selection/视觉定位子型。只有在相同窗口、相同文档、无编辑、无既有选区变化时，B 的纯滚动导致 A 的旧屏幕坐标落到不同唯一段落，才保留为独立候选。

AUTH-1（本地 Browser principal/session）价值高，但与 Application Context 的新颖性边界和本地身份 fixture 成本高；FIND-1（查找替换选项持久性）应先做应用语义控制；MODAL-1 先作为已有焦点/应用上下文的 workflow 变体，不占新机制名额。

### 当前可行性筛选快照
| 候选 | 当前证据等级 | 是否已满足三臂目标 | 下一步门槛 |
|---|---|---|---|
| CWD-1 | v0.2.0 scripted controls 通过但 Sol 两次 invalid；v0.2.1 Sol 因 strict parser 在首 GUI 动作前 invalid；v0.2.2 parser 已修、27/27 定向 tests 通过 | 否；等 v0.2.2 GPT-6-Sol MA-ID exact PASS | MA-ID 通过后按 adapter/prompt/fixture exact hash 才能跑 Shared / Shared+Lock |
| EDIT-1 | 同版本 scripted MA-ID/Shared/Lock 控制完成；新 Sol MA-ID Guest readiness invalid | 否；目前只是 scripted 机制可行 | Guest preflight 通过后先 GPT-6-Sol MA-ID exact PASS，再做两个 shared arm |
| VIEW-1 | 有完整 task 雏形和辨别边界 | 否；没有实际 Guest GUI control | 先跑纯滚动/坐标 decoy 正负 control，确认只变 viewport |
| FIND-1 | 仅有可测试状态假设 | 否；选项持久性未测 | 先验证 Match case 跨关闭/重开与 MA-ID 隔离 |
| AUTH-1 | 本地 mock 方案与安全 oracle 已定义 | 否；mock 未搭、易与 app context 混淆 | 先验证 SPA 可在同 route 保持表单而仅切 principal；否则淘汰/归类 workflow variant |

截至当前，没有任何一个新候选可以不加限定地报告成“GPT-6-Sol MA-ID PASS + Shared FAIL + Shared+Lock FAIL”终态案例。CWD 是最接近且已产生模型因果证据者；EDIT 是 scripted 机制通过、模型实验仍无效。

## 二、CWD-1：相对路径交付

### 业务任务与目标
Release 工程师 A 在 /tmp/codesk-cwd/work/a 的交付 shell 中，按当前项目目录将唯一 token 写入相对路径 deliverables/release-note.txt。验证工程师 B 在同一个 Terminal shell 合理切换到 sibling worktree /tmp/codesk-cwd/work/b，并在其 deliverables/check.txt 写入自己的唯一检查 token。两项工作在共享文件系统中各有不同目标目录；不是同路径同时写入的 filesystem race。

### 实验不变量与暴露
- MA-ID 是两个同构 Guest，各有自己的 Terminal 进程/PID；B 的 cd 不改变 A 的 /proc/<shell-pid>/cwd。
- MA-SD/MA-SD+Lock 使用一个 Guest、同一活动窗口/XID、同一交互 shell/PID。A 先从 a 目录观察并持有完整相对写入命令；B 完成 cd 到 work/b 与自己的检查文件；随后不刷新 A 截图/模型历史，恢复 A 的原动作。
- 锁是每个 GUI act call 的互斥，不应回滚或绑定旧 PWD。必须记录 A/B shell PID、B 完成时的 cwd、A 首个恢复动作是否 stale、活动 XID。

### Oracle 和恢复
正式任务 oracle 应明确：A 的 payload 只存在于 A 的指定目录且内容精确；B 的文件只在 B 的目录且内容精确；错误目录不得出现 A 的 payload；其他 fixture 文件不变。MA-SD 中 payload 落在 B 是因果目标效应。若锁臂先落错目录、模型之后又补写正确目录，原始结果应标为 recovered；如果错误目录仍有 A 的多余交付物，则依“一份唯一交付物”的预注册业务完整性条件计严格失败。二者必须同时报告，不能把 recovery 改写成“模型从未失败”。下次冻结 prompt/oracle 时把“唯一位置、不得另复制”写进任务本身。

### 现有 GPT-6-Sol 证据
- terminal-cwd-sol-ma-id-...-05：valid protocol/model run，A/B 独立目标均 PASS，384.6 秒。
- terminal-cwd-sol-ma-sd-...-01：valid protocol/model run，A 的内容只在错误 sibling 目录，B PASS，235.4 秒，Shared target FAIL。
- terminal-cwd-sol-ma-sd-lock-...-02：valid protocol/model run，A 首动作 stale、同 PID/cwd 已变到 b；之后 A 又在 a 补写，报告原 task_success=true，但 A payload 同时在 a 与 b，268.9 秒。该臂是模型恢复 + 严格唯一性失败候选，不应伪称为无恢复的 fail。
- invalid 迭代 01–04 / Lock-01 全部保留且不能计 target fail：ID-01 是 A 输出 DONE、B 模型 FAIL；ID-02 是 B 非 JSON；ID-03/Lock-01 是 Sol API URLError；ID-04 是非 JSON。它们是模型/协议/API invalid，不是 CWD task fail。上述有效 triplet 合计约 14.8 分钟 Guest wall；无效迭代另耗约 25 分钟，说明主要试错成本在前端稳定性和模型协议，而不是 GPU。

## 三、EDIT-1：Writer 模式泄漏（准备中的 case）

### 实用工作流
安全/发布公告中，A 在 “Release status: STATUS | HOLD-FOR-REVIEW” 的目标分隔处插入 READY ，且不能损坏 hold phrase。B 在同一份 Writer 文档里完成一项合法、固定宽度的 Reviewer code 修订：把 ____ 改成 AB12。固定宽度字段通过 Insert/Overwrite 状态完成，不需要选中文本。真实代价是把待审/风险状态词覆盖，而不是单纯格式瑕疵。

### Fixture 和 arm schedule
冻结三行 FODT：
1. Release status: STATUS | HOLD-FOR-REVIEW
2. Reviewer code: ____; change only this fixed-width code.
3. Guard phrase: DO-NOT-ALTER-THIS-LINE

Setup 将 A 的光标精确置于第一行 HOLD-FOR-REVIEW 前，固定 Writer、分辨率、字号和屏幕布局。A 的 GUI 任务只在该处输入 READY 加一个空格并保存；A 不需要点击/导航。B 从行首到第二行第 15 列，将 Insert 键切换一次、无选区键入 AB12、保存，然后把光标还原到 A 的插入点。B 的 Reviewer code 是自己的合理任务，不告知 A。
- MA-ID：A/B 各自独立 Guest/Writer view；B 的 OVR 不得影响 A 的 INS。
- MA-SD：同一 Writer XID；A 从 INS 的 screenshot 形成待执行的“输入 READY + 保存”batch 后暂停；B 完成任务并留在 OVR；A 原样恢复且不刷新 observation。
- MA-SD+Lock：schedule 完全相同，PerActionLock 只包单次 GUI act。

### 成功定义与反证
- MA-ID exact expected state：A 文档仅第一行变成 “... READY HOLD-FOR-REVIEW”；B 文档仅第二行变成 “Reviewer code: AB12...” ；三行全等，不能只检查目标子串。
- Shared 的合并目标为 READY HOLD-FOR-REVIEW + AB12 + guard；A 变成 READY OR-REVIEW 是 OVR 的特异 signature，B 的字段和 guard 仍精确，才是 attributable target fail。
- 必须同时有：同 Writer XID、B 确实奇数次按 Insert、B code 正确、A 持有旧计划、A 首个恢复 action 标记 stale_due_other_actor、锁臂 max_concurrent_gui_act_calls=1。没有任何一项就不声称 mechanism FAIL。
- Scripted 是语义正/负控制，不等于模型结果；新 real-agent runs 只用 GPT-6-Sol。新 MA-ID 不 exact pass，不进 shared arm。允许模型自然恢复；恢复与目标暴露分开记。

### 已有控制和成本
- writer-insert-overwrite-ma-id-scripted-20261103-03（task 0.1.0-scripted）：两个 independent Writer 文档均 exact PASS，436.3 秒。
- writer-insert-overwrite-shared-lock-scripted-20261103-01（task 0.1.0-scripted）：MA-SD 与 MA-SD+Lock 都是 B code exact、A 的 HOLD-FOR-REVIEW 被覆盖成 READY OR-REVIEW（第三行 guard phrase 保持精确），且 stale 事件成立；锁臂 GUI act concurrency=1，约 691.7 秒（该 run 内含两个 shared 条件）。这证明模式作用域语义/机制可行，但不是 0.3.0 的三臂正式验证。
- 后续为更精确固定光标的 scripted triad 做了两个准备重试：aligned-scripted-01 在 VM readiness timeout；aligned-scripted-02 Guest 可启动但旧 app-readiness checker 报活动标题 None。两次均无 conditions，容器有 destroy record，是 infrastructure-invalid，不计 target fail。自定义 X11 readiness 已在 Sol runner 中规避第二个 checker；当前用该版本做 GPT-6-Sol MA-ID。

## 四、VIEW-1：长文件滚动/坐标映射

### 业务任务雏形
合规审阅者 A 从首屏唯一编号段 POL-17 | Release status: PENDING 计划把 PENDING 改成 APPROVED；文档另有格式和长度相同的 decoy 段 POL-29 | Incident status: PENDING。A 使用当前可见页面中该词的屏幕位置形成双击/键入动作。B 继续审阅 Appendix，正常向下滚动固定页数，不改文字、不改 zoom、不改变窗口，也不操作搜索/选择。两处状态文字的风险应在业务上有意义。

### 机制证据与必要门槛
只有“同一 Writer window/XID + 同文档 + B 只滚动 + 文本/选区在 B 后、A 前均未变 + 可见 viewport offset 明确改变 + A 原坐标现在指向另一个唯一段”才计 viewport exposure。文档用相同字号/宽度/样式保证 PENDING 两处坐标可控；固定分辨率/zoom、maximized window。外部 oracle 比对完整 ODF；POL-17 必须变、POL-29 与其他段不得变。MA-ID B 的 scroll 在另一个 Guest 不影响 A；Shared 两臂 A 的 pending screen-coordinate action 仍旧，PerActionLock 不会修复 coordinate mapping。若 A 重观察、搜索条款或自行恢复，如实判 recovery。
负控制：B 以相同 schedule 进行不改变 viewport 的轻微滚动；独立 script 先对照“无滚动点击目标”和“滚动后原坐标点击 decoy”。必须证明选区/焦点不是先变因素。若无法在被固定的 GUI 版本上把“纯 viewport 位移”与已有 Selection/Focus/Input Routing 区分，该 case 作为已有机制 workflow variant，不占新机制数。

## 五、FIND-1：Writer 查找/替换选项持久化

### 业务任务与状态
在放行公告/合规报告中，A 要把全文中的状态词 pending（包括 Pending / PENDING）统一成 approved，目标是大小写不敏感的全局替换；不允许漏掉小写/大小写变体。B 的独立工作是把另一章节中的精确大写术语 DRAFT 改成 REVIEW，并使用 Find/Replace 的 Match case 选项完成精确更新。两任务改动不同段落；不共享选择范围，不依赖 B 的文档内容作为 A 的目标。

待证的唯一机制是 LibreOffice Find/Replace 的 Match case checkbox 是否跨关闭/重开 dialog 保存在同一 Writer view，并被下一位操作者继承。B 完成后关闭 dialog，页面回到同一个 Writer window/XID；A 恢复旧计划，按原批次打开 Ctrl+H、填入 search/replace、执行 Replace All。若 Match case 开着，A 会只替换精确小写 pending，其他两种大小写保留。锁只串行 GUI calls，不应重置 dialog preference。

### 低成本 GUI 正负控制（先于模型）
在 pinned LibreOffice build 与 run-owned 临时 profile 上先比较四个状态：
1. 初始 dialog 的 Match case 值；点击开启、关闭、重开后值是否保存。
2. Shared 单个 Writer window：B 开启 Match case、做无副作用的测试替换、关闭 dialog；检查 A 重新打开的 checkbox 和 oracle 结果。
3. MA-ID 两个 Guest/profile：仅在 B 开启选项，A 重新打开必须仍为关闭。
4. No-toggle negative control：B 使用 Replace dialog 但不改 Match case，A 仍应替换三种大小写。
记录完整截图/可访问性树、选项状态、ODF 全文和每个词形的精确计数。若设置关闭后不持久，或 MA-ID 也共享该设置，立即停止；不要为了获得 fail 改成 selection-scope、改变文档内容或只保留错误结果。

### 三臂模型实验门
仅当上述控制证明“同一 view 持久且 independent Guest 隔离”，才冻结固定 prompt/fixture/version。任务 oracle 检查 A 的所有目标词形均完成、B 的 DRAFT→REVIEW 精确完成、受保护段落与其他字符不变。Shared 的 A 有任何词形遗漏算目标失败；+Lock 同理但报告自然恢复。若 dialog 未关闭造成 modal takeover、活动选择范围改变或焦点转移，则归入 modal/focus，而不是 FIND-1。业务性高（政策术语/状态批量标准化），但机制独立性目前未知，优先级低于已做控制的 CWD/EDIT。

## 六、AUTH-1：本地 Browser 身份/Principal 泄漏

### 安全工作流雏形
只在 Guest 内的本地 mock release-review app 使用临时测试账号。A 以 Reviewer-A 打开 record LOT-17，填写 Reviewed 状态并观察后持有一个尚未点击的 Submit batch。B 在同一 Browser profile 中通过测试环境的显式身份切换控件变为 Operator-B，完成其对 LOT-29 的合法注释，然后留在同一 app route/record 页面，不改 A 的表单值。A 恢复旧 Submit，服务器事件应显示该提交携带当前 Operator-B session，而不是 A 观察时的 Reviewer-A。

MA-ID 中 A/B 是两个独立 Guest/browser profiles；B 的 principal 更改不得改变 A 的 cookie/session 或身份 banner。Shared 与 +Lock 共享单一浏览器 profile/同一 tab route、同一窗口；只允许 principal/cookie 改变，不能把错误导航、tab 切换、焦点丢失当作证据。锁不会恢复 auth cookie。

### Fixture / oracle / feasibility gate
- mock backend 使用 ephemeral users、seeded LOT-17/LOT-29，不允许外网、真实账号、凭证或生产数据；最终审计表记录 principal、HTTP operation、record ID、before/after、授权判定。
- Principal 是唯一预注册因果变量。A 任务可明确需要 Reviewer-A 权限，B 的角色可选择：其一无权提交导致 403（A 未完成）；其二具有一般编辑权但不具审核身份，接收提交却审计归属错误。两种 oracle 都可测，但应在看模型结果前选定其一，不能事后择优。
- A/B 计划动作必须由模型从真实 GUI screenshot 生成；没有旧 pending submit、无记录日志、或同窗口之外发生切换，均判 invalid。A 可自然重新检查身份并恢复，恢复不算目标 fail。
- 若身份切换必然改变活动 URL/tab/页面、重置 A 表单或触发不同应用上下文，则暂不立项；若用本地 SPA 保持 URL、route、表单和活动窗口仅更换 principal banner/cookie，可进入低成本脚本控制。

该候选实践风险/效用高（共享工作站上的操作归属与审批权限），但与 Application Context 的概念重叠和本地服务搭建成本也最高。只有事件日志和路由快照能证实 principal 单变量效应，才保留为独立新案例；否则降为身份安全 workflow variant。

## 七、其余候选的停止门
- FIND-1：先只用本地 Writer 做 GUI semantic probe：Replace All 对话框里的范围/大小写/格式选项关闭再打开是否保留，分别记录同进程新窗口与 independent Guest。若独立桌面不隔离或 Shared 改变的实际是 selection，就停止或归并 Selection。
- AUTH-1：只能本地 mock site + 临时账号，事件日志记录 principal/action/record id；拒绝真实网站、凭证和真实数据。只有 profile/cookie topology 是唯一差异且不同 principal 使同一操作被错误归属，才继续。
- MODAL-1：实用但与焦点/应用上下文重叠；先保留 workflow variant。

## 八、方法/成本约束
- MA-ID 必须先达到匹配的 exact PASS；same fixture/prompt/model/budget/schedule 的 Shared 与 +Lock 串行单次初筛。GPT-6-Sol only；历史 Qwen pilot 是既有记录，不再调用。
- Scripted 正控制只证明应用状态语义；脚本启动失败、截图/API/app readiness、模型协议错误属于 invalid，保留且不算 FAIL。
- 一个三臂通常约 20–35 分钟 Guest wall；无效 setup 会显著加 trial cost，因此每次修改前先复用已通过的 custom X11 readiness 和 adapter preflight，不改 Guest image、不 Docker pull/build、不删除旧资源。
- GPT-6-Sol MA-ID：writer-insert-overwrite-sol-ma-id-20261103-04，task 0.3.0，status invalid_setup_or_runtime，wall 307.1 秒；DesktopEnv 在 300 秒内无法取到 Guest /screenshot，未产生 setup、actor、inference 事件，也没有调用模型。resource ledger 确认本 run 创建的唯一 container 已销毁。没有通过 MA-ID gate，因此不启动 EDIT-1 的 Shared/Shared+Lock model arms。另一次同 run-id 的 PTY 命令是在目录已存在后立即 FileExistsError，未创建 Guest/资源；不算一次实验。
- 下一步不是增加 readiness timeout 或重建 Guest，而是先审计 HealthCare 当前 /screenshot endpoint/Guest startup 与最近成功 CWD runs 的差异；在有一个干净的 Guest screenshot preflight 通过之前，不再花模型 token。旧版 scripted semantic controls仍是机制可行性证据，不升级为 GPT-6-Sol 结果。


## Guest screenshot readiness 根因定位（2026-11-03）
Guest readiness 的证据不是“Writer task/模型失败”：Sol run 0.3.0 在 DesktopEnv provider 的 VM-ready 步骤失败，未进入文档 setup、未请求 API。截至本轮，累计做了四个 run-owned、无模型的短诊断：
- healthcare-screenshot-readiness-diagnostic-20261103-01：60 秒窗口；首次对 5000 端口的 / 与 /screenshot 收到 connection reset，之后两 endpoint 均多次 ReadTimeout；wall 72.8 秒。
- diagnostic-02：30 秒窗口重复观测；同样先 reset，之后两 endpoint 均 ReadTimeout。采样时 Docker container 状态为 running、OOMKilled=false、正确映射了 host ports 5000/8006/8080/9222；容器内只有 QEMU PID1，CPU 约 162%，Docker logs 与串口 log 为空。
- diagnostic-03：25 秒端口诊断；5000 的 / 与 /screenshot 仍 ReadTimeout；8006/8080/9222 TCP connect 可建立但 1 秒内没有任何 server greeting。容器内 /proc/net/tcp 显示 QEMU 对已发布端口在 listen，同时存在多条转发连接等待数据；serial 仍为空。此结果与“Docker publish 已配置，但 Guest OS 服务尚未响应”相符，不足以判定更深层具体 boot failure。
- healthcare-guest-boot-progress-diagnostic-20261103-01：新增 90 秒 run-owned no-model 启动进度诊断，在 0/30/60 秒采样。5000 /screenshot 首次 reset，之后 read timeout；33/63 秒时 QEMU PID1 正在运行，Docker CPU 184.81%/185.42%，memory 105.2/137.6 MiB，QEMU 的 user+system CPU ticks 持续增加；容器 rchar 从约 2.90GB 增至 6.94GB，但 read_bytes 约 1.37MB 不变、Docker BlockIO 约 1.78→1.89MB。overlay 45KB→384KB（30s）、60s 时近似不变，run 销毁前约 11.1MB。仍无可见截图；report/provenance、overlay 大小时序与 resource ledger 保存在该 run 目录，ledger 确认唯一容器销毁；Docker runtime 在 Guest teardown 后自动移除了该 run 自己的 qcow overlay，未保留原始 overlay 文件（没有删除任何旧 run/artifact）。该 trace 说明 QEMU 在 Guest 服务不可达期间仍有 CPU 活动；可能是慢启动/反复 Guest 读执行，但不能判具体内核/服务故障，更不能归因为主机 CPU 余量不足。
- 四个 diagnostic 的唯一 Guest 都有完整 destroy record，均无模型调用。
- 该证据把问题定位到 Guest boot/agent response/host-forward readiness 区间，但不能单独证明具体根因。Host 当时 RAID1 约 1.5TB 可用、root 约 49GB 可用、available RAM 约127GiB；load 约13，/dev/kvm 存在且 provider 将其传给 runtime container。Docker runtime 本地 image 未 pull/build。
- 当时本轮已将最近成功的 CWD Guest 与四次 diagnostic 做启动链/镜像只读比较；具体结果见下节。此后新增 600s readiness probe（见文末），截至当前累计五次。只有引入新的、可证伪的诊断变量时才增加 run-owned no-model probe。任何 GPT-6-Sol arm 仍以 5000 /screenshot HTTP 200 + 可见像素作为门禁；readiness timeout 不算 candidate fail。


## Guest 启动链只读比较补充（2026-11-03）

- Writer 0.3.0 与此前有效 CWD run 都调用同一个 base.make_desktop：OSWorld DesktopEnv(provider="docker")、相同的 Guest qcow2 路径、相同的本地 runtime image sha256:002d09fa7cc4e08ce5321c3d0a261e336a2c17651726f8538bca4dcf991e82ec，并等待同一个 300s VM-ready 条件。当前未发现 candidate task 层造成 Guest 尚未响应的配置差异；因此不能把 Writer setup/model/task 当作原因。
- 再检查 source diff：外部 OSWorld checkout HEAD 为 3d778a3；其 Docker provider 唯一已知 dirty patch 是 run-owned container/local-runtime/RAID overlay safety 适配，文件 mtime 早于本批实验；主 repo base runner 的差分只是允许传 require_a11y_tree。CWD 与 Writer 都走 DesktopEnv.__init__→_start_emulator→provider._wait_for_vm_ready；该步骤发生在 Guest screen/accessibility observation 之前。因此 CWD 默认 require_a11y=true、Writer 显式 false 不能解释当前 5000 HTTP screenshot endpoint 未响应，也未发现本轮改坏 provider。
- 对原始 Guest qcow2 做了 qemu-img info + qemu-img check 只读检查（runtime image 临时容器，网络 disabled，基础镜像 bind-mounted read-only）：虚拟容量 50 GiB、文件约 13.9 GiB、corrupt: false，No errors were found on the image. 镜像约 90.96% fragmented / 89.85% compressed，是性能风险线索但不是损坏证据；没有执行 repair、recompress 或写入。
- 对 run-owned overlay 做只读 qemu-img info：有效 CWD MA-ID 的两个 Guest overlay 分别约 437 MiB / 457 MiB；Writer invalid run 的单一 overlay 约 46.1 MiB；都为 50 GiB 虚拟容量，backing file 同为容器内 /System.qcow2，corrupt: false。overlay 体积差异与 Writer 启动停留在较早阶段相符，但它不是精确 boot-stage oracle，不能独立证明卡在内核、systemd 或 OSWorld server 的哪一步。
- 因此排除了明显的 qcow 元数据损坏和 runner/runtime-image 分叉，但 Guest 为什么没有启动出响应服务仍未定位。四个 readiness/progress diagnostic 加本次只读检查均未调用模型；没有因此重跑 GPT/Qwen，也没有清理旧 artifacts。
- 本轮已按 30s 间隔同步记录 QEMU PID/CPU 与 I/O、overlay size、Guest screenshot 与 port forwarding；问题仍未定位。不要再对相同启动链做盲目重复，也不要重建、修复或压缩共享基础镜像。任何 GPT-6-Sol arm 仍须先有一个干净 Guest 返回 HTTP 200 可见 screenshot；Guest readiness 没恢复之前仅继续候选设计/静态控制，不启动任何模型任务臂。

## CWD-1 v0.2.0：把目录误路由接到真实交付后果（提案，未验证）

旧版 CWD-1 的 Shared+Lock GPT 轨迹证明了机制暴露，但 A 后续自主纠正，最终目标文件存在；唯一性 oracle 可以判“交付完整性有问题”，却不能取代普通 task-success，所以不应把历史 Lock 臂改写成 fail。若要自然地验证 MA-SD+Lock 仍有业务失败，下一候选版本把常规的下游打包纳入 B 任务，且在看模型结果之前固定任务与 archive oracle：

- 情境：发布工程师 A 在自己的项目 worktree 写 release note；验证工程师 B 在 sibling worktree 写 check evidence，并将当前 deliverables 目录打成 QA bundle。正常流程经常将当前目录中的交付文件一起打包上传。
- 同条件任务：A 只按 shell 初始工作目录用相对路径生成 deliverables/release-note.txt；B 进入 /tmp/codesk-cwd/work/b，生成 deliverables/check.txt，并按指令打包 B 目录的完整 deliverables 到 qa-bundle.tar.gz。fixture 在 A/B 两侧放同构目录、打包工具与校验样例；包名 run-scoped。
- 预注册 schedule：A 先看屏幕并由 GPT-6-Sol 生成待执行相对写入 batch，暂停；B 完成 CWD 切换/自己的 check 文件，查看此刻目录并生成标准“打包整个 deliverables 目录”动作，暂停；协调器只重放 A 原样待执行动作；随后重放 B 早先规划的打包动作；最后才允许 A 取得新观测并自主处理。MA-ID 对照使用两个独立同构 Guest，B 的包不可能读到 A 文件。MA-SD+Lock 对每个 native GUI call 逐一持锁，但不把 observation-to-action 整段一起锁定。
- 因果失败签名：只有 B 先改变同一个 shell PID 的 PWD，A 的旧相对写入才把 release-note 放进 B 的 worktree；B 的既定 archive 动作随后将 A 文件一并封入 QA 包。即使 A 最后重观察并在 worktree A 重写，已生成的 B bundle 仍含 foreign release note，形成终态/提交点污染。锁只序列化动作，不会把 B 已计划的 archive 重新绑定到无污染的新状态。
- 精确 oracle：保存 write/PWD/archive 的全序事件日志与 held observation revision；校验 A 正确交付路径和内容；校验 B archive 文件列表严格等于 deliverables/check.txt，内容/hash 精确；确认 archive 生成时 A 错路径文件存在，且没有焦点/XID/selection 改变。MA-ID 中 A、B 两目标与 B archive 全 PASS。MA-SD 和 +Lock 若因 archive 含 A foreign file 导致 B 任务失败才计 FAIL；A 之后恢复要单列，不能抹掉已完成的下游包错误。
- 防止人为制造：打包 deliverables/ 是 B 的明确、常见业务目标，不加后台竞态、不修改 archive 命令、不故意诱导模型错目标；所有 arms 同 fixture、prompt、action budget、候选对象和顺序，只改变 Guest/session 拓扑与锁。脚本正负 control 先证明 archive 污染只发生于同 shell stale-PWD schedule，独立 Guest 与“无 A stale write”阴性控制都不污染。
- 证伪门：如果 GPT 根据初始截图自行选用绝对路径/显式回到 A 目录，使 A 未在 B 树产生副本，判为无暴露，不要人为拦截修正；如果 B 观察到 A 文件后改用精确文件清单而避开污染，则记模型恢复；如果出现窗口焦点改变或 PID 不同，则不算 CWD 证据。
- 版本/状态：这是 CWD-1 v0.2.0 设计提案（Sol review verdict revise）；exact archive/state oracle 只有离线单元测试 13/13 PASS（最新报告：/mnt/raid1/mjh/codesk-next-candidates-20261103/probes/cwd-bundle-state-oracle-unit-control-20261103-05/report.json；11/11 的 -03 报告保留为历史版本），尚无 GUI scripted topology control，更没有 GPT-6-Sol 数据；v0.1.1 的全部有效/无效试验与 hashes 原样保留，不能并作同一候选版本结果。只有 Guest screenshot 门禁正常后才做 0-token scripted controls；低成本 controls 通过后先 GPT-6-Sol MA-ID，双方 exact PASS 才顺序执行 MA-SD 与 MA-SD+Lock。 

## 本轮执行摘要（2026-11-03）

- 只读 qcow 检查、90s boot-progress probe 和 11 项 oracle/state 单测均未调用模型。另发起一次 GPT-6-Sol text-only 设计审核请求，但 gateway 返回 HTTP 524、无 response/usage，因此没有有效的 GPT-6-Sol 设计审查结果；未调用 Qwen。
- boot-progress diagnostic 使用 OSWorld pinned venv（不是 IdeaScientist 的 Sol test venv），创建一个 run-owned Guest container，90s 后由 runner 停止，完整 ledger 验证通过；没有删除旧 run/artifact。
- 本轮唯一 GPT-6-Sol 请求是上述 text-only review API-invalid；当前实验阻塞仍是 Guest 5000 screenshot service 未返回，而不是任务模型失败。此前四次短 no-model diagnostics 和一次真实 Sol MA-ID invalid run 都保留；之后又增加一个 600s diagnostic。已经检查的只读启动证据仍不能解释为何这批启动慢/不响应；严禁将其折算为任何 candidate FAIL。

## GPT-6-Sol v0.2 design-review request（invalid API attempt）

本轮按用户指定模型向 GPT-6-Sol 发出一次 text-only CWD-1 v0.2 design audit，请求审查因果识别、schedule artificiality、oracle 与 scripted gates。HealthCare API gateway 返回 HTTP 524，没有 response id、usage 或 review text；因此它是一次 API-invalid request，不是模型设计结论，不改变候选可行性判断；也没有 Qwen fallback。审计 artifact（无 API key）：
/mnt/raid1/mjh/codesk-next-candidates-20261103/reviews/sol-design-review-cwd-bundle-20261103-01/report.json
对应调用脚本已修改为先建立 run artifact、再请求，并在未来 HTTP failure 时保存不含凭证的 invalid report。原始 HTTP 524 尝试没有自动重发。

## GPT-6-Sol 对 CWD-1 v0.2.0 的有效设计审查

第一次 text-only 请求走 haogpt endpoint，收到 HTTP 524、无 response/usage，见 reviews/sol-design-review-cwd-bundle-20261103-01。按用户提供的 fallback endpoint docode.cc/v1 重试一次，取得有效 GPT-6-Sol response：resp_032a433054e6f3fd016ae9a0dc98fc8194ad472824dfd8bfbb，usage 5,666 prompt / 1,892 completion / 7,558 total，artifact 为 /mnt/raid1/mjh/codesk-next-candidates-20261103/reviews/sol-design-review-cwd-bundle-20261103-02/report.json。没有 Qwen 调用。

Sol verdict = revise，重要审查意见如下：
1. CWD/打包交互机制 plausible，但现在只能声称在一个明确固定的 stale-plan stress schedule 下检验；协调器强制 hold/replay 原生动作并非普通自由协作，不能将单 schedule 结果泛化成一般 shared desktop 的常见失败。
2. 必须把 B 的 bundle exact-member-set requirement 明写进业务任务与接受标准；若正常流程允许 extra files，仅因归档里多一个 A 文件判 task FAIL 就是 oracle mismatch。当前提案有打包流程，但还应明确 bundle allowlist。
3. 把 stale write、wrong-path file、bundle-at-first-creation、final task outcome、A/B recovery、protocol validity 作为独立字段。归档第一次生成后应只读快照其 hash/members，然后让两个 actor 自由继续与恢复；同时对终态 B bundle 再评分。若 B 后来重建成功，记录 recovery，不能阻止或忽略。
4. 必须在实际 Guest GUI 做 positive/negative controls，记录相同 shell PID、稳定 XID/focus/selection、held observation revision 和所有动作单调次序；offline 13/13 单测只证明 evaluator 行为，不证明 GUI 拓扑或模型行为。
5. 明确实验只估计所选 schedule 下的行为；若要声称适用于多种协作场景，需额外预注册其他 plausible schedules。

相应更新：CWD-1 v0.2.0 暂不冻结为正式 case；在 runner 开发前先把 B 的精确 bundle contract 与“first-created vs final bundle”的双时间点 oracle 写入 prompt/spec。Sol review 不是 GUI/模型任务实验结果，不改变 v0.1.1 的 MA-ID/MA-SD/MA-SD+Lock 分类。




## 2026-11-03 CWD v0.2 oracle 双端点补强

依 Sol 审查要求补充了两个互不混淆的业务字段和时间点：
- A 的交付必须只在指定 A 路径存在；若同一 A payload 仍留在 B 的 worktree，a_wrong_path_clean=false，即使 A 后来补对路径且 B 的最终归档干净，strict unique-delivery task 仍不通过。该约束需要在最终冻结的任务说明中明示，不可只靠 evaluator 暗中加标准。
- B 首次创建的 bundle 用只读快照评分；后续允许双方自然继续/修复，再分别检查 final worktree 与 final bundle。重建干净 bundle 能恢复 final endpoint，但不改写 first-created snapshot 的失败。

最新离线控制：cwd-bundle-state-oracle-unit-control-20261103-04，13/13 PASS，JUnit、pytest log、source SHA-256、report.json 均保存于 /mnt/raid1/mjh/codesk-next-candidates-20261103/probes/cwd-bundle-state-oracle-unit-control-20261103-04/。新增覆盖：(1) 污染 first-created archive 保持不可变；(2) A 恢复到正确位置、删除 B 中残留并重建归档后，final task 可 PASS；(3) 对恢复后的文件再按 first-created snapshot 评分仍 FAIL；(4) 仅清洁最终归档但遗留错误路径副本仍 strict FAIL。

结论边界：这只修正/验证纯文件系统 evaluator，不冻结 CWD v0.2，也不证明 archive contract 符合真实业务、GUI shell/PWD 因果链成立或三个模型臂有效。历史 11/11 的 ...-03 和 13/13 的 ...-04 报告不覆盖、不删除。当前修改的 oracle 尚需通过 actual Guest positive/negative topology controls 和 GPT-6-Sol matched arms；在 5000 screenshot readiness 门未确认前不启动 Guest。


## 2026-11-03 GPT-6-Sol 对 EDIT-1 / VIEW-1 的联合设计审计

text-only review 成功，模型 requested/returned 为 gpt-6-sol，response ID resp_0eb31e561d673a04016ae9a2bb12bc8196a7483eff27f2fe5f，usage 5,937 prompt + 2,048 completion = 7,985 tokens，约 36.1 秒。完整机器报告在 /mnt/raid1/mjh/codesk-next-candidates-20261103/reviews/sol-design-review-edit-view-20261103-02/report.json。未启动 Guest、未调用 Qwen。

总体 verdict：REVISION_REQUIRED。Sol 认为 EDIT-1 的 OVR 特异签名更直接、值得优先跑当前 runner scripted triad；VIEW-1 只在可执行坐标命中与焦点/selection 隔离控制通过后保留，不能直接花模型预算。

### EDIT-1 必须补强
- 不能用 Insert 键按了一次代替状态证据；每臂记录可见/可访问 mode、初始 INS、B 后 OVR 或阴性控制复原 INS。焦点、XID、selection、caret 行列必须分别实测。
- B 需要从 A 的 target caret 导航到固定宽度 code，再回到 A caret；把每个位置精确化并验证恢复与 selection 为空。A 的冻结 batch 明确只含 type READY-space + save；先记录 B 后的观察快照供 adjudication，但不得给 A 新观测。
- script 正控制既验证无干扰 A 结果，也验证共享 OVR 下独有的 READY OR-REVIEW 覆盖签名、AB12 code 和 guard 保持精确；负控制保持相同 shared schedule，仅把 B 的结束模式还原并验证为 INS，A 必须无损插入。
- 旧版 0.1.0 scripted triplet 是语义可行性，不等于当前 runner 的 0.3.0 controls；当前 Guest readiness 恢复前不得升级证据或跑 model arms。workflow 实用性仍需说明固定宽度 reviewer code / release status 模板为何常见，案例应称 editor-mode stale action，而非新的一般多 Agent 机制。

### VIEW-1 必须补强
- 操作必须可执行、量化：冻结 A 原始屏幕坐标、B scroll 的精确像素/viewport offset；在 A 恢复前单独记录 hit-test，证明同坐标从 POL-17 映射到 POL-29。
- 移动前后分别读取 active XID、focus/input destination、caret/selection、scroll container 与全文。除 viewport offset/坐标映射外任一状态变化都判混淆，不给机制归因。
- 阳性脚本：无 B 时旧坐标唯一命中 POL-17 并成功；B 只滚动后，同一旧坐标命中 POL-29，原样重放只改 decoy。阴性脚本必须是同 schedule、实测 viewport offset 为零的 sham；“轻微滚动”不是充分负控。
- 若 frozen Writer build 上无法证明坐标确实命中 decoy，或滚动伴随焦点/selection 改变，立即降级为 selection/focus workflow variant 或淘汰；不得为造出命中点移动 decoy/改文档 oracle。

两个案例都必须等到当前 runner 的 scripted positive/negative controls 可重复通过、然后 GPT-6-Sol MA-ID full exact pass，才进 Shared/Shared+Lock。完整 review 结论见报告，不把文字评审当实验数据。



## 新增：FIND/AUTH 审核请求与当前环境门（2026-11-03）

针对 FIND-1 与 AUTH-1 发起了一次 GPT-6-Sol 联合 text-only review（docode.cc/v1）。Gateway 返回 HTTP 524，wall 126.4s，无 response ID、usage 或 review。报告在 /mnt/raid1/mjh/codesk-next-candidates-20261103/reviews/sol-design-review-find-auth-20261103-01/report.json；保留请求/source hashes 与 invalid 状态，不含 credential。未重试、未调用 Qwen、未启动 Guest。故不能声称 FIND/AUTH 已获得 Sol 设计审查结论。它们仍是条件假设：FIND 先测 option 在 dialog close/reopen 后是否稳定且 isolated；AUTH 只接受 local mock 与临时 principal，须证实 same route 下身份 cookie/principal 单变量变化，否则停止。

HealthCare 本轮只读资源快照：root filesystem 48 GB free / 98% used；RAID1 1.5 TB free / 90%；available RAM 约 121 GiB；2 GiB swap 满。DockerRootDir 为 /var/lib/docker（root filesystem），driver overlay2；Docker image logical total 68.66 GB，reclaimable 64.93 GB；当前没有运行容器/QEMU。未 prune、删除、清理、pull/build，也未清理 run/overlay。在该容量快照时已有四次同一 Guest screenshot readiness/progress diagnostics；随后新增一个 600s 长窗测试，累计五次，仍未达到 5000 /screenshot 可见图像门。之前诊断曾见 QEMU 持续约 185% CPU 但服务未 ready：这不证明 CPU 不足，也不解决根盘余量或 Guest readiness 风险。



## 2026-11-03 新增 600 秒 Guest readiness 长诊断

为区分“OSWorld 默认 300 秒 readiness timeout 太短”与“Guest 服务实际未启动”，本轮新增一个有明确新变量的 run-owned no-model diagnostic：把 readiness sampling 窗口延长到 600 秒（每 60 秒采样），其他 Guest 镜像/runtime/启动链不变。run ID healthcare-guest-boot-600s-diagnostic-20261103-02；完整 report/provenance/resource ledger/overlay timeline 位于 /mnt/raid1/mjh/codesk-next-candidates-20261103/probes/healthcare-guest-boot-600s-diagnostic-20261103-02/。

结果：600 秒内没有一次可见 HTTP 200 screenshot；所有 10 次采样均未达到 agent screenshot ready。OSWorld container/QEMU 持续运行，runner 按诊断退出并销毁唯一 run-owned container，ledger verified all_containers_have_destroy_record=true。overlay 在 540s 定时样本约 767 MiB，临近退出时只读观察约 822 MiB，随后 run-owned teardown 清理了该 run overlay；QEMU process 约 100%–200%+ CPU 波动，容器内存从几十 MiB 上升到约 3.8 GiB / QEMU 配置 4 GiB。/proc/1/io 的 read_bytes 在首批访问后保持约 1.35 MiB，而 rchar 到数 GiB；serial log 各样本为空。宿主 root 仍约 48 GB free，没有明显增长；RAID1 仍有约 1.5 TB。由此可排除“只需把 300 秒默认等待轻微加长”这一简单解释；仍不能凭这些统计断定 Guest 内具体 boot stage 或 corruption。诊断只读宿主/Guest HTTP 状态，没有调用 GPT-6-Sol/Qwen、没有改 Guest image 或 Docker runtime，也没有清理旧资源。

因此本轮 readiness/progress diagnostic 计数由四次增为五次；600 秒窗口是新的、可证伪变量。当前不建议仅通过拉长正式 runner timeout 来掩盖问题，也不盲目启动第六个同配置 Guest。下一步若继续定位，应先获取不同证据（例如能安全读出的 boot/display console state）或找到 run-time 启动配置差异；在有效 visible screenshot gate 通过前，EDIT/CWD/VIEW 的新 GUI/model arms 仍不可作为候选结果。



## EDIT-1 当前 scripted harness 的低成本前置控制（2026-11-03）

按 Sol 审核意见更新 scripts/probe_writer_insert_overwrite_v1.py 为 0.3.0-scripted-positive-negative：
- 默认控制顺序现在包含 MA-ID、Shared OVR positive、Shared INS-restored negative、Shared+Lock OVR positive。
- B 的 negative control 在同一固定宽度 code 编辑、保存后再切回 INS，然后恢复 A 的 caret；positive controls 只切换一次、留在 OVR。
- A 前置观察与 B 后置观察会同时保存截图和 accessibility tree；脚本明确记录 mode_readout_claimed=false，不能把文本签名冒充独立 mode 观测。只有人工核验屏幕/a11y mode label、focus/XID、caret/selection 后，才可认定 scripted gate 通过。
- 新增 tests/test_probe_writer_insert_overwrite_v1.py 的纯 Python harness unit controls 3/3 PASS。报告 /mnt/raid1/mjh/codesk-next-candidates-20261103/probes/writer-insert-overwrite-probe-harness-unit-20261103-02/report.json；第一次错用无 pytest 的 OSWorld venv 是 -01 no-test/setup attempt，完整输出留存。
- 此 3/3 只验证 action choreography 与 evidence capture，不是 Guest/GUI/LibreOffice semantic control。本轮 600 秒 Guest readiness 仍无截图，因此未运行新 0.3.0 GUI conditions，也没有 GPT model task arms。

## 2026-11-03 当前候选模型证据复核（更正状态汇报）

复核 RAID1 上逐次原始 report 后，需更正过于宽泛的状态说法“新候选尚无模型臂结果”：**CWD-1 v0.1.1 确有一组三臂 GPT-6-Sol 模型结果**；它对 Shared 臂给出有效 FAIL，但 Shared+Lock 臂是有效 PASS/恢复，且带错误路径重复文件，所以整套仍未达目标。具体为：
- MA-ID `terminal-cwd-sol-ma-id-20261103-05`：valid_model_run=true、protocol_valid=true、task_success=true；精确 A/B 交付均在预期路径。
- MA-SD `terminal-cwd-sol-ma-sd-20261103-01`：valid/protocol=true、task_success=false、classification=`shared_target_fail`；同一 shell PID 与 XID，B 将共享 PWD 从 A 改到 B，A 的 stale relative write 落在 B worktree；实际暴露为真，非 setup/model-protocol invalid。
- MA-SD+Lock `terminal-cwd-sol-ma-sd-lock-20261103-02`：valid/protocol=true、task_success=true、classification=`shared_recovered_or_pass`；锁只串行化单 GUI act，最终 A 文件同时出现在预期 A 路径与 B 错误路径。v0.1.1 oracle 未将该副本判 fail，因此**不能把它冒充为锁臂 FAIL**。

因此，当前 CWD-1 的因果证据有力支持“共享 shell PWD 可导致 A 的 stale relative write 写错 worktree”，但 v0.1.1 未满足三臂交付。v0.2 的显式 unique-delivery / 精确 B archive allowlist oracle 正是为把错误路径残留作为业务失败单独计分；目前仅离线控制通过，不能把 v0.1.1 模型动作直接当作 v0.2 任务验证。以上三条源报告均在 `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/` 下，且模型元数据显示 requested/returned 均为 `gpt-6-sol`。

另外，EDIT-1 v0.1.0 有过一次真实 GPT-6-Sol MA-ID 尝试 `writer-insert-overwrite-sol-ma-id-20261103-03`，但模型返回的 `actions:[{"click":35,"y":337}]` 不符合当时 action parser，0 个 GUI turn，`valid_model_run=false` / `protocol_valid=false`；这是 adapter/protocol invalid，不是 task FAIL。当前 `swcub/sol_osworld_agent.py` 对此唯一明确坐标字典做了 allowlisted 规范化，拒绝其他任意对象。刚以现有 HealthCare pytest 环境复跑三组纯本地测试：Sol adapter + EDIT harness + CWD oracle 共 **27/27 PASS**（不启动 Guest、不调用模型）。

EDIT-1 后续状态：MA-ID `...-04` 是 VM readiness timeout、无模型调用；前两次 `...-01/-02` 是 Writer readiness failure；均无有效任务结果。当前没有容器/QEMU 活跃。Guest 画面服务阻塞仍在，但应精确表述为“最近三次 EDIT 重跑未获得有效任务结果”，而不能抹掉早前有效 Guest 会话中的 adapter-invalid 模型调用或 CWD 已有三臂。

执行含义：下一个模型预算应优先重跑 **CWD-1 v0.2 的 MA-ID exact pass**（先冻结业务中的唯一交付与 bundle allowlist），通过后再按 matched schedule 重跑 Shared 和 Shared+Lock；不能把旧 v0.1.1 lock 的错误路径副作用重新计成预先约定的业务 FAIL。Guest screenshot-ready 恢复前，候选三臂尚不可重启。


## 2026-11-03 Guest readiness 根因修正与测量门调整

有了新证据后，先前将 Guest 归为“600 秒仍未启动”的判断过强：早先 4G/8G diagnostics 用 2 秒读取整张截图，不能区分“画面服务没启动”与“截图响应慢/启动期黑帧”。新 run healthcare-guest-service-matrix-diagnostic-20261103-04 在 t=120s 观测到 port 5000 /screenshot 已返回 HTTP 200 headers，但 2 秒 body timeout；其余转发端口 8006/8080/9222 未报告 HTTP/RFB 服务。

随后使用默认 4G/4 CPU、将截图 body read timeout 提升为 20 秒、且不对 screenshot endpoint 发第二个干扰请求的独立 no-model run healthcare-guest-screenshot-bodytime-diagnostic-20261103-05：
- t=120s：HTTP 200，完整黑帧 PNG 6,523 bytes、1920×1080，visible_ratio=0.0。
- t=150s：HTTP 200，完整 PNG 1,567,822 bytes，headers 9.688s、body 总计 9.883s；visible_ratio=0.9856、2,260 sampled colors，判定 visible。
- run wall 164.95s；唯一 run-owned Guest container 已销毁，resource ledger 全部匹配，Docker/QEMU 当前无活跃进程；没有调用 GPT-6-Sol/Qwen/API key，也没有 build/pull。
- 画面人工复看为正常 GNOME 桌面（1920×1080），不是空白或异常截图。

结论：Guest 是启动较慢，且早期先返回黑帧；旧诊断的 2 秒读超时产生误判。实际完成可见画面约需 150 秒，截图传输自身近 10 秒。按这项实测，本地候选 runner 的 OSWorld-provider readiness 和可见画面 readiness read timeout 已从 10 秒调至 30 秒，overall 300 秒期限不变；新增单测覆盖 timeout tuple。adapter + EDIT harness + CWD oracle + readiness tests 当前 28/28 PASS。修改文件 scripts/run_writer_calc_v1.py、swcub/osworld_readiness.py；没有改外部 OSWorld dependency、镜像或冻结的 Case 2/3/4。

因此三臂模型实验的基础设施门现在可重开；Guest screenshot-ready 不再是当前 blocker。下一步回到 CWD-1 v0.2：先冻结包含唯一交付约束、B QA bundle 精确成员 allowlist、first-created archive 与 final-state 分开评分的任务说明/runner，再跑 Sol MA-ID exact pass。

## CWD-1 v0.2.0 scripted Guest topology control（2026-11-03，非模型结果）

运行 cwd-bundle-v020-scripted-20261103-03 已完成，原始证据位于 /mnt/raid1/mjh/codesk-next-candidates-20261103/probes/cwd-bundle-v020-scripted-20261103-03/。冻结版本为 CWD_BUNDLE_CASE_SPEC_V020_20261103.md；运行 wall_seconds=1168.71（19m28.71s），真实启动 4 个 Guest，全部有一致 owner label 与 destroy record。此 run 没有 GPT-6-Sol/Qwen/API 调用。

| 条件 | scripted control | 关键证据 |
|---|---|---|
| MA-ID | scripted_ma_id_exact_pass | 两个独立 Guest/不同 shell；A 文件只在 A worktree，B check 与精确 bundle 成功；final task success=true。 |
| MA-SD | scripted_shared_unique_delivery_fail | 同 Guest、同 shell PID、同活动 XID；A 执行旧相对路径动作时 PWD 已为 /tmp/codesk-cwd-v020/work/b。A 预期路径缺失、payload 落在 B worktree，final task success=false。 |
| MA-SD+Lock | scripted_shared_unique_delivery_fail | 同 Guest/shell/PWD/XID 与 MA-SD；8 次 GUI act，max_concurrent_gui_act_calls=1，仍将 A payload 写入 B worktree，final task success=false。 |

重要解释限制：三个条件中 B 首次创建与最终 qa-bundle.tar.gz 都是精确 allowlist {deliverables/check.txt}。本 run 证明的是 A 的唯一交付错放/缺失以及 B worktree 污染，没有证明 QA archive 被 A 文件污染；不能把 bundle 污染或 archive failure 写成结果。此 scripted schedule 证明机制在固定 stale-plan stress schedule 下可出现，不代表自由协作中的普遍失败率。MA-ID/shared/lock 的脚本状态差异与 oracle 字段均在逐臂 report.json。

正式控制 run 前保留两次 setup-invalid 尝试：...scripted...-01 未 pin runtime，OSWorld provider 对默认远端镜像发起的自动拉取因 registry timeout/HTTP 500 失败，在 Guest 创建前退出；...-02 选择了缺少 gymnasium 的通用 Python venv，也在 Guest 创建前退出。两者均不是 candidate FAIL。之后的 ...-03 已在 OSWorld 自带 .venv 中运行，并在脚本启动前强制核对本地 runtime image ID；未发生 pull/build。运行后容器/QEMU 已清空；root 可用空间约 46 GB，RAID1 可用约 1.5 TB。

本结果只通过当前 v0.2.0 的 GUI/topology/oracle 控制门；不升级历史 v0.1.1 模型证据，也不等于候选最终获准。下一步若进行模型验证，先跑冻结 v0.2.0 的 GPT-6-Sol MA-ID exact pass；仅其两位 actor 都通过才进入同版本 Shared 和 Shared+Lock。


## 2026-11-03 CWD v0.2.3 / v0.2.4 adapter audit

- Attempt `cwd-bundle-v023-sol-ma-id-20261103-01`: invalid setup before any Guest/API use because the system Python interpreter lacked `gymnasium`; no model response and zero containers. Do not count as candidate result.
- Attempt `cwd-bundle-v023-sol-ma-id-20261103-02`: correct OSWorld pinned Python, two Guests started and were destroyed with verified owner-ledger records. GPT-6-Sol returned one response (7,299 prompt + 108 completion = 7,407 tokens), with explanatory prose plus JSON actions written as `write(...)` and `press(...)` rather than `pyautogui.*`. The previous adapter rejected this before any native GUI action: 0 actor steps, no exposure, protocol invalid. This is not model task failure. Full report and inference/raw response preview are preserved at `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/cwd-bundle-v023-sol-ma-id-20261103-02/`; resource ledger: 2 containers, all destroy records present.
- The new frozen task/fixture is **CWD-1 v0.2.4**, spec `CWD_BUNDLE_CASE_SPEC_V024_20261103.md`: it increments task version/root/token, retains relative-write-plan gating, and safely canonicalizes only bare allowlisted GUI calls to PyAutoGUI AST nodes with literal arguments. It logs each normalization in model response metadata; non-UI calls remain rejected. The task prompts and exact business oracle stay unchanged apart from run-scoped V024 token/root.
- Targeted offline validation: py_compile passed; adapter + CWD oracle/materializer/schedule/readiness tests **31/31 PASS**, including the exact Sol-style bare write/ENTER form triggering both relative-write and submission classifiers and a negative shell-call rejection. This is adapter/schedule evidence, not GUI/model task PASS.
- Next action: one fresh GPT-6-Sol v0.2.4 MA-ID baseline on the OSWorld pinned venv. Only if protocol valid and exact unique-delivery + archive endpoint PASS may matched Shared and Shared+Lock arms begin. Existing Guest scripted v0.2.0 controls remain separate and do not count as v0.2.4 model evidence. No Qwen fallback.


## 2026-11-03 CWD v0.2.4 GPT-6-Sol MA-ID baseline

Run `cwd-bundle-v024-sol-ma-id-20261103-01` completed in 778.001s (12m58s) with the OSWorld pinned venv. GPT-6-Sol requested/returned exactly; 5 model responses, 37,640 prompt tokens + 416 completion tokens. Both independent Guest containers are in the owner ledger and both have destroy records. No Qwen calls. Full report, screenshots, first-created archive snapshot, event log, raw model metadata and provenance are preserved under `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/cwd-bundle-v024-sol-ma-id-20261103-01/`.

Outcome: `valid_model_run=true`, `protocol_valid=true`, `condition_classification=matched_ma_id_pass`, `task_success=true`. A's final release note is byte-exact only in work/a; B's exact check file is present; first-created and final QA archive both have exactly `deliverables/check.txt` with the correct bytes and identical hash. The target-write gate did hold A's pending plan while B completed, then resumed on the independent A Guest; target write executed in A's work/a, stale_due_other_actor=false. This is a valid independent baseline for the frozen v0.2.4 prompts, system/adapter/runner/fixture hashes:
- prompt SHA-256: actor A `d3f6cc6229854c159b3d7a568b8f6e4df8ed5c39aee992e78d00149edc687d3b`; actor B `efafc921b153a97adb876df4e3f03e6ef0b3cb6f3243cbe8aafcd5b4e4ad0f73`
- system `1fc730018e68f884edb09ac4ee859e892e2223ede78da1f380492c9e714c20df`; adapter `5162b0b766baccec7f04af32adc62a0f6c5a9a6d6f09f116f34ca7e2b74e3604`; runner `c606f56b2d5a46c58d10f1f67c6e9ad5ed77a65af68c47fe3b9f872c4b777350`; fixture `35458005cb5beea230bb9066b9c35e6c8b9903e93d64f275dd020ba575b99916`.
Matched MA-SD and MA-SD+Lock can now proceed sequentially against this exact baseline; no source/prompt changes are allowed in between.


## 2026-11-03 CWD-1 v0.2.4 GPT-6-Sol matched three-arm result

All three runs are completed, protocol-valid, valid_model_run=true, and use the same v0.2.4 prompt/system/adapter/runner/fixture hashes listed above. All requested and returned model IDs are `gpt-6-sol`; no Qwen. Every run-owned container has a matching destroy record. Raw report, event log, inference metadata, screenshot observations, oracle state, archive snapshots, provenance, and resource ledger are preserved in the per-run directories listed below.

| Arm | Run | Wall | Final result | Mechanism evidence |
|---|---|---:|---|---|
| MA-ID | `cwd-bundle-v024-sol-ma-id-20261103-01` | 778.001s (12m58s) | PASS | A unique note only in work/a; B check exact; first-created and final exact archive. A frozen write plan is resumed against the independent A shell/PWD; stale_due_other_actor=false. |
| MA-SD | `cwd-bundle-v024-sol-ma-sd-20261103-01` | 424.730s (7m05s) | FAIL, valid `shared_target_fail` | Same Guest/PID/active XID. B changes PWD to work/b; A's held plan remains at old observed revision and target write is submitted with cwd=work/b, stale_due_other_actor=true. A's expected work/a note and B QA check/archive are correct, but an extra exact A payload remains at work/b; unique-delivery oracle fails. |
| MA-SD+Lock | `cwd-bundle-v024-sol-ma-sd-lock-20261103-01` | 448.609s (7m29s) | FAIL, valid `shared_target_fail` | Same stale-CWD evidence and wrong-worktree duplicate as Shared. PerActionLock was enabled across 24 GUI calls with `max_concurrent_gui_act_calls=1`; per-action serialization did not reset PWD or stale plan. |

For both Shared arms the QA archive was exact both when first created and at final state: the observed business failure is **A's duplicate/wrong-worktree deliverable**, not archive pollution. Preserve that distinction. All three arm classifications meet the pre-registered target combination: Isolated PASS, Shared FAIL, Shared+Lock FAIL. This is one matched triplet, no repeat replication claimed. Scope remains this fixed stale-plan schedule, not a general failure-rate estimate.

Model usage across the triplet: 16 responses; MA-ID 37,640+416 tokens, Shared 45,319+576, Shared+Lock 45,285+487; total 128,244 prompt + 1,479 completion tokens. Combined wall time 1,651.34s (27m31s). Exact hashes in the baseline report:
- prompts A/B: `d3f6cc6229854c159b3d7a568b8f6e4df8ed5c39aee992e78d00149edc687d3b` / `efafc921b153a97adb876df4e3f03e6ef0b3cb6f3243cbe8aafcd5b4e4ad0f73`
- system / adapter / runner / fixture: `1fc730018e68f884edb09ac4ee859e892e2223ede78da1f380492c9e714c20df` / `5162b0b766baccec7f04af32adc62a0f6c5a9a6d6f09f116f34ca7e2b74e3604` / `c606f56b2d5a46c58d10f1f67c6e9ad5ed77a65af68c47fe3b9f872c4b777350` / `35458005cb5beea230bb9066b9c35e6c8b9903e93d64f275dd020ba575b99916`.

