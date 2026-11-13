# Case 2 Lite 研究交接（2026-10-29）

## 先读这里

本交接对应分支 `codex/overnight-cases-2-4`，工作区含任务开始前的本地改动以及本轮未提交改动。不要切回或清理工作区，也不要覆盖现有的 `HANDOFF.md`；它记录的是另一条 Data-to-Deck 研究线。

Case 2 Lite v1 和离线业务闭环已实现，针对 Lite 的离线测试为 **26 passed**。Guest 截图压缩修复、Python 运行环境和缺失的 `libGL` 已有可复用的本机修复。**真实 Guest 的 Guest→Case Desk HTTP 转发还没有通过验证，所以正负 Guest controls、真实模型任务、Shared/Isolated 配对结果目前都没有。** 最近的 QEMU 尝试在等待用户消息期间中断；下面列出的 `progress.json` 若仍为 `GUEST_BOOT`，不代表有活进程。

## 仓库和实现

- 仓库：`/opt/data/private/mjh/projects/CoDesk`
- 分支：`codex/overnight-cases-2-4`（从 `collab-cases` 建立，带有原有本地改动）
- 新任务：`oscombo/collab/ticket_to_resolution/lite_v1/`
- 任务卡：`oscombo/collab/ticket_to_resolution/lite_v1/TASK_CARD_ZH.md`
- UI：`oscombo/collab/ticket_to_resolution/webapp.py` 的可选 `variant="lite-v1"`；默认完整 Case 2 不变
- 启动适配：`oscombo/collab/ticket_to_resolution/runner.py`
- 离线正反向及手递交时序测试：`tests/test_ticket_to_resolution_lite.py`
- Guest 脚本控制：`infra/run_ticket_to_resolution_lite_native.py`
- 真实截图模型 runner：`infra/run_ticket_to_resolution_lite_model.py`
- PNG Guest 临时修复工具：`infra/fix_guest_png_encoding.py`（原来就在未跟踪的本地文件中；Lite runner 仅在 Guest 源码 SHA 匹配时应用）

Lite 将 A 的票据核验压到 6 个关键 GUI 操作，将 B 的退款与结案压到 7 个，合计目标 13 个。A 保存独立 Review 并发消息；B 必须读取 Review、独立确认依据，再退款和结案。数据库服务、Actor 身份、角色权限和 Oracle 仍走原 Case 2 业务实现，任务卡不给出判断答案。正例应由 A/B Oracle 共同通过；反例应保存 Review、拒绝退款并保留未结案票据。

## 主机和数据路径

- OSWorld checkout：`/opt/data/private/mjh/OSWorld-V2`
- Guest 基础镜像：`/opt/data/private/mjh/deps/osworld/images/osworld-v2-ubuntu-x86.qcow2`
- 基础镜像已验证 SHA-256：`28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a`；大小 `14,891,810,816` 字节；QEMU 以只读 base + 每 run overlay 启动
- 私有 QEMU 前缀：`/opt/data/private/mjh/deps/qemu/jammy-6.2/root`
- Guest Python（启动 Guest runner 必须使用）：`/opt/data/private/mjh/deps/osworld/venv-native-qemu/bin/python`，含 `gymnasium 0.28.1`
- 仓库 `.venv` 只用于项目测试；它没有 `gymnasium`，不能用来启动 OSWorld Guest
- 本机运行库补丁：`/opt/data/private/mjh/deps/libgl-runtime/root/usr/lib/x86_64-linux-gnu`。主机没有 `libGL.so.1`；从 Ubuntu deb 下载并解包到私有目录，没有系统级安装。`infra/run_ticket_to_resolution_lite_native.py` 启动时会补入 `LD_LIBRARY_PATH` 并 re-exec；实测 `cv2 4.8.1` 和 `gymnasium` 可一同导入
- API 私有配置：`/opt/data/private/mjh/secrets/codesk-gui-pilot.json`，权限 `0600`。只读入 runner，不打印、不复制、不提交 Key
- Guest 角色凭证、协议 token、Oracle fixture manifest 都按 run 保存在 `secrets/` 或 `oracle/` 下，权限受限
- 原始 runs：`/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite/`
- tmux socket/log：`/opt/data/private/mjh/runs/codesk/tmux/` 和 `/opt/data/private/mjh/runs/codesk/overnight-20261028/`

Guest 截图服务的原始 `/home/user/server/src/capture.py` SHA-256 为 `915cc325a5cc14ae47aa89fc83ba09da0b64ad742374b161a10666f5d1648273`。当且仅当 run 内 Guest 源码 SHA 匹配时，runner 才对该 run 的可写 overlay 应用无损低压缩等级修复；修复后 SHA 为 `70fdab48feb304daea788baebf3547c3ebd74638b7f9b9bd1b14ed6f624fd73e`。修复源码、diff 和结果 JSON 留在对应 run 的 `guest_runtime/<guest>/`；base image 未修改。Run `f` 截图已恢复并捕获到非黑色桌面，但 Case Desk 页面请求随后仍超时。

## 模型和 API

- 目标模型 ID：`gpt-6.1-sol`
- 主 endpoint：`https://api.haogpt.net/v1`
- 备用 endpoint：`https://docode.cc/v1`
- 凭证只在上述 0600 私有 JSON。最终记录 endpoint 标签和模型 ID，不记录 key
- 两 endpoint 的 `/models` 均列出目标 ID；两边都完成了 synthetic screenshot + `report_visible` 工具调用，模型 ID 符合请求
- 主 endpoint 预检：约 14.27 秒，4,459 input + 20 output tokens；备用 endpoint：约 6.57 秒，83 input + 41 output tokens。这些只是 API 能力预检，不是任务实验
- Gateway 没提供可核对的货币成本，因此还没有真实货币成本数字
- 模型任务 relay：`oscombo/responses_tool_image_relay.py`；每角色 relay 事件和 token/延迟日志写入 run 私有目录

## 已完成实验和证据

1. **离线验证：通过。** `python3 -m py_compile infra/run_ticket_to_resolution_lite_native.py` 成功；`NO_PROXY='127.0.0.1,localhost,::1,10.0.2.100' no_proxy='127.0.0.1,localhost,::1,10.0.2.100' .venv/bin/pytest -q tests/test_ticket_to_resolution.py tests/test_ticket_to_resolution_lite.py` 得到 `26 passed`。`git diff --check` 通过。
2. **模型连通性：通过预检。** 两网关与工具调用都通；没有发起任何真实 Case 2 模型任务。
3. **Guest PNG：局部修复有效。** Run `f` 在本地 overlay 对 Guest 源码应用了 SHA-guarded 修复，base 镜像哈希不变，截图接口恢复，桌面最终可见。控制随后在登录页面网络请求处失败。
4. **GUI Guest 正负 controls：未通过。** 尚无 A/B Oracle 成功或失败结果，不能将脚本步骤当实验 outcome。`controls_pass` 已要求精确正反例 Oracle、A/B 操作数及 B 的 Review/message 读取证据，避免只凭脚本退出码报成功。
5. **真实模型 Shared/Isolated：未开始。** 因为 Guest→应用通路未通过，模型调用数为 0，Shared 输入锁/轮流操作/焦点复查消融也未开始。

