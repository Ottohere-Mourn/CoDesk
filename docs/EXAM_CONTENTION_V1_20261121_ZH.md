# 闭卷自检 + 离线盲评双智能体真实桌面竞争套件 `exam_contention_v1`（`EC-01..EC-05`）设计与 `gpt-6.1-sol` / `gpt-6-astra` 实测报告

更新日期：2026-11-21
所在分支：`codex/all-codesk-cases-20261113`
遵循规范：`$paragui-case-design`（Exam-Style Self-Check + Blind Final Grading 闭卷自检与离线盲评架构）
实测集群：`g4-45`（96 核 Xeon + 866 GiB RAM + Non-YOLO Docker）与 `cpu15`（32 核 + 125 GiB RAM），全部 20 组实机结果与动作轨迹已持久化归档至 `cpu15:~/data/paraGUI/runs/exam-contention-v1-live-20261120/` 及本仓库 [`docs/results-manifests/exam_contention_v1_sol61_astra_20261121.json`](results-manifests/exam_contention_v1_sol61_astra_20261121.json)

---

## 一、设计动机与 `$paragui-case-design` 闭卷架构契约

针对早期多智能体竞争套件中曾出现的四类机制污染（上游禁写与首笔提交死锁、后台隐藏采样器与鸽巢超时死锁、在线 `HTTP 422` 判题器泄题、以及四行玩具文档与木偶按键提示词），我们严格依据 `$paragui-case-design` 技能规范重新构建了 **`exam_contention_v1`（`EC-01..EC-05`）** 五大跨行业混合（`GUI + CLI`）双智能体竞争基准：

1. **零在线判题器泄题与 100% 离线盲评（Blind Offline `grade()`）**：
   - 环境内完全移除任何返回跨角色耦合误差或金丝雀真值的 `/api/bench` 与 `/submit` 在线判题端点；所有标准答案比对、跨角色预算/流体/预紧力耦合断言以及文档一致性核查 100% 置于跑局结束后的离线 `grade()` 中。
   - 环境内的所有软件（LibreOffice Calc/Writer、FreeCAD、Inkscape、GDAL/OGR、SQLite、Git、在线结算守护进程与 `HttpOnly` SSO 门户）均完全诚实透明，仔细核查的智能体可在环境内独立完成全部自检。
2. **零空转休眠注水与五门禁良定性验证（5-Gate Deterministic Well-Posedness）**：
   - 彻底废除 `while time.monotonic() - t0 < ...` 空转循环、`BackgroundRegimeSampler` 与 `FAST_SELFVAL` 时钟扭曲；所有工具均以真实原生速度执行。
   - 静态合规审计器 `audit_case_module.py` 扫描 `tasks/exam_contention_v1/`（6 个文件）与 `experiments/exam_contention_v1.py`（1 个文件），取得 **`7 / 7 PASS | 0 FAIL | 0 WARN`**。
   - 五道确定性数学良定性门禁（`Gate 1 pristine_fail == False`、`Gate 2 gt_seq_ab == True`、`Gate 3 gt_seq_ba == True`、`Gate 4 gt_naive_race == False`、`Gate 5 gt_careful_conc == True`）在 `EC-01..EC-05` 上 **5 / 5 全部通过**，且真实耗时下 `Gate 5` 仅需 **`14.62s – 37.33s`**（仅占并发时限 `1800s` 的 **`0.8% – 2.1%`**，远低于 `<= 55%` 门限，彻底杜绝超时死锁）。
3. **GUI 驱动解耦与真实 OS 级共享原语竞争**：
   - 所有角色工单（`task.md`）零硬编码 MCP 工具名、零同伴剧透、零木偶撤销指令（`FORBIDDEN_EXAM_PATTERNS` 零命中），可直接挂载不同 CUA/语义驱动做消融对比。
   - 每个任务在 `1920x1080` X11 桌面上同时拉起左半屏 **`HttpOnly` 单点登录（SSO）业务门户**（进程隔离于 `studio_ui` 用户，阻断读取 Cookie 旁路）与右半屏 **持有未落盘内存控制标签的原生 `LibreOffice Calc / Writer` 活动窗口**（共享 `.~lock.*` 与 `/home/gui/.config/libreoffice` 单例锁），同时在伴生角色容器中关闭 CLI `xdotool`/`xmessage` 注入，迫使窗口交互、剪贴板粘贴与门户切换走真实桌面 GUI。
