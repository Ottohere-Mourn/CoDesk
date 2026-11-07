# CoDesk case handoff — 13 个原始案例 + 2 个后续达标案例

更新日：2026-11-07

## 一页结论

本 handoff 的编号清单是原 13-case portfolio（Case 2/3/4 + 五机制 + 五候选），再纳入后续完成并达标的 PAY-1 与 DATA-REL1，共 15 个。按严格门槛，当前 **10/15 达标**。

达标门槛：同一冻结任务版本、fixture、prompt、model、工具权限和预算下，有效 MA-ID（独立 Guest）PASS、有效 Shared FAIL、有效 Shared+Lock FAIL；两次共享失败均由实际共享状态造成并由业务 oracle 判定。Guest/API/协议/evaluator/reset 无效不能算 FAIL。按用户决定，每案一组三臂即可，不要求第二次有效重复。

### 当前达标的 10 个

1. **Case 3** — VS Code 修复 + 浏览器重测中的跨窗口输入误路由。
2. **C-03 Clipboard** — B 的剪贴板 payload 覆盖 A 的待粘贴内容。
3. **A-01 Application Context** — 同窗多 Tab 下陈旧 Enter 落到非目标 Tab。
4. **S-01 Selection / Active Object** — 活动单元格变化后陈旧输入落到错误对象。
5. **U-01 Undo/Redo** — 共享 Undo 栈使 A 撤销到 B 的操作。
6. **CWD-1** — 共用终端 PWD 改变后，A 的相对路径交付落入 B 的工作树。
7. **VIEW-1** — 视口滚动后陈旧屏幕坐标命中错误记录。
8. **AUTH-1** — 活动审核人改变后，A 的待执行提交被记到错误主体。
9. **PAY-1** — 工时更正晚于付款完成，造成付款快照陈旧。
10. **DATA-REL1** — 数据修订令已生成、尚未发布的 staging export 包过期。

都只有一次有效 screening triplet；“10 个达标”不是重复性、模型总体 fail rate 或发生概率估计。它们也不等于 10 个互相独立的底层机制；DATA-REL1 是 PAY-1 stale-state 模式的数据导出工作流变体。

## 当前 15-case 矩阵

| # | Case / 工作流 | 最新结果与判定 | 证据入口 |
|---:|---|---|---|
| 1 | Case 2：商品工单、Review ID 交接、退款结案 | v1.2.0 三臂业务 PASS；未达标，保留作成功/中性对照 | case234/case2；源分支 codex/case2-v12 |
| 2 | Case 3：VS Code 修复后到浏览器重测 | v1.4.3 PASS / FAIL / FAIL；达标一次 | case234/case3；源 codex/case3-followup |
| 3 | Case 4：Kdenlive 时间线 + VS Code 清单 | SSD cohort 有效锁臂 PASS；未达标 | case234/case4；源 codex/case4-hardening |
| 4 | F-01 Focus/Input Routing：Writer 陈旧输入、B 切 Calc 焦点 | Hybrid v2 最新 PASS / PASS / FAIL；缺普通 Shared FAIL | mechanisms；源 codex/focus-clipboard-pilot-20261102 |
| 5 | C-03 Clipboard：B 覆盖剪贴板后 A 粘贴错误内容 | PASS / FAIL / FAIL；达标一次 | evidence-manifests/C03-gpt6-sol-hybrid-triplet.json |
| 6 | A-01 Application Context：同一 Chromium 窗口多 Tab | PASS / FAIL / FAIL；达标一次 | evidence-manifests/A01-gpt6-sol-hybrid-triplet.json |
| 7 | S-01 Selection：Calc 活动单元格状态共享 | v0.2.2 PASS / FAIL / FAIL；达标一次 | evidence-manifests/S01-gpt6-sol-hybrid-triplet.json |
| 8 | U-01 Undo/Redo：共享 Calc undo stack | v0.2.2 PASS / FAIL / FAIL；达标一次 | evidence-manifests/U01-gpt6-sol-hybrid-triplet.json |
| 9 | CWD-1：共享 shell 当前目录泄漏 | v0.2.4 PASS / FAIL / FAIL；相对路径写入错误工作树；达标一次 | CWD-v024 evidence manifests；scripts/run_sol_cwd_bundle_v2.py |
| 10 | EDIT-1：Writer Insert/Overwrite 模式 | v0.6.2 有瞬时覆盖，但 Agent 后续撤销导致终态归因不干净；不计达标 | next-five/NEXT_CASE_PROGRESS_20261107.md |
| 11 | VIEW-1：审核列表滚动改变 viewport offset | v0.1.1 PASS / FAIL / FAIL；达标一次 | MA-ID view-signoff-sol-v011-ma_id-20261107-1；有效 Shared 为 view-signoff-sol-v011-ma_sd-20261107-retry1；锁臂 view-signoff-sol-v011-ma_sd_lock-20261107-1 |
| 12 | FIND-1：Writer Find/Replace Match-case 设置 | v0.3.2 缺同版本有效 MA-ID，且 Shared 聚合器与内层 evaluator 不一致；本次严格复审不计达标 | next-five/NEXT_CASE_PROGRESS_20261107.md；旧 adjudication 保留 |
| 13 | AUTH-1：活动审核人/提交主体切换 | v0.1.1 PASS / FAIL / FAIL；提交被记到 Operator-B；达标一次 | auth-session-sol-v011-ma_id-20261107-1、auth-session-sol-v011-ma_sd-20261107-1、auth-session-sol-v011-ma_sd_lock-20261107-1 |
| 14 | PAY-1：付款完成后发生合法工时更正 | PASS / FAIL / FAIL；旧付款快照与新工时不符；达标一次 | PAY1_HYBRID_EXPERIMENT_STATUS_20261106.md |
| 15 | DATA-REL1：数据集政策修订后发布前重新评估 | PASS / FAIL / FAIL；staging 包过期；达标一次 | DATA_REL1_EXPERIMENT_SUMMARY_20261106.md、DATA_REL1_CASE_CARD_20261106.md |

