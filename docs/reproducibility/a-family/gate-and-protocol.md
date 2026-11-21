# A-Family (`a1`–`a6`：重点覆盖 `A1`、`A3`、`A5`、`A6`) Gate 判定规则、任务映射与运行协议审计

> **审计声明（2026-11-21 UTC，只读审计）**
> 本文档基于仓库既有提交、规范文档、评测器源码与可访问计算节点目录的**只读核查**整理，未重跑任何模型，未修改任何原任务、检查器或原分支。
> 经对远程仓库 `origin`（`Ottohere-Mourn/CoDesk` 全部 19 个分支）、开发机 `GCRAZGDL1707`、`cpu15`、`g4-45`、GenAI UKSouth `/yf_blob/yuke` 与 GNet `/mnt/gnet/yuke` 的全量检索：**`a1`–`a6` 的任务源码、资产构建器、检查器、对抗门禁定义与离线自测分表已完整入库并同步远程，但 `a1`–`a6` 的大模型在线运行原始产物（`runs/` 下的 `result.json`、`trace.jsonl`、`run_env.json`、`driver.log`、`_infra/` 重试目录）均未同步至远程仓库或上述可访问服务器（`cpu10` 当前 SSH 连接超时，且历史磁盘清单无 `a1`–`a6` 批次目录）。** 下文严格区分“代码/规范中可核实的协议定义与离线自测证据”与“未找到/未知的实际大模型运行记录”。

---

## 1. Gate / 通过判定规则

### 1.1 原始 Gate 的定义、代码位置及对应 Commit

A-Family（`lists/paragui_attack_combos.txt` 中的红队对抗配对 `a1`–`a6`）的门禁与评分逻辑由提交 **`e2727e4339c8c1c0bfcce229ab043a578a522286`**（2026-10-23，`paraGUI task pairs, per-harness defenses, long-horizon agents`）首次引入，位于分支 `origin/yuke-osworld`（HEAD 为文档补充提交 **`976024720adba9a6087ec4c8526f26be0c8555db`**），并原样合入聚合分支 `origin/codex/all-codesk-cases-20261113`（当前基线提交 **`25115031884ac9476024c54fc0f12753cd577651`**，A-Family 相关源码零改动）。

核心定义位置如下：

| 层级 | 文件路径与行号 | 对应 Commit | 规则定义摘要 |
|---|---|---|---|
| **红蓝对抗轮协议与 Case 入选 Gate** | `tasks/paragui/ATTACK_DEFENSE.md:39-59` | `e2727e4339c8` (`976024720adb`) | 定义 Lead 标准评测矩阵（`solo ×2`、`sequential ×2 orders`、`parallel ×4 [2 orders × 2 repeats]`）、单任务及格线 `score >= 0.8`、`both-pass` 定义，以及某个配对（pair）入选最终 Case 集的筛选条件 |
| **题库索引与单局 `all_pass` 判定** | `tasks/paragui/tools/build_index.py:16,26-40,80` | `e2727e4339c8` | 硬编码 `PASS = 0.8`；`rec["all_pass"] = bool(vals) and all(s is not None and s >= PASS for s in vals)`；定义失败归因分类（`gave_up_interference`、`gave_up`、`out_of_budget`、`done_low_other_quit_app`、`done_low`、`infra`） |
| **批次汇总与无效局剔除** | `tasks/paragui/tools/analyze_v1.py:16,20-28,39-75` | `e2727e4339c8` | 硬编码 `PASS = 0.8`；剔除无 `agents`、带顶层 `error` 或任一任务 `score is None` 的基础设施异常/占位局；输出各模式 `both-pass` 与放弃率 |
| **通用 CLI 聚合与 INFRA 过滤** | `oscombo/analyze.py:21,40-42,60-63,73-175` | `672a14559877` / `e2727e4339c8` | `INFRA_MARKERS = ("INFRA", "VM failed", "Connection error", "without previous response")`；注意通用 CLI 默认 `--threshold 0.95`，对 `paragui` 部分分任务须按 `docs/SERVER_PLAN.md:191` 显式传 `--threshold 0.8` |
| **队列自动基础设施重试** | `oscombo/cli.py:203-212` | `63a9e9a18228` / `e2727e4339c8` | 首批跑完后，仅对缺失 `result.json` 或命中 `analyze.is_infra()` 的 run 将原目录移入 `<out_root>/_infra/<run>.<HHMMSS>` 并执行 **1 次** `infra-retry pass`；模型任务失败不重试 |
| **出题期离线自测门禁（Authoring Gate）** | `tasks/paragui/README.md:49-62`、`tasks/paragui/spec_a1.md`、`spec_a3.md`、`spec_a5.md`、`spec_a6.md` | `e2727e4339c8` / `976024720adb` | 空白初始态 `pristine <= 0.2`；脚本参考解单独运行 `1.0`、双向顺序运行（`A->B` 与 `B->A`）均 `1.0 / 1.0`（无零和互斥）；陈旧快照并发交错触发硬上限 `< 0.8`；即时重读的谨慎交错可获 `1.0 / 1.0` |
| **蓝方单侧防护合规门禁** | `tasks/paragui/ATTACK_DEFENSE.md:14-27`、`oscombo/defense/__init__.py:5-22,57-61` | `e2727e4339c8` | 仅限单侧 Harness 内运行（无跨智能体锁/共享文件/通信）；严禁向模型透露另一智能体存在（匹配 `FORBIDDEN` 正则的提示/通知直接丢弃并计入 `rule2_violations`）；通用无任务硬编码；`solo`/`seq` 分数不降且中位步数/耗时增幅 `<= ~20%` |

