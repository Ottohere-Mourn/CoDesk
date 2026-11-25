# `authentic_workstation_v1`：基于新版 `$paragui-case-design` 的 22 候选真实软件搜索、Harness 封堵与 Top-5 双模型实测报告（2026-11-25）

## 一、核心结论与过往套件问题清零总览

围绕新版 `$paragui-case-design` 规范，本轮构建了 100% 运行于真实开源桌面与 Web 软件的评测套件 **`authentic_workstation_v1`**（注册表 [`tasks/authentic_workstation_v1/registry.py`](../tasks/authentic_workstation_v1/registry.py)、密封执行器 [`experiments/authentic_workstation_v1.py`](../experiments/authentic_workstation_v1.py)），完成了 **22 个真实软件候选案例（`AW-01..AW-22`）构建 -> 24 文件静态审计零告警 -> 110 局确定性五门禁全通过 -> 88 局（176 个 Non-YOLO 容器智能体）双模型实测筛选 -> 优选保留 Top-5（`AW-12, AW-14, AW-15, AW-19, AW-20`）** 的全链路闭环。

### 1.1 对历史基准缺陷的系统性根治（含两项新发现的 Linux 容器旁路封堵）

1. **零内联玩具 GUI（`0%` 合成 `PyQt/GTK/Tk` 假应用）**：彻底摒弃 ~100 行内联脚本模拟器的做法，全量采用 `paragui/qwen-cua-desktop:20261120` 预装的真实开源软件栈——`LibreOffice Calc & Writer`、`GIMP 2.10`、`Inkscape 1.2`、`FreeCAD 0.20`、`QGIS 3.22 + GDAL/OGR`、`Qt5 Designer + Qt5 Linguist + lrelease`、`Chromium`、`FFmpeg`、`SQLite` 与 `Git`。
2. **封堵两项隐蔽的 Linux 容器 `guest_bash` 旁路（`Xvfb -auth` + 独立 `UID 2000`）**：
   - **抽象域套接字旁路**：即便 `role_containers` 不挂载 `/tmp/.X11-unix` 文件目录，`--network container:<desk>` 仍会共享 Linux 网络命名空间中的抽象 Unix 套接字 `@/tmp/.X11-unix/X99`；若 `Xvfb` 使用 `-ac` 启动，智能体可在 CLI 中设 `DISPLAY=:99` 直接调 `xdotool/wmctrl/import` 绕过被测 CUA 驱动。`AuthenticWorkstationDesktop` 改为生成随机 `xauth` Cookie（`Xvfb :99 -auth /tmp/x99.auth`），仅向桌面容器内的 GUI 驱动注入 `XAUTHORITY=/tmp/x99.auth`。
   - **`/proc/<pid>/root` 跨容器文件系统穿透**：启用 `--pid container:<desk>` 解决守护进程可见性后，若 `exec_role` 与桌面进程共享数值 UID（`1000/1001`），CLI 智能体可通过 `/proc/<soffice_pid>/root/srv/studio_project` 直接改写 GUI 专属文件（这也是早期 `Wave 2` 中 `AW-01..AW-10` 出现 `1.000 -> 1.000` 饱和的精确根因）。密封版将 `exec_role` 隔离至独立 `--user 2000:0`（`cli_user`），实机探针验证 `DISPLAY=:99 wmctrl -l` 返回 `Authorization required`、`/proc/*/root` 返回 `Permission denied`，使 GUI 交互 100% 真实流经 `qwen-cua-driver 0.27.0`。
3. **消除 `isolated` 基线污染、退出后 `Ctrl+S` 注入与硬编码分屏**：
   - `boot_apps` 接收 `--active-roles` 按需仅启动当前单角色所需应用；`build_aw_grade_payload` 在 `isolated` 模式下跳过跨角色耦合项且保持单角色分母恒定。
   - `stop_and_grade()` 100% 只读采集退出窗口列表并执行离线盲评，绝不在智能体退出后注入 `xdotool key ctrl+s`。
   - 全部桌面窗口采用 Openbox `<center>yes</center>` 自然居中叠放，移除 `max_cua_calls = 42` 低步数断头台（放宽至 `140` 步安全上限、`isolated 1200s / shared 1500s`），`~/Downloads` 对 CLI 容器只读挂载（杜绝明文聊天室）。
