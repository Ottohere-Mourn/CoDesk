# CoDesk Case 6：Spreadsheet Handoff V0

## 目标

两名 GUI Agent 在同一 ODS 补货工作簿中完成预测、采购计划、预算检查和复核。关键共享状态是“工作簿的最新已提交版本”，不是数据库或文件系统差异。A/B 都可以读取全部源数据和规则；角色分工由产物责任界定，不靠信息封锁。

## 固定场景与 Gold

预测未来两个月，销售均值取最近三个月算术平均；目标库存 = 预测量 + 安全库存；可用库存 = 现有 + 确认在途；净需求不得小于零；正净需求向上取整到整箱。采购总额包含固定 `$120` 运费，预算上限 `$3,300`。

| SKU | 最近三个月销量 | 现有/在途/安全库存 | 箱规 | 单价 | 均值/月 | 预测 | 净需求 | 采购量 | 金额 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SKU-LAMP | 40, 50, 60 | 42 / 18 / 30 | 10 | $28.00 | 50 | 100 | 70 | 70 | $1,960 |
| SKU-MUG | 65, 55, 60 | 50 / 10 / 20 | 24 | $7.50 | 60 | 120 | 80 | 96 | $720 |
| SKU-CABLE | 90, 100, 110 | 150 / 30 / 50 | 25 | $6.40 | 100 | 200 | 70 | 75 | $480 |
| SKU-CASE | 18, 20, 22 | 60 / 0 / 10 | 20 | $15.00 | 20 | 40 | 0 | 0 | $0 |

采购小计 `$3,160`；加运费总额 `$3,280`；预算上限 `$3,300`，剩余 `$20`。SKU-CASE 的可用库存高于目标库存，必须保持零采购。Gold 使用 Calc 公式并带公式缓存值。完整规则与源值位于 `Rules`、`Sales`、`Inventory` 工作表。

## Actor 指令

### A — Forecast owner

> You are A, responsible for the demand and inventory analysis in the replenishment workbook. Review the Sales and Inventory sheets against the included data notes. In the Forecast sheet, complete the three-month average, two-month demand forecast, target stock (forecast plus safety stock), available stock (on hand plus inbound), and non-negative net requirement. Preserve every source value. Add concise cell-level evidence and mark your Forecast review complete only after checking B's proposed order quantities against your calculations. You may ask B to clarify any procurement assumption and may revise your own forecast if you find a source-data issue. Do not edit the Replenishment or Budget sheets. Save each workbook revision through the shared version service before handing off; the service permits only one active writer and rejects stale revisions. All source facts and rules are visible to both roles; messages and attachments are available when useful, with no required number or timing.

### B — Procurement owner

> You are B, responsible for procurement planning in the same replenishment workbook. Read the Sales, Inventory, and Rules sheets and use A's Forecast sheet as an auditable input. Complete the Replenishment sheet: round each positive net requirement up to the next allowed case pack, preserve zero requirements as zero, calculate extended cost, and provide a short procurement reason. Complete the Budget sheet using the stated freight and cap, and check that your order rows agree with A's forecast. If figures or assumptions do not reconcile, ask A a specific question and revise your plan after checking the latest saved workbook revision. Do not edit source sheets or the Forecast sheet. Save through the shared version service; only one actor may hold the write lease, and every commit must be based on the latest revision. All source facts are visible to you; use messages or attachments as needed, without a prescribed handoff schedule.

### Single Agent

> Complete the full inventory replenishment workbook. Verify the visible sales, inventory, and procurement rules; fill the Forecast, Replenishment, and Budget sheets; ensure case-pack rounding and total cost fit the budget; and perform a final cross-check. Preserve source data and use formulas where the existing layout calls for them. Save the completed workbook through the version service and verify the committed revision. No hidden evaluator state is available.

## 版本与对照协议

每个 episode 有一个 ODS 版本库。A/B/S 先取得唯一写租约，拿到最新 `.ods` checkout；提交时按 revision + SHA-256 compare-and-swap。提交或 abandon 后租约释放，下一角色取最新版本。并发过期提交会被拒绝，Actor 必须重取版本并合并。三条件使用相同版本库、fixture、服务、消息/附件权限、任务和评分；只改变 GUI 桌面数量：Single=1，MA-ID=2，MA-SD=1。所有来源信息均可见。Lease 会串行化写入，但不会强制消息顺序或预设交接轮次。

文件系统/版本冲突（过期 revision、提交冲突）单独记录；只有真实 GUI 操作及焦点/选择状态证据才能标记桌面干扰。脚本提交不是 GUI/模型证据。

## Oracle 与保护

Oracle 通过 Data-to-Deck 的 `read_ods` 展开 ODF 重复行/单元格；非整数浮点仅使用其 `1e-15` 相对/绝对容差，整数和金额保持精确。检查 source sheets 原样完整、目标 sheet/行集、预测值、采购量、预算、公式位置与表达式、A/B SKU/净需求一致、A 复核状态和真实 ODS 容器。正控为 `fixtures/private/gold.ods`，负控包括空初始、错预测、错箱规数量、错公式、超预算和改写源行。

## 状态

- Fixture、Gold、Oracle、正负控、版本库、消息、reset、配置：离线实现。
- LibreOffice headless ODS 保存/重开：由测试单独报告。
- Calc GUI、Guest、Solo、MA-ID、MA-SD、干扰与恢复：`PENDING_GUEST_VALIDATION`。
