# V38–V42 双智能体新案例：模型结果与判定

更新日期：2026-11-17
分支：codex/all-codesk-cases-20261113
源代码：/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
模型：gpt-6-sol (high)，Codex CLI 0.165.0，GUI-only MCP，单角色最多 60 个 GUI 调用；runner 单角色超时上限 2400s。
实验产物（不入 Git）：/mnt/raid1/mjh/Projects/codesk-v38-v42-20261117/

## 判定口径

- 目标组合按角色级要求：MA-ID 两个角色都 PASS，Shared 两个角色都 FAIL，Shared+PerActionLock 两个角色都 FAIL；Oracle-invalid、模型/进程 timeout 或工具/API error 均不计作 FAIL。
- 只有 V38、V40 完成了有效的三臂序列；V39、V41 在 Shared 未让双方都失败后按预先门控停止，不为凑结果补跑锁臂；V42 Shared 的 A 角色超时，因此不补跑锁臂。
- 这五题不是五个独立底层机制：它们都是 Synthetic Desk 中同一条业务记录、两个字段互不重叠的面板共享一个活动面板状态。它们是五种行业工作流实例，扩展了表层内容和资料，不应宣称为五种机制。

## 结果总表

| Case | Scripted A/B 正控 | MA-ID A/B | Shared A/B | Shared+Lock A/B | 结论 |
|---|---|---|---|---|---|
| V38 Product Recall Desk | 1.0 / 1.0 | 1.0 / 1.0 | 0.0 / 1.0 | 1.0 / 0.0 | 未命中：锁恢复 A，但 Shared 下 B 仍通过；B 只在锁臂失败 |
| V39 Fleet Safety & Service Cover | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 0.0 | 未运行 | 未命中：Shared 只让 B 失败，A 仍通过；按门控停止 |
| V40 Tree Hazard & Crew Desk | 1.0 / 1.0 | 1.0 / 1.0 | 0.0 / 0.0 | 0.0 / 0.0 | 命中一次：本批唯一完整符合角色级 PASS/FAIL/FAIL 的 Case |
| V41 Accessible Passenger Service | 1.0 / 1.0 | 1.0 / 1.0 | 0.0 / 1.0 | 未运行 | 未命中：Shared 只让 A 失败，B 仍通过；按门控停止 |
| V42 Hazardous-Waste Manifest & Pickup | 1.0 / 1.0 | 1.0 / 1.0 | A timeout / 1.0 | 未运行 | 无效/部分：A 超时 2400.7s、无可用 token 用量；不把 timeout 记作 FAIL |

因此，本批有 1/5 符合目标组合，V39、V41 为有效但未命中的部分筛查，V38 为完整有效三臂非命中，V42 为模型超时导致的部分实验。没有重复运行，不声称重复验证。

## 每案记录

### V38 — Product Recall Desk

- Fixture assets-r2/v38。当初 r1 的模型能填完，但 Oracle 因数量字段表示、商店串联分隔方式及日期表示过严产生 0 分。未将该轮作为机制失败；改成单纯数量字段、统一商店短语、日期按日历语义比较后另建 r2 并重跑正控/三臂。
- MA-ID：cdesk3-v38-ma-id-20261117T050453Z-3946681，A/B 1.0/1.0。
- Shared：cdesk3-v38-shared-20261117T051406Z-3951535，A/B 0.0/1.0。
- Shared+Lock：cdesk3-v38-shared-lock-20261117T052752Z-3957091，A/B 1.0/0.0。
- 判定：不符合完整要求。共享失败没有落在 B，锁又恢复 A。

### V39 — Fleet Safety & Service Cover

- r1 / 首次 r2 模型尝试暴露出自然语言自由文本大小写并不应被 Oracle 当作语义差异：输入 Left rear brake-line leak 与种子说明里的 left rear brake-line leak 字义相同。为防止无关大小写导致假阴性，对 v39.defect、v40.hazard、v41.device 三个自由文本字段限定为折叠空白+大小写不敏感；枚举、ID、状态等其余字段仍严格相等。新增相应正负单测；此规则不能把不同短语放过。
- 归一化后 MA-ID：cdesk3-v39-ma-id-20261117T073827Z-4013573，A/B 1.0/1.0。
- Shared：cdesk3-v39-shared-20261117T075217Z-4019405，A/B 1.0/0.0。A 完成车辆检查，B 的路线覆盖记录因共享中的面板切换未完成。
- 判定：不符合双方 Shared 都失败的门槛，故不运行锁臂。先前 ...T072232Z-4007089 为大小写规则修正前结果（A 被 Oracle 过严拒绝；B Codex 子进程 exit 1、token usage unavailable），保留作诊断，不纳入通过/失败判定。

