# `authentic_workstation_v1`：真实开源软件套件审阅修订、零乘数重算与 Top-5 双模型复验报告（2026-11-25）

## 一、核心结论与审阅反馈全量修复总览

围绕新版 `$paragui-case-design` 规范与针对 `AW-12, AW-14, AW-15, AW-19, AW-20` 的底层评分审计反馈，本轮在保持 **100% 真实开源桌面/Web 软件** 与 **`Xvfb -auth` + `UID 2000` 密封容器沙盒** 的基础上，完成了全部三类共性问题与逐题瑕疵的修复，并对 **Top-5 共 20 局（40 个 Non-YOLO 容器智能体）** 重新执行了确定性五门禁验证与双模型（`gpt-6.1-sol` + `gpt-6-astra`，`effort = high`）端到端实测。

### 1.1 根据审阅反馈落地的五项精确修复

1. **彻底移除 `common.py` 中的 `j_mult = 0.75` 不对称全局乘数与重复连坐项**：在 [`common.py`](../tasks/authentic_workstation_v1/common.py) 的 `build_aw_grade_payload()` 中删除了 `j_mult = 0.75 + 0.25 * sc_j`，使 `score_a`、`score_b` 与 `mean_score` 在 `isolated`、`seq_ab`、`seq_ba` 与 `shared` 四个模式下拥有 **100% 完全相同的子项权重与分母**；`checks_joint` 仅保留真正的跨角色耦合与共享制品共存断言，用于门控二值 `joint_pass` 并单独输出 `score_joint`，杜绝单角色旧错在并发模式下被二次乘以 `0.75` 放大为假跌分。
2. **全面开启 `mount_studio_ro: True`（`/srv/studio_project` 只读挂载进 `guest_bash`）**：在 `AW-14, AW-15, AW-19, AW-20` 中统一开启 `mount_studio_ro: True` 并将 `/srv/studio_project` 设为 `0755`（原始 `.xcf` 母版仍保存在 `0700` 的 `/opt/aw*_masters` 防 CLI `gimp -i -b` 批处理绕过）。智能体在终端可执行 `ls /srv/studio_project`、用 `lrelease` 真实编译校验 `dialysis_de.ts`、用 `openpyxl/zipfile/PIL` 只读核对 GUI `Ctrl+S` 落盘结果，而所有写操作因 VFS `:ro` 挂载（`EROFS`）仍必须经由桌面真实 GUI 窗口完成，彻底消除了 VDI 路径不可见的违和感。
3. **修复 `AW-14` 与 `AW-19` 两处 `0/4` 单点判分瑕疵**：
   - **`AW-14`**：将 `b_svg_panel_b` 的硬编码 `"2.88"` 字符串匹配改为正则浮点数扫描 `_svg_has_float(svg_txt, 2.875, tol=0.025)`（同时兼容 `"2.875"`、`"2.88"`、`"2.87"`），并统一 `TICKET_A`、`TICKET_B` 与 `boot_apps` 的海报路径为 `/workspace/assay/poster_layout.svg`。
   - **`AW-19`**：排查 `actions.jsonl` 确认此前 `b_writer_s9` 单人 `0/2` 的精确原因是文档行已含 `"Super-Cap Multiple: "` 前缀，模型合理填入 `"2.75"` 而旧判分器写死 `"2.75x"`；现改为正则 `r"\b2\.75x?\b"`，并将 `Master_Services_Agreement.odt` 升级为第 4 节 5 处 + 第 9 节 5 处共 **10 处结构化红线占位符**。
4. **移除 `AW-14` / `AW-15` 题面内联公式并将 SQLite 扩充至 48–72 行真实规模**：
   - `AW-14`：移除题面 Beer-Lambert 公式，将 `plate_readings.sqlite` 扩充至 **72 行**（`48` 孔酶标仪 `cuvette_od` 含 `BUBBLE_ARTIFACT / SATURATED_OVERFLOW` 质控剔除项 + `24` 泳道 Western Blot 含 `HEMOLYZED_EXCLUDE` 剔除项）。
   - `AW-15`：移除题面 `tmp_mmhg` 公式与控件数值清单（移入 `IEC60601_Dialysis_Spec.pdf` 与门户），将 `patient_runs.sqlite` 由 3 行扩充至 **48 条临床透析记录**（`36` 条合规 `ACUTE_ICU_HD` + `8` 条 `CRRT_CVVHDF` + `4` 条 `ABORTED_CLOT`）。
   - `AW-19`：将 `procurement.sqlite` 扩充至 **56 条采购/租约分项明细**（`32` 条硬件 PO 行含 `CANCELLED_VOID` + `24` 条机房租约分期含 `DRAFT_UNEXECUTED`），门户费率表升级为视觉蓝图卡。
