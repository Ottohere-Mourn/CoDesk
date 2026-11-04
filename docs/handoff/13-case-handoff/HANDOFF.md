# CoDesk 13-case handoff

更新日：2026-11-04

## 一页结论

本分支汇总的是 13 个候选/案例：Case 2/3/4 + 早期五错误机制对应的五 case + 本轮新增的五候选。目标组合定义为：**Isolated 独立 PASS、Shared 共享 FAIL、Shared+Lock 共享加逐动作锁仍 FAIL**；失败必须是有效模型/协议运行，且能归因到共享状态，不把 API、Guest、评估器或 reset 无效运行算作任务 FAIL。

按每个 case 最新的相关证据，目前 **6/13 有一个有效 triplet 达到目标，7/13 尚未达到或仅有设计**：

- 达到：Case 3；C-03 Clipboard；A-01 Application Context；S-01 Selection；U-01 Undo/Redo；CWD-1 Terminal CWD。
- 未达到/待改：Case 2、Case 4、F-01 Focus/Input Routing、EDIT-1、VIEW-1、FIND-1、AUTH-1。
- 每个达到者目前都是单组三臂筛查，**没有第二次有效重复**，不代表稳定失效率或总体发生率。
- 早期五机制过去有 GUI-only/Qwen 的历史证据；此处 6/13 统计以已完成的 GPT-6-Sol Hybrid v2 重跑（若有）为准，不把历史 Qwen 结果冒充 Hybrid 结果。
- 备选 MODAL-1 不在同意的五候选和 13-case 总数中。

## 13-case 状态表

