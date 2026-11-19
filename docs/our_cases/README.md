# CoDesk：本工作流创建的案例索引

更新日期：2026-11-19。聚合分支已有 handoff 记录 211 个任务/配对条目。本次新增并提交 9 个 MECH 任务后，分支总数为 **220 项**。按原任务卡、批次提交和来源分支核对，本工作流明确负责的既有案例为 **84 项**；计入本轮 9 个 MECH 后合计 **93 项**。其余 127 项不应笼统标作 ZYK 原创：其中既有其他工作线，也有外部基准适配和参考任务库。本索引只把来源能对上的算入，不用 Git author 名字单独推断归属。

## 分类

- A1 核心双 Agent：19 项（Case-2/3/4、机制原型与业务流程扩展）
- A2 Synthetic Desk 扩展：48 项（V1–V47 + 独立 `pg_e1`）
- C1 Human-Agent：17 项（脚本化正常用户 + 真实 Agent）
- 本轮机制扩展：9 项（MECH01–09；MECH01–06 有有效模型三臂，MECH07–09 只有 scripted controls）

## 文件

- [`CASE_SUMMARIES.md`](CASE_SUMMARIES.md)：适合人阅读的 93 案逐项文本概要与可用截图链接。
- [`case-catalog.csv`](case-catalog.csv)：机器可读摘要、模型/控制证据状态、来源文档、截图状态与原始截图路径；共 93 条。
- [`screenshots/`](screenshots/)：当前 HealthCare 可访问且能可靠映射到 case 的精选关键 PNG；当前覆盖 **75/93** 个 case。只复制精简精选图，不复制原始 runs。

## 截图边界

原始截图/视频仍保存在对应 RAID run 或 `cpu15:~/data/paraGUI/runs/`，CSV 记录可访问图源路径。本轮 HealthCare 可复制 75 个案例的 PNG；其余 case 明确标为未取得。Human-Agent 全量多臂截图/录像主要在 `cpu15`，但该 SSH 名称在本轮无法解析；Case-2/3/4 和部分早期双 Agent run 也未在当前可访问目录找到可靠对应图。没有用无关图占位。恢复 `cpu15` 访问后可按 CSV 的 case/run 映射只读补齐。

## 归属口径

A1 的 19-case、A2 的 V1–V47 与 `pg_e1`、C1 的 17 个 Human-Agent case，都能从本工作流相应源分支、任务卡与实验批次提交/报告核对。MECH01–09 是本轮新增资产。聚合分支里的其他主题赛道、公开基准适配和参考题库不因同处一个 branch 就计作本工作流原创。