5. **`AW-12` 升级为模块化双子路由 SPA 架构**：将单文件 `index.html` 拆分为共享 SPA 外壳（`index.html + styles.css`）挂载独立子路由文件 `modules/orders_module.js` 与 `modules/capacity_module.js`，并用真实 DOM 点击注入替代隐藏 URL 参数评测，彻底消除了此前 `Astra` 在 `shared` 下借同伴脚手架从 `0.73` 反升至 `1.00` 的正偏互助。

---

## 二、修复后 Top-5 双模型复验核心结论（零 `j_mult` 真实子项口径）

修复后，`audit_case_module.py` 静态审计 **`24/24 PASS | 0 FAIL | 0 WARN`**，五门禁复验 **`5/5`（`25/25` 局）全通过**（`Gate 5` 耗时 `0.17s–8.72s`）。在 **20 局（40 个 Non-YOLO 容器智能体，`permission_audit_ok = 40/40`）** 复验中，最显著的变化是：**此前所有单点判分误杀与正偏倒挂全部清零——双模型在全部 10 局 `isolated` 单人基线中取得 `10/10` 满分（`1.0000`，单局耗时 `6.5–14.1m`，`75–195` 次 GUI 调用），而在 `shared` 并发模式下产生纯净、无乘数放大的真实准确率下降**：

| 模型（`effort = high`） | `isolated` 均分 | `shared` 均分 | **真实无乘数 `ΔScore`** | `joint_pass` (`iso -> shr`) | 输入 Token 膨胀比 | 墙钟耗时膨胀比 | GUI / CLI 膨胀比 | 平均并发重叠 | 焦点翻转 (`iso -> shr`) | 误路由按键 (`iso -> shr`) | 非 YOLO 审计 |
|---|---:|---:|---:|---|---:|---:|---|---:|---|---|---|
| **`gpt-6.1-sol`** | **`1.0000`** | **`0.9163`** | **`-0.0837 (-8.37%)`** | **`100% (5/5) -> 80% (4/5)`** | **`1.769x`** | **`1.580x`** (`580.7s -> 862.0s`) | `1.34x / 1.85x` | `571.7s` | `97 -> 123` | `0 -> 30` | `20/20 PASS` |
| **`gpt-6-astra`** | **`1.0000`** | **`0.8802`** | **`-0.1198 (-11.98%)`** | **`100% (5/5) -> 60% (3/5)`** | **`1.655x`** | **`1.949x`** (`554.2s -> 1026.6s`) | `1.43x / 1.95x` | `643.6s` | **`88 -> 136`** | `0 -> 38` | `20/20 PASS` |

---

## 三、逐案例复验明细与 `mount_studio_ro` 消融洞察

完整逐局成绩单（同时保留修复前 `v1` 无乘数重算对照）见 [`results-manifests/authentic_workstation_v1_top5_sol61_astra_20261124.json`](results-manifests/authentic_workstation_v1_top5_sol61_astra_20261124.json)。

