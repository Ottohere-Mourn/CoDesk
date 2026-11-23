# `rb_osw2_synth_v2`（第二批 `RBS2-01..RBS2-06`）：升级 `LAW_7` 纯视觉画布防旁路定律与 234 项高粒度评分基准双模型实测报告（2026-11-23）

## 一、研发背景与第二批核心升级

在第一批 [`rb_osw2_synth_v1`（`RBS-01..RBS-06`）](RB_OSW2_SYNTH_TOOLKIT_AND_6CASES_20261123_ZH.md) 验证了 `RecreationBench` 与 `OSWorld-V2` 六大冲突定律（`LAW_1..LAW_6`）的基础上，我们进一步针对第一批实测中观察到的两项深层规律升级了造题工厂 [`tools/paragui_case_factory.py`](../tools/paragui_case_factory.py)（同步镜像至 `~/.codex/skills/paragui-case-design/scripts/synthesize_contention_pairs.py`），并面向 `OSWorld-V2`（`P7, P10, P11, P14, P15`）与 `RecreationBench`（`B10..B13`）尚未覆盖的真实工程场景，全新制造并实测了第二批 **6 项高密度双智能体混合桌面任务 `tasks/rb_osw2_synth_v2`（`RBS2-01..RBS2-06`）**：

1. **新增第七条冲突与防旁路定律 `LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI`（AT-SPI 不透明纯视觉 2D 画布）**：
   - 在开放完整 `qwen-cua-driver 0.27.0 + guest_bash` 的前提下，若参考应用将关键数值直接写入标准按钮或标签文本，智能体仅需 1–2 次无障碍树读取即可退场。`LAW_7` 要求把核心几何、波形、热力图或五线谱状态严格绘制在自定义 `QPainter` / 2D 画布图元中（如 `CutForge NLE` 视频遮幅与品红危险框、`TreeStat` 8 块矩形树图、`GeoCurve` 旋转体轮廓绿点与橙色控制柄、`FlowForge BPMN` 死锁网关节点、`GateSim` 8 周期四通道逻辑波形示波器、`MailDesk` 房间维护拉闸热力图），使真实 GUI 观察、跨帧步进与拖拽交互成为不可替代的必经路径。
   - 实测显示，`rb_osw2_synth_v2` 单局平均 GUI 调用数提升至 **`68.0` 次（`gpt-6.1-sol isolated`）与 `61.8` 次（`gpt-6-astra isolated`）**，单局最低 `27` 次、最高 **`115` 次**，彻底消除了“低 GUI 调用早退”现象。
2. **新增 `high_granularity_visual_recreation` 高粒度校准带（每题 `38–40` 项，全套共 `234` 项连续部分得分检查）**：
   - 将单题连续评分细粒度由第一批的 `28–32` 项提升至 **`38–40` 项（6 题合计 `234` 项）**，融合程序化输出检验、隔离 `Xvfb + AT-SPI2 + qwen-cua-driver` 实机拉起候选 GUI 行为探针（`evaluate_recreated_gui_app` + `run_cli_probe_json`）、像素/波形/SVG 几何核验与跨角色不变量校验，使模型基线落在高区分度的 `0.89–1.00` 非饱和区间（`isolated` 联合通过率 `66.7%–83.3%`）。
3. **静态审计、蓝图审计与确定性五门禁全绿**：
   - 静态审计 `audit_case_module.py`：**`8/8 PASS | 0 FAIL | 0 WARN`**（含 `tasks/rb_osw2_synth_v2/` 全部 7 个模块与 `experiments/rb_osw2_synth_v2.py`）。
   - 造题工厂蓝图审计 [`rb_osw2_synth_v2_factory_blueprint_audit_20261123.json`](results-manifests/rb_osw2_synth_v2_factory_blueprint_audit_20261123.json)：**`6/6` 全绿**，双角色时长对称比 **`0.963–1.000`**，预测冲突指数均值 **`89.24`**，预测并发重叠均值 **`419.9s`**。
   - 确定性五门禁 [`rb_osw2_synth_v2_5gate_selfval_20261123.json`](results-manifests/rb_osw2_synth_v2_5gate_selfval_20261123.json)：**`6/6` 全通过**（`Gate 1 pristine = 0.000–0.174`，`Gate 2 seq_ab = 1.000`，`Gate 3 seq_ba = 1.000`，`Gate 4 contention = 0.780–0.935`，`Gate 5 careful_conc = 1.000` 且耗时仅 `0.17s–15.17s`，远低于 `55%` 超时上限）。

