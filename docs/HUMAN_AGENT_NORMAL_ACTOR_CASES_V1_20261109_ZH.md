# Human-like Actor 候选池、HA-TRIAGE Pilot 与后续计划（更新：2026-11-10）

> **最新状态（2026-11-10）：** 本文较早章节中的“等待有效 API 凭据”及“HA-EVIDENCE 将作为第二 Case”的计划为历史快照，已被后续实验更新。当前可用有效凭据的 Codex Harness 已完成 HA-PO-ARCHIVE（第二 Human–Agent Case）v0.1.4 Independent / natural Shared / Shared+PerActionLock 核心 Pilot，以及 v0.1.5 User-only 归档确认截图正控。natural Shared 有一例 Agent PASS、User FAIL，并有 Agent click 改变用户文件选择器目录的逐帧证据。最新完整状态见 [`HA_PO_ARCHIVE_CASE_V1_20261110_ZH.md`](HA_PO_ARCHIVE_CASE_V1_20261110_ZH.md)。每条件只有一次，不声称重复性或泛化。

## 目标与边界

本扩展只改变 Actor 组合：A 是 Codex/OSWorld GUI Harness 驱动的真实模型 Agent；B 是 ScriptedPolicy/ScriptedGUIActor 驱动的正常 GUI 轨迹。两者有独立任务和 Oracle。新增主张是模型 Agent 与正常桌面用户并发时的用户结果、额外操作、等待和恢复成本，不是宣称发现新的焦点/上下文机制。

Linux Human Case 1–5 已冻结。Case 4 的 LibreOffice Writer 无响应及 final-state Oracle 假阳性记录保留；不再修复或补跑。新实验使用独立 case ID 与 RAID 输出目录，不删改旧 runs/overlays。

本分支的新增方向仍是 **一个真实 Codex/OSWorld GUI Agent + 一个 scripted normal-user GUI Actor**。这只增加 Actor 组合，不替代既有双模型 Agent 主线；在首个共享桌面模型对照有效前，后续 Case 只做候选/任务卡设计，不扩建软件栈。

## 候选池（8个）

重合与可行性评分均为1–5；不是验证状态。

| ID | Agent A / User B | 可观测共享状态和 Oracle | 重合/可行 | 处置 |
|---|---|---|---|---|
| HA-TICKET | A核验合成售后工单、证据和政策，退款并解决；B在独立handoff表单提交一条日常运输跟进 | 同一Guest/Browser前台；TTR事务Oracle + handoff提交Oracle | 4/4 | **No-go / 冻结**。真实 Codex 多次未完成 Review→Refund→Resolve 链；与既有 TTR 重合过高，不再调这个复杂版。 |
| HA-TRIAGE | A查工单、订单、送货证据和退货政策，提交一页建议性分诊简报；B更新另一工单的跟进信息 | T-1042/T-1043分离；triage与handoff独立Oracle；同一Guest中为独立Chrome原生窗口 | 4/5 | **当前首个 PoC**。保留 Case Desk 的真实 GUI 信息检索，但不要求创建正式Review/退款/关单，降低无谓复杂度。 |
| HA-MAIL | A阅读数封本地邮件并为客户请求分类、留回复草稿；B回复另一封团队排班邮件 | Thunderbird前台/邮件库；草稿与用户回复Oracle | 2/3 | 候选；先核实Guest内客户端/profile fixture，不实际外发。 |
| HA-EVIDENCE | A核对案件PDF/图片，选出有效材料并生成交接说明；B下载并存档一份常规附件 | Browser/FileManager/Downloads；内容hash、路径和用户附件Oracle | 3/3 | 候选；避免仅改名/manifest以免贴近Workspace Assembly。 |
| HA-QA | A用GUI编辑器修复小型请求页缺陷并浏览器回归；B提交另一条正常表单 | 编辑器/Browser；回归状态与用户提交Oracle | 3/2 | 条件候选；只在GUI-only Codex单臂可解时纳入，不以CLI代GUI。 |
| HA-CALENDAR | A根据邮件安排多方会议；B正常添加个人专注时段 | 日历availability/事件；字段、无重叠Oracle | 4/1 | 暂缓：Guest客户端与可重置fixture未知。 |
| HA-PROCUREMENT | A核对采购申请并制作审批摘要；B更新供应商到货备注 | Spreadsheet/Browser/文档；采购、报告、备注Oracle | 1/2 | 首批淘汰：与Spreadsheet Handoff、Data-to-Deck、Calc selection高度重合且依赖LO。 |
| HA-REPORT | A汇总会后材料生成总结和待办；B确认自己的一条会议记录任务 | 文件/Writer/网页；摘要及状态Oracle | 2/2 | 后备：与Data-to-Deck/Workspace Assembly相邻，且LO不稳。 |
| HA-BOOKING | A从案件资料预约合成维修时段；B改期自己的另一张预约 | 同一Guest内离线预约库存；独立预约记录Oracle | 4/3 | 暂定入选；先实现本地可复位预约fixture，不触达真实服务商。 |

