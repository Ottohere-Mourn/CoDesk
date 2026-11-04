# CWD-1 v0.2.3 — Terminal PWD 泄漏与 QA bundle 唯一交付规格

日期：2026-11-03  
候选状态：本版进入 GPT-6-Sol MA-ID exact-PASS 门；三臂结论仍未知，尚未作为成立 case。  
候选 ID：CODESK-NEXT-CWD-001-v1；机制：同一 Terminal shell 的 process CWD 泄漏。  
模型：只允许 GPT-6-Sol；禁止 Qwen fallback。

## 本版相对 v0.2.2 的改动

v0.2.2 GPT-6-Sol 确实操作了两位 actor 的可见 Terminal，但结果不能评分为候选 PASS/FAIL：
1. runner 调用共享 materializer 时漏传 Guest root；该 helper 默认读取 v0.2.0 路径，因此 v0.2.2 实际文件被误报为缺失。
2. A 的首个模型计划只有 `pwd`，runner 随后才让 B 完成；A 之后重新观察，再写出正确文件。这没有执行预注册 stale relative-write exposure。

v0.2.3 修正两处：每个 materializer 调用显式绑定本版 Guest root；A 可先通过安全的可见 Terminal preflight（如 `pwd`），协调器只在模型自然提出相对路径写入 `deliverables/release-note.txt` 的完整 action batch 时暂停。B 完成 QA bundle 后恢复 A 的**原样待执行 batch，不给新截图、不重规划**。如果模型选择绝对路径、先切回 A、没有提出可识别的相对写入，或未能形成可验证暴露，记为未暴露/协议无效，而非 FAIL；不可强迫模型按特定命令失败。

运行前 source 已通过 py_compile；adapter、CWD oracle、materializer、schedule classifier 与 readiness 的定向测试 30/30 PASS。该单测不证明模型行为或实际 Guest 拓扑。

## 业务任务与冻结文本

Fixture guest root：`/tmp/codesk-cwd-v023`；两边目录均预建 `work/{a,b}/deliverables`。文件为 UTF-8、无尾换行。

### Actor A（逐字 prompt）

“In the existing visible Terminal session, complete the release handoff. Write deliverables/release-note.txt in your release worktree with exactly this content and no extra characters: RELEASE-OK-PILOT-20261103-V023. This release note must exist only in A's worktree; do not leave a copy in the QA/B worktree and do not alter B's QA bundle. Verify the result with a separate, simple cat/list command. Keep commands short; avoid command substitution and nested shell quoting. Normal checking and recovery are allowed. Keep the current Terminal session/window open.”

### Actor B（逐字 prompt）

“Complete the QA handoff in your QA worktree. Its exact root path is /tmp/codesk-cwd-v023/work/b. The visible Terminal may start in a different worktree; use the visible Terminal to change to this exact QA root before writing files. Then write deliverables/check.txt with exactly this content and no extra characters: CHECK-OK-PILOT-20261103-V023. Then create qa-bundle.tar.gz at the root of this worktree. The bundle must contain exactly one regular file member, deliverables/check.txt, with the exact check.txt bytes; needed parent directory entries are okay, but no other files, duplicates, links, or non-regular members. Do not modify A's release note. Verify the file and bundle with separate, simple cat/list commands. Keep commands short; avoid command substitution and nested shell quoting. Keep the current Terminal session/window open.”

三臂均使用同一 actor prompts、system prompt、GPT-6-Sol、temperature=0、512 max tokens、20 actor step budget、fixture、schedule 与 adapter；唯一实验条件是两个独立 Guest、一个共享 Guest、或共享 Guest + PerActionLock。共享臂必须引用通过 exact-PASS MA-ID 报告，且逐项匹配 version、prompt/system/adapter/runner/fixture hashes。任何代码改动都导致旧 baseline 不匹配，须重新跑基线。

## 预注册 schedule 与机制证据