4. **真实共居工作流与零剧透目标驱动工单**：同机双角色均来自同一工程/财务/临床项目组（如超大规模数据中心采购控制与法务顾问、ISO 13485 医疗监护仪前框光学与后壳散热工程师、生物光子学显微与电泳分析师），题面不剧透公式、菜单路径或门户隐藏常量，`audit_case_module.py` 审计 **24 个文件取得 `24 PASS | 0 FAIL | 0 WARN`**。

### 1.2 优选保留 Top-5（`AW-12, AW-14, AW-15, AW-19, AW-20`）双模型核心表现

在密封版 `AuthenticWorkstationDesktop` 下，最终保留的 5 个代表性案例横跨 **5 套异构真实软件栈**，单角色 `isolated` 平均耗时达 **`11.6–12.9 分钟`**（均分 **`0.9099 / 0.9177`**，非天花板饱和），并在并发 `shared` 模式下于两款前沿模型上同时打出显著的准确率退化与自愈开销膨胀：

| 模型（`effort = high`） | `isolated` 均分 | `shared` 均分 | **`ΔScore (shr - iso)`** | `joint_pass` (`iso -> shr`) | 输入 Token 膨胀比 | 墙钟耗时膨胀比 | CLI 调用膨胀比 | 平均并发重叠 | 焦点翻转 (`iso -> shr`) | 误路由按键 (`iso -> shr`) | 非 YOLO 审计 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|---|
| **`gpt-6.1-sol`** | `0.9099` | **`0.8431`** | **`-0.0668 (-6.68%)`** | `40.0% -> 40.0%` | **`1.583x`** | **`1.513x`** (`775.7s -> 1115.7s`) | **`2.615x`** | **`779.0s`** (`13.0m`) | `118 -> 127` | `0 -> 30` | `20/20 PASS` |
| **`gpt-6-astra`** | `0.9177` | **`0.7064`** | **`-0.2113 (-21.13%)`** | **`60.0% -> 40.0%`** | **`1.546x`** | **`1.633x`** (`696.4s -> 1098.5s`) | **`2.246x`** | **`720.8s`** (`12.0m`) | **`120 -> 156`** | **`0 -> 55`** | `20/20 PASS` |

---

## 二、22 候选广泛搜索、五门禁验证与实测筛选漏斗

- **确定性五门禁清单**：[`results-manifests/authentic_workstation_v1_5gate_selfval_20261124.json`](results-manifests/authentic_workstation_v1_5gate_selfval_20261124.json)（`22/22` 候选、`110/110` 局门禁 100% 通过，`Gate 1 = 0.000`，`Gate 2/3/5 = 1.000`，`Gate 4 = 0.333–0.916`，`Gate 5` 真实并发参考解耗时 `0.7s–24.8s`）。
- **全量 22 候选双模型筛选账本**：[`results-manifests/authentic_workstation_v1_22cand_screening_20261124.json`](results-manifests/authentic_workstation_v1_22cand_screening_20261124.json)（`88` 局、`176/176` 容器角色通过 `permission-audit-verified.json`）。

