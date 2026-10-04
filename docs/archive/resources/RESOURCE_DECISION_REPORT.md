# CoDesk resource decision report

采样时间：2026-10-02 10:45–10:46（Asia/Shanghai）  
审计方式：4090 本机只读；A6000 通过既有 SSH alias 只读。未启动模型/Guest，未停止或改动任何其他进程、容器或文件。

## 决策

**恢复路线仍选 4090 做 Qwen inference、A6000 做 Guest/coordinator；但当前不能启动 endpoint。** 4090 的 CPU 已恢复，且这条原路线有一次真实 Writer Solo 通过记录。当前实际阻塞转为 GPU 显存和 4090 可用内存：4090 的 8 张卡都有大量显存分配，15485 端口没有 worker；4090 `MemAvailable` 约 36 GiB 且 2 GiB swap 已满。不能安全重启现有双卡 worker，也不能以“GPU utilization 为 0%”推断已释放显存。

A6000 当前也没有可确认空闲的双卡组合：三张卡均有进程占用，CPU PSI 比 4090 高，且没有 Qwen worker/tunnel。现在转去 A6000 不会更快，反而回到已知双卡 `generate()` 未返回的问题。因此暂停两边的模型启动，等待/预约 GPU 容量；不检查或干扰占卡任务。

## 4090 资源快照

Host：`supermicr-EG840G-G20`；80 个逻辑 CPU。

| 项目 | 观测 | 判断 |
|---|---:|---|
| Load average | 1 / 5 / 15 分钟：1.04 / 1.70 / 1.99 | CPU 当前空闲 |
| CPU PSI | `some avg10/60/300 = 0/0/0%`；`full=0` | 无可见 CPU pressure |
| `vmstat` | 两个样本 run queue 1→0，CPU idle 75%→99%，swap-in/out 均为 0 | CPU 已恢复 |
| RAM | 251 GiB 总；`MemAvailable` 38,222,792 kB（约 36.5 GiB） | 不算宽裕 |
| Swap | 2 GiB 总，约 2 GiB 已用，空闲约 164 KiB；采样期间无 swap-in/out | 历史 swap 占用仍在，尚无当前抖动证据 |
| GPU 显存 | 8× RTX 4090；已用约 27.5–45.4 GiB / 卡（49,140 MiB 总） | 没有可确认的双卡空闲组合 |
| GPU 利用率 | 本次快照均为 0% | 不代表显存/设备已释放；不据此启动模型 |
| CoDesk/Qwen | 无本项目 worker、vLLM、容器或 15485 listener；`/health` 连接被拒绝 | 当前不存在可复用的活动 endpoint |

4090 的 GPU compute 进程表显示显存由正在运行的外部 Python 作业占用。本轮未查看它们的工作目录或任务数据，也未向其发送信号。因 CPU 正常，按本任务要求不做 CPU 占用者的目录/项目调查。

## A6000 资源快照

Host：`admin123-Super-Server`；144 个逻辑 CPU。

| 项目 | 观测 |
|---|---:|
| Load average | 124.87 / 99.32 / 97.38 |
| CPU PSI | `some avg10=10.91%`；`full=0` |
| RAM / swap | `MemAvailable` 约 209 GiB；8 GiB swap 仅余约 31 MiB |
| GPU 0 | 12,625 / 49,140 MiB，利用率 32% |
| GPU 1 | 14,883 / 49,140 MiB，利用率 31% |
| GPU 2 | 28,395 / 49,140 MiB，利用率 100% |
| CoDesk Qwen / Guest | 未发现 worker、15485 listener 或运行中的 Guest |

A6000 是 Guest/coordinator 的 canonical 节点，但本次不启动 Guest。当前卡上活动负载使双卡 BF16 endpoint 无法做不争抢资源的验收。

## 路线判断

| 路线 | 依据 | 当前判断 |
|---|---|---|
| 4090 Qwen + A6000 Guest | `REMOTE_INFERENCE_4090_A6000.md` 记录了 2026-09-30 的真实 Qwen3VLAgent Writer Solo PASS；原 worker、权重和 reverse SSH 流程路径仍在。4090 CPU/PSI 已恢复。 | **最快恢复路线，但等待 4090 两卡及 RAM 余量恢复后再启动。** |
| A6000 双卡 Qwen | 历史 BF16 load 成功、`generate()` 超 600 s 无返回；本次三张卡有占用且主机 PSI 高于 4090。 | **不选为当前首选；不继续调试/启动。** |
| A6000 单卡 CPU offload | 历史单卡真实 screenshot 生成成功，首文本约 22 s、完整约 268 s、CPU offload；但 endpoint C-01 在 CPU 压力下未返回，且当前 GPU 也有占用。 | **保留作资源充足时的 fallback，当前不启动。** |
| vLLM | 现有 `envs/vllm-qwen-0.30.0` 未安装 vLLM；没有可直接切换的既有服务。 | 不属于最快路线。 |

## 本轮实际 endpoint 检查

- 4090 `127.0.0.1:15485/health`：连接拒绝；无服务进程或 listener。
- A6000 `127.0.0.1:15485/health`：无 listener。
- 未启动远程 worker、SSH reverse tunnel、Guest 或模型请求，因为原 4090 `CUDA_VISIBLE_DEVICES=0,1` 对应卡目前有显存占用；加载 BF16 约 58 GiB checkpoint 会与这些进程争用 GPU，且当前可用 RAM 仅约 36.5 GiB、swap 已满。
- 未执行 Step 2 的 CPU 用户/PID/工作目录归属审计：4090 CPU 已满足可用条件，检查其他用户项目目录没有必要。

这不是一次成功 endpoint smoke；当前 outcome 是 **BLOCKED_RESOURCE**。

## 下一步的最短执行路径

1. 等待或预约 4090 上两张可分配 RTX 4090；启动前确认每卡显存空闲至少约 46 GiB、GPU 利用率低，并确认 RAM 余量适合模型加载、swap-in/out 为 0。不要因 GPU 利用率暂时为 0 就越过显存检查。
2. 使用既有 worker 与本地权重：`/home/mjh/.local/share/codesk-remote-qwen/709498e/local_qwen_worker.py` 和 `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`，按 `REMOTE_INFERENCE_4090_A6000.md` 原命令绑定原来的 `CUDA_VISIBLE_DEVICES=0,1`；确认 `/health` 的模型、PID、host、设备和 loopback bind。
3. 建立既有 reverse SSH `127.0.0.1:15485` 隧道，在 A6000 验证 `/health`；然后用归档真实截图/原 prompt 发送一条 image request，并确认原 Qwen3VLAgent parser 返回一个 action。endpoint smoke PASS 前不启动 benchmark Guest。
4. endpoint smoke 通过后，在 A6000 使用原 runner恢复 C-01 Solo A/B gate，再继续 A-01；保持任务、Agent、prompt、evaluator 和条件协议不变。

现在值得等**GPU reservation/release**，而不是继续等 CPU。当前观测无法推断外部 GPU 作业何时释放；若今晚/近期没有两张 4090 可分配卡，先暂停 pilot 并协调预约，不切换到同样繁忙的 A6000。
