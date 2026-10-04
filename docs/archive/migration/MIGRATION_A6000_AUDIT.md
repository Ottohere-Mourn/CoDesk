# CoDesk A6000 主开发节点迁移审计

**范围：只读资源审计与迁移规划。** 本轮未迁移文件、启动 Guest/模型、安装软件、修改 SSH/系统权限、操作进程/容器、清理资源或运行实验。审计对象为 SSH 别名 `A6000` 指向的主机，以及本地 CoDesk 仓库和其已声明的外部依赖。

## 结论

**当前判定：CONDITIONAL GO。** A6000 的 CPU、内存、根盘空间适合先做单 worker 试迁；采样期间 CPU 约四分之一整机利用率，内存与 I/O 压力较低。但目前 `mjh` 无权访问 Docker daemon，也无权读写 `/dev/kvm`；A6000 未挂载 `/mnt/raid1`，也没有本项目 Qwen 权重。三者均未就绪，因此**目前 NO-GO 于启动真实 OSWorld Guest 和正式实验**。须由管理员按本机政策提供 Docker/KVM 使用方式，或提供已批准的替代运行路径后再做 POC；本审计未请求或修改权限。

单 worker 可在权限问题解决后优先试跑；双 worker 暂列条件可行，先以单 worker 完成 Guest/reset 验收，再测双 worker readiness 尾延迟。Qwen3-VL-30B-A3B 预计能在 3×A6000 上部署，但**当前 GPU 占用使可用显存分布不适合承诺可启动**，且权重/推理环境均未迁移；首轮可保留通过 SSH 隧道调用旧 4090 推理端的备选方案，前提是另行验证服务与网络配置。

## 1. 主机身份与资源审计

### 身份核对

| 项目 | 本地旧节点 | SSH `A6000` 目标节点 | 证据/含义 |
|---|---|---|---|
| 主机名 | `supermicr-EG840G-G20` | `admin123-Super-Server` | 两个不同主机名；没有把旧 4090 与目标机混为一台 |
| 账号 | `mjh`, UID 1002 | `mjh`, UID 1037 | 远端账号 UID 不同；需按新主机路径/权限重新配置 |
| 内核 | 本地环境 | `7.0.0-31-generic` | SSH BatchMode 成功；远端身份来自 `hostname`, `id`, `uname` |
| 网络 | — | 默认路由 `10.130.129.1`，DNS 可解析 `github.com` | DNS/路由可用；本轮未做 Git/HTTP 大文件吞吐测试 |

### A6000 约 61 秒采样

远端通过只读 `/proc`、`/sys`、`lscpu`、`df/findmnt` 采样 7 次，间隔约 10 秒。CPU 利用率由相邻 CPU tick 差计算；I/O 为块设备计数差估算；swap 页计数是系统累计量。样本只代表这 61 秒，不代表全天容量。

| 资源 | 实测 | 解读 |
|---|---|---|
| CPU | Intel Xeon Platinum 8352V，2.10 GHz；2 sockets × 36 cores × 2 threads = **72 物理核 / 144 逻辑线程**；NUMA 2 节点 | 单 Guest 的 4 vCPU 及双 Guest 8 vCPU 在静态容量上不高，但宿主仍有其他租户负载 |
| 频率 | 规格范围 0.8–3.5 GHz；7 次采样的 cpufreq policy 中位读数约 **1.04–2.50 GHz** | 读数有波动，不能等同于每核实际有效频率/持续睿频；当前看到 CPU scaling 不固定 |
| CPU 使用率 | 采样区间约 **25.9–28.5%** | 约相当于 37–41 个逻辑 CPU 时间持续被使用；不是整机空闲 |
| Load average | 1 分钟约 **28.9–35.1**；5 分钟约 **35.3–37.0**；15 分钟约 **44.3–45.2** | 对 144 个逻辑线程不是饱和证据；15 分钟值高于本轮短采样，反映更早的负载水平 |
| CPU PSI | `some avg10` 约 0–0.45%，`avg60` 约 0.31–0.63%；`full` 为 0 | 当前短采样可运行任务的 CPU 等待较低；不保证未来其他租户负载不变 |
| 内存 | MemTotal 263,671,312 kB（约 251.5 GiB）；MemAvailable 214,252,720–214,573,440 kB（约 **204.3–204.5 GiB**） | 双 Guest 各 4 GiB 对宿主可用内存影响小；VM/QEMU/模型服务仍需实测 RSS |
| Swap | 8 GiB 总量，约 3.02 GiB 空闲、约 4.98 GiB 已占用；约 30.5–61 秒窗口 `pswpin` 增 1 页、`pswpout` 不变 | 有历史 swap 占用，但采样窗口内几乎没有换入/换出；不是当前持续 swap 抖动证据 |
| CPU/内存/I/O PSI | 内存 PSI `avg10/60/300` 均为 0；I/O PSI 均为 0 | 本轮未见明显内存或存储等待 |
| 磁盘 | `/dev/nvme0n1p2` ext4，915 GiB 总、301 GiB 已用、568 GiB 可用（约 35% 使用率）；A6000 无 `/mnt/raid1` | 足以容纳初始代码、Guest、运行时及模型的选择性迁移；需要先确认目标目录与配额 |
| I/O | 采样设备 busy 约 0–1.9%；每 10 秒仅少量写入，读入接近 0 | 短采样期间 I/O 不是瓶颈；不能代表正式迁移时吞吐 |

