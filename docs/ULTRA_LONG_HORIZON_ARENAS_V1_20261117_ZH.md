# 超长程四智能体真实网站 + 真实桌面软件高重叠“主题工作场”套件报告（`ultra_arenas_v1`，`UA-01..UA-15`）

更新日期：2026-11-17
代码入口：`tasks/ultra_arenas_v1/`（`catalog.py`、`engines.py`、`builders.py`、`flagship_30m.py`、`flagship_builders.py`、`extreme_35m.py`、`extreme_builders.py`）、`experiments/ultra_arenas_v1.py`、`tests/test_ultra_arenas_v1.py`
成绩单与自验证清单：`docs/results-manifests/ultra-arenas-v1-sol61-20261117.json`、`docs/results-manifests/ultra-arenas-selfval-20261117.json`、`runs/comparisons/ultra-arenas-v1-20261117/`
评测模型与沙盒规范：**仅评测 `gpt-6.1-sol (reasoning_effort="high")`**（共 15 场 × 4 智能体 = **60 个非 YOLO 容器实例**，`sandbox_mode = "workspace-write"`、全工具免审批，`permission-audit-verified.json` 100% 通过）

---

## 一、设计目标与从“十余分钟”跨越到“40–70 分钟持续四智能体重合”的核心机制

针对早期主题工作场（`TA-A1..E1` 耗时 `1.2–5.7m`、`UA-01..07` 最高 `26.2m`）中强代码能力智能体通过单次 `guest_bash` Python 循环快速收敛、或部分角色提前完成退场导致后半程仅剩单角色运行的问题，`ultra_arenas_v1` 构建了 **15 个全联网真实外部网站 + 真实原生桌面软件的四智能体工作场（`UA-01..UA-15`）**，并在终极黑盒层（`UA-09, UA-13, UA-14, UA-15`）实现了 **单局真实墙钟耗时 `29.3–70.0 分钟`、累计活跃智能体工时 `107.5–279.8 智能体分钟`、四角色并发重合利用率 `86.1%–99.9%`**：

1. **单工作站串行化重型原生软件仿真锁（`drc_exec_lock`）**：单台共享桌面仅有一套物理验证管线。每次调用 `POST /api/drc_audit` 均在服务端互斥锁下真实拉起无头 LibreOffice Calc 跨表公式重算、Blender 3.4 Cycles 四遍 48–50 采样室内全局光照光线追踪、PyQGIS 3.22 300-DPI 地图排版与空间网络/水文路由、FreeCAD 0.20 OpenCASCADE 72 转角三维 BRep 布尔干涉扫掠、18–24 视口真实 Chromium 光学对比度截图以及 FFmpeg EBU-R128 / BT.709 广电信号检测，单次物理验证真实消耗 `38–60 秒` 多核 CPU 算力。
2. **隐藏评价传感器与二元黑盒反馈（防本地低采样代理绕过）**：在 `UA-09, UA-14, UA-15` 中，隐藏相机的偏轴坐标、季节太阳方位角、离散高杠杆站点/分片权重及非凸悬崖均保存在 `0700` 权限的服务端黑盒内，且仅返回二元门限布尔值与宏观标量指标，阻断了智能体在本地用 `samples=4`（`0.8 秒`）低清克隆渲染绕过真实测试台的路径。
3. **离散组合子集选择与窄窗口跨角色帕累托耦合**：引入 `24 选 10` 数据中心液冷改造与战区调价上限（`UA-12, UA-14`）、`72 节点 6 层级 DAG 限 26 节点改造 + Tier-4 相位共振悬崖` 与 `16 选 6 写偏斜热点分片提升`（`UA-13, UA-15`），并将全局净营业利润率走廊收紧至 `[50.40%, 51.10%]`（宽度仅 `0.70%`）、集群总内存走廊收紧至 `[515, 536] MB`。任一角色单边贪心调参都会击穿同伴门限，迫使四角色围绕同一核心交付物持续博弈与回调。
4. **全程贯穿的共享交付物与长程特有争用源**：
   - 四个角色同时读写同一本多工作表 `.xlsx`（含四角色共写同一张 `Web_Benchmarks` / `Web_Standards` 外部网页核验表）、同一个 Blender `.blend` 室内光追场景、同一个 QGIS `.qgz/.gpkg` 空间工程、同一个 Git `main` 仓库与 `/static/assets/` 目录。
   - 全程穿插 `95s` 短周期单会话 SSO 超时重登（重登会将共享 BI 筛选器重置回 `Q2/EUR/Raw` 陷阱态并轮换 CSRF）、共享 `~/Downloads/bi_view_export.csv` 同名覆盖、`120s` 周期后台自动快照公式审计、动态 Staging 施工态重部署、`60s` 慢查询连续取证防重启污染窗口，以及 `18s–20s` 单席位许可证排他锁 CAE 求解器（并发调用触发 `409 ERR_CAE_LICENSE_BUSY`）。
