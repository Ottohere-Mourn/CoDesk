# A-Family (`a1`–`a6`：`A1`、`A3`、`A5`、`A6`) 可复现性只读审计与交接说明

本目录是对 `CoDesk` / `oscombo` 仓库中 **paraGUI Attack Round 1 红队对抗家族（`a1`–`a6`，重点覆盖 `A1`、`A3`、`A5`、`A6`）** 的只读可复现性审计归档。审计严格遵守：不重跑模型、不修改任何原任务/检查器/原分支、不输出任何 API Key，对找不到的原始记录一律标为 **`未找到/未知`**。

---

## 1. 本目录文件清单

| 文件路径 | 内容说明 |
|---|---|
| [`gate-and-protocol.md`](gate-and-protocol.md) | 原始 Gate 定义、代码行号与 Commit、单/双任务及顺序通过规则、筛选标准 vs 报告汇总指标、各 Case 任务映射（含 `A6` 顺序反转说明）、实际运行配置核查、并发干扰机制证据、确定性证据 vs 推测边界 |
| [`run-index.csv`](run-index.csv) | 共 **80 行**：前 **32 行**为 `A1/A3/A5/A6` 在线大模型标准矩阵槽位（`solo ×2`、`seq ×2`、`par ×4`，逐项标明 `未找到/未知`）；后 **48 行**为 `spec_a1/a3/a5/a6.md` 记录的全部出题期离线自测运行（含正控、残缺负控与并发陈旧快照/行号漂移/表单覆盖失败局） |
| [`task-fixture-manifest.json`](task-fixture-manifest.json) | 机器可读清单：仓库与 OSWorld 固定 Commit、远程仓库同步状态、`a1`–`a6` 角色/任务 ID/顺序映射、生成资产跨构建确定性核验，以及全部 **62 个相关源码与文档文件的字节数、SHA-256 与 Git Blob OID** |
| [`results/live-model-runs-missing.json`](results/live-model-runs-missing.json) | 在线大模型原始 `result.json` / `trace.jsonl` 检索范围记录与 `oscombo` 标准脱敏 `result.json` 结构规范 |
| [`results/a1-selftest-audit.json`](results/a1-selftest-audit.json) | `A1` (`pga1leave` + `pga1rota`) 检查器权重/硬上限与 12 组离线自测得分记录 |
| [`results/a3-selftest-audit.json`](results/a3-selftest-audit.json) | `A3` (`pga3goodsin` + `pga3stocktake`) 检查器权重/硬上限与 14 组离线自测得分记录 |
| [`results/a5-selftest-audit.json`](results/a5-selftest-audit.json) | `A5` (`pga5prices` + `pga5sale`) 检查器权重/硬上限与 10 组离线自测得分记录 |
| [`results/a6-selftest-audit.json`](results/a6-selftest-audit.json) | `A6` (`pga6restructure` + `pga6filing`) 检查器权重/硬上限与 12 组离线自测得分记录 |

---

## 2. 缺失项清单（明确标为“未找到/未知”）

经只读遍历远程仓库 `origin`（全部 19 个分支）、开发机 `GCRAZGDL1707`、跳板机 `yuke-jump`、执行节点 `cpu15`（`~/data/paraGUI`）、GPU 节点 `g4-45`（`~/data/paraGUI`）、GenAI UKSouth 共享盘（`/yf_blob/yuke`）与 GNet 共享盘（`/mnt/gnet/yuke`），以下原始记录确认 **未找到/未知**：

