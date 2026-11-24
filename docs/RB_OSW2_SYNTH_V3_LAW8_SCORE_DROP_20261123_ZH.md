# 为什么 `v1/v2` 在 `Shared` 下少掉分？根因轨迹复盘、`LAW_8` 定律升级与 `rb_osw2_synth_v3` 双模型实测掉分验证（2026-11-23）

## 一、核心问题复盘：为什么 `rb_osw2_synth_v2` 并发开销大涨但 `Score_shared` 几乎持平？

在 `rb_osw2_synth_v2`（`RBS2-01..06`）中，尽管 `LAW_7`（`QPainter` 纯视觉画布）把单局平均 GUI 调用拉升到了 `61.8–68.0` 次、CLI 核验膨胀了 `1.35x–1.52x`、焦点翻转从 `76` 次涨到 `113` 次，但双模型 `isolated -> shared` 均分仅从 `0.9633` 变为 `0.9633`（`Sol`）与 `0.9596`（`Astra`）。逐条回放 `cpu15` 上的真实 `actions.jsonl` 轨迹并与掉分显著的 `OSWorld-V2`（`OSW2-P5`: `0.939 -> 0.000`）、`RecreationBench`（`KSudoku -42.3%`）及 `exam_contention_v2`（`EC2-C01/C06/C07/C08`: 联合通过率 `80% -> 40%`）逐项对照后，定位到 **四项精确的物理根因**：

1. **题面“清单式剧透” + 过宽的步数/时间缓冲垫（`65` 步 CUA、`1680s` 超时）把“失分”吸收成了“重试成本”**：
   - 真实 `RecreationBench` 题面从不剧透二级菜单项或隐藏标签页名称（单角色 `isolated` 仅 `24.84%`），`OSWorld-V2` 则限制 `40` 步 CUA 与 `720s` 超时（`isolated = 0.7230`）。而 `RBS2` 在 `task.md` 中列出了待采集字段清单，且实际单角色仅需 `400s–850s` 却给了 `1680s` 与 `65` 次 CUA 预算；智能体遇到切焦后知道自己缺哪项数据，直接多跑 `1.5x–2.6x` 的 `wmctrl -a` + CLI 脚本把漏项补齐（`isolated` 基线高达 `0.9633` 接近天花板）。
2. **Track 2 Web 门户开启了 `--remote-debugging-port=9222`，使 `HttpOnly` 视图切换被后台静默旁路**：
   - 在 `RBS2-05/06` 的轨迹中，智能体在 `guest_bash` 内直接通过 `:9222` WebSocket 调用 `fetch('/api/.../copy_seal')`，或利用 `qwen-cua-driver` 的 AT-SPI 后台语义点击在不切走 `Calc` 窗口焦点的情况下拷走各自独立的签章；反观 `EC2-C06/C07` 使用无 `:9222` 端口的 `studio_ui` Chromium，且双角色共用同一个服务端互斥 `VIEW`（切换视图会直接把同伴的 `~/Downloads/*.csv` 单位和剪贴板签章覆盖掉）。
3. **“一次性只读采样（Read-Once, Write-Offline）”缺少实时像素取证或共享可变画布**：
   - `RBS2-01..04` 的参考 GUI 虽为 `QPainter` 画布，但全部是只读且跨进程独立的：智能体只要在几百秒内抓到一帧无遮挡截图，后续全部在本地离线写代码/JSON，同伴后续任何操作都不会破坏已落盘产物；而 `OSW2-P5` / `EC2-C01` 强制校验实时视口截图尺寸与全屏扫描帧，`OSW2-P3/P4` 则在**同一个单实例可变画布进程**内双角色共改图层。
4. **跨角色耦合包络过宽（解耦化）**：
   - 在 `RBS2-06` 中，`Grant_Utilization_Ratio` 容差带设为 `[0.840, 0.885]`（宽达 `4.5%`），使得单方取值无论同伴是否更新共享表都能落入区间；而真正能暴露并发陈旧快照写回冲突的设计需要像 `EC2-C06/C07` 一样采用 **`v0` 越界 + 双角色对称调节杆 + 窄耦合窗口（`±0.4%`）**。
