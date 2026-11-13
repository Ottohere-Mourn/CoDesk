# CoDesk：3 个新双 Agent Case — 开发与实验交接

更新：2026-11-12

## 当前结论（以本文末实验补记为准）

已在 HealthCare 的独立 worktree 实现三个 paraGUI task pair、确定性 SQLite fixture、业务 Oracle、离线控制测试，以及用于 Shared+Lock 的 opt-in per-MCP-call lock。Guest setup smoke、离线 controls 与 9 个 GPT-6-Sol 真实模型臂均已完成。

初始评分表面上显示 S1、K2 两组符合三臂数值组合；但质量审计确认两组任务目标均互斥（zero-sum），S1 还实际导入了过期 Oracle。**严格计数为 0/3；S1、K2、K1 均 no-go（K1 是全臂 PASS）。** 原始 run/score 不删除；本文末的质量审计修正覆盖此前的数值解释。

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
- **K2 is no-go after design audit.** Its exact manifest-order oracle requires WO-503 to remain Scheduled, while the other task requires WO-503 Deferred; neither prompt allows the other task's corrective action. These are mutually incompatible terminal goals, so its shared failures cannot qualify.

### Infra-invalid history (preserved, excluded)

- `cdesk3-s1-ma-id-20261112T052333Z-837755`: Guest readiness timed out at prior 300s limit; no model call.
- `cdesk3-s1-ma-id-20261112T053449Z-842799`: old Codex HOME on RAID/NTFS-FUSE failed with `Operation not permitted` before first action.
- `cdesk3-s1-ma-id-20261112T054319Z-847864`: old API key returned quota 403; zero agent steps. This was resolved by the newly provided key / Haogpt endpoint; it does not characterize current API availability.
- Historical directory may also include earlier protocol/setup attempts; retain and label, do not pool with nine valid arms.

### Current decision / next work

- Batch result after quality audit: **0/3 cases qualify; 0 repeated triplets. S1/K2 have mutually incompatible goals; K1 is all-PASS and no-go.**
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

质量审计后 **0/3 合格；S1、K2 目标互斥，K1 全臂 PASS**。
- 不追加无候选语义门的 GPT-6-Sol 调用：已跑完 9 个有效 arms，总输入约 13.0M tokens。模型新 key 与 Haogpt `/v1` endpoint 已工作，但没有重复验证要求。
应如实保留当前 0/3 结果并暂停扩样


## API 凭证更新预检（2026-11-12，本次恢复）

本次用户更新凭证后，使用隐藏 TTY 输入并仅保存在运行时内存，重新预检同一 `https://api.haogpt.net/v1` endpoint：`GET /models` 返回 HTTP 200 且列出 GPT-6-Sol；GPT-6-Sol 最小 `POST /responses` 返回 HTTP 200、`status=completed`。这只是新凭证/协议 smoke，不是新的 case arm，不计入上面的 9 个 model runs；key 没有写入仓库、环境配置或 run artifact。没有再发起正式任务调用。

## 2026-11-12 continuation update: replacement-candidate gate

S1 and K2 are both reclassified as zero-sum designs; the batch is 0/3, with no repeats.
- The prior design-pool W3 label refers only to a laboratory-QC concept in the 2026-11-05 composite-workflow audit. In this active branch, `app_w3.py`/`pg_w3.py`/`build_w3.py` are unrelated Bluepeak CRM tasks; no Lab-QC fixture or pair is implemented.
- Lab-QC remains an unimplemented U-01 Undo-mechanism workflow variant, not a new mechanism and not a fourth tested case. Its candidate needs its own builder/pair/oracle/tasks and natural-use gate. No Guest or GPT run has started for it.
- Resource recheck found root with ~24 GiB free, `/data` ~93 GiB free, and swap 2/2 GiB used; no active OSWorld/QEMU Guest was observed. Do not start a Guest until the exact overlay/output paths and running process ownership are rechecked. Nothing was deleted or moved.
- Next gate if continuing: finalize exact QC/calibration workbook outputs + independent Oracle, add offline positive/negative tests, then revisit Guest only after resource preflight. Do not mandate Ctrl+Z in the Agent prompt or insert an arm-specific interleaving to obtain FAIL.


