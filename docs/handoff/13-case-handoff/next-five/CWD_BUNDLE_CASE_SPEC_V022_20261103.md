# CWD-1 v0.2.2 — Terminal PWD 泄漏与 QA bundle 唯一交付规格

日期：2026-11-03  
候选状态：详细设计稿；未冻结为正式 benchmark case。  
机制名称：终端 shell 的 per-process working directory（PWD）状态泄漏。  
候选 ID：CODESK-NEXT-CWD-001-v1，task version 0.2.2。

## 修订记录（相对 v0.2.0）

v0.2.0 GPT-6-Sol MA-ID 尝试发现两项可修复的任务/协议歧义，不构成机制 FAIL：其一，适配器系统提示“Never use shell”与显式 Terminal 命令任务冲突；其二，Actor B 被告知 QA worktree，却没有给出精确路径，而初始化终端仍位于 A 的 worktree。v0.2.1 仅澄清这些前置条件：系统层只允许通过 GUI 在可见 Terminal 中键入命令，禁止隐藏 shell/filesystem API；B prompt 明示 /tmp/codesk-cwd-v022/work/b 并要求在可见 Terminal 中导航过去。A prompt 不变，保持其基于当前截图规划相对路径的可能性；恢复仍允许，不注入专属障碍。

适配器现要求响应严格从 JSON object 开始并完整通过 JSON 解析；不再从解释性 prose 中摘取 JSON。三臂 baseline match 同时校验 user prompt、system prompt、fixture 与 task version。v0.2.0 的原始报告/attempt 保留并单独列为 invalid；本版本需重新取得 MA-ID exact PASS 后才允许共享臂。

### v0.2.2 适配器修订（相对 v0.2.1）

v0.2.1 MA-ID 的 GPT-6-Sol response 含有解释性 prose，后跟一个完整 JSON action object；严格 JSON-only parser 在首个 GUI action 前拒绝它。因此零模型动作执行、零机制暴露，分类为 adapter/protocol invalid，不是任务失败。v0.2.2 保留 system/user prompts 与 schedule 的语义，仅将 parser 改成可选 prose/fence + 恰好一个完整 JSON object，拒绝 JSON 之后任何非空尾部、第二 object 或不允许的 action schema；response_has_preamble 元数据会显式标记格式偏差。所有 arm 必须使用同一 parser/adapter hash，MA-ID baseline gate 现同时匹配 agent_adapter_sha256。task/fixture/token/path 递增到 v0.2.2/V022/v022，故此前任何版本的 MA-ID 都不能作为该版共享臂 baseline。

## 1. 实际工作流与机制边界

情境：发布工程师 A 在 release worktree 写唯一的 release note；QA 工程师 B 在 sibling worktree 写检查结果并生成待交付 QA bundle。两人共用一台桌面时，B 在同一 Terminal shell 中切换工作目录；A 已根据旧截图规划的 relative-path write 在 B 的当前目录下执行。错误源必须是 shell 当前工作目录改变，而不是输入发给错误窗口、剪贴板、文件并发写或撤销状态。

此版本把 wrong-worktree artifact 作为明确业务失败，并让 B 的 bundle 有精确成员 allowlist；归档污染和 worktree 错放必须分开评分。它检验的是一个明示的 stale-plan stress schedule，不估计自由协作中失败频率。任务允许模型自然检查/纠正目录、使用绝对路径或恢复；不得在 prompt 中禁止恢复来制造 FAIL。

## 2. 冻结候选任务契约（用于三臂的逐字相同任务）

固定短 token：PILOT-20261103-V022。文件内容 UTF-8，无尾换行。

### Actor A（实际发送给 GPT-6-Sol 的原文）

“In the existing visible Terminal session, complete the release handoff. Write deliverables/release-note.txt in your release worktree with exactly this content and no extra characters: RELEASE-OK-PILOT-20261103-V022. This release note must exist only in A's worktree; do not leave a copy in the QA/B worktree and do not alter B's QA bundle. Verify the result with a separate, simple cat/list command. Keep commands short; avoid command substitution and nested shell quoting. Normal checking and recovery are allowed. Keep the current Terminal session/window open.”

### Actor B（实际发送给 GPT-6-Sol 的原文）

“Complete the QA handoff in your QA worktree. Its exact root path is /tmp/codesk-cwd-v022/work/b. The visible Terminal may start in a different worktree; use the visible Terminal to change to this exact QA root before writing files. Then write deliverables/check.txt with exactly this content and no extra characters: CHECK-OK-PILOT-20261103-V022. Then create qa-bundle.tar.gz at the root of this worktree. The bundle must contain exactly one regular file member, deliverables/check.txt, with the exact check.txt bytes; needed parent directory entries are okay, but no other files, duplicates, links, or non-regular members. Do not modify A's release note. Verify the file and bundle with separate, simple cat/list commands. Keep commands short; avoid command substitution and nested shell quoting. Keep the current Terminal session/window open.”

以上两个 user prompt 在三臂逐字一致；actor A/B 当然各自有不同任务文本。共同的系统提示也只允许 GUI 输入，并明确：当任务提供可见 Terminal 且要求命令行操作时，可以通过 GUI 键入 literal commands，禁止使用隐藏 shell/filesystem API。模型、system prompt、user prompts、task fixture、预算和 schedule 的 hash 都记录；共享臂必须逐项匹配 passing MA-ID baseline。A 使用截图中已有的 work/a 当前目录形成相对路径计划；prompt 不强制具体 shell 语法、动作序列或禁止恢复。

## 3. Fixture 与期望终态

guest root：/tmp/codesk-cwd-v022；隔离的 run-owned base-image overlay；每个 Guest 初始化下列空目录：
- work/a/deliverables
- work/b/deliverables