5. **第五项根因（启动期人工“左右/三格分屏”反模式）及全量清除**：
   - 复盘发现前序脚本 `exam_contention_v1.py` 在启动阶段硬编码了 `--window-position=0,0 --window-size=955,1050` 与 `wmctrl -e 0,960,0,958,1050` 左右对半平铺，该坏脚手架被继承进了 `ExamV2Desktop` 与多道任务中，等于在后台替并发智能体预开了平铺窗口管理器、人为消除了视觉遮挡与坐标点击拦截。
   - 现已彻底移除 `exam_contention_v1`、`exam_contention_v2`、`rb_osw2_synth_v1..v3` 共 **26 个文件** 中的启动期硬编码分屏坐标（仅保留可选 `custom_geom` / `window_pos=None` / `ALLOW_CUSTOM_WINDOW_LAYOUT = True` 供未来特殊场景显式按需开启），由 Openbox 居中策略自然叠放窗口（如 `LibreOffice` `1920×1061`、`Chromium` `1220×860`、原生 `Qt` `920×560` 自然居中叠压），并在 `$paragui-case-design` 与 `audit_case_module.py` 中新增 `[RIGID_SPLIT_SCREEN]` 静态拦截规则（全量 38 个文件审计 `0 FAIL | 0 WARN`，`v1 + v2 + v3` 共 17 题 85 局五门禁全绿）。

---

## 二、`LAW_8` 造题定律升级与第三批高难度套件 `rb_osw2_synth_v3`（`RBS3-01..RBS3-05`）

我们将上述四条根因正式编码进造题工厂 [`tools/paragui_case_factory.py`](../tools/paragui_case_factory.py)（镜像同步至 `~/.codex/skills/paragui-case-design/scripts/synthesize_contention_pairs.py`）的第八条定律 **`LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING`** 与 **`non_saturated_coupled_contention`** 校准带（`40` 项子检查/题、`max_cua_calls = 42`、`conc_role_timeout_s = 1080s`），全新构建并通过五门禁验证了 5 项高对抗基准 **`tasks/rb_osw2_synth_v3`（`RBS3-01..RBS3-05`，合计 `200` 项子检查）**：

- **静态审计**：`audit_case_module.py` **`7/7 PASS | 0 FAIL | 0 WARN`**（零阉割 CLI、零休眠注水、零在线判题、零首交锁）。
- **工厂蓝图审计**（[`rb_osw2_synth_v3_factory_blueprint_audit_20261123.json`](results-manifests/rb_osw2_synth_v3_factory_blueprint_audit_20261123.json)）：**`5/5` 全绿，全部 5 题预测冲突指数均达满分 `100.0`**。
- **确定性五门禁**（[`rb_osw2_synth_v3_5gate_selfval_20261123.json`](results-manifests/rb_osw2_synth_v3_5gate_selfval_20261123.json)）：**`5/5` 全通过**（`Gate 1 = 0.000–0.148`，`Gate 2 seq_ab = 1.000`，`Gate 3 seq_ba = 1.000`，`Gate 4 contention = 0.741–0.873`，`Gate 5 careful_conc = 1.000` 且仅耗时 `0.16s–25.37s`）。

---

## 三、去分屏自然窗口叠放（Natural WM Placement）下 `rb_osw2_synth_v3` 双模型 20 局实测

完整成绩单见 [`results-manifests/rb_osw2_synth_v3_sol61_astra_20261123.json`](results-manifests/rb_osw2_synth_v3_sol61_astra_20261123.json)，原始运行轨迹与权限审计归档于 `cpu15:/home/yuke/data/paraGUI/runs/rbs3_natwm_eval_20261124/`。

### 3.1 `v2` vs `v3`（零分屏自然叠放）双模型宏观对比总表