## 2026-11-12 S1 质量审计修正（覆盖以上较早判定）

S1 三臂原始运行仍是完成的 GPT-6-Sol run，不删除、不伪装成 infra-invalid；但从合格案例统计中排除：

- **设计门失败：共享时双方不可能同时 PASS。** Fixture 中 CR-201 容量 4，是唯一可安置四人 H-103 的房间；Intake Oracle 要求房间最终 Open 且容量足够，Facilities 任务强制关闭 CR-201、容量置零。其它房间最多 3 人。两个 actor 的指令又分别禁止对方负责的操作，因此没有协调顺序或 per-action lock 能产生共同可行终态。
- **证据：** Shared agentA/INFEASIBLE 写明唯一四人房已关闭且其它房间最多三人；Shared+Lock 的 INFEASIBLE 同样说明这一点。Agent A 是如实报告不可能，不是错误输入或遗漏可恢复步骤。Agent B 完成了其安全封房任务。
- **评分器漂移：** 实际导入的模块是 OSWorld checkout 下的 evaluation_examples/task_class/pg_shelter1_oracle.py（用 runner 的 PYTHONPATH 解析确认）。安装副本 SHA-256 82dc5de1de8cb1c788aa45846b83b4177182bfaaf25ce289670116af95dd51b3；分支真源 SHA-256 fc7ee04e230aa8ec3fec54019b9aa253f172462a6c6550105ac5db632eee552a。共享结果没有任何 assignments，旧副本仍将空集合容量检查评为 true，故 intake score=0.5；分支修复版对无 assignment 返回 0.0。方向仍是 FAIL，但该 run 没有使用冻结的 canonical evaluator。
本批 0/3 合格：S1/K2 是 zero-sum，K1 全臂 PASS。
- 历史 run IDs：cdesk3-s1-ma-id-20261112T063914Z-866997、cdesk3-s1-shared-20261112T065201Z-873251、cdesk3-s1-shared-lock-20261112T071251Z-882842。日志在 /mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/。

## Runner safety fix

run_new_case_arm.sh now compares each case's required task/evaluator source files against the files present in the OSWorld runtime before it starts a run. A missing or different file stops before Guest/model allocation. In particular, the known stale S1 oracle mismatch blocks a future S1 rerun instead of silently producing another mislabeled score. This guard checks version identity; it does not retrofit any historical result.


## 2026-11-12 K2 共同可行性审计修正

K2 保留 raw GPT-6-Sol triplet，不计入合格案例。Design flaw 与 S1 不同：S1 是床位资源不足，K2 是 Oracle/prompt 的逻辑矛盾：

- Route task 的提示要求 exact stop order WO-501/502/503/504，且不得改工单；
- Service task 要求 WO-503 Deferred，且不得改 route；
- Route oracle 同时检查 stops 等于全部四个已发布工单，并检查所有 stop 的状态仍为 Scheduled；
- B 任务成功后 WO-503 状态必为 Deferred，Route 的状态检查必失败。因此共享桌面下双方没有共同 PASS 解。MA-ID 通过仅因为独立数据库允许 WO-503 在 A 的副本中保持 Scheduled。
- 当前 K2 Shared/Shared+Lock 的失败不能算合格的 shared-only failure；Shared+Lock route 0.8571 是不可满足 oracle 中一项的必然后果，不是 per-action lock 的不足。
- 如保留派车工作流，应把 Route 任务改成根据最终工单状态生成一致草稿（可以排除 Deferred WO-503），并以状态一致性替代 frozen manifest exact-order；先证明双方共享终态可同时 PASS，再做新版本三臂。不得回填修正旧 runs。

run IDs：cdesk3-k2-ma-id-20261112T080745Z-908714、cdesk3-k2-shared-20261112T081915Z-914157、cdesk3-k2-shared-lock-20261112T084500Z-922685。


## 最新持续进展：ROUTE-LIVE1 replacement candidate (q1)

