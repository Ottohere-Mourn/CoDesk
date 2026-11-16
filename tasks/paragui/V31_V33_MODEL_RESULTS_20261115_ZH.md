# V31–V33 GPT-6-Sol model result audit

日期：2026-11-16
分支：codex/all-codesk-cases-20261113
Model/Harness：GPT-6-Sol, high effort；Codex CLI 0.165.0；endpoint https://docode.cc/v1。正式三个 case 均使用相同的 60 GUI calls/Actor、2400-second Actor timeout。下列 input/output token 是 Codex usage event 报告值；input 含 cached tokens，不等同于 API billable tokens。

## 可计分结果

耗时是每个 Actor 的 agent_s，不是 arm 总墙钟时长。Shared/lock 的两个 Actor 并行或交错操作同一 Guest，因此不应把 A、B 秒数相加后当作总时长。

| Case | Arm | Agent A：score / calls / s / input-output tokens | Agent B：score / calls / s / input-output tokens | Run ID |
|---|---|---|---|---|
| V31 | MA-ID | 1 / 15 / 444.2 / 276,838–565 | 1 / 17 / 532.2 / 333,272–697 | cdesk3-v31-ma-id-20261115T123233Z-2933404 |
| V31 | Shared | 1 / 15 / 568.2 / 277,854–732 | 1 / 37 / 1324.2 / 1,185,712–1544 | cdesk3-v31-shared-20261115T124637Z-2939533 |
| V31 | Shared+Lock | 1 / 37 / 1374.1 / 1,196,761–2692 | 1 / 57 / 2064.2 / 2,626,800–4950 | cdesk3-v31-shared-lock-20261115T131133Z-2947808 |
| V32 | MA-ID | 1 / 17 / 862.2 / 334,522–706 | 1 / 14 / 662.2 / 252,170–536 | cdesk3-v32-ma-id-20261115T134836Z-2957699 |
| V32 | Shared | 0 / 28 / 958.2 / 732,904–2850 | 1 / 46 / 1390.2 / 1,764,279–2569 | cdesk3-v32-shared-20261115T140633Z-2965093 |
| V32 | Shared+Lock | 1 / 34 / 1130.2 / 1,033,752–2478 | 1 / 36 / 1486.2 / 1,136,460–1609 | cdesk3-v32-shared-lock-20261115T143221Z-2972377 |
| V33 | MA-ID | 1 / 18 / 610.1 / 361,269–549 | 1 / 24 / 962.1 / 564,808–1449 | cdesk3-v33-ma-id-20261115T151753Z-2987450 |
| V33 | Shared | 1 / 39 / 1236.2 / 1,307,083–2502 | 0 / 26 / 960.1 / 650,418–2803 | cdesk3-v33-shared-20261115T153708Z-2995132 |
| V33 | Shared+Lock | 0 / 50 / 2400.3 / usage unavailable (timeout) | 0 / 59 / 2202.2 / 2,719,232–4429 | cdesk3-v33-shared-lock-20261116T053752Z-3361839 |

备注：V33 lock arm 的 Agent A 达到 2400-second timeout；其 score=0 不能作为失败证据。Agent B 状态为 done，达到 59 GUI calls 后 Oracle score=0；因此 B 的 transfer 任务可以与其 MA-ID=1、Shared=0 组成一次有效 task-level tuple。另一 actor 的 timeout 仍是重要 arm 级预算 caveat，不能省略。V33 lock mode 合计 105 action_lock events、累计 lock_wait_s=8.18；V31 lock=84 events/11.61s，V32 lock=56 events/3.40s。

## Scripted Guest positive controls

三个 controls 都在同一任务/Fixture 设置下把 A、B 任务交给脚本完成，两个 Oracle 均 1.0：

