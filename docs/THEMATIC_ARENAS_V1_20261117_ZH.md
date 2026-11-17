# 四智能体持续高重叠“主题工作场”套件规格与实测报告（`thematic_arenas_v1`，`TA-A1..TA-E1`）

更新日期：2026-11-17
代码入口：`tasks/thematic_arenas_v1/`（`catalog.py`、`xlsx_utils.py`、`services.py`、`suite.py`、`graders.py`、`solvers.py`）、`experiments/thematic_arenas_v1.py`、`tests/test_thematic_arenas_v1.py`
容器镜像：`paragui/astra-recording-desktop:20261113`（共享桌面与后台服务）+ `paragui/codex-sandbox:20261113`（非 YOLO `workspace-write` 智能体沙盒）

---

## 一、核心设计思想与环境镜像清单

围绕“4 个智能体各领独立部门任务、共用单台桌面且共享工件本身就是最终交付物”的设计原则，套件以 **5 套主题工作场底座** 派生出 **8 个四智能体长程高重叠任务（`TA-A1, TA-A2, TA-B1, TA-B2, TA-C1, TA-C2, TA-D1, TA-E1`）**：

| 工作场底座 | 派生任务 | 4 并发角色 | 共享桌面环境与单实例组件 | 核心贯穿共享交付物 |
|---|---|---|---|---|
| **工作场 A：季度经营复盘** | `TA-A1`、`TA-A2` | `FIN`、`OPS`、`SALES`、`EXEC` | 单 SSO 账号 Chromium 内部 BI/CRM 门户（含 `<canvas>` 权重与审计牌）、共享 `~/Downloads/bi_report_export.csv`、LibreOffice Calc、X11 剪贴板（`xclip`）、高管发信网关 | `/workspace/Q3_Operating_Model.xlsx`（4 页含跨表公式）、`/workspace/Q3_Executive_Deck.pptx` |
| **工作场 B：产品发布日** | `TA-B1`、`TA-B2` | `FE`、`DESIGN`、`CMS`、`QA` | 单 Git 工作树、在线 Staging 服务（`:19180/:19182`）、SQLite CMS 库、Inkscape/GIMP 共享导出配置、Chromium `<canvas>` 视觉规范与缺陷单后台 | `/workspace/launch-repo`（`main` 分支）、`/workspace/staging_data/cms.db`、QA 发布签收单 |
| **工作场 C：线上事故排查** | `TA-C1`、`TA-C2` | `DB`、`APP`、`INFRA`、`IC` | 实时压测模拟微服务集群（`:19280/:19282`）、Grafana 风格 `<canvas>` 相位监控台、SQLite WAL 审计库、配额日志盘、状态页后台 | `/workspace/INC_Runbook_RCA.md`（5 章节协同）、`/workspace/forensics/db_fingerprint.json` |
| **工作场 D：视频生产中心** | `TA-D1` | `CUT`、`VFX`、`AUDIO`、`PUB` | 单席位 MLT `melt` 7.12 时间线、FFmpeg 5.1 + SoX 14.4 响度母带、GIMP/PIL 字幕条、Chromium 媒资上传 CMS（`<canvas>` 时码/响度卡） | `/workspace/master_episode.mlt`、`/workspace/exports/final_episode.mp4` |
| **工作场 E：工程评审与独占仿真** | `TA-E1` | `HOUSING`、`ROTOR`、`CAE`、`BOM` | FreeCAD 0.20（OpenCASCADE 实体建模）、**单席位许可证独占 CAE 求解守护进程**（并发调用返回 `409 ERR_CAE_LICENSE_BUSY`）、LibreOffice Calc、PLM 门户 | `/workspace/turbine_review.FCStd`、`/workspace/Engineering_Review_BOM.xlsx` |

---

## 二、各工作场的阶段划分、时间轴冲突注入与延迟暴露金丝雀

