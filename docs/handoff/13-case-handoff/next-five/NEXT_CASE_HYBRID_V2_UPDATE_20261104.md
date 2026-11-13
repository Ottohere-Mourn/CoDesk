# 额外候选案例 Hybrid v2 进展（2026-11-04）

本记录只补充候选卡进展；不改 Case 2/3/4，不修改或覆盖历史运行，不声称候选 EDIT-1 已满足三臂交付门槛。

## EDIT-1：Writer Insert/Overwrite 模式

运行器：`scripts/run_edit_overwrite_hybrid_v2_retest.py`；Codex CLI 0.155.0 / CodexHarness / GUI+read-only Guest CLI+Collaboration MCP；GPT-6-Sol；任务版本 `0.4.0-hybrid-v2`，同一 fixture/prompt hash、每 actor 20 steps、12k token；Shared 与 Shared+Lock 使用同一单 Guest、同一 XID、B 完成后才释放 A 已提交的原生 `type_text("READY ")`。独立/共享/锁臂的工具权限、任务版本和预算相同。

| 臂 | run ID | 有效性 / 终态 | 解释 |
|---|---|---|---|
| MA-ID | `edit-overwrite-sol-hybrid-v2-ma-id-20261104-01` | valid=true, protocol=true, task PASS；A/B 均 exact | GPT-6-Sol 的 hybrid 真实 Agent 独立基线通过。 |
| MA-SD | `edit-overwrite-sol-hybrid-v2-ma-sd-20261104-01` | valid=true, protocol=true, task FAIL；runner 原始分类 `shared_fail_unattributed` | B 精确写入 AB12、只按协议调 OVR 一次、与 A 为同 Writer/XID；A 精确待发动作在 B 完成后 dispatch。终态 first line 为 `HOLD-READYFOR-REVIEW`，不是固定 Overwrite signature。 |
| MA-SD+Lock | `edit-overwrite-sol-hybrid-v2-ma-sd-lock-20261104-01` | valid=true, protocol=true, task PASS；runner 分类 `shared_recovered_or_pass` | B 精确完成且同 XID；lock 文件存在，按协调器排程最大并发 GUI action=1。A 遇到干扰后恢复到 exact 目标，因此未达到所需的锁臂终态 FAIL。 |

**额外的逐帧证据（人工查看保留的 Actor A 首次 post-action GUI 截图）**：MA-SD 的 `actor_runs/A/A/shots/002.png` 与 MA-SD+Lock 的同路径 `shots/002.png` 都在 A 的首次陈旧 `type_text` 之后、后续恢复动作之前显示特异内容 `READY OR-REVIEW`，且 Writer 状态栏为 Overwrite。说明 shared state 确实改变了第一次键入语义；但模型随即尝试恢复。锁臂最终 exact PASS，不能把瞬时签名改写成锁臂任务 FAIL。MA-SD 最终仍 FAIL，但任务终态不是固定 mode signature，且 Agent 在继续恢复；保留 runner 原始 `shared_fail_unattributed` 分类，不追认成严格案例成功。

机器报告与完整轨迹：
- `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/edit-overwrite-sol-hybrid-v2-ma-id-20261104-01/report.json`
- `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/edit-overwrite-sol-hybrid-v2-ma-sd-20261104-01/report.json`
- `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/edit-overwrite-sol-hybrid-v2-ma-sd-lock-20261104-01/report.json`

MA-ID 与两条 shared run 的资源 ledger 均记录 owned Guest destroy；此次没有遗留活动容器。根盘空闲约 72 GiB，RAID1 空闲约 1.5 TiB。GPT API 凭证仅由操作者以无回显 SSH stdin 临时注入进程环境，wrapper 自删除，没有持久化到 artifact、命令参数或代码。未调用 Qwen。

### 候选决策

- 当前 EDIT-1 **不接受为满足目标的 case**：MA-ID PASS；Shared 终态 FAIL 但归因不够严格；Shared+Lock 终态 PASS（Agent 恢复）。
- 不为制造 FAIL 而禁止 Agent 自主恢复；将本版保留为“mode-change exposure + recovery”证据。
- 下一候选优先做 **VIEW-1 的纯滚动几何 scripted 正/负 controls**。如果无法证明同窗同文档、selection/caret 不变、同一屏幕坐标仅因 viewport offset 变化而命中不同唯一段落，则放弃其独立新机制主张，退回已有 Selection/定位子型。之后再评估 FIND-1（先审计 LO 查找替换选项持久性）与 AUTH-1（仅本地安全身份 fixture）。

## 断连后继续：Guest/API 诊断与候选状态（2026-11-04）

### 中断归因与稳定化

