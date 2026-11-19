# MECH06–09 全局 Undo 竞争：模型 Pilot 与迭代记录

日期：2026-11-19（HealthCare）

## 当前结论

MECH06 v0.5.0 的 GPT-6-Sol 三臂均有效，并一次满足 arm-level 目标组合：MA-ID A/B=1/1，Shared A/B=0/1，Shared+PerActionLock A/B=1/0。所有模型 actor 均产生终止结果，任务 Oracle、Guest/reset 正常，无 API/Guest/runner 错误。按本项目定义这是一次有效的模型方向命中；它不代表双角色都失败，也没有重复试验。完整 v0.5 说明见文末和 case family card。

本文件以下 v0.4.0 结果是保留的历史迭代，不应与最新 v0.5.0 混为一谈。v0.4.0 曾是真实有效但未满足目标的模型三臂：MA-ID PASS/PASS、Shared PASS/PASS、Shared+PerActionLock A FAIL/B PASS。其 Shared 中出现了被 B 恢复的 Undo 干扰，说明竞争实际发生，但没有形成共享任务失败。

## v0.4.0 运行

三臂输出目录（RAID）：

`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/undo-family/mech06-sol-triplet-20261119T052307Z-1048000/`

| Arm | A/B 评分 | GUI MCP 调用 A/B | arm 总秒数 | 有效性 |
|---|---|---:|---:|---|
| MA-ID | 1.0 / 1.0 | 5 / 5 | 378.4 | 有效，PASS/PASS |
| Shared | 1.0 / 1.0 | 14 / 8 | 539.0 | 有效，PASS/PASS |
| Shared+PerActionLock | 0.0 / 1.0 | 10 / 17 | 609.4 | 有效，A FAIL/B PASS |

三臂合计约 25.45 分钟（不含后续离线分析）；真实模型调用、Guest 和评估均有效，失败不能归因为基础设施。MA-ID、Shared、Shared+Lock 的两个 Actor 均产生终止回复；每个臂的任务 ODS 均可读取，记录 ID/行序/非目标字段检查正常。

### 观察到的干扰

- Shared 中 A 的 `Ctrl+Z` 发生在 B 第一次录入 Delivery Ref 后、B 保存前。B 随后重新录入 ASN-6407 并保存，最终两个 Oracle 都 PASS。这是一次被 Actor 自行修复的共享 Undo 干扰；它使 Shared 结果不能算 FAIL。
- Shared+PerActionLock 中，A 最终 `temporary_edit_undone=false`，其审核标记仍保存、非目标字段完整；B 的目标更新 PASS。该臂有效地暴露了锁不保护多步 Undo 事务，但不满足“双方都失败”的严格判据。
- 不能只看“输入调用已被锁住”来推断交易性保护；锁确实只是单次 GUI 调用粒度。

## v0.5.0 迭代

为后续 MECH06–09 统一修改（task/fixture 主题保持）：

1. A 改为更完整但仍正常的记录审查：逐格核对 ID、日期/单位/项目、数量/预算、引用等多个事实，然后执行一次 Undo，并检查临时字段回到基线。
2. B 的目标操作改成单一、明确的目标单元格写入，禁止额外 Undo，减少因目标 cell 定位错误而反复试探。
3. 同步更新 scripted controls，使正控及固定负向机制控覆盖与 v0.5 任务相同的“逐格审查”步骤。
4. 初始截图已确认 LibreOffice 窗口和 E2 临时值正确；移除 Guest 中不支持的 `xdotool windowmaximize` 调用，只保留稳定等待，避免把该错误误记作成功。
5. Python 合约/回归测试：20 passed（含 MECH02–05 的相关测试）。

v0.5 scripted positive + fixed-interleaving controls 正在 HealthCare 上重新验证；在 controls 完成前没有启动 v0.5 模型三臂。该版本增加的是合理工作流审查，不是人为 sleep 或只为制造失败的额外障碍；如果模型仍自行恢复，照实记录，不筛除不利结果。

## 解释与后续判据

- 固定脚本负控证明的是机制可被触发；它不是自然模型调度的失败率估计。
- 模型目标判定使用 MA-ID 两个 PASS、Shared 至少一个任务确实 FAIL、Shared+PerActionLock 至少一个任务确实 FAIL，并且三臂均为有效终止。
- Infrastructure-invalid、Oracle 读失败、超时或未终止回复一律不得算模型 FAIL。
- v0.4 结果、旧 v0.1/v0.2 runs 以及早期 v0.3 scripted controls 均保留，不覆盖、不筛选。


## v0.5.0 ?????2026-11-19?

v0.4.0 ?????????v0.5.0 ????? `tasks/mechanism_expansion_v1/MECH06_09_GLOBAL_UNDO_CASE_FAMILY_20261118.md`??? MECH06 ? MA-ID A/B=1/1?Shared=0/1?Shared+PerActionLock=1/0??? arm ? `valid_terminal=true`??? actor ? terminal?API/Guest/runner error ?? null?reset/Oracle ?????????? arm-level `MA-ID PASS / Shared FAIL / Shared+Lock FAIL`?????????????????????? 45.3 ???MECH07?09 ??? fixture/Oracle ? scripted controls???????????????

????????HealthCare RAID??`/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/undo-family/mech06-sol-triplet-20261119T062005Z-1078853/`?v0.4 ????????/??????????????????