- 原 K2 确认 zero-sum 后，新建 q1 版本：路由 Agent 需基于“保存时仍 Scheduled 的清单项”建路线；客服 Agent 延期 WO-503。Oracle 动态按最终工单状态计算路线，存在共同 PASS 的终态。三条静态 Oracle controls passed。
- GPT-6-Sol/Codex 真实 triplet 的数值结果达到一次 MA-ID 1.0/1.0, Shared 1.0/0.25, Shared+Lock 0.1429/0.25。详情、run ID、成本、检查项和锁遥测：tasks/paragui/ROUTE_LIVE1_MODEL_RESULTS_20261112.md。
- 重要限定：Shared 中 B 没有保存延期；Shared+Lock 双方均未完成。日志显示实质失败是 Chrome 当前页面/表单在两个 Actor 间切换，而非“延期工单使已保存路线陈旧”。因此不把它作为 route-state 机制证据，也不计入已质量合格的三新 case；可以暂记为一个 workflow-level shared-browser outcome。它在机制上靠近现有 application-context family。
- Shared+Lock 共 55 个有锁变更调用；lock_wait_s 总和 6.509、lock_held_s 总和 126.674、最大单次等待 2.153 秒；每个调用串行，但锁不覆盖模型思考时间。
- 后续门槛：先做不改冻结 prompt/fixture/oracle 的 Guest joint positive control（共享状态下确实完成 WO-503 update，A 随后刷新并保存三站路线），再决定是否重跑。未通过控制前不要扩增模型臂或声称目标因果。
- 本批 S1/K1/K2 仍为 0/3 qualified；q1 是修订候选，不改变此前计数。


## 最新更新：EDIT-MODE1 三臂筛查（2026-11-12）

首个替代候选 E1 已完成固定 Guest 控制和一次 GPT-6-Sol 三臂筛查。严格不计入达标数：MA-ID A/B=1.0/1.0，Shared=0.5/0.5，但 Shared+Lock=1.0/1.0。Shared 真实轨迹的输出是并发文本输入冲突，不是 scripted 控制中的特定 OVR 签名；锁臂的模型恢复成功。E1 因未满足 Shared+Lock FAIL 判定为 no-go，保留为机制/锁恢复对照。详细 Task、fixture、oracle、控件结果、run IDs、token/耗时及 overlay 归档限制见 tasks/paragui/EDIT_MODE1_MODEL_RESULTS_20261112.md。本批严格合格仍为 0/3；下一个替代候选需要不同任务设计，不能仅调参续跑 E1。

## 2026-11-12 VIDEO-REVIEW1 GPT-6-Sol triplet（新增替代案例）

VIDEO-REVIEW1 是 13 帧、时间码的 Northline Loading Bay 4 clip-review storyboard：Safety reviewer 记录 frame 2/4/6/8 四项危险，Maintenance coordinator 记录 frame 3/5/7/9/11 五项设备缺陷。两者共享一个媒体帧游标及当前 worklist/表单，保存时应用读取当时可见的帧作为 timestamp；任务目标本身互不排斥，离线共同正控、reset 与真实 Guest scripted joint positive 均通过。

首轮 GPT-6-Sol triplet 一次达到目标组合（未经重复）：MA-ID 1.00/1.00，Shared 0.25/0.40，Shared+Lock 0.00/0.60。有效模型/API/Guest/evaluator；三臂的 task、fixture hash、source hash、Codex 0.165.0、GUI-only 与每 Agent 45-call budget 一致。Shared+Lock Safety Actor 明确报告共享页面在其多步任务中多次被另一 Actor 改帧、改 worklist、清空笔记；锁臂 60 个受锁动作逐个串行，lock wait 合计 9.068s、held 145.934s，但 PerActionLock 不覆盖跨工具调用的完整审核事务。Maintenance 受同一 45 次预算限制，仅完成 3/5。

- MA-ID: `cdesk3-v1-ma-id-20261112T145415Z-1062817`
- Shared: `cdesk3-v1-shared-20261112T150911Z-1070500`
- Shared+Lock: `cdesk3-v1-shared-lock-20261112T152938Z-1078225`
- 详情：`tasks/paragui/VIDEO_REVIEW1_MODEL_RESULTS_20261112.md`

判定：**一次 triplet 满足三个臂的目标组合，列作这批新案的 1 个初筛达标候选；不声称稳定重复。** 设计边界为 storyboard，而非真实 MP4/商业审片软件；只能支持共享帧游标/表单状态的具体场景。暂不 push。\n\n## 2026-11-13 WAREHOUSE-LABEL1 model screen — no-go

