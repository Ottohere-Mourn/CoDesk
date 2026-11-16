# 实际源码、Sol 6.1切换和CPU10 KVM复查

用户已明确允许改用 `gpt-6.1-sol`；先前“不能替换gpt-6-sol”的模型门禁不再适用。
保留Codex统一harness目标及原版A/B三臂设计，不改成四并发。

## 已做的源码工作

- Fetch了全部远程分支，并检索分支tip及可达Git历史中的实际Python实现，不把结果报告当源码。
- 新副本：`runs/imports/codesk-sol61-source-20261105-r1/`。
- CPU10副本：`/data/users/yuke/paraGUI/codesk13-sol61-20261105-r1/source-bundle/`。
- 只收纳实现目录、相关fixture/template和测试；不复制顶层历史`runs/outputs/audits/docs/benchmarks`。
- 找到12个case对应的11个入口脚本，来源为Case 2/3/4与mechanisms四个分支。
- 在新副本中实际修改9个模型相关源码文件，将精确的`gpt-6-sol`模型字面量改为`gpt-6.1-sol`。
  Case 2/3/4原本已是6.1，不重复改动。原始快照与历史实验均未修改。
- 每处改动记录行号、修改前后SHA-256；938个部署文件在CPU10完成哈希核对。
- 新副本的103项原仓库聚焦离线测试全部通过；另有10项收纳/模型替换测试通过。
- CPU10新私有API配置采用`gpt-6.1-sol / medium`；2026-11-05 12:40 UTC实际Responses请求返回200、completed、同名模型。

具体入口见 `source-index.json`，原始/修改后源码哈希见 `source-provenance.json`。
配置见 `experiment-config.json`，以上三个文件都在新副本根目录。

仍不能把“入口存在”视为“完整可运行”：

- 八个Hybrid入口仍引用未发布的adapter/helper。
- EDIT/VIEW/FIND在Git中的实现仍是旧版，11月5日修复结果对应的新实现没有在已检查分支中找到。
- AUTH已有上游结果报告，但实际实现没有发布在这些分支；不是断言上游没有实现过。
- CWD旧入口使用SolOSWorldAgent/Chat Completions；必须迁移到Codex/Responses后才能运行6.1，不能只改模型名便直接启动旧transport。

## KVM实测：机器有设备，账号无访问权限

2026-11-05 12:38 UTC，在新的CPU10 SSH会话中：

| 检查 | 实测结果 |
|---|---|
| 主机/账号 | `yifan-cpu-wus3-10` / `yuke`，UID1001 |
| CPU与内核模块 | CPU标志含`svm`；`kvm_amd`和`kvm`已加载 |
| 设备 | `/dev/kvm`存在，字符设备，`root:kvm`，GID993，权限`0660` |
| 当前组与NSS组 | 均只有1001，不含kvm |
| 宿主真实设备打开 | `os.open('/dev/kvm', O_RDWR)`返回errno13：Permission denied |
| rootless Docker实测 | 正常创建并启动仅带`--device /dev/kvm`的诊断容器；容器内打开设备同样errno13 |

这次不只检查`os.access`，也不从宿主权限单独推断容器结果，两处都做了真实设备打开。
诊断容器无网络、只读根文件系统、未使用privileged、未启动Guest；已按完整容器ID、项目/run/owner标签和ledger校验后清理。
没有改设备权限、组成员或系统服务，没有重启正在承载其它任务的Docker。

证据：CPU10的`/data/users/yuke/paraGUI/codesk13-sol61-20261105-r1/kvm-probe/report.json`及同目录`resource-events.jsonl`。
可复查脚本：`experiments/codesk_kvm_probe.py`。

下一步需要管理员为`yuke`授予`/dev/kvm`读写权限，并在授权后重新验证rootless容器。
仅设备存在不等于账号可用；新增组成员也不能当成已有Docker进程自动获得权限的证据。
本次真实任务episode数仍为0，模型切换/离线通过不等于已经启动三臂实验。
