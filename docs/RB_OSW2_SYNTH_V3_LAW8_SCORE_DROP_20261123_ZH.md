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

---

## 二、`LAW_8` 造题定律升级与第三批高难度套件 `rb_osw2_synth_v3`（`RBS3-01..RBS3-05`）

我们将上述四条根因正式编码进造题工厂 [`tools/paragui_case_factory.py`](../tools/paragui_case_factory.py)（镜像同步至 `~/.codex/skills/paragui-case-design/scripts/synthesize_contention_pairs.py`）的第八条定律 **`LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING`** 与 **`non_saturated_coupled_contention`** 校准带（`40` 项子检查/题、`max_cua_calls = 42`、`conc_role_timeout_s = 1080s`），全新构建并通过五门禁验证了 5 项高对抗基准 **`tasks/rb_osw2_synth_v3`（`RBS3-01..RBS3-05`，合计 `200` 项子检查）**：

- **静态审计**：`audit_case_module.py` **`7/7 PASS | 0 FAIL | 0 WARN`**（零阉割 CLI、零休眠注水、零在线判题、零首交锁）。
- **工厂蓝图审计**（[`rb_osw2_synth_v3_factory_blueprint_audit_20261123.json`](results-manifests/rb_osw2_synth_v3_factory_blueprint_audit_20261123.json)）：**`5/5` 全绿，全部 5 题预测冲突指数均达满分 `100.0`**。
- **确定性五门禁**（[`rb_osw2_synth_v3_5gate_selfval_20261123.json`](results-manifests/rb_osw2_synth_v3_5gate_selfval_20261123.json)）：**`5/5` 全通过**（`Gate 1 = 0.000–0.148`，`Gate 2 seq_ab = 1.000`，`Gate 3 seq_ba = 1.000`，`Gate 4 contention = 0.741–0.873`，`Gate 5 careful_conc = 1.000` 且仅耗时 `0.16s–25.37s`）。

---

## 三、`rb_osw2_synth_v3` 双模型 20 局（40 智能体）实测：成功复现真实 `Shared` 掉分！

完整成绩单见 [`results-manifests/rb_osw2_synth_v3_sol61_astra_20261123.json`](results-manifests/rb_osw2_synth_v3_sol61_astra_20261123.json)，原始运行轨迹与权限审计归档于 `cpu15:/home/yuke/data/paraGUI/runs/rbs3_eval_20261123/`。

### 3.1 `v2` vs `v3` 双模型宏观对比总表

| 套件版本与模型 | `isolated` 均分 | `shared` 均分 | **`ΔScore (shr - iso)`** | 平均并发重叠（活跃重叠率） | 平均墙钟膨胀比 | 平均 CLI 膨胀比 | 焦点翻转 (`iso -> shr`) | 误按键 | 非 YOLO 审计 |
|---|---:|---:|---:|---|---:|---:|---|---|---|
| `v2` · `gpt-6.1-sol` | `0.9633` | `0.9633` | `0.0000` | `456.0s` (`92.5%`) | `0.981x` | `1.522x` | `76 -> 113` | `12` | `24/24 PASS` |
| **`v3` · `gpt-6.1-sol`** | **`0.9749`** | **`0.9066`** | **`-0.0683 (-6.83%)`** | **`517.4s` (`93.1%`)** | **`1.299x`** | **`1.758x`** | `62 -> 72` | `8` | `20/20 PASS` |
| `v2` · `gpt-6-astra` | `0.9633` | `0.9596` | `-0.0037` | `241.4s` (`90.5%`) | `0.971x` | `1.346x` | `74 -> 91` | `11` | `24/24 PASS` |
| **`v3` · `gpt-6-astra`** | **`0.9799`** | **`0.9630`** | **`-0.0169 (-1.69%)`** | **`349.3s` (`93.7%`)** | **`1.198x`** | **`2.096x`** | **`58 -> 84`** | `7` | `20/20 PASS` |

### 3.2 `rb_osw2_synth_v3` 逐案例双模型实测与失分机制拆解