**进程归属（只读统计，不检查命令行或项目内容）：** CPU 计时中，`wky` 账号约占整机 CPU **25.8–28.9%**，约 99 个进程；`mjh` 在这些窗口约 0.01%。其余账号只记录聚合资源，不读取私人目录。GPU 上 3 个计算 PID 的 `/proc` owner 均为数值 UID 1028；只读 `comm` 均为 Python，未检查 argv、cwd 或项目文件。

### Docker、KVM、QEMU、GPU 与存储访问

| 检查项 | A6000 结果 | 对 CoDesk 的影响 |
|---|---|---|
| Docker CLI/daemon | Docker CLI 29.8.1；daemon active，但 `docker version/info` 对当前账号返回 socket `permission denied`。`mjh` 只有自身组，`/var/run/docker.sock` 为 `root:docker 0660`，当前不可读写 | **Guest 启动阻塞**。不尝试加组、改 socket 权限或 sudo |
| KVM | `/dev/kvm` 存在，`root:kvm 0660`；`mjh` 不属于 `kvm`，设备不可读写 | **硬件加速 Guest 启动阻塞**。未改权限/组 |
| QEMU 工具 | `qemu-system-x86_64` 与 `qemu-img` 均未在当前账号 PATH 中发现 | Guest 主要由 Docker runtime 提供；独立诊断/修复 QCOW 的工具路径未就绪，不在本轮安装 |
| GPU | 3× RTX A6000，每张 49,140 MiB；Driver 580.178.04，nvidia-smi 报 CUDA 13.0 | GPU 硬件存在；没有验证 PyTorch/CUDA 推理兼容性 |
| GPU 当前占用 | GPU0：12,874 MiB、34% util；GPU1：39,859 MiB、100% util；GPU2：18 MiB、0% util。对应当前 free 约 36,266 / 9,281 / 49,122 MiB | GPU1 高占用，GPU2 空闲；当前没有足够均匀、可保证的 3 卡空闲显存。未查看进程命令行、容器或归属项目 |
| 挂载/空间 | 可见根盘 ext4 约 568 GiB 可用；`/mnt/raid1` 不存在；`/home` 与项目目标若放根盘将共用同一文件系统 | 不可沿用旧机 RAID1 绝对路径；需批准新路径并参数化 |
| 网络 | 路由存在，`github.com` DNS 解析成功 | 基础 DNS/路由通过；大文件链路速度、SSH 端口转发策略及远程推理连通性未验证 |

## 2. Worker、Guest 与推理容量判断