| 套件版本与模型 | `isolated` 均分 | `shared` 均分 | **`ΔScore (shr - iso)`** | 平均并发重叠（活跃重叠率） | 平均墙钟膨胀比 | 平均 CLI 膨胀比 | 焦点翻转 (`iso -> shr`) | 误按键 | 非 YOLO 审计 |
|---|---:|---:|---:|---|---:|---:|---|---|---|
| `v2` · `gpt-6.1-sol` | `0.9633` | `0.9633` | `0.0000` | `456.0s` (`92.5%`) | `0.981x` | `1.522x` | `76 -> 113` | `12` | `24/24 PASS` |
| **`v3`（自然叠放）· `gpt-6.1-sol`** | **`0.9799`** | **`0.9430`** | **`-0.0369 (-3.69%)`** | **`329.1s` (`92.6%`)** | **`1.596x`** | **`1.759x`** | **`72 -> 86`** | `4` | `20/20 PASS` |
| `v2` · `gpt-6-astra` | `0.9633` | `0.9596` | `-0.0037` | `241.4s` (`90.5%`) | `0.971x` | `1.346x` | `74 -> 91` | `11` | `24/24 PASS` |
| **`v3`（自然叠放）· `gpt-6-astra`** | **`0.9849` (`80%` 通)** | **`0.9530` (`60%` 通)** | **`-0.0319 (-3.19%)`** | **`335.5s` (`92.2%`)** | **`1.057x`** | **`1.655x`** | **`83 -> 98`** | **`12`** | `20/20 PASS` |

### 3.2 `rb_osw2_synth_v3`（零分屏自然叠放）逐案例双模型实测与失分机制拆解