| Case ID | 真实软件栈与修订要点 | 模型 | `Score_iso -> Score_shr`（`A, B`） | `joint_pass` | **`ΔScore`** | 输入 Token (`iso -> shr`) | 墙钟耗时 (`iso -> shr`) | GUI / CLI (`shr`) | 焦点翻转 (`iso -> shr`) | 误按键 (`shr`) | 复验实测机理与结论 |
|---|---|---|---|---|---:|---|---|---|---|---|---|
| **`AW-12`** | `Chromium` (`HttpOnly`) + 双子路由 SPA (`orders_module.js` / `capacity_module.js`) | `gpt-6.1-sol` | **`1.0000 -> 0.9307`** (`0.86, 1.00`) | `T -> T` | **`-0.0693`** | `3.49M -> 3.50M` (`1.00x`) | `555.2s -> 508.9s` | `113 / 26` | `6 -> 0` | `0` | 共享 `Chronos ERP` 路由切换干扰下，`orders_module.js` 漏采 `$450/hr` SLA 弹窗元数据 |
| **`AW-12`** | 同上 | `gpt-6-astra` | `1.0000 -> 1.0000` (`1.00, 1.00`) | `T -> T` | `0.0000` | `2.09M ->` **`3.82M (1.83x)`** | `433.5s -> 501.9s` (`1.16x`) | `106 / 32` | `6 -> 6` | `0` | 拆分双路由模块后 `isolated` 升至 `1.00`，彻底消除 `+26.9%` 正偏，并发耗费 **`+83%` Token** |
| **`AW-14`** | `GIMP 2.10` + `Inkscape 1.2` + `72` 行 SQLite + `2.875` 容差 + `mount_studio_ro` | `gpt-6.1-sol` | `1.0000 -> 1.0000` (`1.00, 1.00`) | `T -> T` | `0.0000` | `2.24M ->` **`7.16M (3.20x)`** | `388.0s ->` **`987.6s (2.55x)`** | **`205 / 29`** | **`25 -> 47`** | `0` | `isolated` 修复至双满分；并发在只读校验辅助下耗费 **`3.20x` Token、`2.55x` 耗时、`47` 次翻转**自愈 |
| **`AW-14`** | 同上 | `gpt-6-astra` | **`1.0000 -> 0.6848`** (`0.37, 1.00`) | **`T -> F`** | **`-0.3152`** | `1.92M ->` **`6.20M (3.23x)`** | `396.0s ->` **`1485.3s (3.75x)`** | **`191 / 30`** | **`24 -> 43`** | **`14`** | 单实例 `GIMP` 标签与 `Scale Image` 模态框互抢焦点（`14` 次误按键），耗时逼近 `25m` 上限致 Role A 导出图损坏 |
| **`AW-15`** | `Qt5 Designer` + `Qt5 Linguist` + `lrelease` + `48` 行 SQLite + `mount_studio_ro` | `gpt-6.1-sol` | **`1.0000 -> 0.7065`** (`1.00, 0.41`) | **`T -> F`** | **`-0.2935`** | `2.58M ->` **`5.20M (2.01x)`** | `408.9s ->` **`674.7s (1.65x)`** | `190 / 22` | **`6 -> 18`** | **`20`** | 即便开放只读 `lrelease` 核验，**`20` 次并发误按键**仍打断 `Linguist` 录入（仅 `4/8` 生效）并覆写 `release_gate.json` |
| **`AW-15`** | 同上 | `gpt-6-astra` | **`1.0000 -> 0.7717`** (`1.00, 0.54`) | **`T -> F`** | **`-0.2283`** | `3.24M ->` **`4.59M (1.42x)`** | `569.1s ->` **`744.6s (1.31x)`** | `185 / 15` | **`12 -> 33`** | **`13`** | **双模型同步跌穿 `joint_pass`**：`33` 次切窗与 `13` 次误按键导致 `dialysis_de.ts` 仅 `4/8` 词条完成 |
| **`AW-19`** | `LibreOffice Calc` + `Writer` 10 处红线 + `56` 行 SQLite + `2.75` 修复 + `mount_studio_ro` | `gpt-6.1-sol` | **`1.0000 -> 0.9445`** (`0.89, 1.00`) | `T -> T` | **`-0.0555`** | `6.23M -> 6.77M` (`1.09x`) | `848.7s ->` **`1052.7s (1.24x)`** | `157 / 55` | `23 -> 14` | `3` | 单人 `b_writer_s9` 升至 `1.00`；**去掉 `j_mult` 后仍产生真实 `-5.55%` 并发掉分**（`Writer` 第 4 节红线被并发抢焦冲掉，CLI 膨胀 `2.75x`） |
| **`AW-19`** | 同上 | `gpt-6-astra` | **`1.0000 -> 0.9445`** (`1.00, 0.89`) | `T -> T` | **`-0.0555`** | `4.22M -> 2.85M` | `665.3s ->` **`1501.6s (2.26x)`** | **`203 / 26`** | **`12 -> 23`** | **`6`** | **双模型对称真实掉分 `-5.55%`**：`203` 次 GUI 调用与 `23` 次焦点翻转耗尽 `25m` 预算，第 9 节红线未写完 |
| **`AW-20`** | `FreeCAD 0.20` + `GIMP 2.10` + `Calc` 悬臂配重 + 视觉蓝图 + `mount_studio_ro` | `gpt-6.1-sol` | `1.0000 -> 1.0000` (`1.00, 1.00`) | `T -> T` | `0.0000` | `5.20M ->` **`8.02M (1.54x)`** | `702.5s ->` **`1086.2s (1.55x)`** | **`211 / 33`** | **`37 -> 44`** | **`7`** | 经历 `44` 次切窗与 `7` 次误按键，靠只读复核 `/srv/studio_project/ISO13485_DHR_Checklist.xlsx` 以 `+54%` Token 自愈 |
| **`AW-20`** | 同上 | `gpt-6-astra` | `1.0000 -> 1.0000` (`1.00, 1.00`) | `T -> T` | `0.0000` | `4.48M -> 5.05M` (`1.13x`) | `707.0s ->` **`899.6s (1.27x)`** | `153 / 34` | `34 -> 31` | **`5`** | **关键消融对照**：此前未开 `mount_studio_ro` 时 `Astra` 漏存 `Rear_Assy!B3/B5`（`0.9352`）；开放只读挂载后模型在 CLI 读表发现漏写并回到 `Calc` 补存（CLI `1.89x`） |

---

## 四、复现命令

```bash
# 1. 静态反模式与 Harness 隔离审计（24 PASS | 0 FAIL | 0 WARN）
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py tasks/authentic_workstation_v1
python3 ~/.codex/skills/paragui-case-design/scripts/audit_case_module.py experiments/authentic_workstation_v1.py

# 2. 单元测试（含无乘数评分契约断言）
python3 -m unittest -v tests/test_authentic_workstation_v1.py

# 3. Top-5 确定性五门禁验证
python3 -m experiments.authentic_workstation_v1 --mode self_validate --retained-only \
  --workers 2 --code-root . --out /tmp/aw_v1_selfval
```