## Guest 失败记录

所有失败原始目录都保留在前述 runs 目录，不要按成功结果筛选。主要 run：

- `ttr-lite-shared-controls-20261029a`：QMP socket 路径过长；base image 哈希复核不变，清理已验证。
- `...b`：启动前 progress/run-root 顺序问题，未启动 VM。
- `...c`、`...d`：Guest/浏览器可见性或黑屏问题，分别约 482 秒、627 秒；清理已验证。
- `...e`：直接登录页请求超时，约 897 秒；清理已验证。
- `...f`：PNG overlay 修复和可见桌面成功；Guest 登录请求超时约 15 秒，总 run 453.61 秒；QEMU 停止前 RSS 约 2.9 GiB、CPU user 891.65 秒，cleanup 和端口释放已验证。
- `...g`：PNG overlay 修复生效；修复后显式 `curl --noproxy '*'` 的重复 `/health` 超时 15 秒，Case Desk access log 没有收到 Guest 请求。QEMU 运行约 359.69 秒，base image 哈希不变，cleanup 已验证。
- `...h`：误用仓库 `.venv`，缺 `gymnasium`；未启动 Guest，cleanup 已验证。
- `...i`：改用 OSWorld Python，QEMU 在 TCG 启动阶段；之后遇用户中断，保留 overlay 和 `GUEST_BOOT` progress，未有最终 result。
- `...j`：运行环境缺 `libGL.so.1`，约 26 秒失败，cleanup 已验证。随后把需要的 Ubuntu runtime libs 解包到私有目录，并加入 runner 自启动环境配置；`cv2` 与 `gymnasium` 导入验证通过。
- `...k`：私有库修复后的新试跑已启动 QEMU，但下一次用户中断时仍在 `GUEST_BOOT`。PID `12487` 后来已不存在，manifest/progress 是中断前快照，没有控制结果。

早期 run 的 `progress.json` 可能显示启动中；必须先看 `result.json`、QEMU `manifest.json` 和 PID 是否仍活着，不能把旧 progress 当作活动 run。

## 下一位接手的执行顺序

1. 保持当前分支和原有 dirty work。先检查 `git status`，只提交/改本任务文件；本轮尚未提交 commit。
2. 先恢复一个新的 Shared scripted control run，再做 Isolated。两个条件的 app、backend、fixture、任务卡、权限和 Oracle 相同；Guest 各自使用 OSWorld Python。不要重用已非空的 run root。
3. 首要诊断 Guest→Host app 转发：`10.0.2.100:8765` 经 QEMU `guestfwd` 指向 host `127.0.0.1:<app_port>`。旧实现无 `--noproxy` 的健康响应没有进入 Case Desk access log，可能受 Guest proxy 环境影响；这是待证假设。新 runner 现在先运行强制直连 health probe，失败时收集 proxy 变量是否存在、Guest IP/routes，并保留错误。
4. 直连失败时，在下一次 Guest probe 同时观察 host `ss -ntp`、listener 地址/端口、Case Desk `db/case.http.jsonl` 和 QEMU manifest；检查 Guest 的 route、proxy 和 `NO_PROXY`，修好 guestfwd 后再浏览器登录。不要因代理健康响应误判 app 可达。
5. 两个 Guest controls 正反例都通过后，先跑单模型单 Agent solvability，再做小并发 pilot，然后做真实 Shared/Isolated 配对。使用同一 `gpt-6.1-sol`、role instructions、15 个 GUI call/角色、900 秒 wall/角色和评分规则。保留所有失败证据。
6. 只有 Shared 有截图证明的 focus/input 冲突时，才分别测输入锁、轮流操作或 focus recheck；不预设缓解有效或无效。Case 2 未有可信配对证据前不扩 Cases 3/4。

建议从仓库根目录用独立 tmux socket 启动，避免与原 `HANDOFF.md` 所记录的其他实验共用 session 名：

```bash
SOCK=/opt/data/private/mjh/runs/codesk/tmux/codesk-case2.sock
RUN=ttr-lite-shared-controls-20261029m
ROOT=/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite/$RUN
LOG=/opt/data/private/mjh/runs/codesk/overnight-20261028/$RUN.log
tmux -S "$SOCK" new-session -d -s case2 \
  "cd /opt/data/private/mjh/projects/CoDesk && NO_PROXY='127.0.0.1,localhost,::1,10.0.2.100' no_proxy='127.0.0.1,localhost,::1,10.0.2.100' /opt/data/private/mjh/deps/osworld/venv-native-qemu/bin/python infra/run_ticket_to_resolution_lite_native.py --mode controls --condition collaborative_shared --run-id '$RUN' --run-root '$ROOT' > '$LOG' 2>&1"
tmux -S "$SOCK" list-sessions
```

该控制 run 可在同一独立 tmux server 中持续检查；新用户消息有时会结束当前执行上下文及其子进程，所以每次恢复前先看 tmux socket、run PID 和 manifest，再决定是继续旧 run 还是新建 run ID。不要覆盖旧 run 的原始证据。

## 2026-10-29 续跑补充：Case 2 Lite 与最新 Guest controls

### 项目目标澄清

当前这条工作线要沿用 Case 1 精简版所体现的“缩短 GUI 协作任务、但保留真实业务判断/交接/独立复核”的方向，把 **Case 2 Ticket-to-Resolution 精简化并验证**。不是只做 QEMU 网络修复，也不是开始消耗模型 API。原完整 Case 2 保持不变，Lite v1 是独立可选 variant；当前目标是先把 Lite 控制组跑通，再按门槛进行模型实验。

仓库基线为分支 `codex/overnight-cases-2-4`，HEAD `659c417`（`feat: complete seven collaborative case handoff`）；Case 2 Lite v1 作为本地未提交工作存在。实现位置、13 个目标 GUI 操作（A 6、B 7）、保留完整 Case 2 默认行为等见上文。

### 最新验证进度（本补充覆盖本文较早的过时状态）

