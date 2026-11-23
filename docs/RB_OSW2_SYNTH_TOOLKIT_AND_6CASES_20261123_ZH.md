# `rb_osw2_synth_v1` + `paragui_case_factory`：融合 `RecreationBench` 与 `OSWorld-V2` 冲突规律及任务长度的造题工具与 6 项深度基准实测报告（2026-11-23）

## 一、研发背景与核心交付物

基于 `RecreationBench`（7 批 14 款桌面应用并发重现）与 `OSWorld-V2`（`OSW2-P1..P5` 原生 KVM + `qwen-cua-driver 0.27.0` 三臂实测）揭示的真实冲突物理规律与自然任务时长分布，本轮工作完成了 **可复用造题与配对校准工具链（`paragui_case_factory.py`）** 以及全新一批 **6 项高密度双智能体混合桌面任务（`rb_osw2_synth_v1`：`RBS-01..RBS-06`）** 的构建、五门禁校验与双模型（`gpt-6.1-sol` + `gpt-6-astra`）全量实测：

1. **造题与配对校准工具 [`tools/paragui_case_factory.py`](../tools/paragui_case_factory.py)**（同步集成至 `$paragui-case-design` 技能目录 `~/.codex/skills/paragui-case-design/scripts/synthesize_contention_pairs.py`）：
   - **六大实证冲突定律建模（`LAW_1..LAW_6`）**：量化刻画（1）AT-SPI `app=` 语义点击隔离假象与全局 X11 快捷键跨窗误投（`LAW_1`）、（2）同名 `Preferences` 子窗口与模态文件框抢焦（`LAW_2`）、（3）CSD `F10` 失焦自隐 Popover 与 `:99` 候选窗口拉起互扰（`LAW_3`）、（4）单实例 `:9222` CDP 多视口响应式走查 vs 全屏 `1920x1080` 多幕录制冲突（`LAW_4`）、（5）多浮动 `QDockWidget` 工具面板 / Z-order 置顶军备竞赛遮挡 2D 画布拖拽与全局截屏（`LAW_5`）、（6）单窗口多标签 MDI（`DeckCraft` / `WPS`）共享吸管/保存目标及单实例 `soffice.bin` + SQLite 文献库脑裂（`LAW_6`）。
   - **任务长度与双角色重叠度校准引擎**：约束双角色孤立时长对称比 `min(T_a, T_b) / max(T_a, T_b) >= 0.65`、预测并发 GUI 重叠时长 `>= 300s`、细粒度连续评分项 `>= 24–32` 项（含隔离 `Xvfb + AT-SPI2 + qwen-cua-driver` 实机拉起候选 GUI 验证），消除过短微任务导致的提前退场与满分饱和。
   - **上游题库自动挖掘**：对 `RecreationBench` 全部 50 款 Ubuntu 桌面应用完成两两评分，筛出 477 组高对称冲突配对并导出 Top-15 清单 [`lists/recreationbench_mined_top15_v2.json`](../lists/recreationbench_mined_top15_v2.json)（最高分对 `horizon_symmetry_ratio = 1.0`，预测冲突指数 `88.8`）。

2. **全新 6 项深度基准 `rb_osw2_synth_v1`（`RBS-01..RBS-06`，共 176 项细粒度评分检查）**：
   - 静态审计 `audit_case_module.py` 取得 **`8/8 PASS | 0 FAIL | 0 WARN`**，造题工具蓝图审计 [`rb_osw2_synth_v1_factory_blueprint_audit_20261123.json`](results-manifests/rb_osw2_synth_v1_factory_blueprint_audit_20261123.json) **`6/6` 全绿**（对称比 `0.958–0.981`，预测平均并发重叠 `397.8s`），确定性五门禁 [`rb_osw2_synth_v1_5gate_selfval_20261123.json`](results-manifests/rb_osw2_synth_v1_5gate_selfval_20261123.json) **`6/6` 全通过**。
   - 在 **24 局（48 个 Non-YOLO 空气隔离容器智能体，`permission_audit_ok = 48/48`）** 双模型实测中，真实并发重叠率高达 **`75.6%`（`gpt-6.1-sol`，均值 `250.6s`，最高 `445.7s`）** 与 **`83.6%`（`gpt-6-astra`，均值 `341.2s`，最高 `513.1s`）**，跨角色交错切换达 **`364` 次（`Sol`）与 `408` 次（`Astra`）**，精准复现了 `RecreationBench` 与 `OSWorld-V2` 在开放 `GUI + CLI` 下的典型并发规律：**警觉智能体被迫将 CLI 定向校验/窗口控制调用拉高 `1.85x`（`Sol`）与 `1.62x`（`Astra`），输入 Token 膨胀 `1.43x`（最高 `2.35x`），墙钟耗时膨胀 `1.27x`（最高 `1.80x`），窗口焦点翻转由 `87 -> 118`（`Sol`）与 `86 -> 130`（`Astra`），并录得 `6–15` 次并发按键跨窗误投**。

