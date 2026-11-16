# paraGUI 当前服务器方案：CPU15（2026-11-13）

**新任务默认使用 `cpu15`，数据放 `~/data/paraGUI`。** `cpu10` 已宕机，本次 SSH 探测超时；恢复后只按需读取历史结果，不作为新任务默认目标。下面的 VM10 方案仅保留作历史记录，其中旧路径、sudo 安装步骤和管理器脚本不适用于新机器。

## 当前连接与存储

从开发机复用已有跳板配置，密钥留在原位置：

```bash
ssh -T -o BatchMode=yes gpu48-jump 'ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes cpu15 hostname'
ssh -tt gpu48-jump 'ssh -tt -o StrictHostKeyChecking=yes cpu15'
# GPU 按需使用：在跳板机执行 ssh g4-45
```

| 项目 | CPU15 实测 | GPU g4-45 实测 |
| --- | --- | --- |
| 主机 | `yifan-cpu-scus-15` | `t2vg-a100-G4-45` |
| 用户/权限 | `yuke`；无 sudo；rootless Docker | 无 sudo；rootless Docker |
| 数据位置 | `~/data` → `/data-premium/users/yuke`，4T 盘，约 3.2T 可用 | `~/data` 位于本地 NVMe，约 736G 可用 |
| 资源 | 32 逻辑 CPU、125 GiB RAM；用户可读写 `/dev/kvm` | 4 × A100 80GB；每张约 24 GiB 显存可用 |
| Docker 数据 | `/data-premium/users/yuke/docker` | 使用该用户现有 rootless daemon |

GPU 数据盘在停机或迁移时可能丢失，重要产物及时复制回 CPU15 和开发机；需要整卡时再向机器提供者申请。本项目目前使用远端模型 API，无需占用 GPU。

## 新工作目录与运行配置

- 代码：`~/data/paraGUI/CoDesk`。
- 任务素材、镜像、覆盖层、结果和归档：`~/data/paraGUI/{assets,images,overlays,runs,archives}`。
- 新配置模板：[env.cpu15.example.sh](../configs/env.cpu15.example.sh)。在 CPU15 上 source；不使用旧 `env.vm10.example.sh` 或只支持 VM10 的 `remote_cpu/vm10.py`。
- 专业软件/Astra 独立 runner 不读取全部 `OSCOMBO_*` 配置。运行时显式传 `--code-root "$OSCOMBO_ROOT/CoDesk"`、`--out "$OSCOMBO_RUNS_ROOT/<新批次>"`、`--api-json <受保护凭据路径>`、`--codex-bin "$OSCOMBO_ROOT/runtime/codex/codex"`；Astra 初次只用 `--workers 1`。
- `experiments/codesk_container_codex.py` 的二进制默认值仍指向历史 CPU10 路径，必须使用上述 `--codex-bin` 覆盖。历史实验文件中的 CPU10 路径保留用于追溯。

本次迁移先保存工作树、已同步结果和恢复记录。CPU15 初次检查时没有 Docker 镜像或运行容器，也没有 `qemu-system-x86_64`；**源码迁移不代表实验运行环境已就绪**。后续运行前需恢复/重建 `paragui/professional-rootless:20261103`、`paragui/weavebench-pairs:20261103`、`paragui/astra-race-desktop:20261111` 及容器内 Codex 二进制；19-case OSWorld 实验还需要 QEMU 和 Guest 镜像。软件版本应与历史记录匹配并做 smoke 验证。

## 延续的运行约束

- 不在 CPU/GPU 宿主启动实验 Codex；宿主和 Docker 内都禁止 YOLO、`danger-full-access` 和等价沙箱绕过。智能体只在隔离 rootless Docker 内运行，保留权限审计。
- Full GUI+CLI 使用 `workspace-write` + `approval_policy="never"`，现有 GUI/CLI MCP 工具设为 `approve`。每个实验智能体容器只读挂载 [codex.requirements.toml](../configs/codex.requirements.toml)，限制只可选择 `read-only` / `workspace-write`。详情见 [Codex 配置记录](CODEX_SANDBOX_POLICY_20261113.md)。
- Full GUI+CLI 无锁臂沿用既有容器边界；不把宿主 Docker socket 或凭据挂进智能体容器。
- 长批次用持久进程并逐任务落盘；用户要求的实验监控间隔为 **10 分钟**，不恢复高频轮询。
- 每个阶段复制结果到开发机并校验 SHA-256。CPU15 同盘归档只是本机副本。
- 恢复会话先读 [恢复核对记录](RECOVERY_20261113.md)，按需提取旧 JSONL；不要把完整历史、截图或长日志灌入上下文。