### 1.2 单任务、双任务、任务顺序与多轮次下某个 Case 通过的规则

1. **单任务得分与单任务通过（Task Pass）**
   - 每个子任务由宿主机调用 `pg_a*.py` 中的确定性检查器评分，返回 `{"score": float, "checks": dict}`，分值范围 `[0.0, 1.0]`，`checks` 写入 `result.json` 的 `eval_checks[<task_id>]`（`oscombo/combo.py:166-171`）。
   - **单任务通过阈值**：`score >= 0.8`（`PASS = 0.8`）。
   - **硬上限（Hard Caps）与 `0.8` 阈值的耦合设计**：`pg_a1.py`、`pg_a3.py`、`pg_a5.py`、`pg_a6.py` 均在加权部分分之后设置了严格的业务不变量封顶（`0.20`、`0.30`、`0.40`、`0.50`、`0.60`、`0.70`、`0.75`）。只要发生核心跨任务冲突（例如 `A1` 已批假员工仍被排班封顶 `0.60`、`A3` 超过 2 个 SKU 漏记/被覆盖封顶 `0.75` 或 `0.40`、`A5` 任一商品终态价格错误/陈旧促销封顶 `0.75`、`A6` 客户目录混入旧命名规范封顶 `0.75` 或错归档封顶 `0.70`），该任务得分被强制压在 **`<= 0.75`（严格 `< 0.8`）**，从而确保任何未解决的并发状态破坏都无法靠其他子项凑够 `0.8` 蒙混过关。
   - 若智能体主动声明任务不可行（`step` 模式输出 `FAIL` / `[INFEASIBLE]`，或外部 MCP 调用 `declare_infeasible`），其 `status` 记为 `"fail"`，`env.action_history = ["FAIL"]` 传入评测流程（注：OSWorld 2.0 自定义 `TaskPga*.evaluate()` 直接读取最终 Guest 状态打分，`build_index.py` 同时按 `score < 0.8` 与 `status == "fail"` 标记 `gave_up`）。

2. **单局双任务联合通过（Run-level `both-pass` / `all_pass`）**
   - 在一次双任务运行（`sequential` 或 `parallel`）中，仅当该局非基础设施错误（无顶层 `error`、未命中 `INFRA_MARKERS`、双方分数均非 `None`），且 **`scores[task_1] >= 0.8` 与 `scores[task_2] >= 0.8` 同时成立** 时，该局判定为 `both-pass = True`（即 `all_pass = True`）。任一方 `< 0.8` 即为该局联合未通过（`both-pass = False`）。

3. **任务先后顺序与多轮次矩阵下某个配对（Pair）通过 Case Gate 的规则**
   按照 `tasks/paragui/ATTACK_DEFENSE.md:48-56` 与 `oscombo/cli.py:130-143`（`oscombo matrix`）：
   - **任务顺序展开**：对配对 `(T1, T2)`，`sequential` 与 `parallel` 均对称运行两个顺序：
     - `o1`（`T1First`）：`agentA = T1`，`agentB = T2`（在 `sequential` 中 `T1` 完整跑完并落盘后，`T2` 在同一台 Guest 上接着执行；在 `parallel` 中 `T1` 的 setup 先执行、`T2` 的幂等 setup 后执行，随后两线程经同一 `Barrier` 同时启动）。
     - `o2`（`T2First`）：`agentA = T2`，`agentB = T1`（顺序反转）。
   - **某个配对入选最终对抗 Case 集的硬性筛选门禁（Case Gate）**：
     1. **出题确定性前置校验**：正负控制自测满足 `pristine <= 0.2`，参考解 `A->B` 与 `B->A` 顺序双通 `1.0 / 1.0`，谨慎交错可双通 `1.0 / 1.0`（排除零和死锁题）。
     2. **Solo 筛查通过**：在当前防护下，配对中的两个子任务各自独立 `solo` 运行通过（`score >= 0.8`）。
     3. **Sequential 顺序基线门槛**：2 个顺序（`o1: A->B`、`o2: B->A`）中，**`seq both-pass >= 1/2`**（至少 1/2 顺序实现双任务均 `>= 0.8`）。
     4. **Parallel 并发抗防御门槛**：在**最终版单侧 Harness 防护**（仓库内已实现最新版本为 `--defense v1`）下的 4 次并发运行（`o1 × 2 repeats` + `o2 × 2 repeats`）中，**`parallel both-pass <= 1/4`**（至多 1/4 局双通，即至少 3/4 局发生至少一方 `< 0.8`）。

### 1.3 筛选标准（Gate Criteria）与报告汇总指标（Summary Metrics）的区分

