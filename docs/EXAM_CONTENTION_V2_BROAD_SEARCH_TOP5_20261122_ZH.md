# `exam_contention_v2`：基于更新版 `$paragui-case-design` 的 9 候选广泛搜索与 5 项优选基准实测报告（2026-11-22）

## 一、核心结论与契约对齐总览

围绕更新后的 `$paragui-case-design` 规范，本轮工作构建了多驱动（默认 `qwen-cua-driver 0.27.0` + `AT-SPI2`，支持无缝切换 `xdotool`）与全工作站 CLI（`guest_bash` 100% 开放）并行的闭卷评测套件 **`exam_contention_v2`**，并严格执行了 **“9 候选池广泛构建 -> 静态审计 + 五道确定性门禁 -> 全量 `gpt-6.1-sol (high)` 实测筛选 -> 优选 Top-5 跨模型 `gpt-6-astra (high)` 复验”** 的漏斗式筛选流程：

1. **100% 满足更新版 `$paragui-case-design` 四项核心升级**：
   - **严格 `GUI + CLI` 全开放并发（零阉割 CLI）**：所有角色容器同时挂载 `qwen_cua_driver`（连接 `/run/user/1000/qwen-cua.sock` 与 `AT-SPI2` 无障碍总线）以及完整 `guest_bash`（`DISPLAY=:99`、`xdotool`、`wmctrl`、`xclip`、编译器与办公/工程命令行全部保留），任务题面与评分器 100% 与驱动工具名解耦。
   - **同时覆盖两大一等竞争家族（Track 1 隔离磁盘纯屏幕竞争 + Track 2 共享进程/会话/耦合制品竞争）**：候选池横跨 5 个 **零共享工作目录（`workspace_mode = "isolated"`）的纯屏幕/焦点/视口/拖拽竞争场景** 与 4 个 **共享单实例进程、会话与双向耦合制品（`workspace_mode = "shared"`）场景**。
   - **连续部分得分（`[0.0, 1.0]`）+ 多维竞争恢复代价遥测**：离线盲评 `grade()` 同时输出连续 `score_a / score_b / mean_score` 与二值 `pass_a / pass_b / joint_pass`，并同步采集 **得分下降（`Score_shared < Score_isolated`）** 与 **自愈开销膨胀（输入 Token 倍率、端到端墙钟耗时倍率、窗口焦点翻转 `focus_flips`、按键误路由 `misrouted_keystrokes`、剪贴板变更与交错切换）**。
   - **静态审计零告警 + 五门禁 9/9 全通过**：`audit_case_module.py` 对 `tasks/exam_contention_v2` 与 `experiments/exam_contention_v2.py` 共 11 个文件取得 **`11/11 PASS | 0 FAIL | 0 WARN`**；9 个候选案例在真实容器时序下 **`9/9` 全部通过五道确定性门禁**（`Gate 5` 谨慎并发参考解耗时 `0.71s–22.62s`，远低于 `conc_role_timeout_s = 1500s` 的 `55%` 上限）。

2. **广泛实测筛选与最终保留的 5 个优质 Case（`EC2-C01, EC2-C03, EC2-C06, EC2-C07, EC2-C08`）**：
   - 在 **56 次** Non-YOLO 空气隔离容器智能体实测（`permission_audit_ok = 56/56` 100% 验证通过）中，优选保留的 **Top-5** 案例在两个前沿模型上均呈现高度一致的双维竞争信号：
   - **`gpt-6.1-sol (high)`（Top-5）**：连续均分由 `isolated` **`0.9850`** 降至 `shared` **`0.9510`**（`joint_pass` 联合通过率由 **`80.0% (4/5)` 腰斩至 `40.0% (2/5)`**），平均输入 Token 膨胀至 **`1.790x`**（最高 `3.22x`），平均墙钟耗时膨胀至 **`1.539x`**（最高 `2.50x`），窗口焦点翻转由 `44` 次升至 **`75` 次**，并发按键误路由由 `0` 升至 **`11` 次**。
   - **`gpt-6-astra (high)`（Top-5）**：连续均分由 `isolated` **`0.9850`** 降至 `shared` **`0.9565`**（`joint_pass` 联合通过率由 **`80.0% (4/5)` 降至 `60.0% (3/5)`**），平均输入 Token 膨胀至 **`1.490x`**，平均墙钟耗时膨胀至 **`1.300x`**，窗口焦点翻转由 `43` 次升至 **`77` 次**，并发按键误路由由 `0` 升至 **`17` 次**。