- Guest→Case Desk HTTP 路由已由重复 health 请求、Guest `/login` HTTP 200 且正文 2,380 bytes、Guestfwd relay 的逐连接收发字节计数证明；所以此前“转发尚未证明”的假设已过时。
- Run `ttr-lite-shared-controls-20261029v`：A/B 都登录成功，网页截图可见；但 Chrome 登录后出现原生“Save password?”弹窗并抢焦点。脚本记录的 6 个 A GUI 输入没有写出有效 Case Review，最终 `INFRA_FAIL`（`scripted A did not save a Case Review`）。
- 随后 runner 增加登录后按 `Esc` 关闭浏览器提示；相关测试 **28 passed**，`py_compile` 与 `git diff --check` 通过。
- Run `ttr-lite-shared-controls-20261029w`：Guest 桌面就绪，但 A 的 Chrome 页面停在 `Untitled`，浏览器日志有 Network Service crash/restart；登录页未加载，最终 `INFRA_FAIL`。这次不能验证 `Esc` 修复对流程控制的效果。
- `v`、`w` 两次均已完成清理，QEMU 已退出、overlay 移除、端口释放，base qcow SHA 仍为 `28b617...186a`。所有 run 原始证据仍在独立目录，勿覆盖。
- 至今仍无正/负 GUI controls 的通过结果；因此 Isolated controls、single-agent solvability、pilot、Shared/Isolated 模型配对均未开始。Case 2 任务模型调用数仍为 0。此前记录的 endpoint synthetic 预检不是 Case 2 实验。
- API 凭证不得写入仓库、日志或 handoff；到模型阶段须使用受限权限的私有配置，并继续按 scripted Shared + Isolated controls → single-agent solvability → pilot → paired experiments 的顺序执行。

### 下一步（按用户目标重新对焦）

1. 继续优化/验证 Case 2 Lite 本身；保持完整 Case 2 和既有 dirty work 不动，优先定位 Chrome 空白页/Network Service 崩溃的 Guest 环境原因，并以可见 UI 与 DB/Oracle 证据确认 GUI 控制，而非仅看脚本已发键盘事件。
2. 用全新 run ID 重新跑 Shared scripted controls，正例和负例均通过后再跑 Isolated controls。
3. 两种 controls 都通过后，才依次做 single-agent solvability、pilot 与真实模型 Shared/Isolated 对比；不提前调用模型 API。

## 2026-10-29 夜间续跑：Shared 正例通过，负例判定修订中

- Run `ttr-lite-shared-controls-20261029z` 跑完了正、负两场景，整体为 `CONTROL_FAIL`，不是 Guest/Infra 故障；清理通过、base image SHA 保持不变、无模型调用。
- **正例已满足 Oracle**：A/B 分别 6/7 步，B 读取 handoff 并 GUI 打开 review，退款 88 美元并结案，`joint_business_success=true`。
- **负例操作的业务安全行为实际符合设计**：A 保存一个故意错误的 $80 review；B 用 4 步读 review 并尝试退款；系统以 `REVIEW_INVALID` 拒绝，退款数 0、订单仍 `PAID` 且余额 23500、票据未结案（`REVIEWED`）。但总控要求 `negative_oracle.review_pass=true`，与故意错误 review 的负向场景互相矛盾，导致 `CONTROL_FAIL`。旧 Oracle 的 `review_author_role_ok` 只针对有效 review；无效 review 无法单独表达“确为 A 保存”。
- 已作最小修订：Oracle 增加 `review_recorded_by_expected_actor`（从最新已保存 review 独立判作者）；负向控件门槛现在要求 A 保存一条 invalid review、B 实际打开并收到 `REVIEW_INVALID` 拒绝、无退款、原订单余额/状态保护、票据未解决，而非错误地要求无效 review 通过正向 `review_pass`。新增 invalid-review author 单测；现有相关测试为 **31 passed**，py_compile 与 diff-check 通过。
- 新的 Shared 完整复跑正在 tmux `case2aa` 中，run `ttr-lite-shared-controls-20261029aa`，结果路径 `/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite/ttr-lite-shared-controls-20261029aa`，日志 `/opt/data/private/mjh/runs/codesk/overnight-20261028/ttr-lite-shared-controls-20261029aa.log`。启动时 `model_called=false`。关机/掉线后先检查该 run 的 `result.json` 和 PID，不要重用 run root。
- 目前仍未进入 Isolated、single-agent solvability、pilot 或模型配对；应先确认新的 Shared run `CONTROL_PASS`，再按原 gate 做 Isolated。API key 保持只在模型阶段使用，勿写入文件或日志。

## 2026-10-29 Shared controls gate 通过；Isolated 正负 controls 运行中

- Updated runner + Oracle after run `...20261029z` now verified in fresh run `ttr-lite-shared-controls-20261029aa` with **`CONTROL_PASS`**. Positive A/B=6/7 passed joint Oracle; negative A/B=6/4 saved a deliberately invalid review, B read/reviewed it, got one `REVIEW_INVALID` rejection, no refund, order stayed PAID/$235 balance and ticket remained REVIEWED. Overall `controls_pass=true`, `cleanup_verified=true`, base image unchanged, `model_called=false`.
- Isolated scripted controls have now started in fresh run `ttr-lite-isolated-controls-20261029bb`, tmux `case2bb`; it runs both A and B in separate Guest overlays with the same shared backend/fixture and same positive/negative scripts. Start stage `GUEST_BOOT booting_guest_A`, no model calls. Check `result.json` and processes after reconnect; retain run directory.
- Related offline suite currently **31 passed**. Shared/Isolated controls are gate work only. Do not start models unless this Isolated run also reaches `CONTROL_PASS` and verified cleanup.

## 2026-10-29 Isolated controls：QEMU image-lock 修复与复跑

- 旧 Isolated run `ttr-lite-isolated-controls-20261029bb` 未跑完：Guest A 已启动并仍持有共享只读 base qcow2 时，Guest B 启动流程里的 `qemu-img info` 以默认独占锁打开同一 base，报 `Failed to get shared "write" lock`，因此 `INFRA_FAIL`。清理通过，无残留 Guest/QEMU 进程，base image 未改。
- 根因是两个隔离桌面需同时读取同一只读 qcow2 base，但镜像 helper 对 `qemu-img info/create` 使用默认锁定检查。已新增 `oscombo/qemu_image_ops.py`：inspect 用 `qemu-img info -U --output=json` 并继续校验 qcow2；创建 guest overlay 用 `qemu-img create -u ... -b BASE OVERLAY`。`oscombo/native_qemu.py` 接入 helper，新增 `tests/test_native_qemu_image_ops.py` 覆盖参数和验证。
- 修复后相关离线测试 **34 passed**，`py_compile` 与 `git diff --check` 通过；私有 QEMU 的 help 确认支持 info `-U` 与 create `-u`。`-u` 只跳过创建时对只读 pinned backing 的打开/锁检查；run 仍需核对 base fingerprint、实验 Oracle 和退出清理，不能据此放宽其他数据安全检查。
- 正在用新 run ID `ttr-lite-isolated-controls-20261029cc` 重新跑完整 isolated 正/负 scripted controls，tmux `case2cc`；run root `/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite/ttr-lite-isolated-controls-20261029cc`，日志 `/opt/data/private/mjh/runs/codesk/overnight-20261028/ttr-lite-isolated-controls-20261029cc.log`。A/B 应各使用独立 Guest overlay、共同 backend/fixture。开跑时 `model_called=false`；尚未判定 controls 通过。
- **门槛不变**：必须先看到此 run `CONTROL_PASS` 且 cleanup/base image 检查通过，才能进行 single-agent solvability → 小并发 pilot → 模型 Shared/Isolated 配对。现在仍未进入模型调用，凭证不落盘、不回显。