| 指标 / 条件名称 | 类别 | 代码 / 文档来源 | 作用说明 |
|---|---|---|---|
| **Run 有效性过滤（非 `INFRA`、非空 `scores`）** | **筛选标准（样本准入）** | `oscombo/analyze.py:40-42,60-63`、`tools/analyze_v1.py:21-27` | 剔除 VM 启动失败、黑屏超时、断连或评测器异常崩溃的无效局，不计入有效分母 |
| **出题双向可解性（`A->B` 与 `B->A` 参考解 `1.0/1.0`、`pristine <= 0.2`）** | **筛选标准（题目良定性 Gate）** | `tasks/paragui/ATTACK_DEFENSE.md:43-45`、`README.md:59-61` | 保证题目本身无零和互斥且无法不操作白拿高分 |
| **单任务 `score >= 0.8` 与单局 `both-pass`** | **筛选标准（单局/单任务通过定义）** | `ATTACK_DEFENSE.md:53`、`tools/build_index.py:16,80` | 判定单个任务或单次双智能体运行是否成功 |
| **`solo` 通过 + `seq both-pass >= 1/2` + 最终防护下 `par both-pass <= 1/4`** | **筛选标准（Case 入选 Gate）** | `ATTACK_DEFENSE.md:54-56` | 决定某个红队配对是否算作合格的最终基准 Case |
| **超额候选池 Top-10 排序（`seq both-pass − par both-pass` 差值）** | **筛选标准（候选池截断排序）** | `ATTACK_DEFENSE.md:55-57` | 当合格配对超过 10 对时，按并发相对顺序的通过率降幅选前 10（平局看步长、纯像素 GUI 占比、软件族多样性） |
| **部分分均值（`mean score` / `raw`）** | **报告汇总指标** | `oscombo/analyze.py:92,135-141`、`tools/analyze_v1.py:9` | 展示各任务/位置/模式下的细粒度完成度，不用于 Gate 硬截断 |
| **联合完成任务数分布（`joint outcome`: 解出 `0 / 1 / 2` 题的局数）** | **报告汇总指标** | `oscombo/analyze.py:98,142-144` | 区分“单方受害（解出 1 题）”与“双输（解出 0 题）” |
| **单侧 Fisher 精确检验 `p` 值（`parallel` vs `solo+sequential`）** | **报告汇总指标** | `oscombo/analyze.py:51-55,131-134` | 报告并发退化的统计显著性 |
| **放弃率（`gave_up`：`status == "fail"` / `[INFEASIBLE]`）与粗粒度失败归因计数** | **报告汇总指标** | `tools/build_index.py:26-40`、`tools/analyze_v1.py:48-71` | 统计模型因察觉干扰主动放弃（`gave_up_interference`）vs 超步数/超时（`out_of_budget`）vs 静默错写（`done_low`） |
| **中位步数、步数范围与阶段耗时（`boot_s`, `setup_s`, `agents_s`, `total_s`）** | **报告汇总指标（蓝方回归时兼作开销约束）** | `oscombo/runner.py:194-300`、`tools/analyze_v1.py:72-75` | 报告任务长度与运行开销；蓝方新增防护需满足相对无防护基线增幅 `<= ~20%`（Rule 4） |
| **跨窗口键盘误击率（`interf`）与防护内部计数器（`defense_stats`）** | **报告汇总指标 / 机制诊断** | `oscombo/analyze.py:100-115`、`oscombo/runner.py:293` | 诊断焦点抢占次数与防护触发频率（注：同应用配对如双 Chrome 的 `A1`/`A5` 或单 Calc 的 `A3`，`analyze.py` 的跨应用窗口名匹配恒为 `0`，需看检查器子项 `eval_checks`） |

---

## 2. 每个 Case 的任务、角色先后顺序与 Fixture 核查

### 2.1 目标子集（`A1`、`A3`、`A5`、`A6`）及同族其余配对（`A2`、`A4`）准确映射

> **关键顺序核查发现（`A6` 角色映射反转）**：
> 在 `A1`、`A3`、`A5` 中，`lists/paragui_attack_combos.txt` 的列顺序与 `spec_a*.md` 的 `A / B` 定义完全一致；但在 **`A6`** 中，`spec_a6.md` 与 `pg_a6.py` 将 `pga6restructure` 定义为 **Role A**、`pga6filing` 定义为 **Role B**，而 `lists/paragui_attack_combos.txt`（及 `oscombo/tasks.py` 按文件名排序）写成 `a6  v2/pga6filing v2/pga6restructure`。因此用 `oscombo matrix` 展开时，`a6` 的 `o1` 实际是 `agentA = pga6filing, agentB = pga6restructure`（即 Spec B 先于 Spec A），`o2` 才是 `agentA = pga6restructure, agentB = pga6filing`（Spec A 先于 Spec B）。