## 首选 Pilot：HA-TRIAGE v0.1.0

- **当前 Case ID/version**：`ha-evidence-triage-normal-user-v1 / 0.1.0`。原 HA-TICKET 是退款/解决复杂版，已 No-go；不可把两者混为一个验证任务。
- **Actor A /真实模型**：在 Case Desk GUI 查看 T-1042、订单 O-2048、送货证据 DELIVERY-EV-77 和 POLICY-RET-4；在独立 Shift Triage Brief 表单写准确分类、建议下一步、证据/政策ID及简短理由。只写 advisory brief，不执行 Review、退款、预检或状态更新。
- **Actor B /模拟用户**：在 Shift Handoff GUI 将另一张 T-1043 更新为固定准确说明并设定跟进时间。当前策略为六动作 fixed-open-loop；先用显式点击落入文本框的版本，不允许读Agent私有答案/评估器。
- **Oracle**：Agent必须确实通过 GUI 读取票据/订单/政策页面、提交内容符合 source-grounded rubric，且 T-1042 仍 OPEN、O-2048 仍 PAID、无Review/Refund/precheck；User Oracle独立检查handoff精确字段与提交次数。Oracle从服务端fixture状态判定，不以截图或agent自报代替。
- **条件等价**：Independent 两个Guest分别重置为同一 TTR、triage、handoff hashes；Shared/Shared+Lock一个Guest/一个桌面，同一Chrome profile中两任务为不同原生窗口；Shared 不安排固定先后。Lock 仅为消融。模型条件使用相同 Codex CLI 0.155.0、gpt-6-sol、GUI权限、40 GUI MCP call 上限与1200秒 Agent上限。
- **记录**：联合/分Actor成功率、焦点与窗口变更、窗口标题误路由、User输入/API错误、额外GUI动作/重输/恢复时间、锁等待、模型GUI调用数、token、Agent wall time；自然Shared与任何机制probe分开。

## 验证顺序与指标

1. 离线positive/negative controls：fixture、handoff API、TTR evaluate、manifest/hash及双Oracle均有独立测试。
2. 先验证真实Guest readiness、GUI可见/可操作、User-only结果、Agent-only可解、reset与两桌面状态等价；窗口标题不能替代Oracle。
3. 再跑 Independent（双Guest）与自然Shared（同Guest）各至少一例；natural Shared不预设必须FAIL。Shared+PerActionLock只有在主对照有效后作为消融。
4. 当前 User策略先用固定回放；仅当动作/错误日志可用后，再设计可恢复策略。恢复Policy只能看用户自己的视觉状态与动作历史，不访问另一Actor的私有答案或Evaluator。
5. 所有 Guest、认证、服务、模型端点/授权或 Oracle 故障都标为 infrastructure-invalid，不能记成任务FAIL；保留raw日志并单独写 adjudication。

逐run记 User/Agent/joint success、Oracle细项、User动作/误路由/重输/额外操作/等待/恢复起止、焦点和窗口截图、Agent GUI MCP调用数、Codex JSON返回的input/cached/output/reasoning token、模型wall time、Guest boot/readiness与resource ledger。首版fixed User没有恢复行为时，恢复成本记0但不推导“无干扰”。