---

## 二、第一阶段：9 候选池五门禁验证与 `gpt-6.1-sol (high)` 广泛筛选漏斗

### 2.1 9 个候选案例的五道确定性门禁验证（`9/9 PASS`）

结构化清单见 [`results-manifests/exam_contention_v2_9cand_5gate_selfval_20261122.json`](results-manifests/exam_contention_v2_9cand_5gate_selfval_20261122.json)。

| 候选 ID | 竞争赛道与工作目录 | 领域与共享桌面竞争表面 | Gate 1 `pristine` | Gate 2 `seq_ab` | Gate 3 `seq_ba` | Gate 4 `contention` | Gate 5 `careful_conc` | 门禁结论 |
|---|---|---|---:|---:|---:|---:|---:|---|
| `EC2-C01` | Track 1 (`isolated`) | 单实例 `:9222` CDP 浏览器响应式断点的移动视口 vs `1920x1080` 全屏 6 幕动效录制 | `0.000` | `1.000` | `1.000` | `0.900` (`False`) | `1.000` (`7.73s`) | **PASS** |
| `EC2-C02` | Track 1 (`isolated`) | GTK3 失焦自隐 `F10` 弹窗 `VibraScope` vs PyQt5 热键 `TelemetryHex` 探索复刻 | `0.000` | `1.000` | `1.000` | `0.850` (`False`) | `1.000` (`2.13s`) | **PASS** |
| `EC2-C03` | Track 1 (`isolated`) | PyQt5 连续鼠标拖拽桁架节点 `AeroTruss` vs 叠窗遮挡 `SpectraProof` D50 色度采证 | `0.000` | `1.000` | `1.000` | `0.875` (`False`) | `1.000` (`2.62s`) | **PASS** |
| `EC2-C04` | Track 1 (`isolated`) | 单实例 `GIMP 2.10` 多图层主视觉 `.xcf` 合成 vs 包装刀线印前校样 | `0.000` | `1.000` | `1.000` | `0.875` (`False`) | `1.000` (`0.71s`) | **PASS** |
| `EC2-C05` | Track 1 (`isolated`) | 共享 PyQt5 广电母带示波器滑块/剪贴板 vs `FFmpeg` EBU R128 / Rec.709 响度合规 | `0.000` | `1.000` | `1.000` | `0.875` (`False`) | `1.000` (`2.38s`) | **PASS** |
| `EC2-C06` | Track 2 (`shared`) | 单实例 `soffice.bin`（8 页 `Writer` 董事会报告 + `Calc` 偿付能力模型）脏缓冲脑裂 | `0.140` | `1.000` | `1.000` | `0.904` (`False`) | `1.000` (`22.62s`) | **PASS** |
| `EC2-C07` | Track 2 (`shared`) | 24 例肿瘤住院化疗/肾脏支持给药 + `HttpOnly` EHR 单位切换 + 剪贴板 + 驻留 `Writer` | `0.000` | `1.000` | `1.000` | `0.904` (`False`) | `1.000` (`13.20s`) | **PASS** |
| `EC2-C08` | Track 2 (`shared`) | 1U 机箱 `FreeCAD` `.FCStd/.step` + `Inkscape` 丝印 + `HttpOnly` PLM 公英制 + 驻留 `Calc` | `0.135` | `1.000` | `1.000` | `0.608` (`False`) | `1.000` (`16.46s`) | **PASS** |
| `EC2-C09` | Track 2 (`shared`) | 多币种清算网关 `Git main` + 实况 `:19190` 守护进程 + HMAC 防重放 + 驻留 `Calc` | `0.139` | `1.000` | `1.000` | `0.723` (`False`) | `1.000` (`14.87s`) | **PASS** |

### 2.2 全量 9 候选 `gpt-6.1-sol (high)` 实测筛选对比（18 局 = 36 个容器智能体）

完整筛选成绩单见 [`results-manifests/exam_contention_v2_9cand_screening_20261122.json`](results-manifests/exam_contention_v2_9cand_screening_20261122.json)。

