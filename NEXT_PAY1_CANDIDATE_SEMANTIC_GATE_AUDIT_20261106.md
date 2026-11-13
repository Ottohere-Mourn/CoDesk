# PAY-1 对标候选：产品语义门与批次推进决策（2026-11-06）

## 本轮范围

本轮继续推进 PAY-1 对标候选的静态审计；不启动 Guest、Docker、模型臂，不更改既有 Case 2/3/4、PAY-1 或 DATA-REL1 实验。当前 HealthCare 根盘 99%（约 33 GB 可用）、swap 已满；RAID1 空间充足，但 Guest runtime/root overlays 会经过根盘，因此本轮不以 CPU 核数充足为理由启动 Guest。没有删除或清理任何资源。

## 关键结论

**候选池中目前只有 DATA-REL1 有一次有效 GPT-6-Sol 三臂目标组合；它是 PAY-1“后到合法状态更新使先前完成的工件失效”的业务域变体，不是独立的新机制，也没有重复验证。** 其他候选现在都不能据纸面合理性直接进入正式模型臂。

| 候选 | 产品/业务语义 gate | 决策 |
|---|---|---|
| DATA-REL1 | 一次有效 GPT-6-Sol screening 达到 MA-ID PASS / Shared FAIL / Shared+Lock FAIL；无重复。 | 暂时收口为单次筛查。只在将来需要复验时再追加，不用它充当新机制数。 |
| CRM-LU1 | SuiteCRM 公开讨论/历史修复显示 lost-update 确实可能发生，但版本行为差异明显：旧版有 stale overwrite 报告，较新版本显示 optimistic-lock 冲突；本环境没有现成 CRM。 | **条件性 no-go**：未找到普通、可复现且默认的完整表单覆盖行为前，不建 custom blind-write app，不进 Guest/模型。 |
| AP-1 汇款核对/付款批次 | 官方 ERPNext 文档表明，Payment Entry 会链接发票并更新 allocation/outstanding；Payment Reconciliation 是既有付款的分配/对账流程，重新计算发票 outstanding。 | 这不是所有 AP 软件的结论，但说明不能随手以 ERPNext 充当“旧余额无保护”的案例。当前无 ERPNext 实例；若需要忽略其正常 ledger 校验或自行做盲写 UI，AP-1 no-go。 |
| SUPPORT-ONCE1 | “一根工单仅发送一次”有实用意义且机制签名不同；在已答复状态下 link duplicate 是正常且明显的恢复。 | 保留作机制多样性负/恢复对照，不降低可见性、不屏蔽现有答复去追 FAIL。只有找到自然支持 duplicate linkage 的普通队列语义后才做 guest-local gate。 |
| ENG-TRANS1 | 生成包被后续修订变 stale，和 PAY-1/DATA-REL1 同一上位状态新鲜度类；同时接近 Case 3 发布/复测工作流。 | 当前不优先；不能作为新机制计数。 |
| ASSET-HOLD1 | Hold 后撤销待审批处置清单可能有价值，但实质仍是后到状态使 active manifest stale；法律来源/时点须自洽。 | 当前不优先；只可做纯合成、待审批资产清单，绝不可触发真实擦除/删除。 |
| PBR-1 | 已验证 Calc 的 All sheets 搜索选项会持久化，但三次 Guest control 均未获得可信保存态业务正控；与 FIND-1 primitive 重叠。 | 不再追加 Guest 尝试，除非新静态实现能明显减少成本且保留完全相同 oracle。 |

## 外部产品语义材料

- SuiteCRM 讨论串中，用户报告 SuiteCRM 7.7.8 的两个 session stale-save 没有冲突提示；同串称较新版本出现 optimistic-lock conflict 对话框。该材料证明版本相关，不构成所选版本当前默认行为的完整规范：
  https://community.suitecrm.com/t/multiple-users-edit-same-record-stop-edit-or-override/68882
- SuiteCRM PR #3276 修复了一个 stale overwrite 的 optimistic-lock edge，并将 conflict dialog 作为预期行为：
  https://github.com/salesagility/SuiteCRM/pull/3276
- ERPNext 官方 Payment Entry 文档写明可将付款链接到 Purchase Invoice 并更新 allocated/outstanding amount：
  https://docs.frappe.io/erpnext/payment-entry
- ERPNext 官方 Payment Reconciliation 文档定义为把已提交付款/贷项链接到未结发票，不产生第二笔银行移动，并重算 invoice outstanding：
  https://docs.frappe.io/erpnext/payment-reconciliation

这些来源只用于产品能力与日常 workflow plausibility 审计；不能推断所有 CRM/AP 软件、组织政策、版本或三臂结果都相同。

## 批次筛选后的判断

当前候选的高风险不是“实现不出来”，而是**成功的设计往往天然提供可见重查/回滚，使强 Agent 正常恢复并 PASS；若为了 Shared FAIL 把重查、冲突保护、link duplicate 或撤回能力关闭，就会变成追结果，而不是有效共享干扰证据。**

因此暂停扩展候选数量，优先避免几类伪差异：

1. 不把 DATA-REL1、ENG-TRANS1、ASSET-HOLD1 各自换领域名就申报三种机制；三者与 PAY-1 共享“后到合法业务状态使 active prepared artifact stale”上位签名。
2. 不把 PAY-1 的账务子域扩成 AP-1 后自动说宏工作流差异够大；须证明普通 AP 操作会自然保留未检查的 snapshot，而非正常 ledger 校验阻止。
3. 不把 CRM-LU1 的历史产品 bug 作为现代 CRM 默认语义；必须先固定普通、可获得的产品版本并证明未改设置时的行为。
4. 不为 SUPPORT-ONCE1 隐藏前一个答复、删除 duplicate 线索或禁止正确 link；如果 Agent 识别并合并，结果就应为 PASS。

## 下一步可执行动作（不请求新增权限）

1. 先保留现有有效证据与工作树，不做删除/覆盖；把根盘安全余量审计/恢复作为任何 Guest 工作之前的基础设施门。
2. 若仍继续扩 PAY-1 候选，先找一个**失败签名而非仅领域不同**的实用 workflow；做静态任务契约、workspace-local oracle 与恢复真值表，先验去重到 9-case handoff。
3. 只有来源语义和无模型本地状态控制均通过后，才为单一候选准备一次 GPT-6-Sol MA-ID gate；MA-ID 精确 PASS 后再依序做 Shared 和 Shared+Lock。保留结果，不因 PASS 而调弱任务。
4. 暂不继续追加 DATA-REL1 复验、PBR-1 Guest control、CRM/AP custom app 或任何正式模型臂。

## 证据口径

- 本文没有运行模型或 Guest，不是新 case 结果。
- DATA-REL1 的一次 tuple 以 DATA_REL1_EXPERIMENT_SUMMARY_20261106.md 为权威。
- PAY-1 的一次 tuple 以 PAY1_HYBRID_EXPERIMENT_STATUS_20261106.md 为权威。
- CRM/AP/SUPPORT/ENG/ASSET 的状态均为候选 gate 判断，不得纳入已达标计数。
