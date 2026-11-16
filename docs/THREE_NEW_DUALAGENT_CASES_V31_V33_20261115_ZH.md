# 三个双 Agent 工作流候选：V31–V33

日期：2026-11-16
分支：codex/all-codesk-cases-20261113
状态：三组任务代码、Fixture/Oracle、scripted Guest 正控和 GPT-6-Sol 模型三臂筛选已完成。**本批新增 1/3 个一次性满足 MA-ID PASS + Shared FAIL + Shared+Lock FAIL 的 case-task tuple（V33 的 Agent B/transfer 任务）。**它有 Actor A 的锁臂 timeout caveat，不能描述为双 Actor 全部完成的完整通过；timeout 本身不计 FAIL。

## 共用协议与判定

- GPT-6-Sol 经现有 Codex GUI Harness（Codex CLI 0.165.0），high effort；60 GUI calls/Actor，Actor timeout 2400 秒。
- MA-ID：两个 Actor 分属独立 Guest；Shared：同一 Guest/桌面；Shared+Lock：同一 Guest，GUI 动作由 action lock 序列化。case 的每一臂使用相同 Fixture 版本。
- 每个任务有独立确定性 Oracle，评分根据 Fixture DB 中对应业务记录的字段，不按模型自述计分。每个 case 的 Fixture SHA-256 在三臂一致。
- 每案的 scripted joint Guest 正控均 2/2 PASS。三个新工作流均复用现有 Paragui Synthetic Desk/Chrome 模板，区别主要是业务外壳与字段任务，并没有新增 GUI Runtime。
- 判定约定沿用聚合 handoff：由同一 task/Actor 在 MA-ID 通过，并在 Shared 和 Shared+Lock 至少各有一个**已完成且 Oracle 失败**的 task，即计为一次性 tuple hit。timeout/infra-error 绝不算 FAIL。比如 V33 锁臂的 Agent A timeout 不计 FAIL；只有 Agent B 完成且 Oracle=0 的 transfer task 用于判断锁臂。

## V31 — Civic Data Office：数据治理审查 + 开放数据发布

**情境：**Civic Data Office 将合成数据集 DAT-6028 纳入公共开放数据目录。

- **Agent A / governance review：**填写 sensitivity、retention period、public-access decision、governance review reference。
- **Agent B / release preparation：**填写 approved export format、planned release date、public catalog title、release package reference。
- **共享状态：**浏览器 Synthetic Desk 内 DAT-6028 的相邻治理/发布流程；任务目标分别保存审查和发布记录。
- **Oracle/Fixture：**TaskV31Civicreview 与 TaskV31Releaseprep 检查各自结果行；Fixture 文件在 RAID 上的 assets/v31/。
- **三臂共同 Fixture hash：**7becdcb6e478367588e8aa7e78d1f6157a9486a5ef583fc465068f98840a13f2。

| 臂 | Agent A | Agent B | case 级结果 |
|---|---:|---:|---|
| MA-ID | 1.0（15 calls） | 1.0（17） | PASS |
| Shared | 1.0（15） | 1.0（37） | 不满足 Shared FAIL |
| Shared+Lock | 1.0（37） | 1.0（57） | 不满足 Shared+Lock FAIL |

**判定：不达标 / all-pass。**锁臂 Agent B 用到 57/60 个 GUI 调用，但没有达到硬上限，不据此声称预算导致失败。

## V32 — Northshore Energy Cooperative：电表差异调查 + 现场复访

**情境：**Northshore Energy Cooperative 处理合成电表差异 MTR-1472。

- **Agent A / meter review：**填写 finding、verified reading、account action、review reference。
- **Agent B / site revisit：**填写 assigned technician、visit date、arrival window、work-order reference。
- **共享状态：**同一 MTR-1472 工作区中的调查与后续派工表单。
- **Oracle/Fixture：**TaskV32Meterreview 与 TaskV32Sitevisit 检查各自结果行；Fixture 在 RAID 的 assets/v32/。
- **三臂共同 Fixture hash：**d6f7ccaf1ac11bff52ef147b0ffe588d86a9109dce4b64b25768b82570e06cac。

