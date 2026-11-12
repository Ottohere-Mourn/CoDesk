# CoDesk：3 个新双 Agent Case — 开发与实验交接

更新：2026-11-12

## 当前结论（以本文末实验补记为准）

已在 HealthCare 的独立 worktree 实现三个 paraGUI task pair、确定性 SQLite fixture、业务 Oracle、离线控制测试，以及用于 Shared+Lock 的 opt-in per-MCP-call lock。Guest setup smoke、离线 controls 与 9 个 GPT-6-Sol 真实模型臂均已完成。

初始评分表面上显示 S1、K2 两组符合三臂数值组合；但 2026-11-12 质量审计发现 S1 的两任务目标互斥（zero-sum），且实际运行导入了过期 Oracle。**严格计数只有 K2 一组暂时保留为候选（1/3）；S1、K1 均 no-go。** 原始 run/score 不删除；本文末的质量审计修正覆盖此前将 S1 算入达标的解释。

## 判定门槛和一致配置

每案使用同一 frozen task pair、prompt、fixture、Codex Harness、模型、工具权限和预算：

- MA-ID：OSCombo 的 isolated 模式；两位 Agent 在独立 Guest 并发执行，每个 Guest 从相同 pair seed DB 开始。
- Shared：parallel 模式；两位 Agent 共用一个 Guest、Chrome GUI 会话和本地 app database。
- Shared+Lock：同一 parallel 条件加 opt-in action lock。锁只包围一次会改变 GUI 的 MCP 调用及其返回截图，不保护 agent reasoning，也不提供跨多步操作的事务。
- 三臂统一 GPT-6-Sol、`https://api.haogpt.net/v1` endpoint、high reasoning、45 个 GUI MCP-call 上限、同一 Codex binary/version、相同环境 reset。
- 目标是 Oracle 判 MA-ID PASS / Shared FAIL / Shared+Lock FAIL。Guest/API/reset/evaluator 错误或无分数都标 invalid，不能算 Shared FAIL。
- 每案先一组 screening triplet；无效臂不并入判定。不删失败尝试、不以调度 barrier 刻意制造失败、不把能恢复的真实 PASS 改判 FAIL。
- 受测 Agent 权限是 GUI MCP only；无 Guest CLI、宿主机 Shell、Collaboration MCP。API key 在运行时从 stdin/env 注入，不写仓库或结果文件。

## 三个 Case

### S1 — SHELTER-INTAKE1：家庭床位分配与安全封房

- Agent A：读四个 household card、房间容量/无障碍/伴侣动物信息，完成 placement draft 并写简短备注。
- Agent B：按 SAFE-204 封闭 CR-201、容量归零并建立高优先级维修工单。
- H-103 是 4 人家庭，CR-201 是唯一容量至少为 4 的房间。Facilities 的安全封房会使当前家庭 placement 目标无可行房间；per-action lock 不能把两个业务流程变成一个事务。
- Oracle 分别检查家庭人数、房间可用状态/容量/无障碍/动物条件/备注，以及精确的 closure/work-order。
- 这是本地单工作站业务板上的共享状态测试，不代表真实远程 shelter SaaS 后端事务语义。共享冲突来自真实容量与安全约束，没有 arm-specific 障碍或强制 barrier。

### K1 — COURT-SERVICE1：小额法庭立案包与送达回证

- Agent A：给 SC-208 准备立案封面、当事方、金额、附件与 clerk-check 状态。
- Agent B：给 SC-193 记录服务日期、送达方法、process-server ID 与送达结果。
- 合成旧式单窗口 clerk desk 使用一个全局 active-docket selector；保存时写到提交时活动的 docket。它用来测试共享 GUI 中的活动记录上下文，不是现代浏览器多标签隔离或生产法院系统的外推。
- Oracle 按正确 docket ID 检查精确字段；错 docket 不算成功。
- 与 Case 3 / A-01 的窗口和记录上下文机制家族相近；新意在 filing + service 两角色日常业务工作流，不宣称新底层机制。是否能在真实模型三臂产生目标组合仍待验证。

### K2 — ROUTE-RECON1：早班派车路线与客户改期