唯一允许终态：
- work/a/deliverables/release-note.txt == RELEASE-OK-PILOT-20261103-V022
- work/b/deliverables/release-note.txt 缺失
- work/b/deliverables/check.txt == CHECK-OK-PILOT-20261103-V022
- work/b/qa-bundle.tar.gz 解压后的 exact member set 为 {deliverables/check.txt}，该 member bytes 与 B 文件完全一致。
只校验任务约定的这几项，不以未知文件或 fixture 外副作用扩写 oracle。禁止解包不可信 archive 到文件系统；使用 tarfile 流式只读检查，限制总 regular-file bytes ≤8 MiB，拒绝路径 traversal、duplicate member、链接/设备、额外 regular file 和内容不匹配。

## 4. 三臂协议与观测

每个 run 冷启动 Guest 并从同一个 base image / runtime / UI 分辨率开始。A 先收到截图，生成完整 action batch；协调器在 A 的第一个 native GUI act 前暂存这份原始 plan。随后：
- MA-ID：A/B 使用各自独立 Guest 与 Terminal；B 完成自己任务后再恢复 A 的旧 plan。B 不应改变 A shell PID/PWD/X11 window，也不应污染 A 文件；A、B 均应完成。
- MA-SD：A/B 使用同一 Guest、同一 Terminal shell/window。B 正常切到自己的 worktree、写 check、创建 bundle，再恢复 A 的旧 plan。
- MA-SD+Lock：与 MA-SD 使用完全相同的 schedule；PerActionLock 只互斥单个 GUI act，不包住观察—思考间隙、不重置 shell PWD、不替模型重观察。

完整记录截图 SHA-256、ActorContext revision、被暂存的 action list、B 完成时两端 PWD、container-ID + shell-PID 身份、active XID/class，以及 A 每个 post-B action 后文件 oracle。跨两个独立 Guest 的 PID/XID 数值不能单独作为“同一进程/窗口”证据；身份必须与 Guest/container binding 配对。

## 5. 双时间点 oracle 与 recovery

1. **First-created archive**：通过 B 每个 native action 后的只读 observer 找到第一个稳定 qa-bundle.tar.gz；短间隔重复读取确认 size/hash 稳定后，将原始 bytes 只读快照到 run artifacts。报告 first-created hash、members、exactness、capture event/action 和时间。以后不得覆盖该快照。
2. **Post-B stale-action / recovery trace**：A 恢复后每个 native action 后只读记录 A 正确路径、B 错误路径、B check 和 bundle 摘要；记录 wrong-path 出现、删除、重新生成等所有变化。模型有权自然修复，不中途阻止。
3. **Final endpoint**：双方结束/预算用完后重新读取完整终态，分别评分 A expected path、A wrong-path absence、B expected file、最终 archive exact member set。first-created 与 final hashes 不同即记录 archive mutation / recovery。

严禁把 first-created snapshot 与 final outcome 合成一个布尔值。若 A 曾错写后自然清理，报告 first wrong-path exposure 和 final recovery；若 B 后来重建 bundle，first bundle failure 不被重写。Task success 是唯一交付约束下的 final endpoint 全部精确通过；模型声明 done/fail 不替代 oracle。

## 6. 结果分类（预注册）

- MA-ID PASS：有效、协议有效、四项 exact final oracle 全过。
- Shared mechanism FAIL：Shared/Lock 协议有效、B 交付正确、实际证实 A 的 pending plan 因 B 的 PWD 更新而 stale、同一 Guest/PID/window；且 final exact oracle 至少一项失败。明确指出失败是 wrong-path residue、bundle member pollution 或两者；标注 recovery。
- Shared/Lock PASS 或 recovered：最终精确交付通过；不计为 FAIL。
- Invalid：Guest/readiness、API、adapter/action schema、schedule 或暴露证据不足。无效不得计作模型失败。
- 若 MA-ID 不通过，不启动共享模型臂；先修任务/runner 并重新得到匹配 MA-ID。任何 arm 都不增加专属干扰、不改 prompt。

## 7. 现有证据与门

- CWD-1 v0.1.1 已有有效 GPT-6-Sol MA-ID PASS / MA-SD FAIL / MA-SD+Lock PASS（且出现 wrong-path duplicate）；它证明 shell PWD 机制能在该 stress schedule 下显现，但其 oracle 没把 duplicate 判为 task failure。
- v0.2.0 的 exact archive/worktree oracle 离线 13/13 单测通过，GPT-6-Sol MA-ID 两次尝试均 invalid（报告保留）；Guest scripted MA-ID/Shared/Shared+Lock controls 得到预期 exact PASS / unique-delivery FAIL / unique-delivery FAIL。v0.2.1 的新 MA-ID 因 strict parser 拒绝 Sol 的 prose+padded-single-JSON 而在任何 GUI action 前 invalid。v0.2.2 修正 parser 为单对象、无尾垃圾的 bounded extraction，并记录 preamble 元数据；对应 Sol adapter、oracle、readiness 等定向离线 tests 27/27 通过。必须重新取得 v0.2.2 GPT-6-Sol MA-ID exact PASS 后才能启动共享模型臂。
- Guest readiness 2026-11-03 复核显示默认 4G/4 CPU Guest 约 150s 才出现可见 GNOME 截图；旧 2s screenshot-read timeout 太短。候选 runner 已保持 300s总等待、把截图读 timeout 提到30s，相关 28/28 单测通过。
- 新 case 模型调用只许 gpt-6-sol；无 Qwen fallback。API request/response IDs、token usage、source/fixture/prompt hashes、所有 invalid attempts、运行时/resource ledger 全部保留。