4. **前沿双模型（20 局 Non-YOLO 实测）核心结论**：
   - **`gpt-6.1-sol (high)`**：串行基线（`seq_ab`）联合通过率 **`3 / 5 (60.0%)`**（角色通过率 `8 / 10 = 80.0%`，非饱和真实难度），双并发（`shared`）联合通过率跌至 **`1 / 5 (20.0%)`**（角色通过率 `6 / 10 = 60.0%`），**并发净跌 `-40.0` 个百分点**。
   - **`gpt-6-astra (high)`**：串行基线（`seq_ab`）联合通过率 **`5 / 5 (100.0%)`**（角色通过率 `10 / 10 = 100.0%`），双并发（`shared`）联合通过率跌至 **`3 / 5 (60.0%)`**（角色通过率 `8 / 10 = 80.0%`），**并发净跌 `-40.0` 个百分点**。
   - **双模型合计（20 局、40 角色）**：串行联合通过率 **`8 / 10 (80.0%)`** -> 双并发联合通过率 **`4 / 10 (40.0%)`**（**相对竞争折损整整减半**，且保留了谨慎复核智能体在共享冲突下自检恢复的真实区分度）。

---

## 二、5 项手工定制场景与五门禁确定性良定性验证总表（5 / 5 全通）

结构化五门禁验证清单见 [`docs/results-manifests/exam_contention_v1_5gate_selfval_20261120.json`](results-manifests/exam_contention_v1_5gate_selfval_20261120.json)。

| ID | 业务/工程领域与双角色（`Role A` / `Role B`） | 桌面原生 GUI 与工程软件栈 | 核心共享竞争原语与双向耦合约束 | Gate1 `pristine` | Gate2 `seq_ab` | Gate3 `seq_ba` | Gate4 `naive_race` | Gate5 `careful_conc` (真实耗时 / 预算占比) |
|---|---|---|---|---|---|---|---|---|
| `EC-01` | 跨国并购（M&A）财务尽调数据室与净杠杆契约<br>`qoe_ebitda_lead` / `tax_treasury_lead` | LibreOffice Calc (`.xlsx` + PDF) + SQLite (`2,650` 行总账) + Chromium SSO VDR (`:18801`) + 5 份扫描审计底稿 | 活动 Calc 内存脏缓冲 vs CLI 落盘脑裂 + LibreOffice 单例 Profile 锁 + VDR `AVG_2026_PL` vs `SPOT_CLOSE_BS` 汇率切换与 `vdr_schedule.csv` 覆写 + X11 剪贴板签章 + `[3.03, 3.09]x` 净杠杆契约 | `False` | **`True`** | **`True`** | `False` | **`True`** (`37.33s` / `2.1%`) |
| `EC-02` | 肿瘤内科第 4 周期联合化疗与肾脏支持给药核对<br>`chemo_regimen_pharmacist` / `renal_supportive_pharmacist` | LibreOffice Writer (`.odt` + PDF) + SQLite (`24` 例住院患者医嘱库) + Chromium SSO EHR (`:18802`) + 3 份临床列线图扫描件 | 活动 Writer `.odt` 内存脏缓冲脑裂 + EHR `CONV_MG_DL` vs `SI_UMOL_L` 检验单位切换与 `ehr_renal_cbc_panel.csv` 覆写 + X11 剪贴板药师核签章争抢 + 心衰患者 24h 静脉总液量 `[1640, 1710] mL` 耦合 | `False` | **`True`** | **`True`** | `False` | **`True`** (`14.62s` / `0.8%`) |
| `EC-03` | 1U 通信机箱三维钣金开孔、EMC 屏蔽与丝印印前制版<br>`mech_thermal_eng` / `emi_prepress_eng` | FreeCAD (`.FCStd` / `.step` 双实体 B-Rep) + Inkscape (`.svg` -> `1760x360` PNG) + LibreOffice Calc (`.xlsx`) + SSO PLM (`:18803`) | 单体 `.FCStd` ZIP 与 `.step` 装配体丢失更新 + PLM 公制 `mm` vs 英制 `mil` 切换与目录 CSV 覆写 + X11 剪贴板 ECN 签章 + 活动 Calc 紧固件/导电衬垫预紧力 `[244, 252] Ncm` 窗口 | `False` | **`True`** | **`True`** | `False` | **`True`** (`24.64s` / `1.4%`) |
| `EC-04` | 多币种清算网关割接、HMAC 防重放账本与头寸对账<br>`clearing_engine_dev` / `dispute_security_dev` | Git (`main`) + 在线清算守护进程 (`:18910`) + SQLite WAL + LibreOffice Calc (`.xlsx`) + SSO 清算运营台 (`:18804`) | 共享 Git 工作树与 `app/server.py` 合并及 `:18910` 单端口重启竞争 + 运营台 `TREASURY_WHOLESALE_BPS` vs `NATIVE_EXACT` 导出覆写 + X11 剪贴板割接令牌 + 活动 Calc 监管流动性缓冲 `[78600, 80800] USD` | `False` | **`True`** | **`True`** | `False` | **`True`** (`20.81s` / `1.2%`) |
| `EC-05` | 县域流域行蓄洪区与光伏微电网空间规划环评（EIS）<br>`solar_microgrid_planner` / `stormwater_hydrology_planner` | GDAL/OGR SpatiaLite (`.gpkg` 24 地块 + 湿地) + QGIS (`.qgz`) + LibreOffice Calc (`.xlsx`) + SSO 洪水位滑块门户 (`:18805`) | `.gpkg` 多图层并发改写与跨图层 `150m` 欧氏退界 + 连续拖拽洪水位滑块（光伏 `118 ft` vs 滞洪溢洪道 `122 ft`）与 CSV 覆写 + X11 剪贴板许可章 + Calc 与 `.qgz` 市政绿债 `[17750, 18150] kUSD` 同步 | `False` | **`True`** | **`True`** | `False` | **`True`** (`22.72s` / `1.3%`) |