| Case / Pair ID | 准确 Case 名称 | Spec Role A (`task_id`) | Spec Role B (`task_id`) | `paragui_attack_combos.txt` 顺序 (`o1`: `agentA`, `agentB`) | 反转顺序 (`o2`: `agentA`, `agentB`) | 共享软件与核心冲突面 |
|---|---|---|---|---|---|---|
| **`A1` (`a1`)** | Elmbrook House Care Home: leave approvals vs filling the open shifts of the same week | `pga1leave`（按休假制度审批第 47 周 6 条请假单、为获批者安排合规替班并写汇总文本） | `pga1rota`（按排班规则填满同周 8 个 OPEN 空缺班次并从打印视图导出 PDF） | `o1`: `agentA=pga1leave`, `agentB=pga1rota` | `o2`: `agentA=pga1rota`, `agentB=pga1leave` | 同一 Chrome + 内网排班系统 `RotaDesk` (`127.0.0.1:8131`, SQLite `rotadesk/app.db`)；B 优先安排未满合同班次的请假申请人（如将 Amy 排入周四早班），A 基于旧快照批假导致“获批休假期间仍在岗” |
| **`A3` (`a3`)** | Copper Lane Cycles: one open Calc stock workbook — booking in deliveries vs applying a stock-take | `pga3goodsin`（读取 3 份扫描送货单 PDF，累加实收库存、更新收货日期、记 `Goods in` 日志并写缺货单） | `pga3stocktake`（读取 2 份手写盘点扫描件，按盘盈亏差值修正库存、删 3 行停产项、按序插 2 行新品并建 `Variance 2026-11` 表） | `o1`: `agentA=pga3goodsin`, `agentB=pga3stocktake` | `o2`: `agentA=pga3stocktake`, `agentB=pga3goodsin` | 单实例 LibreOffice Calc 打开同一 `~/Documents/Stock/parts_stock.xlsx`；9 个重叠 SKU 的读改写覆盖、B 删插行导致 A 记忆行号错位，以及脚本改盘 vs Calc 内存保存相互覆盖 |
| **`A5` (`a5`)** | Fenwick & Bloom Home & Garden: one shop back office — supplier price increase vs Black Friday sale | `pga5prices`（按供应商调价扫描函更新 10 款商品进价与零售价、重算在促商品折后价、停产下架并导出 CSV） | `pga5sale`（按带手写批注的黑五传单校样设置 13 款商品促销价/日期/标签并导出印刷价目表 CSV） | `o1`: `agentA=pga5prices`, `agentB=pga5sale` | `o2`: `agentA=pga5sale`, `agentB=pga5prices` | 同一 Chrome + 电商后台 `ShopAdmin` (`127.0.0.1:8135`, SQLite `shopadmin/app.db`)；8 款商品重叠，全字段表单无锁保存造成 `LOST UPDATE`，或 B 按涨价前旧零售价算出 `STALE` 折扣价 |
| **`A6` (`a6`)** | Kestrel Lane Accountants: restructuring the client files vs filing the morning post | `pga6restructure`（按合伙人扫描备忘录与 12 份客户登记扫描件，将 `~/Clients` 重组为 `Active\|Ceased/<Surname>, <First> (<ID>)/<ID>_<Type>_<YYYY-MM-DD>.pdf`，重写 `README.txt` 与 `index.csv`） | `pga6filing`（读取 `~/Scans/Inbox` 12 份晨间来信扫描件，去重并留存非客户信件，将其余 10 份按 `README.txt` 规范归入对应客户目录并写 `filed_log.csv`） | **`o1`: `agentA=pga6filing` (Spec B), `agentB=pga6restructure` (Spec A)** | **`o2`: `agentA=pga6restructure` (Spec A), `agentB=pga6filing` (Spec B)** | 同一用户目录树 `~/Clients` + `~/Clients/README.txt` + 双 Nautilus 窗口；A 批量重命名期间 B 归入旧命名文件，或 B 读旧 `README` 后 `mkdir -p` 重建旧目录导致客户档案分裂 |
| `A2` (`a2`，同族非目标) | Varga & Hale Architects: one Thunderbird calendar — meeting requests vs site inspections & design reviews | `pga2requests` | `pga2visits` | `o1`: `pga2requests`, `pga2visits` | `o2`: `pga2visits`, `pga2requests` | 单实例 Thunderbird 115 日历 `local.sqlite` 3 个空闲时段争抢（注：`v1_NOTES.md` 记录无 KVM 下 Thunderbird 存在黑屏问题） |
| `A4` (`a4`，同族非目标) | Tidewater Community Libraries website: two new pages in one working tree | `pga4closures` | `pga4fees` | `o1`: `pga4closures`, `pga4fees` | `o2`: `pga4fees`, `pga4closures` | 单 Git 工作树与暂存区（5 个共享文件 `git add` 互卷对方未完 hunk / `git stash` 清空对方修改） |

### 2.2 代码与 Fixture 版本：Git 版本 vs 工作区磁盘版本及哈希

1. **源码、任务类、构建器与检查器版本核验**：
   - 本地开发机 `/home/v-yukezhao/code/paraGUI/CoDesk` 磁盘上的全部 `a1`–`a6` 相关文件（`spec_a1..a6.md`、`build_a1..a6.py`、`pg_a1..a6.py`、`task_pga1..6*.py`、`app_a1.py`、`app_a5.py`、`pg_common.py`、`lib_x.py`、`lists/paragui_attack_combos.txt`、`tasks/paragui/ATTACK_DEFENSE.md`、`oscombo/defense/{__init__,noop,v1}.py`）与 **`origin/yuke-osworld` (`976024720adba9a6087ec4c8526f26be0c8555db`)** 及 **`origin/codex/all-codesk-cases-20261113` (`25115031884ac9476024c54fc0f12753cd577651`)** 上的 Git blob **100% 逐字节一致（零未提交修改）**。
   - 全部 62 个追踪文件的精确字节大小、SHA-256 与 Git Blob OID 已完整收录于同目录 [`task-fixture-manifest.json`](task-fixture-manifest.json)。

