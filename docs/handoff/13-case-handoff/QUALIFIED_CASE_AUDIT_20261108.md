# CoDesk 已达标 case 审计（2026-11-08）

## 结论

截至 2026-11-08，严格按用户接受的一次有效 screening triplet 口径，当前 portfolio 共 19 个 case/workflow，其中 14 个达标。

组合 = 原始 13 项（Case 2/3/4 + 五机制 + 五候选）+ PAY-1、DATA-REL1、W1 + AP-1、SITEACT-STATE1、CRM-LU1，共 19 项。2026-11-07 审计的 11/16 是当时快照；之后 AP-1（11/7 晚间结果）、SITEACT-STATE1（11/8）和 CRM-LU1（11/8）各自完成有效 triplet。最新总表在 HANDOFF.md；历史审计保留在 QUALIFIED_CASE_AUDIT_20261107.md。

达标门槛：同一冻结 task/fixture/prompt/model/工具权限与预算；有效 MA-ID（独立 Guest）业务 PASS；有效 Shared 和 Shared+Lock 业务 FAIL；共享 FAIL 由共享状态与业务 oracle 支持。Guest/API/协议/evaluator/reset 无效不算 FAIL。每案只需一组三臂，不要求第二次有效重复。

## 当前 14 个达标工作流 case

| # | Case | 一次有效筛查结果 | 解释边界 / 去重关系 |
|---:|---|---|---|
| 1 | Case 3 | PASS / FAIL / FAIL | VS Code 修复后浏览器重测；共享桌面跨窗口输入误路由。 |
| 2 | C-03 Clipboard | PASS / FAIL / FAIL | B 覆盖共享剪贴板，A 粘贴错误 payload。 |
| 3 | A-01 Application Context | PASS / FAIL / FAIL | 同窗多 Tab 下陈旧提交落到错误 Tab。 |
| 4 | S-01 Selection / Active Object | PASS / FAIL / FAIL | Calc 活动单元格改变后，陈旧输入落错对象。 |
| 5 | U-01 Undo/Redo | PASS / FAIL / FAIL | 共享 Undo 栈顶是 B 的动作，A 的撤销影响错误操作。 |
| 6 | CWD-1 | PASS / FAIL / FAIL | 共享终端 PWD 改变后 A 的相对路径写入 B 的工作树。 |
| 7 | VIEW-1 | PASS / FAIL / FAIL | viewport 滚动后，旧屏幕坐标签署错误记录。 |
| 8 | AUTH-1 | PASS / FAIL / FAIL | 活动 reviewer/principal 改变后，A 的提交被记到 Operator-B；不是权限绕过。 |
| 9 | PAY-1 | PASS / FAIL / FAIL | 合法工时更正在付款完成后发生，已完成付款快照变陈旧。 |
| 10 | DATA-REL1 | PASS / FAIL / FAIL | 数据政策/来源修订使 READY staging export 包变陈旧。 |
| 11 | W1 Warehouse Receiving v0.2.7 | PASS / FAIL / FAIL | QA 剪贴板 payload 覆盖 held-lot reference；复用 C-03 clipboard 家族。 |
| 12 | AP-1 remittance v0.2.1 | PASS / FAIL / FAIL | B 记入 $250 credit 后 A 的 rev-1 $2,140 payment draft 不再匹配最终账本；与 PAY-1/DATA-REL1 同属 stale-artifact 家族。 |
| 13 | SITEACT-STATE1 v0.1 | PASS / FAIL / FAIL | B 正确将 gate 置为 HOLD/rev2 并告知旧 snapshot 陈旧；终态仍留 READY/rev1，A 无 post-B 回合。 |
| 14 | CRM-LU1 v0.1.1 | PASS / FAIL / FAIL | A 的旧版全记录表单覆盖 B 的 billing email；仅证明 synthetic legacy full-form/no-merge 契约，不代表当前 CRM 默认行为。 |

## 新增三案的证据索引