| # | 案例 / 当前任务 | 三臂最新结果与证据结论 | 当前交付状态 | 源分支与入口 |
|---:|---|---|---|---|
| 1 | Case 2：双人核验损坏商品工单、协作交接 Review ID、退款并结案 | v1.2.0 Isolated/Shared/Shared+Lock 均业务 PASS，严格交接均 PASS | 未达到共享故障目标；保留为有用的成功/中性对照 | codex/case2-v12 @ 953d684；infra/run_ticket_to_resolution_lite_healthcare.py |
| 2 | Case 3：A 在 VS Code 修复筛选脚本、B 在浏览器重测 | v1.4.3 一组三臂 Isolated PASS，Shared FAIL，Shared+Lock FAIL；轨迹支持跨窗口误路由 | **达到一次**；小样本，不是重复证据 | codex/case3-followup @ c6bcb56；infra/run_case3_lite_pair_pilot.py |
| 3 | Case 4：Kdenlive 时间线修复 + VS Code 清单另存 | SSD cohort：Isolated 2/2 PASS，Shared 0/2 PASS，Shared+Lock 1/1 PASS；另有一次锁臂 API-invalid | 未达到：有效锁臂为 PASS；不能与较旧 HDD cohort 合池 | codex/case4-hardening @ 3462672；infra/run_case4_lite_pair_pilot.py |
| 4 | F-01 Focus/Input Routing：A 对 Writer 的陈旧输入发生在 B 将焦点切至 Calc 后 | GPT-6-Sol Hybrid v2 最新三臂：PASS / PASS / FAIL；锁臂将 A 文本写进 B 的 Calc 目标，但普通 Shared 由 Agent 恢复并 PASS | 未达到：缺 Shared FAIL；历史 Qwen GUI-only 结果另列，不作当前架构证据 | codex/focus-clipboard-pilot-20261102 @ c866975；scripts/run_f01_hybrid_v2_retest.py |
| 5 | C-03 Clipboard：A 复制 Calc 区域，B 复制 Writer 文本，A 随后粘贴 | GPT-6-Sol Hybrid v2：PASS / FAIL / FAIL；两共享臂观察到 B 的剪贴板 payload 被粘进 A 的 Calc 目标 | **达到一次**：overwrite digest 与任务失败吻合 | 同上；scripts/run_c03_hybrid_v2_retest.py |
| 6 | A-01 Application Context：同一 Chromium 窗口内两个 Tab；陈旧 Enter 落在 B 的 Tab | GPT-6-Sol Hybrid v2：PASS / FAIL / FAIL；共享态产生 B Tab 的重复/非目标提交 | **达到一次** | 同上；scripts/run_a01_hybrid_v2_retest.py |
| 7 | S-01 Selection/Active Object：B 改变 Calc 活动单元格后 A 继续陈旧输入 | GPT-6-Sol Hybrid v2 v0.2.2：PASS / FAIL / FAIL；共享两臂 exposure=true | **达到一次** | 同上；scripts/run_calc_hybrid_v2_retest.py |
| 8 | U-01 Undo/Redo：A 的 Ctrl+Z 面对共享 Calc undo 栈顶的 B 操作 | GPT-6-Sol Hybrid v2 v0.2.2：PASS / FAIL / FAIL；共享两臂 exposure=true | **达到一次** | 同上；scripts/run_calc_hybrid_v2_retest.py |
| 9 | CWD-1：B 改变同一持久 shell 的 PWD 后，A 的相对路径交付写入 B worktree | GPT-6-Sol v0.2.4：精确 PASS / 精确 FAIL / 精确 FAIL；同 Guest/shell 与 wrong-worktree duplicate delivery 轨迹支持归因 | **达到一次**：目前新候选中唯一达标 | 同上；scripts/run_sol_cwd_bundle_v2.py |
| 10 | EDIT-1：Writer Insert/Overwrite 模式状态泄漏 | GPT-6-Sol v0.4.0：精确 PASS / Shared 归因不足的 FAIL / Shared+Lock PASS；早期瞬时 READY OR-REVIEW 后 Agent 恢复 | 未达到：不要把瞬时签名包装成锁臂最终 FAIL | 同上；scripts/run_edit_overwrite_hybrid_v2_retest.py |
| 11 | VIEW-1：滚动改变 viewport offset，旧屏幕坐标命中其他段落 | GPT-6-Sol v0.2.0：有效 Isolated PASS、Shared 归因较弱、Shared+Lock PASS；纯滚动几何暴露成立 | 未达到：锁臂 PASS，Shared 因果归因不足 | 同上；scripts/run_viewport_scroll_hybrid_v2.py |
| 12 | FIND-1：Find/Replace Match Case 选项持久化 | GPT-6-Sol v0.2.0：Isolated PASS；Shared 终态 FAIL 源于 A/B 指令目标冲突（A 把 B 的 REVIEW 改回 DRAFT），不是 Match Case；未跑锁臂 | 未达到：需要改提示并重新从 Isolated gate 开始；不接受当前 Shared 结果 | 同上；scripts/run_find_replace_hybrid_v2.py |
| 13 | AUTH-1：共享浏览器 principal/cookie/session 变化导致提交身份错 | 仅设计审查，尚无 scripted control 或 LLM run；与 A-01 Application Context 有潜在重叠 | 未达到：先做本地无外网 mock 控制并证明机制独立，否则 reclassify/停止 | 同上；目前没有获准的模型 runner |

## Case 2/3/4 详况

- Case 2 v1.2 保留了有效业务工作流，并强化 B 独立预核验和 Review ID 消息交接。正式三臂均完成且都 PASS，所以它对“简单业务可解”和严格协作时序有价值，但不是 shared-fail case。
- Case 3 v1.4.3 是 Case 2/3/4 中唯一满足目标者。共享两臂有效 FAIL；另有 setup-invalid 与 scorer-crash 历史尝试保留。v1.4.4 对一个历史 scorer-crash 做了后验评估修复，不计作新模型试验或重复。
- Case 4 SSD 对照支持普通共享时的窗口焦点干扰，但有效锁臂有一次 PASS；另外锁臂无效 API episode 不计为业务 FAIL。共享+锁目标仍待设计，不要把 HDD/SSD 条件合并为重复。

对应设计/结果全文已复制到本目录的 case234/case2、case3、case4 子目录。

## 五机制 Hybrid v2 证据

五机制的 GPT-6-Sol Hybrid v2 当前机器摘要见 evidence-manifests/F01-gpt6-sol-hybrid-triplet.json、C03-gpt6-sol-hybrid-triplet.json、A01-gpt6-sol-hybrid-triplet.json、S01-gpt6-sol-hybrid-triplet.json、U01-gpt6-sol-hybrid-triplet.json。对应完整原始 run IDs、轨迹、截图和协议门禁在 HealthCare 的 RAID1 路径中，见下文。