---

# 历史方案：VM10（已停用，仅供追溯）

桌面实验、任务构建和评测统一放在 **VM10**；开发机负责代码修改与结果查看，模型通过 VM10 可访问的
API 调用。需要自部署模型时再使用 GPU 节点。VM10 的项目数据落在 `/data`，结果另做显式异机备份。

依据：开发机上的 [CPU_NODE.md](/home/v-yukezhao/code/GPU_node/CPU_NODE.md)（实际位置为
`~/code/GPU_node/CPU_NODE.md`），以及 2026-10-23 的只读登录核验。本方案中的目录和安装命令是待部署配置；
本次只核验了宿主机，没有创建项目目录、安装软件或启动实验容器。

## 机器分工与连接

| 位置 | 职责 |
| --- | --- |
| 当前开发机：`/home/v-yukezhao/code/paraGUI/CoDesk` | 开发、离线测试、生成实验清单、查看结果 |
| `gpu48-jump` / `jump-machine` → `cpu10` | SSH 转接；使用跳板机受管逐机密钥 |
| VM10：`yifan-cpu-wus3-10` | 运行 oscombo、Docker/QEMU Ubuntu Guest、任务评分与结果归档 |
| 模型 API / 按需使用的 GPU 推理服务 | 接收截图并生成动作；端点须从 VM10 连通 |

VM10 是共享 CPU 服务器：32 个逻辑 CPU，约 125.7 GiB 内存，已有 WeaveBench、Judge 及其他容器工作负载。
VM10 使用独立的连接路径，单独检查 CPU、内存和磁盘负载；`gpu48 top` 不包含它。

### 当前连接（2026-11-03 04:53 UTC 只读核验）

从开发机使用 `gpu48-jump`，在跳板机使用受管的 `cpu10` 别名：

```bash
ssh -T gpu48-jump 'ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes cpu10 hostname'
# yifan-cpu-wus3-10
ssh -tt gpu48-jump 'ssh -tt -o StrictHostKeyChecking=yes cpu10'
```

脚本执行也可复用现有管理器主连接；本次同样实测成功：

```bash
printf 'hostname\n' | python3 /home/v-yukezhao/code/mini-harness/remote_cpu/vm10.py --timeout 30
```

密钥/地址的当前来源都在跳板机，不要在任务脚本中硬编码历史私钥：

- SSH 别名：`~/.ssh/config.d/yifan-vms.conf`，`cpu10` 自动选择其配置的逐机 IdentityFile。
- 管理器清单：`~/zisu/cpu-vm-manager-bridge/machines.json` 的 `vm10` 项。
- 本次两处指向同一逐机密钥：`~/.ssh/fleet-keys-20261026/yifan-cpu-wus3-10/id_ed25519`。
  这是当前核验值，不是应永久固定的路径。跳板记录显示该逐机密钥于 2026-10-27 同步；
  本次确认了受管密钥配置及成功认证，尚未定位自动轮换的调度脚本或周期。
- `vm10.py` 动态查找 `~/.ssh/cpu-vm-manager-control/vm10-*` 中仍存活的主连接；
  失效时明确失败，不自动回退到旧密钥认证。`cpu10` 别名本身已通过独立新认证。

**外层 `gpu48-jump` 当前依赖存活的 SSH 主连接。** 新建外层连接仍报公钥认证失败，
不要为了重试而关闭现有主连接。旧 `gcr492` 本地转发端口失效、旧
`~/.ssh/yifan-cpu-vm` 路径和本机直连失败，都不能单独据此判断 CPU 离线。
密钥只在原位置使用，不复制私钥到开发机，不调整 VM/宿主机的 Codex 权限。

## 存储布局

项目根目录规划为 `/data/yuke/paraGUI`。本次核验时 `/data/yuke` 属于 `root:root`，登录用户 `yifan`
不可写，项目根目录尚不存在。部署时先由有权限的账号创建并授权**这个项目目录**：

```bash
sudo install -d -o yifan -g "$(id -gn yifan)" -m 0750 /data/yuke/paraGUI
```