## 首个 Pilot 的真实运行状态（2026-11-10）

| Run | 条件/结果 | 解释 |
|---|---|---|
| `20-triage-user-only` | User-only PASS | 正向控制；旧User脚本五动作版。 |
| `21-triage-user-negative-control` | Negative control正确检测错误note | 证明User Oracle会拒绝错误文本；不是正常任务FAIL。 |
| `22-triage-agent-only` | **真实 gpt-6-sol/Codex GUI Agent PASS**；18 GUI MCP calls、约442s、input 322,638（cached 272,896）、output 669 | Agent单臂可解性的有效证据；未做重复试次。 |
| `23-triage-independent` | Infra-invalid，Chrome冷启动/页面ready失败；无model调用 | setup失败，不是Actor失败。 |
| `24-triage-independent-retry1` | Agent PASS；User未提交，因旧脚本把文字打进地址栏 | Agent侧结果有效；联合结果不能用于Shared干扰结论。 |
| `25-triage-user-only-click-focus` | User-only PASS，6动作、零脚本额外操作 | 显式点击后的正向控制，确认旧User脚本bug已修。 |
| `26-triage-independent-user-focusfix` | runner/SSH进程中断于Guest setup，模型与Actor均未启动；精确run标签容器已清理、overlays保留 | 状态是中断/infra-invalid，不算失败；根因未确认。 |
| `27-triage-independent-focusfix2` | Chrome可见窗口URL加载失败并有BadWindow诊断；无model调用 | setup-invalid。后续在新triage runner中增加disable-gpu、延长冷启动ready等待、wmctrl焦点验证与失败截图。 |
| `28-triage-independent-chrome-retry` | 两Guest均KVM启动；三类fixture hashes相同；User 6动作 PASS；Codex请求被 endpoint **401 Invalid token** 拒绝、0 GUI MCP、0 usage event | **Auth-invalid，不是Agent task FAIL，也不能算模型Independent对照。** raw run保留，另有`adjudication.json`。 |

修复后的Chrome路径在Run 28完成两Guest、每Guest双原生窗口setup且User Oracle通过，但还只有一例，不声称稳定性已充分验证。setup截图还发现Chrome的“Save password?”泡泡；triage-only后续runner已加Esc清除，并把误导性的`both_windows_visible`改为两个窗口各自是否存在/前台是否正确的字段（**这两个小修尚未再做真实Guest复验**）。窗口同时不在前台是自然的遮挡/焦点现象，记录focus change，而不把“窗口列表中存在”夸成“同屏都可见”。HealthCare RAID上已保留所有上述输出与qcow2 overlays；根盘接近满载，但当时约30GiB可用，临时Guest与结果目录都在RAID。triage相关离线回归在Chrome-startup修复后为 **26 passed**；Esc/字段命名修订后需再跑一次。

**首Pilot结论**：User-only正控和真实 Agent-only正控通过；Independent的User侧在Run 28通过，但Agent侧因认证无效不可评分。自然Shared尚未运行；当前没有任何“Shared让User/Agent失败”的证据，也不能宣称HA-TRIAGE已经达到Shared干扰主张。

后续轻量端点预检确认：一次 HealthCare 默认壳中的 `OPENAI_API_KEY` 对`https://api.haogpt.net/v1`得到401 Invalid token；这不能证明用户早先提供的那把Key已过期，只能说明当时继承值不可用/不匹配。`docode.cc/v1`备选端点还没有获得有效鉴权测试：`29–33-docode-*`仅是Codex CLI命令/stdio/CODEX_HOME/key继承预检，没有一项拿到有效模型响应（prompt quoting、stdin EOF、RAID CODEX_HOME权限、非交互key缺失）；这些目录不是Case实验。所有输出只保留无密钥日志。**不要再用当前继承值发模型请求**；需先重新安全注入当前可用的Sol key并验证端点。

## 暂定入选的后续Case（只做任务卡雏形，尚未实现）

为覆盖不同共享状态而避免复制TTR，后续暂定总组合为 **HA-TRIAGE + 3种**，先做条件验证后逐个实现；目前不是PASS清单。

