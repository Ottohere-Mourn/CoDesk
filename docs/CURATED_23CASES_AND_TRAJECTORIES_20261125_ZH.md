# 精选 23 项高质量双智能体基准与 184 条全量轨迹交付总览（2026-11-25）

- **机器可读总索引**：[`lists/curated_23cases_and_trajectories_20261125.json`](../lists/curated_23cases_and_trajectories_20261125.json)
- **92 局 / 184 角色全量轨迹目录**：[`trajectories/curated_23cases_20261125/`](../trajectories/curated_23cases_20261125/README.md)
- **双轨制任务构建规范 Skills**：[`.agents/skills/paragui-case-design/`](../.agents/skills/paragui-case-design/SKILL.md)（盲并发共居）与 [`.agents/skills/paragui-collab-case-design/`](../.agents/skills/paragui-collab-case-design/SKILL.md)（明示同伴双向协作）

## 一、整体大盘统计（`gpt-6.1-sol` vs `gpt-6-astra`，`effort = high`）

| 统计切片 | 题数 | `gpt-6.1-sol` `Isolated -> Shared`（严格 `joint_pass`） | `gpt-6-astra` `Isolated -> Shared`（严格 `joint_pass`） | `Shared` 分差 (`Astra - Sol`) |
|---|---:|---|---|---:|
| **1. `Curated-8`**（`EC-01,03` + 6 项优选 `RBS`） | 8 | `0.8533 (37.5%) -> 0.8394 (62.5%)` | `0.9846 (75.0%) -> 0.9081 (62.5%)` | `+0.0687` |
| **2. `AW-v1`**（`2h` 零步数上限复验 5 题） | 5 | `1.0000 (100%) -> 0.9321 (80.0%)` | `0.9778 (100%) -> 0.9639 (80.0%)` | `+0.0318` |
| **3. `NF-v1`**（100% 真软件重构 5 题） | 5 | `0.8835 (40.0%) -> 0.8339 (0.0%)` | `0.9276 (60.0%) -> 0.9017 (60.0%)` | `+0.0678` |
| **4. `NF2`**（`2h` 零步数上限复验 5 题） | 5 | `0.9891 (100%) -> 0.9327 (80.0%)` | `0.9274 (60.0%) -> 0.9000 (60.0%)` | `-0.0327` |
| **全量 23 题合计** | **23** | **`0.9213 (65.2%) -> 0.8786 (56.5%, 13/23)`** | **`0.9583 (73.9%) -> 0.9171 (65.2%, 15/23)`** | **`+0.0385`** |
| **17 题非饱和核心集**（去 6 道双模满平题） | **17** | **`0.8978 (58.8%) -> 0.8358 (41.2%, 7/17)`** | **`0.9464 (70.6%) -> 0.8878 (52.9%, 9/17)`** | **`+0.0520`** |

## 二、23 题源码与轨迹路径逐题索引