### Isolated controls 第二次复跑的参数修正（覆盖上文 cc “正在跑”状态）

- `ttr-lite-isolated-controls-20261029cc` 很快在 Guest A 启动前退出，`INFRA_FAIL`，cleanup 与 base fingerprint/SHA 检查通过、`model_called=false`。锁冲突已解决；新错误是该 QEMU 6.2 在 `qemu-img create -u` 模式下要求显式传入 overlay virtual size。
- 再次修正 helper：把 `qemu-img info -U` 返回的 `virtual-size` 传给 `qemu-img create -u ... OVERLAY SIZE`，对缺失/非正整数 size 明确失败。新增单测也断言此参数。使用本机实际 QEMU `qemu-img` 对 pinned 50 GiB base 做了一次临时 overlay create/info 实测成功（格式与 virtual size 均匹配），临时 overlay 已移除；测试 **40 passed**，py_compile 与 diff-check 通过。
- 新的完整复跑 `ttr-lite-isolated-controls-20261029dd` 已启动于 tmux `case2dd`；目录 `/opt/data/private/mjh/runs/codesk/ticket-to-resolution-lite/ttr-lite-isolated-controls-20261029dd`，日志 `/opt/data/private/mjh/runs/codesk/overnight-20261028/ttr-lite-isolated-controls-20261029dd.log`。这才是当前有效 isolated controls run，尚待正/负场景及 cleanup/oracle 结果。
- 不要把前面两次 infra fail 算成控制失败，但都要保留证据。门槛依旧：dd 必须 `CONTROL_PASS` + base 未变 + cleanup verified 后，才进 solvability / pilot / model pair；当前 Case 2 model call 仍为 0。


## 2026-10-29 QEMU shared-base lock fix and isolated rerun

- Isolated run ttr-lite-isolated-controls-20261029dd ended INFRA_FAIL while booting Guest B, before any scripted business controls. The QEMU log confirms the original legacy drive graph still fails to get a consistent read lock on the pinned base while Guest A is live. Cleanup was verified; base SHA-256 before/after remained 28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a; model call count remains zero.
- Added readonly_backed_disk_args() in oscombo/qemu_image_ops.py; native QEMU now uses an explicit blockdev graph: private writable qcow2 overlay plus shared base file and format nodes marked read-only, with file-node locking disabled. This keeps base immutability and per-Guest overlay ownership intact while avoiding QEMU 6.2 legacy-drive backing lock conflicts. Added a unit test for the exact graph.
- Validation: focused Case 2 Lite/native-QEMU suite 41 passed; py_compile and git diff --check passed. Then two independent QEMU 6.2 processes were held live at the same time with separate overlays and this exact blockdev graph; both opened the common base successfully. They were stopped and their temporary overlays removed.
- A fresh isolated controls rerun is now ttr-lite-isolated-controls-20261029ee in tmux session case2ee, using new run root/log paths. It has no model/API calls. Check result.json, progress and cleanup before interpreting it; an actual CONTROL_PASS is still required before solvability/pilot/model phases.
- Do not modify the pinned base, clear any prior evidence, or launch model work before both scripted conditions pass. Existing unrelated dirty work remains untouched.


## 2026-10-29 Isolated scripted controls gate passed

- Fresh run ttr-lite-isolated-controls-20261029ee completed as CONTROL_PASS. Both isolated Guests booted concurrently on distinct writable overlays using the new explicit shared-base blockdev graph; both loaded separate A/B authenticated browser sessions against the same Case Desk backend and passed visible-UI scripted controls.
- Positive control: A/B GUI steps were 6/7; B read A's handoff/review; Oracle confirms the $88 refund, correct partial-refund order state and resolved ticket, with audit payload/sequence and GUI review-open evidence passing.
- Negative control: A/B steps were 6/4; B opened the deliberately invalid review and received REVIEW_INVALID; no refund occurred, the order remained PAID with $235.00 remaining, and the ticket remained REVIEWED. The negative Oracle and protected-state checks passed.
- Cleanup is verified: both QEMU processes exited, overlays were removed, and all forwarded ports were released. Pinned base qcow2 SHA-256 is identical before/after (28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a). Run elapsed 1236.81 seconds; model/API calls are still zero.
- Shared controls run ttr-lite-shared-controls-20261029aa and this Isolated run ee now both pass the required scripted-controls gate. Next research gate is single-agent Lite solvability, followed by the small-concurrency pilot. No Shared-vs-Isolated model pair may start until those gates pass.



## 2026-10-29 Single-agent solvability gate started

- With Shared and Isolated scripted controls both passing and cleanup/base-integrity verified, started the single-agent Lite solvability run: ttr-lite-single-agent-solvability-20261029a (tmux session case2solvability).
- The restricted private model config was validated by file mode and presence only; no credential value was printed or added to the repo. Authenticated model-catalog preflight returned HTTP 200 from both requested endpoints, and both list gpt-6.1-sol. The runner is configured to request gpt-6.1-sol at medium effort; this run is the first authorized Case 2 Lite task-model gate. At the first checkpoint, task model_called remained false and the single-agent relay was being initialized.
- Run uses the full single-agent role budget (not the pilot cap); no collaborative Shared/Isolated agents are launched in this solvability gate. Retain any outcome and cleanup evidence, then proceed to the small-concurrency pilot only if single-agent solvability passes.


## 2026-10-29 单 Agent solvability 首次启动故障

- 首次尝试 ttr-lite-single-agent-solvability-20261029a 通过了两个端点的无任务模型 catalog 预检（均 HTTP 200，且列出目标模型），建立了 S relay，但在 Guest/Agent 阶段前退出；没有 events.jsonl 记录、没有 QEMU manifest，run 的 model_called=false。原始 run 目录保留，不能覆盖。
- 退出时发现 run_ticket_to_resolution_lite_model.py 的 finally 清理代码引用了未定义的 env_vars_to_clear，实际变量名是 relay_env_names；该 NameError 又遮蔽了先前异常并阻断 result.json 写入。已按唯一正确变量名修复。该 run 专属孤立 relay 已按 ready PID 与完整命令行匹配后终止；确认模型 relay event log 为空。
- 现在先验证修复，再用全新 run ID 重跑 single-agent solvability。API key 没有打印/改写；本故障尝试没有任务模型调用。任何新结果均以新目录记录。


## 2026-10-29 Single-agent runner follow-up fix

- Retry b (ttr-lite-single-agent-solvability-20261029b) also stopped before Guest boot/model calls and produced a preserved INFRA_FAIL result: relay_urls was referenced but not initialized. The corrected finally path did run, stopped the relay, and wrote result.json; relay event log is empty, there are no QEMU manifests, and model_called=false. cleanup_verified is false because Guest services/ports were never created, not because of a remaining process.
- Added an explicit per-role relay_urls mapping initialization alongside the relay PID/token maps. Revalidate syntax/tests before another fresh run; previous run directories remain untouched.


## 2026-10-29 Single-agent runtime prerequisite fix