2. **生成的运行时 Fixture 资产（`$PARAGUI_TASK_ASSETS/<pair>/`）确定性与哈希边界**：
   - 历史运行时的预构建 `$PARAGUI_TASK_ASSETS` 目录快照在远程仓库与可访问服务器上均 **未找到/未知**。
   - 经对构建器源码做无副作用临时目录双次构建核验（详见 `task-fixture-manifest.json` 的 `generated_fixture_assets`）：
     - **完全跨构建逐字节确定性资产（固定 SHA-256）**：
       - `a1/app_a1.py`：`6be1a51dca3c8315a4181863994af8658fca15f80bb9a29736ffd3383e925726`（`34,197` B）
       - `a1/rotadesk_seed.db`：`3408d95c4df37570559e93ac58fef6ae4c81ae51d87b9a1a09b3f5cbc417087b`（`45,056` B）
       - `a1/expected.json`：`45f4efaa1fa63bbc32c3e7e2156eef63dd6fff4b8ed0d8163623ebcce12afad7`（`4,246` B）
       - `a3/expected.json`：`b747f6f51c84b1c6826231c185b2bd996f8d0ceac644ec0e867a66f1ca28fc5b`（`16,759` B）
       - `a5/app_a5.py`：`ff80687cf81b634baf51646794bf9f428474f2fe21215fc2d9adbee179f1ab70`（`26,972` B）
       - `a5/shopadmin_seed.db`：`2ad9497a9d826443c2a570f145d1b56daed671c3e67402335dbb52b16c476c99`（`65,536` B）
       - `a5/expected.json`：`fcbb4820cee5f2ce07f7baa65b1c619d4e91894940fb9d82587f8996632e52f4`（`21,157` B）
     - **语义与随机种子固定、但字节流含构建时间戳/噪点的资产**（正如提交 `9760247` 在 `tasks/paragui/README.md:34-36` 专门注明）：
       - `a3` 的 `parts_stock.xlsx`（`openpyxl` 写入 ZIP 时间戳）及 5 份扫描 PDF（`lib_x._degrade` 调用 `PIL.Image.effect_noise` 且 PDF 含 `CreationDate`）；
       - `a5` 的 `Greenleaf_price_change_Nov2026.pdf` 与 `BF_flyer_proof_marked.pdf`；
       - `a6` 的 `a6.tar.gz` 与 `a6/expected.json`（`a6/expected.json` 记录同一次 `build_a6.py` 生成的 50 份扫描 PDF 的 MD5 供 `pg_a6.py` 追踪文件搬移，因此同一批次必须固定使用同一次 `oscombo tasks install` 产出的 `a6.tar.gz` 与 `a6/expected.json`）。

---

## 3. 实际运行配置核查

> **重要区分**：由于 `a1`–`a6` 的在线大模型运行 `result.json` 与 `run_env.json` **未找到/未知**，下表同时给出 **（1）`a1`–`a6` 历史实跑记录状态** 与 **（2）仓库代码及部署规范中为该任务族配置的准确参数**，绝不将代码默认值伪装为已找到的实跑日志。

| 配置维度 | `a1`–`a6` 历史实跑原始记录 | 仓库代码与协议配置（`oscombo` `9760247` / `2511503` + `ATTACK_DEFENSE.md` + `SERVER_PLAN.md`） |
|---|---|---|
| **模型准确名称 / 版本** | **未找到/未知** | `ATTACK_DEFENSE.md:7-8` 记录同框架 dataset-v1 基线模型为 **`gpt-6-astra`**。（注：仓库另一条合成工作流线 A2 `V1–V47` 使用 `gpt-6-sol`，CPU15 新近套件主要使用 `gpt-6.1-sol` 与 `gpt-6-astra`） |
| **Reasoning Effort / 推理参数** | **未找到/未知** | `oscombo/cli.py:72` 与 `oscombo/policies/openai_cua.py:76` 默认 `reasoning_effort = "medium"`（环境变量 `OSCOMBO_REASONING_EFFORT` 或 `--effort` 覆盖）；`max_tokens` 默认不额外截断（由服务端默认决定） |
| **API Endpoint 服务名称（不含任何 API Key）** | **未找到/未知** | 通过 `OPENAI_BASE_URL` 接入 OpenAI 兼容 Responses API 服务（原生支持 `computer` 工具的 OpenAI / Azure OpenAI `.../openai/v1` 服务端点或团队内部 OpenAI 兼容 LLM Proxy 网关）。**本交接包不包含任何 API Key 或私有凭据** |
| **Harness 类型与版本 / Commit** | **未找到/未知** | 对抗轮协议绑定 **`oscombo` 内置 `step` Harness**（`oscombo/harness/step_loop.py` + `--policy openai-cua`，封装官方 OSWorld `GPTResponseAPIAgent`），源码提交 `e2727e4339c8c1c0bfcce229ab043a578a522286` / `976024720adba9a6087ec4c8526f26be0c8555db`。注意 `oscombo/runner.py:318` 明确规定 `--defense v1` **仅对 `step` Harness 生效**，外部 `codex`/`pi` Harness 会跳过 `--defense` |
| **Codex CLI 版本** | 若使用 `step` Harness 则不涉及 Codex CLI；若外部曾用 `codex` Harness 则版本 **未找到/未知** | 仓库当前环境实测版本供参考：开发机 `GCRAZGDL1707` 为 `codex-cli 0.167.1`；执行机 `cpu15:~/data/paraGUI/runtime/codex/codex` 为 `codex-cli 0.163.0`；A2 `V1–V47` 报告记录为 `codex-cli 0.165.0` |
| **OSWorld 版本 / Commit 与镜像** | 代码固定（`setup_osworld.sh`） | `https://github.com/xlang-ai/OSWorld-V2` tag **`osworld-v2.1`**，固定 commit **`3d778a3c9a34a079316f70df023b166700445792`**；Ubuntu 22.04 GNOME X11 镜像包 `osworld-v2-ubuntu-x86.qcow2.zip`（HF `xlangai/v2-image` commit `6e16459a2feb5a8f1ed65babcfe7a2a6205d049d`，SHA-256 `14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3`；无 KVM 时经 `infra/make_pngfast_image.sh` 转为 `pngfast` 镜像） |
| **Agent 可用工具面（GUI / Shell / 其他 MCP）及 Shell 所在位置** | **未找到/未知** | 1) **`step` Harness（对抗轮标准）**：模型仅使用原生 `computer` 工具（全屏 `1920x1080` 截图输入，转译为 Guest 内 `pyautogui` 执行），**无任何宿主机/容器 Shell 工具，也无其他 MCP**；若模型需执行终端命令，只能通过桌面 GUI 按 `Ctrl+Alt+T` 打开 **Ubuntu Guest 内部**的 `gnome-terminal` 并敲入命令（`defense v1` M6 将快捷键重写为带私有 `--role` 的 Guest 内 `gnome-terminal`）。<br>2) **`codex` Harness（外部对照）**：仅挂载 `oscombo.desktop_tools --mcp`（9 个工具：`screenshot, click, drag, move, type_text, key, scroll, wait, declare_infeasible`，`1280x720` 缩放截图），配置 `sandbox_mode = "read-only"`、`shell_tool = false`、无其他 MCP；同样没有任何宿主机/容器 Shell，仅能通过 GUI 操作 Guest 内终端 |
| **每 Actor 工具步数预算及计费口径（只算 GUI 还是 GUI+Shell）** | **未找到/未知** | 1) **`step` Harness**：`tasks/paragui/README.md:30` 与 `docs/SERVER_PLAN.md:190` 为长程 `paragui` 任务指定 **`--max-steps 150`**（CLI 裸默认 `25`，`spec_a4.md:124` 亦提及 `100`），每 `chain_steps = 40` 次预测自动携带最近 12 步摘要重开新会话链以绕过单链 50 张图上限。预算单位为 **模型预测轮次（`predict` turns）**：无论该轮输出点击还是向 Guest 终端敲脚本，均按 1 轮计费（因不存在独立 Shell 工具）。<br>2) **`codex` Harness**：`max_steps` 统计**全部 `desktop` MCP 调用次数**（含 `screenshot` 与 `wait`，仅 `declare_infeasible` 不计入耗尽判定），无独立 Shell 工具 |
| **超时设置（Timeout）** | **未找到/未知** | 1) **`step` Harness 单 Actor 墙钟上限**：`wall_s = 7200` 秒（2 小时，`step_loop.py:35`，超时置 `status = "timeout"`）。<br>2) **`codex` Harness 单 Actor 上限**：`options.timeout = 2400` 秒（40 分钟，`external.py:109`），单次 MCP 工具超时 `300s`。<br>3) **Guest 与队列级超时**（`configs/env.{vm10,cpu15}.example.sh`）：VM 启动就绪 `1800s`、桌面绘制等待 `240s`、单帧截图耐心 `300s`、`setup_settle = 20s`、`eval_settle = 15s`、`queue --run-timeout = 21600s`（6 小时，CLI 裸默认 `0` 不限时） |
| **重试设置（API 层与 Run 层）** | **未找到/未知** | 1) **API 请求层**：`openai_cua.py:45-67` 对 HTTP `429` 随机退避 `2–10s` 重试最多 `60` 次（`OSCOMBO_RATE_LIMIT_RETRIES`），对 `500/502/503/Timeout/Connection` 指数退避 `30s -> 240s` 重试最多 `5` 次；`transports.py` 对 `429` 重试 `60` 次、其他瞬态码重试 `8` 次；`CodexHarness` 设 `request_max_retries = 6`。<br>2) **队列 Run 层**：`oscombo queue` 仅对命中 `INFRA` / 缺失 `result.json` 的基础设施故障局移入 `_infra/` 并补跑 **1 次**；业务低分、`max_steps`、`timeout`、`[INFEASIBLE]` 绝不自动重跑 |