| 运行形态 | 容量判断 | 理由与准入条件 |
|---|---|---|
| 单 worker / 单 Guest | **条件可行** | 4 vCPU / 4 GiB 的 Guest 远低于整机静态 CPU/RAM 总量；短采样 CPU PSI 和内存/I/O PSI 低。前置条件是 Docker/KVM 经授权可用，并完成单 Guest 冷启动、截图、accessibility、应用 readiness、销毁与 reset 验收 |
| 双 worker（每个各 1 Guest） | **先单 worker、再小规模条件可行** | 两 Guest 共请求 8 vCPU / 8 GiB，内存余量充足；但已有账号消耗约 26–29% 整机 CPU，频率波动，尚无目标机 Guest readiness 历史。先测 5 个单 worker reset 周期，再用相同任务测 2 worker 的 p50/p95 readiness、服务失败和 reset；不因空闲逻辑线程直接放大并发 |
| 一个 MA-ID episode | **单 worker 下条件可行** | 两个独立 Guest 同时活动，至少 8 vCPU / 8 GiB 请求；总 Guest 数必须按 2 计入 worker/宿主上限。按旧性能审计，每个 Guest 启动约 115–140 秒，MA-ID 另有两侧 reset Guest 的启动开销；A6000 上需重测 |
| 双 worker 并行 MA-ID | **暂不建议** | 可同时达到 4 个活动 Guest（16 vCPU / 16 GiB 请求）且叠加宿主其他负载、Qwen 推理 CPU 预处理；只有单 worker/双 worker readiness 稳定、资源调度获批后再测 |
| MA-SD 双 Actor | **单 Guest 容量相对轻** | 两 Actor 共用一 Guest/同桌面，由 Coordinator 串行提交 GUI 动作；资源按 1 Guest 计。它与双 Guest MA-ID 的 Guest 容量不同，调度协议需保持匹配 |
| 后续批量评测 | **未准许估算固定吞吐** | 历史 Guest readiness 中位数约 121–126 秒/次；一次episode会另含清洁 reset Guest，MA-ID 为双活 Guest 且 reset 成本更高。真实环境耗时会由 readiness、应用启动、Qwen 每步推理主导。先获得目标机真实 trace，再从单 worker 估 p50/p95，不能按 144 线程线性外推 |

### Qwen3-VL-30B-A3B

- 旧机权重位于 `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`，目录约 58 GiB；safetensors index 的 `metadata.total_size` 为 **62,141,508,064 bytes**，13 个 shard、882 个 tensor，配置为 `Qwen3VLMoeForConditionalGeneration`，未见量化配置。这是权重文件大小，不是完整运行显存需求。
- A6000 显存物理合计约 144 GiB，理论上三卡部署有可能；但本次 GPU free 分布不均（约 35.4、9.1、48.0 GiB），加上模型激活/KV cache、视觉输入与 CUDA runtime，**当前不应宣称模型可直接加载**。GPU0+GPU2 当前空余合计约 83.4 GiB，理论上可能承载权重和小规模 context，但必须在得到 GPU 使用协调后用原 OSWorld Agent/原配置做一次受控加载验证。
- A6000 权重路径未找到；Transformers/CUDA/PyTorch 版本和三卡并行映射未验证。不得在迁移前启动下载或模型进程。
- 可选回退：原 4090 节点的已有本地推理 worker 采用 loopback/offline 模式。要跨主机使用需经批准配置 SSH 转发/服务监听方式，并确认动作与观察仍由 A6000 Guest 返回、没有改变模型/任务/评测协议；本轮未建立隧道或改服务。

## 3. CoDesk 代码与依赖清单

### 当前状态与版本

- CoDesk 工作树：`/home/mjh/Projects/Shared-Workspace-Benchmark-V0`；branch `v0`，HEAD `69aac16441bfa544419aebc4685a67257c6ad8c8`，相对 `origin/v0` **ahead 8 commits**，Git 工作树干净。
- 仓库约 103 MiB（`.git` 约 35 MiB），384 个 tracked files；`outputs/` 下 189 个 tracked files，约 80 MiB。配置、task registry/Task Factory、evaluator、runner、provenance、测试均在仓库内；应随完整 Git 历史迁移，不单独挑选代码文件。
- 本报告写入前工作树干净；写入后预期只有 `MIGRATION_A6000_AUDIT.md` 新增。没有运行测试，也没有提交或推送。

### 外部运行时、数据与路径