- Agent A：基于 08:00 frozen manifest，为 RTE-17 设置四个工单的顺序、Van 4、08:00 发车、日期和 Draft 状态。
- Agent B：客户变更 WO-503（Riverside Hall）：改为 Deferred、移至 2026-11-14 并记录客户原话。
- 共享 dispatch board 同时保存已发布路线与工单当前状态。客户改期使仍包含 WO-503 的 Friday route draft 过期；逐次 GUI call lock 不提供跨 workflow 的版本协调或路线重发。
- Oracle 分别核对路线内容/顺序和 customer update；最终若路线仍纳入 Deferred stop，则 route task 不通过。
- 与 PAY-1 / DATA-REL1 同属 stale-artifact 近邻，但宏观流程为现场派车与客户改期。本地 fixture 不代表远程调度系统。

## 工程与环境

- 独立 worktree：/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
- 分支从 origin/yuke-osworld 的 976024720adba9a6087ec4c8526f26be0c8555db 开始；尚未 push，没有改动其他 CoDesk worktree。
- OSWorld checkout：/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1。保留其已有 dirty modification：desktop_env/providers/docker/provider.py。
- 本机已有 runtime：swcub/osworld-v2.1-qemu-runtime:local；Guest base 是 /mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2。
- Run output/cache 与 overlay archive 位于 RAID1 的 /mnt/raid1/mjh/Projects/codesk-next3-20261112；最新 runner 先把只读 Guest base 与活动 overlay 放在 /dev/shm，run 结束将 overlay 归档回 RAID1。当前 RAID1 约 1.1 TiB 可用，根盘约 26 GiB 可用/99%。runs 串行执行；不清理其他用户的 Docker image/container 或历史数据。
- Docker provider 使用本机 swcub package 和已有 runtime image，避免 Docker Hub 下载。早先 K1 setup smoke 使用 RAID overlay；最新 runner 将 SWCUB_OSWORLD_OVERLAY_HOST_DIR 指向每个 run 的 /dev/shm overlay，降低 NTFS/FUSE I/O stall，退出后归档到 RAID。
- smoke 的前两次尝试是 infra-invalid：第一次因 PYTHONPATH 缺少 swcub；第二次 provider 使用默认 Docker image 名称、尝试从 Hub 获取时遇网络超时，未实际拉到镜像。后续改用本地 runtime 与 RAID overlay 后，Guest GUI setup 正常；零动作脚本结果 score 0.0。
- 系统 PATH 中没有 codex；使用既有显式 binary /home/mjh/.local/share/codesk-case3-tools/codex，版本 codex-cli 0.165.0。所有 arms 将固定同一 binary/version；这与旧记录的 0.155.0 不同，不和旧 triplet 混合。

## 文件和验证

- 任务、应用、fixture builders、Oracle：tasks/paragui/task_pg*、app_*、build_*、pg_*。
- pair roster：lists/paragui_v1_combos.txt。
- 本地控制：tests/test_shelter1_reference_controls.py、tests/test_k1_reference_controls.py、tests/test_k2_reference_controls.py。
- Action lock：tests/test_action_lock.py；runner：scripts/run_new_case_arm.sh。
- 六个 task class 可通过 OSWorld task loader 导入；离线正/负 controls 和 lock test 共 10 passed；bash -n 与 git diff --check 通过。
- Assets：/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets/{s1,k1,k2}
- Run root：/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/
- Guest overlay：/mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays/

## 运行方式

runner 会从 stdin 读一行 API key；命令本身没有 key 字符串。PowerShell/SSH 调用时也不要把真实 key 打印到终端、放命令历史或贴回报告。

    printf '%s\n' "$DOCODE_KEY" | bash scripts/run_new_case_arm.sh s1 ma-id
    printf '%s\n' "$DOCODE_KEY" | bash scripts/run_new_case_arm.sh s1 shared
    printf '%s\n' "$DOCODE_KEY" | bash scripts/run_new_case_arm.sh s1 shared-lock

K1/K2 仅把第一个参数改为 k1 或 k2。运行前确认无活跃 Guest；每臂有唯一 run ID、resource ledger、独立 RAID output 和 cache。

