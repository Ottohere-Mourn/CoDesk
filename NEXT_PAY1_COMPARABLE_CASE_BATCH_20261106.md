# PAY-1 对标的新候选批次：静态雏形与筛选（2026-11-06）

状态：设计头脑风暴与纸面审计；全部是未实现、未验证的候选。本轮没有启动 Guest、Codex Actor 或正式模型实验，也未改 Case 2/3/4。

> **后续状态（2026-11-06 晚间）**：DATA-REL1 已从候选完成到一次 GPT-6-Sol screening triplet：MA-ID PASS / Shared FAIL / Shared+Lock FAIL。细节见 `DATA_REL1_CASE_CARD_20261106.md` 与 `DATA_REL1_EXPERIMENT_SUMMARY_20261106.md`。其他候选仍是设计/语义 gate 阶段。本文件中的 11/06 上午“未验证”标记为当时快照，不代表晚间进展。

## PAY-1 的边界与本批目标

PAY-1 一次有效筛查为 MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL：薪资专员先完成 8h/$256 付款行，主管之后在共同工时账本提交合法的 6h 更正，导致付款行与当前批准工时不一致。这证明晚到业务更正可使已完成快照失效；不是 GUI 焦点/键鼠误路由，也没有测试并发动作锁竞争。Shared+Lock 按任务完成顺序运行，说明逐动作锁不会自动刷新跨任务业务状态。

本批借鉴的是 PAY-1 的实验纪律与 workspace-local oracle，不把“再找一个晚到更正”直接宣称为新机制。

## Brainstorm 来源与模型可用性

按用户建议尝试 Astra 子 Agent，但协作工具当前没有 gpt-6-astra 选项；替代的 gpt-6-luna 请求返回 404（账号组不支持）。随后成功用 gpt-6-sol 子 Agent 作独立 brainstorm。它提出 CRM 并行字段更新、客服重复外发、测试/部署版本漂移、重复退款、离职撤权、会议室冲突、重复发票等方向。本卡对建议做了去重审计，没有调用外部 API key。

## 所有候选必须过的验收门

1. 同臂固定 task version、fixture、prompt、模型、工具、预算、reset、oracle。MA-ID 是同初始 fixture 的 A/B 私有 Guest workspace；Shared 是一个共同工作件，采用相同 workspace-local 评分函数，不按实验臂硬编码答案。
2. 证明 Shared-only 的完整因果链：A 的观察/提交、B 的合法变更、共享状态变化与具体终态错误都有时间戳证据。若实际是共同后端、焦点/选择/剪贴板、隐藏障碍或 evaluator 造成，不能称为 shared-desktop 效应。
3. 保留刷新、重查、合并、撤回、重做、升级等正常恢复。模型恢复成功就是 PASS；不关闭正常版本保护/唯一键，不隐藏信息来追 FAIL。
4. +Lock 结果不能预设。先查清生产 PerActionLock 粒度，若应用/Agent 恢复或防住错误应判 PASS。逐动作锁未必覆盖跨任务业务事务，但需实测。
5. 先做静态/fixture/oracle 与 Guest-local scripted controls，再 MA-ID；仅 valid exact PASS 后运行匹配 Shared、Shared+Lock。无效基础设施不算模型 FAIL。一次筛查不算重复。
6. workflow-level case 与 new mechanism 分开计数；相同上位机制换业务域，不宣称新机制。

## 候选批次（先验判断，不是测量）

| 优先级 | 候选 | 工作流/失败签名 | 实用性与距离 | 主要风险 |
|---|---|---|---|---|
| 1 | **CRM-LU1 客户主档 lost update** | A 改续约联系人，B 改账单邮箱；过期的完整表单保存覆盖另一方字段。 | 客户主档维护频繁；不是焦点、剪贴板、Tab、Selection、Undo 或 PAY-1 工资快照。 | 现代 CRM 可能做版本冲突检查或 PATCH；不能关闭保护来造错。 |
| 2 | **DATA-REL1 隐私限制与数据集导出** | A 生成待发布合成数据包；B 登记合法 subject-level exclusion；Shared 的 active package 仍包含被限制记录。 | 数据导出/撤回是常见合规工作；业务域区别大。上位状态新鲜度家族接近 PAY-1。 | MA-ID clone 语义、限制生效时点和发布撤回政策必须一致、自然。 |
| 3 | **SUPPORT-ONCE1 跨渠道重复 intake/单一响应** | 同一根工单经邮件和网页重复进入队列；若 Shared 出现两条答复，造成重复承诺。 | 客服重复 intake 常见；错误签名是重复副作用，而非工资快照；与 Case 2/W4 有一定邻近。 | 克隆任务的公平性困难；B 发现已有答复并链接是正常恢复。只能用本地假 outbox。 |
| 4 | **ENG-TRANS1 工程图纸 transmittal 版次失配** | A 做 staging 交付包，B 正式 supersede 一张图；有效包仍引用旧版。 | 施工/工程交付实用；与 Case 3 软件发布/测试及 PAY-1 stale artifact 有中等重合。 | 更像 PAY-1 状态新鲜度的领域变体，不应称新机制。 |
| 5 | **ASSET-HOLD1 IT 资产报废清单遇 Legal Hold** | A 准备待审批处置 manifest，B 对设备加有来源的 hold；active manifest 仍列该设备。 | 合规后果显著，工作流不在已知主要领域。 | 仅限假资产和待审批清单；不得真的删数据/擦设备；hold 权威来源易歧义。 |