### 3.1 各实验模式的桌面隔离性、Guest 数量、启动顺序/间隔与重复次数

以下整理自 `oscombo/runner.py`、`oscombo/cli.py`（`matrix` / `queue`）及 `tasks/paragui/ATTACK_DEFENSE.md:48-50`：

| 模式 (`mode`) | 桌面形态（独立 vs 共享） | 每局 Guest 数 | 同局内 Setup 与 Actor 启动顺序 / 间隔 | 每对任务标准重复与顺序数（`ATTACK_DEFENSE.md` / `oscombo matrix`） | 队列级跨局启动间隔 (`queue --stagger`) |
|---|---|---:|---|---|---|
| **`solo`** | 独立单任务桌面 | **1** | 单任务 `DesktopEnv.reset` -> 等待 `setup_settle = 20.0s` -> `agentA` 独立运行 | 每子任务 **1 次**，每对共 **2 局**（`task1 ×1`、`task2 ×1`） | CLI 默认 `20.0s`；VM10/CPU15 模板 `60s` |
| **`isolated`**（并发负载对照，可选） | **独立桌面**（每 Actor 独占 1 台 VM） | **2** | 并发启动 2 台 Guest，Guest 0 立即启动、Guest 1 延迟 **`isolated_boot_stagger = 30.0s`** 启动以避开端口竞争；两台均就绪并等待 `20.0s` 后，由 **`threading.Barrier(2)` 零间隔同步释放** `agentA` 与 `agentB` | `1 个顺序 × 1 次 = 1 局`（`isolated:1`） | 同上（注意 `--lanes 1` 下单局仍占 2 台 Guest） |
| **`sequential`** (`seq`) | **共享同一桌面与同一应用实例** | **1** | 在同一 Guest 内依次执行 `task_first.setup()` 与幂等的 `task_second.setup()` -> 等待 `20.0s` -> **`agentA` 完整运行结束 -> 间隔 `0s` 紧接着启动 `agentB`** -> 双任务解耦后置保存与分别评分 | **2 个顺序 × 1 次 = 2 局**（`o1: T1->T2`、`o2: T2->T1`） | 同上 |
| **`parallel`** (`par` / `defense:v1`) | **共享同一桌面与同一应用实例** | **1** | 在同一 Guest 内依次执行两任务的幂等 `setup()` -> 等待 `20.0s` -> 双方完成 `prepare()`（若开 `--defense v1`，在计时钟前串行执行 `defense.start()`）-> **`threading.Barrier(2)` 同一时刻零间隔（`0s` stagger）并发释放** `agentA` 与 `agentB` | **2 个顺序 × 2 次重复 = 4 局**（`o1-r1, o1-r2, o2-r1, o2-r2`）；红蓝对抗需分别对照 `--defense noop` 与 `--defense v1`（6 对攻击轮单防护矩阵共 `2×6 + 2×6 + 4×6 = 48` 局） | 同上 |
| **`shadow`**（纯轮询负载对照，可选） | 共享同一桌面（仅 A 操作，B 只截图轮询） | **1** | 双任务 `setup()` -> `20.0s` -> `Barrier(2)` 同步启动 `agentA` 与每 `3–8s` 截图一次的 `ShadowPoller` | 按需对照（`shadow:1`） | 同上 |