---

## 二、24 局（48 智能体）双模型集群实测结果与冲突规律验证

完整机器可读成绩单见 [`results-manifests/rb_osw2_synth_v2_sol61_astra_20261123.json`](results-manifests/rb_osw2_synth_v2_sol61_astra_20261123.json)，原始运行产物与权限审计归档于 `cpu15:/home/yuke/data/paraGUI/runs/rbs2_eval_20261123/`。

### 2.1 双模型宏观指标总表（`RBS2-01..RBS2-06`，`reasoning_effort = high`，共 234 项子检查）

| 模型 | `isolated` 均分（联合通过率） | `shared` 均分（联合通过率） | 平均 GUI 调用 (`iso -> shr`) | 平均并发重叠时长（全局占比 / 短角色活跃重叠率） | 跨角色交错切换总数 | 平均 CLI 核验膨胀比 | 焦点翻转总数 (`iso -> shr`) | 误路由按键 (`iso -> shr`) | 非 YOLO 权限审计 |
|---|---|---|---|---|---:|---:|---|---|---|
| **`gpt-6.1-sol`** | `0.9633` (**`83.3%`**) | `0.9633` (**`66.7%`**, **`-16.7%`**) | **`68.0 -> 54.5`** | **`455.97s`** (`64.2%` / **`92.5%`**) | **`351` 次** | **`1.522x`** | **`76 -> 113` (`1.49x`)** | `0 ->` **`12`** | `24/24 PASS` |
| **`gpt-6-astra`** | `0.9633` (`66.7%`) | **`0.9596`** (`66.7%`, `-0.0037`) | **`61.8 -> 55.0`** | **`241.40s`** (`62.6%` / **`90.5%`**) | **`283` 次** | **`1.346x`** | **`74 -> 91` (`1.23x`)** | `0 ->` **`11`** | `24/24 PASS` |

### 2.2 逐案例设计锚点、时长重叠与并发物理冲突明细