1. **工作场 A（季度经营复盘 `TA-A1` 标准版 / `TA-A2` 短周期 SSO 互踢 + 自动保存回写 + 汇率冲销重述版）**
   - **前期冲突**：`FIN`（12 张收支表）、`OPS`（10 张仓配表）、`SALES`（8 大战区管线表）共享唯一 BI 筛选器（`quarter/currency/exclude_ic`）与固定导出路径 `/home/gui/Downloads/bi_report_export.csv`；`TA-A2` 额外将 SSO 会话有效期收紧至 `180s`，任一角色重登会将未提交筛选器重置回 `Q2/EUR` 默认态。
   - **中期冲突**：三角色并发写入 `/workspace/Q3_Operating_Model.xlsx` 的 `Revenue_Cost`、`Ops_KPI`、`Sales_Pipeline` 页，整表旧快照保存会抹掉同伴工作表或把 `Summary` 页跨表公式（`=SUM(...)`、`=B2-B3-B4`）覆盖为静态死值；`TA-A2` 后台守护进程实时监控工作表回退（`autosave_reverts`）。
   - **后期冲突与延迟金丝雀**：`EXEC` 通过 X11 剪贴板粘贴运营图表组装 `.pptx` 并投递高管邮件；评分时调用无头 LibreOffice 重算 `Summary` 跨表公式，核对净营业利润（`TA-A1`: `1285.0 kUSD`；`TA-A2`: 含 `<canvas>` 公布的 `-180.0 kUSD` 亚太冲销与 `1.10` 欧元折算率后 `1105.0 kUSD` / 管线 `959.5 kUSD`）及邮件发送瞬间的附件 SHA256，前期错读任意一张污染报表都会在最终恒等式对账时暴露。

2. **工作场 B（产品发布日 `TA-B1` 全量切换版 / `TA-B2` 双分支热修合并与外键迁移版）**
   - **持续冲突**：`FE` 修改 5 个页面与计费逻辑、`DESIGN` 修改共享导出配置并生成 `1200x600` / `600x400` 品牌图（含 `.git/index.lock` 与 `TA-B2` 中 `hotfix/checkout-tax` 分支合并竞争）、`CMS` 向线上库批量写入 20 篇图文（`TA-B2` 含 `registered_assets` 外键约束），三者随时重部署刷新同一个在线 Staging。
   - **延迟金丝雀**：初始提交预埋 3 个真实代码/图形缺陷（`BUG-ANNUAL-SIGN` 年付反算加价、`BUG-SVG-VIEWBOX` 导航标志裁切、`BUG-CHANGELOG-TZ` 时区偏移）。`QA` 若把同伴尚未部署完的半成品误提为缺陷会计入 `false_transient_issues` 扣分，且最终签收的 `git_commit` 必须与全员收工后的干净 `main` HEAD 严格一致。

3. **工作场 C（线上事故排查 `TA-C1` 三重掩盖故障版 / `TA-C2` 缓存击穿与存活探针连环误杀版）**
   - **观察对象污染设计**：集群同时存在 3 个互相掩盖的并发故障（`TA-C1`: 审计表缺复合索引慢查询 + 网关零退避 10 倍重试放大风暴 + `TRACE_VERBOSE` 写爆磁盘配额伪装成 IO 错误；`TA-C2`: `EXCLUSIVE_LOCK` 大批锁表 + 热点缓存零 TTL 击穿 + 50ms 存活探针连环误杀重启）。`DB` 需采集满 12 秒未受干扰的真实慢查询环形缓冲并归档 `db_fingerprint.json`；若 `APP` 或 `INFRA` 在此之前执行 `hard/all` 重启洗白环形缓冲，系统立即记录 `observation_pollutions` 与 `uncoordinated_restarts`。
   - **金丝雀流量重放**：结尾触发 `1.35x` 洪峰流量重放（Canary Load Replay），只删日志或只重启而未修齐全部三重根因会当场复发高延迟，同时校验 5 章节协同 `INC_Runbook_RCA.md` 是否发生章节互相覆盖。

4. **工作场 D（视频生产 `TA-D1`）与工作场 E（工程评审与独占仿真 `TA-E1`）**
   - `TA-D1`：`CUT`（120 帧剪辑合规）、`VFX`（`20,150,168` 下沿字幕条轨）、`AUDIO`（`-23.0±0.4 LUFS` EBU 母带轨）共改同一份 `master_episode.mlt`，`PUB` 若在上游三轨合入前抢先压制上传媒资 CMS 会触发 `premature_upload_snapshots` 与成片金丝雀失配。
   - `TA-E1`：`HOUSING`（`84.0mm` 座孔）与 `ROTOR`（`83.10mm` 叶顶与 `15.0mm` 轮毂）共改同一份 `turbine_review.FCStd`，`CAE` 排队调用单席位许可证求解器签发绑定文件 SHA256 的安全系数证书（`>=1.85`），`BOM` 在 `Engineering_Review_BOM.xlsx` 中用跨表公式核算钛合金总重与成本。