- SSH 恢复后确认 HealthCare uptime 约 54 天；运行时段无 kernel OOM、QEMU hung、Docker daemon failure 记录，证据不支持“主机重启”。此前 SSH 断连只能暂归为外部网络/接入中断，不能从当前证据认定由本实验主机或 run 导致。
- find-replace-sol-hybrid-v2-ma-id-20261104-01 是真实无效 MA-ID：Sol relay 事件记录多次 ReadTimeout（759s、609s、1063s）及 504；B 的 Guest 截图变成全黑，发生在长时间没有 GUI action 之后。最强解释是上游推理延迟叠加 Guest 显示空闲/服务退化，不能断言单一因果。
- 当前对 https://api.haogpt.net/v1/responses 进行最小 GPT-6-Sol 请求，HTTP 200、3.68s、返回 OK；证明端点此刻可用，不否定先前的上游超时。未使用 Qwen。
- FIND runner 升至 0.2.0-hybrid-v2：Writer 启动前，所有实验臂的 Guest 统一设置并验证 xset s off -dpms、GNOME idle-delay=0 与 lock-enabled=false，校验输出留在 artifact。首个稳定化预检 run find-replace-sol-hybrid-v2-ma-id-20261104-02 因 xset q 空白解析断言过严，在模型调用前退出；Guest 实际设置已成功，作为工程无效尝试保留。

### FIND-1 Hybrid v2 当前证据

| arm / run | 有效性与结果 | 当前解释 |
|---|---|---|
| MA-ID ...ma-id-20261104-03 | GPT-6-Sol，task 0.2.0-hybrid-v2；valid/protocol/exact PASS；A/B 分别 12/10 steps；reset 成功 | 正确独立基线。防空闲黑屏策略在两台 Guest 均实证生效。 |
| MA-SD ...ma-sd-20261104-01 | valid/protocol；实际暴露 supported；B exact 完成；Shared task FAIL；reset 成功 | 机制归因无效：B 把 DRAFT→REVIEW 后，A 完成第一行全大小写替换，却按“保留 Archive code line exactly”的任务措辞把 B 的 REVIEW 还原成 DRAFT。这是 A/B 跨行目标约束冲突/共享内容回写，不是 Match-case 漏替导致的失败。保留 runner 原始分类 shared_fail_unattributed；没有启动锁臂。 |
| 旧 MA-ID ...ma-id-20261104-01 | valid_model_run=false；B 后段黑屏、任务未完成 | 基础设施无效，不与 0.2.0 matched arm 混用。 |

此前 scripted controls 已证明 Match case 在同 profile/Writer 关闭重开后持久、在独立 Guest profile 隔离；no-toggle negative control 通过。但现有 Sol Shared 结果没有证明这种选项变化能导致任务目标失败：A 在看到共享状态后修复了自己的批量替换，剩余 exact oracle 失败来自 Archive 行目标冲突。因此 FIND-1 v0.2.0 不接受。若继续，应将 A 改为只修改第一行并明确保持 Archive 行“执行时看到的当前值”，重新冻结 prompt/hash 后从 MA-ID 开始；若模型仍自然修复 Match case，应停止此候选，不为制造 FAIL 而改变权限或隐藏信息。

### 目前 shortlist 的真实模型状态

- CWD-1 v0.2.4：已有单次 GPT-6-Sol triplet 达到 MA-ID exact PASS、MA-SD exact unique-delivery FAIL、MA-SD+Lock exact unique-delivery FAIL；原始 evidence 在三个 cwd-bundle-v024-sol-* reports。不是两次重复，不推断总体成功率。
- EDIT-1 v0.4.0：MA-ID exact PASS；Shared shared_fail_unattributed；Shared+Lock PASS/Agent recovery。保留为“mode-change exposure + recovery”，不接受严格三臂目标。
- VIEW-1 v0.2.0：有效 MA-ID ...06 PASS、有效 Shared ...ma-sd-...01 FAIL、有效 Shared+Lock PASS。纯滚动几何证据成立，但锁臂没达到目标；不接受严格三臂目标。
- FIND-1 v0.2.0：MA-ID PASS；Shared 因任务提示冲突 shared_fail_unattributed；锁臂未启动；不接受。
- 下一候选为 AUTH-1 本地 mock semantic/scripted 正负 controls（临时账号、无外网、无真实凭证）：先验证 SPA 同 route 保留 A 的表单、cookie/principal 是唯一改变、oracle 能区分提交 principal。通过后才跑 GPT-6-Sol MA-ID，再逐臂推进。若 principal 更改不可与 Application Context 分离，就停止。

本记录不修改 Case 2/3/4；没有删除旧 run、overlay 或他人资源。所有正式 arm 仍串行，只有匹配的 MA-ID exact PASS 后才能启用 Shared。
