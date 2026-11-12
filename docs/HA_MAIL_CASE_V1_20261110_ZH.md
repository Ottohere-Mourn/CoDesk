# HA-MAIL：邮件线程处置与日常内部回复

日期：2026-11-10
Case ID：`ha-mail-review-normal-user-v1`
任务/fixture版本：`0.1.0`
状态：已实现离线邮件 fixture。自然条件的 User-only / Agent-only / Independent 均 PASS；自然 Shared #78 双方 PASS、未见任务损害。2026-11-11 另完成固定 25 秒用户启动偏移 probe：offset Independent #83 双方 PASS，offset Shared #84 为 User FAIL + Agent PASS，并有三次错焦点标记、截图/时间线和 Oracle 证据。该 FAIL 属受控交错，不是自然 Shared 结果；授权无效的 #82 作为 infrastructure-invalid 保留且不计任务失败。每臂样本仍少。

## Task Card

- **Actor A（Codex/OSWorld GUI Agent）**：在 CoDesk Mail 读取 `CUST-2048` 全部客户/仓库/服务消息及 `POL-WAR-3` Warranty/Delivery-Damage Playbook；选择正确 case label 与 priority；向 Casey Rivera 准备 replacement 回复草稿。必须保存为 Draft、不得发送、不得承诺退款或改源邮件。
- **Actor B（固定 scripted User）**：在 Inbox 打开 `OPS-117` Afternoon queue coverage；回复 `ops-oncall@company.test`，正文为 `I can cover 14:00-16:00 today; please assign me the queue.`；发送并标记该内部对话 Done。
- **共同 GUI 状态**：同一 Linux Guest 中单个 Chrome 窗口、同一 Inbox/选中邮件/回复编写器；两任务分别写客户线程和内部线程，因此业务终态兼容。独立臂各用一台从相同 fixture 创建的 Guest；Shared 使用同一 mailbox 与浏览器会话。邮件服务是 Guest 可见的 run-local 合成 Web app，不连接互联网邮箱、不发真实邮件。
- **User 工作流**：固定的5步可见鼠标/键盘回放；无自动恢复。GUI action、时间、窗口标题、截图和锁等待统一写到 `events.jsonl` / `shots/`。自然Shared不预排先后、不插入抢焦点动作。
- **Agent Oracle**（Actor 完成后在主机读取 SQLite）：只读到了正确 customer thread 与 policy；review 恰一次，label=`replacement_eligible`、priority=`P2`；草稿恰一封、收件人和 subject 正确，正文道歉/承诺replacement/包含“两工作日”派送时限；customer thread 未发送且仍Open；源邮件/政策摘要hash未变。
- **User Oracle**：内部线程 `OPS-117` 恰有一条发往 `ops-oncall@company.test` 的精确回复且 status=`done`。
- **模型权限与预算**：复用 Codex CLI `0.155.0` / `gpt-6-sol` / 现有 desktop GUI MCP，不实现新模型 Runtime，不开放 Guest CLI、HTTP/SQLite 或隐藏 Oracle；Agent budget 每臂40 GUI MCP calls / 1200s。

## 已完成结果

Artifacts 位于 RAID：`/mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/`。

| Run | 条件 | 判定与观测 |
|---|---|---|
| `74-mail-user-only-positive-v1-20261110` | User-only 正控 | **有效 PASS**。所有六项 Oracle 为真；User 5 GUI动作/29.3s，0多余操作、0错前台、0恢复、0锁等待；总run 197.4s，Guest KVM，清理完成。 |
| `75-mail-agent-only-sol-v1-20261110` | 真实 Agent-only 正控 | **有效 PASS**。所有14项 Agent Oracle 为真；14 GUI MCP calls/328.5s；220,412 input（157,634 cached）、502 output、54 reasoning tokens；无错前台动作；总run 512.6s，KVM，清理完成。Agent草稿以“replacement / two business days”为核心，未发送。 |
| `76-mail-independent-sol-v1-20261110` | Independent 尝试1 | **Infrastructure-invalid**，不可视为任务FAIL。一个Guest的Chrome只保持 `Untitled` 窗口，虽Guest与宿主healthcheck成功，却未加载 `/mail`；Actor/模型都未启动。资源ledger确认两个 run-owned容器均被清理。随后启动等待改为4轮且加入焦点重试/诊断。原始目录保留。 |
| `77-mail-independent-sol-retry1-20261110` | Independent双Guest | **有效，User PASS + Agent PASS，joint PASS**。fixture source hash与初始状态等价；两Guest均报告KVM。User 5动作/28.2s；Agent14 MCP calls/704.2s、220,188 input（160,084 cached）、443 output；0错前台。总run 981.1s，两个Guest均清理。 |
| 78-mail-shared-natural-sol-v1-20261110 | 单Guest自然Shared | **有效 PASS：User PASS + Agent PASS，joint PASS**。User 5动作/28.3s；Agent 15 GUI MCP calls/806.2s、244,479 input（200,705 cached）、548 output；无记录的错前台/误路由；总run 987.6s，Guest KVM、清理完成。用户选择 OPS-117 回复界面时，Agent 首张截图捕获到该界面；Agent 随后回 Inbox 并切到 CUST-2048，任务完成。 |