| 项目路径 | 内容 |
| --- | --- |
| `CoDesk/` | 当前 `yuke-osworld` 工作树，包含本方案与 VM10 配置模板 |
| `bootstrap/` | 安装 `uv` 的独立 Python 环境 |
| `OSWorld-V2/` | 本项目专用的 OSWorld checkout 与 `.venv`，由安装脚本固定版本 |
| `images/` | 原始 Guest 镜像、下载包及需要时生成的 pngfast 镜像 |
| `overlays/` | 每个 Guest 的可写磁盘覆盖层 |
| `assets/`、`base/` | paraGUI 任务素材、标准答案和 Thunderbird 基础配置 |
| `runs/` | 每次实验的评分、轨迹、截图、独立任务缓存和日志 |
| `lists/` | 本批次实际使用的任务与实验清单 |
| `archives/` | 本机打包暂存，随后复制到异机或 Blob |

`/data` 位于 `/dev/sda1` 的 ext4 文件系统。2026-10-23 核验时约剩 439 GiB，可用空间会随其他任务变化；
首次部署先为镜像下载包、解压镜像、Python 环境、覆盖层及少量结果预留约 100 GiB，再按实测增长量调整。
Docker 已使用 `/data/docker`；沿用现有 daemon，项目镜像使用 `oscombo/qemu-runtime:local` 名称。

CPU 的 `/data` 与 GPU 的 Blob 挂载相互独立。VM10 没有 `/blob`、`/datasets` 或 `/output` 挂载。
GPU 上 `/output` 对应存储账号 `yifanyang` 的 `exps` 容器；若选用该位置归档，目标可规划为
`exps/paragui/<批次>/`，但需要另外配置并验证 VM10 的 Blob 访问凭据。把文件写入本机 `archives/`
只完成了本机归档。

## 宿主能力与资源预算