- Fresh attempt c (ttr-lite-single-agent-solvability-20261029c) reached the Guest_BOOT stage but failed before QEMU creation: the model runner had not invoked the existing private libGL runtime bootstrap, so OSWorld import reported libGL.so.1 missing. It produced a preserved INFRA_FAIL; relay log is empty, no QEMU process/manifest or task model request occurred, and the relay was stopped. cleanup_verified is false because startup failed before allocating services/Guest.
- Updated the model runner main path to call the same _ensure_guest_runtime_libraries bootstrap used by the scripted-controls runner before starting the episode. Extended the runner-state regression test to require this prerequisite call. Revalidate, then retry with a fresh run directory.


## 2026-10-29 Single-agent boot retries: relay state, GUI libraries, static audit

- The first two task-runner starts exited before Guest boot/model calls: attempt a exposed two finalizer bugs (undefined env_vars_to_clear and missing relay_urls); attempt b confirmed the cleanup fix and exposed relay_urls. Attempt c then exposed that the model entry point had not bootstrapped private libGL runtime libraries before importing OSWorld. For a/b/c, relay event logs are empty, model_called=false, no QEMU Guest manifest survived/was created, and each owned relay process was stopped; all original run roots remain preserved.
- Fixed the finalizer to clear the existing relay_env_names set, initialized relay_urls beside other per-role relay state, and invoked native._ensure_guest_runtime_libraries() in model runner main before episode startup. Added a static symtable regression guard against unresolved global references in the model runner and checks for the initialized relay state/bootstrap.
- Focused Case 2 Lite/native-QEMU suite now **43 passed**; model runner py_compile and git diff --check passed. Launching a fresh solvability run next; it is the first retry with all three startup fixes and no task model request before the Guest agent is ready.


## 2026-10-29 Single-agent browser startup finding

- Attempt d reached a real Guest desktop with the read-only-base blockdev graph, passed direct Guest health/login HTTP probes, and captured a content-ready Ubuntu desktop; it failed before the model agent/API task because Chromium disappeared during login-page launch. At timeout the Guest showed only the desktop wallpaper, had no Chrome process/window, the DevTools endpoint refused connections, and the browser log showed a Network Service crash/restart. No task request was recorded; model_called=false. Original run d result/artifacts remain preserved.
- The run manifest shows its owned QEMU was stopped and overlay removed; pinned base SHA stayed unchanged, relay was stopped. The model report could not receive the helper's cleanup rows because browser preparation raised before its resource tuple returned, so cleanup_verified was conservative/false. The setup helper now records Guest/server/port cleanup before rethrowing and the model finalizer consumes those rows.
- Added Guest-side memory, filesystem, kernel-log and Chromium Crashpad-file diagnostics to the browser startup failure path, to distinguish OOM/disk/kernel termination from a browser/network crash on the next attempt. No browser flags/task design changed. Focused suite remains 43 passed; both runner modules compile and diff-check passes.
- Single-agent solvability is still an open gate. Starting a fresh attempt e with no task-model call until an authenticated visible browser session and Agent harness are ready.


## 2026-10-29 Single-agent model gate is now active

- Fresh attempt e passed the browser step that failed in d: its S Guest is ready, Chrome rendered and logged into the visible Case Desk S session, and the authenticated desktop is handed to the single-agent Codex harness. Run status is MODEL_ACTORS_RUNNING.
- The task-model relay event log now has 4 upstream requests; unlike the earlier boot-only retries, this is a real single-agent solvability attempt and model API calls have begun. The key remains only in the permission-restricted private config/environment and is not in artifacts.
- No pass/fail judgment yet. The run uses the full S role budget (20 desktop steps / 1200 seconds), and should be allowed to finish or hit its declared budget; inspect result.json, token counts, oracle, screenshots and cleanup before deciding whether to begin the small-concurrency pilot.

## 2026-10-30 resumed status: single-agent solvability stopped on relay usage accounting

- Read-only inspection confirms run `ttr-lite-single-agent-solvability-20261030a` is complete with `INFRA_OR_BUDGET_STOP_WITH_ORACLE_SCORE`; preserve its run directory and do not reuse the ID.
- The run made 11 upstream requests with HTTP 200 and parsed usage for 7; the last response had `usage: null`. The relay set `usage_unknown=true` and returned HTTP 409 on the next request (the configured output budget was 12,000; accumulated parsed output was 765). This is a relay usage-accounting stop, not evidence that the configured token budget was reached. No provider credential values were logged or exposed.
- The model actor ran 370.04 active seconds and stopped after 10 desktop steps with `Reading additional input from stdin...`; no Case Review/refund was recorded. Oracle joint success is false. Do not treat solvability as passed, and do not start a concurrency pilot or paired Shared/Isolated model runs.
- Cleanup checks recorded `cleanup_verified=true`, `base_image_unchanged=true`, and `service_port_released=true`; run evidence and screenshots remain preserved.
- Resume decision: missing streaming-usage parsing is **not** listed as an authorized code task in this handoff. Do not modify relay parsing, change output-budget thresholds, or launch another model call on this basis. The next authorized gate requires explicit review/authorization for a narrow relay diagnosis/fix and regression test; after that, rerun solvability under a fresh run ID and require a true business Oracle pass before the small-concurrency pilot.

## 2026-10-30 Narrow relay usage diagnosis/fix authorized and validated

- 按用户继续推进授权，对 `oscombo/responses_tool_image_relay.py` 做了窄范围、fail-closed 修复：SSE usage 同时识别顶层 `usage` 与 `response.usage`；流末最后一个无换行 `data:` 数据块也会解析这两种位置。未放宽预算，也未忽略 `usage_unknown`。
- 新增 relay 回归覆盖：两种 usage 事件位置、最后无换行数据块；relay 全部测试 **10 passed**。Case 2 Lite/native-QEMU 相关组合测试 **22 passed**，model runner 与 relay `py_compile`、`git diff --check` 均通过。
- 当前仍未重跑 single-agent solvability：下一步必run ID 启动，检查 usage 统计、Oracle、cleanup/base 不变；只有真实业务 Oracle 通过后，才可启动 small-concurrency pilot，再后才是 Shared/Isolated 配对实验。既有失败 run 目录保持不变。
\n\n## 2026-10-30 Case 2 Lite resolution-form usability 修复与 solvability 重跑\n\n- 检查失败 run `ttr-lite-single-agent-solvability-20261030c` 的 HTTP 记录、最终 Agent trace、DB 和业务 Oracle：review 保存和复核路径正常，退款 $88 成功；Agent 最终 GET 退款后的页面，但没有 POST `/lite/tickets/resolve`。Oracle 是 `ticket_status=REFUND_PENDING`、`resolution_audit_payload_pass=false`。Agent 最后把 `88.00` 当作 resolution 表单的客户备注内容，然后试图点击提交；服务端访问记录没有 resolve POST。失败 run 数据、截图及状态均保留。\n- 最小 UI 改善仅针对 Case 2 Lite resolution 表单：将备注标签明确为“简短文字，不是退款金额”，并提供面向客户的简短备注 placeholder；保留原单选 code 和业务校验，不改订单/退款逻辑及 pinned base image。更新了 Lite UI regression test，覆盖退款成功后的 resolution 表单。\n- 验证：`tests/test_ticket_to_resolution_lite.py` **4 passed**；`py_compile`、`git diff --check` 通过。\n- 用全新 run ID `ttr-lite-single-agent-solvability-20261030d` 启动真实单 Agent solvability，不是 Shared/Isolated 配对或 concurrency pilot。tmux `case2lited`；日志 `/opt/data/private/mjh/runs/codesk/overnight-20261030/ttr-lite-single-agent-solvability-20261030d.log`。启动已确认 `GUEST_BOOT`、`model_called=false`；需跟进最终 Oracle、usage、cleanup 和 base-image 不变。仍须在 Oracle 通过后才进入 pilot/配对实验。\n- API credential 仅从私有权限配置载入，未写入代码/handoff/log 摘要。\n
## 2026-10-30 Lite UI retry and second single-agent gate