---

## 二、造题工具预测指标 vs 真实集群双模型实测对照

完整实测数据见 [`results-manifests/rb_osw2_synth_v1_sol61_astra_20261123.json`](results-manifests/rb_osw2_synth_v1_sol61_astra_20261123.json)。

### 2.1 双模型宏观指标总表（`RBS-01..RBS-06`，`reasoning_effort = high`）

| 模型 | `isolated` 均分 | `shared` 均分 | 平均并发重叠时长（重叠占比） | 跨角色交错切换总数 | 平均 CLI 核验膨胀比 | 平均输入 Token 膨胀比 | 平均墙钟耗时膨胀比 | 焦点翻转 (`iso -> shr`) | 误路由按键 (`iso -> shr`) | 非 YOLO 权限审计 |
|---|---:|---:|---|---:|---:|---:|---:|---|---|---|
| **`gpt-6.1-sol`** | `0.9611` | `0.9817` | **`250.55s` (`75.6%`)** | **`364` 次** | **`1.851x`** | **`1.431x`** | **`1.270x`** | `87 -> 118` (`1.36x`) | `0 -> 6` | `24/24 PASS` |
| **`gpt-6-astra`** | `0.9611` | `0.9691` | **`341.22s` (`83.6%`)** | **`408` 次** | **`1.623x`** | **`1.245x`** | **`1.151x`** | `86 -> 130` (`1.51x`) | `0 -> 15` | `24/24 PASS` |

### 2.2 逐案例冲突定律、时长重叠与多维代价明细

| Case ID & 对应冲突定律 | 模型 | `Score_iso -> Score_shr` | 并发重叠 / 总耗时 (`overlap_ratio`) | 交错切换 | Token 倍率 (`iso -> shr`) | CLI 调用 (`iso -> shr`) | 焦点翻转 (`iso -> shr`) | 误按键 | 复现的 `RB / OSW2` 物理冲突表征 |
|---|---|---|---|---:|---|---|---|---|---|
| **`RBS-01`** (`LAW_2 + LAW_3`)<br>双同名 `Preferences` 模态框应用复刻 | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 -> 1.000`<br>`1.000 -> 1.000` | **`445.7s / 483.8s (92.1%)`**<br>**`513.1s / 559.4s (91.7%)`** | `109`<br>`109` | `3.07M -> 3.08M (1.01x)`<br>`2.74M ->` **`3.15M (1.15x)`** | `41 ->` **`62 (1.51x)`**<br>`52 ->` **`59 (1.13x)`** | `44 -> 44`<br>`39 -> 42` | `0`<br>`0` | 接近 9 分钟持续高重叠（`>91%`）；`VaultSearch` 与 `LogicGrid` 同名 `Preferences` 迫使智能体加写 `xdotool` 定向脚本核验候选窗 |
| **`RBS-02`** (`LAW_1 + LAW_3`)<br>失焦自隐 `F10` CSD 弹窗 vs 多模态十六进制热键复刻 | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 -> 1.000`<br>`1.000 -> 1.000` | **`276.6s / 400.5s (69.1%)`**<br>**`508.2s / 528.6s (96.1%)`** | `73`<br>**`112`** | `2.53M -> 2.07M (0.82x)`<br>`2.36M ->` **`2.88M (1.22x)`** | `31 -> 33`<br>`34 -> 34` | `15 ->` **`34 (2.27x)`**<br>`15 ->` **`47 (3.13x)`** | `0`<br>`0` | 同伴操作反复打灭 `CadenceReader` 的 `F10/F9` 自隐 `Gtk.Popover`，焦点翻转飙升 **`2.3x–3.1x`**（`Astra` GUI 调用由 `83` 涨至 `102`） |
| **`RBS-03`** (`LAW_5`)<br>5 窗口浮动 `QDockWidget` 凸轮拖拽 vs 红外热像去遮挡抓拍与复刻 | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.860 -> 0.935`<br>`0.860 -> 0.860` | **`169.0s / 251.3s (67.3%)`**<br>**`236.6s / 273.0s (86.7%)`** | `23`<br>`33` | `0.67M ->` **`1.10M (1.63x)`**<br>`0.68M ->` **`1.13M (1.65x)`** | `11 ->` **`24 (2.18x)`**<br>`11 ->` **`21 (1.91x)`** | `4 ->` **`14 (3.50x)`**<br>`5 ->` **`14 (2.80x)`** | `0`<br>`1` | 完美复现 `RB-B5 Pencil2D+ksnip` 规律：4 个浮动面板遮挡热像靶标触发 **`3.5x` 切窗**与 **`+65%` Token** 置顶重拍 |
| **`RBS-04`** (`LAW_4`)<br>单实例 `:9222` `HttpOnly` 3 视口票务 QA vs 8 幕全屏动效录制 | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.955 -> 0.955`<br>`0.955 -> 0.955` | **`168.4s / 295.2s (57.1%)`**<br>**`270.3s / 331.9s (81.4%)`** | `34`<br>`53` | `1.13M ->` **`1.68M (1.49x)`**<br>`2.13M -> 1.78M (0.84x)` | `24 ->` **`31 (1.29x)`**<br>`38 -> 29` | `1 ->` **`3 (3.00x)`**<br>`1 ->` **`3 (3.00x)`** | `0`<br>`0` | 剥离前端静态常量并启用 `HttpOnly` 视口校验后，`Sol` 在 `:9222` 视口争夺下耗时与 Token 同步膨胀 **`+48% / +49%`** |
| **`RBS-05`** (`LAW_6 + LAW_5`)<br>单窗口双标签 `DeckCraft MDI` 黄柄拖拽与共享吸管 | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 -> 1.000`<br>`1.000 -> 1.000` | **`139.9s / 168.6s (83.0%)`**<br>**`175.5s / 235.2s (74.6%)`** | `44`<br>`51` | `0.50M ->` **`1.18M (2.35x)`**<br>`0.55M ->` **`0.83M (1.52x)`** | `4 ->` **`14 (3.50x)`**<br>`4 ->` **`15 (3.75x)`** | `8 -> 8`<br>`8 ->` **`12 (1.50x)`** | **`5`**<br>**`7`** | 对标 `OSW2-P3 WPS MDI`：单窗 `Alt+1/Alt+2` 标签切换与共享吸管引发 **`5–7` 次按键误投**、**`3.5x+` CLI 重验**与 **`2.35x` Token 膨胀** |
| **`RBS-06`** (`LAW_6 + LAW_2`)<br>`CiteVault` SQLite + BibTeX 勘误 + 单进程 `soffice.bin` 荟萃分析 | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.952 -> 1.000`<br>`0.952 -> 1.000` | **`303.7s / 357.9s (84.9%)`**<br>**`343.6s / 485.3s (70.8%)`** | `81`<br>`50` | `2.20M ->` **`2.85M (1.30x)`**<br>`1.92M ->` **`2.13M (1.11x)`** | `36 ->` **`56 (1.56x)`**<br>`33 ->` **`39 (1.18x)`** | `15 -> 15`<br>`18 -> 12` | **`1`**<br>**`7`** | 对标 `OSW2-P8/P9 + P1`：5–6 分钟高强度并发（`81` 次交错），`Astra` 遭遇 **`7` 次按键误投**后经剪贴板与工作簿复核自愈 |