| 项目 | 当前实测/已记录状态 | 迁移处置 |
|---|---|---|
| OSWorld-V2 代码 | `/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1`，约 1.9 GiB；当前 checkout `3d778a3c9a34a079316f70df023b166700445792`；detached HEAD，有 `desktop_env/providers/docker/provider.py` 未提交补丁（50 insertions / 31 deletions） | 记录 base SHA；导出/审阅该单文件 binary diff，纳入新主机独立 patch；不复制开发环境缓存。与 release manifest 的 pinned commit 核对一致后再应用 |
| OSWorld V2.1 Guest | `/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2`；约 14,891,810,816 bytes（13.87 GiB 分配、50 GiB 虚拟容量）；`ENV_SETUP.md` 记录官方压缩包 SHA-256 `14b08aa7…7fc8b3` 与 QCOW `corrupt:false` | **必须**选择性传输/重建；传输后校验 SHA-256、虚拟容量及 OSWorld readiness。源文件不可改写；不转移旧 overlays |
| Docker runtime image | `swcub/osworld-v2.1-qemu-runtime:local`，约 192 MB / 183 MiB，image ID `sha256:002d09fa…f991e82ec`；由 digest-pinned base 构建，官方 OSWorld runtime 当时不可拉取 | 可从 pin 与 Dockerfile 在远端重建（推荐核对包清单/最终 image id）；也可经批准导出/导入该精确镜像并校验 ID。远端目前没有 Docker 权限 |
| OSWorld 外部数据目录 | `/mnt/raid1/mjh/Projects/_deps/osworld-v2.1` 总约 99 GiB，含 Guest、overlays、task-cache | **不要整目录迁移**。只传 Guest base；overlay、临时 cache 可重建。历史 episode overlay 若作为失败证据单独选出并校验，不作为启动依赖 |
| Qwen 权重 | 上述模型 58 GiB | 只有选择本地 A6000 推理才迁移；选择性复制模型目录并比对每个 shard/hash。若先用 4090 远程服务则不传 |
| Python/OSWorld 环境 | 仓库 `pyproject.toml`、`env/requirements.lock`；旧模型解释器默认 `/opt/miniconda3/bin/python`； OSWorld 环境依赖由固定 release lock 安装 | 不复制 `/opt/miniconda3` 整个环境；在授权后用锁文件重建隔离环境，记录 Python/CUDA/torch/transformers 版本。新路径通过环境变量覆盖 |
| Task Factory 与任务资产 | family/template/instance registry、manifest、task/evaluator 在 Git 里，规模很小；OSWorld task-cache 不属于核心任务定义 | 必须迁移 Git；只搬需要的任务样例/固定输入/manifest，cache 可重建；对重生成实例校验 task ID、seed、spec/target hashes |
| 实验报告与结果 | Git 内 `outputs/` 约 80 MiB；`outputs/osworld-v2.1/office`、`browser` 是指向旧 RAID1 artifact 的软链接。RAID 实验根体量见下表 | 必须保全正式结果的原始 `report/events/model trace/screenshots/provenance/resource ledger`，但按 run manifest 选取并去重；在校验前不改/删旧机文件。不要直接复制所有 Guest overlay |
| SSH/凭证 | SSH alias 在本机 config 中可用；远端不挂载旧机 RAID | 不复制私钥、SSH config 密钥材料、token、`.env`、其他项目配置；新主机连接单独依照管理员批准建立，不向仓库写 secret |

本机当前 `/` 约 1.8 TiB 总、182 GiB 可用；`/mnt/raid1` 为 15 TiB NTFS/FUSE，约 1.8 TiB 可用。目标 A6000 只有根盘，约 568 GiB 可用。

### 已发现的机器耦合

脚本、配置默认值中存在 `/mnt/raid1/mjh/...`、`/home/mjh/Projects/...`、`/opt/miniconda3/bin/python`。包括 Guest image、OSWorld repo/cache/overlay、模型权重、artifact root。部分配置已支持 `SWCUB_OSWORLD_GUEST_IMAGE`、`SWCUB_OSWORLD_OVERLAY_HOST_DIR`、`SWCUB_MODEL_PYTHON`、`SWCUB_LOCAL_VLM_PATH`、`SWCUB_LOCAL_VLM_DEVICE`，但默认路径仍需迁移前盘点；不在本审计中改代码。Office/Browser artifacts 使用 symlink，复制时须按 manifest 显式跟随目标路径，不能保留指向不存在 RAID 的断链。

`CODESK_PROTOCOL_V1.md` 已规定 MA-ID 与 MA-SD 共享同一 authoritative backend、seed/schedule/evaluator，仅桌面会话拓扑不同。但 registry 明确记载历史 Writer+Calc MA-ID 是每个 Actor 单独 Guest/workspace、MA-SD 共一个 Guest，导致 backend identity 混杂；**同 backend MA-ID/MA-SD 目前 design-only，尚未实现/验证**。迁移不能复刻旧拓扑并声称满足协议；必须先实现/验收相同 backend 绑定，再做新对照。旧结果保持原样并标为旧拓扑证据。