新候选 WAREHOUSE-LABEL1（共享热敏标签台：仓库 Bin 2x1 标签 + 发运 Parcel 4x6 标签）已完成真实 Guest 正控/固定机制对照和 GPT-6-Sol 三臂；Shared state 在提交时采样，固定 GUI 交错能复现错误标签尺寸，但真实模型三臂任务均完成：MA-ID 1.0/1.0、Shared 1.0/1.0、Shared+Lock 1.0/1.0。因此**不满足目标 tuple，明确 no-go，不计达标**；Shared/lock 的 GUI 调用和耗时明显增加只能当成本观察，不能改称 FAIL。任务提示要求每次打印前检查 profile，给了强恢复线索；不移除该线索或加 race 来制造失败。

真实 Guest 控件：joint scripted GUI 正控双方 1.0；清楚标注的 fixed-interleaving mechanism control 使 bins 中 B-104 在切换 stock 后保存错 profile（bins 0.8, parcels 1.0），这是人为调度的机制验证，不是模型并发证据。另有一次 scripted authoring 错误（B 误点 bin 行）保留并排除于结论。完整结果、token、动作预算、fixture/source hash 一致性、lock wait/held、控制 run ids：`tasks/paragui/WAREHOUSE_LABEL1_MODEL_RESULTS_20261113.md`。

模型 run IDs：
- MA-ID `cdesk3-v2-ma-id-20261112T161600Z-1099988`
- Shared `cdesk3-v2-shared-20261112T162411Z-1104670`
- Shared+Lock `cdesk3-v2-shared-lock-20261112T164011Z-1111210`

截至现在，三个新案替代筛查中 V1 VIDEO-REVIEW1 是 1 个一次性目标 tuple（无重复），V2 WAREHOUSE-LABEL1 no-go；故本批 3-case 目标仍只有 1/3 达到一次性目标组合。V1 storyboard 边界、V2 本地模拟打印台边界均见各自 spec/report。暂未 push。

## 2026-11-13 COMMUNITY-PANTRY1 初筛：替代候选 V3（更新）

COMMUNITY-PANTRY1 是社区食品储藏室周末服务台工作流：Agent A 为 6 名志愿者排班并确认，Agent B 同步处理 6 笔里程报销。两者操作单窗口 kiosk 的共享 active-volunteer/work-area 上下文；任务域不同且有明确联合 PASS 终态。业务是日常流程，但底层仍是 application-context/shared-active-record 变体，不宣称新增机制。

**一次真实 GPT-6-Sol triplet 达到目标组合（无重复）：MA-ID A/B=1.0/1.0；Shared=0.0/0.8333；Shared+Lock=0.0/0.6667。**
- MA-ID 两任务分别写入 6/6，48/49 GUI calls，60-call budget。
- Shared 里 Mileage Actor 正常工作后，共享 desk 变成 1/6 processed；Shift Actor 将“不要处理 mileage”误读为共享状态必须保持 0/6，9 次工具调用后 declare_infeasible，班次 0/6。Mileage 5/6。
- Shared+Lock Shift Actor 在多步排班过程中看到全局 work-area 被另一个合法 Actor 切成 Mileage，认为 UI 无法保持上下文并 declare_infeasible，24 次调用后班次 0/6。PerActionLock 串行了单个 GUI 工具调用，但没有锁住完整的志愿者/工作区/表单事务；Mileage 4/6。
- 两个共享臂均 state_readable=true、run error=null；失败不是 Guest/API/evaluator 错误。共同正终态已由六条 Oracle 和同屏 scripted GUI 正控验证。没有注入人为障碍或固定强制交错。

离线 6 个 V3 tests passed；真实 Guest scripted joint GUI positive run 两任务都 1.0：cdesk3-v3-scripted-joint-20261113T032751Z-1433698。有效模型 run IDs、逐条 exact Oracle、token、时长、lock telemetry、fixture/source manifest SHA、资源/overlay 归档校验见 tasks/paragui/COMMUNITY_PANTRY1_MODEL_RESULTS_20261113.md。