---

## 三、`gpt-6.1-sol (high)` 与 `gpt-6-astra (high)` 串行 vs 并发实测汇总

全部 20 局（40 个容器化智能体实例）均运行于 `paragui/codex-sandbox:20261113` 非 YOLO 隔离沙盒（`all_non_yolo_verified = True` 100% 验证通过）。

| 模型与运行模式 | 联合通过数 (`joint_pass`) | Role A 通过数 | Role B 通过数 | 单角色总通过率 | 平均单局墙钟时长 | 平均 GUI 调用数 | 平均 CLI 调用数 | 相对串行竞争折损 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **`gpt-6.1-sol (high)` — `seq_ab`（串行基线）** | **`3 / 5 (60.0%)`** | `5 / 5` | `3 / 5` | `8 / 10 (80.0%)` | `754.28s (12.6m)` | `79.4` | `33.2` | — |
| **`gpt-6.1-sol (high)` — `shared`（双并发）** | **`1 / 5 (20.0%)`** | `2 / 5` | `4 / 5` | `6 / 10 (60.0%)` | `687.11s (11.5m)` | `81.8` | `62.0` | **联合 `-40.0%`（角色 `-20.0%`）** |
| **`gpt-6-astra (high)` — `seq_ab`（串行基线）** | **`5 / 5 (100.0%)`** | `5 / 5` | `5 / 5` | `10 / 10 (100.0%)` | `739.48s (12.3m)` | `74.6` | `37.4` | — |
| **`gpt-6-astra (high)` — `shared`（双并发）** | **`3 / 5 (60.0%)`** | `4 / 5` | `4 / 5` | `8 / 10 (80.0%)` | `640.01s (10.7m)` | `84.6` | `64.6` | **联合 `-40.0%`（角色 `-20.0%`）** |
| **双模型合计 — `seq_ab`（10 局）** | **`8 / 10 (80.0%)`** | `10 / 10` | `8 / 10` | `18 / 20 (90.0%)` | `746.88s (12.4m)` | `77.0` | `35.3` | — |
| **双模型合计 — `shared`（10 局）** | **`4 / 10 (40.0%)`** | `6 / 10` | `8 / 10` | `14 / 20 (70.0%)` | `663.56s (11.1m)` | `83.2` | `63.3` | **联合 `-40.0%`（通过率减半）** |