## 4. 数据量估计与选择原则

以下是目录 `du` 观测值，非迁移承诺；旧 artifacts 可能包含重复截图、临时文件或 Guest overlays，最终传输量需按 manifest 去重后生成清单。

| 数据集合 | 当前占用 | 计划 |
|---|---:|---|
| Git 仓库（含历史） | 约 103 MiB | Git bundle/sync，含 branch `v0` 的 8 个本地提交 |
| OSWorld checkout | 约 1.9 GiB | 远端按精确 commit clone；只携带 81 行改动补丁 |
| Guest base QCOW | 约 13.87 GiB 分配 | 作为首个 Guest 唯一大型必需资产传输并校验 |
| runtime image | 约 183 MiB | 可重建；如导出传输则校验 digest |
| Git 内 outputs | 约 80 MiB | 已随 Git；断链目标另按所需文件迁移 |
| Qwen 30B 权重 | 约 58 GiB | 本地推理才需要；远程模型服务路径可不复制 |
| 旧 RAID 实验目录 | `Shared-Workspace-Benchmark-V0-artifacts` 14 GiB；CoDesk V1 的 experiments 616 MiB、track-a 18 GiB、parallel-pilot 4.2 GiB、real-app-track-a 57 GiB、real-dual-agent-eval 844 MiB、v2 6.2 GiB | 合计约 101 GiB 原始目录体量上界（约 14 GiB + 86.9 GiB）；只选正式 run 的原始证据/报告，overlay 与缓存不迁；先检查 manifest 与文件哈希避免重复 |
| OSWorld data/overlay/cache 整体 | 约 99 GiB | 不整包迁；绝大多数可重建或不属于必需运行依赖 |

**最小可启动数据预算约 17.2 GiB**（仓库 0.1 + OSWorld 1.9 + QCOW 13.87 + runtime 0.18 + 少量清单），不含 Python 环境、选取的结果和 staging 临时空间；**加本地模型约 75 GiB**。若未经筛选搬迁全部历史 artifact，上界约 119 GiB（最小运行资产加约 101 GiB 旧结果）；如再加 Qwen 约 177 GiB。A6000 现有 568 GiB 可用空间足够容纳上述选择方案，但应预留 Guest overlays、Docker layers、模型运行缓存及系统空间，建议首阶段目标盘占用不超过 150 GiB，并按独立项目目录设配额/监控（不得改系统级配置而未获批准）。

## 5. 最短可行迁移与验收

实际迁移属于后续操作，本轮未执行。开始前需明确目标目录、Docker/KVM授权路径、GPU分配，以及历史 artifact 选择范围并获用户确认。建议按下列门槛递进：

### A. 远端基础环境与权限

1. 再核对 `hostname`、`id`、CPU/内存/磁盘及 GPU 进程占用；确认 SSH 仍指向 `admin123-Super-Server`。
2. 由管理员/资源所有者确认 Docker daemon 的授权运行方式和 `/dev/kvm` 可访问方式，不改共享权限、不借用他人容器。确认目标目录（如经批准的 `/home/mjh/Projects/CoDesk`）与数据保留策略。
3. 确认本地到目标的 SSH 文件传输路线、Git 可达性、有效带宽和 GPU 调度窗口。GPU 上其他任务未获授权时，不使用/中断它们。

**通过标准：** `mjh` 能按授权方式查询和创建带 CoDesk ownership label 的单个测试 runtime/Guest，能访问 KVM；网络、磁盘和资源归属留有记录。权限不通则停止 Guest 阶段。

### B. 迁移代码与最小 Guest

1. 通过 Git bundle 或经批准的私有 Git 同步完整 `v0` 历史（含 8 个 ahead commits）；核对 HEAD 和工作树，不在公共 remote 暴露未审代码。
2. 在远端按 OSWorld 固定 SHA `3d778a3c…445792` 准备 checkout；从旧 checkout 单独导出审阅过的 provider patch，记录 patch SHA，避免把整个环境状态误当源码。
3. 复制 Guest QCOW 到新项目数据目录，用源发布 SHA/目标 SHA-256、大小和 QCOW metadata 复核；runtime image 按 pin 重建或核对已导出 image ID。
4. 建立项目隔离 Python 环境，按锁文件安装；不复制整套 Conda，也不下载 gated assets。
5. 将 Guest/image/OSWorld/artifact/cache 根路径由环境变量指向经批准目录。初期不搬模型和大体量历史 artifacts。

