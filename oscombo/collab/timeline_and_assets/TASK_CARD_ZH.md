# CDD-TLA-001：Timeline-and-Assets — GreenLoop 短片

版本：`0.1.0`。这是 CoDesk 第四个离线协作 Case。唯一真实剪辑应用目标为 **Kdenlive**；工程采用 MLT XML `.kdenlive` 与原生字幕 sidecar。固定视频为本地合成的短素材，不连接外网或真实客户媒体。

## 研究问题

两个 GUI Agent 分别整理素材与编辑时间线时，共享 Kdenlive 实时桌面会引入什么额外成本？除普通窗口焦点外，重点观察源监视器播放头、Project Bin 当前选中素材、活动监视器、时间线播放头、选中时间线片段和活动轨道等应用内部状态。任务不会要求双方同时改同一时间线，也不会按脚本强制制造错误插入。共享状态暴露、可观察干扰、最终结果与恢复必须分别记录。

本 Case 的分工是可审计的专业交接：A 产出镜头选择清单，B 把清单实现为剪辑工程。因为所有事实对双方公开，单个强 Agent 理论上也可能完成全部工作；评测不得把“发过消息”或满足角色产物要求等同于已证明不可替代的协作。

## 用户任务和确定性素材

Northstar GreenLoop 已有一个未完成的 10 秒公益短片工程。请完成“包装分类 → 清洗 → 再利用”的镜头顺序，保留原始媒体和工程素材箱，加入匹配的三条字幕以及完整音乐床。项目配置固定为 320×180、25 fps。素材共四段视频（含一个应保留但不进入时间线的低质量 outtake）和一条 10 秒合成音乐床；所有资产 ID、相对路径、帧数在 `template/asset_catalog.json` 中。

已知可见资料包括：公开任务 brief（含三条字幕原文）、全部源视频/音频、asset catalog、初始 Kdenlive 项目、该项目的初始 SRT 和 `shot_manifest.schema.json`。双方都可以读这些资料、预览任意素材、查看彼此的交付物和消息。素材在 leader/tail handle 中明确显示“LEADER / NO ACTION”或“TAIL / HOLD”，实际动作区间的起止与 gold 帧边界吻合；这让 source trim 可由预览验证，而不是随机挑选时间码。演员不可见 `oracle/` 和包内评分代码。

初始 `GreenLoop.kdenlive` 确实是部分工程：V1 只有开头和结尾两个镜头，源区间错误且总长不足；缺中间清洗镜头；A1 只覆盖开头；字幕缺失一个 cue 且时间不匹配。项目素材箱已包含全部五个固定资产。演员不得改源媒体、从素材箱移除非目标素材或直接调用隐藏生成器写正式结果。

## A/B 完整初始指令

### Actor A — Footage Curator

> You are A, the footage curator for the GreenLoop short. Inspect the supplied source clips in the Kdenlive Project Bin/Clip Monitor and use the brief to prepare `deliverables/asset_shot_manifest.json`. Choose the three usable shots that tell the requested intake → wash → reuse story, record each asset ID and exact source in/out, explain each choice briefly, and note why the unused outtake should stay out of the cut. Keep the original media and starter project intact. B owns timeline editing in Kdenlive. You may inspect the starter project and all source material; if B finds a shot unsuitable or too short, review the request and revise your manifest as needed. You may message or attach the manifest when useful; no message count or timing is prescribed. Do not edit or save the final timeline project.

A 的独立目标是 `asset_shot_manifest.json`：逐段 ID、源入/出帧、故事段落、简短选择理由；对 outtake 说明不放入成片。A 可以使用 Kdenlive Project Bin 与 Clip Monitor 预览，不保存最终工程。

### Actor B — Timeline Editor

> You are B, the video editor for the GreenLoop short. In the supplied Kdenlive starter project, finish the timeline and save `deliverables/GreenLoop_Final.kdenlive` plus its matching subtitle sidecar. Use the shared brief, all source clips, and A's asset shot manifest as useful evidence. Create the requested ordered V1 cut with the specified source ranges, subtitle cues, and music on A1; preserve all source assets in the project bin and do not alter the media. You may inspect footage yourself and may ask A to clarify or revise a selection if it does not fit. You own the final Kdenlive project; do not modify A's shot manifest. Save through Kdenlive GUI in a real episode. Do not infer success from the monitor alone: save, close/reopen in the real-GUI phase, and verify the timeline.

B 的独立目标是通过 Kdenlive GUI 保存最终工程与 SRT；可自行预览源素材、使用 A 清单、要求 A 复核。B 不改 A 的清单。

### Single-Agent 指令

> You are S, responsible for both footage curation and editing the GreenLoop short. Inspect the supplied source clips, write `deliverables/asset_shot_manifest.json` with the selected asset IDs and source ranges, then finish the Kdenlive project and save `deliverables/GreenLoop_Final.kdenlive` with its matching subtitle sidecar. Follow the brief, preserve source files and non-target bin items, and do not use hidden evaluator files. In a real episode, perform project edits through Kdenlive GUI.

## 角色互补与自然交接

A 通过预览对固定素材做镜头筛选和源区间记录；B 将选择转成有序、定时的 V1、字幕和 A1。A 的清单提供可追溯来源，B 的工程提供可播放结果。B 发现片段不适配时可通过共享消息/附件 API 请求 A 复核并更新；A 也可主动补充。没有要求消息轮数、固定交接时点、强制等待或同时点击。