| ID / 预期共享状态 | Actor A（模型） | Actor B（正常用户） | 各自可验证结果 /主要干扰证据 | 可行性门槛与和既有Case差异 |
|---|---|---|---|---|
| **HA-MAIL** / 邮件列表、草稿/收件人字段 | 阅读本地客户邮件线程及订单/政策线索，创建一封不发送的准确客户回复草稿 | 回复另一封内部协调邮件并发送到正确收件人 | Draft正文/recipient/未误发；用户sent message/线程/收件人；误线程、草稿被覆盖、收件人错、重打/等待 | Thunderbird现有OSWorld snapshot依赖远程Outlook，不直接用其远程账户；先验证可用 Local Folders/离线可复位mailbox。不发送外部真邮件。与旧七题无邮件工作流直重叠。 |
| **HA-BOOKING** / 预约slot库存与当前前台表单 | 为合成客户按设备/时限证据预约一个满足条件的维修时段 | 为自己另一张预约单改期到给定窗口 | Agent reservation ID/slot正确且无冲突；User改期记录准确；冲突/被占用slot、错误确认、等待、回退 | 只用Guest内合成预约站点和离线Oracle，不触达真实日历/供应商；中等成本。与数据/Writer任务差异高。 |
| **HA-EVIDENCE** / 浏览器下载、PDF预览/FileManager焦点 | 查阅故障PDF与照片，记录关键证据/物件结论到独立简报 | 下载另一份日常账单并存入指定月份文件夹，核验名称与内容 | evidence citations与结论；User路径/哈希；modal/窗口误路由、误保存位置、额外导航/恢复 | 复用真实PDF viewer/FileManager与本地fixture；必须让Agent做内容判断，不能退化为纯文件重命名。与Workspace Assembly相邻，需用不同的Oracle主张和短任务避免重复。 |

备选 HA-CALENDAR（客户端/fixture较难）、HA-QA（与Build-and-Verify重合）、HA-REPORT（与Data-to-Deck和Workspace Assembly重合）不列入首批；HA-PROCUREMENT继续淘汰。

## Portfolio 对照

七题为 Data-to-Deck、Ticket-to-Resolution、Build-and-Verify、Timeline-and-Assets、Model-and-Review、Spreadsheet Handoff、Workspace Assembly；证据状态不全相同，不能统称七题都完成GUI Agent验证。五类Human机制覆盖焦点路由、共享剪贴板、Calc选区、Writer Undo、PDF modal。新Case要报告正常User任务结果和成本，而非把旧机制换背景重命名。

## 下一步与复现

1. 先为 GPT-6-Sol/API端点获得当前可用的授权，再以相同版本/权限/预算完成 HA-TRIAGE 的自然Shared；如该条件有效且环境许可，再跑 Shared+PerActionLock。模型请求需通过安全运行环境传入凭据，不把token写入文档、命令行参数或实验输出。
2. 明确记录 Shared 的自然交错与User结果；若失败，拆分模型/Guest/Oracle原因，不人为强制失败或挑有利样本。
3. 只有首Pilot能在至少一个有效Shared与独立/正控中完成时，才开始实现HA-MAIL、HA-BOOKING、HA-EVIDENCE；各自先Task Card+fixture+Oracle+User脚本+独立/共享负控，再真实模型单臂。
4. 新实验均写到`/mnt/raid1/mjh/Projects/CoDesk-human-agent-normal-actor-pilot-20261109/<unique-run-dir>`，不同run不覆盖。标准runner示例：`python -m oscombo.human_agent_triage_case_runner --mode independent --out <RAID新目录> --base-url https://api.haogpt.net/v1 --model gpt-6-sol --budget 40 --timeout 1200`；另支持`user-only`、`agent-only`、`shared`、`shared-lock`。仅在endpoint认证已核验后运行模型模式。

本文件包含候选和一个已实现Pilot规格；后续三个Case目前只是设计雏形，不是实现或PASS报告。旧 Human Case 1–5保持冻结。


## GPT-6-Sol 鉴权复核（2026-11-10，更新 Run 28 之后）