这些实用性/差异度均为设计先验，不是频率或实验结论。

## 优先三案规格雏形

### CRM-LU1 — 客户主档 stale-form overwrite
- A 维护 C-014 的续约联系人；B 维护同一客户账单邮箱。字段不同，凭证均明确。
- Shared 交错假设：A 读入普通完整表单、改联系人但暂未提交；B 更新并保存邮箱；A 随后保存旧表单。
- 只有普通 UI 确实整行覆盖时才可能丢失 B 的字段；锁住保存按钮不等于合并过期表单。MA-ID 为同初态私有 clone，各 Actor 对自己 workspace 的 owner 字段评分。
- 恢复（刷新、合并两个字段、解决冲突）完全开放并按 PASS 计。
- Oracle：record ID 不变；两字段最终值都符合源凭证；审计可定位丢失字段。负控：单 Actor 更新 exact pass、错误 ID 失败。
- No-go：界面有乐观并发拒绝、只 patch 修改字段、或只有关闭版本保护才产生覆盖。先 scripted 测完整表单语义，不先跑模型。

### DATA-REL1 — 隐私例外使待发布导出包失效
- A 按批准清单建立 local-only synthetic staging export；B 依据有效例外凭证登记一条 subject-level 限制和原因。
- A 将包标为 READY 后发标准 handoff；B 再提交限制。若 Shared 的 active READY 文件仍含当前受限记录则 A 的业务结果不合格；逐动作锁不会重算既有文件。MA-ID 各自 clone、各用 workspace-local oracle。
- 正常恢复：撤回旧 staging package，重筛、重算 manifest/hash；若 Agent 在发布前复核并修正按 PASS。
- Oracle：active READY 包都满足当前 exclusion；受限 subject 不出现在有效包中；旧包可留档但必须标 revoked/superseded。正控为无排除记录可导出，负控为限制后旧包仍 active，重导出应通过。
- 最大风险：不能把不同 Guest 后端 clone 说成同一真实研究数据库的政策传播；数据全合成、不出 Guest，并明确这只测 workspace topology。时点必须来自真实合理流程，而非臂别规则。

### SUPPORT-ONCE1 — 重复 intake 但一个根工单只答一次
- A 处理邮件问题；B 处理同一客户稍后由网页表单重复提交的问题；正常队列将两者关联到一个 root ticket。
- 共享工作区若 A 已发送本地模拟答复，B 再发第二条而未 link duplicate，就产生重复副作用；PerActionLock 不提供业务 idempotency。MA-ID 是相同 fixture 的私有副本，各自完成 owner-local inbox task；Shared 对单一 root thread 检查总答复数。
- B 可重查线程、link/close duplicate，不再回复；这属正常恢复。已发生 duplicate event 仍记任务失败，之后道歉另记恢复而不抹除事件。
- Oracle：唯一 root ID、渠道别名、recipient、回复次数与时间线、duplicate linkage。只用假邮箱和本地 outbox，严禁真实发送。
- 资格硬门：若 MA-ID 两边的任务无法与 Shared 中同一根工单定义为等价，或第二封回复在业务上其实应当发送，no-go；不得在 prompt 中指令“发两次”。

## 保留案与重合

ENG-TRANS1：小型合成 DWG/PDF 的 revision register；A 生成 staging transmittal，B 按正式变更通知 supersede 旧版；active package 若仍引用旧版则错，撤回重建可恢复。先审查与 Case 3 和 PAY-1 的差异。

ASSET-HOLD1：只模拟待审批销毁清单；A 列序列号，B 为一个序列号登记 legal hold；仍处于 active manifest 才算失败，模型可移除、撤回再建。绝不真实擦除，先审计法定流程和 MA-ID 含义。

Sol brainstorm 的测试/部署版本漂移因与 Case 3 软件发布/复测较近，不列优先；重复退款/发票因与 Case 2、AP-1、PAY-1 金融业务过近；离职撤权与 auth/身份场景重叠；会议室冲突与 W2 排程/容量邻近。

## 下一步建议

下一轮只做前三案的静态规格审计与真值表，不实现也不跑正式模型。选最容易通过因果/公平性门的一案，补 synthetic fixture 与 Python oracle positive/negative tests，再做 Guest-local scripted control；其后先 MA-ID exact PASS，再进匹配 Shared 与 Shared+Lock。

本批目前只是 workflow-level case 雏形，不支持 claim 五种新机制。DATA-REL1 与 ENG-TRANS1 属于“状态更新使已生成 staging artifact 变旧”的 PAY-1 上位变体；CRM-LU1 的字段 lost update 和 SUPPORT-ONCE1 的重复副作用签名更不同。“MA-ID clone + Shared 共同工作件”是本批沿用的解释；若研究要求三臂共享同一 enterprise backend、只改变桌面隔离度，本批和 PAY-1 都需重审，不能外推至一般数据库一致性。
