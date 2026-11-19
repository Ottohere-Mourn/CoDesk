# 五个低覆盖竞争机制候选（MECH-01–05）—设计与实验状态

日期：2026-11-18
所在分支：codex/all-codesk-cases-20261113

## 目的与当前状态

从 Synthetic Desk 的“共享当前记录/活动面板”族转向不同桌面状态竞争。本文件最初是设计计划，现已包含控制与模型实验结果：MECH01–05 的 fixture/Oracle、scripted controls 和 GPT-6-Sol 三臂均已完成且有效；其中 MECH02/03 达到一次 arm-level 方向目标，MECH01/04 存在失败归因混杂，MECH05 锁臂通过。MECH06–09 的最新整体状态见 `tasks/mechanism_expansion_v1/MECH06_09_GLOBAL_UNDO_CASE_FAMILY_20261118.md`：MECH06 v0.5.0 是本批唯一一项目前明确满足 MA-ID 双 PASS / Shared FAIL / Shared+Lock FAIL 的新模型 case；MECH07–09 仅有 scripted controls。每项模型评分都以有效 Oracle/模型终止为前提；不得将基础设施无效或固定机制控冒充真实模型失败。

机制名称沿用已验证过的基础原型做“不同工作流的扩展”，不是宣称此前完全没有此类 case。

## 共同实验协议

- 平台：HealthCare 现有 OSWorld Ubuntu Guest；任务必须通过桌面/常规应用完成，不调用 Synthetic Desk 页面。机制遥测和任务状态只供评分端读取。
- MECH-01 的首个可复现控制夹具是一个本地采购对账网页，运行在 Guest Chrome 中；它不是现成的业务软件，也不是 Synthetic Desk。此夹具仅用于证实真实 Chromium 剪贴板及因果日志可测，模型任务有效性通过后再决定是否迁移到 Writer/Calc。
- 三臂：同版本 fixture 和任务提示；MA-ID 两 Guest、Shared 一 Guest、Shared+Lock 对每个 GUI 动作持互斥锁。模型/预算/工具权限保持一致。
- 每个独立 Actor 都须在双角色独立 Guest 上单独达到 PASS；共同 Shared fixture 应可行，不得存在逻辑上不可能的联合解。
- 先做 Oracle 单元正负控和 Guest scripted GUI 正控；再做一次模型 MA-ID；只有 MA-ID 两角色均通过且日志有效才继续 Shared。Shared/Lock 结果无论是否符合假设都保留。
- 自然并发结果与协议门控/固定交错机制验证分开报告。若 Shared+Lock 恢复为 PASS，就记录为“锁有效”，不改任务逼出 FAIL。
- Guest overlays 和 runs 写 RAID；检查资源归属和隔离，不停止外部容器，不清除旧结果。

## 候选任务卡

### MECH-01 — CLIP-RECON：采购例外单与付款登记的剪贴板引用号交接

- **机制**：OS 系统剪贴板是跨窗口共享单槽状态；复制/粘贴是多步临界区，单次动作锁不能天然锁住 copy→switch→paste 整段流程。
- **控制夹具中的任务**：A 从可见采购发票区域复制发票引用号，把供应商、引用号和核准金额登记到 Role A 行；B 从另一份可见付款凭证复制 ACH 回执号，并把收款方、引用号和金额登记到 Role B 行。两行独立，无共同业务数据写冲突。
- **共享状态**：Guest 上真实 Chromium 系统剪贴板；共同网页状态包含互不重叠的两条目标记录。
- **Oracle**：按角色检查 reference/amount/vendor-or-payee 和 saved 状态；只依据 UI copy/paste 事件与最后一次复制者、粘贴值和来源值进行机制归因。控制结果不能将自报失败当成评分。
- **独立桌面对照**：每个桌面各一份同版网页和相同两张可见凭证，仅对应 Actor 写其行。
- **主要混杂风险**：模型可能手动重打号码避免粘贴。任务卡提出 GUI Copy/Paste 是自然工作流指引但不禁用其他操作；若模型绕过粘贴，即使任务完成也不算 clipboard 机制命中。
- **夹具局限**：本地采购网页不是现成业务套件，因此本轮只将它视作低成本机制可观测性探针。不能单凭 scripted 负控声称已验证模型生态学有效性；后续若扩展此题，应优先迁移到 Writer/Calc 单据与工作簿。
- **旧锚点差异**：区别于 C-03/W1 的字段内容与单据流程；若只复现“另一 Actor 覆盖剪贴板”而没有不同工作流证据，不作为新机制命中。