| Case ID（40 项/题）& `LAW_8` 硬化设计 | 模型 | `Score_iso -> Score_shr`（`ΔScore`） | 并发重叠 / 总耗时（活跃重叠率） | 切换次数 | GUI 调用 (`iso->shr`) | CLI 调用 (`iso->shr`) | 焦点翻转 (`iso->shr`) | 误按键 | 真实轨迹捕获的失分与冲突机理 |
|---|---|---|---|---:|---|---|---|---|---|
| **`RBS3-01`**<br>零剧透 5 表面深度复刻（启动向导 + `QPainter` 6 段柱图 + 失焦自隐 `F10 QMenu` + 三标签双 `Preferences` + 双 `About`） | `gpt-6.1-sol`<br>`gpt-6-astra` | **`0.900 -> 0.690` (`-0.2100`)**<br>`0.925 -> 0.925` (`0.0000`) | **`658.6s / 1081.5s` (`95.4%`)**<br>**`621.1s / 694.5s` (`97.3%`)** | `73`<br>**`108`** | `80 -> 54`<br>`82 -> 66` | `67 -> 64`<br>`38 ->` **`69 (1.82x)`** | `30 -> 28`<br>`26 ->` **`37`** | `0`<br>`0` | **复现 `KSudoku` 级大幅掉分（`-21.0%`，Role B `0.85 -> 0.53`）**：零剧透下双启动向导、失焦自灭 `F10` 菜单与双 `Preferences` 反复抢焦，耗尽 `Sol` 预算致候选窗漏实现模式与校准页；`Astra` 靠 **`1.82x` CLI** 与 `+21%` Token 勉强守平 |
| **`RBS3-02`**<br>单实例 `:9222` 4 断点像素级色带截屏 QA vs 8 幕 `0.6s` 全屏可见性扫描录制 | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 -> 1.000` (`0.0000`)<br>`1.000 -> 1.000` (`0.0000`) | `358.4s / 696.5s` (`88.8%`)<br>`163.1s / 196.0s` (`91.5%`) | `32`<br>`37` | `42 -> 19`<br>`49 -> 20` | `30 -> 28`<br>`23 -> 26` | `5 -> 6`<br>`3 ->` **`10 (3.33x)`** | `0`<br>`0` | `Astra` 遭遇 **`3.33x` 焦点翻转**与 `SWEEP_ABORTED` 重试后通过重扫全部 8 幕恢复满分 |
| **`RBS3-03`**<br>单实例可变画布 `VectorForge MEP Studio`（`Alt+1/Alt+2` 双层拖拽 + 全局 `MM/IN` + `[636,644]mm` 双向净空耦合） | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 -> 1.000` (`0.0000`)<br>`1.000 -> 1.000` (`0.0000`) | **`448.1s / 582.2s` (`91.2%`)**<br>`212.9s / 232.4s` (`93.0%`) | `41`<br>`62` | `53 -> 37`<br>`53 -> 44` | `6 ->` **`20 (3.33x)`**<br>`6 ->` **`25 (4.17x)`** | `4 -> 4`<br>`4 -> 4` | **`4`**<br>**`3`** | 单实例双标签画布互切触发 **`3–4` 次误按键**与初始 `626mm` 耦合越界，迫使两模型将 CLI 核验拉高 **`3.33x` 与 `4.17x`**、Token 暴涨 **`+40% / +81%`** |
| **`RBS3-04`**<br>无 CDP `ICU` 互斥单位门户 + `QPainter` 16 床室速报警 + 单实例 `Calc+Writer` `[1900,1908]mL` 液体耦合 | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.975 -> 1.000` (`+0.0254`)<br>**`0.975 -> 0.890` (`-0.0847`)** | **`623.7s / 844.1s` (`95.7%`)**<br>**`565.6s / 675.6s` (`96.9%`)** | `60`<br>**`85`** | `39 -> 41`<br>`44 ->` **`60`** | `30 ->` **`47 (1.57x)`**<br>`34 ->` **`56 (1.65x)`** | `17 -> 22`<br>`19 -> 23` | `0`<br>`0` | **关闭 `:9222` 后门立竿见影**：`Astra` 在 `85` 次交错切换与 `VASOPRESSOR_CONV / VENT_RENAL_SI` 互抢中发生工作簿覆盖（`Vaso_Orders` 12 床有效剂量被冲回 `0`，**Role A `0.949 -> 0.780` 暴跌 `-17.0%`**），同时耗费 **`1.80x` Token（`3.23M`）** |
| **`RBS3-05`**<br>无 CDP 硬件合规门户 + `QPainter` 8 区红外热像 + 实况 `:19515` CAN-FD 守护进程 + `Calc` `[190.0,190.8]W` 功耗耦合 | `gpt-6.1-sol`<br>`gpt-6-astra` | **`1.000 (T) -> 0.843 (F)` (`-0.1568`)**<br>`1.000 (T) -> 1.000 (T)` (`0.0000`) | **`498.1s / 1082.4s` (`94.4%`)**<br>`184.0s / 483.9s` (`89.6%`) | `56`<br>`42` | `38 ->` **`53`**<br>`40 -> 42` | `20 ->` **`40 (2.00x)`**<br>`18 ->` **`31 (1.72x)`** | `6 ->` **`12 (2.00x)`**<br>`6 ->` **`10`** | **`4`**<br>**`4`** | **`Sol` 联合通过由 `True` 跌为 `False`（`-15.7%`）**：`VRM_THERMAL_SPEC` 与 `CAN_FD_VECTOR_SPEC` 反复互切（`4` 次误按键、CLI 翻倍 `20->40`、耗时翻倍 `518s->1082s`），耗尽窗口致 `Thermal_Report.pdf` 未能导出；`Astra` 耗时亦膨胀 **`1.81x`** |

---

## 四、复现入口

- **任务套件与执行器**：[`tasks/rb_osw2_synth_v3/`](../tasks/rb_osw2_synth_v3/)、[`experiments/rb_osw2_synth_v3.py`](../experiments/rb_osw2_synth_v3.py)
- **单元测试**：[`tests/test_rb_osw2_synth_v3.py`](../tests/test_rb_osw2_synth_v3.py)
- **结构化成绩单**：[`rb_osw2_synth_v3_factory_blueprint_audit_20261123.json`](results-manifests/rb_osw2_synth_v3_factory_blueprint_audit_20261123.json)、[`rb_osw2_synth_v3_5gate_selfval_20261123.json`](results-manifests/rb_osw2_synth_v3_5gate_selfval_20261123.json)、[`rb_osw2_synth_v3_sol61_astra_20261123.json`](results-manifests/rb_osw2_synth_v3_sol61_astra_20261123.json)