**通过标准：** 固定 commit、patch、lock、Guest hash、image digest、路径配置均写入 provenance；`docker info`、KVM 访问、Guest screenshot/accessibility、Guest CLI、Writer/Calc readiness 均通过。

### C. Writer+Calc scripted Solo / reset

在一个新 Guest 上分别启动指定 Writer 文档和 Calc 工作簿，检查活动窗口、初始内容/单元格、可交互性、保存持久化；运行两个 scripted Solo、程序化评分、reset。保留截图、日志、event provenance、reset oracle。

**通过标准：** 两 actor solo 目标可达；环境失败单列，不混成任务失败；reset 后初始状态哈希/干净 Guest 校验通过。不得只看窗口已启动。

### D. 接入原 Qwen3-VL

先确定模型路径策略：经批准传权重至 A6000，或从 A6000 经受控 SSH 转发调用原 4090 loopback worker。固定 Agent、权重/config hash、依赖、解码参数、action budget；先 Writer/Calc 各 1 次 Solo。不得训练或替换 planner。

**通过标准：** 截图输入、模型动作、OSWorld 执行动作、目标文件实际改变、evaluator/provenance 完整；模型失败、环境失败分别记账。双 Actor 有独立 history、budget、actor/run ID。

### E. Solo / MA-ID / MA-SD 对照

先修复并验收同一 authoritative backend 的 MA-ID adapter：独立桌面/input/clipboard 会话，但相同 workspace/backend 实例及初始 state。之后对配对任务运行 Solo、MA-ID、MA-SD，冻结 task seed、目标、Agent、schedule、预算、evaluator。MA-SD 两 Actor 使用同一真实 Guest；Coordinator 串行提交 GUI 操作，保留各自观察与动作历史。计数器中 MA-ID 两 Guest 均计入活动 guest 限额。

**通过标准：** 各条件 topology manifest 可证明 backend identity 与 desktop/session identity；reset/provenance/evaluator 完整；旧拓扑结果不覆盖、不混并。

### F. 切换 A6000 为主开发节点与回滚

所有验收通过并由用户确认后，将日常开发分支/实验根迁至 A6000。旧 4090 保留当前提交、OSWorld 源码/patch、模型、Guest base 和 artifact 的只读/冻结副本；切换期明确唯一写入主机，避免双端同时写同一 artifact。稳定一段预定周期后再决定是否清理旧机（清理需另外审批，不能由此计划自动执行）。

**回滚：** 暂停新实验，保存 A6000 原始日志/状态但不删除；将唯一写入主机切回冻结的 4090 版本；校验最后一个已验收 checkpoint 和 artifacts。若需把 A6000 新产物带回旧机，按 manifest/哈希选择性回拷，不同步覆盖任何旧结果。

## 6. 风险与迁移准入门槛

1. **权限是当前硬阻塞：** Docker/KVM 对 `mjh` 不可用。未获准替代方案前不做安装或 Guest 尝试。
2. **竞争资源与 GPU 可用性：** CPU 采样约 26–29% 忙；GPU1 100% busy。正式预约 GPU 前须确认 owner/时间窗；不通过查看其私人项目或操作进程解决。
3. **NUMA/跨卡拓扑：** 双路 NUMA + 3 GPU 的 PCIe/NVLink、拓扑及亲和性未审。Qwen 跨卡传输性能与 Guest CPU 可竞争，必须在隔离窗口实测。
4. **存储迁移：** 旧机 RAID1 为 NTFS/FUSE，新机为 ext4；权限、稀疏文件/overlay、mtime、软链接语义可能变化。QCOW 和 artifacts 用 SHA 清单验证；不复制 FUSE 元数据并假设语义一致。
5. **路径耦合和模型配置：** 环境变量已有部分支持，但不少默认值写死旧 `/mnt/raid1` 和用户路径。要逐条用新目录 dry-run 展开并固化配置，而非全局文本替换。
6. **MA-ID/MA-SD 后端混杂：** 同 backend MA-ID 尚未实现/验证，是论文对照有效性的门槛，与机器迁移是两个独立问题；不可通过迁移掩盖。
7. **并行吞吐：** 历史 readiness 约 2 分钟/Guest，两个 worker 并不保证两倍吞吐；Guest 启动序列、应用启动、模型推理和 reset 影响 p95。先建立新机基线再逐级增 worker。