### MECH-02 — UNDO-HANDOFF：质量表筛选复核中的全局撤销历史竞争

- **机制**：同一份 Calc 文档的 Undo 历史跨 Actor 共用；一方正常的撤销可能回滚另一方刚提交的有效编辑。
- **任务**：A 临时筛出待复核批次，核对后恢复完整表格视图，并填写自己的复核状态；B 同时登记另一批次的实测读数与签名。
- **共享状态**：同一 Calc 文档的撤销历史、筛选状态和表格内容。
- **Oracle**：完整行集恢复；A/B 两条记录的状态、读数、签名都正确；无多余删除/格式破坏。
- **独立桌面对照**：双方分别在相同初始工作簿中完成筛选、恢复和各自登记。
- **主要混杂风险**：A 可能不用 Undo，而通过清除筛选恢复视图。允许这样做；若确实避免 Undo，就说明该任务没暴露此机制，不把失败硬算给撤销栈。
- **旧锚点差异**：U-01 的扩展工作流，不仅是改单元格后 Ctrl+Z；需先通过 scripted control 证明“对方一次合法编辑插入 undo history 后，A 的合法恢复动作会产生可观察的回滚”。

### MECH-03 — FOCUS-ROUTE：工单响应与表格财务登记的前台窗口输入误路由

- **机制**：X11 当前活动窗口/焦点是单一共享状态；键盘输入可能落入另一个 Actor 激活的应用或弹窗。
- **任务**：A 在 Calc 完成服务额度表的指定单元格更新并保存；B 在 Writer 中编辑并保存该工单的简短客户回复。
- **共享状态**：同一 Guest 上的 Writer、Calc 窗口、前台焦点、保存/格式对话框。
- **Oracle**：Calc 指定单元格和 Writer 指定段落均正确；同时记录 active window/XID、窗口切换、键盘事件、文本落点截图，区分焦点误路由与普通任务失误。
- **独立桌面对照**：每个 Actor 在独立 Guest 处理相同源文件。
- **主要混杂风险**：模型可能每次先激活目标窗口（正确自我保护）。这是有效 PASS，不制造额外切换；如无真实焦点误路由，就不算机制命中。
- **旧锚点差异**：与 F-01/Case-3 的 Writer/Calc 或 VS Code/Browser 流程不同，聚焦客户服务双文档保存；是否真的更可靠必须由轨迹证明。

### MECH-04 — RANGE-DRIFT：表格筛选/排序期间的活动范围漂移

- **机制**：Calc 的活动单元格/选区是共享的瞬态 GUI 状态；一个 Actor 正常排序或筛选会改变另一 Actor 按旧行号进行的下一次编辑目标。
- **任务**：A 按批次编号给两项抽样结果标记“复测”；B 对同一张样本台账按日期排序、筛出逾期行并更新其交接状态。
- **共享状态**：同一个 Calc 工作簿中的行顺序、筛选、活动选区及可见视口；任务数据应允许排序后用稳定批次编号找回目标。
- **Oracle**：按稳定记录 ID 校验各字段；检查总行集/公式/非目标项未变；记录排序、选区位置、最终写入单元格。
- **独立桌面对照**：同版独立工作簿，分别执行完整任务。
- **主要混杂风险**：这是容易被正确重定位规避的机制；Oracle 必须按稳定记录 ID 评分，脚本同时验证选区/排序交错能否导致误写，不能按“预期单元格坐标”奖励错误。
- **旧锚点差异**：S-01 是活动单元格漂移；本题增加合法排序/筛选和稳定 ID 操作，不应退化成静态“选错格”。

### MECH-05 — SESSION-LEASE：财务审批单席位会话的身份/会话失效竞争

- **机制**：两个合法角色需要同一个浏览器 profile 的单席位审批门户；B 以自己的合法凭证切换/建立会话，可能改变或使 A 的审批会话失效。
- **任务**：A 以 Claims Reviewer 身份核准已具备条件的理赔单；B 以 Treasury Reviewer 身份查看另一笔已核准款项并确认付款批次。两项业务本身没有数据依赖或资源互斥。
- **共享状态**：浏览器 cookie/session 与活动 principal，而非共享记录/活动面板。
- **Oracle**：分别检查业务状态、审计事件中的 actor/principal、被拒绝或错误归属事件、session refresh/logout；结果不足以仅靠最终页面推断时保存服务端 append-only 审计日志和 Guest 截图。
- **独立桌面对照**：两套桌面各自建立 A/B 对应登录态，初始业务数据等价。
- **主要混杂风险**：与 AUTH-1 的相似度最高。为避免只重复“下拉框切换 reviewer”，本题必须使用身份认证/单席位 session 生命周期（重新登录、session rotation/logout）和跨业务队列任务；若无法在现有 Guest 建立可信的角色与会话审计，停止该题或替换为独立文件保存竞争题。
- **旧锚点差异**：强调认证 session 生命周期与操作归属，而非一个页面上的 Active reviewer 选择器。