| 臂 | Agent A | Agent B | case 级结果 |
|---|---:|---:|---|
| MA-ID | 1.0（17 calls） | 1.0（14） | PASS |
| Shared | 0.0（28） | 1.0（46） | 至少一项 Shared FAIL |
| Shared+Lock | 1.0（34） | 1.0（36） | 不满足 locked FAIL |

**判定：不达标。**有效的一侧 Shared 失败由锁臂恢复为全通过，不能计完整 tuple。现有遥测没有捕获明确焦点误路由；该失败只按 Shared 下 Oracle 未通过记录。

## V33 — Great Lakes Wildlife Rescue：野生动物分诊 + 转运交接

**情境：**Great Lakes Wildlife Rescue 处理合成收容个案 WILD-3381。

- **Agent A / intake triage：**填写 species group、condition、triage disposition、assessment reference。
- **Agent B / transfer coordination：**填写 receiving center、transfer date、transport setup、transfer manifest reference。
- **共享状态：**同一浏览器 Synthetic Desk 中 WILD-3381 的收容/转运工作区。
- **Oracle/Fixture：**TaskV33Intaketriage 与 TaskV33Transfer 检查各自结果行；Fixture 在 RAID 的 assets/v33/。
- **三臂共同 Fixture hash：**81a11142b5341dc6963bbbf2ebd2c230d0c32622ceb3beecec40a549d4bc80ab。

| 臂 | Agent A / triage | Agent B / transfer | case 级结果 |
|---|---:|---:|---|
| MA-ID | 1.0（18 calls） | 1.0（24） | PASS |
| Shared | 1.0（39） | 0.0（26，Agent done） | B 任务有效 FAIL |
| Shared+Lock | 0.0（50 calls 后 2400 秒 timeout；不计 FAIL） | 0.0（59 calls，2202 秒，Agent done） | B 任务有效 FAIL；A 仍 timeout |

**判定：计 1 个一次性 case-task tuple hit，锚定同一个 Agent B/transfer 任务。**B 在 MA-ID 通过、Shared 失败、Shared+Lock 也完成并被 Oracle 判失败。Agent A 的锁臂超时是独立的预算截断，明确不计作失败；因此这不是“双 Actor 都成功跑完”的完整 lock triplet，联合任务完成情况仍受限。B 只剩 1 个 GUI 调用的预算余量，属于明显的成本 caveat。

## 三案汇总

| Case | MA-ID | Shared | Shared+Lock | tuple 判定 |
|---|---|---|---|---|
| V31 | 2/2 PASS | 2/2 PASS | 2/2 PASS | 不达标 |
| V32 | 2/2 PASS | 1/2 FAIL | 2/2 PASS | 不达标 |
| V33 | 2/2 PASS | B FAIL | B FAIL；A timeout 排除 | 计 1 次（仅 B/transfer tuple） |

所以本批次新增 **1/3** 一次性 tuple hit。V32/V33 的 Shared 分数差异只是 workflow-level 证据，不是 OS 窗口焦点证据。所有已写入的 Shared/lock 事件里，focus_switch_action=true 与 misrouted_focus_before=true 都为 0；遥测只看见同一个 Chrome window title，无法排除 Chrome 内 tab/panel 切换，也无法逐键证明输入落点。三案仍是同一 Synthetic Desk active-panel/current-record 模板的业务变体，不应算成三种独立机制。

## 运行记录和异常排除

### Scripted joint positive controls

- V31：cdesk3-v31-scripted-joint-20261115T121029Z-2924390，2/2 PASS（Agent A 有一次表单重试）。
- V32：cdesk3-v32-scripted-joint-20261115T121335Z-2925678，2/2 PASS。
- V33：cdesk3-v33-scripted-joint-20261115T121628Z-2926927，2/2 PASS。

### GPT-6-Sol 三臂有效结果

**V31**：MA-ID cdesk3-v31-ma-id-20261115T123233Z-2933404；Shared cdesk3-v31-shared-20261115T124637Z-2939533；Shared+Lock cdesk3-v31-shared-lock-20261115T131133Z-2947808。所有 run 的 scores 都是 2/2。

**V32**：MA-ID cdesk3-v32-ma-id-20261115T134836Z-2957699；Shared cdesk3-v32-shared-20261115T140633Z-2965093；Shared+Lock cdesk3-v32-shared-lock-20261115T143221Z-2972377。分数依次是 2/2、1/2、2/2。