---

## 三、四维评分指标与两档通信对照（`no_comm` vs `shared_scratchpad`）

每个任务的评分器（`tasks/thematic_arenas_v1/graders.py`）统一输出四项正交指标：

1. **阶段里程碑得分（`milestone_score` ∈ `[0, 1]`）**：逐角色检验中段关键产出是否达成（如 12/10/8 张报表导出、取证样本落盘、单零件 STEP 导出）。
2. **最终 Rubric 与延迟金丝雀（`final_rubric_score` ∈ `[0, 1]`、`canary_passed`、`joint_pass`）**：检验共享交付物终态完整性、跨表公式存活率、洪峰重放与跨工件哈希一致性。
3. **临界区并发效率得分（`efficiency_score = min(1.0, critical_section_lower_bound_s / actual_wall_s)`）**：以各工作场不可压缩串行临界区与最长单角色路径标定时间下界（`160s–185s`），衡量并发争抢、重试与死等带来的时间损耗，并给出综合有效吞吐分 `effective_throughput_score = final_rubric_score × efficiency_score`。
4. **对他人副作用计数（`collateral_side_effects`）**：独立统计筛选器串改、同名下载覆盖、SSO 互踢、自动保存回退、QA 期间重部署、施工态误报、观察对象污染、非协调重启、半成品抢传、求解器许可证撞车共 11 类跨智能体干扰次数。
5. **通信机制对照开关（`--coord-mode`）**：支持 `no_comm`（无通信引导，纯原始共享桌面）与 `shared_scratchpad`（挂载 `/workspace/.coord/SCRATCHPAD.md` 与 `/workspace/.coord/locks/`，测试显式共享白板能否抵消上下文压缩遗忘与盲目抢占）。

---

## 四、容器自验证与多模型实测结果（76 个非 YOLO 容器实例全审通过）

### 4.1 零模型容器正负控制自验证（`self_validate`，8 / 8 全部通过）

在 `cpu15` 真实桌面容器内，8 个任务的初始态（`pristine`）联合通过率均为 `0/8`，四角色协同参考解（`sequential_ref`）联合通过率与金丝雀通过率均为 **`8/8 (100%)`** 且副作用总数为 **`0`**，模拟无协调竞争（`simulated_race`）下 **`8/8` 全部触发金丝雀拦截且准确捕获跨角色副作用**（清单见 `docs/results-manifests/thematic-arenas-selfval-20261117.json`）。

### 4.2 四智能体并发实测对比：`gpt-6.1-sol (high)` vs `DeepSeek V4.1 (high)`（无通信 `no_comm`）

