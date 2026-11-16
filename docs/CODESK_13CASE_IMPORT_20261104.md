# 13-case 收纳、离线验证与运行边界

## 当前状态

后续用户已确认统一Codex、并发等配置参考原版；该口径及实际启动门禁见
`CODESK_13CASE_EXECUTION_GATE_20261104.md`。本文保留首次收纳/预检记录，不代表仍在等待选择四并发或双角色。

已收纳用户指定分支的 13 个 case，保留原始定义、源分支、commit、runner、历史状态和本次运行状态。
没有合并/切换当前脏工作树，没有覆盖已有 WeaveBench 数据或实验结果。
**本次已执行离线检查；新 Guest/模型实验数均为 0。离线通过不等于模型可解或 GUI 运行通过。**

- 入口实际位于 `docs/handoff/13-case-handoff/HANDOFF.md`。
- handoff commit：`1549126399c0be41b6bbc34d1b9b611381591b04`。
- 导入目录：`runs/imports/codesk-13case-20261104-r1/`。
- `catalog.json`：13 个 case 的登记表、runner 静态检查、历史结论及当前阻塞项。
- `provenance.json`：六个源码快照的分支、commit 和逐文件 SHA-256。
- `offline-tests-r2/summary.json`：本次原仓库聚焦测试结果；103 项通过，0 失败/错误/跳过。
- `runner-preflight/summary.json`：仅 `--help` 导入检查及共享 actor API 签名检查，不调用模型。

## 登记表

历史一栏只转录 handoff 的最新相关证据，不是本次新模型结果。每个达标项只有一组三臂筛查。

| ID | 任务/共享状态 | handoff 历史结论 | 本次准入注意事项 |
|---|---|---|---|
| Case 2 | 双人商品工单核验、Review ID交接、退款 | 三臂均PASS，成功/中性对照 | 可保留业务工作流；原runner绑定HealthCare Guest/密钥路径 |
| Case 3 | VS Code修复筛选脚本，浏览器重测 | 一组PASS/FAIL/FAIL | 需Guest、编辑器、浏览器、service bridge和原harness依赖 |
| Case 4 | Kdenlive时间线与清单另存 | 锁臂有效样本PASS | 需Kdenlive/MLT；不混合HDD/SSD历史cohort |
| F-01 | Writer/Calc焦点路由 | Shared被恢复，未达标 | 缺旧workflow helper与Hybrid v2依赖 |
| C-03 | 共享剪贴板覆盖 | 一组PASS/FAIL/FAIL | 缺旧workflow helper与Hybrid v2依赖 |
| A-01 | Chromium活动标签页 | 一组PASS/FAIL/FAIL | 缺Hybrid v2依赖；原协议对陈旧Enter进行调度 |
| S-01 | Calc活动单元格/选区 | 一组PASS/FAIL/FAIL | 缺Calc机制helper与Hybrid v2依赖 |
| U-01 | 共享Undo栈 | 一组PASS/FAIL/FAIL | 与S-01共用入口，不可误登记为同一任务 |
| CWD-1 | 持久shell的当前目录 | 一组PASS/FAIL/FAIL | 原runner为SolOSWorldAgent，不是当前Codex/Freehand桥接 |
| EDIT-1 | Writer插入/覆盖模式 | 锁臂恢复为PASS | 缺Writer overwrite helper及Hybrid v2依赖 |
| VIEW-1 | 滚动改变旧坐标命中位置 | 锁臂PASS，Shared归因弱 | 固定坐标及动作限制；不直接等同自然hybrid任务 |
| FIND-1 | Find/Replace Match Case状态 | 当前FAIL有目标约束冲突 | 先修复A/B提示矛盾、冻结新版本并重做独立基线 |
| AUTH-1 | 浏览器principal/cookie/session | 只有设计 | 没有模型runner；须先验证本地mock和独立机制 |

## 源码快照