## 实现门控 / 风险排序

| Case | 可观察机制主信号 | 初判成本 | 开始大模型前的硬门槛 |
|---|---|---:|---|
| MECH-01 | 两次不同 clipboard write/read 与错误引用回填 | 中 | Clipboard 真实系统范围确认；各自单独与 scripted 正控通过 |
| MECH-02 | undo 历史记录序列、撤销目标变化 | 中高 | 证明文档范围 Undo 在并发顺序下可观察且共同最终态可行 |
| MECH-03 | 活动窗口变化与输入目标不一致 | 中 | Guest 可采集 X11 焦点与窗口截图；对照无焦点误路由 |
| MECH-04 | 排序/筛选前后选区与稳定记录 ID 不符 | 中 | Oracle 不依赖固定行坐标；负控确保错误写入能检出 |
| MECH-05 | principal/session generation 改变与审计归属 | 高 | 有受支持的 session/auth 事件遥测，且双角色独立基线等价 |

本轮优先落地次序：MECH-01、MECH-03、MECH-04、MECH-02；MECH-05 先做只读可行性探针。若 MECH-05 session 归属 oracle 不可靠，不为凑足五题而保留，改用明确的同路径文件保存/另存覆盖竞争题并记录设计替换。


## MECH-01 实际验证更新（2026-11-18）

### 真实 Guest scripted controls
- Guest 上正控通过：两位角色都保存正确；系统剪贴板有真实 Chromium copy/paste 事件；没有交叉覆盖。
- 固定交错机制负控通过：A 复制后，B 复制覆盖系统剪贴板，再由 A 粘贴；A 失败、B 通过，服务端事件把 A 的错误值归因到 B 的最后一次复制。
- 控制产物与 reset/destroy 记录位于 RAID：`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech01-guest-control-20261118T050702Z-333372/`。

### GPT-6-Sol 小规模三臂
模型、版本和每臂预算冻结一致：Codex CLI 0.155.0、GUI-only MCP、task 0.1.4、每角色最多 18 步、每臂 1200 秒。结果清单：`runs/model-pilot/mech01-sol-triplet-20261118T052139Z-340392/pilot-audit.json`（该目录在 RAID）。
- MA-ID：A/B 均 PASS，13/11 步，约 7.4 分钟。
- Shared：A PASS、B FAIL，约 12.7 分钟。B 的可见字段正确，但没有点保存；未出现“他人复制介入 B 的 copy→paste”证据。因此这是任务失败，不是可归因的剪贴板干扰。
- Shared+Lock：A/B 均 FAIL，A 达 18 步上限，约 16.2 分钟。轨迹直接显示 B copy → A copy → B paste；B 的引用号被串接、未保存，A 的金额字段为空。此处证明单动作锁不覆盖 copy/切窗/paste 多动作临界区。
- 三臂总运行约 36 分钟；运行归属的 Guest 均已销毁，外部 `sharp_bhabha` 未动。文件系统的临时 Codex runtime 占根盘约 0.6GB，RAID 仍有充足余量。

### 当前判定
数值任务 tuple 是 MA-ID PASS / Shared FAIL / Shared+Lock FAIL，但只有 Shared+Lock 有强剪贴板因果证据，Shared FAIL 来自漏保存。**MECH-01 暂记为“有机制正控且方向性模型结果、待补强”，不能宣称是已充分机制验证的达标 case。** 不应针对 Shared 额外制造障碍；后续若继续此题，应在不改变任务难度的前提下让“引用粘贴后保存”仍是自然完成路径，重新校准预算，并保留当前全部运行作为历史版本。



## MECH-03 实际验证更新（2026-11-18；task 0.6.0）