此前校准 runs `70–73-mail-user-only-*` 均保留。它们不是干扰实验：固定User脚本的坐标和页面加载等待尚未校准，依次出现点错Inbox行/错过回复按钮、正文输入或Send/Done点击未命中。#73已成功发送精确邮件，但未标记Done。不要把这些校准失败归因于共享干扰；以#74最终5步版本的User-only PASS为当前正控。

## 代码和复现

- App、run-scoped Fixture、HTTP访问记录和私有Oracle：`oscombo/human_apps/mail_workflow.py`
- Guest/Actor/模型实验协调、统一日志和清理：`oscombo/human_agent_mail_case_runner.py`
- HealthCare入口（OSWorld与资源安全模块路径已配置）：`infra/run_human_agent_mail.sh`
- 测试：`tests/test_mail_workflow.py`

```bash
# No-model User positive control
infra/run_human_agent_mail.sh --mode user-only --out /mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/<new-run>

# Model controls/comparisons: use a unique RAID output and provide GPT-6-Sol key through controlled stdin/env only
infra/run_human_agent_mail.sh --mode agent-only|independent|shared|shared-lock --out /mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/<new-run> --model gpt-6-sol --base-url https://api.haogpt.net/v1 --budget 40 --timeout 1200
```

每个 condition 只有一例。即使自然Shared出现失败，也只说明一条有效轨迹；不能推断干扰率、可恢复真人失败率或 PerActionLock 普遍有效。若 fixed User 已失败但最终用户 Oracle失败，则记录作任务结果；恢复时间对当前open-loop策略不可估计，不能记作“无恢复成本”。

### 自然 Shared Pilot 判读

Run 78 中两个 Actor 同时启动。用户先按正常脚本打开 OPS-117、撰写并发送内部回复、标记 Done；Agent 的首次截图约在两个 Actor 启动后 26.7 秒，画面已处于用户正在操作的 Afternoon queue coverage / Reply 页面。Agent 随后通过返回 Inbox、选择 CUST-2048 与政策页完成自己的任务。这是可审计的**共享当前页面上下文变化**，且用户完成时序与 Agent 截图时段相邻；但 Agent 没有把输入落到错误线程，动作日志记录的 wrong_foreground_actions=[]、15次调用 misrouted_focus_before=false，两侧 Oracle 均通过，用户也无额外动作或恢复。

焦点监视器记录9次窗口标题变化，但其中主要是 Agent 自己在 Inbox、客户线程、政策页、Reply 与 Drafts 之间的预期导航，**不能把9次都算作用户造成的干扰**。Shared 本次比 Agent-only 和 Independent 的14次 GUI MCP calls 各多1次；Agent 用时806.2秒，也高于 Agent-only 的328.5秒与 Independent 的704.2秒。跨单次请求的模型/API延迟波动较大，这些只能作观察，不能作因果归因。结论是：观察到一次自然的任务上下文交接，双方仍成功；这既不是干扰失败，也不是无干扰证明。

HA-MAIL 达到继续扩展到下一类工作流的 pilot 门槛：**可运行、各方独立可解、Independent 与 Shared 都可评分，且日志保留了实际自然交错**。目前不需要为了得到 FAIL 加强交错或重调本任务；后续可按候选池推进 HA-CALENDAR / HA-INVENTORY，并继续保持自然 Shared 与机制 probe 分开。每条件一次，不能推断概率/总体体验。