---

## 三、造题工具与新套件使用指南

- **造题与配对校准工具**：[`tools/paragui_case_factory.py`](../tools/paragui_case_factory.py)（技能镜像脚本：`~/.codex/skills/paragui-case-design/scripts/synthesize_contention_pairs.py`）
- **新任务套件与执行器**：[`tasks/rb_osw2_synth_v1/`](../tasks/rb_osw2_synth_v1/)、[`experiments/rb_osw2_synth_v1.py`](../experiments/rb_osw2_synth_v1.py)
- **上游配对挖掘输出**：[`lists/recreationbench_mined_top15_v2.json`](../lists/recreationbench_mined_top15_v2.json)
- **单元测试**：[`tests/test_rb_osw2_synth_v1.py`](../tests/test_rb_osw2_synth_v1.py)

```bash
# 1. 查看 6 大 RB/OSW2 冲突定律与任务时长校准区间
python3 tools/paragui_case_factory.py laws

# 2. 从上游 RecreationBench 50 款 Ubuntu 应用中自动挖掘高对称、强冲突配对
python3 tools/paragui_case_factory.py mine-upstream \
  --rb-jsonl tasks/recreationbench_v1/metadata/ubuntu.jsonl --top-k 15

# 3. 对自定义任务包执行时长对称度、预测并发重叠、细粒度评分项与冲突定律审计
PYTHONPATH=. python3 tools/paragui_case_factory.py audit-suite tasks/rb_osw2_synth_v1

# 4. 一键生成符合 $paragui-case-design 契约的新案例骨架
python3 tools/paragui_case_factory.py scaffold \
  --case-id RBS-07 --title "Custom Multi-Modal Workbench" \
  --laws LAW_1_KEYSTROKE_MISROUTING LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP \
  --out /tmp/rbs07_skeleton.py

# 5. 运行 rb_osw2_synth_v1 五门禁校验与双臂模型实测
PYTHONPATH=. python3 experiments/rb_osw2_synth_v1.py \
  --mode self_validate --workers 6 --code-root . --out /tmp/rbs-selfval
```