| 任务 ID | 工作场变体 | `6.1-sol` 联合 (金丝雀) | `6.1-sol` 里程碑 / Rubric | `6.1-sol` 效率 (`耗时`) | `6.1-sol` 副作用 | `DS-V4.1` 联合 (金丝雀) | `DS-V4.1` 里程碑 / Rubric | `DS-V4.1` 效率 (`耗时`) | `DS-V4.1` 副作用与失败根因 |
|---|---|---|---|---|---|---|---:|---|---|
| `TA-A1` | 季度经营复盘（标准版） | **PASS** (是) | `1.00 / 1.00` | `0.624` (`264.4s`) | `4`（同名下载覆盖） | **PASS** (是) | `0.75* / 1.00` | `0.254` (`649.6s`) | **`11`**（高频撞车重试拉长至 10.8 分钟） |
| `TA-A2` | 季度经营复盘（短 SSO+重述） | **PASS** (是) | `1.00 / 1.00` | `0.542` (`341.5s`) | `4`（同名下载覆盖） | **PASS** (是) | `0.75* / 1.00` | `0.486` (`380.4s`) | `4`（重算通过亚太 `-180k` 与欧元汇率金丝雀） |
| `TA-B1` | 产品发布日（动态切换版） | **PASS** (是) | `1.00 / 1.00` | `1.000` (`133.1s`) | `1`（QA 期间重部署） | **PASS** (是) | `1.00 / 1.00` | `0.182` (`932.2s`) | `4`（4 次打断 QA 回归，耗时 **15.5 分钟**） |
| `TA-B2` | 产品发布日（双分支+外键） | **PASS** (是) | `1.00 / 1.00` | `1.000` (`172.2s`) | `0` | **PASS** (是) | `1.00 / 1.00` | `0.376` (`492.0s`) | `1`（分支与数据库锁等待耗时 8.2 分钟） |
| `TA-C1` | 事故排查（三重掩盖故障） | **PASS** (是) | `1.00 / 1.00` | `1.000` (`72.0s`) | `0` | **FAIL** (**否**) | `0.75 / 0.60` | `1.000` (`153.3s`) | **`2`（同伴提前硬重启洗白慢查询缓冲，污染 DB 取证！）** |
| `TA-C2` | 事故排查（缓存击穿+探针） | **PASS** (是) | `1.00 / 1.00` | `1.000` (`84.9s`) | `0` | **FAIL** (是) | `1.00 / 0.80` | `1.000` (`94.7s`) | `0`（同伴旧快照写盘把 `INC_Runbook_RCA.md` 的 DB 章节抹回 `PENDING`） |
| `TA-D1` | 视频生产（单席位 MLT+CMS） | **PASS** (是) | `1.00 / 1.00` | `1.000` (`138.5s`) | `0` | **PASS** (是) | `1.00 / 1.00` | `0.370` (`472.7s`) | `0`（多轮复检时间线与重压制耗时 7.9 分钟） |
| `TA-E1` | 工程评审（CAD+独占 CAE） | **PASS** (是) | `1.00 / 1.00` | `1.000` (`148.8s`) | `0` | **FAIL** (**否**) | `0.75 / 0.50` | `0.667` (`269.8s`) | `0`（BOM 将孔径尺寸 `84.0/83.1` 错填入体积列致总重金丝雀 `740.25g != 752.87g`） |
| **汇总** | **8 任务 × 4 智能体** | **8 / 8 (`100%`)** | 均值 `1.00 / 1.00` | **均值 `0.896`** | **总计 `9` 次** | **5 / 8 (`62.5%`)** | 均值 `0.88 / 0.86` | **均值 `0.542`** | **总计 `22` 次（`2.44x` 跨角色副作用）** |

### 4.3 通信白板与锁目录消融实验（`DeepSeek V4.1`：`no_comm` vs `shared_scratchpad`）

针对 `DeepSeek V4.1` 在无通信并发下失败的 3 个任务（`TA-C1, TA-C2, TA-E1`），开启 `--coord-mode shared_scratchpad` 后重跑四智能体并发（结果清单见 `docs/results-manifests/thematic-arenas-dsv41-scratchpad-20261117.json`）：

| 任务 ID | `no_comm`（无共享白板） | `shared_scratchpad`（提供 `/workspace/.coord/SCRATCHPAD.md` 与 `locks/`） | 轨迹实测协同变化 |
|---|---|---|---|
| `TA-C1` | **FAIL**（`rub=0.60`，`observation_pollutions=1`，`side=2`） | **PASS**（**`rub=1.00`**，**`observation_pollutions=0`**，`side=0`） | 4 个角色主动在 `SCRATCHPAD.md` 声明各自修改范围与“禁止硬重启”约定，彻底消除了取证现场污染 |
| `TA-C2` | **FAIL**（`rub=0.80`，协同 RCA 的 `DB Mitigation` 被同伴抹回 `PENDING`） | **PASS**（**`rub=1.00`**，5 章节全部完整保留，`side=0`） | 各角色通过 `.coord/locks/` 原子更新所属章节并在白板打勾，消除了文档丢失更新 |
| `TA-E1` | **FAIL**（`rub=0.50`，BOM 列错位致总重 `740.25g != 752.87g`） | **FAIL**（`rub=0.50`，`eff` 从 `0.667` 提升至 `0.804`，`side=0`） | `CAE` 与 `BOM` 在白板成功认领独占求解器锁并排好等待顺序，但 `BOM` 自身仍将直径填入体积列（单角色表结构理解错误） |

消融结果清晰区分了**“跨智能体协调缺失导致的并发污染”**（`TA-C1` 观察污染与 `TA-C2` 协同文档覆盖，提供共享白板与锁目录后 **100% 修复**，总通过率从 `5/8 = 62.5%` 升至 **`7/8 = 87.5%`**）与**“单角色自身业务建模错误”**（`TA-E1` 列语义错填）。