---

## 四、20 局逐题实测对照与并发竞争归因取证

| 任务 ID | 模型 | `seq_ab` 串行结果（角色明细 / 交互 / 时长） | `shared` 双并发结果（角色明细 / 交互 / 竞争遥测 / 时长） | 真实并发失效机制与恢复行为取证 |
|---|---|---|---|---|
| `EC-01` | `gpt-6.1-sol` | **FAIL** (`A:PASS, B:FAIL`，`79`G+`38`C，`954.8s`)<br>单人难点：`B` 误算远期结汇违约金 `B5=1217.9 != 1110.0` | **FAIL** (`A:FAIL, B:PASS`，`105`G+`83`C，切屏 `8`、**CSV 覆写 `9` 次**、剪贴板 `6` 次，`905.0s`) | **共享下载与汇率切换污染**：并发下 `B` 将数据室切至 `SPOT_CLOSE_BS` 并与 `A` 反复互覆 `~/Downloads/vdr_schedule.csv` 达 9 次，致 `A` 混入即期汇率算出 `QoE_Bridge!B6=-571.2 != -657.0` |
| `EC-01` | `gpt-6-astra` | **PASS** (`A:PASS, B:PASS`，`107`G+`41`C，`1215.1s`) | **PASS** (`A:PASS, B:PASS`，`77`G+`88`C，切屏 `6`、CSV 覆写 `2` 次，`779.7s`) | **自检恢复**：双角色核对了导出汇率行与活动 Calc 工作簿中的对方债务分档，收敛至 `3.0600x` 净杠杆并保持各自 PDF 一致 |
| `EC-02` | `gpt-6.1-sol` | **PASS** (`A:PASS, B:PASS`，`64`G+`25`C，`516.8s`) | **FAIL** (`A:PASS, B:FAIL`，`77`G+`60`C，**切屏 `18` 次**、CSV 覆写 `3` 次、剪贴板 `7` 次，`811.2s`) | **活动 Writer 协议与 PDF 导出交错**：`B` 导出 `Supportive_Care_Signoff.pdf` 时，共享 `.odt` 缓冲正被同伴改写保存，导致导出的签收单丢失有效 `RENAL_SUPPORT_ATTESTATION_SEAL` |
| `EC-02` | `gpt-6-astra` | **PASS** (`A:PASS, B:PASS`，`48`G+`25`C，`461.4s`) | **FAIL** (`A:FAIL, B:PASS`，`46`G+`43`C，**切屏 `10` 次**、CSV 覆写 `2` 次、剪贴板 `3` 次，`372.1s`) | **X11 剪贴板与 EHR 会话抢占**：`A` 在 EHR 点击复制签章后准备向 LibreOffice Writer 粘贴期间，门户被 `B` 切至 `RENAL_SUPPORTIVE/SI_UMOL_L`，致 `.odt` 与 `Chemo_Dispense_Signoff.pdf` 缺失合法化疗核签章 |
| `EC-03` | `gpt-6.1-sol` | **FAIL** (`A:PASS, B:FAIL`，`89`G+`34`C，`802.1s`)<br>单人难点：`B` 漏标 SVG 图层 ID | **FAIL** (`A:FAIL, B:PASS`，`74`G+`43`C，切屏 `9`、CSV 覆写 `3` 次、剪贴板 `6` 次，`503.0s`) | **PLM 公英制切换与 CAD 几何越界**：并发切屏下 `B` 完成全部后背板开孔与 SVG 印前交付（`B:PASS`），而 `A` 在顶盖散热槽建模中侵入禁布区 `112.0 mm^3` |
| `EC-03` | `gpt-6-astra` | **PASS** (`A:PASS, B:PASS`，`74`G+`41`C，`649.7s`) | **FAIL** (`A:PASS, B:FAIL`，`43`G+`62`C，切屏 `7`、CSV 覆写 `3` 次、剪贴板 `5` 次，`398.8s`) | **PLM 视图/单位抢占与装配竞争**：串行下 `astra` 双角色满分通过；双并发下门户在 `CATALOG` 与 `DRAWINGS`、`mm` 与 `mil` 间切换 7 次，`B` 后背板开孔面积偏至 `1692.0 mm^2` 且遗漏前面板 SVG 组标签 |
| `EC-04` | `gpt-6.1-sol` | **PASS** (`A:PASS, B:PASS`，`118`G+`51`C，`1110.3s`) | **PASS** (`A:PASS, B:PASS`，`88`G+`76`C，切屏 `10`、剪贴板 `8` 次、**察觉 `2/2`**，`775.9s`) | **Git 提交历史感知与合并恢复**：双角色在操作共享 Git `main` 分支与 `:18910` 守护进程时通过 `git log`/`git status` 发现同伴提交，主动合并 `app/server.py` 并重算 Calc 缓冲分档 |
| `EC-04` | `gpt-6-astra` | **PASS** (`A:PASS, B:PASS`，`96`G+`59`C，`1002.6s`) | **PASS** (`A:PASS, B:PASS`，`201`G+`86`C，切屏 `12`、CSV 覆写 `6` 次、**察觉 `2/2`**，`1293.4s`) | **高频 GUI 复核恢复**：面对 12 次运营台切换与 6 次队列 CSV 覆写，`astra` 投入 `201` 次 GUI 操作与 `86` 次 CLI 校验完成 Git 合并、双签章粘贴与资本缓冲配平 |
| `EC-05` | `gpt-6.1-sol` | **PASS** (`A:PASS, B:PASS`，`47`G+`18`C，`387.4s`) | **FAIL** (`A:FAIL, B:PASS`，`65`G+`48`C，**切屏 `14` 次**、剪贴板 `8` 次，`440.5s`) | **BFE 洪水位滑块与剪贴板错贴（铁证 `ATTEST-6E3EBBE0FAC9`）**：`A` 需 `118 ft` 光伏章、`B` 需 `122 ft` 滞洪章；双方拖拽同一滑块切换 14 次，`A` 将被污染的剪贴板签章 `ATTEST-6E3EBBE0FAC9` 粘入 `Solar_Siting!B3` 与 JSON |
| `EC-05` | `gpt-6-astra` | **PASS** (`A:PASS, B:PASS`，`48`G+`21`C，`368.6s`) | **PASS** (`A:PASS, B:PASS`，`56`G+`44`C，切屏 `8`、CSV 覆写 `3` 次，`356.1s`) | **空间退界与绿债同步恢复**：双角色避开 `PCL-15/16` 60m 退界冲突地段，分别选出合规 5 地块并同步 `.gpkg`、Calc 与 `county_master.qgz` |