1. 初始化可见 Terminal：工作目录 A，记录 shell PID、`/proc/PID/cwd`、Guest/container ID、活动窗口 XID/title/class 与初始截图。
2. A 观察桌面并正常生成 action batch。若非目标相对写入（例如查询 `pwd`），正常执行并让 A 继续观察；若 batch 含目标相对写入，则在首个 GUI action 前保存完整 batch、截图摘要及 observed revision 并暂停 A。
3. B 使用可见 Terminal 完成 B worktree 的 check 文件和 QA archive。首次稳定 archive 只读快照；允许模型自然检查/恢复。记录 B 完成时 A/B shell CWD、PID/Guest 绑定、active XID、精确 archive 与 check 文件。
4. 恢复 A 冻结的原始 batch。每个 native GUI action 后记录 GUI revision 事件、actor、held observed revision、PWD/PID/window 与文件状态；对目标写入的提交键另记当时 CWD 与 stale-due-other-actor。
5. 允许 A/B 自然继续、检查和修复；最后分别评分终态唯一交付和 bundle。首次归档快照不得被后续重建覆盖。
6. MA-ID：A/B 分属独立 Guest；B 的活动不得改变 A 的 shell CWD。Shared 与 Shared+Lock：相同 Guest、同 shell PID、同活动 Terminal XID；锁只串行化单个 GUI act，不覆盖 observation-to-action 间隙，也不重置 CWD。

共享机制 exposure 必须同时有：A 目标相对写入计划确实在 B 完成前形成并被 hold；同 Guest/PID/window；B 已改变共享 shell PWD 为 B worktree；A 的冻结 batch 在 B 操作后仍按旧 observed revision 执行；目标写入实际在 B CWD 提交，stale_due_other_actor=true。缺任何一项均不作机制归因。

## 精确终态与分类

终态唯一允许交付：
- A: `work/a/deliverables/release-note.txt` 内容精确；B worktree 中不能遗留 A 副本。
- B: `work/b/deliverables/check.txt` 内容精确。
- B: `work/b/qa-bundle.tar.gz` 成员恰为 `deliverables/check.txt`（目录项允许），member bytes 精确；拒绝链接、重复、额外文件等。
- first-created archive 与 final archive 分别记录 hash、members、准确性和 recovery；不得将两者压成同一字段。

MA-ID 只有在 protocol valid 且以上终态全部 exact PASS 时通过；不通过时不得启动共享 arm。Shared/Lock 是有效机制 FAIL 的前提为 protocol/exposure valid、B 交付正确、A 唯一交付或 bundle 终态失败且失败可归因于过期相对写入。最终恢复为 PASS/恢复，不冒充 FAIL。Setup/API/parser/adapter/schedule/exposure/oracle 无效一律记 invalid/未暴露，不计 FAIL。模型自述 done/fail 均不替代 oracle。

## 版本历史、证据边界与运行门

- v0.1.1 有效 Sol 三臂：MA-ID exact PASS、MA-SD FAIL、MA-SD+Lock PASS/recovery（有 B worktree 重复文件）；说明机制能暴露但不满足锁臂 FAIL。
- v0.2.0 scripted Guest topology controls：MA-ID exact PASS、Shared 和 Shared+Lock unique-delivery FAIL；约 19m29s；不是模型证据。它支持基本 Guest 拓扑/状态 oracle，不直接验证 v0.2.3 的 target-write gate。
- v0.2.0 两次、v0.2.1 一次和 v0.2.2 一次 MA-ID Sol 尝试均是 API/adapter/runner/oracle/schedule 无效，不计候选结果；逐次原始 report 与 artifacts 保留。v0.2.2 的已执行操作及根因见 candidate audit update。
- v0.2.3 新增 schedule gate 的 Python classifier 已由定向 tests 覆盖；Guest GUI positive/negative 原型需在任何模型共享臂前用审慎的 scripted control 验证其可观测字段。先跑 v0.2.3 MA-ID；仅 exact PASS 才按 matched hashes 顺序跑 Shared、Shared+Lock。
- GPT-6-Sol vision smoke 必须有效且 API base 一致；Guest screenshots 需可见。runtime image pin、RAID1 artifacts/overlay、resource owner ledger 必须核验；不得 pull/build/prune/删除旧证据。
- 结论只估计这个预注册 stale-plan stress schedule，不泛化为自由协作的一般失败率。