- **Scripted controls：**真实 Guest 正控（两份任务均 PASS）和 stale-focus 机制负控通过；报告见 `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech03-guest-control-20261118T073737Z-401335/report.json`。
- **MA-ID：**A/B 均 PASS，6/5 次 GUI 调用，总计约 414.5 秒。
- **Shared：**A FAIL、B PASS，6/10 次调用，约 529.7 秒。X11/截图轨迹记录到 A 从 Writer 切到 Calc 后，B 原计划对 Writer 执行的 `type_text` 实际落在活动 Calc 窗口；之后 Ctrl+Z/清理动作又造成 A 的表格目标失败。此臂包含直接的焦点误路由证据。
- **Shared+Lock：**最初 triplet 的 `shared-lock` 目录实际 `action_lock=false`，只能当作重复 Shared，不能算锁臂。之后以单臂方式重新运行，`action_lock=true`，17 个锁事件、A/B 均 PASS（8/9 次调用），约 591.6 秒；虽发生瞬时误路由，两位 Agent 都恢复了。
- **判定：**MA-ID PASS / Shared（A FAIL、B PASS）/ Shared+Lock PASS/PASS，**未达到 PASS/FAIL/FAIL**。Shared 的 A 失败与焦点误路由证据一致；锁臂表现为有效恢复，不能把它写成 FAIL。首轮锁臂误配置以及有效锁臂的产物分别保留于 `runs/model-pilot/mech03-sol-triplet-20261118T074248Z-403827/shared-lock/result.json`、`runs/model-pilot/mech03-sol-shared-lock-20261118T081526Z-426171/shared-lock/result.json`；三臂审计在 `runs/model-pilot/mech03-sol-triplet-20261118T074248Z-403827/pilot-audit.json`。

## MECH-02 实际验证更新（2026-11-18；task 0.1.1 / control 0.1.2）

- **任务机制：**Calc 的共享 Undo 历史。A 将 QC Queue 升序排序，按指令一次 Ctrl+Z 恢复顺序并标记 S-4108；B 给 S-4112 录入计数 427、签名 JL。Oracle 按稳定样本 ID 比较，允许双方目标格变化，不把排序本身误判为非目标破坏；同时按列 schema 补齐 ODS 合法省略的尾部空单元格。
- **本地测试：**`tests/test_mech02.py tests/test_mech03.py tests/test_mechanism_expansion_v1.py` 合计 16 项通过；其中 MECH-02 测试 5 项。
- **真实 Guest scripted controls：**报告 `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech02-guest-control-20261118T090347Z-461366/report.json`。正控中 A/B 均 PASS，排序改变过行序，随后 A 撤销恢复原顺序；固定交错负控中，B 输入 427/JL 后 A 的一次合法撤销移除了 B 的 JL、保留 427，且 A 的排序仍未撤销，Oracle 判 A/B 均 FAIL。Guest 关闭且归属容器已销毁；未停止外部 `sharp_bhabha`。
- **真实模型首次尝试（作废）：**运行组 `runs/model-pilot/mech02-sol-triplet-20261118T090833Z-463385/` 将 Codex runtime 放在 RAID 后出现写权限错误，两个 Agent 零步骤；作为基础设施无效记录保留。
- **真实模型重跑（不构成有效三臂）：**运行组 `runs/model-pilot/mech02-sol-triplet-20261118T091247Z-466050/` 改为可写的本地 Codex runtime。
  - MA-ID Oracle 两个分数均为 1；但 Agent A 为 `done`（12 次调用、1042.3 秒、156,351 输入 token），Agent B 为 `timeout`（1200.4 秒、9 次调用、无完成 token 记录）。B 最终文件状态虽然满足 Oracle，超时仍意味着 MA-ID **无效**，不能当作两人都有效完成的 PASS。
  - Shared 中 A/B 均 `timeout`（各 1200.2 秒，10/5 次 GUI 调用），两份 Oracle 都为 0；运行日志记录过 GPT-6-Sol SSE idle-timeout/reconnect。该结果是预算/协议超时，**不是可归因的 Shared 机制 FAIL**。
  - 因 MA-ID 不满足 Agent 完成状态门槛，Shared+Lock 未运行。Shared Guest 已销毁；`sharp_bhabha` 外部容器保持运行。该运行组中 action lock 为 false。