- Fresh run `ttr-lite-single-agent-solvability-20261030d` finished as `TASK_FAIL`; preserve all artifacts. It passed the 15-request model/relay stage with usage present on every request (`input=255,796`, `output=827`), then completed 12 desktop steps in 522 active seconds. The agent saved the eligible $88 review but did not open it/issue a refund/resolve; Oracle `review_pass=true`, `refund_pass=false`, ticket remained `REVIEWED`. Cleanup verified and pinned base image unchanged.
- Failure artifact gives a better fix direction than guessing from the prior run: steps 1–12 and the trace show the agent saved a review, then stopped on `/lite` and told the user it had not yet verified/issued/resolved. The task card's “then independently verify … issue … resolve” did not sufficiently enforce mandatory phase completion. We also retain the resolution-form clarification added in the webapp; its test now enters the real post-refund UI state and checks the note label/example and radio control.
- Updated only the Lite single-agent task card with explicit ordered UI steps: reopen saved review, go through “Issue Refund”, then choose “Partial refund — damaged item”, fill a brief customer-facing resolution note (not amount), click “Resolve Ticket”, and continue until visible `RESOLVED`. Added regression assertions for required completion milestones. No business evaluator logic, amount rules or pinned base image changed.
- Focused Lite suite: **5 passed**; `py_compile` and `git diff --check` passed after task-card revision.
- Next required action: launch yet another fresh single-agent solvability run to actually exercise the final tightened task card. Do not start pilot/paired runs until a fresh run reaches the full business Oracle pass.
- Initial status: run `ttr-lite-single-agent-solvability-20261030e` 再次启动真实单 Agent solvability；tmux `case2litee`，初 `GUEST_BOOT`, `model_called=false`。日志 `/opt/data/private/mjh/runs/codesk/overnight-20261030/ttr-lite-single-agent-solvability-20261030e.log`。请跟踪结束后检查完整 Oracle、usage、cleanup/base-image
- Follow-up fresh run `ttr-lite-single-agent-solvability-20261030e` did not call the task model (`model_called=false`) and ended `INFRA_FAIL` before desktop handoff: Chrome's DevTools existed but the signed-in S window disappeared; diagnostics show only GNOME desktop and disk at 95%. `cleanup_verified=true`, `base_image_unchanged=true`; artifacts preserved. Do not count it as a task attempt or infer solvability. Before another new ID, inspect/relieve non-runner disk pressure safely and diagnose the Chromium/window startup failure; do not delete prior run evidence.
codex-plus --no-daemon run 的 Guest/Agent session 已启动后写入，故不会热更新正在运行的 instruction；而 `20261030e` 在 agent 启动前基础设施失败。已核对 runner 每次从 Lite spec 加载指令。下一次 fresh run 才会真正验证最终指令；d/e 均保留且不作为最终通过证据。
- Startup failure retry: because `20261030e` was infrastructure-only, a fresh run `ttr-lite-single-agent-solvability-20261030f` was started to exercise the corrected task card. tmux `case2litef`; initial progress `GUEST_BOOT`, `model_called=false`. Its terminal result is still pending; preserve prior e artifacts and do not call this pass until the full Oracle and cleanup/base checks are complete.

## 2026-10-30 follow-up: late review POST race; solvability rerun extended

- Run `ttr-lite-single-agent-solvability-20261030f` is complete and must remain preserved. The actor reached the correct Lite review form and submitted the supported review. The actor timeout was at `1793349317.495` (1200.21 active seconds); the review row was committed at `2026-10-30T08:35:20.434Z`, about 2.94 seconds later. Its pre-reset DB snapshot was taken at `1793349318.727`, before that commit, so the saved-review transaction was omitted from the scored snapshot. The live post-run DB later contained the correct single `$88` review (`ELIGIBLE`, target dock line/evidence, shipping $0), ticket `REVIEWED`, no refund. This is an actor budget stop plus snapshot race—not a failed review decision; no refund or resolution was attempted.
- Narrow Case 2 Lite runner correction: `infra/run_ticket_to_resolution_lite_model.py` now waits for DB/journal, desktop request, relay-event and completed write-request activity to remain quiet before Oracle scoring/reset; if it cannot establish quiescence, it marks the snapshot unreliable and skips reset. Regression tests simulate a delayed review POST and a non-settling write stream. Focused Lite suite: **7 passed**; `py_compile` and `git diff --check` passed.
- Fresh run `ttr-lite-single-agent-solvability-20261030g` ended `INFRA_FAIL` before model calls because it was launched with the CoDesk `.venv` missing `gymnasium`. Preserve it as an environment launch error, not a solvability attempt.
- Fresh run `ttr-lite-single-agent-solvability-20261030h` is currently running under the pinned OSWorld native-QEMU Python environment, with a calibration override of 30 desktop steps / 2400 seconds. At last check the visible S desktop was ready and model relay events/actions had begun. Do not start concurrency pilot or Shared/Isolated model pairing until this fresh single-agent run passes all business Oracle checks, side-effect drain, cleanup and base-image checks.
- No API credential values were added to this handoff or run artifacts.

## 2026-10-30 follow-up: screenshot-history context growth found

- Run `ttr-lite-single-agent-solvability-20261030h` is complete as `TASK_FAIL`; preserve artifacts. Actor `S` exited normally after 6 desktop steps / 320 seconds, before saving a Case Review. Oracle shows pristine business state (OPEN/PAID; no review/refund); the post-actor drain settled and reset verified pristine, so this score is reliable.
- The prompt in `actor_runs/S/instruction.txt` contains the full mandatory Lite workflow, but the Agent's final response asked for task details and its reasoning hallucinated unrelated product records after several screenshot actions. Relay metadata shows old screenshot images accumulated in conversation input (`input_image_parts` rose to 5–6, with two requests around 180k input tokens). The relay previously moved the newest tool screenshot into a user turn but retained older screenshot images, allowing visual history to crowd the task/visual context.
- Narrow relay fix: `move_latest_tool_image()` now prunes superseded tool screenshot images and older relay-generated screenshot turns while preserving tool text and any explicit user-provided image. Added a regression assertion that a task image plus only the latest desktop image remain. Combined focused suite: **17 passed**; Python compile and `git diff --check` passed.
- Next action: start a fresh single-agent run `20261030i` with the corrected screenshot-history relay, OSWorld native-QEMU interpreter, and the same 30-step / 2400-second calibration override. Do not start the pilot or paired Shared/Isolated model experiment until a reliable fresh Oracle pass.