---

## 4. 失败与并发干扰的机制证据及精简片段说明

由于 `a1`–`a6` 没有已同步的大模型在线 `trace.jsonl`，**真实 LLM 逐步动作轨迹标为“未找到/未知”**。但仓库内的检查器源码（`pg_a1.py`、`pg_a3.py`、`pg_a5.py`、`pg_a6.py`）与规范自测记录（`spec_a1.md`、`spec_a3.md`、`spec_a5.md`、`spec_a6.md`）完整保留了确定性并发交错如何击穿单侧防护并触发精确诊断子项的机制链条：

1. **`A1`（`pga1leave` + `pga1rota`）—— 跨页面数据库不变量冲突（`0.60 / 0.60`）**
   - **交错过程**：`pga1rota`（B）按规则优先选择低于合同班次数的员工，在初始排班表上将 `Amy Clarke` 填入 `2026-11-19 E`（周四早班 OPEN 槽位）；与此同时 `pga1leave`（A）基于稍早读取的请假页快照批准了 `Amy Clarke` 周三至周四的年假，仅替掉了她原有的周三早班。RotaDesk 服务端照常返回保存成功，但最终数据库中 `Amy Clarke` 在已批准休假的周四仍被排班。
   - **检查器子项判定**（`tasks/paragui/pg_a1.py:133-168,200-238`）：
     - `evaluate_leave`：`checks["requesters_off_shift"]["Amy Clarke"] = False`，触发硬上限 `(not all(off.values()), 0.6)`，得分封顶 **`0.60`**（`< 0.8` FAIL）。
     - `evaluate_rota`：`checks["rostered_on_leave_in_open_slots"] = ["Amy Clarke 2026-11-19 E"]`，触发硬上限 `(bool(on_leave_b), 0.6)`，得分封顶 **`0.60`**（`< 0.8` FAIL）。

2. **`A3`（`pga3goodsin` + `pga3stocktake`）—— 共享工作簿读改写覆盖、行号漂移与 GUI/CLI 脑裂**
   - **三种已验证干扰模式**（`tasks/paragui/spec_a3.md:122-138`、`pg_a3.py:143-286`）：
     - *读改写丢失更新（Lost Update）*：9 个带非零盘点差值的 SKU 全部同时出现在本周到货单中；双方先读取 `On hand` 再各自心算写入，后写入方静默抹掉先写入方的增量，受害方触发 `(ok_oh < 6, 0.4)` 或 `(nz_ok < 4.5, 0.4)`，得分 **`0.40`**。
     - *删插行引发的行号错位（Row Shift）*：B 删除 `BRK-104`、`CBL-410`、`TUB-707` 3 行并插入 `CBL-411`、`TYR-824` 2 行，A 若按先前搜索记住的行号（如 `E19`）输入数量与日期，数据落入相邻无关 SKU，`checks["other_skus_changed_or_missing"]` 非空且 `ok_oh` 跌破半数，A 得分 **`0.40`**。
     - *脚本改盘 vs 打开的 Calc 内存文档覆盖*：A 在终端用 `openpyxl` 脚本直接修改磁盘上的 `parts_stock.xlsx`，B 在已打开的 Calc 窗口按 `Ctrl+S` 将旧内存模型整表写回磁盘，A 的 12 笔入库全部蒸发，仅剩独立文本文件 `backorders_2026-11.txt` 的 `0.15` 分（**`0.15 / 1.00`**）。

3. **`A5`（`pga5prices` + `pga5sale`）—— 无乐观锁全字段表单覆盖与陈旧基准派生价**
   - **两种已验证干扰模式**（`tasks/paragui/spec_a5.md:122-135`、`pg_a5.py:98-235`）：
     - *双标签页全字段表单覆盖（`race_stale_forms`: `0.75 / 0.75`）*：8 款商品同时需要 A 改成本/零售价、B 设黑五促销；双方各自打开同一商品编辑页后提交，后一次 `POST` 将表单内旧字段原样写回。检查器通过审计表 `changes` 精确识别并输出：
       - `evaluate_prices`：`"LOST UPDATE: the right price was saved, a later save overwrote it"` -> 触发 `0.75` 封顶；
       - `evaluate_sale`：`"LOST UPDATE: a sale price was saved, a later save cleared it"` -> 触发 `0.75` 封顶。
     - *陈旧零售价基准计算（`race_stale_plan`: `0.75 / 0.7415`）*：B 先抄下涨价前零售价计算 `-20%`/`-25%` 促销价，期间 A 完成涨价，B 随后填入旧促销价，检查器检出 8 款商品 `"STALE: computed from the pre-increase retail"`（且 A 的 `promo_sale_prices_stale` 非空），双双低于 `0.8`。