## 日志与解释边界

- Action log/trace 保留工具名、参数、焦点窗口、GUI code、截图及 lock_enabled / lock_wait_s / lock_held_s。run-level 标记有 action-lock。
- Lock 的范围是一次 GUI MCP mutation call + 该 call 返回截图。它不会自动锁住多轮规划、标签选择、表单填充或数据库状态；这正是 Shared+Lock 臂的实际能力边界。
- 只有 API/Guest/reset/evaluator 有效、MA-ID oracle 全 PASS 且两 shared oracle 失败，才算符合目标。某个 task score partial 也算该业务 task 未 PASS，但 invalid 不得计为 FAIL。


## 2026-11-12 实验补记（不是有效 triplet）
- MA-ID 首试 `cdesk3-s1-ma-id-20261112T052333Z-837755`：两台 Guest 在 300 秒就绪期限内启动超时，infra-invalid；没有模型调用。
- `cdesk3-s1-ma-id-20261112T053449Z-842799`：使用 RAID/NTFS-FUSE 上的 Codex HOME 时 CLI 在首个动作前报 `Operation not permitted`；两 Guest/app 已启动，零步，invalid。
- `cdesk3-s1-ma-id-20261112T054319Z-847864`：改用 ext4 Codex runtime HOME/work 后，CLI 成功发出 Responses 请求；Docode 对两 Agent 返回 403 用户额度不足，Agent 0 步。运行分数不作任务成败证据。
- Haogpt GET /v1/models 返回 200 并列出 GPT-6-Sol；但 Haogpt 的 /v1/responses 最小调用与 Docode 同样返回 403 insufficient_user_quota，余额约为 -$0.072590。故目前是账户额度不足（非协议/key 错误），已停止所有模型 API 请求；需先恢复额度再继续。
- 0 步 evaluator 曾给 S1 intake 0.5（容量约束空集合真导致 vacuous partial）。已在 `a08cb9c` 改成无 assignment 为 0 分并加回归测试；上述旧 run 分数仍保留，不能追溯成模型 FAIL。


## 环境/验证补正（覆盖上文较早的资源描述）
- 最新 runner 使用 /dev/shm/codesk-next3/osworld-v2-ubuntu-x86.qcow2 作为只读 Guest base；每次运行的活动 overlay 写到 /dev/shm/codesk-next3/overlays/RUN_ID，结束后复制归档到 RAID 的 overlays/RUN_ID。因此，上文“Guest overlay 全程写在 RAID”的旧描述已过时；run output/cache 仍写 RAID。
- 新 runner 将 SWCUB_OSWORLD_VM_READY_TIMEOUT=600；这是为了容忍双 Guest 启动，不影响 Agent 任务时间/预算。
- Codex HOME/work 在本机 ext4 /home/mjh/.cache/codesk-next3-runtime/RUN_ID，解决 NTFS/FUSE 上创建 helper alias 的 EPERM；可审计的非 secret config 副本在每 Agent 的 run output。
- 2026-11-12 最新验证：离线 controls + action-lock 共 10 passed；OSWorld task loader 六项全部可导入；py_compile / bash -n / git diff --check 均通过。K1 real Guest setup smoke 已成功。模型三臂尚无有效结果。
- Host lock primitive 另在 RAID/FUSE 与 ext4 各做了 flock preflight，均成功；action-lock unit test 通过。

- OSWorld checkout 的 smoke loader 另外创建了 7 个未跟踪的 paraGUI loader/helper 文件，位于 evaluation_examples/task_class/pg_*.py；源文件真源仍是本分支的 tasks/paragui。该 checkout 还保留原有 dirty provider.py。不要把这些修改误提交到 OSWorld，也不要清理他人改动。


## 2026-11-12 实验结果更新：9 个有效 GPT-6-Sol arms

### 运行设置与严格判定

九个有效 arms 全部使用 GPT-6-Sol、Codex CLI 0.165.0、high effort、相同 Codex GUI-only MCP 工具、每 Agent 45 GUI MCP-call 上限及同一 frozen fixture/reset 协议。GPT provider endpoint 为 `https://api.haogpt.net/v1`。用户新 key 的 `/v1/models` 和最小 `/v1/responses` 预检均成功，九臂无 API 错误；key 从 stdin/env runtime 注入，**不得**复制到文档、仓库、shell history 或结果。无 Qwen。

