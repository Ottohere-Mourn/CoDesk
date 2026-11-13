# Native QEMU 本地运行副本

用户于 2026-10-25 授权恢复本地运行副本，解决 LeoFS 对依赖导入、Agent 状态和停止标记的间歇读取错误。持久正本、私有模型配置和最终证据继续放在 `/opt/data/private/mjh`。

## 已完成

- 本地目录：`/tmp/codesk-local-runtime-20261025`，权限 0700、含 ownership 和大小上限记录。
- 完成 32,988 个文件的复制与校验，包含 CPython 3.12.15、OSWorld venv、QEMU 6.2、只读 qcow2、CoDesk/OSWorld 运行代码以及 Codex 0.162.1 可执行文件。
- 镜像 SHA-256：`28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a`，与已验证正本一致，无 backing file。
- 本地 venv 增装 MCP 1.12.4；保留 Pydantic 2.11.7，并约束 Starlette 0.47.3、sse-starlette 2.4.1，避免自动安装的新版本破坏原 FastAPI 依赖。`uv pip check` 通过。
- 已修正工作副本的 Python 链接、pyvenv.cfg、console scripts 和 QEMU wrapper 绝对路径。Python/OSWorld/CoDesk 导入预检中没有从 LeoFS 加载的模块。
- 准备完成时占用 17,251,389,440 bytes（约 16.1 GiB），本地缓存预算 25 GiB。后续单轮 overlay/日志另占用少量空间，需继续记录实际大小。
- 所有 `/opt` 正本和旧兼容软链接保持原位；重复 raw、ZIP、历史分块与历史临时目录没有恢复。

复制耗时约 1019 秒。过程出现一次单文件 I/O 错误，文件级重试后成功；最终无未完成项。

## 运行与恢复

准备脚本和完成检查脚本：

```bash
cd /opt/data/private/mjh/projects/CoDesk
python3 infra/stage_native_qemu_runtime.py
/tmp/codesk-local-runtime-20261025/python/bin/python3.12 \
  /tmp/codesk-local-runtime-20261025/CoDesk/infra/finalize_native_qemu_runtime.py
```

已有 READY 缓存时，复制脚本保留现有缓存，不把它覆盖成持久目录的旧绝对路径。缓存里的代码是经过记录的运行快照；仓库代码变化后需要在所有本轮进程停止后，显式刷新相应代码并比较 SHA，才能用于下一轮。

启动新的有界 Calc Pilot：

```bash
cd /opt/data/private/mjh/projects/CoDesk
bash infra/run_local_calc_pilot.sh \
  /opt/data/private/mjh/runs/codesk/NEW_UNIQUE_RUN_ID
```

实际结果见 [9 步 Calc 模型 Pilot 报告](DATA_TO_DECK_LOCAL_GUI_PILOT_20261025_ZH.md)：执行链通过，数值答案错误。

本轮实际 run：`data-to-deck-calc-local-pilot-20261025a`。单 Guest、4 vCPU/6 GiB、TCG、最多 10 个真实模型 GUI 工具步。

`CODESK_LOCAL_RUNTIME_ROOT` 使 Pilot 使用以下本地路径：

- `image/base.qcow2`：只读 base 缓存。
- `.native-state-<run_id>`：该轮 overlay、PID、serial 和 ownership manifest。
- `.native-cache-<run_id>`：OSWorld cache。
- `.pilot-staging/<run_id>`：Agent 工作区、CODEX_HOME、MCP 状态、停止标记、截图和日志。
- `venv/bin/python`、`bin/codex`、`qemu/` 和 `CoDesk/`、`OSWorld/`：本地依赖和代码快照。

API key 始终从私有 `/opt` 配置读取，仅传入本轮 relay 环境；不复制配置文件到缓存或 Guest。模型 endpoint 预检在启动阶段进行，运行证据在收尾阶段归档到 `/opt`。这些是保留的明确持久访问。

每轮退出先停止 Agent，再关闭 relay/Guest，核验 PID、overlay 和端口。证据复制后逐文件比对 SHA，通过后才删除该轮临时证据；归档失败则保留本地证据，不能误报已持久化。可复用的 16 GiB 运行缓存保留，以免每轮重复复制大镜像。

## 审计位置

- `/opt/data/private/mjh/runs/codesk/local-runtime-restore-20261025/`：状态、复制清单、导入检查与依赖检查。
- 本地缓存 `ownership.json`、`copy-manifest.json`、`external-links.json`、`status.json`：归属、文件校验、软链接与 READY 状态。
- Pilot 内 `storage-isolation-live.json`：真实 QEMU 的 base 只读 FD、本地 backing 路径和进程映射记录。

删除缓存前必须确认没有 Guest、relay 或 Agent 引用它；只处理这个明确归属的目录。该例外也已写入 `/opt/data/private/mjh/AGENTS.md`，避免再次把活跃运行状态统一迁回 LeoFS。

## 一次读表对照（2026-10-25）

已有默认指令继续保留。可选 `CODESK_CALC_PILOT_INSTRUCTION_VARIANT=verify-source-v1` 仅增加先核验季度标签和最终报告小计的提醒。实际单轮运行已结束，见 [对照报告](DATA_TO_DECK_MODEL_READBACK_20261025_ZH.md)。对照提示不同，不作 baseline Case 成绩；不要为了重复验证基础设施重启 Guest。

## 正确读表/保存子任务闭环已通过

最新 run `data-to-deck-calc-local-pilot-20261025c` 为 PASS_GUI_PILOT，详见 [报告](DATA_TO_DECK_ZOOM_STABLE_PILOT_20261025_ZH.md)。条件 `CODESK_CALC_PILOT_INSTRUCTION_VARIANT=zoom-stable-v1` 会增加 GUI 放大和核验提示，并将真实 HTTP 截图前等待设为5秒（默认1秒）；不修改任务源数据或 Oracle。默认 baseline 和 verify-source-v1 都保留。当前不需要重复运行该子任务，下一步为 Impress 和完整应用链。