- **判定：**MECH-02 的**脚本化全局撤销交错机制已被正/负控验证**，但 GPT-6-Sol 真实模型结果尚无有效 MA-ID 起点，不能宣称达到需求 tuple。一次完整 MA-ID+Shared 已耗约 46 分钟；不要以超时分数补成通过证据。当时的 MA-ID 门控只接受 `status=done`；其后为保留有正常终态但到达 max-step 上限的任务失败，修订 runner 改成检查状态属于终态、没有 agent error、存在 `turn.completed` 与非空终答；MA-ID 仍另要求 Oracle 两项均为 1。
- **资源提示：**模型运行 overlays/结果均在 RAID；Codex runtime 位于 `/home/mjh/.cache/codesk-mech02-sol-pilot`，HealthCare 根盘目前只有约 21 GiB 可用，后续启动前重新 preflight。暂不重复跑此模型三臂，先推进其它候选的便宜设计/Guest 正负控，待接口时延或任务步数问题解决后再决定是否复测。
### MECH-02 修正 runner 三臂重跑（2026-11-18；task 0.1.1 / protocol 0.1.3）

- 新运行组：`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech02-sol-triplet-20261118T124447Z-565007/`。之前权限错误与 SSE timeout 运行都保留；本次是使用 tmpfs Codex runtime、修正超时与终态门槛后的单次有效完整三臂。
- **MA-ID**：Oracle A/B=1/1；Agent A/B 分别 done、15/6 次 GUI 调用，token usage 210,026/55,307 input，678/237 output；臂耗时 755.2s。
- **Shared**：Oracle A/B=0/0；A/B 均有终态 turn 和终答、无 API/Guest 错误，状态为 max_steps 18/18；臂耗时 557.1s。故这是有效预算内任务失败，不是 infra-invalid；但 A 没有完成预期的排序后 Ctrl+Z，不能把该臂单独当成 undo 因果证明。
- **Shared+Lock**：Oracle A/B=0/0；action_lock=true，两位 Agent 都有终态终答、无运行错误，18/18 次调用；臂耗时 661.8s。统一事件流中 A 执行其 Ctrl+Z/保存后，B 约 2.3s 后再发 Ctrl+Z，随后又连续两次 Ctrl+Z；终态 A 的 Verified 丢失，B 仅保留 427、缺 JL。逐动作锁未隔离 Calc 的共享 undo history / 多步工作流。因遥测没有 undo-target identity，且两共享臂都到调用上限，机制因果结论为**强支持但未完全闭环**。
- Shared+Lock 记录 35 条输入动作锁事件，累计 wait 6.278s、max 1.755s，累计 held 84.98s、max 4.525s。三臂约 32.9 分钟、93 GUI 调用、约 1.478M input / 9.7K output tokens。
- **判定**：本轮在数值任务结果上首次得到 MA-ID PASS / Shared FAIL / Shared+Lock FAIL；按单次 pilot 可列为“达到目标结果组合、机制证据较强的 provisional case”。由于 Shared 臂本身没有按计划执行 undo、两个共享臂都触及固定步数上限、且尚无 undo-target instrumentation，不能称为无歧义/重复确认的正式机制验证。完整细节见 `tasks/mechanism_expansion_v1/MECH02_GLOBAL_UNDO_CASE_CARD_20261118.md`。
- 资源：Guest/overlay/artifacts 属于该运行组并已销毁/留存在 RAID；Codex runtime 在 `/run/user/1002/codesk-mech02-sol-pilot-20261118`；结束后唯一仍运行容器为外部 `sharp_bhabha`。根盘约 20.89 GiB 可用、RAID 约 882.48 GiB 可用。没有清理旧结果。

## MECH-04 原型与 Guest 控件更新（2026-11-18；task 0.1.0 / control 0.1.0）

