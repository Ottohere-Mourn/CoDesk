# Data-to-Deck Lite v1 (CDD-LITE-001)

一位经理需要一页 Q3 财务回顾。公开工作簿只有 Q2/Q3 的区域销售额与成本、指标定义，以及预留的两行 Findings。草稿幻灯片有数字、方向和因果表述问题。两个角色可以同时开始；B 可先检查草稿，但最终必须使用 A 实际保存的 Findings 版本。

A 是 Data Verifier。只修改输出副本 `outputs/agent_A/verified_analysis.ods` 的 Findings：Q3 gross margin（百分比）和 West operating-profit change（Q3−Q2，千美元），分别写入数值与能追溯到 Sales/Costs 单元格的依据。不得改原始 Sales、Costs、KPI_Definitions，也不得编辑 B 的幻灯片。保存后发布 revision 并向 B 传递验证结论；可以先发布阶段性版本。成本变化与利润变化同时发生，不足以证明因果关系。

B 是 Report Editor。只修改 `outputs/agent_B/final_management_brief.odp` 中唯一一页的错误内容，保留正确标题。最终版本需准确表述 Q3 gross margin、West 利润变化的方向和幅度、West 推广支出的变化与因果证据边界。B 可提前整理草稿，但完成前必须查看 A 最新保存版本，将最后一行 pending source 换为该输出工作簿的 SHA-256 前12位；若 A 后来又保存，新版本也须核对。引用字符串本身不构成已阅读 A 分析的证据，评审会检查消息、产物版本和 GUI 轨迹。

两种条件使用相同公开输入、角色指令、模型、工具、40次/角色 GUI 工具调用上限和1200秒/角色超时。同为真实并发模型调用。Shared 使用一个 Ubuntu Guest 及其共同鼠标、键盘、焦点，不加输入锁；Isolated 使用两个独立 Guest，通过既有版本桥同步完整保存的 ODS/ODP。两边都有消息和附件工具。保存、回收、关闭重开和 reset 都纳入验收。

评分侧独立验证：A 的两个数值、单位、源单元格依据和受保护表；B 的一页最终内容、正确方向/数值、因果限定和与 A 最终文件匹配的来源摘要；同时给出 A、B、联合与保护结果。过程侧另外审计 B 是否实际读到 A 的 revision 或消息，不能从摘要字符串单独推断发生有效交接。Gold 与 Oracle 不挂载到 Actor Guest。

这一版只有两项 Calc 核验和一页 PPT 的三处业务修订加来源行。预期约15–30个有效 GUI 调用/角色，这是待实测估计，不是成功判据；不会为某个拓扑的结果修改 v1 的任务或 Oracle。
