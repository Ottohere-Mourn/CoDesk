# Data-to-Deck Lite v2.1：West 利润变动交接

本版仅修复评分对 `11 USD thousands` 的等价单位表达识别；公开任务、Fixture 文件内容、角色指令和 GUI 流程与 v2.0.0 相同。v2.0.0 的历史评分保持原样。

管理层要在一页汇报中看到 West 区 Q3 相对 Q2 的营业利润变动。A 在已打开的 Calc 工作簿中核算变动，填写 B6 数值和 D6 输入单元格依据，保存并发布，再给 B 发送核验结果。B 可以同时查看已打开的 Impress 草稿，但最终结论须采用 A 已保存、已交接的分析；将一处未完成文本改成包含变动方向、金额和 `verified_analysis.ods` 来源的句子，保存并发布。

两种桌面条件使用同一公开文件、角色指令、模型、工具和评分。Shared 两个 Agent 并发控制同一 Ubuntu 桌面；Isolated 两个 Agent 分别控制一个 Ubuntu 桌面，已保存产物由版本桥共享。评分检查真实 ODS/ODP 内容，交接行为另由消息、版本和轨迹核验。Gold/Oracle 不给 Actor。
