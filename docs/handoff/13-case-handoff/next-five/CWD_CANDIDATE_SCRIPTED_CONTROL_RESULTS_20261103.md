# CWD-1 scripted topology control — results
Date: 2026-11-03
Repo: /home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102
Run: terminal-cwd-scripted-20261103-03
Artifact root: /mnt/raid1/mjh/codesk-next-candidates-20261103/probes/terminal-cwd-scripted-20261103-03
Classification: scripted GUI/state control only; not an LLM result.

## Outcome

All three scripted condition controls showed the intended topology contrast:

| Condition | A shell PID CWD before A action | A expected path | A found path | B expected path | Result |
|---|---|---|---|---|---|
| MA-ID | /tmp/codesk-cwd/work/a; B in different Guest, PID 2110 | RELEASE-OK-PILOT-20261103 at a/deliverables/release-note.txt | exact match | CHECK-OK-PILOT-20261103 at b/deliverables/check.txt | both exact PASS |
| MA-SD | /tmp/codesk-cwd/work/b; A and B same shell PID 2108 | A at a/deliverables/release-note.txt | missing | A payload instead at b/deliverables/release-note.txt; B check exact at b | target task FAIL; topology mechanism observed |
| MA-SD+Lock | /tmp/codesk-cwd/work/b; A and B same shell PID 2266 | A at a/deliverables/release-note.txt | missing | A payload instead at b/deliverables/release-note.txt; B check exact at b | target task FAIL; topology mechanism observed |

Exact final files and per-arm classifications are in report.json. PWD evidence reads /proc/PID/cwd for each interactive shell PID. events.jsonl shows B's cd and check-file commands precede A's unchanged relative-path write. Shared+Lock used LockedActionEnvironment backed by PerActionLock for each GUI act.

This supports a causal topology control: the same legitimate CWD change affects A only when A and B use the same terminal shell. The lock serializes acts but does not restore the earlier PWD. MA-ID is the negative topology control.

## Evidence limits

- This is deterministic scripted state/topology control, not GPT-6-Sol and not model capability.
- The runner captured A's screenshot before B and delayed A's precomputed relative write until after B, but used Episode.refresh_observation rather than ActorContext.observe. Therefore gui event observed_revision is not an event-level stale-observation witness. The real Sol runner uses OSWorldAgentActor/ActorContext and records pending actions/revision.
- OSWorld active-window-before/after fields were null in scripted rows. The real runner independently records active XID/title/class before A observes, after B completes and after A's first pending action; same XID is required to rule out focus/input routing.
- Scripted Shared and Shared+Lock are feasibility evidence, not benchmark acceptance.

## Runtime and resources

- Wall time: 1,269.145 seconds (21m 9s) for four real Guest starts (two MA-ID, one per shared arm), GUI actions, oracle reads and ledger-owned shutdown.
- resource-events.jsonl confirms all four containers have consistent ownership labels and destroy records. No unrelated Guest/container was stopped.
- Artifacts/overlays are on RAID1; run directory about 3.6 GB. At finish root had about 54 GB free; RAID1 about 1.6 TB free.
- No GPU/model calls; zero token cost. Runtime image was already present; no pull/build.

## Preserved setup attempts

- terminal-cwd-scripted-20261103-01 failed before Guest creation because system Python lacked gymnasium.
- terminal-cwd-scripted-20261103-02 used the OSWorld environment but the first implementation required xterm, absent in Guest. It remains an invalid setup artifact and has an owned Guest destroy record.
- terminal-cwd-scripted-20261103-03 used the existing x-terminal-emulator and completed all controls.

All three artifact directories are kept. None were removed, overwritten or counted as model failures.

## Decision / next step

CWD-1 passes scripted semantic/topology feasibility and is promoted as the first real-agent candidate; it is not yet an accepted benchmark case. Run GPT-6-Sol vision API smoke, then MA-ID first. Only if both actors pass, run MA-SD and MA-SD+Lock. Preserve absolute-path choices, re-observation and recovery as outcomes; do not manufacture failure. Record shell PID/PWD, X11 identity, observation revision, held actions, response IDs/token usage, path oracle, lock call log and lifecycle ledger.

## CWD-1 v0.2.0 scripted Guest topology control（2026-11-03，非模型结果）

运行 cwd-bundle-v020-scripted-20261103-03 已完成，原始证据位于 /mnt/raid1/mjh/codesk-next-candidates-20261103/probes/cwd-bundle-v020-scripted-20261103-03/。冻结版本为 CWD_BUNDLE_CASE_SPEC_V020_20261103.md；运行 wall_seconds=1168.71（19m28.71s），真实启动 4 个 Guest，全部有一致 owner label 与 destroy record。此 run 没有 GPT-6-Sol/Qwen/API 调用。

| 条件 | scripted control | 关键证据 |
|---|---|---|
| MA-ID | scripted_ma_id_exact_pass | 两个独立 Guest/不同 shell；A 文件只在 A worktree，B check 与精确 bundle 成功；final task success=true。 |
| MA-SD | scripted_shared_unique_delivery_fail | 同 Guest、同 shell PID、同活动 XID；A 执行旧相对路径动作时 PWD 已为 /tmp/codesk-cwd-v020/work/b。A 预期路径缺失、payload 落在 B worktree，final task success=false。 |
| MA-SD+Lock | scripted_shared_unique_delivery_fail | 同 Guest/shell/PWD/XID 与 MA-SD；8 次 GUI act，max_concurrent_gui_act_calls=1，仍将 A payload 写入 B worktree，final task success=false。 |

重要解释限制：三个条件中 B 首次创建与最终 qa-bundle.tar.gz 都是精确 allowlist {deliverables/check.txt}。本 run 证明的是 A 的唯一交付错放/缺失以及 B worktree 污染，没有证明 QA archive 被 A 文件污染；不能把 bundle 污染或 archive failure 写成结果。此 scripted schedule 证明机制在固定 stale-plan stress schedule 下可出现，不代表自由协作中的普遍失败率。MA-ID/shared/lock 的脚本状态差异与 oracle 字段均在逐臂 report.json。

正式控制 run 前保留两次 setup-invalid 尝试：...scripted...-01 未 pin runtime，OSWorld provider 对默认远端镜像发起的自动拉取因 registry timeout/HTTP 500 失败，在 Guest 创建前退出；...-02 选择了缺少 gymnasium 的通用 Python venv，也在 Guest 创建前退出。两者均不是 candidate FAIL。之后的 ...-03 已在 OSWorld 自带 .venv 中运行，并在脚本启动前强制核对本地 runtime image ID；未发生 pull/build。运行后容器/QEMU 已清空；root 可用空间约 46 GB，RAID1 可用约 1.5 TB。

本结果只通过当前 v0.2.0 的 GUI/topology/oracle 控制门；不升级历史 v0.1.1 模型证据，也不等于候选最终获准。下一步若进行模型验证，先跑冻结 v0.2.0 的 GPT-6-Sol MA-ID exact pass；仅其两位 actor 都通过才进入同版本 Shared 和 Shared+Lock。