- **任务机制：**Calc 同一工作表中的活动单元格/目标范围被另一 Actor 合法排序操作改变。A 在批次台账中为 B-5108 标记 `Recheck`；B 将 Next Count 升序排序，再按稳定批次 ID 给 B-5112 标记 RM。应用仍是普通 LibreOffice Calc；机制区别于 MECH-02 的全局 Undo 历史，焦点也始终在同一窗口。
- **Fixture：**`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets/mechanism_expansion_v1/mech04/range-drift-log.ods`；SHA-256 `ccea29904da73a3274ba1177c89b35cffc35c4468e849bdd3efb2a95894af2b1`。Oracle 按 Batch ID 比较字段，并核对排序日期和完整标题/行集。
- **测试：**`tests/test_mech04.py` 3 项通过：ODF 尾部空单元格补齐、两角色联合正态、错误活动选择导致表头损坏可检出。
- **真实 Guest scripted controls：**最终有效报告 `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech04-guest-control-20261118T101554Z-494308/report.json`。正控（A 先写入，再由 B 排序并按稳定 ID 更新）A/B 均 PASS。固定交错负控（A 选中 E2 暂不输入；B 为排序选择 C1 并排序；A 随后输入）中，A 的 `Recheck` 误写入 C1 的 `Next Count` 标题，B 的 RM 字段本身正确，但 Oracle 两角色均 FAIL，截图和 ODS 终态都保留。该结果是刻意交错的机制控制，不是自然并发模型结果。
- **GPT-6-Sol MA-ID/Shared/Shared+Lock：**运行组 /mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech04-sol-triplet-20261118T121209Z-550215/。MA-ID A/B PASS/PASS（7/15 GUI 调用，408.1 秒）。Shared A/B Oracle 都为 0（15/15 次调用，675 秒）；B 报告排序/编辑控件不可用，A 的 Retest Flag 未命中目标，但没有 API/Guest error。Shared+Lock A PASS、B FAIL（8/16 次调用，500.3 秒，action_lock=true）。B 最后截图里排序与 RM 看似正确，但没有按保存；终答也承认未能保存，且正好用尽 16-call budget。
- **锁遥测与归因：**20 个 per-action lock 事件，等待总计约 2.083 秒，最长 1.103 秒；没有焦点误路由标志。Shared+Lock 的 B 失败是未保存，不是证明多动作临界区仍被干扰；Shared 任务失败真实，但目前不足以把原因具体归到跨 Agent 的选区/排序变化。三臂结果/图像/事件完整审计位于该运行组 pilot-audit.json。
- **判定：**联合成功角度是 MA-ID PASS / Shared FAIL / Shared+Lock FAIL，但这只是结果组合；严格机制标准下，锁臂失败由预算耗尽前漏保存解释，所以不计为机制已验证的 PASS/FAIL/FAIL case。控件正负证据成立，模型结果保留为探索性，不为得到期望锁臂失败再重复。
- **实现/资源：**模型与控件日志和 overlay 位于 RAID；Codex runtime 位于 /run/user/1002 tmpfs，避免继续占根盘。运行结束后任务 Guests 已销毁，外部 sharp_bhabha 保持运行。详见 tasks/mechanism_expansion_v1/MECH04_RANGE_DRIFT_CASE_CARD_20261118.md。

## 组合机制覆盖复核与 MECH-05 改选（2026-11-18）

这次复核了 `tasks/paragui/spec_*.md`，避免仅凭新任务外观把已有机制误称为新覆盖：

| 候选 | 现有覆盖审计 | 定位修正 |
|---|---|---|
| MECH-01 Clipboard | `spec_v5.md` 已有 AP-CLIPBOARD1，明确 OS clipboard race；其模型结果没有可靠证明 clipboard 造成失败。 | 可作为不同业务域的**机制复现/补强**，不能称为新机制。 |
| MECH-02 Global Undo | 当前已有 spec 未发现同一 Calc Undo 栈跨 Actor 撤销对方有效改动的直接机制题。 | 仍是本组较新的机制候选；脚本正负控已成立。 |
| MECH-03 Focus routing | 多个双 GUI 任务都涉及抢焦点/窗口切换；`spec_m1.md` 也写到窗口窃焦。 | 不是新机制；本题价值在提供可审计的 X11 焦点错误实证，但不应称为低覆盖发现。 |
| MECH-04 Active-cell/range drift | `spec_a3.md` 已明确共享 active cell、Name Box 与表格选择状态。 | 是排序情境下的更窄变体/复现，不宜宣称全新机制。 |
| 旧 MECH-05 SESSION-LEASE | `spec_x1/x2/w3/w4.md` 多个任务已有同一 cookie session、登录失效、会话过滤/选择器共享。 | **不作为新 Case 继续实现**：身份轮换能带来细微差别，但当前投资回报不足，且 session-generation Oracle/角色登录较难保持自然可信。 |

因此本组的准确贡献不是“五种前所未见机制”，而是补强已有的 Clipboard/Focus/Selection 失败因果证据，并增加一个在现有任务卡中少见的跨 Actor 全局 Undo 机制。MECH-01/03/04 可继续作为验证/扩展，但 portfolio 统计必须标为机制复现或细化。

### MECH-05 替代候选：Writer TRACK-CHANGES-MODE（待原型门控）