| 缺失项类别 | 当前状态 | 核查依据与原因说明 |
|---|---|---|
| **`a1`–`a6` 大模型在线运行 `result.json`** | **未找到/未知** | 根 `.gitignore` 自初始提交 `63a9e9a` 起忽略 `runs/` 与 `out/`；`2026-10-23` 从外部出题环境推送 `origin/yuke-osworld` (`e2727e4` / `9760247`) 时未提交任何运行产物；此后在 `GCRAZGDL1707`、`cpu10`、`cpu15`、`g4-45` 上亦未对 `lists/paragui_attack_combos.txt` 发起过大模型多臂运行（与 `docs/ALL_CASES_HANDOFF_20261113_ZH.md` 第六节“尚未单独发起完整大模型多臂实测”一致） |
| **`a1`–`a6` 大模型逐步轨迹 `trace.jsonl`、截图与 `driver.log` / `queue_*.log`** | **未找到/未知** | 同上，未随 `yuke-osworld` 同步至 Git 或可访问服务器 |
| **`a1`–`a6` 失败、超时、`max_steps`、`[INFEASIBLE]` 及 `_infra/` 重试记录** | **未找到/未知** | 无在线运行目录，故各局原始判定 vs `_infra/` 重试判定、Actor 终态（`done/timeout/max_steps/fail/error`）、实际步数、墙钟耗时与 Token 用量均为 **未找到/未知** |
| **`a1`–`a6` 历史实跑时的 `run_env.json` / `env.sh`（模型准确版本、推理档位、预算参数）** | **未找到/未知** | `.gitignore` 排除 `env.sh` 与 `*.local.sh`；仓库仅保留模板 `configs/env.{example,vm10.example,cpu15.example}.sh` 与 `ATTACK_DEFENSE.md` 基线说明 |
| **出题宿主机离线自测驱动脚本 `lib_atest_a1..a6.py` 及 `lib_xtest.py` / `lib_mselftest.py` / `lib_dselftest.py`** | **未找到/未知（未入库）** | `tasks/paragui/README.md:59-62` 明确注明：*"Those harnesses depend on the authoring host and are not part of this repository."* 仓库内仅在 `spec_a1..a6.md` 保留了自测结果汇总表 |
| **历史运行时的预生成 `$PARAGUI_TASK_ASSETS/{a1..a6}/` 目录快照** | **未找到/未知** | 开发机与 `cpu15:~/data/paraGUI/assets` 均为空；源码 `build_a1..a6.py` 完整在库，其中数据库与 `a1/a3/a5` 的 `expected.json` 可逐字节复现，扫描 PDF / XLSX / `a6.tar.gz` 含构建时间戳（提交 `9760247`） |
| **旧执行机 `cpu10` (`yifan-cpu-wus3-10`) 实时在线核验** | **机器宕机 / SSH 连接超时** | `2026-11-21` 经跳板机实测 `cpu10` SSH 连接超时；但本地留存的 `2026-10-26` 磁盘扫描 `runs/maintenance/vm10-disk-cleanup-20261026T1543Z/du-yuke.tsv` 与会话恢复包 `runs/recovery/20261113-session-01a1c8e6/` 显示 `cpu10` 上同样未曾创建过 `a1`–`a6` 运行目录 |

---

## 3. 与远程仓库（`origin`）同步状态核查

远程仓库地址：`git@github.com:Ottohere-Mourn/CoDesk.git`（HTTPS：`https://github.com/Ottohere-Mourn/CoDesk.git`）。

1. **A-Family 源码、规范、检查器与防护插件：已 100% 与远程仓库同步**
   - `lists/paragui_attack_combos.txt`、`tasks/paragui/ATTACK_DEFENSE.md`、`oscombo/defense/{__init__,noop,v1}.py`、`docs/defense/v1_NOTES.md` 以及 `a1`–`a6` 全部 32 个任务/构建器/应用/检查器/规范文件，在本地工作区 `/home/v-yukezhao/code/paraGUI/CoDesk` 与远程分支 **`origin/yuke-osworld` (`976024720adba9a6087ec4c8526f26be0c8555db`)**、**`origin/codex/all-codesk-cases-20261113` (`25115031884ac9476024c54fc0f12753cd577651`)** 之间 **SHA-256 完全相同，无任何未同步本地改动**。
2. **A-Family 运行结果与资产缓存：未与远程仓库同步（且本地亦无遗留）**
   - 如第 2 节所述，`.gitignore` 排除了 `runs/`、`out/`、`env.sh`、`*.qcow2*`，`origin` 全部 19 个分支中均不含 `a1`–`a6` 的 `result.json` 或 `trace.jsonl`。
3. **开发机原工作树（`codex/all-codesk-cases-20261113`）上的其他未同步本地内容（与 A-Family 无关，按只读原则保持原状未触碰）**
   - 原工作树 `HEAD` 指向 `25115031884ac9476024c54fc0f12753cd577651`（与 `origin/codex/all-codesk-cases-20261113` 一致），存在 1 个未提交修改（`tasks/human_agent_v1/pyautogui_shim.py`）和 37 项 `2026-11-16..20` 其他新套件的未跟踪文件/目录（`cua_drivers_h2h_v1`、`exam_contention_v1`、`macos_primitives_v1`、`mechanism_expansion_v2`、`real_mac_scen9_v1`、`recreationbench_v1` 等）以及被 `.gitignore` 忽略的 `runs/`。本交接分支通过独立 Git Worktree 从 `2511503` 切出并推送到 **`origin/codex/zyk-a-family-repro-handoff-20261121`**，未改动原分支与原工作树。

---

## 4. 原始材料位置与核心文件 SHA-256 哈希速查表

完整 62 个文件的 SHA-256 与 Git Blob OID 请见 [`task-fixture-manifest.json`](task-fixture-manifest.json)；以下列出 `A1`、`A3`、`A5`、`A6` 及 Gate 核心文件的精确哈希：

