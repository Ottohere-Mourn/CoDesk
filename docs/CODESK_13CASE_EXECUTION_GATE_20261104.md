# 13-case Codex统一运行：执行口径与实测门禁

## 已按用户确认的口径调整

- 统一为Codex harness，不再规划Freehand。
- 参考交接版本保留两角色A/B与三臂：Isolated → Shared → Shared+逐动作锁，不强制扩成四人。
- 新的Isolated有效且精确PASS后，才能继续同case共享两臂；旧历史PASS不能替代新cohort基线。
- 保留每case的提示、工具权限、受控交错与预算；不自动将只读CLI升级为可写CLI。
- API/Guest/源码/评分器无效与业务FAIL分开记录，所有业务分数保持空值直至真实执行和验收。

模型和调用预算不是全部相同：Case 2/3/4源runner采用`gpt-6.1-sol / medium`，
各角色桌面调用上限分别为15/12/15，actor wall上限1800秒；Hybrid机制runner采用
`gpt-6-sol / medium`、每角色20次调用、12000输出token预算、3500秒超时。
CWD原版为20次模型动作批次，每批最多16动作；换Codex时还需明确映射这些预算单位，不能当作完全相同的调用上限。
AUTH尚无可直接冻结执行的模型runner，FIND的已知目标冲突需版本化修复并重新做基线。

## 本次实际检测，不是推测

### 模型权限

通过CPU10已有实验凭据向同一网关分别发送最小Responses请求：

| 请求模型 | HTTP | 结果 |
|---|---:|---|
| gpt-6-sol | 403 | 当前Key不可访问该模型或该名称无效；网关模型列表也没有该ID |
| gpt-6.1-sol | 200 | completed，返回模型名一致，15 total tokens |

未把`gpt-6-sol`自动换成`gpt-6.1-sol`、`gpt-6-astra`或Copilot池模型。
这两次是连通性预检，不是任何case的Agent episode。

### Guest环境

CPU10个人账户`yuke`下，`/dev/kvm`存在但没有读写权限；自己的rootless Docker中没有
QEMU/OSWorld运行镜像。只读搜索个人数据目录`/data/users/yuke`至7层深度未发现可用Guest镜像。
没有使用其他用户的镜像或权限，没有sudo，也没有停止正在运行的其他实验。
此前Writer实验使用的是原生应用容器，不是原分支要求的KVM/OSWorld Guest；不能静默视为同一环境。

### 交接源码

除原来的六个快照，还检查了仓库的`codex/overnight-cases-2-4`、`collab-cases`、`lyw-dev`、
`prep/codesk-v1-handoff`、`v0`分支提交，仍未找到四个被引用的文件：

- `oscombo/harness/hybrid_v2.py`
- `scripts/run_workflows_qwen_v1.py`
- `scripts/run_calc_mechanism_qwen_v1.py`
- `scripts/run_sol_writer_overwrite_v1.py`

已交付的`_run_model_actor`版本也不接受Hybrid runner传入的`hybrid_v2`参数。
这些helper涉及提示、准备和调度，不能用空模块跳过导入就宣称保持原case协议。

## 当前执行状态

机器记录：`runs/comparisons/codesk-13case-codex-20261104-r1/preflight.json`。
**任务模型episode数为0；没有正在运行的13-case批次，也没有成功/失败得分。**

原版执行需要补齐可访问的Guest环境、缺失源文件/API版本及`gpt-6-sol`模型权限。
如果改用当前CPU10原生应用容器与可用模型，需要明确授权后作为独立移植cohort重新冻结和验证，
不能直接与原版历史结果合并。
已完成的13-case收纳和103项离线测试仍保留，但不替代上述真实运行门禁。