重点解释：
- F-01 的 MA-SD PASS 不能因 MA-SD+Lock 最终 FAIL 而改写；这一版确实没有满足三臂方向。
- C-03、A-01、S-01、U-01 是最新 Sol/Hybrid v2 下四个单次合格筛查。
- 每臂相同工具权限：GUI MCP、受限 Guest CLI MCP、Collaboration MCP；同一 case 内 task/prompt/fixture/oracle/model/budget 对齐，仅拓扑和 Shared+Lock 的 per-action lock 不同。此架构声明不外推到历史 Case 2/3/4。

## 怎么拉取与使用

本 handoff 分支包含 13 个 case 的导航、设计/结果文档副本以及小型 summary JSON；Case 2/3/4 和 Hybrid runner 的可执行源代码分别留在下列并行分支，避免把互相不兼容的实验 worktree 硬合并。

在新 clone 中先 fetch，再以独立 worktree 打开各源分支，保留自己的未提交修改：

    git fetch origin
    git worktree add ../CoDesk-case2 origin/codex/case2-v12
    git worktree add ../CoDesk-case3 origin/codex/case3-followup
    git worktree add ../CoDesk-case4 origin/codex/case4-hardening
    git worktree add ../CoDesk-mechanisms origin/codex/focus-clipboard-pilot-20261102

建议顺序：先读本文件，再读每个案例目录中的冻结 spec/report；在对应源 worktree 查看 git status、commit hash、runner --help 和聚焦测试。不要直接执行整个队列 runner。任何新三臂实验先做资源/ownership preflight，冻结预算与版本，顺序运行 Isolated → Shared → Shared+Lock；只有 Isolated valid exact PASS 才继续。保留全部无效和有效尝试；不允许针对共享臂加障碍、差异权限/提示/预算，或把 Guest/API/scorer/reset invalid 当作任务 FAIL。

Runner 入口：
- Case 2：运行 infra/run_ticket_to_resolution_lite_healthcare.py --help 后再决定控制/模型模式。
- Case 3：infra/run_case3_lite_pair_pilot.py 的 --help 和 case3 follow-up notes。
- Case 4：infra/run_case4_lite_pair_pilot.py 的 --help 和 hardening report。
- 五机制/新候选：上述脚本分别在 codex/focus-clipboard-pilot-20261102 分支；先 python scripts/<runner>.py --help，确认 endpoint、OSWorld 路径、guest image、artifact root 和预算。所有新增模型验证使用 GPT-6-Sol；不启动 Qwen worker。

## 文档与证据位置

本文件邻近目录：
- case234/case2：Case 2 v1.2 spec、handoff、实验计划和 v1.1.3 hardening report。
- case234/case3：Case 3 follow-up 报告。
- case234/case4：Case 4 SSD hardening report、实验计划及原 Lite 报告。
- mechanisms：Focus/Clipboard 早期协议、A-01 报告、机制 4/5 报告。
- next-five/design 与 next-five：候选审计/卡片、CWD v0.2.0–0.2.4、控制结果、v0.2.4 Sol 模型结果及 Hybrid v2 最新状态。
- evidence-manifests：五机制 Hybrid triplet 摘要和新候选可用的精选每臂 report.json。
- CASE_STATUS_MATRIX 已并入本 HANDOFF，以免产生两套计数；本表即汇总权威版本。

原始数据没有复制到 Git：
- Case 2：/home/mjh/Projects/CoDesk-case2-healthcare/runs/ticket_to_resolution/healthcare/
- Case 3：/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/<run-id>/
- Case 4：/home/mjh/Projects/CoDesk-case4-hardening/runs/<run-id>/
- 早期机制与 Hybrid v2：/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs/
- 新候选：/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/

以上绝对路径仅在 HealthCare 主机上存在，A800 或本地 pull 不会自动取得截图/轨迹。此分支不含私有 API key；不要将密钥复制进 Git。完成一个 case 不等于在相同旧 run-id 上重跑；一切重跑须生成新版本/新 run ID 并保留旧证据。