| Case ID（子检查数）& 对标原型 | 模型 | `Score_iso (Pass) -> Score_shr (Pass)` | 并发重叠 / 总耗时（活跃重叠率） | 交错切换 | GUI 调用 (`iso -> shr`) | CLI 调用 (`iso -> shr`) | 焦点翻转 (`iso -> shr`) | 误按键 | 实测捕获的 `RB / OSW2` 并发冲突机理 |
|---|---|---|---|---:|---|---|---|---|---|
| **`RBS2-01`（38 项）**<br>`OSW2-P10/P11` `CutForge NLE` 视频遮幅打码 vs `ScoreCanvas` 8 小节五线谱听写<br>(`LAW_7 + LAW_1 + LAW_5`) | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.980 (T) -> 0.980 (T)`<br>`0.980 (T) -> 0.980 (T)` | **`330.8s / 534.6s` (`89.1%`)**<br>`147.2s / 322.8s` (`87.7%`) | `44`<br>`35` | `39 -> 39`<br>`36 -> 40` | `10 ->` **`22 (2.20x)`**<br>`12 ->` **`20 (1.67x)`** | `3 ->` **`13 (4.33x)`**<br>`1 ->` **`9 (9.00x)`** | `0`<br>`0` | 两款应用均绑定数字键 `1/2/3` 与 `Space`；并发下窗口焦点翻转激增 **`4.3x–9.0x`**，两模型输入 Token 同步上涨 **`+30% / +29%`**，CLI 定向核验翻倍（**`2.20x / 1.67x`**） |
| **`RBS2-02`（40 项）**<br>`RB-B10/B12` 双启动向导 + 双同名 `Preferences`：`TreeStat` 树图 vs `VaultSafe` 密码箱复刻<br>(`LAW_7 + LAW_2 + LAW_3`) | `gpt-6.1-sol`<br>`gpt-6-astra` | **`0.915 (T) -> 0.890 (F)`**<br>`0.890 (F) -> 0.890 (F)` | **`731.0s / 1031.5s` (`93.6%`)**<br>**`384.6s / 502.7s` (`95.9%`)** | **`105`**<br>**`76`** | **`115 -> 94`**<br>**`94 -> 79`** | `14 ->` **`37 (2.64x)`**<br>`17 ->` **`34 (2.00x)`** | `28 ->` **`36`**<br>`30 ->` **`36`** | `0`<br>`0` | **创下 `12.2` 分钟（`731.0s`）超长高密度并发重叠与 `105` 次切换**；双模态向导与同名 `Preferences` 互相抢占导致 `gpt-6.1-sol` 的 `VaultSafe` 角色得分由 `0.88` 跌至 `0.83`（**触发 `joint_pass: True -> False` 实测退化**），CLI 核验暴涨 **`2.64x`** |
| **`RBS2-03`（38 项）**<br>`OSW2-P15 + RB-B11` `GeoCurve` 5 控制柄旋转体拟合 vs `:9222` 响应式技术博客主题复刻<br>(`LAW_7 + LAW_5 + LAW_4`) | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 (T) -> 1.000 (T)`<br>`1.000 (T) -> 1.000 (T)` | **`359.4s / 582.2s` (`91.9%`)**<br>`208.1s / 280.8s` (`92.7%`) | `36`<br>`42` | `27 -> 29`<br>`60 -> 42` | `21 -> 20`<br>`19 -> 13` | `4 -> 5`<br>`8 -> 7` | **`2`**<br>**`7`** | `:9222` Chromium 覆盖 `GeoCurve` 旋转曲面画布并在暗色切换热键 `Ctrl+J` / 导出 `Ctrl+E` 间产生 **`2–7` 次跨窗按键误投**；`Sol` 墙钟耗时由 `423.8s` 拉长至 **`582.2s` (`1.37x`)** |
| **`RBS2-04`（38 项）**<br>`RB-B13` `FlowForge BPMN` 三泳道死锁画布修复 vs 默认置顶 `QuickStamp` 剪贴板面板<br>(`LAW_7 + LAW_5 + LAW_3`) | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.910 (F) -> 0.910 (F)`<br>`0.910 (F) -> 0.910 (F)` | **`418.4s / 905.3s` (`93.4%`)**<br>`158.2s / 503.2s` (`82.7%`) | `53`<br>`36` | `73 -> 74`<br>`63 -> 67` | `24 -> 21`<br>`18 -> 19` | `19 ->` **`31 (1.63x)`**<br>`15 ->` **`17`** | `0`<br>`0` | 默认 `WindowStaysOnTopHint` 置顶的 `QuickStamp` 遮挡 `BPMN` 中央红色故障节点并争夺系统剪贴板，使 `Sol` 焦点翻转由 `19` 次飙升至 **`31` 次**，两模型稳定落在非饱和 `0.910` 连续分区间 |
| **`RBS2-05`（40 项）**<br>`OSW2-P7` `Meridian LoanHub` 16 笔房贷核保 vs `GateSim` 12 电路波形示波器助教批改<br>(`LAW_7 + LAW_4 + LAW_2 + LAW_1`) | `gpt-6.1-sol`<br>`gpt-6-astra` | `1.000 (T) -> 1.000 (T)`<br>**`1.000 (T) -> 0.978 (T)`** | **`474.2s / 826.6s` (`93.8%`)**<br>`232.5s / 399.8s` (`92.2%`) | `62`<br>`49` | `76 -> 58`<br>`68 -> 61` | `26 ->` **`41 (1.58x)`**<br>`14 ->` **`18 (1.29x)`** | `6 ->` **`14 (2.33x)`**<br>`10 -> 7` | **`3`**<br>**`1`** | 共享 `:9222` 双门户与 `:99` 示波器引发 **`1–3` 次单键热键误投**；`Astra` 在并发同名 `Preferences` (`Ctrl+P`) 干扰下漏采 `glitch_setup_margin_ns = 1.8`（**得分 `1.000 -> 0.9777` 直接下降**），Token 与 CLI 同步上涨 **`+14% / +29%`** |
| **`RBS2-06`（40 项）**<br>`OSW2-P14` `MailDesk` 拉闸热力图与 `.ics` 答辩排期 vs 单实例 `Calc` 供应商 SLA 合同核算<br>(`LAW_6 + LAW_7 + LAW_2 + LAW_1`) | `gpt-6.1-sol`<br>`gpt-6-astra` | `0.975 (T) -> 1.000 (T)`<br>`1.000 (T) -> 1.000 (T)` | **`421.9s / 482.8s` (`93.3%`)**<br>**`317.9s / 353.4s` (`91.6%`)** | `51`<br>`45` | `78 -> 33`<br>`50 -> 41` | `35 -> 31`<br>`21 ->` **`29 (1.38x)`** | `16 -> 14`<br>`10 ->` **`15 (1.50x)`** | **`7`**<br>**`3`** | 全局墙钟并发重叠占比高达 **`87.4%`（`Sol`）与 `89.9%`（`Astra`）**；共享 `MailDesk`、`Calc` (`CONTRACT-DESK-906` 脏缓冲) 与 `:9222` 采购门户产生 **`3–7` 次误按键**，智能体通过刷盘与重读成功保住联合预算包络 |

---

## 三、目录结构与复现命令

- **第二批任务包与注册表**：[`tasks/rb_osw2_synth_v2/`](../tasks/rb_osw2_synth_v2/)（`rbs2_01` .. `rbs2_06`、`common.py`、`registry.py`）
- **多驱动评测与五门禁执行器**：[`experiments/rb_osw2_synth_v2.py`](../experiments/rb_osw2_synth_v2.py)
- **升级版造题工厂（含 `LAW_1..LAW_7`）**：[`tools/paragui_case_factory.py`](../tools/paragui_case_factory.py)
- **单元测试**：[`tests/test_rb_osw2_synth_v2.py`](../tests/test_rb_osw2_synth_v2.py)
- **机器可读清单**：
  - 造题蓝图审计：[`results-manifests/rb_osw2_synth_v2_factory_blueprint_audit_20261123.json`](results-manifests/rb_osw2_synth_v2_factory_blueprint_audit_20261123.json)
  - 确定性五门禁：[`results-manifests/rb_osw2_synth_v2_5gate_selfval_20261123.json`](results-manifests/rb_osw2_synth_v2_5gate_selfval_20261123.json)
  - 双模型 24 局实测：[`results-manifests/rb_osw2_synth_v2_sol61_astra_20261123.json`](results-manifests/rb_osw2_synth_v2_sol61_astra_20261123.json)

```bash
# 1. 静态合规审计（0 FAIL | 0 WARN）与七定律造题蓝图审计
PYTHONPATH=. python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py tasks/rb_osw2_synth_v2
PYTHONPATH=. python3 tools/paragui_case_factory.py audit-suite tasks/rb_osw2_synth_v2

# 2. 运行确定性五门禁校验（Gate 1..Gate 5）
PYTHONPATH=. python3 experiments/rb_osw2_synth_v2.py \
  --mode self_validate --workers 6 --code-root . --out /tmp/rbs2-selfval

# 3. 运行 isolated / shared 真实大模型评测（支持 --gui-driver qwen_cua 或 xdotool）
PYTHONPATH=. python3 experiments/rb_osw2_synth_v2.py \
  --mode shared --gui-driver qwen_cua --api-json /path/to/api.json \
  --codex-bin /path/to/codex --effort high --workers 3 --code-root . --out /tmp/rbs2-eval
```
