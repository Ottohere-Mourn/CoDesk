# CoDesk Case 7：Workspace Assembly V0

## 共同目标

将已有的 Project Aurora 项目资料整理成可以交付的文件夹：附件按公开 brief 分类、重命名并生成校验清单；Writer 报告移动到 delivery 目录，保留叙述并更新四个相对附件引用。起始资料、目标名称、报告和所有附件均对 A/B 可见。两人的职责互补，但不存在强制消息轮次或固定交接时间。

## Fixture 与预期交付

`fixtures/initial_workspace/` 含真实 ODT、PNG、PDF、CSV、TXT、项目 brief 和需保留的历史/说明文件。Actor 通过工作区根目录下的 `incoming/Project_Brief.md` 读取最终路径。A 将四个附件按 brief 移至 `delivery/attachments/`，逐字节保留，并生成 `delivery/attachment_manifest.csv`：asset ID、相对路径、SHA-256、描述。B 将 `incoming/Quarterly_Supply_Report.odt` 移至 `delivery/Quarterly_Supply_Report.odt`，保留全部段落，将四个链接改为相对报告目录的最终路径：

- `attachments/q3_revenue_chart.png`
- `attachments/vendor_terms.pdf`
- `attachments/inventory_snapshot.csv`
- `attachments/compliance_summary.txt`

`incoming/README.md`、`incoming/Project_Brief.md` 和 `archive/q2_baseline.txt` 必须保持原样。完整 Gold 树在 `fixtures/private/gold_workspace/`。

## Actor 指令

### A — 文件整理与附件清单

> You are A, the delivery-file coordinator. The incoming project folder contains the full source set and the report draft; no files are hidden. Use the file manager to create the delivery folder, move and rename the four referenced attachments according to the project brief, and produce `delivery/attachment_manifest.csv` with each attachment ID, relative path, SHA-256, and description. Preserve the source bytes exactly and leave unrelated files in place. Verify B's updated report links against the final folder and manifest; if a filename or digest does not match, message B with the concrete discrepancy and reconcile it. You own file organization and the manifest, not the Writer report. Messages and attachments are available when useful; no message count or timing is prescribed.

### B — Writer 报告

> You are B, the report editor. Read the complete project folder and brief; all files are visible. Use Writer to move the draft to `delivery/Quarterly_Supply_Report.odt`, preserve its existing report content, and update its four attachment references to the final relative paths listed in the brief/manifest. Keep the reference labels descriptive and ensure every link resolves from the report's delivery directory. Ask A about a missing or ambiguous attachment only if the visible materials do not resolve it. Reopen and verify the saved ODT after A's path changes. You own the report, not the attachment renames or manifest. Messages and attachments are available when useful; there is no prescribed number or timing.

### Single Agent

> Prepare the Project Aurora delivery package. Use the file manager to organize and rename the four listed attachments into `delivery/attachments/`, preserve their bytes, and create `delivery/attachment_manifest.csv`. In Writer, move the existing report into `delivery/`, preserve its content, and update all four relative attachment links to the final paths. Verify hashes, links, and protected files. All source materials are visible; no hidden evaluator state is available.

## 条件与因果边界

Single、MA-ID、MA-SD 使用同一初始目录、同一 run-scoped canonical workspace/backend、消息/附件服务、Actor 权限和 Oracle；MA-ID 与 MA-SD 仅改变桌面/session 拓扑。MA-ID 未来需要两个桌面都连接同一 workspace backend；Guest 映射目前未实现/验证，不能用两个不同副本替代。MA-SD 是一个实时桌面。

文件重命名、文件树变化、版本提交与路径传播记录为 workspace 状态；只有真实 GUI 证据支持时，才把活动目录、选区、文件选择器、剪贴板或焦点变化标记为桌面干扰。共享桌面不要求两人同时编辑同一窗口。

## Oracle 与状态

Oracle 检查精确最终路径集、四个附件 SHA 与初始源相同、源路径不残留、CSV 清单精确、ODT 真实容器/全部原文/超链接目标、相对路径能在交付树解析、三个非目标文件完整。离线 Gold PASS、Initial FAIL；链接损坏、缺/多文件、清单哈希错、附件字节变化、受保护文件变化均为负控。离线和宿主 LO 保存重开不等于 Guest/GUI Agent 成功。Guest、Single Agent、MA-ID、MA-SD 均 `PENDING_GUEST_VALIDATION`。
