# V43–V47 实现 / 预检记录（2026-11-17）

## 状态摘要

| 验证层 | 结果 |
|---|---|
| 数据、网页 fixture 和 expected Oracle 构建 | **5/5 已生成**，输出在 RAID：`/mnt/raid1/mjh/Projects/codesk-v43-v47-20261117/assets/v43..v47/` |
| OSWorld task adapter | **10/10 可由当前 OSWorld loader 加载**，task id 与 instruction 可读 |
| Oracle / 资产离线测试 | `pytest -q tests/test_v456_oracles.py` **63 passed**；有正例、错字段负例、边界规范化、源信息字段覆盖断言与 5 个本地 Web App HTTP roundtrip 测试 |
| Bash / Python 静态检查 | `bash -n scripts/run_new_case_arm.sh`、Python 编译、`git diff --check` 通过 |
| scripted GUI Guest 正控 | **未运行**；不得把离线 Oracle 测试算成 GUI 控制 |
| GPT-6-Sol 三臂 | **未运行**；目前没有 MA-ID / Shared / Shared+Lock 结果 |

## Guest 运行前置阻塞（不作为 case FAIL）

2026-11-17 HealthCare 只读 preflight：根盘约 99%（28 GB free），RAID 约 95%（886 GB free），`/dev/shm` 约 91%（13 GB free）；80 个 CPU，load average 约 5–6，swap 2 GB 已用满。RAID 足够承载这些用例的 fixture、结果和 Guest overlay，但不得把 overlay 写到根盘或继续扩大 `/dev/shm`。

Docker 中有一个已运行约 3 天的 `sharp_bhabha` OSWorld runtime，它发布固定宿主端口 `5000/8006/8080/9222`，其中有 root-owned QEMU Guest 进程；这个容器不是本批启动，归属未能仅凭只读检查确认。为避免占用端口、改动或重置他人正在使用的桌面，本轮**没有**启动新的 Guest，也没有停止/清理该容器。需要由资源所有者确认其释放/可复用后，再启动 scripted positive controls。CPU 核数多并不能绕开固定端口和 Guest 所有权冲突。

因此此处是基础设施资源隔离门槛，不是模型 API/key 额度问题；也不是 case 的 FAIL。没有调用 GPT-6-Sol API，未产生 token 成本或声称的模型结果。

## 下一步复现

1. 资源所有者确认固定端口 OSWorld Guest 可释放，且检查无其他运行中的 runner。
2. 单题串行执行 `python scripts/run_v456_guest_control.py v43` … `v47`，确认 A/B scripted GUI 分数均为 1.0，并留存截图/结果与 Guest reset 状态。
3. 先对 5 题逐个跑 MA-ID；只有 A/B 都有效通过的题才进入 Shared。Shared 未造成双角色有效失败则门控停止；仅双方仍失败/达预注册条件时进入锁臂。Timeout / infra-invalid 一律不计 FAIL。
4. Run/overlay/result 保存到上方 RAID 根路径。重跑时保留此前证据，不清理旧 Guest overlay。
