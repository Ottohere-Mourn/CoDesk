# 精选 23 项高质量双智能体基准与 184 条全量轨迹交付总览（严格 `pass_threshold = 1.0` 审计版）

- **统一严格判分标准**：`pass_threshold = 1.0`——单角色 `pass_a / pass_b` 与双角色联合 `joint_pass` 均要求 **100% 检查项全部通过（零错误，`mean_score == 1.0000` 才可判 `T`）**，彻底取消任何 `< 1.0` 容错及格线；部分完成度仅体现在连续得分 `mean_score` 中。
- **机器可读总索引**：[`lists/curated_23cases_and_trajectories_20261125.json`](../lists/curated_23cases_and_trajectories_20261125.json)
- **92 局 / 184 角色全量轨迹目录**：[`trajectories/curated_23cases_20261125/`](../trajectories/curated_23cases_20261125/README.md)
- **双轨制任务构建规范 Skills**：[`.agents/skills/paragui-case-design/`](../.agents/skills/paragui-case-design/SKILL.md)（盲并发共居）与 [`.agents/skills/paragui-collab-case-design/`](../.agents/skills/paragui-collab-case-design/SKILL.md)（明示同伴双向协作）

## 一、整体大盘统计（`gpt-6.1-sol` vs `gpt-6-astra`，`effort = high`，严格全对口径）

| 统计切片 | 题数 | `gpt-6.1-sol` `Isolated -> Shared`（严格 `1.0` 通过率） | `gpt-6-astra` `Isolated -> Shared`（严格 `1.0` 通过率） | `Shared` 分差 (`Astra - Sol`) |
|---|---:|---|---|---:|
| **1. `Curated-8`**（`EC-01,03` + 6 项优选 `RBS`） | 8 | `0.8718 (62.5%) -> 0.8394 (62.5%)` | `1.0000 (100.0%) -> 0.9175 (62.5%)` | `+0.0781` |
| **2. `AW-v1`**（`2h` 零步数上限复验 5 题） | 5 | `1.0000 (100.0%) -> 0.9321 (60.0%)` | `0.9778 (80.0%) -> 0.9778 (80.0%)` | `+0.0457` |
| **3. `NF-v1`**（100% 真软件重构 5 题） | 5 | `0.9260 (60.0%) -> 0.8762 (20.0%)` | `0.9701 (60.0%) -> 0.9583 (80.0%)` | `+0.0822` |
| **4. `NF2`**（`2h` 零步数上限复验 5 题） | 5 | `0.9891 (80.0%) -> 0.9458 (60.0%)` | `0.9274 (40.0%) -> 0.9131 (40.0%)` | `-0.0327` |
| **全量 23 题合计** | **23** | **`0.9370 (17/23, 73.9%) -> 0.8907 (12/23, 52.2%)`** | **`0.9729 (17/23, 73.9%) -> 0.9385 (15/23, 65.2%)`** | **`+0.0478`** |
| **15 题非饱和核心集**（筛除 8 道双模 `1.0->1.0` 满平题） | **15** | **`0.9033 (9/15, 60.0%) -> 0.8324 (4/15, 26.7%)`** | **`0.9584 (9/15, 60.0%) -> 0.9057 (7/15, 46.7%)`** | **`+0.0734`** |

## 二、23 题逐题严格全对成绩与路径索引