用户在本轮授权注入此前提供的凭据后，我用固定 Codex CLI 0.155.0、`gpt-6-sol` 与 Responses API 做了两次最小 `OK` 请求：

| Smoke | Base URL | Codex结果 | 判定 |
|---|---|---|---|
| `35-sol-auth-smoke-docode` | `https://docode.cc/v1` | HTTP 401 `Invalid token`，无模型输出 | `auth-invalid`；不是模型任务失败 |
| `36-sol-auth-smoke-haogpt` | `https://api.haogpt.net/v1` | HTTP 401 `Invalid token`，无模型输出 | `auth-invalid`；不是模型任务失败 |

raw stderr/stdout（不含凭据）分别留在 `/mnt/raid1/mjh/Projects/CoDesk-human-agent-shared-poc-20261109/35-sol-auth-smoke-docode/` 和 `.../36-sol-auth-smoke-haogpt/`。凭据通过一次性输入管道供远端进程读取，没有写入远端文件或实验配置；日志中无凭据。两次都在 Codex 启动真实 GUI Harness 前失败，模型 usage 与 GUI MCP calls 均为0。这个结果说明**本次提供的凭据对两个已配置端点都无效/不被接受**，不能据此判断端点协议或历史 Run 22 的凭据状态。

因此停止真实模型请求，不启动 Shared / Shared+Lock，也不将401归类为 Agent FAIL。当前HA-TRIAGE状态没有改变：User-only及历史Agent-only正控保留，Run 28与本次端点测试均为认证无效，尚无可评分的有效Independent模型对照或任何Shared干扰证据。恢复实验需要一个当前有效、可导出给 Codex 子进程的 GPT-6-Sol 凭据；应通过外部密钥管理/受控环境变量注入，不要再把密钥明文贴进聊天或实验文档。建议轮换已在聊天中分享的密钥。

本次代码离线回归复核：`git diff --check`通过；六组相关测试 `26 passed`（2.79s）。
## 认证阻塞后的可运行性推进：真实Guest用户正控（2026-11-10）

鉴权失败后没有继续发模型请求；改为完成当前runner的非模型真实Guest闭环，验证最新Chrome启动/焦点修订和用户Oracle：

| 输出目录 | 状态 | 说明 |
|---|---|---|
| `37-triage-user-only-post-keyguard` | pre-run-invalid | 首次启动没有设置 `OSWORLD_DIR`，在Guest启动前报配置缺失；没有模型/Actor调用。原目录保留。 |
| `38-triage-user-only-post-keyguard` | pre-run-invalid | 补了 `OSWORLD_DIR` 后，OSWorld Docker Provider 导入时缺少 `swcub` Python包路径，Guest容器未创建、Actor未启动。后续把已有机制仓库中的同哈希 `resource_safety.py` 包目录纳入 `PYTHONPATH`，未改动或复制安全模块。原目录保留。 |
| `39-triage-user-only-post-keyguard` | **valid User-only PASS** | 单Guest使用最新triage runner；`experiment_valid=true`、用户Oracle全部通过、精确备注和跟进时间各提交一次；6动作、0误输入/动作错误/额外操作/恢复，0锁等待，用户Actor约33.2s。非模型、非Shared对照。 |

Run 39的Guest setup确认Case Desk与Handoff两个窗口都存在、初始Case Desk前台验证成功；Chrome readiness无重试。GUI里一次预期Alt+Tab焦点切换，之后五个用户操作都发往Handoff；最终Oracle检查`fixture_exists/submitted/ticket_id/note/follow_up`全部为true，提交数1。它验证了最新User路径与Oracle，但**不代表Shared发生干扰**，也不能替代Agent或reset等价性对照。

资源与cleanup：Run 39的OSWorld Docker Guest成功启动，容器内QEMU命令为`-machine pc,accel=kvm`，实际KVM可读；ready等待31.4s，总运行218.2s（主要时间为冷启动）。Guest overlay约486 MiB、输出及overlay均在RAID；resource ledger记录同一run owner的Guest容器正常destroy，运行后没有活跃CoDesk Guest。运行前机器80 logical CPUs、load约11.1、CPU PSI约0、可用内存约216 GiB、RAID余量约1.23 TiB；根盘仍只剩约40 GB且swap已满（虽内存available充足，继续留意swap，避免向根盘写大文件）。