| Case / 模块 | 仓库相对路径 | 字节数 | SHA-256 | 与 `origin` (`9760247` & `2511503`) 一致 |
|---|---|---:|---|---|
| Combo 清单 | `lists/paragui_attack_combos.txt` | 413 | `1105770511fd9aa6505407165dbb0759398f6b821d073de7c8618edc4491d7f0` | 是 |
| Gate 与对抗规则 | `tasks/paragui/ATTACK_DEFENSE.md` | 4,729 | `54a0f5eae3d13cfc6bb18565201b0aad03a0ea1b23292b3f333a24bf6833144d` | 是 |
| 索引与判定脚本 | `tasks/paragui/tools/build_index.py` | 3,680 | `a26dc73cc459067461095738baf5ee7b84599803e745c55556d9be5499670799` | 是 |
| 汇总分析脚本 | `tasks/paragui/tools/analyze_v1.py` | 3,800 | `7dbbe49d3441ed17b56c53d7727cb6bf72a7c1fde854a7fcf4eb403900f1a2ad` | 是 |
| Defense 接口 | `oscombo/defense/__init__.py` | 3,157 | `5d12bb107f7e6623c1d549b322850215a6829148d831fd2c56204a6411013111` | 是 |
| Defense v1 实现 | `oscombo/defense/v1.py` | 33,195 | `3066ad101f141e0aba84ad0c40a9b316a6a2bcc4187d43f6272080fe56f544f9` | 是 |
| Defense v1 笔记 | `docs/defense/v1_NOTES.md` | 13,523 | `ea306e64d7d6425a386cf914d6bfff501cd14a2ec869aa123a2322225464046a` | 是 |
| **A1** 规范与自测 | `tasks/paragui/spec_a1.md` | 15,411 | `09bb56b485605e4e12aad95554ac3863caaec4426d0c973c3b200c971c6e5e5d` | 是 |
| **A1** Web 应用 | `tasks/paragui/app_a1.py` | 34,197 | `6be1a51dca3c8315a4181863994af8658fca15f80bb9a29736ffd3383e925726` | 是 |
| **A1** 资产构建器 | `tasks/paragui/build_a1.py` | 12,998 | `d99e76c8f495b2db9060cf21bb450ba894004544215a6fb97ee1f7db1397dacf` | 是 |
| **A1** Setup 与检查器 | `tasks/paragui/pg_a1.py` | 13,456 | `5f9d0b8c4f22ec4212569606c1cb0325a7e11a7a0a3d695a6006ce4b3b8d7e87` | 是 |
| **A1** 任务类 A | `tasks/paragui/task_pga1leave.py` | 1,671 | `91a5af23b0ce71e15e01c5f351f708279e7af259092eb84d74d3dde6e01360c7` | 是 |
| **A1** 任务类 B | `tasks/paragui/task_pga1rota.py` | 1,591 | `894d0d0215cb34039c660596a5fdfb6395f6cb30f301c5005ab56911d6bfd22a` | 是 |
| **A3** 规范与自测 | `tasks/paragui/spec_a3.md` | 14,546 | `ae998246becce5c91ad4ac727a16162b1beb8a56afee31373228187d70ad7b15` | 是 |
| **A3** 资产构建器 | `tasks/paragui/build_a3.py` | 17,237 | `feb86aa5410b7cc1fe525d9e0cf8549907a95a9df2b8e70f0d73ced343fd3a75` | 是 |
| **A3** Setup 与检查器 | `tasks/paragui/pg_a3.py` | 16,424 | `c5be6195c807a5ffc8fd43e8fe7d5525b179318983b994a7ca678f91d90f6e7d` | 是 |
| **A3** 任务类 A | `tasks/paragui/task_pga3goodsin.py` | 1,920 | `e2527970bbc623021a286c110b0da32e36bff1a389d6419c89ddf82cb752a5c2` | 是 |
| **A3** 任务类 B | `tasks/paragui/task_pga3stocktake.py` | 2,006 | `6f18b93cd948e207019e59a88bffa4f3f93e4dfe98b4788916874a1e76359b53` | 是 |
| **A5** 规范与自测 | `tasks/paragui/spec_a5.md` | 14,194 | `b24f68c28bf41deda1ce8d10e6c16a905e04dbd87f5fa379b067eded8fa1baea` | 是 |
| **A5** Web 应用 | `tasks/paragui/app_a5.py` | 26,972 | `ff80687cf81b634baf51646794bf9f428474f2fe21215fc2d9adbee179f1ab70` | 是 |
| **A5** 资产构建器 | `tasks/paragui/build_a5.py` | 22,001 | `decd48c79f8eb6f34add926659af288304653cecb88eb25753530523351a9a37` | 是 |
| **A5** Setup 与检查器 | `tasks/paragui/pg_a5.py` | 13,778 | `7c07d962625d8d556c9f249c0f45c470d9cf3b2ac202f0ca85c84c8cbfbf9a91` | 是 |
| **A5** 任务类 A | `tasks/paragui/task_pga5prices.py` | 1,716 | `05a6da65053dee51aaed8e5aab035913e17c3f3982aa9ea4cb706e17adc8e973` | 是 |
| **A5** 任务类 B | `tasks/paragui/task_pga5sale.py` | 1,653 | `dec63b445b98dbdf67c0e6e714e49bb004b00479b6899ca6b317fae56746caab` | 是 |
| **A6** 规范与自测 | `tasks/paragui/spec_a6.md` | 13,746 | `dcae1864cd92ccee0fcfbd2590ccb2de6db34233f23953f0bf98ef22ace87545` | 是 |
| **A6** 资产构建器 | `tasks/paragui/build_a6.py` | 17,367 | `9c73fd0b930404cd37d7b9fa20201e1956513e6be2a45e509d1f40c47db7f494` | 是 |
| **A6** Setup 与检查器 | `tasks/paragui/pg_a6.py` | 14,298 | `6a841d495dd89590faeb1b38b53acce84db9357462b74685d4da9ef9c36e3837` | 是 |
| **A6** 任务类（Spec A） | `tasks/paragui/task_pga6restructure.py` | 1,885 | `02b75442f4e07f585b95fbc9d5b8ab9503d8e2667a8b8b06de8ecabb9f31433e` | 是 |
| **A6** 任务类（Spec B） | `tasks/paragui/task_pga6filing.py` | 1,780 | `59b4db4bf5c8fd80bf2d94f61c6337df5b2fcf8ae9f33e122af93038545005a7` | 是 |

