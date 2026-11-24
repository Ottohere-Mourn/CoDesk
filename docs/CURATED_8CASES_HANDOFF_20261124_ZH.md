# 精选 8 项高质量双智能体 GUI+CLI 竞争基准交付说明（`curated_8cases_v1`）

更新日期：2026-11-24
统一注册表：`tasks/curated_8cases_v1/registry.py`
统一评测与自检执行器：`experiments/curated_8cases_v1.py`
结构化清单：`lists/curated_high_quality_8cases_20261124.json`

## 一、筛选背景与本批 8 题构成

本套件从既有双智能体真实桌面（`GUI + CLI` 混合）候选题库中，按“单角色业务真实性、跨角色同机自洽、无隐式上下游空等锁、真实 OS/会话级竞争原语”标准精选出 **8 项高质量任务**（6 项 `shared` 共享进程/制品赛道 + 2 项 `isolated` 独立工作区共享屏幕赛道）：

| Case ID | 中文场景与双角色 | 底层源码路径 | 工作区模式 | 核心真实软件栈与底层竞争原语 | `gpt-6.1-sol (high)`（单人/串行 -> 并发） | `gpt-6-astra (high)`（单人/串行 -> 并发） |
|---|---|---|---|---|---|---|
| **`RBS3-04`** | 无 CDP ICU 互斥单位门户 + 16 床室速波形 + Calc/Writer 液量耦合<br>`vasopressor_pharmacist` / `ventilator_renal_lead` | `tasks/rb_osw2_synth_v3/rbs3_04_icu_sso_nomogram_soffice.py` | `shared` | 无 `:9222` Chromium `HttpOnly` 门户互斥单位切换 + `~/Downloads/icu_round_feed.csv` 同名互覆 + X11 剪贴板签章 + 单进程 `soffice.bin`（`Calc` + `Writer`）+ `[1900, 1908] mL` 窄耦合 | `0.9746 -> 1.0000`（墙钟 `330s -> 693s`，Token `2.20x`） | `0.9746 ->` **`0.8899`**（`A: 0.78, B: 1.00`，并发真实掉分） |
| **`RBS3-05`** | 无 CDP 硬件合规门户 + 8 区 PCB 热像 + `:19515` CAN-FD 守护进程 + Calc 功耗耦合<br>`thermal_power_eng` / `protocol_firmware_eng` | `tasks/rb_osw2_synth_v3/rbs3_05_ircam_firmware_gateway_calc.py` | `shared` | 无 `:9222` 合规门户模式切换 + `~/Downloads/board_compliance.csv` 互覆 + 在线 `:19515` 固件网关热修复重启 + 驻留 `LibreOffice Calc` + `[190.0, 190.8] W` TDP 耦合 | `1.0000 -> 1.0000`（耗时 `1.52x`，Token `1.92x`） | `1.0000 -> 1.0000`（耗时 `1.46x`，焦点翻转 `14 -> 24`） |
| **`RBS3-02`** | 单实例 `:9222` 4 断点响应式色带截屏 QA vs 8 幕全屏可见性扫描录制<br>`finops_viewport_auditor` / `orbit_reel_director` | `tasks/rb_osw2_synth_v3/rbs3_02_cdp_live_frames_vs_8scene_sweep.py` | `isolated` | 单实例 Chromium 窗口尺寸竞争（`375/768/1024/1440` 四视口像素截屏 vs `1920x1080` 无遮挡连续动态采样） | `1.0000 -> 1.0000`（墙钟 `218s -> 372s`） | `1.0000 -> 1.0000`（焦点翻转 `2 -> 5`） |
| **`RBS2-06`** | MailDesk 拉闸热力图与 RFC-5545 `.ics` 排期 vs 单实例 Calc 供应商 SLA 核算<br>`defense_scheduler` / `contract_automation_eng` | `tasks/rb_osw2_synth_v2/rbs2_06_maildesk_ics_vs_calc_contracts.py` | `shared` | 共享 `maildesk.sqlite` + `.ics` 日历排期 + 驻留 `LibreOffice Calc` 脏缓冲 + 同名 `Preferences` 模态框与系统剪贴板争用 | `0.9746 -> 1.0000`（并发触发 `7` 次误按键） | `1.0000 -> 1.0000`（焦点翻转 `10 -> 15`，`3` 次误按键） |
| **`RBS-06`** | CiteVault SQLite + BibTeX 勘误去重 vs 单进程 Writer+Calc 荟萃分析<br>`bib_manuscript_editor` / `evidence_quant_analyst` | `tasks/rb_osw2_synth_v1/rbs06_citevault_bibtex_soffice.py` | `shared` | 单进程 `soffice.bin` 同时打开 `Survey_Manuscript.odt` 与 `Evidence_Synthesis.xlsx` + 共享 `citevault.sqlite` + `~/Downloads/registry_feed.csv` 互覆 | `0.9520 -> 1.0000`（重叠 `303.7s`，CLI `36 -> 56`） | `0.9520 -> 1.0000`（并发 `7` 次误按键） |
| **`RBS3-01`** | 零剧透 5 表面探索复刻：SpectrumPad 音频 DSP vs PacketForge 抓包台<br>`spectrumpad_recreator` / `packetforge_recreator` | `tasks/rb_osw2_synth_v3/rbs3_01_zerospoiler_popovers_recreation.py` | `isolated` | 零剧透探索（启动向导 + `F10` 失焦自隐弹出菜单 + 同名 3 标签 `Preferences` + `F1` 弹窗）在共享 `:99` 触发真实焦点抢占与复刻窗口自撞 | **`0.9250 -> 0.7150`**（`Δ = -0.2100`，`B: 0.85 -> 0.43`） | **`0.9500 -> 0.8750`**（`joint_pass: T -> F`） |
| **`EC-01`** | 跨国并购尽调数据室、同名 CSV 导出互覆与 `[3.03, 3.09]x` 净杠杆契约<br>`qoe_ebitda_lead` / `tax_treasury_lead` | `tasks/exam_contention_v1/ec01_ma_dataroom_calc.py` | `shared` | `LibreOffice Calc` 驻留脏缓冲 + `SQLite` 2,650 行总账 + `HttpOnly` VDR 即期/平均汇率切换 + `~/Downloads/vdr_schedule.csv` 同名导出互覆 + 剪贴板签章 + 净杠杆双向契约 | `FAIL (A:T,B:F) -> FAIL (A:F,B:T)`（并发 9 次互覆 CSV 混入即期汇率） | `PASS -> PASS`（主动核对汇率行与同伴债务分档收敛至 `3.06x`） |
| **`EC-03`** | 1U 机箱三维钣金开孔、EMC 屏蔽与丝印制版耦合<br>`mech_thermal_eng` / `emi_prepress_eng` | `tasks/exam_contention_v1/ec03_enclosure_cad_emi.py` | `shared` | `FreeCAD` 单体 `.FCStd/.step` B-Rep 互覆 + `Inkscape` `.svg -> .png` 印前图层 + 驻留 `Calc` BOM + PLM 公英制切换与同名 `iec_enclosure_spec.csv` 导出 + `[246, 252] Ncm` 预紧力耦合 | `FAIL (A:T,B:F) -> FAIL (A:F,B:T)`（并发顶盖散热槽侵入禁布区） | **`PASS -> FAIL (A:T,B:F)`**（并发公英制切换 7 次致开孔面积偏离） |