| ID | 真实软件栈与工作空间 | 验证波次 | `gpt-6.1-sol` (`iso -> shr`) | `gpt-6-astra` (`iso -> shr`) | 双模平均 `ΔScore` | 去留结论与机制复盘 |
|---|---|---|---|---|---:|---|
| `AW-01..AW-10` | `Chromium / GIMP / Inkscape / QGIS / FreeCAD / Calc / Writer / Designer / Linguist / FFmpeg` | `wave2_r2` | `1.000 -> 1.000` | `1.000 -> 1.000` | `0.0000` | **淘汰（推动密封升级）**：智能体通过同 UID `/proc/<pid>/root` 与抽象 `@/tmp/.X11-unix/X99` 绕过 GUI 窗口，直接促成 `sealed_cert` 隔离升级 |
| `AW-11` | `QGIS 3.22 + Calc + Chromium` (`shared`) | `wave2_r2` | `0.917 -> 0.932` | `0.917 -> 0.932` | `+0.0158` | **淘汰**：仅 3 个汇总单元格写入，开销小且共享表带来微弱互助 |
| **`AW-12`** | **`Chromium` 8 状态零剧透 `Chronos ERP` 探索复刻 (`shared`)** | **`sealed_cert`** | **`0.862 (T) -> 0.594 (F)` (`-26.7%`)** | `0.731 (F) -> 1.000 (T)` | `+0.0010` | **保留（Top-5 #1）**：`isolated` 非饱和（`0.73–0.86`，`16–17m`），`Sol` 在并发探索与打包写入时丢失 `Capacity` 抽屉模块重挫 `-26.7%` |
| `AW-13` | `LibreOffice Calc + Writer` 5 行财务关账 (`shared`) | `sealed_cert` | `1.000 -> 1.000` | `1.000 -> 1.000` | `0.0000` | **淘汰**：单表单公式行数偏少（5 行），模型在 `5–14m` 内靠重试吸收全部焦点冲突 |
| **`AW-14`** | **单实例 `GIMP 2.10` 四图层去遮罩缩放 + `Inkscape 1.2` 海报 (`shared`)** | **`sealed_cert`** | `0.913 -> 0.913`（**`3.04x` Token、`2.00x` 耗时、`56` 翻转**） | **`0.913 -> 0.310` (`-60.3%`，`27` 误按键)** | **`-0.3016`** | **保留（Top-5 #2）**：单实例 `GIMP` 双标签与 `Scale Image / Export As` 模态弹窗正中叠压引发剧烈误按键与失分 |
| **`AW-15`** | **`Qt5 Designer` 透析面板 + `Qt5 Linguist` 8 条德语本地化 (`shared`)** | **`sealed_cert`** | `0.880 -> 1.000`（`miskey=6`，耗时 `1.23x`） | **`1.000 (T) -> 0.579 (F)` (`-42.1%`)** | **`-0.1508`** | **保留（Top-5 #3）**：`Designer` 属性框与 `Linguist` `Ctrl+Return` 录入互抢焦点，致 `Astra` 仅完成 `4/8` 词条 |
| `AW-16` | `QGIS 3.22 + Calc` 输电走廊 (`shared`) | `sealed_cert` | `1.000 -> 1.000` | `1.000 -> 1.000` | `0.0000` | **淘汰**：4 行无耦合表格，未突破模型自愈缓冲 |
| `AW-17` | `LibreOffice Calc + Writer` 光伏项目融资 DSCR (`shared`) | `sealed_cert` | `0.873 -> 1.000` | `0.873 -> 1.000` | `+0.1275` | **淘汰**：门户标题括号内的 `term_code` 在 `shared` 下经共享 `.odt` 被同伴补齐，产生协作正增益 |
| `AW-18` | `FreeCAD 0.20 + QGIS 3.22 + Calc` 风机基础 (`shared`) | `sealed_cert` | `1.000 -> 1.000` | `1.000 -> 1.000` | `0.0000` | **淘汰**：`Calc` 仅需填 2 个单元格，Token 翻倍（`1.76x`）但准确率饱和 |
| **`AW-19`** | **零剧透 `LibreOffice Calc` 32 格双栏公式 + `Writer` 6 处红线修订 (`shared`)** | **`sealed_cert`** | **`0.894 (F) -> 0.708 (F)` (`-18.6%`)** | **`0.945 (T) -> 0.708 (F)` (`-23.6%`)** | **`-0.2111`** | **保留（Top-5 #4）**：**双模型同步重挫超 `18%`**；单实例 `soffice.bin` 多表录入与 `Ctrl+H` 查找替换弹窗冲突致第 9 节红线丢失 |
| **`AW-20`** | **零剧透 `FreeCAD 0.20` + 单实例 `GIMP 2.10` + `Calc` 悬臂配重 DHR (`shared`)** | **`sealed_cert`** | `1.000 -> 1.000`（`miskey=14`，耗时 `1.56x`） | **`1.000 -> 0.935` (`-6.5%`，耗时 `2.03x / 23.5m`，翻转 `55`)** | **`-0.0324`** | **保留（Top-5 #5）**：四款真实软件同屏叠压，`238` 次 GUI 调用与 `55` 次切窗导致 `Calc` `Rear_Assy` 公式漏存 |
| `AW-21` | `isolated` `StrataFin Cloud` 复刻 + `Inkscape` + `FFmpeg` (`isolated`) | `sealed_cert` | `1.000 -> 1.000`（耗时 `1.32x`，`miskey=11`） | `1.000 -> 1.000`（`ov=799.4s`，`miskey=12`） | `0.0000` | **淘汰**：智能体在 `guest_bash` 用 PIL 校验只读 `~/Downloads` 截图并循环重拍直至无遮挡，按规范不认证 `1.0 -> 1.0` 饱和题 |
| `AW-22` | 零剧透 `QGIS 3.22` 四图层排除 + 视觉水文图 + `Calc` 零壅水 (`shared`) | `sealed_cert` | `0.927 -> 1.000`（`CLI 3.53x`，`Token 3.31x`） | `1.000 -> 1.000`（`ov=600.5s`，`miskey=7`） | `+0.0366` | **淘汰**：虽触发 `3.31x` Token 膨胀，但未产生并发净掉分 |