- V31：cdesk3-v31-scripted-joint-20261115T121029Z-2924390，2/2 PASS；Agent A 的表单有一次脚本 retry。
- V32：cdesk3-v32-scripted-joint-20261115T121335Z-2925678，2/2 PASS。
- V33：cdesk3-v33-scripted-joint-20261115T121628Z-2926927，2/2 PASS。

这些是评分与 reset 的正控，不作为模型试验，也不证明自然 Shared 干扰机制。

## Fixture 和事件审计

| Case | MA-ID / Shared / Lock Fixture SHA-256（逐臂相同） |
|---|---|
| V31 | 7becdcb6e478367588e8aa7e78d1f6157a9486a5ef583fc465068f98840a13f2 |
| V32 | d6f7ccaf1ac11bff52ef147b0ffe588d86a9109dce4b64b25768b82570e06cac |
| V33 | 81a11142b5341dc6963bbbf2ebd2c230d0c32622ceb3beecec40a549d4bc80ab |

所有正式 Shared/lock logs 中 focus_switch_action=true 与 misrouted_focus_before=true 计数都为零。事件显示同一 Chrome window title；这套 telemetry 不足以观察 Chrome tab/panel 内部切换或证明某个键盘事件落到哪一个字段。V32 与 V33 各有一个 Shared Oracle FAIL，因此可报告 task outcome 分歧，但机制因果主张要保持克制。

## Tuple 筛选结论

- **V31：0/3 tuple。** MA-ID、Shared、Shared+Lock 都是 2/2 PASS。
- **V32：0/3 tuple。** MA-ID 2/2 PASS；Shared 仅 Agent A fail；lock 2/2 PASS。
- **V33：1/3 tuple hit。** 同一个 Agent B/transfer task：MA-ID=1、Shared=0、Shared+Lock=0（Agent B 是完成状态且有 Oracle score）；Agent A 锁臂 timeout 单独排除，不算 FAIL。
- **本批次合计：1/3 case-task tuple hit。** 仅表示一个 effective one-time score pattern；不是复现或概率证据，不等于验证了 OS 级焦点误路由，也不是两个 actor 联合任务在锁模式下全部成功/失败的陈述。

## 保留但不纳入统计的尝试

- V31 最早 MA-ID：cdesk3-v31-ma-id-20261115T122637Z-2930310。Agent 尚未启动就因 Codex runtime config 的 FUSE/权限问题无法写配置；后续 runtime metadata 移至 /home/mjh/.cache/codesk-next5-runtime 后重跑。
- V33 早期 api.haogpt.net MA-ID：cdesk3-v33-ma-id-20261115T145938Z-2979990。请求报 error sending request，两个 actor 无 GUI 调用；之后改为用户已授权且可连通的 docode.cc/v1。
- V33 第一次 Shared+Lock：cdesk3-v33-shared-lock-20261115T160013Z-3005790。实验会话中断，没有 result.json；保持不完整目录和事件记录。启动它的 Docker Guest container 后来按其精确 ID 停止，未删容器数据或 overlay。
- V33 detached/no-TTY Shared+Lock：cdesk3-v33-shared-lock-20261116T043742Z-3338217。两个 actor 都到 2400.3 秒 timeout，token usage unavailable；Codex stderr 显示 “Reading additional input from stdin...”。此 run 不可用于 outcome 判定。之后以 PTY/tmux 重跑，获得上表 B 的已完成 Oracle 失败。

## 复现路径和磁盘

代码仓库是 /home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112，OSWorld runtime 在 /home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1。正式 assets、runs 和 overlay archive 在 /mnt/raid1/mjh/Projects/codesk-next5-20261115/{assets,runs/triplets,overlays}；Codex runtime 在本地 ext4 的 /home/mjh/.cache/codesk-next5-runtime，以避免 FUSE chmod/config 失败。重跑命令和环境变量见 docs/THREE_NEW_DUALAGENT_CASES_V31_V33_20261115_ZH.md。原始 run artifacts 没有放进 Git，也未删除。
