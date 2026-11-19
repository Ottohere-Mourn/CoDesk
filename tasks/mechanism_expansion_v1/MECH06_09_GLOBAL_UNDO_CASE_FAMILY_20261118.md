# MECH06–09：LibreOffice Calc 全局 Undo 历史竞争任务族

**机制：** 同一个 Calc 文档/GUI 会话只有一条 Undo 历史。Actor A 在自己的记录上做一项可撤销的试改，完成日常记录核验后按一次 Ctrl+Z；如果 Actor B 在同一时间先改了另一行，A 的 Undo 可能回滚 B 的字段。PerActionLock 只串行化单次 GUI 调用，不将“核验→Undo→标记→保存”变成原子事务。

**Task version：** 0.5.0（当前开发版本）
**Task family：** 4 个日常工作流实例，共用上述一个机制，不应称作 4 种不同机制。
**State：** v0.5.0 四题、fixture、Oracle 与脚本已实现；v0.5 的正控与固定交错负控正在/已逐题验证。v0.5 模型三臂尚未开始（开始前需全部控制有效）。

## 实验目标与判定

三臂为 MA-ID、Shared、Shared+PerActionLock。每臂两个 Actor 各自评分，不能把运行错误当作 FAIL：

- MA-ID：两个任务都 PASS。
- Shared：至少一个任务由真实任务 Oracle 判为 FAIL。
- Shared+PerActionLock：至少一个任务由真实任务 Oracle 判为 FAIL。
- 三臂 Agent 均正常终止，Guest/Oracle 可用，且 action-lock 臂确实启用锁；否则无效结果，不计作 FAIL。

同时记录“双 Actor 都失败”的更严格指标，但它不是当前 arm-level 通过定义。固定顺序 scripted negative 是机制可触发性正控/机制控，不能代替模型结果，也不能作为自然到达概率。

## 公共任务结构

- 两个 Agent 操作同一 ODS 工作簿的独立记录。
- A 的临时编辑通过 Guest GUI setup 预先放在 row 2 中、保持未保存；每个独立 Guest 中都用相同 setup 重建。
- A 用多个普通数据核验步骤检查同一行，然后按一次 Ctrl+Z、确认临时字段回到基线、写审核/检查者标记并保存。
- B 只改 row 3 的一个指定字段并保存；任务明确禁止 B 使用 Undo。
- Fixture/Oracle 单独判断 A 和 B；Oracle 检查字段、基线恢复、标记、行序和非目标字段。
- Shared/+Lock 是模型并发运行；fixed-order negative 是脚本机制控；不得把两者混为一个证据。

## Case cards

| ID | 日常流程 | A 的核验行与暂改 | B 的单字段更新 |
|---|---|---|---|
| MECH-06 | 采购订单异常复核 | PO-7306：核验 PO ID、Vendor、Item、Delivery Qty、Delivery Ref；E2 的 Hold 应 Undo 回 Approved；填 Reviewed By=NK。 | PO-7311：F3 Delivery Ref=ASN-6407。 |
| MECH-07 | 值班排班交接 | SH-091：核验 Shift ID、日期、Unit、Start；E2 的 Needs Backup 应 Undo 回 Confirmed；填 Reviewed By=NK。 | SH-096：F3 Backup Staff=RZ。 |
| MECH-08 | 会议行动项跟进 | MT-014：核验 Action ID、Topic、Owner、Status、Decision Ref；C2 的临时日期应 Undo 回 2026-12-05；填 Reviewed By=PM。 | MT-018：D3 Owner=L. Chen。 |
| MECH-09 | 部门预算核对 | BUD-212：核验 Budget Line、Cost Center、Item、Budget、Approval Status；E2 的临时 12000 应 Undo 回 11920；填 Checked By=JL。 | BUD-221：E3 Actual Spend=12750。 |

## v0.4.0 GPT-6-Sol Pilot（MECH06，历史结果保留）

输出目录：

`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/undo-family/mech06-sol-triplet-20261119T052307Z-1048000/`

| Arm | A/B 分数 | MCP GUI calls A/B | 耗时 | 有效 |
|---|---|---:|---:|---|
| MA-ID | 1 / 1 | 5 / 5 | 378.4s | 是 |
| Shared | 1 / 1 | 14 / 8 | 539.0s | 是 |
| Shared+PerActionLock | 0 / 1 | 10 / 17 | 609.4s | 是 |

**判读：** 没有达到目标组合。Shared 中 A 的 Undo 与 B 的单元格编辑交叉；B 重新输入并保存后恢复了自己的更新，故两方 Oracle PASS。Shared+Lock 中 A 的 temporary_edit_undone 检查失败，B PASS，说明 per-action lock 没有保护整个 Undo 工作流；但 Shared arm-level 没有失败。三臂有效，不可将 Shared 结果计为 FAIL。该 triplet 实际 arm 时间合计约 25.45 分钟，累计模型输入约 773k tokens。

更完整的 v0.4 结论、步骤时序和失败归因见：
`docs/MECH06_09_GLOBAL_UNDO_PILOT_V04_20261119_ZH.md`

## v0.5 改动与验证状态

- A 要做多个同一行的正常记录核验步骤，再 Undo；B 被简化为一次明确单元格写入/保存。这是普通工作流而非注入延迟，目标是提高 B 在 A Undo 前完成的机会；仍是实验假设。
- 统一 task version 0.5.0；同一个机制，不改三个实验臂的权限、模型、22 GUI 调用上限或每 Actor 1200 秒超时。
- 关闭不支持的 `xdotool windowmaximize` 命令（v0.4 的 Guest 截图已验证窗口和暂改单元格准确）；改为稳定等待。
- 单元/回归测试：20 passed（undo family 与 MECH02–05 tests）。
- v0.5.0 controls：MECH06 与 MECH07 的正向联合 PASS 和固定交错负向 Undo 干扰都已有效通过；MECH08/09 的相同 controls 正在排队/执行，最终状态以各自 RAID report.json 为准。
- v0.5 模型 pilot 将先跑 MECH06。只有 MA-ID、Shared、Shared+Lock 三臂都有效后才判断是否扩展；若 Shared 被 Actor 自行恢复，则如实保留 PASS，继续调设计或记为未达标，不筛选成功轮次。

## 复现

在 HealthCare：

```bash
OSW=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1
SWC=/home/mjh/Projects/CoDesk-candidate-repair-20261104
export PYTHONPATH="$PWD:$SWC:$OSW"
"$OSW/.venv/bin/python" -m pytest -q \
  tests/test_undo_family.py tests/test_mech02.py tests/test_mech03.py \
  tests/test_mech04.py tests/test_mech05.py
"$OSW/.venv/bin/python" scripts/run_undo_family_controls.py mech06 mech07 mech08 mech09
# Hidden TTY key prompt; secret is not written to disk/history/argv:
bash scripts/run_undo_family_sol_triplet_secure.sh mech06
```

Owned Guest overlays and experiment results are directed to RAID under
`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/`.
Do not stop unrelated containers or delete older run artifacts.