| 候选 ID | 赛道 | `Score_iso` | `Score_shr` | `ΔScore` | `joint_pass` (`iso->shr`) | Token 膨胀比 | 耗时膨胀比 | 焦点翻转 (`iso->shr`) | 误路由按键 (`iso->shr`) | `shared` GUI/CLI 调用 | 筛选去留与实证依据 |
|---|---|---:|---:|---:|---|---:|---:|---|---|---|...|
| **`EC2-C01`** | Track 1 | `0.925` | **`0.875`** | **`-0.050`** | `F -> F` | **`1.71x`** | **`1.35x`** | `3 -> 7` | `0 -> 0` | `29 / 28` | **保留（优选 #1）**：视口/全屏互抢直接拉低 Role B 得分（`1.00->0.90`），Token 暴涨 `+71%` |
| `EC2-C02` | Track 1 | `0.475` | `0.475` | `0.000` | `F -> F` | `0.89x` | `1.04x` | `4 -> 5` | `0 -> 0` | `17 / 20` | **淘汰**：`isolated` 下已漏检 `F10` 自隐弹窗，双臂区分度弱于 `C01/C03` |
| **`EC2-C03`** | Track 1 | `1.000` | **`1.000`** | `0.000` | `T -> T` | **`1.24x`** | **`1.32x`** | **`3 -> 9`** | `0 -> 0` | `22 / 15` | **保留（优选 #2）**：零共享文件下节点拖拽与窗口遮挡触发 **`3.0x` 焦点翻转**与 `+32%` 自愈耗时 |
| `EC2-C04` | Track 1 | `1.000` | `1.000` | `0.000` | `T -> T` | `0.91x` | `0.96x` | `7 -> 8` | `0 -> 0` | `28 / 25` | **淘汰**：智能体通过非交互批处理绕开了 GIMP 画布驻留冲突，双臂无显著开销差 |
| `EC2-C05` | Track 1 | `0.075` | `0.125` | `+0.050` | `F -> F` | `1.44x` | `1.30x` | `0 -> 0` | `0 -> 0` | `5 / 16` | **淘汰**：音频滤波器容差过严导致 `isolated` 基线过低（`0.075`），掩盖桌面竞争信号 |
| **`EC2-C06`** | Track 2 | `1.000` | **`0.960`** | **`-0.040`** | **`T -> F`** | `1.04x` | `0.94x` | `18 -> 17` | `0 -> 0` | `48 / 45` | **保留（优选 #3）**：经典单实例 `soffice.bin`（`Writer+Calc`）脏缓冲脑裂自然触发，`joint_pass` 由通转挂 |
| **`EC2-C07`** | Track 2 | `1.000` | **`0.920`** | **`-0.080`** | **`T -> F`** | **`3.22x`** | **`2.50x`** | **`11 -> 25`** | **`0 -> 6`** | `106 / 70` | **保留（优选 #4）**：全场最强多维冲突，`joint_pass` 跌落 + **`3.22x` Token** + **`2.50x` 耗时** + `6` 次误按键 |
| **`EC2-C08`** | Track 2 | `1.000` | **`1.000`** | `0.000` | `T -> T` | **`1.74x`** | **`1.59x`** | **`9 -> 17`** | **`0 -> 5`** | `53 / 56` | **保留（优选 #5）**：`FreeCAD + Inkscape + PLM + Calc` 多工具互抢引发 `+74%` Token 与 `5` 次误按键（且在 `Astra` 上直接击穿 `joint_pass`） |
| `EC2-C09` | Track 2 | `0.827` | `1.000` | `+0.173` | `F -> T` | `1.11x` | `1.04x` | `14 -> 10` | `0 -> 11` | `61 / 47` | **淘汰**：共享 Git 历史使 Role A 在并发下顺带获益（分数倒挂且耗时仅 `1.04x`） |

---

## 三、第二阶段：最终保留的 5 个优质 Case 双模型（`gpt-6.1-sol` & `gpt-6-astra`）实测全表

双模型完整结构化成绩单见 [`results-manifests/exam_contention_v2_top5_sol61_astra_20261122.json`](results-manifests/exam_contention_v2_top5_sol61_astra_20261122.json)。

### 3.1 宏观汇总指标（Top-5）

| 模型（`reasoning_effort = high`） | `isolated` 均分 | `shared` 均分 | `isolated` `joint_pass` | `shared` `joint_pass` | 平均输入 Token 膨胀比 | 平均墙钟耗时膨胀比 | 总焦点翻转 (`iso -> shr`) | 总误路由按键 (`iso -> shr`) | 非 YOLO 权限审计 |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| **`gpt-6.1-sol`** | `0.9850` | **`0.9510`** (`-0.0340`) | `80.0%` (`4/5`) | **`40.0%` (`2/5`)** | **`1.790x`** | **`1.539x`** | `44 -> 75` (`1.70x`) | `0 -> 11` | `20/20 PASS` |
| **`gpt-6-astra`** | `0.9850` | **`0.9565`** (`-0.0285`) | `80.0%` (`4/5`) | **`60.0%` (`3/5`)** | **`1.490x`** | **`1.300x`** | `43 -> 77` (`1.79x`) | `0 -> 17` | `20/20 PASS` |