---

## 三、最终保留 Top-5 逐题双模型实测明细与真实软件冲突机理

完整逐局与逐角色 JSON 成绩单见 [`results-manifests/authentic_workstation_v1_top5_sol61_astra_20261124.json`](results-manifests/authentic_workstation_v1_top5_sol61_astra_20261124.json)。

| Case ID | 真实软件栈与双角色 | 模型 | `Score_iso -> Score_shr`（`A, B`） | `joint_pass` | 输入 Token (`iso -> shr`) | 墙钟耗时 (`iso -> shr`) | GUI / CLI (`shr`) | 焦点翻转 (`iso -> shr`) | 误按键 (`shr`) | 实测触发的真实软件失分/自愈机理 |
|---|---|---|---|---|---|---|---|---|---|---|
| **`AW-12`** | `Chromium` (`HttpOnly`) + `HTML5/CSS3/JS`<br>`orders_ui_eng` + `capacity_ui_eng` | `gpt-6.1-sol` | **`0.8615 -> 0.5942`** (`0.65, 0.54`) | **`T -> F`** | `5.62M -> 4.21M` (`0.75x`) | `1023.4s -> 931.2s` | `137 / 28` | `6 -> 3` | `0` | 零剧透 8 状态 ERP 门户并发点击切换路由，叠加前端源码并发落盘覆盖，丢失 `Capacity` 抽屉与配额子页 |
| **`AW-12`** | 同上 | `gpt-6-astra` | `0.7308 -> 1.0000` (`1.00, 1.00`) | `F -> T` | `4.93M -> 5.54M` (`1.12x`) | `939.3s -> 906.1s` | `169 / 32` | `6 -> 5` | `0` | `isolated` 下 Role B 漏采滑出式故障转移抽屉（`0.60`）；并发下耗时 `723.5s` 重叠并合并双模块代码 |
| **`AW-14`** | `GIMP 2.10` + `Inkscape 1.2` + `Chromium` + `SQLite`<br>`microscopy_img_analyst` + `gel_blot_analyst` | `gpt-6.1-sol` | `0.9130 -> 0.9130` (`1.00, 0.83`) | `F -> F` | `3.40M ->` **`10.33M (3.04x)`** | `628.2s ->` **`1256.9s (2.00x)`** | **`245 / 47`** | **`37 -> 56`** | **`6`** | 单实例 `GIMP` 双 `.xcf` 标签与缩放弹窗抢焦，耗费 **`10.33M` Token** 与 **`20.9m`（重叠 `96.5%`）** 反复核验 PNG 像素自愈 |
| **`AW-14`** | 同上 | `gpt-6-astra` | **`0.9130 -> 0.3098`** (`0.38, 0.24`) | `F -> F` | `3.89M ->` **`7.38M (1.90x)`** | `598.2s ->` **`1021.8s (1.71x)`** | **`218 / 36`** | `45 -> 43` | **`27`** | **`27` 次并发按键误路由**打断 `GIMP` 图层隐藏与 `Image -> Scale Image (600x400)` 模态框，双角色导出图残留伪影标尺 |
| **`AW-15`** | `Qt5 Designer` + `Qt5 Linguist` + `lrelease` + `Chromium`<br>`dialysis_ui_eng` + `dialysis_l10n_eng` | `gpt-6.1-sol` | `0.8804 -> 1.0000` (`1.00, 1.00`) | `F -> T` | `4.53M -> 4.91M` (`1.08x`) | `860.4s ->` **`1060.0s (1.23x)`** | `178 / 20` | `17 -> 14` | **`6`** | 经历 `6` 次误按键与 `695.2s` 并发重叠后用 `lrelease` 校验补齐全部 8 条德语翻译 |
| **`AW-15`** | 同上 | `gpt-6-astra` | **`1.0000 -> 0.5788`** (`0.75, 0.41`) | **`T -> F`** | `3.24M ->` **`5.44M (1.68x)`** | `559.9s ->` **`1001.0s (1.79x)`** | `198 / 14` | **`10 -> 15`** | **`5`** | `Designer` 控件属性编辑与 `Linguist` 词条输入框互抢键盘焦点，导致 `dialysis_de.ts` 仅 `4/8` 词条生效 |
| **`AW-19`** | `LibreOffice Calc` + `LibreOffice Writer` + `Chromium` + `SQLite`<br>`dc_capex_controller` + `msa_commercial_counsel` | `gpt-6.1-sol` | **`0.8944 -> 0.7084`** (`0.75, 0.67`) | `F -> F` | `4.56M ->` **`7.93M (1.74x)`** | `662.5s ->` **`1232.8s (1.86x)`** | `190 / 68` | `24 -> 23` | **`4`** | CLI 调用暴涨 **`5.67x`**、重叠 **`882.4s (14.7m)`**；单实例 `soffice.bin` 双窗口并发切换与保存导致 `Writer` 第 9 节 `2.75x` 红线遗失 |
| **`AW-19`** | 同上 | `gpt-6-astra` | **`0.9445 -> 0.7084`** (`0.75, 0.67`) | **`T -> F`** | `4.76M ->` **`6.96M (1.46x)`** | `691.4s ->` **`1154.4s (1.67x)`** | `199 / 35` | **`22 -> 38`** | **`17`** | **`38` 次焦点翻转 + `17` 次误按键**：`Calc` 32 格录入与 `Writer` 查找替换弹窗互抢焦点，双模型复现同构红线丢失 |
| **`AW-20`** | `FreeCAD 0.20` + `GIMP 2.10` + `LibreOffice Calc` + `Chromium`<br>`front_bezel_overlay_eng` + `rear_vesa_chassis_eng` | `gpt-6.1-sol` | `1.0000 -> 1.0000` (`1.00, 1.00`) | `T -> T` | `5.67M ->` **`7.39M (1.30x)`** | `703.9s ->` **`1097.8s (1.56x)`** | `177 / 39` | `34 -> 31` | **`14`** | 承受 `14` 次误按键与 `723.4s` 并发重叠，以 `+56%` 墙钟耗时完成三维布尔、双图层导出与悬臂配重协调 |
| **`AW-20`** | 同上 | `gpt-6-astra` | **`1.0000 -> 0.9352`** (`1.00, 0.87`) | `T -> T` | `5.39M ->` **`8.45M (1.57x)`** | `693.0s ->` **`1409.2s (2.03x)`** | **`238 / 28`** | **`37 -> 55`** | **`6`** | 四窗口叠压引发 **`55` 次焦点翻转**（耗时翻倍至 `23.5m`），`Calc` 活动工作表焦点偏移致 `Rear_Assy!B3/B5` 未写入 |

---

## 四、复现命令与目录索引

```bash
# 1. 静态反模式与 Harness 隔离审计（预期 24 PASS | 0 FAIL | 0 WARN）
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py tasks/authentic_workstation_v1
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py experiments/authentic_workstation_v1.py

# 2. 单元测试
python3 -m unittest -v tests/test_authentic_workstation_v1.py

# 3. 优选 Top-5 确定性五门禁验证（零 LLM 调用）
python3 -m experiments.authentic_workstation_v1 --mode self_validate --retained-only \
  --workers 2 --code-root . --out /tmp/aw_v1_selfval

# 4. 优选 Top-5 单角色隔离基线 vs 双角色共享桌面评测
python3 -m experiments.authentic_workstation_v1 --mode isolated --retained-only \
  --workers 2 --code-root . --out /tmp/aw_v1_eval --api-json /path/to/api.json --codex-bin /path/to/codex --effort high
python3 -m experiments.authentic_workstation_v1 --mode shared --retained-only \
  --workers 2 --code-root . --out /tmp/aw_v1_eval --api-json /path/to/api.json --codex-bin /path/to/codex --effort high
```
