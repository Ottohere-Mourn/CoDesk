# CoDesk：3 个新双 Agent Case — 开发与实验交接

更新：2026-11-12

## 当前结论

已在 HealthCare 的独立 worktree 实现三个 paraGUI task pair、确定性 SQLite fixture、业务 Oracle、离线控制测试，以及用于 Shared+Lock 的 opt-in per-MCP-call lock。一次真实 OSWorld Guest setup smoke 已启动 Guest、上传本地 app/fixture、打开浏览器、取得截图并运行 evaluator。

**尚未完成 GPT-6-Sol 的 MA-ID / Shared / Shared+Lock 模型 triplet；当前没有新 Case 可声称达标。** setup smoke 使用零动作 scripted policy，score 0.0 仅说明空任务不通过，不是模型结果或有效任务 FAIL。

## 判定门槛和一致配置

每案使用同一 frozen task pair、prompt、fixture、Codex Harness、模型、工具权限和预算：

- MA-ID：OSCombo 的 isolated 模式；两位 Agent 在独立 Guest 并发执行，每个 Guest 从相同 pair seed DB 开始。
- Shared：parallel 模式；两位 Agent 共用一个 Guest、Chrome GUI 会话和本地 app database。
- Shared+Lock：同一 parallel 条件加 opt-in action lock。锁只包围一次会改变 GUI 的 MCP 调用及其返回截图，不保护 agent reasoning，也不提供跨多步操作的事务。
- 三臂统一 GPT-6-Sol、Docode endpoint、high reasoning、45 个 GUI MCP-call 上限、同一 Codex binary/version、相同环境 reset。
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
- Guest overlay、OSWorld cache、run output 放在 /mnt/raid1/mjh/Projects/codesk-next3-20261112/；当前 RAID1 约 1.1 TiB 可用，根盘约 26 GiB 可用/99% 使用。runs 串行执行；不清理其他用户的 Docker image/container 或历史数据。
- Docker provider 的本地 swcub package 来自 /home/mjh/Projects/CoDesk-candidate-repair-20261104；环境通过 SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE 指定已有本机 runtime，并将 SWCUB_OSWORLD_OVERLAY_HOST_DIR 指向 RAID1，避免再触发 Docker Hub 下载。
- smoke 的前两次尝试是 infra-invalid：第一次因 PYTHONPATH 缺少 swcub；第二次 provider 使用默认 Docker image 名称、尝试从 Hub 获取时遇网络超时，未实际拉到镜像。后续改用本地 runtime 与 RAID overlay 后，Guest GUI setup 正常；零动作脚本结果 score 0.0。
- 系统 PATH 中没有 codex；使用既有显式 binary /home/mjh/.local/share/codesk-case3-tools/codex，版本 codex-cli 0.165.0。所有 arms 将固定同一 binary/version；这与旧记录的 0.155.0 不同，不和旧 triplet 混合。

## 文件和验证

- 任务、应用、fixture builders、Oracle：tasks/paragui/task_pg*、app_*、build_*、pg_*。
- pair roster：lists/paragui_v1_combos.txt。
- 本地控制：tests/test_shelter1_reference_controls.py、tests/test_k1_reference_controls.py、tests/test_k2_reference_controls.py。
- Action lock：tests/test_action_lock.py；runner：scripts/run_new_case_arm.sh。
- 六个 task class 可通过 OSWorld task loader 导入；离线正/负 controls 和 lock test 共 9 passed；bash -n 与 git diff --check 通过。
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