| 批次 | Case ID | 源码路径 | `6.1-sol` (`Iso -> Shared`) | `Astra` (`Iso -> Shared`) | 饱和状态 |
|---|---|---|---|---|---|
| `Curated-8` | `RBS3-04` | `tasks/rb_osw2_synth_v3/rbs3_04_icu_sso_nomogram_soffice.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 0.8899 (F)` | **核心区分题** |
| `Curated-8` | `RBS3-05` | `tasks/rb_osw2_synth_v3/rbs3_05_ircam_firmware_gateway_calc.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |
| `Curated-8` | `RBS3-02` | `tasks/rb_osw2_synth_v3/rbs3_02_cdp_live_frames_vs_8scene_sweep.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |
| `Curated-8` | `RBS2-06` | `tasks/rb_osw2_synth_v2/rbs2_06_maildesk_ics_vs_calc_contracts.py` | `0.9746 (F) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | **核心区分题** |
| `Curated-8` | `RBS-06` | `tasks/rb_osw2_synth_v1/rbs06_citevault_bibtex_soffice.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |
| `Curated-8` | `RBS3-01` | `tasks/rb_osw2_synth_v3/rbs3_01_zerospoiler_popovers_recreation.py` | `1.0000 (T) -> 0.7150 (F)` | `1.0000 (T) -> 0.9500 (F)` | **核心区分题** |
| `Curated-8` | `EC-01` | `tasks/exam_contention_v1/ec01_ma_dataroom_calc.py` | `0.5000 (F) -> 0.5000 (F)` | `1.0000 (T) -> 1.0000 (T)` | **核心区分题** |
| `Curated-8` | `EC-03` | `tasks/exam_contention_v1/ec03_enclosure_cad_emi.py` | `0.5000 (F) -> 0.5000 (F)` | `1.0000 (T) -> 0.5000 (F)` | **核心区分题** |
| `AW-v1 (2h)` | `AW-12` | `tasks/authentic_workstation_v1/aw12_chromium_zerospoiler_suite_recreation.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |
| `AW-v1 (2h)` | `AW-14` | `tasks/authentic_workstation_v1/aw14_gimp_crop_layers_inkscape_poster.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |
| `AW-v1 (2h)` | `AW-15` | `tasks/authentic_workstation_v1/aw15_qt_designer_2tab_linguist_10str.py` | `1.0000 (T) -> 0.7717 (F)` | `1.0000 (T) -> 1.0000 (T)` | **核心区分题** |
| `AW-v1 (2h)` | `AW-19` | `tasks/authentic_workstation_v1/aw19_libreoffice_dense_budget_and_redline.py` | `1.0000 (T) -> 0.8889 (F)` | `0.8889 (F) -> 0.8889 (F)` | **核心区分题** |
| `AW-v1 (2h)` | `AW-20` | `tasks/authentic_workstation_v1/aw20_inkscape_gimp_freecad_meddevice_enclosure.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |
| `NF-v1` | `NF-01` | `tasks/novel_frontier_v1/nf01_dach_xkb_writer_calc.py` | `0.8366 (F) -> 0.9183 (F)` | `1.0000 (T) -> 0.7917 (F)` | **核心区分题** |
| `NF-v1` | `NF-05` | `tasks/novel_frontier_v1/nf05_broadcastchannel_quant_lineage.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |
| `NF-v1` | `NF-11` | `tasks/novel_frontier_v1/nf11_biologics_uno_lims_coldchain.py` | `1.0000 (T) -> 0.7002 (F)` | `0.9618 (F) -> 1.0000 (T)` | **核心区分题** |
| `NF-v1` | `NF-13` | `tasks/novel_frontier_v1/nf13_stateful_kernel_pos_coldstorage.py` | `0.7936 (F) -> 0.7936 (F)` | `0.8889 (F) -> 1.0000 (T)` | **核心区分题** |
| `NF-v1` | `NF-14` | `tasks/novel_frontier_v1/nf14_blender_gui_surgical_trocar_dhf.py` | `1.0000 (T) -> 0.9688 (F)` | `1.0000 (T) -> 1.0000 (T)` | **核心区分题** |
| `NF2 (2h)` | `NF2-05` | `tasks/novel_frontier_v2/nf2_05_qtassistant_arinc429_flight_calc.py` | `1.0000 (T) -> 0.9400 (F)` | `1.0000 (T) -> 0.7400 (F)` | **核心区分题** |
| `NF2 (2h)` | `NF2-11` | `tasks/novel_frontier_v2/nf2_11_blender_vse_broadcast_nle_ebur128.py` | `0.9453 (F) -> 0.7891 (F)` | `0.8672 (F) -> 1.0000 (T)` | **核心区分题** |
| `NF2 (2h)` | `NF2-12` | `tasks/novel_frontier_v2/nf2_12_freecad_cubesat_mass_cg_coupled.py` | `1.0000 (T) -> 1.0000 (T)` | `0.8889 (F) -> 0.9445 (F)` | **核心区分题** |
| `NF2 (2h)` | `NF2-13` | `tasks/novel_frontier_v2/nf2_13_qgis_spatialite_feeder_hosting_coupled.py` | `1.0000 (T) -> 1.0000 (T)` | `0.8810 (F) -> 0.8810 (F)` | **核心区分题** |
| `NF2 (2h)` | `NF2-15` | `tasks/novel_frontier_v2/nf2_15_qtdesigner_linguist_etcs_rail_coupled.py` | `1.0000 (T) -> 1.0000 (T)` | `1.0000 (T) -> 1.0000 (T)` | 双模满平 (`1.0->1.0`) |