4. **`A6`（`pga6restructure` + `pga6filing`）—— 共享目录树重命名窗口与新旧命名规范分裂**
   - **两种已验证干扰模式**（`tasks/paragui/spec_a6.md:129-142`、`pg_a6.py:114-272`）：
     - *陈旧目录快照批处理（`stale A listing`: `0.75 / 0.75`）*：A 先扫描初始目录列清单并逐份阅读 12 张扫描登记表，期间 B 按旧 `README.txt` 将晨间来信以 `YYYYMMDD description.pdf` 放入客户目录；A 执行重命名脚本时移动了整个文件夹但漏改新放入的文件名，导致新目录下混入旧格式文件，触发 `evaluate_restructure` 的 `(not others_clean, 0.75)` 封顶，同时 `evaluate_filing` 因新目录下文件名不符合新规范扣减 `named_ok` 至 **`0.75`**。
     - *陈旧 README 归档重建旧目录（`stale B README`: `0.75 / 0.25`）*：B 先读旧 `README.txt`，A 随后将 `~/Clients/SMITH_Jon` 迁至 `~/Clients/Active/Smith, Jonathan (KL-1043)` 并改写 `README.txt`；B 执行 `mkdir -p ~/Clients/SMITH_Jon && mv ...` 静默重建已废弃的旧目录，造成客户文件分裂在两个目录中，`stray_dirs_or_files` 使 A 封顶 **`0.75`**，B 因文件未落入持有客户登记表的权威目录（`placed < 5` 封顶 `0.40`）仅得 **`0.25`**。

---

## 5. 过 Gate 关键证据 vs 仅属推测的结论

### 5.1 仓库内可独立复核的确定性事实证据

1. **题目本身的四门良定性（Well-posedness）证据充分**：
   - `A1`、`A3`、`A5`、`A6` 的任务源码、资产构建器与双角色检查器完整保存在 Git（`e2727e4` / `9760247` / `2511503`）。
   - `build_a1.py`（第 106–124 行 `verify(rota)`）在构建期对全部 **72,296 种** B 先填满空缺班次的合法方案与全部 **28 种** A 先安排替班的合法方案做了穷举数学证明，保证无论谁先做都绝不会锁死对方；`pg_a3.py` 兼容“单方增量或双方增量叠加”；`pg_a5.py` 允许印刷价目表匹配涨价前或涨价后任一自洽快照；`pg_a6.py` 同时解析新旧目录路径。
   - `spec_a1.md`、`spec_a3.md`、`spec_a5.md`、`spec_a6.md` 记录了完整的 48 组出题离线自测结果（`pristine <= 0.1077`、单跑 `1.0`、双向顺序 `1.0/1.0`、并发陈旧快照冲突全部精准压在 `0.15–0.75 < 0.8`、谨慎重读交错 `1.0/1.0`）。
2. **对单侧防护 `--defense v1` 的机制穿透性（Structural Immunity）可由源码直接证明**：
   - 核查 `oscombo/defense/v1.py` 的全部 7 项机制（M1 通用提示、M2 首动作重激活原截图窗口、M3 逐字符焦点守卫输入、M4 截图前恢复自有窗口、M5 复制独立 Chrome Profile、M6 独立 `--role` 终端窗口、M7 关闭窗口回退）可知：它们解决的都是**窗口焦点、键鼠串扰、浏览器会话 Cookie 与共享终端**层面的冲突。
   - 而 `A1` 与 `A5` 的冲突发生在**服务端同一个 SQLite 业务库**（独立 Chrome Profile 仍读写同一张表），`A3` 的冲突发生在**同一个打开的 Calc 工作簿数据模型与行号索引**（`v1_NOTES.md` 第 6 节亦自承无法在 v1 单侧修复），`A6` 的冲突发生在**同一个 `~/Clients` 文件系统命名空间**。因此在不违反蓝方 Rule 1/2（禁止跨 Harness 锁或告知同伴存在）的前提下，`Defense v1` 无法消除这四题的跨步语义竞争窗口。

### 5.2 缺乏原始记录支撑、仅属推测（Inference / Speculation）的部分

1. **`A1`、`A3`、`A5`、`A6` 在真实大模型下的实际过 Gate 结论目前无法在本地/远程复核**：
   - 由于没有任何 `a1`–`a6` 的大模型 `result.json` 或 `trace.jsonl` 被提交或同步到可访问存储，**“大模型在 `A1`、`A3`、`A5`、`A6` 上实际满足 `solo >= 0.8`、`seq both-pass >= 1/2` 且 `--defense v1` 下 `par both-pass <= 1/4`”目前没有原始运行文件可直接证实**。若此前在外部出题环境（如 `spec_a*.md` 提及的 `node 0 / node 1`）跑过在线筛选，其原始 `result.json` 需从原出题宿主机补拉后方可确认为实测事实。
2. **为何是 `A1`、`A3`、`A5`、`A6` 而非 `A2`、`A4` 的原因仅能推测**：
   - *技术推测（非实测记录结论）*：`docs/defense/v1_NOTES.md:40-42` 明确记录在无 KVM 的 QEMU TCG Guest 中 **Thunderbird 启动即黑屏**，而 `A2` 恰好依赖 Thunderbird 日历 UI（`A1`/`A3`/`A5`/`A6` 均不使用 Thunderbird）；`A4` 则是 Git + VS Code 代码仓任务，使用终端 `git status`/`git diff` 的强编码模型可能在并发下更容易察觉工作树脏块并手动避开或修复，或受限于单人手敲 14 条 JSON 的步数风险（`spec_a4.md:124`）。在找回 `a1`–`a6` 实跑日志前，这一解释仅作为代码与环境层面的合理推测。