### V40 — Tree Hazard & Crew Desk

- Fixture r2 将任务说明中的短语 split limb over trail 与预期自由文本统一；正控 A/B 1.0/1.0。
- MA-ID：cdesk3-v40-ma-id-20261117T060601Z-3976183，A/B 1.0/1.0；总耗时 486.0s，Guest boot 161.0s，Agent 时间 290.1s。
- Shared：cdesk3-v40-shared-20261117T061419Z-3980478，A/B 0.0/0.0；总耗时 837.7s，boot 98.9s，Agent 时间 682.2s。A 显式报告树木评估表被切至 crew 工作单而无法可靠保存，B 在 30 次 GUI 调用后未获得正确 Oracle 状态。
- Shared+Lock：cdesk3-v40-shared-lock-20261117T062829Z-3986100，A/B 0.0/0.0；总耗时 2419.8s，Agent 时间 2264.4s。B 显式报告每次输入间工作区在 hazard/crew 面板之间切换；A 运行 39 次 GUI 调用后状态仍不符合 Oracle。
- 这是本批唯一目标命中。但锁臂约 40 分钟，样本仅一次；需注意 Oracle 只显示最终字段不符，Shared 的明确归因主要来自 Agent 轨迹陈述，不是 OS 窗口焦点遥测。

### V41 — Accessible Passenger Service

- 首次 MA-ID cdesk3-v41-ma-id-20261117T070910Z-4000165 的 A 仅因 Aisle chair / aisle chair 大小写被严格 Oracle 判 0；B 通过。自由文本定向大小写归一化已解释并覆盖单测。
- 归一化后 MA-ID：cdesk3-v41-ma-id-20261117T081452Z-4028426，A/B 1.0/1.0。
- Shared：cdesk3-v41-shared-20261117T082633Z-4033945，A/B 0.0/1.0。A 明确声明 passenger form 与 gate coordination 反复互切而不能保存；B 完成 Gate C14 协调。
- 判定：有效非命中，不补跑锁臂。

### V42 — Hazardous-Waste Manifest & Pickup

- Scripted 正控及 MA-ID 均通过；MA-ID：cdesk3-v42-ma-id-20261117T085444Z-4043633，A/B 1.0/1.0。
- Shared：cdesk3-v42-shared-20261117T090753Z-4050609。B 1.0，A status=timeout、exit_code=-9、agent_s=2400.7，无可用 token usage；结果 JSON 对 A 的 0.0 是超时后的占位评分，不是有效任务 FAIL。
- 判定：A 的共享臂无效，停止；不运行锁臂。不要把该实验包装成 Shared FAIL。

## 可复现

在 HealthCare 上：

    cd /home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
    export REPRO_ROOT=/mnt/raid1/mjh/Projects/codesk-v38-v42-20261117
    export CO_DESK_ASSETS_ROOT=$REPRO_ROOT/assets-r2
    export CO_DESK_RUN_ROOT=$REPRO_ROOT/runs-r2/triplets
    export CO_DESK_OVERLAY_ROOT=$REPRO_ROOT/overlays-r2
    export CO_DESK_OVERLAY_ARCHIVE_ROOT=$REPRO_ROOT/overlays-r2
    export CO_DESK_CODEX_RUNTIME_ROOT=/home/mjh/.cache/codesk-next3-runtime
    export CO_DESK_API_BASE_URL=https://docode.cc/v1
    bash scripts/run_new_case_arm.sh v40 ma-id
    bash scripts/run_new_case_arm.sh v40 shared
    bash scripts/run_new_case_arm.sh v40 shared-lock

V42 原始 fixture 使用 REPRO_ROOT/assets、runs、overlays。两套实验根目录均保留，未删除失败、timeout、旧 fixture 或运行证据。API key 只经 SSH stdin 提供，没有存入仓库或实验文档。

## 实现与验证

- 五个案例的 source task card、Guest Fixture、Oracle 和 OSWorld task adapters 位于 tasks/paragui/；脚本正控及三臂 runner 位于 scripts/。
- 已完成五题的 scripted GUI 正控（A/B 均 1.0）。
- 更新 targeted case-insensitive free-text Oracle；其它字段依旧严格。tests/test_v456_oracles.py：39 passed。
- 结果只能支持“行业工作流皮肤覆盖 + 一个较强的 active-panel 竞争命中”；不支持“新增五种独立机制”，也不支持“5 个都达标”。