## 2026-10-30 follow-up: Chrome startup failure diagnostics and fresh solvability attempt

- Preserve fresh run `ttr-lite-single-agent-solvability-20261030i`: it failed as `INFRA_FAIL` before the Agent call. A new clean attempt `...20261030j` reproduced the same visible-browser startup failure; cleanup verified and the pinned base image stayed unchanged. These are infrastructure failures, not Case 2 solvability outcomes.
- Runs i/j reached a ready Guest desktop and the Google Chrome launcher returned success / logged `DevTools listening`, but after the 180-second window wait there was no Chrome window or profile process and the Guest CDP port refused connections. The browser log included a Network Service crash/restart line, but that is not yet confirmed as the root cause. Guest memory remained available; root filesystem was under high use. Runs f/h did launch Chrome successfully, so startup appears intermittent.
- Narrow diagnostic hardening in `infra/run_ticket_to_resolution_lite_native.py`: run Chrome through a detached wrapper that records its PID and eventual exit code; persist those paths in launch metadata; compose all browser-failure diagnostics into one executed Guest shell command (the prior argv arrangement only executed the first command). The failure report now captures exit status, Crashpad/core filenames, DevTools version/targets, and permitted kernel-event hints. This adds evidence collection, not a proven Chrome fix.
- A harmless shell smoke verified the wrapper captures an exit code. Focused regressions passed: 17 passed across the Relay, Lite, and model-runner test files; `py_compile` and `git diff --check` passed.
- Fresh run `ttr-lite-single-agent-solvability-20261030k` has been started with the native-QEMU Python, 30 desktop steps / 2400 seconds, and the updated browser diagnostics. At this note it is still booting; inspect the run artifacts before further action. Do not start a pilot or paired Shared/Isolated run until a single-agent attempt passes the business Oracle and cleanup/base-image checks.
- No API credential values were added to the repository, handoff, or response.

## 2026-10-30 follow-up: Chrome process exit classified; attempt l active

- Run `ttr-lite-single-agent-solvability-20261030k` reached the visible desktop but failed before model invocation (`INFRA_FAIL`). Preserve run artifacts. Cleanup and base-image-unchanged checks passed.
- The new Guest-side monitor captured the Chrome launcher process exiting with status 137 (SIGKILL); DevTools was then unavailable. Chrome's log shows DevTools startup, a Network Service crash/restart, then no browser window. After the exit, Guest memory showed about 4.5 GiB available and no Crashpad files; Guest kernel-log access was denied, so OOM is plausible but not established.
- Added non-invasive cgroup `memory.events`/limit/current, memory pressure, and filtered kernel-journal observations to the next startup-failure report to distinguish Guest OOM from an external SIGKILL. Do not treat status 137 alone as proof of OOM.
- Focused regressions now pass: 22 passed across Relay, Lite, model-runner, and native diagnostics test files; py_compile and diff checks pass.
- Fresh attempt `ttr-lite-single-agent-solvability-20261030l` is running with the correct native-QEMU interpreter and 30-step / 2400-second budget. Continue monitoring browser setup and record Oracle only if the Agent actually starts. No pilot or paired run until the single-agent business Oracle passes.

## 2026-10-30 follow-up: SIGKILL still unexplained; richer Guest evidence enabled

- Run `ttr-lite-single-agent-solvability-20261030l` also stopped before model invocation with `INFRA_FAIL`; cleanup verified and pinned base image unchanged. Chrome wrapper again recorded exit 137. Guest `MemAvailable` after exit was ~4.5 GiB, memory PSI was very low, no Crashpad files were present, and kernel journal access was denied. The attempted cgroup-v2 files were absent, so OOM remains unproven (and cannot be ruled out from this snapshot).
- Before the next attempt, added one-second Guest samples of `MemAvailable` and Chrome/Chromium RSS while the browser process is active, plus discovery of both cgroup-v1 and cgroup-v2 memory counters and filtered user-journal evidence. This is diagnostic-only; browser flags, task, pinned image, and experimental condition are unchanged.
- Focused tests passed again: 22 passed across Relay, Lite, runner, and native diagnostics tests; `py_compile` and `git diff --check` passed.
- Fresh attempt `ttr-lite-single-agent-solvability-20261030m` is now running with 30 steps / 2400 seconds. Check its browser launch diagnostics before deciding on any runtime change. No pilot or paired Shared/Isolated experiment until the single-agent business Oracle passes.

## 2026-10-30 follow-up: Guest RPC timeout during attempt m

- Run `ttr-lite-single-agent-solvability-20261030m` stopped `INFRA_FAIL` before any model call; cleanup and pinned-base verification passed. The failure was an HTTP read timeout from the Guest execute service while collecting browser startup diagnostics, so no failure diagnostics text was saved. The final setup screenshot was only 120 KB, consistent with an incomplete capture but not enough to infer the browser state.
- Attempt m used a temporary one-second Guest memory/RSS sampler. Removed that sampler to reduce Guest-side diagnostic load; this is precautionary, not a proven cause of the RPC timeout. Kept the passive browser exit-code monitor, broadened cgroup v1/v2 discovery, and made Guest failure-diagnostic collection best-effort with bounded 45-second calls so RPC failures are written into the run artifacts instead of aborting evidence capture.
- Focused suite still passes (22 tests). Fresh attempt `20261030n` should use the current code and unchanged task/model condition; monitor whether a visible browser / Agent session starts.

## 2026-10-30 follow-up: bounded Chrome resource diagnostics; fresh attempt o

- Fresh run `ttr-lite-single-agent-solvability-20261030n` ended `INFRA_FAIL` before Agent invocation; preserve the full run. Cleanup and pinned-base-image verification passed. Chrome's detached wrapper recorded exit status 137 again, but this alone does not prove OOM. Browser log showed DevTools startup followed by Network Service failure/restart and eventual CDP refusal. No Crashpad files were found. The Guest resource-diagnostics RPC returned HTTP 500; no business task was attempted.
- Simplified the next diagnostic probe to avoid broad filesystem scans / journal queries: bounded `free`/`df`/MemAvailable, `/proc/self/cgroup`, direct expected cgroup v1/v2 counters, memory PSI, and Crashpad filenames. Kept diagnostics best-effort and did not alter Chrome flags, task text, model condition, or pinned image.
- Latest validation after this edit: `py_compile` passed, `git diff --check` passed, and focused Relay/Lite/model-runner/native-diagnostics tests passed (**22 passed**). Note the OSWorld native-QEMU environment has no pytest module; tests were run with the repository `.venv`.
- Starting fresh single-agent solvability attempt `ttr-lite-single-agent-solvability-20261030o` with the native-QEMU Python, 30 desktop steps / 2400 seconds, and the bounded diagnostics. Follow the startup carefully; if Agent starts, score only after reliable quiet drain and Oracle. If startup fails, retain the Guest diagnostics and investigate before changing runtime conditions.
- Do not start the pilot or Shared/Isolated Agent pairing until single-agent business Oracle, ticket resolution/audit, cleanup, and base-image invariants all pass. No credential values were added to this handoff.