## 两个新增 case 的 run IDs 和边界

- **PAY-1**：pay1-sol-ma_id-20261106-180233-b0578d；pay1-sol-completion-order-ma_sd-20261106-184148-ca9cde；pay1-sol-completion-order-ma_sd_lock-20261106-184751-88fc4b。Shared+Lock 是完成顺序 schedule，锁没有并发竞争者；支持“逐动作锁不保证跨任务事务新鲜度”，不支持“测到了 GUI 同时锁竞争”。
- **DATA-REL1**：data-rel1-sol-ma-id-20261106-200855-214b9e；data-rel1-sol-ma_sd-20261106-202524-d0ad31；data-rel1-sol-ma_sd_lock-20261106-203612-361464。也是 completion-order；不外推到数据库级隔离或真实数据发布平台。

Shared+Lock 始终指该实验实际配置的逐动作锁，不自动等于多动作事务锁或数据库隔离。VIEW-1 的锁臂同样是按序执行；解释是锁不会重新绑定旧坐标意图，不声称测过 GUI 锁竞争。AUTH-1 发现的是 mock 系统内错误主体归属，不是权限绕过或真实审批事件。

原始截图和完整轨迹仍只在 HealthCare RAID1：/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/。本分支提供新 case 的 runner、fixture、测试、结果摘要和 run IDs；不把大型 raw artifacts 复制进 Git。

## 计数变化与 roster 外探索

2026-11-05 handoff 曾列 9/13，含 FIND-1。本次重审发现 FIND-1 的 v0.3.2 shared arms 缺少匹配版本的有效 MA-ID，不能与 v0.3.1 baseline 拼接，因此原 13 项按本门槛为 8/13。随后 PAY-1、DATA-REL1 各有一个有效 triplet 达标，故为 10/15。

另有 roster 外探索，不增达标数：W4 incident-response 有效三臂都 PASS（MA-ID 10f09960、Shared d8267a3a、锁臂 4344174a；Shared 中间 clipboard 错误后恢复）；CALCMODE1 有效三臂都 PASS（MA-ID 114732-52c8a4、Shared 121736-da4919、锁臂 122405-ed993e）；warehouse-receiving v0.2.7 的最近 MA-ID 67cbbad0 protocol_valid=false，不能与后续 Shared 8ab534ba / Shared+Lock aa92d441 拼成有效 triplet。W3、AP1、PBR-1 尚属设计/控制阶段，不能算通过。审计细节见 QUALIFIED_CASE_AUDIT_20261107.md。

## Case 2/3/4 概览

- Case 2 v1.2 的三臂任务均 PASS，是业务成功/协作时序对照，不是 shared-fail case。
- Case 3 v1.4.3 是 Case 2/3/4 中唯一满足目标者；保留 setup-invalid 和 scorer-crash 等历史尝试边界。
- Case 4 SSD 对照中有效锁臂 PASS；不把较旧 HDD cohort 合池。

## 怎么拉取和使用

此 handoff 沿用历史分支名 codex/13-case-handoff-20261104，但 case roster 已更新为 15 项。先读本文件、QUALIFIED_CASE_AUDIT_20261107.md 和相关结果摘要，再选择源 worktree：

    git fetch origin
    git worktree add ../CoDesk-case2 origin/codex/case2-v12
    git worktree add ../CoDesk-case3 origin/codex/case3-followup
    git worktree add ../CoDesk-case4 origin/codex/case4-hardening
    git worktree add ../CoDesk-mechanisms origin/codex/focus-clipboard-pilot-20261102

- PAY-1 / DATA-REL1 的 fixture、app、runner、unit tests 已附在此分支。
- VIEW-1/AUTH-1 v0.1.1 runner、安全 wrapper、共享本地 mock app 和 control probes 已附在此分支。
- 所有新 case 使用 GPT-6-Sol / Codex CLI 0.155.0；新三臂工具权与预算匹配。早期 Case 2/3/4 配置不同，不宣称 harness 完全同构。
- 任何重复均使用新 run ID，并保留全部 invalid/valid 尝试。不得针对 Shared arm 添加专属障碍、改变预算、禁用正常恢复，或把 infrastructure/evaluator/reset invalid 算作失败。
- 分支不存私有 API key；认证只能使用安全隐藏输入，不得写入 source、shell history 或报告。

## Raw evidence 位置

- Case 2：/home/mjh/Projects/CoDesk-case2-healthcare/runs/ticket_to_resolution/healthcare/
- Case 3：/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/<run-id>/
- Case 4：/home/mjh/Projects/CoDesk-case4-hardening/runs/<run-id>/
- 五机制与 Hybrid v2：/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/
- 新候选：/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/