## 2026-11-11：固定启动偏移的受控干扰验证

本节是受控机制探针，不替代 Run 78 的自然 Shared 条件。为验证用户正控仍成立且捕捉明确同桌面竞争，在 Actor A 正常执行客户线程审核/草稿任务期间，将正常的 OPS-117 用户脚本延迟 25 秒启动；没有要求 Agent 扰乱用户，也没有注入 GUI 故障。fixed_mechanism_probe=true、natural_parallelism=false。该轨迹不可作为自然并发率或自然失败率估计。

| Run（RAID 目录） | 条件 / 判定 | 证据与成本 |
|---|---|---|
| 81-mail-user-only-offset25-loopback-fix | 相同 25s User schedule 正控，**User PASS** | 5 个基准动作、0 extra、29.49s；总计 208.04s。证明这条固定用户轨迹在同样起始延迟下独立可解。 |
| 82-mail-independent-offset25-loopback-fix | **Infrastructure-invalid**，不计任务失败 | 新提供的端点凭据被 API 返回 401 Invalid token；Agent 为 0 次 GUI 操作。User 虽通过，联合条件仍无效。原始 run/日志完整保留。 |
| 83-mail-independent-offset25-oldkey | 25s probe schedule 下 **User PASS + Agent PASS，joint PASS**；有效 | 两 Guest 初始 Inbox/邮件状态和内容 SHA-256 相同。User 5 动作/29.45s、0 extra、0 错焦点；Agent 14 GUI MCP/484.17s、221,799 input（166,656 cached）/401 output tokens、0 错焦点；总计 697.58s。 |
| 84-mail-shared-offset25 | 25s probe schedule 下 **User FAIL + Agent PASS，joint FAIL**；有效 | 同一 Guest/Inbox；Agent 17 GUI MCP/354.26s、287,699 input（243,968 cached）/477 output tokens。User 固定 5 步/30.64s，步骤 2–4 均检测到前台窗口与预期不符（3 次 misrouted_focus_before=true），最终没有在 OPS-117 发出回复、也未标记 done；User Oracle 的精确收件人/正文/状态全部失败。Agent 所有 14 项 Oracle 均通过，客户草稿保持未发送。总 run 531.44s。 |

Run 84 的事件链（events.jsonl 与 shots/）显示：Agent 在 run elapsed 198.57s 将窗口切至 CUST-2048；User 在 201.09s 启动，并于 207.58s 按固定轨迹点击 OPS-117；Agent 在 211.87s 又切到 POL-WAR-3，User 随后在 214.02s 打开 Reply、220.12s 输入内容时焦点仍处在政策页，226.04s 点击发送时再次处于错误上下文。User 按脚本执行时没有自动恢复（策略是 fixed open-loop），Agent 随后返回 Inbox 并正确完成自己的草稿任务。共享桌面造成的输入误路由由时间、窗口标题、3 个错前台标记和服务端 Oracle 共同佐证，而不是只根据最终失败推断。

本次是**明确交错的机制验证**：User 延迟 25 秒是实验者设定；不是自然时间行为，也没有把它与 #78 合并。自然 Shared #78 仍是 User PASS + Agent PASS。即使本探针与相同 schedule 的 User-only / Independent 正控形成有效对照，也只能说明该可复现交错可损害固定回放用户；不代表真人策略或未调度并发必然失败，不估计概率。用户没有恢复策略，因此恢复时间“不可估计/未实现”，不是 0 秒。

复现示例（每次用全新 RAID run 目录；三臂的模型/GUI 权限/预算相同）：

~~~bash
infra/run_human_agent_mail.sh --mode user-only --user-start-delay-s 25 --out /mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/<unique-user-only>
infra/run_human_agent_mail.sh --mode independent --model gpt-6-sol --base-url https://api.haogpt.net/v1 --budget 40 --timeout 1200 --user-start-delay-s 25 --out /mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/<unique-independent>
infra/run_human_agent_mail.sh --mode shared --model gpt-6-sol --base-url https://api.haogpt.net/v1 --budget 40 --timeout 1200 --user-start-delay-s 25 --out /mnt/raid1/mjh/Projects/codesk-human-agent-normal-actor-pilot-20261109/<unique-shared>
~~~

模型凭据须通过受控环境安全注入，不写入仓库、参数、日志或 run 目录。此前无效的 82 和所有历史输出均保留。