只有两个 isolated task score 都是 1.0 才算 MA-ID PASS；任一共享臂任一 task <1.0 为 task/joint failure，但仍须确认其为有效业务结果。infra-invalid 单列，不得计入 FAIL。

| Case / arm | Run ID | Scores A/B | GUI calls A/B | input (cached) | output | elapsed s |
|---|---|---:|---:|---:|---:|---:|
| S1 MA-ID | `cdesk3-s1-ma-id-20261112T063914Z-866997` | 1.0 / 1.0 | 18 / 6 | 654,974 (553,333) | 2,542 | 486.7 |
| S1 Shared | `cdesk3-s1-shared-20261112T065201Z-873251` | 0.5 / 1.0 | 22 / 23 | 1,299,037 (1,118,630) | 5,888 | 581.4 |
| S1 Shared+Lock | `cdesk3-s1-shared-lock-20261112T071251Z-882842` | 0.5 / 1.0 | 11 / 10 | 524,783 (432,806) | 3,462 | 319.6 |
| K1 MA-ID | `cdesk3-k1-ma-id-20261112T072115Z-887645` | 1.0 / 1.0 | 14 / 12 | 689,115 (570,683) | 2,178 | 406.3 |
| K1 Shared | `cdesk3-k1-shared-20261112T073152Z-893194` | 1.0 / 1.0 | 40 / 31 | 2,835,504 (2,542,614) | 8,451 | 967.2 |
| K1 Shared+Lock | `cdesk3-k1-shared-lock-20261112T075008Z-900779` | 1.0 / 1.0 | 23 / 29 | 1,770,415 (1,550,061) | 4,838 | 787.4 |
| K2 MA-ID | `cdesk3-k2-ma-id-20261112T080745Z-908714` | 1.0 / 1.0 | 19 / 12 | 865,015 (746,972) | 2,639 | 455.7 |
| K2 Shared | `cdesk3-k2-shared-20261112T081915Z-914157` | 0.1429 / 0.25 | 42 / 45 | 2,617,483 (2,328,166) | 9,729 | 749.7 |
| K2 Shared+Lock | `cdesk3-k2-shared-lock-20261112T084500Z-922685` | 0.8571 / 1.0 | 23 / 29 | 1,699,210 (1,513,460) | 4,768 | 738.0 |

Totals: 12,955,536 input tokens (11,356,725 cached), 44,495 output tokens, and 5,492 seconds summed run elapsed (~91.5 minutes). These are model usage totals, not a provider bill.

### Case interpretations

- **S1 is no-go after audit.** Raw runs remain intact, but the shared failure is not a valid inter-agent interference case: closing the only four-person room makes Intake's required assignment impossible, and the Intake Agent correctly reports infeasibility. The expected 0.5 also came from a stale installed evaluator. See the correction appendix at the end.
- **K1 does not meet target.** All six agent-arm results are full pass. It had elevated shared GUI calls/time (71 calls combined, 967s) but performance cost is not failure. Do not claim pass. Active docket context also repeats Case 3/A-01 vicinity; recommend no-go rather than arm-specific tuning.
- **K2 meets target once.** Independent full pass. Shared route and WO-503 task scores are 0.1429/0.25 with repeated focus/page switching between route draft and service form. With lock, Agent B updates WO-503 successfully (1.0), while Agent A route still includes the now-Deferred stop (`every_stop_still_scheduled=false`; route 0.8571). This is valid stale shared-state failure, not an invalid Guest/API result.

### Infra-invalid history (preserved, excluded)

- `cdesk3-s1-ma-id-20261112T052333Z-837755`: Guest readiness timed out at prior 300s limit; no model call.
- `cdesk3-s1-ma-id-20261112T053449Z-842799`: old Codex HOME on RAID/NTFS-FUSE failed with `Operation not permitted` before first action.
- `cdesk3-s1-ma-id-20261112T054319Z-847864`: old API key returned quota 403; zero agent steps. This was resolved by the newly provided key / Haogpt endpoint; it does not characterize current API availability.
- Historical directory may also include earlier protocol/setup attempts; retain and label, do not pool with nine valid arms.