## 二、统一评测底座加固项

通过 `tasks/curated_8cases_v1/registry.py` 与 `experiments/curated_8cases_v1.py` 统一入口运行时，自动启用以下评测加固（不破坏历史冻结成绩单）：

1. **解除低步数 GUI 截断**：统一将 `max_cua_calls` 安全上限提升至 `150`（消除旧批次 `42` / `65` 步上限对不同 CUA Driver 消融的干扰）。
2. **修复 `isolated` 单人基线的缺席角色误扣分**：对于 `shared` 多文档任务（如 `RBS-06`、`RBS3-04`、`EC-01`、`EC-03`），单人 `isolated` 评测结束后自动补齐缺席角色的参考解，再执行只读判分，消除缺席方未保存文档带来的假 `split_brain` 扣分。
3. **补齐跨容器守护进程 PID 命名空间共享**：`RBS3-05` 默认挂载 `--pid container:<desk>`，使角色容器可通过标准 `ps` / `kill` 管理 `:19515` 网关进程。
4. **纯只读考后判分与可选 X11 隔离消融**：`stop_and_grade()` 通过 UNO 只读探针检查内存脏态，不再向桌面注入考后 `Ctrl+S` 按键；支持 `--isolate-cli-from-x11` 在做纯 GUI Driver 消融时剥离 `guest_bash` 中的原始 `:99` X11/AT-SPI 套接字。
5. **收紧 `EC-01` 与 `EC-03` 边缘判据**：`EC-01` 要求 `Tax_Treasury_Pack.pdf` 必须包含税务 VDR 签章 `TAX_VDR_SEAL`；`EC-03` 使用 XML AST 校验 `front_bezel_silkscreen.svg` 三个必选 `<g id="...">` 图层均非空。

## 三、快速运行命令

```bash
# 1. 静态合规审计与单元测试
PYTHONPATH=. .venv/bin/python .agents/skills/paragui-case-design/scripts/audit_case_module.py tasks/curated_8cases_v1
PYTHONPATH=. .venv/bin/python .agents/skills/paragui-case-design/scripts/audit_case_module.py experiments/curated_8cases_v1.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_curated_8cases_v1.py

# 2. 运行确定性五门禁自检（支持 --tasks all 或指定子集如 EC-01,EC-03,RBS3-04）
PYTHONPATH=. python3 experiments/curated_8cases_v1.py \
  --mode self_validate --tasks all --workers 4 --code-root . --out /tmp/curated8-selfval

# 3. 运行 Non-YOLO 模型评测（isolated / seq_ab / shared，支持 --gui-driver qwen_cua | xdotool）
PYTHONPATH=. python3 experiments/curated_8cases_v1.py \
  --mode shared --gui-driver qwen_cua --model gpt-6.1-sol --effort high \
  --tasks all --workers 4 --code-root . \
  --api-json ~/data/paraGUI/private/sol61-api.json \
  --codex-bin ~/data/paraGUI/runtime/codex/codex \
  --out /tmp/curated8-shared
```