- **替换原因：**登录/会话竞争已反复出现；不再靠新应用包装重复 session race。
- **共享状态：**同一份 Writer 合规变更说明的全局“记录修改”模式；不是活动记录、窗口焦点、选区、剪贴板或撤销栈。
- **日常工作流：**A 按已批准的监管措辞修订“审批边界”一段，要求修改保留为可审阅修订；B 在另一个不重叠章节补上最终版本的联系方式，要求该处为普通已定稿文本，不产生待接受修订。初始状态为 Track Changes 关闭。
- **公平终态：**A 的精确措辞必须仍以 tracked insertion/deletion 存在；B 的文本必须正确且不带 tracked-change marker；其它内容不变。MA-ID 下两人分别设置所需模式，应可通过。Shared 中若记录修改开关在“设模式—定位—输入”之间被另一方切换，可留下 A 未跟踪或 B 意外带修订的可观察状态；自然恢复/复核成功也记 PASS。
- **独立桌面对照：**两份同哈希 ODT，等价初始 Track Changes=OFF；独立保存后对比可见文本及 ODT change-tracking XML。Oracle 只由 Guest 之外的 evaluator 读取，不向 Actor 暴露。
- **机制门槛：**先验证 Writer GUI 操作记录修改开关、ODT XML Oracle 能区分 A tracked/B plain；然后 Guest scripted 正控 (A tracked + B plain 均 PASS) 与固定交错负控 (在一次输入前切换模式，能检出属性错配)。若 Writer 无法可靠保存/导出可审计的修订状态，立即放弃此候选，不转成强制调度模型实验。
- **与旧内容的边界：**`spec_e1.md` 的 Writer Insert/Overwrite 是键入模式；Track Changes 决定文本是否进入文档修订审计，是不同应用语义，但二者都属于“文档模式泄漏”的上位家族。故 MECH-05 不包装为全新机制家族，只作为共享编辑器文档状态变体；后续只在 controls 证明能稳定区分后再进入模型 Pilot。

## MECH-05 实际原型与真实 Guest 控件（2026-11-18；TRACK-CHANGES-MODE 0.1.0）

- **重新选型：**原 SESSION-LEASE 候选因 `spec_x1/x2/w3/w4` 已多次覆盖同一 cookie/session 共享而冻结。替换为 Writer 文档级 Record Changes 模式；不将它包装成此前未见过的“全新机制家族”，而作为共享文档模式泄漏变体；区别于 `spec_e1.md` 的 Insert/Overwrite 字符替换模式。
- **Actor A：**把访问审批措辞从“两名指定审阅者”改成“五名指定审阅者”，并要求这条改动保持可审阅修订、不要接受。**Actor B：**把另一段待确认联系方式改为 `compliance-ops@example.org`，要求普通定稿文本、不得被 Track Changes 标记。文档其余控制文本必须不变。双方都是日常合规文档协作里合理的目标，且共同可满足。
- **Fixture：**`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets/mechanism_expansion_v1/mech05/access-review-draft.odt`，SHA-256 `bf01e60c60a53fb18c27f478bb26aa2ee6ccac8451d9417a5d7e4dd63ba22721`；初始 Record Changes=OFF。生成器、两个 Task wrapper、XML Oracle 与 Case Card 已新增；Task/Oracle 版本 `0.1.0`。
- **自动测试：**`tests/test_mech05.py` 4 项通过，覆盖初始 fixture、A 精确 tracked replacement、B plain text 与 tracked-text 区分、A 仅改字但未保留修订时判 FAIL。
- **真实 Guest scripted controls：**正控与固定交错控制均通过。正控中 GUI 菜单 `Edit > Track Changes > Record` 操作得到 A=PASS、B=PASS；ODT 中正好有 2 个 change regions，旧审批措辞为 tracked deletion，新措辞为 tracked insertion，联系方式保持普通文本。固定机制负控在 A 开启模式后由 B 关闭全局模式并完成其普通文本，再由 A 输入：A 可见文案正确但缺少 tracked revision 因而 FAIL；B=PASS。这只是刻意的机制 control，不是自然 Shared 模型失败。报告 `/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls/mech05-guest-control-20261118T105119Z-509781/report.json`；该 run Guest 关闭且所属容器销毁，外部 `sharp_bhabha` 未被停止。
- **无效尝试也保留：**首次误用 `Ctrl+Shift+E`，GUI 未进入记录模式，正控如实 FAIL（`...103112Z-500976`）；另一次 host 系统 Python 缺 `gymnasium`、Guest 未创建（`...102917Z-500198`）。二者不纳入机制证据。单独 host-headless UNO 可行性检查只验证 Writer/ODT 实际标记格式，不计为 Guest 或 Agent 结果。
- **现状：**MECH-05 有真实 Guest 正/负控和可审计 Oracle，但没有任何模型 arm。不得因此算成用户最终要求的 PASS/FAIL/FAIL case；下一门槛为正确 GPT-6-Sol 的 MA-ID 先完成（两个 Actor status=done 且 Oracle=1），再决定是否执行 Shared/Shared+Lock。考虑 MECH-02 最近一次模型 triplet 因 SSE idle timeout 花费约 46 分钟但未产生有效 baseline，当前暂缓重复昂贵调用。