- MA-ID：cdesk3-v3-ma-id-20261113T033134Z-1435452
- Shared：cdesk3-v3-shared-20261113T034951Z-1443495
- Shared+Lock：cdesk3-v3-shared-lock-20261113T040006Z-1448452

保留的校准尝试 cdesk3-v3-ma-id-20261113T030907Z-1425007 用旧的 45-call budget，且 expected note 漏了任务提示末尾句点；不得与修正后的 triplet 混算。修正后统一三臂 60-call budget，expected note 与 prompt 完全一致。校准原始 run 不删除。

**三新候选计数现为 2/3 一次性初筛达标：VIDEO-REVIEW1、COMMUNITY-PANTRY1；WAREHOUSE-LABEL1 是全臂 PASS no-go。** 均不声称有效重复；本分支仍未 push。


## 2026-11-13 V4-V6 pilot continuation (new compact candidate revisions)

The V4/V5/V6 case designs are LIBRARY-ROOM1 (programme booking + safety closure), AP-CLIPBOARD1 (invoice + reimbursement references), and EXAM-ACCESS1 (approved accommodations + seating). These are workflow/domain variants; do not call them three new mechanism families. Their task cards/specs, builders, assets and controls are under tasks/paragui/spec_v4.md, spec_v5.md, spec_v6.md and scripts/run_v456_guest_control.py.

### Preserved V4 calibration (pre-revision; do not count as pass)
- Run: cdesk3-v4-ma-id-20261113T052039Z-1485864.
- Pre-revision fixture was 5 bookings + 3 closures. Result: A 2/5 (0.4), B 2/3 (0.6667), both status timeout, agent_s=2400.3, exit_code=-9; Oracle readable, Guest boot/reset succeeded. This is not infra-invalid, but an incomplete MA-ID, so no Shared/Shared+Lock from this fixture and no qualified triplet.
- Per-Actor GUI call budget was 60; wall timeout 2400s. Agents used 38 and 19 GUI steps before timeout. Preserve output and overlays; do not fold the partial scores into any later revision.
- The current revision reduces workloads to V4 2+2, V5 2+2, V6 3+3 records. Fixture/source hashes therefore differ. Repeat controls and start any new triplet at MA-ID.

### Current resource placement / do not clean
- Code worktree: /home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112.
- Runs/assets/archived overlays: /mnt/raid1/mjh/Projects/codesk-next3-20261112/{runs/triplets,assets,overlays}.
- Active Guest overlays and base: /dev/shm/codesk-next3/overlays, /dev/shm/codesk-next3/osworld-v2-ubuntu-x86.qcow2.
- Last pre-run check: root had about 21 GiB free at 99%; RAID1 about 1 TiB free; /dev/shm about 80 GiB free. Root is still critically full. Do not write large files to root, pull Docker images, remove other people's resources, or clear earlier evidence. Recheck active containers and disk before each new arm. GPT was called through API from the Codex GUI-only harness; no Guest CLI permissions were added.
- The user-supplied GPT-6-Sol key was consumed through a hidden TTY wrapper (/tmp/run_authenticated_case.sh) and is not stored in repository files. Reuse secure TTY injection only; do not print/log the key.

### Run order status
The prior prospective run list is complete. Current compact-fixture scripted controls, the V4-V6 MA-ID/Shared/Shared+Lock triplets, source/fixture parity checks and RAID overlay hash checks are all recorded in the later section titled V4-V6 compact model triplets complete. Do not restart from the prospective checklist or mix the pre-revision V4 timeout into the current triplet.


### V4 LIBRARY-ROOM1 compact triplet (one-time target hit; caveat retained)
- Result report: tasks/paragui/LIBRARY_ROOM1_MODEL_RESULTS_20261113.md.
- Current compact-fixture triplet: MA-ID A/B 1.0/1.0; Shared A/B 1.0/0.0; Shared+Lock A/B 1.0/0.0. This screens as one Independent PASS / Shared FAIL / Shared+Lock FAIL case, no repeats.
- The Shared and lock Facilities agent explicitly reported that the common UI repeatedly switched between panels between actions; lock telemetry confirms per-action serialization but no transaction-level lock.
- Content-validity caveat: R-202 safety notice remains visible as an auxiliary worklist item although the task requests only R-101/R-201. It was not filtered post hoc; resolve before publication/repeat. Do not claim generality from one run.
- Preserve the larger-fixture timeout calibration cdesk3-v4-ma-id-20261113T052039Z-1485864 separately; it is not part of this triplet.