5. **四角色同步哈希绑定签收（`POST /api/role_signoff`）与逐帧 Cycles 三维动画渲染**：要求全部子系统门限同时绿灯且与当前磁盘主交付物 SHA-256 一致时方可完成角色签收，配合 192–360 帧 Blender Cycles 三维动画逐帧渲染与 `-23.0 LUFS` 音频母带合成，杜绝“提前做完单表先退场”的一次性避让。

---

## 二、真实公网网站与原生桌面软件栈清单

桌面容器（`paragui/astra-recording-desktop:20261113`）开启真实公网直连，智能体容器（`paragui/codex-sandbox:20261113`）保持 `--network none --read-only` 非 YOLO 隔离，仅能通过共享桌面的 Chromium 浏览器（`DISPLAY=:99`）与工作站工具链访问公网资源：

- **28 个经 `cpu15` 实测 `HTTP 200` 的真实外部网站**：涵盖 GitHub 开源仓库（`pallets/flask`、`psf/requests`、`encode/httpx`、`sqlalchemy/sqlalchemy`、`pydantic/pydantic`、`fastapi/fastapi`、`FreeCAD/FreeCAD`）、HuggingFace 模型卡与 `config.json`（`openai-community/gpt2`、`google-bert/bert-base-uncased`）、arXiv 论文页（`1706.03762`、`1512.03385`、`2005.14165`）、Python 官方规范与标准库文档（`pep-0008`、`pep-0020`、`pep-0484`、`docs.python.org/3/library/sqlite3.html`、`concurrent.futures.html`）、PyPI 包元数据与在线安装源（`pypi.org/project/requests/`、`pillow/`），以及 Wikipedia 工程与金融词条（`Debt_service_coverage_ratio`、`Power_usage_effectiveness`、`Software_as_a_service`、`Little's_law`、`Token_bucket`、`Exponential_backoff`、`Titanium_alloy`、`Strain_wave_gearing`、`Write-ahead_logging`）。
- **11 类真实原生 Linux 桌面软件与工程引擎**：Chromium 156（单会话 SSO 门户、公网检索与多视口无头光学对比度渲染）、LibreOffice 7.4 Calc & Writer（`.xlsx` 跨表公式重算、`.odt/.pdf` 导出）、Blender 3.4 Cycles（多反弹室内全局光照与逐帧三维动画渲染）、QGIS 3.22 + SpatiaLite（`.qgz/.gpkg` 多图层空间拓扑与 300-DPI 制图）、FreeCAD 0.20（OpenCASCADE 参数化 BRep 实体建模、BSpline 谐波凸轮扫掠与 STEP 导出）、GIMP 2.10、Inkscape 1.2、FFmpeg 5.1 + SoX 14.4 + MLT `melt`（BT.709 色域与 EBU-R128 `-23.0 LUFS` 响度母带）、Git、SQLite3 WAL + FTS5 全文检索、X11 `xdotool`/`wmctrl`/`import` 剪贴板与窗口栈。

---

## 三、四大主题工作场 15 个任务全景与 `gpt-6.1-sol (high)` 实测总表

15 个任务在 `cpu15` 容器正负金丝雀自验证（`self_validate`）中 **15 / 15 全部通过**（`pristine_pass = False`、`ref_pass = True`、`race_pass = False`）。在无预置通信白板（`no_comm`、工单不剧透同伴存在）的四智能体并发条件下，`gpt-6.1-sol (high)` 的完整实测成绩如下：