两人可能分别使用 Kdenlive 的 Clip Monitor/Project Bin 与 Timeline/Project Monitor。共享桌面时，切换活动监视器、素材箱选择、source playhead、timeline playhead、active track、timeline clip selection 会影响另一 Actor 对当前上下文的理解。自然的暴露机会是：A 刚预览/选中素材后，B 在同一 Kdenlive session 继续 timeline 操作，或 B 离开再恢复后使用旧观察。只有动作前后观察与最终工程共同显示“内部 context 被改变，后续编辑落入错误对象/轨道/位置”才能记为 interference。单独窗口切换不够。Agent 可以自主重新观察、选择对象、seek、修复或重做。

这是一种 opportunity，不是保证发生的错误。若两个 Agent 选择不交错，MA-SD 可以成功；这仍是有效结果。

## Gold Answer 与最终工程 Oracle

### A 镜头清单标准答案

| 顺序/段落 | 素材 | 源入帧 | 源出帧（包含） | 时长 |
|---|---|---:|---:|---:|
| intake | ASSET-01 | 25 | 99 | 3.00 s |
| wash | ASSET-02 | 25 | 124 | 4.00 s |
| reuse | ASSET-03 | 0 | 74 | 3.00 s |

`ASSET-04` 必须保留在素材箱，不得放入时间线。清单记录每段的来源 ID、帧区间和非空理由。评分器用精确帧序列和资产 ID核对，不读取理由文本来决定影片正确性。

### B 最终工程标准答案

| 轨道 | 位置 | 素材 | 源区间 | 时长 |
|---|---:|---|---|---:|
| Video 1 | 0.00 s | ASSET-01 | 1.00–3.96 s | 3.00 s |
| Video 1 | 3.00 s | ASSET-02 | 1.00–4.96 s | 4.00 s |
| Video 1 | 7.00 s | ASSET-03 | 0.00–2.96 s | 3.00 s |
| Audio 1 | 0.00 s | AUDIO-01 | 0.00–9.96 s | 10.00 s |

时间线总长必须是 250 帧（10.00 秒），镜头连续无空隙、无重叠。字幕以 Kdenlive `avfilter.subtitles` 和匹配 SRT sidecar 表示：

| 起止 | 字幕 |
|---|---|
| 00:00:00.200–00:00:02.800 | Sort it for a second life. |
| 00:00:03.200–00:00:06.800 | Rinse. Recover. Reuse. |
| 00:00:07.200–00:00:09.800 | Ready for another use. |

### 联合 Oracle

评分器从最终 `.kdenlive` 的 MLT XML 解析 Producer、main-bin、track tractor/playlist、entry source in/out、timeline placement、字幕 filter；从配套 SRT 精确解析文本与时码。分别检查 A 清单和 B 工程，最后计算 joint success。还检查所有源资产仍在素材箱、outtake 未进入任何时间线、初始 brief/catalog/project/SRT/媒体 SHA-256 未变。最终评分不相信 GUI 成功提示。

负控覆盖：漏镜头、顺序错误、源区间偏移、错轨、空隙、重复/非目标片段、字幕文本/时码错误、缺字幕 filter/sidecar、A1 时长错误、素材箱删掉 outtake、源媒体污染、缺 A 清单或修改原工程。正确工程必须 PASS，每类上述错误至少一项必须 FAIL。

过程数据（消息、manifest revision、action trace、window sample）独立于业务评分。只有 `actor_id + action + screenshot/hash + app/window state + timeline outcome` 形成可核验链条时才归因 shared-state interference。focus/selection/playhead 观测若非原子采样，应标记相关性证据；不能伪称精确因果。

## 条件公平性

| 条件 | 桌面 | workspace / backend | 预算及消息 |
|---|---|---|---|
| `single_agent` | 一个桌面，一个 S | episode-scoped 唯一 project/media workspace | S 获得 A+B 合计预算；同消息服务与同 Oracle |
| `collaborative_isolated` | A/B 各自独立 desktop session | 与 Shared 相同的 workspace backend ID、相同原始工程/媒体和输出路径；每人独立 Kdenlive session | A/B 各自预算；现有 ProtocolStore |
| `collaborative_shared` | A/B 控制同一 live desktop/session | 与 Isolated 相同的 workspace backend ID、文件与输出路径 | 同样 A/B 预算、ProtocolStore 与 Oracle |

三条件只改变桌面控制拓扑；素材、project backend、初始快照、应用版本、角色、任务、消息功能、各角色预算、评分与 reset 语义固定。MA-ID 的两个桌面必须连接同一个 episode workspace/backend，不能用两套文件副本再把同步失败归因给桌面。当前条件计划只声明该因果契约，OSWorld 多桌面挂载/共享 workspace adapter 尚未接入/验证，不得声称 MA-ID 已可运行。

## 范围与停止条件

- 本版本只覆盖单序列 3 镜头 montage、2 个真实 timeline tracks、1 个 SRT 字幕 sidecar、1 条音轨；不加复杂转场、调色或代理媒体。
- Kdenlive/Mlt 项目 XML 的可解析子集已由离线 Oracle 覆盖；本机没有 Kdenlive/MLT CLI，因此应用实际打开、保存回写、媒体解码和字幕显示尚未验证。Guest smoke 若不能稳定打开/保存此工程，先缩小工程/格式特性，不换自制编辑器。
- 若 A 的清单不提高 B 的镜头可追溯性，或 Solo/Isolated/Shared 无法保持同 backend，暂停此 Case，不用强制 GUI 交错掩盖问题。