### 3.2 逐案例双模型精细指标与机制剖析

| Case ID | 模型 | `Score_iso -> Score_shr`（角色分 `A, B`） | `joint_pass` | 输入 Token (`iso -> shr`) | 墙钟耗时 (`iso -> shr`) | 焦点翻转 (`iso -> shr`) | 误按键 (`iso -> shr`) | `shared` 实测冲突表征与自愈/失分机制 |
|---|---|---|---|---|---|---|---|---|
| **`EC2-C01`**<br>CDP 响应式 Web QA vs 全屏 6 幕录制 | `gpt-6.1-sol` | `0.925 (0.85,1.00) ->` **`0.875 (0.85,0.90)`** | `F -> F` | `0.90M ->` **`1.54M (1.71x)`** | `142.4s ->` **`191.7s (1.35x)`** | `3 -> 7` | `0 -> 0` | 共享 `:9222` Chromium 在 `390x844` 移动断点与 `1920x1080` F11 全屏间来回拉锯，污染第 6 幕 `scene_codes` |
| **`EC2-C01`** | `gpt-6-astra` | `0.925 (0.85,1.00) ->` **`0.840 (0.85,0.83)`** | `F -> F` | `1.10M ->` **`1.51M (1.37x)`** | `219.7s ->` **`254.9s (1.16x)`** | `3 -> 10` | `0 -> 0` | `10` 次窗口焦点翻转导致 Role B 动效暂停态/遥测汇总失准（`1.00 -> 0.83`） |
| **`EC2-C03`**<br>PyQt5 节点拖拽桁架 vs 叠窗色度校样 | `gpt-6.1-sol` | `1.000 (1.00,1.00) ->` **`1.000 (1.00,1.00)`** | `T -> T` | `0.45M ->` **`0.56M (1.24x)`** | `100.1s ->` **`131.6s (1.32x)`** | `3 -> 9` | `0 -> 0` | `AeroTruss` 连续拖拽与 `SpectraProof` `D50` 窗口截图在 `x=660..1100` 重叠区互抢 Z-order，触发 `3.0x` 焦点重激活自愈 |
| **`EC2-C03`** | `gpt-6-astra` | `1.000 (1.00,1.00) ->` **`1.000 (1.00,1.00)`** | `T -> T` | `0.42M ->` **`0.68M (1.61x)`** | `102.1s ->` **`139.4s (1.37x)`** | `3 -> 10` | `0 -> 0` | 跨模型高度一致复现：`3.33x` 焦点翻转 + `+61%` Token 重新置顶截图 |
| **`EC2-C06`**<br>单实例 `Writer+Calc` 偿付能力与董事会报告 | `gpt-6.1-sol` | `1.000 (1.00,1.00) ->` **`0.960 (0.96,0.96)`** | **`T -> F`** | `2.29M -> 2.38M (1.04x)` | `345.1s -> 324.6s (0.94x)` | `18 -> 17` | `0 -> 0` | 并发修改磁盘 `.xlsx/.odt` 后未同步重载同一 `soffice.bin` 打开的驻留窗口，触发脏缓冲脑裂失分 |
| **`EC2-C06`** | `gpt-6-astra` | `1.000 (1.00,1.00) ->` **`1.000 (1.00,1.00)`** | `T -> T` | `1.39M ->` **`1.60M (1.16x)`** | `273.3s ->` **`316.4s (1.16x)`** | `11 -> 13` | `0 -> 0` | `Astra` 在保存与导出 PDF 前主动刷盘并校验打开的 `soffice.bin` 窗口，以 `+16%` 开销避免脑裂 |
| **`EC2-C07`**<br>24 例肿瘤给药 + EHR 单位 + 剪贴板 + `Writer` | `gpt-6.1-sol` | `1.000 (1.00,1.00) ->` **`0.920 (1.00,0.84)`** | **`T -> F`** | `1.77M ->` **`5.71M (3.22x)`** | `268.7s ->` **`671.6s (2.50x)`** | `11 -> 25` | `0 -> 6` | `CONV_MG_DL` / `SI_UMOL_L` 会话与剪贴板剧烈互抢（`176` 次工具调用），Role B 签收单丢失肾脏核验章 |
| **`EC2-C07`** | `gpt-6-astra` | `1.000 (1.00,1.00) ->` **`1.000 (1.00,1.00)`** | `T -> T` | `1.79M ->` **`2.84M (1.59x)`** | `372.7s ->` **`494.6s (1.33x)`** | `12 -> 15` | `0 -> 14` | 遭遇 **`14` 次按键误路由**后通过 `xclip` 读回校验与 SQLite 复核完成闭环恢复 |
| **`EC2-C08`**<br>1U 机箱 `FreeCAD` + `Inkscape` + PLM + `Calc` | `gpt-6.1-sol` | `1.000 (1.00,1.00) ->` **`1.000 (1.00,1.00)`** | `T -> T` | `1.70M ->` **`2.96M (1.74x)`** | `260.9s ->` **`415.7s (1.59x)`** | `9 -> 17` | `0 -> 5` | 并发重算 `.FCStd/.step` 与紧固件预紧力期间产生 `17` 次切窗与 `5` 次误按键，靠 `+74%` Token 自愈 |
| **`EC2-C08`** | `gpt-6-astra` | `1.000 (1.00,1.00) ->` **`0.942 (1.00,0.88)`** | **`T -> F`** | `2.24M ->` **`3.86M (1.72x)`** | `437.6s ->` **`651.2s (1.49x)`** | `14 -> 29` | `0 -> 3` | **`29` 次焦点翻转**：PLM 公英制切换抢占剪贴板，导致 Role B 写入错误的 `PLM_EMC_ECN_Seal` |