- **总体通过率**：**13 / 15 (`86.7%`)** 严格联合通过（`joint_pass` 与延迟金丝雀 `canary_passed` 双过）；未通过的 `UA-13`（`29.3 分钟`，`10/10` 物理门限全满但第 29 分钟长上下文遗忘状态页 `incident_token` 字段名）与 `UA-14`（`70.0 分钟` 满预算，`14/15` 门限达成 `milestone=0.9333`，卡在 1-bit 偏轴隐藏机位 6 分区非对称 Cycles 光追）清晰刻画了模型在超长程高并发下的真实能力边界。
- **超长程耗时与四智能体重合规模**：
  - 终极黑盒层三场代表作均跨越 40–70 分钟大关：**`UA-09`（产品发布日，`41.9 分钟` / `2,515.6s`，累计 `158.0 智能体分钟`，重合率 `94.2%`）**、**`UA-15`（线上事故与 72 节点 DAG 数字孪生排障，`65.7 分钟` / `3,943.9s`，累计 `226.3 智能体分钟`，重合率 `86.1%`，11/11 全过）**、**`UA-14`（季度经营复盘与投资者日，`70.0 分钟` / `4,202.0s`，累计 `279.8 智能体分钟`，重合率 `99.9%`）**。
  - 中高阶长程层（`UA-04, UA-11, UA-13`）墙钟耗时 **`24.2–29.3 分钟`**（累计 `76.4–107.5 智能体分钟`）；基础与中程帕累托对照层（`UA-01..03, UA-05..08, UA-10, UA-12`）墙钟耗时 **`7.8–19.7 分钟`**，构成从 10 分钟级到 70 分钟级的完整难度梯度。