### MECH-05 后续模型验证与当前判定（2026-11-18）

- v0.1.0 MA-ID 历史运行：A 未生成 tracked revision，B 通过。该版本的独立基线任务失败，Shared 未跑。
- v0.1.1 MA-ID：模型正确操作的 Writer 截图显示旧句删除标记、新句插入标记，但旧 Oracle 把修订标记中的字符串直接拼进正文，结果呈现假阴性风险；该结果保留为 Oracle-ambiguous，不算 Pass 或 Fail。
- Oracle/task 0.1.2：有效正文文本排除已标记的删除内容，同时继续要求旧文案 tracked deletion 与新文案 tracked insertion。5 个 Parser 测试、真实 Guest 正控 A/B PASS/PASS、固定交错负控 A FAIL/B PASS。报告路径见 case card。
- GPT-6-Sol 模型结果（预算 16，Codex CLI 0.155.0）：MA-ID A/B PASS/PASS（A 达 16-call cap、状态 max_steps，但有明确 terminal turn.completed 与短完成消息；B done）；Shared A FAIL/B PASS，双方均有 terminal 结果、无 API/Guest error；Shared+Lock A/B PASS/PASS，action_lock=true。
- Shared A 失败检查为 approval_text_correct=false、approval_change_tracked=false；最后截图显示原审批句仍被选中，Actor 声称未能完成/保存；B 的联系方式正确且普通未跟踪。焦点窗口日志都指 Writer，未见窗口误路由。动作确有同窗口的 selection/caret 操作竞争，但没有足够直接事件证明 B 切换了 A 的 Track Changes 模式，因此对“共享文档编辑造成未完成”有证据，对“全局 Record 开关是直接原因”仅是待验证解释。
- Shared+Lock 两位均通过且记录 24 个锁事件，所以此题不是目标 PASS/FAIL/FAIL case；锁在此试验中表现为恢复，不应为得到锁臂失败而改任务或调度。具体记录见 case card 的 triplet v0.1.2。
- 该 triplet 的 MA-ID result 在 20261118T113640Z 目录；Shared 与 Shared+Lock 在 20261118T114821Z 目录，其 ma-id-reference.json 明确指向基线。总体判定：保留为机制探索/锁可恢复证据，不计达标 case，不再仅为寻求 Shared+Lock FAIL 重复。

## 2026-11-18 后续：MECH-06..09 全局 Undo 机制族

在 MECH-02（共享 Calc 撤销栈）之后新增四个任务实例：采购订单异常复核、值班覆盖交接、会议行动项跟进、部门费用核对。四题均有独立 ODS Fixture/Oracle；v0.1.0 的 Guest 正控和固定交错负控逐题通过。四题复用同一 Calc Undo 机制，不应计作四种机制。MECH-06 v0.1.0 的 GPT-6-Sol 三臂未达目标组合：MA-ID PASS/PASS、Shared PASS/PASS、Shared+Lock A FAIL（18-call cap）/B PASS；Shared 可见任务重做恢复，锁臂失败的机制归因不充分。随后 v0.2.0 三臂也未达目标：MA-ID PASS/PASS，Shared PASS/PASS（A 到 18-call cap），Shared+Lock A PASS/B FAIL。时间线解释为 Shared 中 B 的提交早于 A 临时编辑，A 的 Undo 因而撤销自己的改动；Shared+Lock 中 B 提交落在 A 临时编辑后、Undo 前，B 目标值被撤销。按此证据，v0.3.0 改为启动时预选 A 的临时编辑单元格并要求 A 先直接执行临时编辑，再做常规复核；B 仍做真实单字段修改。四题 v0.3 控件及模型结果待验证。任何 scripted negative 仅是机制 control，不算模型失败。详细任务说明、Oracle、版本及复现方式见 `tasks/mechanism_expansion_v1/MECH06_09_GLOBAL_UNDO_CASE_FAMILY_20261118.md`。