## 2026-11-13 V4-V6 compact model triplets complete

This supersedes the earlier note that V5/V6 model runs were pending. Joint PASS means both task oracles score exactly 1.0; one failed actor makes the workflow joint outcome FAIL. Each case has one triplet and no repeat is claimed.

| Case | Workflow | MA-ID (A/B) | Shared (A/B) | Shared+Lock (A/B) | Joint tuple |
|---|---|---:|---:|---:|---|
| V4 LIBRARY-ROOM1 | two programme bookings + two safety closures | 1.0 / 1.0 | 1.0 / 0.0 | 1.0 / 0.0 | PASS / FAIL / FAIL |
| V5 AP-CLIPBOARD1 | two invoices + two staff claims | 1.0 / 1.0 | 0.0 / 0.0 | 1.0 / 0.0 | PASS / FAIL / FAIL |
| V6 EXAM-ACCESS1 | three accommodations + three seating rows | 1.0 / 1.0 | 1.0 / 0.0 | 0.0 / 0.0 | PASS / FAIL / FAIL |

**Batch: 3/3 meet the joint task-level tuple once. This is not repeatability evidence.** Shared and Shared+Lock results are valid model task failures with error=null, not API/Guest-invalid runs. All three have direct failed-actor reports of panel/work-area/window switching. No force-fail obstacle or arm-specific schedule was added.

Reports:
- V4: tasks/paragui/LIBRARY_ROOM1_MODEL_RESULTS_20261113.md
- V5: tasks/paragui/AP_CLIPBOARD1_MODEL_RESULTS_20261113.md
- V6: tasks/paragui/EXAM_ACCESS1_MODEL_RESULTS_20261113.md

IDs:
- V4: cdesk3-v4-ma-id-20261113T061735Z-1511887; cdesk3-v4-shared-20261113T063225Z-1518582; cdesk3-v4-shared-lock-20261113T065713Z-1527746.
- V5: cdesk3-v5-ma-id-20261113T072336Z-1538703; cdesk3-v5-shared-20261113T073931Z-1545618; cdesk3-v5-shared-lock-20261113T074956Z-1550241.
- V6: cdesk3-v6-ma-id-20261113T080324Z-1558552; cdesk3-v6-shared-20261113T081855Z-1565394; cdesk3-v6-shared-lock-20261113T084133Z-1574032.

Qualification limits: V4 still has the out-of-scope R-202 notice caveat. V5 meets the broad shared finance workflow criterion, but the failure demonstrates shared panel/focus routing rather than clipboard overwrite; no clipboard-value telemetry was captured. V6 seating directly reports shared work-area switching. Its accommodations actor's Shared+Lock failure is weaker because the instruction says authorization notices while the app shows inline source summaries. Do not overclaim V5 as a clipboard mechanism or V6's A-side failure as causal evidence; align these items before publication/repeat.

Controls/protocol: scripted current-fixture joint positives passed (V4 2/2 + 2/2; V5 2/2 + 2/2; V6 3/3 + 3/3). Offline Oracle suite rerun: 9 passed. All arms use GUI-only Codex CLI 0.165.0/GPT-6-Sol, matching per-case source and fixture manifests, 60 calls/actor, 2400-s timeout; MA-ID has two reset isolated Guests, the other arms one reset shared Guest, and the lock arm adds only per-action locking. No CLI or collaboration MCP was granted.

Run JSON, actions, screenshots and Codex logs are on RAID: /mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets/. V5/V6 overlay archives were SHA-256 matched to tmpfs sources. Copy commands emitted permission-metadata warnings although data hashes match. No experiment data was deleted. Root remains critically full (about 19 GiB free at 99%); RAID has about 1 TiB free and /dev/shm about 70 GiB free. There are no active model/Guest containers. Do not clean old artifacts or overlays.

No commit or push was made. Branch: codex/three-new-dualagent-cases-20261112. API key was injected via hidden TTY and not written to source or reports.