| 任务 ID | 工作场代号 | 联合 (金丝雀) | 里程碑 / Rubric | 墙钟耗时 | 四角色累计工时 | 4角色重合率 | DRC 次数 | GUI / CLI 调用 | 主工件版本数 | 跨角色副作用 | 各角色活跃时长明细 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `UA-01` | `qbr_cloud_ai_portfolio` | **PASS** (PASS) | `1.0000` / `1.0000` | **`906.5s` (`15.1m`)** | **`2899.0s` (`48.3m`)** | `80.0%` | `35` | `104` / `157` | `27` | `14` | SALES:8.7m, FIN:10.0m, OPS:14.5m, EXEC:15.1m |
| `UA-02` | `launch_fullstack_devportal` | **PASS** (PASS) | `1.0000` / `1.0000` | **`876.8s` (`14.6m`)** | **`2232.6s` (`37.2m`)** | `63.6%` | `33` | `40` / `118` | `1` | `0` | CMS:3.8m, FE:9.2m, DESIGN:9.6m, QA:14.6m |
| `UA-03` | `warroom_geo_edge_cluster` | **PASS** (PASS) | `1.0000` / `1.0000` | **`560.8s` (`9.3m`)** | **`1716.8s` (`28.6m`)** | `76.5%` | `28` | `25` / `97` | `0` | `0` | DB:5.2m, APP:5.5m, INFRA:8.6m, IC:9.3m |
| `UA-04` | `actuator_cad_cae_lit_media` | **PASS** (PASS) | `1.0000` / `1.0000` | **`1572.5s` (`26.2m`)** | **`6238.3s` (`104.0m`)** | `99.2%` | `22` | `14` / `127` | `6` | `0` | CAD_ROTOR:25.8m, CAE_LIT:25.9m, MEDIA_PUB:26.0m, CAD_HOUSING:26.2m |
| `UA-05` | `marathon_qbr_3cam_pareto` | **PASS** (PASS) | `1.0000` / `1.0000` | **`755.9s` (`12.6m`)** | **`2045.0s` (`34.1m`)** | `67.6%` | `25` | `62` / `98` | `15` | `20` | SALES:5.2m, FIN:6.7m, OPS:9.6m, EXEC:12.6m |
| `UA-06` | `marathon_launch_turntable_e2e` | **PASS** (PASS) | `1.0000` / `1.0000` | **`1179.7s` (`19.7m`)** | **`3817.1s` (`63.6m`)** | `80.9%` | `30` | `50` / `178` | `1` | `1` | CMS:6.0m, DESIGN:18.8m, FE:19.2m, QA:19.6m |
| `UA-07` | `marathon_warroom_cyber_physical` | **PASS** (PASS) | `1.0000` / `1.0000` | **`470.2s` (`7.8m`)** | **`1515.8s` (`25.3m`)** | `80.6%` | `23` | `19` / `112` | `12` | `3` | APP:4.8m, DB:5.4m, INFRA:7.3m, IC:7.8m |
| `UA-08` | `ultra_qbr_4role_flagship` | **PASS** (PASS) | `1.0000` / `1.0000` | **`1011.4s` (`16.9m`)** | **`3852.7s` (`64.2m`)** | `95.2%` | `26` | `37` / `154` | `8` | `3` | FIN:14.9m, OPS:16.0m, EXEC:16.5m, SALES:16.8m |
| `UA-09` | `ultra_launch_4role_flagship` | **PASS** (PASS) | `1.0000` / `1.0000` | **`2515.6s` (`41.9m`)** | **`9480.3s` (`158.0m`)** | `94.2%` | `27` | `127` / `209` | `6` | `2` | DESIGN:36.4m, QA:39.1m, FE:40.6m, CMS:41.9m |
| `UA-10` | `ultra_warroom_4role_flagship` | **PASS** (PASS) | `1.0000` / `1.0000` | **`916.2s` (`15.3m`)** | **`3525.0s` (`58.8m`)** | `96.2%` | `23` | `42` / `127` | `6` | `0` | APP:14.0m, DB:14.4m, INFRA:15.1m, IC:15.2m |
| `UA-11` | `ultra_actuator_4role_flagship` | **PASS** (PASS) | `1.0000` / `1.0000` | **`1454.5s` (`24.2m`)** | **`4583.3s` (`76.4m`)** | `78.8%` | `18` | `104` / `133` | `3` | `0` | CAE_LIT:16.6m, CAD_ROTOR:17.5m, CAD_HOUSING:18.0m, MEDIA_PUB:24.2m |
| `UA-12` | `extreme_qbr_combinatorial_35m` | **PASS** (PASS) | `1.0000` / `1.0000` | **`1129.3s` (`18.8m`)** | **`4139.4s` (`69.0m`)** | `91.6%` | `28` | `52` / `142` | `26` | `16` | OPS:16.2m, FIN:16.3m, SALES:17.7m, EXEC:18.8m |
| `UA-13` | `extreme_warroom_dag_35m` | **FAIL** (FAIL) | `1.0000` / `0.7000` | **`1760.0s` (`29.3m`)** | **`6450.1s` (`107.5m`)** | `91.6%` | `18` | `57` / `179` | `6` | `0` | DB:24.9m, INFRA:26.2m, APP:27.1m, IC:29.3m |
| `UA-14` | `ultra_qbr_binary_investor_day_35m` | **FAIL** (FAIL) | `0.9333` / `0.6533` | **`4202.0s` (`70.0m`)** | **`16788.4s` (`279.8m`)** | `99.9%` | `64` | `87` / `403` | `40` | `1` | OPS:69.8m, SALES:70.0m, FIN:70.0m, EXEC:70.0m |
| `UA-15` | `ultra_warroom_binary_35m` | **PASS** (PASS) | `1.0000` / `1.0000` | **`3943.9s` (`65.7m`)** | **`13578.9s` (`226.3m`)** | `86.1%` | `45` | `108` / `345` | `9` | `0` | APP:52.2m, INFRA:53.2m, DB:55.2m, IC:65.7m |

---

## 四、超长程实测中涌现的关键多智能体协作与冲突现象

1. **盲测环境下自发涌现的桌面鼠标/键盘排号与测试台预约协议**：
   - 在完全未开启 `shared_scratchpad` 且工单未剧透同伴存在的 `no_comm` 模式下，`gpt-6.1-sol` 在长达 40–70 分钟的执行过程中通过观察窗口焦点跳变、文件哈希变化与 `drc_queue_waits` 队列等待，自发在共享目录创建协调账本：例如 `UA-09`（`41.9m`，`127` 次 GUI 操作）中四个智能体共写 `/workspace/TEAM_NOTES.txt` 预约桌面浏览器控制权（`DESIGN 12:34: Reserving desktop ~1min to visit...`、`FE reserving one audit NOW...`）；`UA-04`（`26.2m`）自发建立 `/workspace/MEDIA_STATUS.md` 同步 360 帧 Cycles 渲染进度；`UA-15`（`65.7m`）在 `/tmp/APP_COORDINATION.txt` 与 `/tmp/IC_RESPONSE.txt` 中跨角色同步 72 节点水文/流量 DAG 与 6 分区光学搜索进展。