Run 39启动期间发现的两个环境配置错误已用单独的新目录重跑解决；未删除这些失败目录或任何旧overlay。相关六组离线测试复核仍为26 passed，`git diff --check`通过。

**当前判定不变**：GUI Guest与User-only正控当前可运行，真实GPT-6-Sol仍被两个端点的401凭据拒绝。没有有效的新Independent/Shared模型run；等到有效凭据安全注入前，不进入Shared模型实验，也不把这些infra/auth结果记作任务失败。
### HealthCare 可复现入口

本次发现OSWorld Docker Provider依赖的`swcub.resource_safety`不在当前case仓库或OSWorld虚拟环境内，直接从repo启动会在Guest前失败。因此新增`infra/run_human_agent_triage.sh`：设置固定OSWorld checkout，并将当前repo与现有安全模块所在树加入`PYTHONPATH`；不会写API key或绕过鉴权。脚本支持通过`OSWORLD_DIR`、`OSWORLD_PYTHON`和`SWCUB_SAFETY_ROOT`覆盖默认值。已通过`bash -n`和`--help` smoke；Run 39是通过相同路径变量的真实User-only验证。

HealthCare后续应使用：

```bash
infra/run_human_agent_triage.sh --mode user-only --out /mnt/raid1/mjh/Projects/CoDesk-human-agent-normal-actor-pilot-20261109/<unique-run-dir>
```

模型模式使用同一脚本及相同`--model gpt-6-sol --base-url https://api.haogpt.net/v1 --budget 40 --timeout 1200`参数；仅在`OPENAI_API_KEY`由受控方式安全注入且最小Codex smoke得到有效响应后启动。不要把凭据放在shell命令行或脚本参数里。
## GPT-6-Sol 凭据复验与 HA-TRIAGE 三条件真实 Pilot（2026-11-10，最新状态）

本节覆盖上文“等有效凭据、尚无有效 Independent / Shared”这一旧状态；历史 35/36 两次 401 记录仍保留为当时的认证无效尝试。用户随后提供了新凭据（本文及配置中均不保存该值）。一次性输入管道对首选 https://api.haogpt.net/v1/responses 的 gpt-6-sol 最小请求返回 HTTP 200；随后 Codex CLI 0.155.0 实际启动 GUI MCP 并完成模型调用。没有触碰备用 docode endpoint，也没有把密钥写进命令参数、run 目录或文档。

| RAID 运行目录 | 条件 | 有效性与任务结果 | 主要记录 |
|---|---|---|---|
| 40-triage-independent-newsol-20261110 | Independent | **有效；User PASS、Agent PASS、联合 PASS** | 两个Guest的 TTR / handoff / triage 初始hash全部一致；User 6/6 GUI操作、0误路由、0 extra、33.7s；Agent 18次GUI MCP、352.1s、315,530 input / 584 output tokens；总耗时590.2s。真实Guest均记录 KVM，2个独立Guest在结束后已清理。 |
| 41-triage-shared-natural-newsol-20261110 | Shared，自然并发 | **有效；Agent PASS、User FAIL、联合 FAIL** | User完成6个基准动作但其中3次落在Chrome “New Tab”而非handoff表单；handoff提交数0、note/follow-up不符；无API错误、无自动恢复。日志可见Agent新建tab和User动作竞争同一焦点。Agent最终经26次GUI MCP（比独立条件多8次）完成，550.1s、574,177 input / 881 output tokens；7次动作发生在非授权窗口/焦点代理上，期间10次焦点转换；User未受益于恢复逻辑（仍是open-loop）。总耗时728.5s。 |
| 42-triage-shared-lock-newsol-20261110 | Shared+PerActionLock | **有效的任务失败；User FAIL、Agent FAIL、联合 FAIL** | 7次Agent GUI调用由逐动作锁串行化，但Agent停在handoff窗口，没有读取Case Desk来源或提交简报；Codex最终明确报告无法访问来源并留下未保存结果。User handoff提交数0。User动作等待锁累计6.58s（Agent action-lock事件累计等待约2.72s）。虽然动作没有同时注入，PerActionLock并未提供“整个任务/窗口上下文”的隔离；Agent的7/7次GUI调用都落在Agent不应使用的窗口。不能把这一点解释为锁造成Agent能力退化或锁已修好干扰——每个条件目前只有单次。总耗时323.3s。 |