### Current decision / next work

- Batch result after quality audit: **1/3 candidate triplets retained (K2 only); 0 repeated triplets; S1 and K1 are no-go.**
- Do not push without a request. Current task branch remains separate from `yuke-osworld`.
- Next: audit K1 against the existing suite and replace it with a less overlapping workflow. Screen fixture/oracle and scripted positive/negative controls first. A bounded GPT-6-Sol pilot should be run only after those pass; do not change the arm-specific schedule, insert race barriers, or treat high cost as failure.
- Latest runner's Guest base/active overlay are staged on `/dev/shm/codesk-next3`; result/cache and archived overlays go to RAID1. Root remains critically full (~99%); never delete other projects, runs, or source overlays as a cleanup shortcut. Recheck active containers and free memory/disk before any new triplet.


## 19-case portfolio 去重审计（2026-11-12）

对照 `CoDesk-13case-publish-20261105/docs/handoff/13-case-handoff/QUALIFIED_CASE_AUDIT_20261108.md` 中的 19-case roster（当时 14 个一次筛查达标），新三案的“工作流新颖性”和“机制新颖性”分开表述：

| 新案 | 与旧 roster 的最近邻 | 审计结论 |
|---|---|---|
| S1 SHELTER-INTAKE1 | capacity/resource feasibility；旧 roster 有 VIEW/Selection 和 stale-state 家族，但未见同型收容所安置 + 安全封房业务 | 工作流差异最清楚，但由于两任务目标无法共同达成而明确 no-go；仍是合成应用，不把“共享可用容量”称为全新机制。 |
| K1 COURT-SERVICE1 | Case 3 / A-01 的活动记录/窗口上下文；并近邻已通过 CRM-LU1 的陈旧表单更新流程 | 9 个有效模型结果全 PASS，且机制/工作流接近旧上下文场景；明确 no-go，不为达 tuple 针对 Shared 加障碍。 |
| K2 ROUTE-RECON1 | PAY-1、DATA-REL1、AP-1、SITEACT-STATE1、CRM-LU1 等 stale-state / artifact freshness 家族 | 现场派车 + 客户改期是不同日常流程；但机制增量有限，应标注为 workflow-level variant，不能声称新增 stale-artifact 机制。 |

已审阅的既有未成熟候选也不能直接补位：CRM-LU1 已是 roster 第 19 项；PRINT-ROUTE1 在 pinned Guest 没有目的队列/默认打印机而 no-go；ATTACH-EVIDENCE1 与 S-01/A-01 的选中文件/上下文邻近；SUPPORT-ONCE1 与 Case 2/W4 的客服流程有邻近；ENG-TRANS1、ASSET-HOLD1 与 PAY-1/DATA-REL1/SITEACT-STATE1 同属状态变更使既有工件陈旧。它们需重新审计，不能仅换业务名称就加入。

### 当前推进决策

- 这批卡片保留 3 项；质量审计后 **只有 K2 一次符合目标（1/3），S1 与 K1 均 no-go**。
- 不追加无候选语义门的 GPT-6-Sol 调用：已跑完 9 个有效 arms，总输入约 13.0M tokens。模型新 key 与 Haogpt `/v1` endpoint 已工作，但没有重复验证要求。
- 下一轮新增工作流优先从新的日常业务域/共享状态来源开始；先做与 19-case roster 的重叠审计和低成本 Guest/Oracle 语义门，再决定是否启动真实 triplet。要是没有同时通过实用性、差异度和 fixture 因果门的候选，应保留当前审计后 1/3 结果并暂停扩样，而不是为数字凑第三个。


## API 凭证更新预检（2026-11-12，本次恢复）

本次用户更新凭证后，使用隐藏 TTY 输入并仅保存在运行时内存，重新预检同一 `https://api.haogpt.net/v1` endpoint：`GET /models` 返回 HTTP 200 且列出 GPT-6-Sol；GPT-6-Sol 最小 `POST /responses` 返回 HTTP 200、`status=completed`。这只是新凭证/协议 smoke，不是新的 case arm，不计入上面的 9 个 model runs；key 没有写入仓库、环境配置或 run artifact。没有再发起正式任务调用。