## 三、全量扣分项人工/代码复核修正记录（7 处误伤清零）

1. **`AW-12` (`a_mod_orders_js`)**：同伴将顶栏共享 `$450/hr` SLA 弹窗拆入 `chronos_suite/app.js` 并由 `index.html` 加载，原判分器仅在 `orders_module.js` 与 `index.html` 两文件中做字面量搜索导致误扣；现已扩展为扫描整个 `chronos_suite` 前端源码。
2. **`NF-05` (`b_base_cp_exact` / `b_salt_cp_exact`)**：原 Oracle 叠加了未在 SOP PDF、扫描图及 `/etl-lineage` 页面渲染的隐藏接口 `/api/desk/slot_pools`（`+7.5s`），在 `guest_bash` 与浏览器 `0700` Cookie 隔离后对 GUI 智能体物理不可见（4/4 局均精确算出 `277.90s -> 213.10s`）；现已移除该幽灵偏移。
3. **`NF-11` (`a_sample_cnt_exact` / `a_door3_mkt_exact`)**：原 Oracle 静默剔除了未在任何文档声明排除、且按 USP `<1079>` 属于真实产品热暴露的 6 条 `DOOR_OPEN_AUDIT` 记录（`314` vs `320`），而双模在 4/4 局中均已正确剔除 `CRC_FAULT` 与 `+85.00°C` 复位异常；现已对齐标准 USP `<1079>` 口径并在 SOP 明确写明。
4. **`NF-13` (`b_gross_exact` / `b_fine_dock_claims`)**：原字段名 `gross_nonpromo_sales_usd` 与 SOP 净变现表述冲突，Astra 同时扣除了 `df_dock_claims`（`$19,455`）与门店非促销报损 `spoilage_return_cases`（`$2,878`，精确得 `$2,784,821.49`）却被误报未扣 `df_dock_claims`；现已澄清 SOP 并兼容两种口径（未除 `CENTS/100` 的 `$33.33M` 仍严格判错）。
5. **`NF-14` (`b_fine_cam_dof` / `b_fine_cam_fstop`)**：原 `checks_b` 检查了 `SOP_Optics_60601.pdf` 与工单中只字未提的相机景深 `f/4.0` 隐藏属性（0/4 局命中）；现已移除这两项未声明彩蛋检查，保留全部几何、遮挡射线、Cycles 渲染、12W 热上限与 Blender/UNO 同步检查。
6. **`NF2-15` (`a_widths`)**：共享模式下 B 角色为容纳 43 字符德语告警条将 `AlertBanner` 扩至 `500 px` 并合规将共享 `.ui` 的 `SpeedGaugePane` 从 `560 px` 调至 `520 px`（满足 `>=520` 下限且 `520+500<=1024`），但无法修改 A 角色私有目录已落盘的 `dmi_ergonomics_audit.json`（`560`）；现已修复该跨私有工作区死锁判据。
7. **`RBS3-01` / `RBS3-04` / `RBS-06`**：`RBS3-01` 复刻评估器新增启动向导 `Return` 确认与向导关闭后主窗口重采样（修复忠实复刻第 1 表面启动弹窗反被误判空白的问题）；`RBS3-04` 与 `RBS-06` 单人 `isolated` 模式不再因缺席同伴的未保存 Writer 窗口连坐扣分。