---

## 四、保留的 5 个优质 Case 设计卡片摘要

1. **`EC2-C01` — 单实例 CDP 浏览器响应式 Web QA vs 无遮挡 `1920x1080` 6 幕动效故事板录制**（[`c01_cdp_responsive_storyboard.py`](../tasks/exam_contention_v2/c01_cdp_responsive_storyboard.py)）
   - **工作空间模式**：`isolated`（零共享磁盘文件，纯共享显示服务器与单实例 `:9222` Chromium 竞争）。
   - **GUI 不可替代性（Exploration-as-Oracle）**：桌面预启动无源码的动态 WebGL/Canvas 应用 `NebulaFlow Cloud Ops`；`responsive_qa_lead` 必须在 `390x844 / 820x900 / 1440x900` 三组真实视口下检测移动端横向溢出、按钮触控高度与三档计费汇率，而 `motion_demo_producer` 必须将同一浏览器切至 `1920x1080` 无边框全屏并保持播放态录制 `scene_1..6.png` 与合成 `nebula_keynote.gif`。

2. **`EC2-C03` — PyQt5 连续节点拖拽桁架优化器 `AeroTruss` vs 叠窗色度校样工作台 `SpectraProof`**（[`c03_canvas_drag_zorder_gamut.py`](../tasks/exam_contention_v2/c03_canvas_drag_zorder_gamut.py)）
   - **工作空间模式**：`isolated`（零共享磁盘文件，纯 X11 连续鼠标拖拽与窗口 Z-order 遮挡竞争）。
   - **GUI 不可替代性**：`structural_sketch_eng` 需要在实况 PyQt5 `AeroTruss Sketcher` 画布上拖拽橙色上弦节点 `T1/T2` 使应力、挠度、钢材质量与风管净空四项实时仪表同时达标并导出签名几何包；`color_proof_specialist` 需要将重叠在 `x=660..1100` 区域的 `SpectraProof Studio` 切换至 `D50_ISO12647_PRINT`、采集无遮挡 8 色块窗口图像并计算 `CIELAB Delta-E76` 超差色块。

3. **`EC2-C06` — 单实例 `LibreOffice`（8 页 `Writer` 董事会报告 + `Calc` 偿付能力模型）脏缓冲脑裂**（[`c06_impress_calc_actuarial.py`](../tasks/exam_contention_v2/c06_impress_calc_actuarial.py)）
   - **工作空间模式**：`shared`（共享 `/home/user/.config` 下唯一 `soffice.bin` 实例、`HttpOnly` 再保/资产风险门户、`~/Downloads` 与 X11 剪贴板）。
   - **核心竞争表面**：`Solvency_II_Model.xlsx`（含未落盘 `ACTUARY-DESK-402` 标签）与 `Q4_Board_Brief.odt`（含 `Comic Sans MS` 字体污染与 `20.5cm` 越界左缩进）同时打开于同一 `soffice.bin` 进程，且次级债与侧挂抵押品通过 `Solvency_Coverage_Ratio ∈ [1.62, 1.66]` 双向耦合。