所有三个模型 run 均标记 experiment_valid=true，使用同一 case version 0.1.0、同一 gpt-6-sol / Codex CLI 0.155.0、40 GUI MCP calls / 1200s Agent上限，初始三类fixture内容hash相同。Shared 与 Shared+Lock 都只使用1个 Guest；Guest live QEMU均报告KVM，结果与overlay在RAID；当前同项目Docker运行容器为空。指定26项相关pytest再次通过（26 passed / 2.72s），git diff --check通过。机器仍应避免向根盘写大文件（约37–40GB空闲；RAID约1.2TB空闲）。

### Pilot 判读与限制

- **支持继续扩展的初步路线证据**：同一个任务中，Independent一例双方均通过；自然Shared一例 Agent 能完成而正常User没有完成，且有逐动作窗口/焦点/HTTP Oracle证据。这符合“真实任务并发，而非预设输赢”的 PoC 目标。
- **尚未证明普遍性或重复性**：每条件仅一例，不能据此估计干扰概率或Claim所有共享桌面都会失败；Shared+Lock本例两Actor都失败，也不是锁的确定性效果。
- **发现的设计/测量缺口**：PerActionLock只序列化输入动作，不固定任务间的激活窗口，也不保护多步骤GUI事务；User的窗口标题仍是handoff时，Oracle却显示没有提交，说明仅用窗口标题做焦点代理不够，后续需保留实际服务端状态、加入可验证的控件/活动tab焦点证据。不要通过改Oracle或强制先后顺序掩盖本轮结果。
- **有成本的自然干扰记录**：Shared下Agent自己额外用了8次GUI调用，Agent wall time多约198s，输入tokens约增至独立条件的1.82倍；这些只是两次单样本的观察差异，不是因果均值。User fixed-open-loop策略没有自动恢复，因此User恢复时间本轮不可估计（记0不等于无干扰）。
- 42号Run展示了锁在边界处的等待成本，但并没有给出好的隔离结果。不要把三条条件合并为“Shared必败、锁有效/无效”的结论。

### 下一步（修订）

首Pilot已达到“至少一次有效Independent + 一次真实Shared模型对照”的推进门槛。先冻结上述三个run及原始轨迹，基于同一initial fixture检查并补足焦点/控件级观察方法，再把 HA-EVIDENCE（本地证据文件审核 + 用户归档普通附件）作为第二种Actor组合的候选Task Card进入实现；邮件与预约继续保留候选池。后续Case必须先做User-only / Agent-only Oracle正控，再做Independent与自然Shared；任何模型重复、锁消融或用户恢复策略都分别记录，不能筛选有利样本。当前没有push/commit，也不应清理这些实验目录或overlays。

## 最新更新：HA-PO-ARCHIVE Case 2（2026-11-10）

已实现并完成小规模固定用户 Actor Pilot。详细任务卡、Oracle、复现步骤、全部关键运行、逐帧 GUI 干扰证据和限制见 [`HA_PO_ARCHIVE_CASE_V1_20261110_ZH.md`](HA_PO_ARCHIVE_CASE_V1_20261110_ZH.md)。

当前 runner 是 v0.1.5；v0.1.4 的核心对照结果为：Independent 双方 PASS；自然 Shared 中 Agent PASS、User FAIL（Agent 点击改变用户原生文件选择器目录，有截图与事件时间佐证）；Shared+PerActionLock 双方 PASS，但 User 锁等待 12.68s。v0.1.5 增加提交后等待以留存归档确认截图。每臂目前只有一次，不声称重复性/泛化；用户模拟仍是固定 open-loop，后续可以另开 recoverable strategy，不回写本轮结果。
## 最新更新：HA-MAIL Case 3（2026-11-10）