---

## 5. 命名消歧说明：仓库内其他已跑大模型的相邻套件（供交叉核对）

为回应审计要求中 *“如果你实际通过的是不同子任务，请列出准确 case 名称和 task ID”*，下表列出本仓库中容易与 `tasks/paragui` 红队 `a1`–`a6` 产生编号联想、且**确实在仓库/服务器留有在线大模型结果**的其他双智能体套件，供交叉比对（它们均不替代 `a1`–`a6`）：

| 套件族 | 准确 Case / Task ID | 在线大模型实测状态与仓库内结果位置 |
|---|---|---|
| **Track D 红队对抗 A-Family（本目录审计对象）** | `a1` (`pga1leave`, `pga1rota`)、`a2` (`pga2requests`, `pga2visits`)、`a3` (`pga3goodsin`, `pga3stocktake`)、`a4` (`pga4closures`, `pga4fees`)、`a5` (`pga5prices`, `pga5sale`)、`a6` (`pga6filing`, `pga6restructure`) | 出题离线自测 6/6 已记录于 `spec_a1..a6.md`；**在线大模型 `result.json` 未找到/未知** |
| **Track A1 早期 19-Case 机制与工作流** | 含 `A-01`、`AP-1`、`AUTH-1`、`C-03`、`CRM-LU1`、`CWD-1`、`DATA-REL1`、`EDIT-1`、`F-01`、`FIND-1`、`PAY-1`、`S-01`、`SITEACT-STATE1`、`U-01`、`VIEW-1`、`W1`、`Case-2`、`Case-3`、`Case-4` | 已跑 `gpt-6-sol` 三臂与 `gpt-6.1-sol` 四臂，汇总见 `docs/CODESK_19CASE_4ARM_SOL61_20261111.md`（本地 `runs/comparisons/codesk-19case-4arm-sol61-20261111-r1/`） |
| **Track A2 `tasks/paragui` 合成单窗口扩展** | `S1`, `K1`, `K2`, `Q1`, `E1`, `V1`–`V47`（`pg_v1..pg_v47.py`） | 已在 HealthCare 跑 `gpt-6-sol` 三臂（30 项命中 `PASS/FAIL/FAIL`），逐批次 Run ID 与 Token 审计已提交于 `tasks/paragui/*MODEL_RESULTS*.md` |
| **Track B1 `zyk` 专业软件与单会话竞争** | `PR-BLENDER-1`, `PR-QGIS-1`, `PR-FREECAD-1`, `PR-INKSCAPE-1` 及 `AR-01`–`AR-10` | 已在 `cpu10`/`cpu15` 跑 `gpt-6.1-sol` 与 `gpt-6-astra`（顺序全通、并发全挂），结果已提交于 `docs/PROFESSIONAL_RACES_FULL_CLI_V1_20261111.md`、`docs/ASTRA_HIGH_10TASK_RACE_SUITE_20261111.md` 及 `docs/results-manifests/` |