| 批次 | Case ID | 源码路径 | 轨迹目录（含 4 局 × 2 角色） | `6.1-sol Shared` | `Astra Shared` |
|---|---|---|---|---:|---:|
| `Curated-8` | `EC-01` | `tasks/exam_contention_v1/ec01_ma_dataroom_calc.py` | `trajectories/curated_23cases_20261125/EC-01/` | `0.5000 (F)` | `1.0000 (T)` |
| `Curated-8` | `EC-03` | `tasks/exam_contention_v1/ec03_enclosure_cad_emi.py` | `trajectories/curated_23cases_20261125/EC-03/` | `0.5000 (F)` | `0.5000 (F)` |
| `Curated-8` | `RBS-06` | `tasks/rb_osw2_synth_v1/rbs06_citevault_bibtex_soffice.py` | `trajectories/curated_23cases_20261125/RBS-06/` | `1.0000 (T)` | `1.0000 (T)` |
| `Curated-8` | `RBS2-06` | `tasks/rb_osw2_synth_v2/rbs2_06_maildesk_ics_vs_calc_contracts.py` | `trajectories/curated_23cases_20261125/RBS2-06/` | `1.0000 (T)` | `1.0000 (T)` |
| `Curated-8` | `RBS3-01` | `tasks/rb_osw2_synth_v3/rbs3_01_zerospoiler_popovers_recreation.py` | `trajectories/curated_23cases_20261125/RBS3-01/` | `0.7150 (F)` | `0.8750 (F)` |
| `Curated-8` | `RBS3-02` | `tasks/rb_osw2_synth_v3/rbs3_02_cdp_live_frames_vs_8scene_sweep.py` | `trajectories/curated_23cases_20261125/RBS3-02/` | `1.0000 (T)` | `1.0000 (T)` |
| `Curated-8` | `RBS3-04` | `tasks/rb_osw2_synth_v3/rbs3_04_icu_sso_nomogram_soffice.py` | `trajectories/curated_23cases_20261125/RBS3-04/` | `1.0000 (T)` | `0.8899 (F)` |
| `Curated-8` | `RBS3-05` | `tasks/rb_osw2_synth_v3/rbs3_05_ircam_firmware_gateway_calc.py` | `trajectories/curated_23cases_20261125/RBS3-05/` | `1.0000 (T)` | `1.0000 (T)` |
| `AW-v1 (2h)` | `AW-12` | `tasks/authentic_workstation_v1/aw12_chromium_zerospoiler_suite_recreation.py` | `trajectories/curated_23cases_20261125/AW-12/` | `1.0000 (T)` | `0.9307 (T)` |
| `AW-v1 (2h)` | `AW-14` | `tasks/authentic_workstation_v1/aw14_gimp_crop_layers_inkscape_poster.py` | `trajectories/curated_23cases_20261125/AW-14/` | `1.0000 (T)` | `1.0000 (T)` |
| `AW-v1 (2h)` | `AW-15` | `tasks/authentic_workstation_v1/aw15_qt_designer_2tab_linguist_10str.py` | `trajectories/curated_23cases_20261125/AW-15/` | `0.7717 (F)` | `1.0000 (T)` |
| `AW-v1 (2h)` | `AW-19` | `tasks/authentic_workstation_v1/aw19_libreoffice_dense_budget_and_redline.py` | `trajectories/curated_23cases_20261125/AW-19/` | `0.8889 (T)` | `0.8889 (F)` |
| `AW-v1 (2h)` | `AW-20` | `tasks/authentic_workstation_v1/aw20_inkscape_gimp_freecad_meddevice_enclosure.py` | `trajectories/curated_23cases_20261125/AW-20/` | `1.0000 (T)` | `1.0000 (T)` |
| `NF-v1` | `NF-01` | `tasks/novel_frontier_v1/nf01_dach_xkb_writer_calc.py` | `trajectories/curated_23cases_20261125/NF-01/` | `0.9183 (F)` | `0.7917 (F)` |
| `NF-v1` | `NF-05` | `tasks/novel_frontier_v1/nf05_broadcastchannel_quant_lineage.py` | `trajectories/curated_23cases_20261125/NF-05/` | `0.9137 (F)` | `0.9137 (F)` |
| `NF-v1` | `NF-11` | `tasks/novel_frontier_v1/nf11_biologics_uno_lims_coldchain.py` | `trajectories/curated_23cases_20261125/NF-11/` | `0.6255 (F)` | `0.9254 (T)` |
| `NF-v1` | `NF-13` | `tasks/novel_frontier_v1/nf13_stateful_kernel_pos_coldstorage.py` | `trajectories/curated_23cases_20261125/NF-13/` | `0.7936 (F)` | `0.9296 (T)` |
| `NF-v1` | `NF-14` | `tasks/novel_frontier_v1/nf14_blender_gui_surgical_trocar_dhf.py` | `trajectories/curated_23cases_20261125/NF-14/` | `0.9185 (F)` | `0.9480 (T)` |
| `NF2 (2h)` | `NF2-05` | `tasks/novel_frontier_v2/nf2_05_qtassistant_arinc429_flight_calc.py` | `trajectories/curated_23cases_20261125/NF2-05/` | `0.9400 (T)` | `0.7400 (F)` |
| `NF2 (2h)` | `NF2-11` | `tasks/novel_frontier_v2/nf2_11_blender_vse_broadcast_nle_ebur128.py` | `trajectories/curated_23cases_20261125/NF2-11/` | `0.7891 (F)` | `1.0000 (T)` |
| `NF2 (2h)` | `NF2-12` | `tasks/novel_frontier_v2/nf2_12_freecad_cubesat_mass_cg_coupled.py` | `trajectories/curated_23cases_20261125/NF2-12/` | `1.0000 (T)` | `0.9445 (T)` |
| `NF2 (2h)` | `NF2-13` | `tasks/novel_frontier_v2/nf2_13_qgis_spatialite_feeder_hosting_coupled.py` | `trajectories/curated_23cases_20261125/NF2-13/` | `1.0000 (T)` | `0.8810 (F)` |
| `NF2 (2h)` | `NF2-15` | `tasks/novel_frontier_v2/nf2_15_qtdesigner_linguist_etcs_rail_coupled.py` | `trajectories/curated_23cases_20261125/NF2-15/` | `0.9345 (T)` | `0.9345 (T)` |