HA-MAIL 已实现并完成 User-only、Agent-only、Independent 双Guest及自然 Shared 单Guest的有效小规模 Pilot。详细 Task Card、界面/Oracle、逐动作结果、成本、限制与复现方法见 [HA_MAIL_CASE_V1_20261110_ZH.md](HA_MAIL_CASE_V1_20261110_ZH.md)。User-only、Agent-only与Independent双方均 PASS；自然 Shared 也为 User PASS + Agent PASS，联合 PASS。自然交错日志显示 Agent 首次截图时正处在用户正在操作的 OPS-117 回复页面，Agent 随后正常返回 Inbox 并完成客户线程；本次没有误路由、用户额外操作或任务失败。监视器记录的9次标题切换多数为 Agent 自己的预期导航，不作为9次干扰计数。该例适合证明 PoC 可审计和双任务可并发完成，不证明干扰概率；每臂仍只有单样本。

运行 78-mail-shared-natural-sol-v1-20261110 结束后 Guest/KVM 已清理；所有相关产物在 RAID 的 .../78-mail-shared-natural-sol-v1-20261110/。本轮没有新增代码改动或筛选删除旧 run；HA-MAIL 是否扩成多重复应以后续总体计划决定。

## 最新更新：HA-CALENDAR Case 4（2026-11-10）

HA-CALENDAR 已实现并完成一轮小规模 GUI-only Codex + Scripted User Pilot。详细 task card、fixture、Oracle、复现命令、逐动作证据、runner 修复和运行限制见 [`HA_CALENDAR_CASE_V1_20261110_ZH.md`](HA_CALENDAR_CASE_V1_20261110_ZH.md)。

最终 fixture 的 User-only PASS、Codex CLI 0.155.0 Agent-only PASS；Independent 两 Guest 中双方任务 PASS，原 runner 汇总被复制自 Mail 的 `review_count` 字段检查打断，结果未覆盖，并通过 `posthoc-assessment.json` 离线重新运行两个 Oracle / fixture 等价性审计。自然 Shared 一例为 Agent PASS、User FAIL：个人日历事件日期/时间/提醒正确，但标题仅存为 `FNovember report`；首个 Agent 截图与 User 表单填写/保存短暂重叠。PerActionLock 一例双 PASS，观察到 User 等锁约4.58s、Agent约5.68s。无错应用窗口轨迹，但同一 Chrome 内部输入焦点的测量不足；每臂仅单样本，不做概率或普遍因果结论。

试验过程中遇到两个非任务失败：第一次模型返回未发 GUI MCP 调用；另一次 Host healthcheck 经 Docker bridge 返回502。两者均未计入模型任务 FAIL。Host healthcheck 和独立 Fixture 等价性字段已修正并补测试。主要结果在 RAID，Guest 已清理；当前未 commit/push。


## 最新更新：HA-INVENTORY Case 5（2026-11-11）

HA-INVENTORY 已实现并完成一轮 GUI-only Codex + Scripted User Pilot。完整任务卡、fixture/Oracle、公式、复现命令、各臂结果和限制见 [HA_INVENTORY_CASE_V1_20261111_ZH.md](HA_INVENTORY_CASE_V1_20261111_ZH.md)。User-only、Agent-only、Independent 双 Guest、自然 Shared 和 Shared+PerActionLock 均有至少一条最终正确任务结果；Independent 两 Guest 初始状态完全相等。自然 Shared 下双方均完成，但 Agent 的首张 GUI 截图仅与 User 打开收货表短暂重叠，实质 Agent GUI 操作在用户结束后开始，故没有自然干扰成功证据。

Shared+Lock 初次有效运行中，User 的 lot 字段因脚本输入节奏过快记录为 LO1，随后通过增加逐字符输入间隔后 User-only 与 Shared+Lock 重跑 PASS。失败样本保留，不归因为干扰。本例是可运行的 PoC/pilot，不是已证明共享桌面伤害用户的 Case；固定用户回放仅5个GUI动作、任务过短、库存UI为离线合成应用。Run 输出和 overlay 均在 RAID，Guest cleanup 正常。完整回归测试 102 passed。未 commit/push。