## 2026-11-12 continuation update: replacement-candidate gate

K2 remains one retained target tuple. S1 is reclassified as a zero-sum design with evaluator drift, so the batch is 1/3, with no repeats.
- The prior design-pool W3 label refers only to a laboratory-QC concept in the 2026-11-05 composite-workflow audit. In this active branch, `app_w3.py`/`pg_w3.py`/`build_w3.py` are unrelated Bluepeak CRM tasks; no Lab-QC fixture or pair is implemented.
- Lab-QC remains an unimplemented U-01 Undo-mechanism workflow variant, not a new mechanism and not a fourth tested case. Its candidate needs its own builder/pair/oracle/tasks and natural-use gate. No Guest or GPT run has started for it.
- Resource recheck found root with ~24 GiB free, `/data` ~93 GiB free, and swap 2/2 GiB used; no active OSWorld/QEMU Guest was observed. Do not start a Guest until the exact overlay/output paths and running process ownership are rechecked. Nothing was deleted or moved.
- Next gate if continuing: finalize exact QC/calibration workbook outputs + independent Oracle, add offline positive/negative tests, then revisit Guest only after resource preflight. Do not mandate Ctrl+Z in the Agent prompt or insert an arm-specific interleaving to obtain FAIL.


## 2026-11-12 S1 质量审计修正（覆盖以上较早判定）

S1 三臂原始运行仍是完成的 GPT-6-Sol run，不删除、不伪装成 infra-invalid；但从合格案例统计中排除：

- **设计门失败：共享时双方不可能同时 PASS。** Fixture 中 CR-201 容量 4，是唯一可安置四人 H-103 的房间；Intake Oracle 要求房间最终 Open 且容量足够，Facilities 任务强制关闭 CR-201、容量置零。其它房间最多 3 人。两个 actor 的指令又分别禁止对方负责的操作，因此没有协调顺序或 per-action lock 能产生共同可行终态。
- **证据：** Shared agentA/INFEASIBLE 写明唯一四人房已关闭且其它房间最多三人；Shared+Lock 的 INFEASIBLE 同样说明这一点。Agent A 是如实报告不可能，不是错误输入或遗漏可恢复步骤。Agent B 完成了其安全封房任务。
- **评分器漂移：** 实际导入的模块是 OSWorld checkout 下的 evaluation_examples/task_class/pg_shelter1_oracle.py（用 runner 的 PYTHONPATH 解析确认）。安装副本 SHA-256 82dc5de1de8cb1c788aa45846b83b4177182bfaaf25ce289670116af95dd51b3；分支真源 SHA-256 fc7ee04e230aa8ec3fec54019b9aa253f172462a6c6550105ac5db632eee552a。共享结果没有任何 assignments，旧副本仍将空集合容量检查评为 true，故 intake score=0.5；分支修复版对无 assignment 返回 0.0。方向仍是 FAIL，但该 run 没有使用冻结的 canonical evaluator。
- **统计结论：** 本批最多 1/3 暂时保留（K2）；S1 和 K1 都不计达标。raw score table 不变，仅作为旧版本 result.json 记录。S1 若重做，必须改 fixture 以确保两个目标能共同达成，固定实际加载的 evaluator 并增加启动时版本一致性检查，然后重做完整 MA-ID/Shared/Shared+Lock。
- 历史 run IDs：cdesk3-s1-ma-id-20261112T063914Z-866997、cdesk3-s1-shared-20261112T065201Z-873251、cdesk3-s1-shared-lock-20261112T071251Z-882842。日志在 /mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/。

## Runner safety fix

run_new_case_arm.sh now compares each case's required task/evaluator source files against the files present in the OSWorld runtime before it starts a run. A missing or different file stops before Guest/model allocation. In particular, the known stale S1 oracle mismatch blocks a future S1 rerun instead of silently producing another mislabeled score. This guard checks version identity; it does not retrofit any historical result.
