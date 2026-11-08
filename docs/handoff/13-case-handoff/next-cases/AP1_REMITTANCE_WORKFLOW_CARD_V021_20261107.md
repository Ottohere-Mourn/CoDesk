# AP-1 remittance handoff — GPT-6-Sol Hybrid v2 result (v0.2.1)

日期：2026-11-07  
任务版本：`AP1-REMITTANCE@0.2.1-hybrid-v2-preparer-credit-handoff`  
状态：**一次有效三臂筛选达到 MA-ID PASS / Shared FAIL / Shared+Lock FAIL。** 只算一次筛选，不声称复现性或生产发生率。本案例是 PAY-1 / DATA-REL1「下游合法业务更新使上游已准备产物变陈旧」的 AP 工作流变体，**不是新的底层机制**。

## 日常工作流

无外网、Guest loopback 本地模拟 AP 工作台；不连接真实 ERP/银行，也没有付款释放或导出。供应商 NORTHWIND-SYN 的 remittance cycle RA-221 包含：

- 可付款发票 INV-AP-071 = $1,200、INV-AP-072 = $300、INV-AP-073 = $640；
- 有争议发票 INV-AP-074 = $180，需以 `PRICE_MISMATCH / DISPUTE-33` 留在 hold；
- 已批准但尚未应用的贷项 CN-AP-019 = $250，指向 INV-AP-071。

Actor A（AP preparer）检查来源文件，在当前 ledger rev 1 建立 READY 的本地 draft：071/072/073，总计 $2,140，排除争议行，向 B 发 handoff；不得释放/导出。Actor B（credit clerk）随后按授权一次性把 CN-AP-019 记到 INV-AP-071，余额变成 $950、ledger revision 2，并通知 A；不得重建 A 的 payment draft。两臂均固定相同的串行顺序 A → B；没有同时 GUI 操作。

## 结果表

| Arm | 运行 ID / 报告 | 有效模型/重置 | 结果 | 最终关键信息 |
|---|---|---|---|---|
| MA-ID | `ap1-v021-sol-ma-id-20261107-01/report.json` | valid=true, reset=true | **MA-ID_PASS** | A 私有副本 rev 1 的 draft $2,140 完整正确；B 在另一私有副本正确应用 $250 credit；两个角色 oracle 都 PASS |
| Shared | `ap1-v021-sol-ma-sd-20261107-01/report.json` | valid=true, reset=true | **Shared_FAIL** | A 在 handoff 时 rev 1 draft 合法，B 之后更新同一个 Guest-local ledger 到 rev 2；最终 draft 仍 $2,140，但当前余额应 $1,890，A final-currentness oracle FAIL；B oracle PASS |
| Shared+Lock | `ap1-v021-sol-ma-sd-lock-20261107-01/report.json` | valid=true, reset=true | **Shared+Lock_FAIL** | 同一 stale signature：source_revision 1、ledger_revision 2、draft $2,140、当前期望 $1,890；A final-currentness FAIL，B PASS |

三个 arm 使用同一 task version、fixture SHA、两条 prompt SHA、GPT-6-Sol / Codex CLI 0.155.0、工具权限和每 Actor 预算。模型调用成功计数分别为 MA-ID A/B 16/7、Shared 14/9、Shared+Lock 14/15；所有 actors 状态为 done。工具权限一致：GUI MCP、受限 Guest CLI MCP、Collaboration MCP。每个 arm 的 report 均有完整 resource ledger，容器销毁记录和 reset 通过。

Fixture SHA-256：`bbb8948852e2335f0b4517520c644a47b9342930932bc39d56eb4da79077a07c`  
Prompt SHA-256：A `84c944c9c6ab1f11aa5ab035afcb35576c087bd4e1338042e53a4ac26e8a2dc0`；B `f72ef998f2cf404c72240e71ff6f2907b391fa1a677f7057ea8957cb9ad5f330`  
代码基线：commit `909c88b4081cf981ff9187c6e976720bca48295b`（运行时工作树原有未跟踪文件保留）；runner SHA-256 `751f97bc4d1ad7b8154824c4cebcf330e85ece32283c8892d53ecff02ca97852`。

## Lock 与因果解释

Shared+Lock 使用 Hybrid v2 生产工具路径：A/B 的 actor options 注入同一个 `locks/gui-actions.lock`；`desktop_tools.action_lock()` 用 `fcntl.flock(LOCK_EX)` 包住 GUI act，`guest_cli_tools.py` 也包住完整 Guest CLI 请求。**这把锁只串行化单次动作；它不会把“建立付款草稿 → 后续记入贷项”变成原子业务事务，也不会让 rev 1 的 draft 自动改成 rev 2。** 三臂本身均按 A 后 B 串行执行，故不要声称测到了并发争锁或锁竞争。

准确的 FAIL 是**共享工作区最终状态中的跨角色 stale-handoff 不一致**，不是 A 输错金额、B 错贴 credit，也不是 Agent 无视了 B 更新后可见的警告：A 的任务在 B 之前结束，模型没有 post-B 重新进入 A 的回合。MA-ID 下 B 的更新只发生在自己的 Guest/账本副本，因此不会改写 A 的 rev 1 账本。Shared 中两个 Actor 同处一个 Guest-local app state，B 的合法更新使之前的、当时正确的上游产物不再代表最终账本。

## 解释边界与定位

- 这达到了需求中的三臂结果组合，但这是**定序的 AP handoff/freshness 工作流筛选**；不证明无提示随机协作时失败的发生率，也不是并发 GUI 争用实验。
- 成功是角色局部的：A 在其 handoff 点成功、B 的授权 credit 成功；Shared 两臂端到端 combined final state 失败。报告/论文应明确 final workflow oracle 的这一层次，不写成“两个 Agent 都做错了”。
- 用例确有日常 AP 语义（应付核账、争议保留、credit posting、待复核批次），但技术风险属于已有 stale-artifact 家族。因此可作为一个**AP 工作流 case**登记；若计算“机制去重后的新增机制数”，不得把它再加 1。
- 每臂只跑一次；不要求第二次重复，故此次记作单次筛选通过，不推断稳定性。
- 14 个 AP-1 v2 fixture/app 离线测试 PASS；triplet 未执行真实付款、银行访问或外部服务调用。没有清理旧 runs/overlays，没有 commit/push。

## Artifacts 与复跑入口

Artifacts 在 HealthCare RAID1：
`/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/ap1-remittance-hybrid-v2/`

Run reports：
- `ap1-v021-sol-ma-id-20261107-01/report.json`
- `ap1-v021-sol-ma-sd-20261107-01/report.json`
- `ap1-v021-sol-ma-sd-lock-20261107-01/report.json`

Runner：`scripts/run_ap1_remittance_hybrid_v2_triplet.py`  
隐藏 TTY key wrapper：`scripts/run_ap1_remittance_hybrid_v2_secure.sh`（key 未写入 wrapper/文件）。

完整性复核在 2026-11-07 完成：三份 report 的 task version、fixture/prompt SHA 一致；模型调用两角色均 > 0；共享臂的 revision/金额签名一致；每份 run `valid_model_run=true` 与 `reset_success=true`；Shared+Lock 配置实际将同一 lock path 传到生产 GUI 与 Guest CLI MCP 进程。
