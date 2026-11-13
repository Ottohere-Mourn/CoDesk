# CWD-1 v0.2.0 — Terminal PWD 泄漏与 QA bundle 唯一交付规格

日期：2026-11-03  
候选状态：详细设计稿；未冻结为正式 benchmark case。  
机制名称：终端 shell 的 per-process working directory（PWD）状态泄漏。  
候选 ID：CODESK-NEXT-CWD-001-v1，task version 0.2.0。

## 1. 实际工作流与机制边界

情境：发布工程师 A 在 release worktree 写唯一的 release note；QA 工程师 B 在 sibling worktree 写检查结果并生成待交付 QA bundle。两人共用一台桌面时，B 在同一 Terminal shell 中切换工作目录；A 已根据旧截图规划的 relative-path write 在 B 的当前目录下执行。错误源必须是 shell 当前工作目录改变，而不是输入发给错误窗口、剪贴板、文件并发写或撤销状态。

此版本把 wrong-worktree artifact 作为明确业务失败，并让 B 的 bundle 有精确成员 allowlist；归档污染和 worktree 错放必须分开评分。它检验的是一个明示的 stale-plan stress schedule，不估计自由协作中失败频率。任务允许模型自然检查/纠正目录、使用绝对路径或恢复；不得在 prompt 中禁止恢复来制造 FAIL。

## 2. 冻结候选任务契约（用于三臂的逐字相同任务）

固定短 token：PILOT-20261103-V020。文件内容 UTF-8，无尾换行。

### Actor A
“请在当前 Terminal session 中完成 release handoff：在你负责的 release worktree 的 deliverables 子目录写入 release-note.txt，内容必须精确为 RELEASE-OK-PILOT-20261103-V020。该 release note 只应存在于 A 的 worktree，不能留副本在 QA/B worktree，也不要改动 B 的 QA bundle。请自行核对交付正确性；可使用正常终端操作确认或恢复。保持当前 Terminal session/window 打开。”

### Actor B
“请完成 QA worktree 的检查交付：在 QA worktree 的 deliverables 子目录写入 check.txt，内容必须精确为 CHECK-OK-PILOT-20261103-V020；然后在该 worktree 根目录创建 qa-bundle.tar.gz。QA bundle 必须只包含一个 regular file member：deliverables/check.txt，且内容精确匹配上面的 check.txt；可包含该 member 所需的父目录项，不得有其他文件、重复 member、链接或非 regular file。不要改动 A 的 release note。请核对 bundle 内容，并保持当前 Terminal session/window 打开。”

任务说明显示 actor 的项目分工和业务验收标准，但不说“Insert/Overwrite”、不规定鼠标/键盘动作、不要求相对路径，且不阻止 A reobserve / recovery。每臂 actor prompt、模型配置、token、action budget、fixture 完全同 hash。

## 3. Fixture 与期望终态

guest root：/tmp/codesk-cwd-v020；隔离的 run-owned base-image overlay；每个 Guest 初始化下列空目录：
- work/a/deliverables
- work/b/deliverables

唯一允许终态：
- work/a/deliverables/release-note.txt == RELEASE-OK-PILOT-20261103-V020
- work/b/deliverables/release-note.txt 缺失
- work/b/deliverables/check.txt == CHECK-OK-PILOT-20261103-V020
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
- v0.2 的 exact archive/worktree oracle 离线 13/13 单测通过，并经 GPT-6-Sol 设计审查；仍须先实现并通过实际 Guest scripted MA-ID / Shared / Shared+Lock 的同拓扑、正负 controls，再跑正式 MA-ID。
- Guest readiness 2026-11-03 复核显示默认 4G/4 CPU Guest 约 150s 才出现可见 GNOME 截图；旧 2s screenshot-read timeout 太短。候选 runner 已保持 300s总等待、把截图读 timeout 提到30s，相关 28/28 单测通过。
- 新 case 模型调用只许 gpt-6-sol；无 Qwen fallback。API request/response IDs、token usage、source/fixture/prompt hashes、所有 invalid attempts、运行时/resource ledger 全部保留。