| 快照 | 分支 | commit |
|---|---|---|
| handoff | codex/13-case-handoff-20261104 | 1549126399c0be41b6bbc34d1b9b611381591b04 |
| case2 | codex/case2-v12 | 953d68418e35864e176c8b5c54f3bd497c60b7d3 |
| case3 | codex/case3-followup | c6bcb56d9bd65bc37891d58a7f9e7d991349eaf2 |
| case4 | codex/case4-hardening | 3462672b50b73d08183528ba2148304b83438a89 |
| mechanisms | codex/focus-clipboard-pilot-20261102 | c866975460faa24db38c4722fafc8c6ddc367963 |
| hybrid_dependency_candidate | codex/case2-healthcare | b5745cd5bfbc15e645301b1118ae43299740050b |

快照采用 `git archive`，没有创建新工作分支，也没有把不同分支的 `oscombo` 强行混装。
完整最新HealthCare模型轨迹并不在交接包中；Git中已有的历史outputs保留原状，不伪装成新运行。
源码、隐藏oracle和gold fixture只用于控制器/评测，不可整棵挂进agent桌面。

## 已执行的离线检查

| 源组 | 聚焦测试数 | 结果 |
|---|---:|---|
| Case 2 | 15 | PASS |
| Case 3 | 11 | PASS |
| Case 4 | 4 | PASS |
| 机制与新候选 | 73 | PASS |

测试覆盖fixture、oracle正反例、交接审计、状态解析、调度判据和资源安全mock。
没有使用真实Guest、GUI模型或API；FIND/AUTH等缺少完整独立测试的条目不因此被宣称验证完成。
导入器另有5个测试通过。首次尝试因为解释器软链接解析丢失venv而未收集测试，日志保留在
`offline-tests/`；修正导入器后另建 `offline-tests-r2/` 重跑，未覆盖第一次记录。
源码逐文件哈希在离线检查后保持一致。

## 模型运行前的两个实际问题

### 源码/环境不是自包含交付

在已获取的源分支中，以下被runner引用的文件没有随交付提交：

- `oscombo/harness/hybrid_v2.py`；所提供的 `_run_model_actor` 也没有 `hybrid_v2` 参数。
- `scripts/run_workflows_qwen_v1.py`。
- `scripts/run_calc_mechanism_qwen_v1.py`。
- `scripts/run_sol_writer_overwrite_v1.py`。

这些不是API报错，不能靠重试模型解决。`runner-preflight/` 保存实际导入失败信息。
Case 3/4 在当前本地检查环境还缺 Python `docker` 包；这与缺失上游源码是两类问题。
多处原runner硬编码 `/home/mjh`、`/mnt/raid1`、Guest镜像、MCP解释器和工具路径，不能直接在CPU10照抄启动。
原版完整复现需补齐上述源文件/API版本并迁移runtime，不应自行猜实现后仍称原版复现。

### 实验口径不能静默改变

原case大多为两角色，按 **Isolated → Shared → Shared+逐动作锁** 逐臂推进，独立基线有效PASS后才能继续。
部分case使用只读Guest CLI、明确的GUI动作限制、协调器持有/释放陈旧动作、专门的collaboration工具。
这与现有 **Codex/Freehand + gpt-6-astra/high + 四并发 + 可写CLI/UNO + 自然调度** 不同。
例如 VIEW-1 原提示规定固定点击点、禁止搜索/CLI，并只允许B滚动一格；不能把它的历史结论当作宽权限自然任务结果。

下一轮必须明确选择原版复现，或建立独立命名的四角色改编cohort。
若改编，应先验证四个角色目标相容、fixture/oracle有效、CLI策略一致；不得简单复制A/B造成目标冲突。
若复现，应保留original条件、权限、gate和baseline，不暗中替换模型/harness或减少Guest数量。
本次没有自动切换到旧模型，也没有启动原仓库的整个队列。

## 本地重现收纳流程

先fetch表中各源分支，再在CoDesk下执行；输出目录必须是新的：

```bash
.venv/bin/python -m experiments.codesk_case_handoff \
  --repo . --out runs/imports/codesk-13case-<new-run-id> --offline-tests
.venv/bin/python -m pytest -q tests/test_codesk_case_handoff.py
```

CPU10数据根目录仍为 `/data/users/yuke`，不改旧用户权限，不使用全局Docker清理，不触碰其它正在运行的实验。