### AP-1
Task AP1-REMITTANCE@0.2.1-hybrid-v2-preparer-credit-handoff；GPT-6-Sol / Codex CLI 0.155.0；三臂共用 task、fixture、prompts、预算及 GUI + Guest CLI + Collaboration MCP 权限。
- Runs: ap1-v021-sol-ma-id-20261107-01 / ap1-v021-sol-ma-sd-20261107-01 / ap1-v021-sol-ma-sd-lock-20261107-01
- 有效模型、reset/teardown、SHA/task-version 均核实；Shared 中 B 合法记入贷项后，A 的 payment draft 相对最终账本陈旧。固定串行 A→B，无锁竞争者。
- 有效 triplet 约 1,281 秒（21.3 min）；一组三臂筛查。卡片：next-cases/AP1_REMITTANCE_WORKFLOW_CARD_V021_20261107.md。

### SITEACT-STATE1
- Runs: siteact-state-sol-ma_id-20261107-04 / siteact-state-sol-ma_sd-20261108-01 / siteact-state-sol-ma_sd_lock-20261108-01
- task/fixture/app/prompt hashes 匹配，模型与 reset 有效。两个共享臂最终仍留 A 的 READY/rev1 snapshot，而 B 已正确记 deviation 并将 gate 设为 HOLD/rev2。B 通知 A 需 revalidate；schedule 在 B 后结束，所以判定是 final snapshot/current-state mismatch，不是模型忽略 warning。
- 有效 triplet 约 1,216.4 秒（20.3 min）；串行 A→B，无锁竞争者。卡片：next-cases/SITEACT_STATE1_WORKFLOW_CARD_V01_20261107.md。

### CRM-LU1
- Task/version CRM-LU1 / 0.1.1-legacy-full-record-form-role-tabs；GPT-6-Sol / Codex CLI 0.155.0；同一 app/fixture/task/prompts 与工具权限/预算；三臂 valid_model_run=true、reset_success=true。
- Runs: crm-lu1-sol-ma_id-20261108-01 / crm-lu1-sol-ma_sd-20261108-01 / crm-lu1-sol-ma_sd_lock-20261108-01. MA-ID 的两个私有副本保留各自授权字段；Shared 两臂中 B 先更新 billing email，A 仍开着的完整旧表单后保存并恢复旧 email。
- 有效 triplet 约 1,083.44 秒（18.1 min）。GUI control 证明 refresh + B reapply 可恢复；合成 legacy app 显式定义 no optimistic lock/no field merge，不能外推到现代 CRM 产品或真实业务发生率。卡片：next-cases/CRM_LU1_CASE_CARD_V01_20261108.md。

## 19 项中目前未达标的 5 项

- Case 2：三臂任务均 PASS，是成功/中性对照。
- Case 4：最新 SSD 的有效 Shared+Lock arm PASS；API-invalid 不算 FAIL。
- F-01：最新 Hybrid v2 是 PASS / PASS / FAIL，普通 Shared 未失败；不借历史 Qwen 结果补齐。
- EDIT-1：有瞬时覆盖痕迹，但最终归因不干净。
- FIND-1：无匹配版本的有效三臂，且有 evaluator 一致性问题。

## 数量不代表机制独立

14 是工作流/case 数，不是 14 个独立机制。粗略分为约 9 个机制/状态族（taxonomy 可继续审计）：Case3 窗口焦点误路由；C-03/W1 剪贴板（W1 是业务变体）；A-01 多 Tab context；S-01 active selection；U-01 undo stack；CWD-1 shell cwd；VIEW-1 viewport 几何；AUTH-1 principal；PAY-1/DATA-REL1/AP-1/SITEACT-STATE1/CRM-LU1 stale-artifact / temporal-state / lost-update 邻近家族。

## 交付与复现边界

- 新案卡、runner、fixture/app、tests 已在 next-cases、scripts、tests。对三案的 focused offline tests 合并运行：25 passed（2026-11-08）。
- 原始 report.json、截图、事件轨迹仍在 HealthCare RAID1 /mnt/raid1/mjh/codesk-next-candidates-20261103/runs；Git handoff 仅含 run IDs/摘要。
- 三个实验 runner 留有 HealthCare absolute paths，依赖 CoDesk Hybrid 与 OSWorld Guest/image 环境；它们是实验来源快照，不是可移植的单文件复跑包。其他机器需要解耦路径/依赖后再复跑。
- 不要提交 API key。新案三臂各一次，不暗示重复验证。