只读核验结果：Docker daemon 可访问，版本为 29.1.3；宿主存在 `/dev/kvm`，权限为 `root:kvm 0660`，
`yifan` 不在 `kvm` 组且不能直接读写该设备；非交互 PATH 和常见用户安装路径中未找到 `uv`。
**容器内 KVM 是否可用仍需验证**：[固定版本的 OSWorld provider](https://github.com/xlang-ai/OSWorld-V2/blob/3d778a3c9a34a079316f70df023b166700445792/desktop_env/providers/docker/provider.py#L128)
在设备存在时将它传入 Docker，宿主登录用户的
直接访问权限不能单独决定容器能否使用 KVM。

| 场景 | 初始设置 | 实际 Guest 数 |
| --- | --- | --- |
| 首次安装、smoke、两任务的 solo / sequential / parallel / shadow | 每 Guest 8 vCPU、8 GiB；`--lanes 1` | 最多 1 |
| 两任务的 isolated 对照 | 相同 Guest 配置；单独队列，`--lanes 1` | 最多 2 |
| 已验证稳定的共享桌面批次 | 可尝试 `--lanes 2`，同时观察其他工作负载 | 最多 2 |

`queue --lanes` 限制的是 **run 数**，不是 Guest 数；一个包含 N 个任务的 `isolated` run 会启动 N 个 Guest。
多队列同时运行时，各队列的上限会相加。因此起步阶段只运行一个队列，isolated 与其他模式分批。
8 vCPU 是 Guest 配置，不是宿主 CPU 用量的硬上限；扩容以宿主负载、截图延迟和 INFRA 错误为依据。
原有运行笔记中的“96 核宿主约 6 个 TCG Guest”只适用于当时的机器。

使用 [VM10 配置模板](../configs/env.vm10.example.sh)。默认保留 30 分钟启动等待、300 秒截图等待，
每个 agent 的运行上限为 7200 秒，queue 的单次 run 上限为 21600 秒。后者为双任务 sequential 的两个
agent 及启动、setup、评分留出时间；超过两个任务时需重新预算。

## 部署步骤

以下除明确标注外均在 **VM10 内**执行。先完成项目目录授权，并将本次本地工作树同步至
`/data/yuke/paraGUI/CoDesk`，包含 `configs/env.vm10.example.sh`。可通过已提交的 Git 版本同步；未提交的
改动则打包当前工作树逐跳复制，保留 Git 元数据，并排除 `.venv/`、`env.sh`、运行结果及缓存。
复制后记录 `git rev-parse HEAD` 与 `git diff`，使本地修改也能追溯。

1. 检查宿主和存储，创建项目子目录。

   ```bash
   hostname
   uptime
   free -h
   df -h /data
   findmnt -T /data -o TARGET,SOURCE,FSTYPE
   docker info --format 'Docker={{.ServerVersion}} Root={{.DockerRootDir}}'
   export OSCOMBO_ROOT=/data/yuke/paraGUI
   mkdir -p "$OSCOMBO_ROOT"/{images,overlays,assets,base,runs,lists,archives}
   cd "$OSCOMBO_ROOT/CoDesk"
   cp configs/env.vm10.example.sh env.sh
   chmod 600 env.sh
   source env.sh
   ```

   `env.sh` 已被 Git 忽略。上面的复制用于首次配置；已有配置时合并新增项。模型端点和密钥在此文件或调用
   环境中设置。模型推理请求由 VM10 上的 harness 发出；端点里的 `127.0.0.1` 指 VM10。

2. 准备 `uv`，安装本项目的 OSWorld 环境。

   ```bash
   python3 -m venv "$OSCOMBO_ROOT/bootstrap"
   "$OSCOMBO_ROOT/bootstrap/bin/python" -m pip install uv
   uv --version
   bash infra/setup_osworld.sh
   ```

   宿主需具备 Python venv 支持；若缺少，先安装系统对应的 `python3-venv` 包。安装脚本使用 `git`、`curl`
   和 `unzip`，固定 OSWorld `osworld-v2.1` / `3d778a3c9a34a079316f70df023b166700445792`，下载并校验约 15 GB
   的压缩镜像，然后只修补本项目的 OSWorld checkout。外部 MCP harness 额外使用 `--with-mcp`；官方受限
   v2 任务才使用 `--with-v2-tasks` 并配置 `HF_TOKEN`。paraGUI 自带任务通过下一步安装。

3. 构建运行镜像，验证容器内 KVM。

   ```bash
   bash infra/build_runtime.sh
   docker run --rm --device /dev/kvm --entrypoint bash "$OSCOMBO_RUNTIME_IMAGE" -lc '
     timeout 3 qemu-system-x86_64 -accel kvm -machine q35 -nodefaults -display none -monitor none -serial none -S
     probe_status=$?
     test "$probe_status" -eq 124
   '
   ```

   探测期望 QEMU 成功初始化后等待，由 `timeout` 结束；设备或 KVM 初始化错误会让命令失败。通过后使用
   模板中的原始镜像。此探测不会启动任务桌面，实际启动和截图由下一节的 smoke 验证。

   如果探测失败，先确认设备透传、daemon 权限和宿主的虚拟化支持。当前 provider 只按 `/dev/kvm` 是否存在
   决定透传，仓库没有强制关闭透传的配置项；不能仅改镜像路径就宣称已切换 TCG。在确认容器不暴露可用 KVM
   的部署路径后，按 [No KVM 步骤](../README.md#setup) 构建 pngfast 镜像并更新 `OSCOMBO_GUEST_IMAGE`。
   TCG 初始仍用单 run，单独测量性能后再扩容。

4. 安装首个 paraGUI 任务对，并运行离线测试。

   ```bash
   uv pip install --python "$OSWORLD_DIR/.venv/bin/python" -e '.[test]'
   python -m pytest -q
   python -m oscombo tasks install --pairs w1
   python -m oscombo tasks list
   ```

   `tasks install` 会构建素材并准备 Thunderbird 基础配置，需能下载相关公开文件。先验收 W1，再为所选
   批次安装其他任务对。同一批次沿用同一次素材构建的 `expected.json`；生成的 PDF 带构建时间戳，重新生成
   素材会改变文件校验值。

## 从 smoke 到正式实验

先运行无模型的真实 Guest smoke。它验证启动、setup、截图、评分和关闭；scripted agent 只声明 DONE，
低任务分数属于预期，检查重点是日志、图片和基础设施错误。

```bash
source env.sh
OSCOMBO_RUN_LABEL=vm10-smoke-w1 python -m oscombo run \
  --mode parallel --policy scripted --max-steps 2 \
  --tasks v2/pgw1reply v2/pgw1triage --out "$OSCOMBO_RUNS_ROOT/vm10-smoke-w1"
```

随后在 `env.sh` 填写 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OSCOMBO_MODEL` 和 `OSCOMBO_POLICY`。
`openai-cua` 要求端点支持原生 computer tool；兼容的自部署视觉模型可按项目接口选择 `chat-pyautogui`。
先跑 W1 的小矩阵：2 次 solo、2 个顺序的 sequential、2 个顺序各重复 2 次的 parallel，共 8 次 run。

```bash
source env.sh
: "${OPENAI_BASE_URL:?configure the endpoint in env.sh}"
: "${OPENAI_API_KEY:?configure the credential in env.sh}"
: "${OSCOMBO_MODEL:?configure the model in env.sh}"
: "${OSCOMBO_POLICY:?configure the policy in env.sh}"
batch="vm10-w1-$(date -u +%Y%m%dT%H%M%SZ)"
printf '%s\n' 'w1 v2/pgw1reply v2/pgw1triage' > "$OSCOMBO_ROOT/lists/$batch.combos.txt"
python -m oscombo matrix "$OSCOMBO_ROOT/lists/$batch.combos.txt" \
  --prefix "$batch" --mode sequential:1 --mode parallel:2 --solo 1 \
  > "$OSCOMBO_ROOT/lists/$batch.runs.txt"
python -m oscombo queue "$OSCOMBO_ROOT/lists/$batch.runs.txt" \
  --out-root "$OSCOMBO_RUNS_ROOT" --lanes "$OSCOMBO_QUEUE_LANES" \
  --stagger "$OSCOMBO_QUEUE_STAGGER" --run-timeout "$OSCOMBO_RUN_TIMEOUT" \
  --archive "$OSCOMBO_ARCHIVE_DIR" \
  -- --policy "$OSCOMBO_POLICY" --model "$OSCOMBO_MODEL" --max-steps 150 \
  --opt chain_steps=40 --opt wall_s=7200
python -m oscombo analyze "$OSCOMBO_RUNS_ROOT" --prefix "$batch-" --threshold 0.8
```

长队列在 VM10 的 `tmux` 会话内运行。`OSCOMBO_QUEUE_LANES` 等变量是本方案的 shell 便捷项，上述命令显式
传给 CLI；只设置变量不会改变 `queue` 的默认值。先检查 smoke 和 solo 的实际产物，再接受其余结果。
CLI 的退出码不能代替结果检查，应读取 `result.json` 中的 `error`、`eval_errors`、`scores` 和 agent 状态。

扩展时按任务族分批。完整 v1 清单有 29 对任务，按上述次数会生成 232 次 run；攻击轮清单有 6 对任务，
会生成 48 次 run。新增防护条件使用新批次名与一致的模型、素材、步数预算；`--defense v1` 用于 `step`
harness 的 shared-Guest 模式，isolated 单独跑无防护对照。

## 结果保存、监控与恢复

每批保留 `result.json`、`trace.jsonl`、截图、driver/queue 日志、实验清单、代码提交及本地 diff，另外记录
模型端点与模型名称、KVM/TCG 模式、Guest 资源和镜像校验值；配置记录排除密钥。
`queue --archive` 在整份清单结束后打包该清单的运行目录，长批次还需阶段性复制已结束的 run。
任务清单、素材的 `expected.json`、代码差异和 `_infra/` 中的失败尝试另行保存。

用现有多跳链路将归档复制回开发机，或通过配置好的 Blob 客户端写入 `exps/paragui/<批次>/`。
在目标端校验文件大小和 SHA-256 后，再决定本机结果的保留期限。VM10 上的归档与源结果在同一块磁盘上，
不计作异机备份。

运行时在 VM10 检查 `uptime`、`free -h`、`df -h /data`、本项目容器的 `docker stats`，以及
`runs/queue_<清单名>.log`。扩容重点看启动时间、截图等待、磁盘增长、INFRA 错误及其他项目的负载。
queue 会跳过已有 `result.json` 的 run，并对其识别的基础设施失败补跑一次；模型失败与评测异常仍需查看记录。
恢复同一批次时复用原清单，不重新生成时间戳批次名。

终止实验后按具体 run 名清理，例如清理上面的 smoke：

```bash
python -m oscombo cleanup vm10-smoke-w1
```

清理范围限于本项目的容器标签、已结束 run 的覆盖层及已备份结果；共享 daemon 上其他项目的容器、镜像和
`/data/zisu/cua-env-scaling/` 下的现有环境继续由其各自项目管理。