4. **`EC2-C07` — 肿瘤住院病房 24 例化疗/肾脏支持医嘱、`HttpOnly` EHR 单位切换、剪贴板与驻留 `Writer`**（[`c07_oncology_ehr_writer.py`](../tasks/exam_contention_v2/c07_oncology_ehr_writer.py)）
   - **工作空间模式**：`shared`（共享 SQLite 给药库、3 张扫描版药学列线图 PNG、`HttpOnly` EHR 门户、X11 剪贴板与打开未保存 `ONC-7N-ROUND-514` 的 `Cycle4_Infusion_Protocol.odt`）。
   - **核心竞争表面**：化疗药师（需 `CONV_MG_DL` 传统单位与化疗核验章）与肾脏支持药师（需 `SI_UMOL_L` 国际单位与肾脏核验章）共享唯一登录态 EHR 与剪贴板，并在 5 名心衰（`CHF`）患者上受 24h 总输液量 `[1640, 1710] mL` 双向耦合约束。

5. **`EC2-C08` — 1U 机箱 `FreeCAD` 三维开孔、`Inkscape` 面板丝印、`HttpOnly` PLM 公英制与预紧力耦合**（[`c08_enclosure_freecad_plm.py`](../tasks/exam_contention_v2/c08_enclosure_freecad_plm.py)）
   - **工作空间模式**：`shared`（共享 `chassis_housing.FCStd` / `release/chassis_housing.step`、`front_bezel_silkscreen.svg`、`Thermal_EMI_BOM.xlsx` 与 `HttpOnly` PLM）。
   - **核心竞争表面**：热设计工程师与电磁兼容工程师并发编辑同一三维装配体（顶盖散热阵列避让禁布区 vs 后背板 QSFP28/RJ45/AC 开孔）及同一打开的 Calc BOM 表（总紧固预紧力 `[244, 252] N·cm` 双向耦合），同时争夺 PLM 公制 `mm` / 英制 `mil` 导出与 ECN 剪贴板签章。

---

## 五、代码入口、单测与复现命令

- **任务包与注册表**：[`tasks/exam_contention_v2/`](../tasks/exam_contention_v2/)（`CANDIDATE_POOL_CATALOG` 收录全部 9 个候选，`RETAINED_TOP5_IDS` 导出最终优选 5 项）
- **多驱动评测与五门禁执行器**：[`experiments/exam_contention_v2.py`](../experiments/exam_contention_v2.py)
- **契约与结果清单单元测试**：[`tests/test_exam_contention_v2.py`](../tests/test_exam_contention_v2.py)
- **持久化归档目录**：`cpu15:/home/yuke/data/paraGUI/runs/exam-contention-v2-screen-20261122*` 与 `cpu15:/home/yuke/data/paraGUI/runs/exam-contention-v2-top5-astra-20261122-backup/`

```bash
# 1. 运行更新版 $paragui-case-design 静态与时序预算审计（0 FAIL | 0 WARN）
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py tasks/exam_contention_v2
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py experiments/exam_contention_v2.py

# 2. 运行五道确定性良定性门禁验证（默认全量 9 候选，或传 --tasks top5 仅测优选 5 项）
PYTHONPATH=. python3 experiments/exam_contention_v2.py \
  --mode self_validate --workers 5 --code-root . --out /tmp/ec2-selfval --tasks top5

# 3. 运行优选 Top-5 的 isolated / shared 双臂 Non-YOLO 容器实测（支持 --gui-driver qwen_cua | xdotool）
PYTHONPATH=. python3 experiments/exam_contention_v2.py \
  --mode isolated --gui-driver qwen_cua --effort high --workers 5 \
  --code-root . --api-json ~/data/paraGUI/private/sol61-api.json \
  --codex-bin ~/data/paraGUI/runtime/codex/codex --out /tmp/ec2-top5 --tasks top5

PYTHONPATH=. python3 experiments/exam_contention_v2.py \
  --mode shared --gui-driver qwen_cua --effort high --workers 5 \
  --code-root . --api-json ~/data/paraGUI/private/sol61-api.json \
  --codex-bin ~/data/paraGUI/runtime/codex/codex --out /tmp/ec2-top5 --tasks top5
```