**V33**：有效 MA-ID cdesk3-v33-ma-id-20261115T151753Z-2987450（2/2）；Shared cdesk3-v33-shared-20261115T153708Z-2995132（1/2，B FAIL）；可用于 B tuple 判定的 TTY Shared+Lock cdesk3-v33-shared-lock-20261116T053752Z-3361839（结果 scores A=0、B=0；A status=timeout，B status=done 且 Oracle score=0）。此 run 的 event log 有 105 个 action_lock 事件，累计 lock_wait_s=8.18；B 完成任务需 59/60 GUI calls，Agent A 在 50 calls 时达到 2400 秒 timeout。

另保留两次不能作为结果的 lock 尝试：cdesk3-v33-shared-lock-20261115T160013Z-3005790 在会话中断时无 result.json；cdesk3-v33-shared-lock-20261116T043742Z-3338217 用 detached/no-TTY 方式执行，A/B 都在 2400 秒 timeout，token usage=0，Codex stderr 写有“Reading additional input from stdin...”。它们不改变上述有效 Actor B oracle 结果，但也不被当成额外重复。

## 复现

在 HealthCare 现有 OSWorld Guest/runtime 中运行；run 输出和 Guest overlays 放 RAID，Codex runtime metadata 放本地 ext4。有效模型 endpoint 是 https://docode.cc/v1。API key 用隐藏 TTY 输入，不放入 argv 或文件。

~~~bash
export CO_DESK_ASSETS_ROOT=/mnt/raid1/mjh/Projects/codesk-next5-20261115/assets
export CO_DESK_RUN_ROOT=/mnt/raid1/mjh/Projects/codesk-next5-20261115/runs/triplets
export CO_DESK_OVERLAY_ROOT=/mnt/raid1/mjh/Projects/codesk-next5-20261115/overlays
export CO_DESK_OVERLAY_ARCHIVE_ROOT=/mnt/raid1/mjh/Projects/codesk-next5-20261115/overlays
export CO_DESK_CODEX_RUNTIME_ROOT=/home/mjh/.cache/codesk-next5-runtime
export CO_DESK_API_BASE_URL=https://docode.cc/v1
# 如需重建 Fixture，先把 ASSETS_ROOT 指向一个全新目录；builder 会重写该 case 的 seed.db
# export CO_DESK_ASSETS_ROOT=/mnt/raid1/mjh/Projects/codesk-next5-20261115/assets-rebuild-unique
# python3 tasks/paragui/build_v456.py v31 "$CO_DESK_ASSETS_ROOT/v31"
read -rs -p 'GPT-6-Sol API key: ' OPENAI_API_KEY; export OPENAI_API_KEY; echo
./scripts/run_new_case_arm.sh v31 ma-id   # arm 可换为 shared / shared-lock
~~~

case 的源配置在 tasks/paragui/v456_data.json；生成 SQLite Fixture 的 builder 是 tasks/paragui/build_v456.py。builder 会重写目标目录中的 seed.db，复建时应使用新/备份过的输出目录，不要覆盖需要保留的 Fixture。Task class 需同步到 OSWorld 的 evaluation_examples/task_class/；Runner 会比较源码与 Guest runtime 副本，不一致则拒绝启动。Codex CLI 对 stdin/PTY 有依赖，正式实验需使用有 PTY 的持久会话。原始 run、截图、events 与 overlays 位于 HealthCare RAID 的 runs/triplets/ 和 overlays/，不在 Git 中。

## 证据边界

- V31 的首次 MA-ID cdesk3-v31-ma-id-20261115T122637Z-2930310 在 Agent 启动前因 FUSE runtime config 写权限错误失败；改用 /home/mjh/.cache/codesk-next5-runtime 后重跑才有效。
- V33 的首次 MA-ID cdesk3-v33-ma-id-20261115T145938Z-2979990 连接 api.haogpt.net 出现 error sending request，双方均无 GUI 调用；不计结果。有效 V33 model runs 使用 docode.cc/v1。
- source/fixture hashes、events.jsonl、result.json 与 actor 目录保存在每个 run ID 下，所有失败/超时/不完整尝试均原样保留；不要通过删 artifact 来“清理”结果。
