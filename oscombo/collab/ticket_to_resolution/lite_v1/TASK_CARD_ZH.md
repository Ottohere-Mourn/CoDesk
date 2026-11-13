# Case 2 Lite v1.2.0 任务卡

## 案件

合成工单 T-1042：客户收到损坏的 USB-C dock，订单 O-2048 中的显示器完好。核验订单行 O-2048-L2、送达证据 DELIVERY-EV-77 与政策 POLICY-RET-4。应退 dock 本金 $80 加税 $8，共 $88；不退 $15 运费，不修改完好的显示器或其他记录。

## 协作角色

- **A / Order Verifier**：查看客户陈述、订单、证据和政策；保存结构化 Case Review；向 B 发送实际生成的 Review ID。消息不得直接包含拟退款金额。
- **B / Support Processor**：先独立复核来源记录，在 B 自己的页面保存资格、受损行、证据、运费处理和拟退款总额；然后读取 A 的协作消息，在 GUI 中输入消息给出的 Review ID 打开 Review；比较两份审核后，按当前有效 Review 退款并以 `PARTIAL_REFUND_DAMAGED_ITEM` 结案。
- **S / 单 Agent**：沿用原单人完整业务流程，不要求 A/B 双人预核验。

## 重要流程

B 起始页面保留工单、订单、证据和政策；不会轮询或自动跳转到 A 的 Review，也不会预先显示 Review ID。B 未保存独立预核验前，服务器拒绝其打开 Review 页面。该预核验是有评分意义的双人复核，不是解锁码或预填答案。Review ID 必须由 A 的 GUI 保存审核后产生并通过消息交接；退款仍须引用 A 的最新有效 Review。

Isolated、Shared 与 Shared+Lock 使用完全相同的任务、提示、fixture、预算和评分。GUI 事件、协作消息与实际读取、审核 ID、退款关联、结案时间线、桌面输入、模型/API 及 reset/cleanup 状态分别留证。Shared 失败是研究假设，不是验收条件；保留所有成功、失败和无效运行。