## 7. 审计证据边界

- **直接观察：** 两机不同 hostname/UID；A6000 60 秒 CPU/PSI/swap/I/O采样；远端 Docker socket 与 KVM 权限；GPU 型号、显存使用与 compute PID 的 UID/comm；远端根盘及挂载；Git 状态；本地文件/目录大小、软链接、OSWorld checkout commit/patch 状态；本地 Qwen 权重 index 元数据。
- **来自已有项目记录、非本轮复跑：** Guest QCOW 历史完整性和哈希、旧机 Docker/Guest readiness、115–140 秒启动记录、模型 Agent 历史接口与成功 smoke、脚本所设 4 vCPU/4 GiB、实验输出完成状态。
- **尚未验证：** A6000 上任一 Guest、Docker 容器创建、QEMU runtime、A6000 Writer/Calc、PyTorch/CUDA 推理、Qwen 模型装载、多卡通信、SSH 隧道、模型与 Guest 并行吞吐、迁移后的 same-backend MA-ID。
- **没有做：** 读取其他账号项目目录、检查其命令行或容器内容、停止任务、改权限、复制/删除任何数据、启动实验。


## Migration execution addendum (2026-09-30)

The original document above is the pre-migration read-only audit. Follow-up asset transfer, environment setup, offline tests, blockers, same-backend implementation status and the next-day single-worker acceptance sequence are recorded in MIGRATION_PROGRESS.md. In brief: core Git/OSWorld/QCOW/runtime assets were copied and hashes checked; 117 non-Guest tests pass; the target still lacks Docker/KVM access; Qwen weights were not copied because source SSH timed out; no Guest or model inference was run. Do not treat earlier proposed migration items as evidence of completed Guest acceptance.

### Transfer correction (2026-09-30)

The earlier audit's model-transfer statement was a snapshot before the source RAID mount became available. The Qwen3-VL-30B-A3B-Instruct directory has since been copied read-only to `/home1/mjh/Projects/CoDesk-V0-A6000/models/Qwen/Qwen3-VL-30B-A3B-Instruct` using a single rsync stream capped at 8 MiB/s. Source and target SHA-256 manifests cover all 26 files, including 13 weight shards; `sha256sum --check` passed all entries. The official OSWorld V2.1 Guest ZIP archive is currently being copied, separately from the already verified raw QCOW. This corrects only migration status; it does not change the original resource or capacity audit.

### Final migration status addendum (2026-09-30)

The model and official Guest archive transfers are now complete. Qwen weights are copied and every file SHA-256 matches the source manifest. The Guest ZIP matches the pinned OSWorld V2.1 release SHA-256 and contains the expected QCOW member. `scripts/verify_a6000_assets.sh` exits 0 for all migration manifests. User-level environments and CPU-only Qwen config/processor loading pass. The A6000 still cannot run a Guest: Docker daemon permission and `/dev/kvm` access are unavailable to `mjh`. No image/container/Guest operation or GPU/model inference was attempted. See `MIGRATION_PROGRESS.md` and `../snapshots/a6000-validation/` for the detailed evidence and acceptance steps.

## Post-audit update — permissions restored and single-worker smoke completed (2026-09-30)

This is a later operational update; the resource values and permission denials above describe the original read-only audit snapshot. At the time of this update, account `mjh` is in `docker` and `kvm`; Docker daemon and `/dev/kvm` read/write checks pass. The project runtime image was prepared without overwriting the migrated `:local` image. One scripted Writer/Calc paired-Solo Guest smoke then passed on A6000 with exact application state, complete provenance/artifacts, 1/1 reset, and all four run-owned Guest containers destroyed with ledger records. The first bootstrap failure remains separately preserved. See `MIGRATION_PROGRESS.md` for the run ID, exact artifact path, timings, regression tests, and the runtime tag precedence correction. No model inference was started.