---

## 五、复现命令与静态审计入口

```bash
# 1. 运行 $paragui-case-design 静态反模式与时间预算审计器（期望：7 files | 0 FAIL | 0 WARN）
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py CoDesk/tasks/exam_contention_v1
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py CoDesk/experiments/exam_contention_v1.py

# 2. 运行本地单元测试（目录多样性、提示词零禁词/零工具耦合、五门禁清单与实测清单校验）
PYTHONPATH=CoDesk pytest CoDesk/tests/test_exam_contention_v1.py

# 3. 运行 5-Gate 确定性良定性容器自验证（零 LLM 调用，真实工具速度）
PYTHONPATH=CoDesk python3 -m experiments.exam_contention_v1 \
  --mode self_validate --workers 5 --code-root CoDesk --out /tmp/ec_selfval

# 4. 运行串行基线（seq_ab / seq_ba）与双智能体共享桌面并发评测（shared）
CODESK_CODEX_CONTAINER_IMAGE=paragui/codex-sandbox:20261113 \
PYTHONPATH=CoDesk python3 -m experiments.exam_contention_v1 \
  --mode shared --tasks EC-01 EC-02 EC-03 EC-04 EC-05 --workers 2 \
  --code-root CoDesk --out /tmp/ec_live \
  --api-json /path/to/api.json --codex-bin /path/to/codex --effort high
```