| Case ID（40 项/题）& `LAW_8` 硬化设计 | 模型 | `Score_iso -> Score_shr`（`ΔScore`） | 并发重叠 / 总耗时（活跃重叠率） | 切换次数 | GUI 调用 (`iso->shr`) | CLI 调用 (`iso->shr`) | 焦点翻转 (`iso->shr`) | 误按键 | 真实轨迹捕获的失分与冲突机理 |
|---|---|---|---|---:|---|---|---|---|---|
| **`RBS3-01`**<br>零剧透 5 表面深度复刻（双窗自然居中叠压 + 失焦自灭 `F10 QMenu` + 三标签双 `Preferences`） | `gpt-6.1-sol`<br>`gpt-6-astra` | **`0.925 (F) -> 0.715 (F)` (`-0.2100`)**<br>**`0.950 (T) -> 0.875 (F)` (`-0.0750`)** | **`504.0s / 1081.5s` (`96.1%`)**<br>**`614.5s / 637.4s` (`97.1%`)** | `86`<br>**`103`** | `79 -> 56`<br>`83 -> 54` | `86 -> 72`<br>`84 -> 79` | `35 -> 31`<br>`36 -> 35` | `0`<br>`0` | **去掉偏移坐标让两窗自然正中叠压后，双模型同步掉分**：`Sol` Role B 由 `0.85` 暴跌至 `0.43`（`-42.0%`）；`Astra` 此前带偏移时 `0.925->0.925` 不掉分，自然叠压后 **`0.950 (T) -> 0.875 (F)` 直接击穿 `joint_pass`** |
| **`RBS3-02`**<br>单实例 `:9222` 4 断点像素级色带截屏 QA vs 8 幕 `0.6s` 全屏可见性扫描录制 | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 (T) -> 1.000 (T)` (`0.0000`)<br>`1.000 (T) -> 1.000 (T)` (`0.0000`) | `165.0s / 371.7s` (`90.8%`)<br>`159.1s / 191.8s` (`87.2%`) | `29`<br>`34` | `19 -> 17`<br>`51 -> 22` | `22 ->` **`28 (1.27x)`**<br>`24 -> 18` | `3 -> 4`<br>`2 ->` **`5 (2.50x)`** | `0`<br>`0` | `Sol` 墙钟耗时膨胀 **`1.71x`**（`217.9s -> 371.7s`），`Astra` 焦点翻转 `2 -> 5` |
| **`RBS3-03`**<br>单实例可变画布 `VectorForge MEP`（`Alt+1/Alt+2` 双层拖拽 + `[636,644]mm` 净空耦合） | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 (T) -> 1.000 (T)` (`0.0000`)<br>`1.000 (T) -> 1.000 (T)` (`0.0000`) | `124.8s / 222.2s` (`87.0%`)<br>`158.9s / 354.8s` (`88.1%`) | `36`<br>`40` | `51 -> 31`<br>`53 -> 47` | `6 ->` **`17 (2.83x)`**<br>`6 ->` **`20 (3.33x)`** | `4 -> 6`<br>`4 -> 4` | **`3`**<br>**`10`** | 单窗双标签互切引发 **`10` 次跨标签误按键（`Astra`）**，耗时膨胀 **`1.68x`**，CLI 核验拉高 **`2.83x–3.33x`** |
| **`RBS3-04`**<br>无 CDP `ICU` 互斥单位门户 + 16 床室速画布 + 全尺寸叠放 `Calc+Writer` `[1900,1908]mL` 耦合 | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.975 (F) -> 1.000 (T)` (`+0.0254`)<br>**`0.975 (F) -> 0.890 (F)` (`-0.0847`)** | **`627.9s / 693.0s` (`96.9%`)**<br>**`404.1s / 504.4s` (`93.7%`)** | **`94`**<br>`62` | `42 -> 48`<br>`44 -> 47` | `39 ->` **`82 (2.10x)`**<br>`33 ->` **`49 (1.48x)`** | `18 ->` **`28`**<br>`27 ->` **`30`** | `0`<br>`0` | 全尺寸 `Calc/Writer (1920×1061)` 自然盖住 `Chromium` 与 `BedsideWave`：`Astra` Role A 暴跌 `-17.0%`（`0.949 -> 0.780`）；`Sol` 输入 Token 暴涨 **`2.20x`（`1.92M -> 4.22M`）**、耗时 **`2.10x`**、CLI **`2.10x`** |
| **`RBS3-05`**<br>无 CDP 硬件合规门户 + 8 区红外热像 + `:19515` CAN-FD 守护进程 + 全尺寸叠放 `Calc` `[190.0,190.8]W` 耦合 | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 (T) -> 1.000 (T)` (`0.0000`)<br>`1.000 (T) -> 1.000 (T)` (`0.0000`) | `223.8s / 373.4s` (`92.1%`)<br>`340.6s / 421.6s` (`94.7%`) | `46`<br>`64` | `31 ->` **`40`**<br>`37 ->` **`43`** | `24 ->` **`42 (1.75x)`**<br>`26 ->` **`46 (1.77x)`** | `12 ->` **`17`**<br>`14 ->` **`24`** | **`1`**<br>**`2`** | 自然叠放迫使两模型高频切窗（`flips` `12->17` / `14->24`），输入 Token 暴涨 **`1.92x`（`Sol`）与 `1.61x`（`Astra`）**，耗时膨胀 **`1.52x / 1.46x`** |

---

## 四、复现入口

- **任务套件与执行器**：[`tasks/rb_osw2_synth_v3/`](../tasks/rb_osw2_synth_v3/)、[`experiments/rb_osw2_synth_v3.py`](../experiments/rb_osw2_synth_v3.py)
- **单元测试**：[`tests/test_rb_osw2_synth_v3.py`](../tests/test_rb_osw2_synth_v3.py)
- **结构化成绩单**：[`rb_osw2_synth_v3_factory_blueprint_audit_20261123.json`](results-manifests/rb_osw2_synth_v3_factory_blueprint_audit_20261123.json)、[`rb_osw2_synth_v3_5gate_selfval_20261123.json`](results-manifests/rb_osw2_synth_v3_5gate_selfval_20261123.json)、[`rb_osw2_synth_v3_sol61_astra_20261123.json`](results-manifests/rb_osw2_synth_v3_sol61_astra_20261123.json)