## 2026-10-30 follow-up: attempt o isolated browser SIGKILL; diagnostics probe corrected

- Fresh run `ttr-lite-single-agent-solvability-20261030o` ended `INFRA_FAIL` before Agent invocation. It took 458 seconds for Guest boot; the desktop became content-ready after about 144 seconds of readiness polling. The audited screenshot-capture optimization was applied only in the Guest overlay and the service restarted. Chrome launch returned success, but no Case Desk window/CDP target appeared; the detached Chrome monitor recorded exit 137. Preserve the run. Cleanup and pinned-base-image checks passed; no model call or business action occurred.
- The browser log again recorded DevTools starting and a Network Service crash/restart; no Crashpad file was present. Post-exit MemAvailable was about 4.7 GiB, which does not establish or exclude OOM. The resource probe itself exposed a shell-escaping bug (`awk: unexpected character`), so cgroup counters were not collected in this attempt. This is a diagnostics defect, not a proven cause of Chrome exit.
- Replaced the fragile shell `awk` cgroup parsing with a bounded embedded Python probe that reads `/proc/self/cgroup` and only direct v1/v2 memory counter files. Added a regression test that executes the generated probe and checks markers / no quoting failure.
- Current validation: focused Relay/Lite/model-runner/native-diagnostics suite **23 passed**; `py_compile` and `git diff --check` passed. Next fresh run `20261030p` will recheck Chrome startup and, if it fails again, should retain readable cgroup counters. No pilot or paired Shared/Isolated experiment until a single-agent business Oracle pass.
- No credential values were added to the handoff or repository.

## 2026-10-30 follow-up: attempt p shows renderer fork failure; process-limit diagnostics added

- Fresh run `ttr-lite-single-agent-solvability-20261030p` ended `INFRA_FAIL` before Agent invocation. Preserve the run. Guest boot took about 427 seconds; the desktop became content-ready after ~143 seconds of readiness sampling. Chrome launched but never exposed a Case Desk window/CDP target and exited 137. Cleanup and pinned-base checks passed; `model_called=False`.
- The fixed probe now reads cgroup-v2 memory counters: `memory.events` had `oom=0` and `oom_kill=0`, `memory.max` was unlimited, post-exit MemAvailable was ~4.5 GiB, and memory PSI was zero. Therefore Guest cgroup memory OOM is not supported by this run's evidence. Chrome stderr newly showed `zygote_linux.cc:639 Zygote could not fork: process_type renderer numfds 5 child_pid -1`, which points to a process/resource fork failure, but the exact limit is not yet identified.
- Expanded the bounded Guest probe to include `pids.current/max/events`, user/process/thread counts, `ulimit -u`, `ulimit -n`, `threads-max`, and `pid_max`, alongside memory counters. Added regression coverage. Focused suite: **23 passed**; `py_compile` and `git diff --check` passed.
- Next fresh run `20261030q` will capture those additional counters if the renderer fork failure recurs. The Gate is still closed; do not start pilot or paired Shared/Isolated model runs until single-agent business Oracle and cleanup/base-image conditions all pass.
- No credentials were written to the handoff or logs.

## 2026-10-30 follow-up: attempt q reached the real Agent episode

- Fresh run `ttr-lite-single-agent-solvability-20261030q` is active with the OSWorld native-QEMU interpreter (30 steps / 2400 seconds). Unlike o/p, Chrome displayed the Case Desk page; actor S is `READY` and has made real model calls. At the latest check it had 12 GUI actions / screenshots and 13 relay events, with usage parsing present.
- The latest screenshot is on Order Verification: Eligible is selected, the $80 USB-C dock is selected, and the matching damaged-carton evidence is selected. Shipping treatment and the proposed refund field were still unset in that screenshot; do not treat the task as complete. Continue monitoring the Agent through review save, matching refund, resolution, reliable drain, Oracle, cleanup and base-image verification.
- This is still a single-agent solvability attempt, not a pilot or paired Shared/Isolated experiment. No API credentials were added to this note.

## 2026-10-30 follow-up: attempt q passed review/refund; exhausted 30-step cap before ticket submit

- Run `ttr-lite-single-agent-solvability-20261030q` finished `TASK_FAIL` at the 30-step actor cap. Preserve the run; cleanup verified and base image hash unchanged. The real Agent completed one correct Case Review and one correct `$88.00` partial refund for order line `O-2048-L2` (USB-C dock), using `DELIVERY-EV-77` / `POLICY-RET-4`, with shipping excluded. Oracle: `review_pass=true`, `refund_pass=true`, `order_state_pass=true`, protected state and cross-reference passed.
- The Agent reached Ticket Resolution and selected `Partial refund — damaged item`, but used all 30 actions before the final Resolve Ticket click. Oracle observed `ticket_status=REFUND_PENDING`, so `ticket_state_pass=false`, `audit_payload_pass=false`, and joint business success is false. The final saved screenshot shows the short resolution note filled and the Resolve Ticket button still visible; this is a strict step-cap stop, not evidence the resolution submission failed.
- Run used 37 successful model requests (usage recorded, no missing-usage calls). Focused validations remain 23 passing. No API credentials were added to artifacts.
- Next fresh run `20261030r` will repeat the same single-agent task on the unchanged image with a larger **40-step** budget, so the final ticket-resolution submission can occur. Still no pilot or paired Shared/Isolated models until the complete Oracle passes.

## 2026-10-30 follow-up: larger-step solvability rerun active; publishing code and handoff

- Run `ttr-lite-single-agent-solvability-20261030r` is active with the same task/model/Guest setup and a 40-step budget. Guest boot and browser startup completed; actor S is running and Relay has begun recording model responses. No final score is available yet; continue monitoring its run directory rather than infer a pass from partial actions.
- This handoff is being published together with the Case 2 Lite implementation/tests and the native-QEMU runtime components needed to reproduce the real single-agent gate. Per-run directories and their credentials are intentionally not committed; the run ID, Oracle outcomes and diagnostic summary above are the durable record.

## 2026-10-30 publish-time status refresh

- At the latest check, run `ttr-lite-single-agent-solvability-20261030r` still reports `MODEL_ACTORS_RUNNING`; `model_called=false`, and its `desktop_requests.jsonl` contains 17 entries. No terminal Oracle result is available. This is not a completed or passing solvability run. Keep its run directory and secret files out of Git.