2. **高频跨角色状态碰撞与共享工作簿版本风暴**：
   - 在共享 18 页分页 BI 与 `95s` 短周期 SSO 的季度经营复盘系列中，四角色围绕浏览器筛选器、同名导出文件与多工作表 `.xlsx` 展开密集交锋：`UA-01` 产生 `27` 个 `.xlsx` 版本与 `14` 次 BI/SSO/下载覆盖副作用，`UA-05` 产生 `20` 次碰撞，`UA-12` 产生 `26` 个版本与 `16` 次碰撞，而在最长程的 `UA-14`（`70.0m`）中，`Q4_Enterprise_Master_Model.xlsx` 经历了 **`40` 个独立 SHA-256 版本演进** 与 **`64` 轮多软件联合 DRC 验证**，中间多次因同伴修改数据中心或战区组合导致全局净营业利润率跌出 `[50.40%, 51.10%]` 窄走廊（通过门限从 `10/15` 回落至 `9/15`、`8/15` 回落至 `6/15`），随后再经跨表回调恢复。
3. **长程上下文增长后的收尾契约遗忘（`UA-13` 第 29 分钟金丝雀失守）**：
   - 在 `UA-13`（`29.3m`，`236` 次工具调用）中，`DB`、`APP`、`INFRA`、`IC` 四个角色解出了 72 节点 6 层级 DAG 限 26 节点改造、16 选 6 热点分片提升、72 转角空化谐波冷却阀 20s 独占 CAE 认证与非对称 Cycles 热力照明，拿满 **`10 / 10` 全部工程门限（`milestone_score = 1.0000`）** 并完成 `4 / 4` 角色签收，甚至从真实 PyPI 下载 `reportlab` 与 `python-pptx` 生成了完整排障简报；但在第 29 分钟最终投递 `/api/statuspage/resolve` 时，`IC` 遗忘了 `<canvas>` 公布的 `incident_token` 参数而发送了空 JSON `{}`，被终局延迟金丝雀拦截（`canary_passed = False`，`final_rubric_score = 0.7000`）。在随后规则更严苛的 `UA-15`（`65.7m`）中，`IC` 历经 `175` 次工具调用与 `45` 轮 DRC 验证，完整携带令牌与洪峰延迟完成闭环（`1.0000`）。
4. **1-Bit 二元偏轴全局光照优化构成 70 分钟级非饱和区分度（`UA-14`）**：
   - 在 `UA-14`（`70.0m`）中，`FIN`、`OPS`、`SALES` 通过分组筛查（`sales_screen_01..05.json`）在零诊断列表提示下破解了两个 `24 选 10` 离散黑盒组合优化并命中 `0.70%` 极限利润率走廊，完成了 24 视口投资者门户与 240 帧 Cycles 路演短片（达成 **`14 / 15` 门限，`milestone_score = 0.9333`**）；唯独第 15 项门限（未知偏轴相机下的 4 灯非对称 6 分区照明均衡，每次仅返回 1-bit 布尔反馈且耗时近 1 分钟）在 64 轮 DRC 预算内未能撞中，使该任务成为检验下一代多智能体实验设计与跨角色算力排程的高区分度试金石。

---

## 五、复现命令

```bash
# 1. 零模型容器正负金丝雀自验证（15/15 校准检查）
PYTHONPATH=. python3 -m experiments.ultra_arenas_v1   --mode self_validate   --out ~/data/paraGUI/runs/ultra-arenas-selfval-20261117   --code-root . --workers 4

# 2. 运行 40-70 分钟级旗舰代表作（UA-09 产品发布日 / UA-14 季度经营复盘 / UA-15 线上事故排障，仅测 gpt-6.1-sol）
CODESK_CODEX_CONTAINER_IMAGE=paragui/codex-sandbox:20261113 PARAGUI_UA_CPUS=6 PYTHONPATH=. python3 -m experiments.ultra_arenas_v1   --mode benchmark   --out ~/data/paraGUI/runs/ultra-arenas-sol61-20261117/flagship_run   --code-root .   --api-json ~/data/paraGUI/private/sol61-api.json   --codex-bin ~/data/paraGUI/runtime/codex/codex   --coord-mode no_comm --workers 3   --tasks UA-09 UA-14 UA-15
```
