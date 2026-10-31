# Case 2 Lite：HealthCare 迁移与真实桌面对照（2026-10-31）

## 仓库与环境

- 上游：`faa896a Case2 Lite: add native-QEMU solvability workflow`，来自 a800 的 `codex/overnight-cases-2-4`。HealthCare 原主工作区有其他未提交改动，未修改；本工作在独立 worktree `/home/mjh/Projects/CoDesk-case2-healthcare`、分支 `codex/case2-healthcare` 进行。
- a800 的单 Agent 原始试验在 TCG 下运行超过 1300 秒，完成了复核和 $88 退款，但未结案；没有完成独立/共享对照。HealthCare 使用 Docker/KVM OSWorld Guest、同一轮次的 Case Desk/SQLite/协作服务与原业务 Oracle。
- HealthCare 适配入口：`infra/run_ticket_to_resolution_lite_healthcare.py`。每轮新建有所有权标签的 Docker Guest，基础镜像只读；模型通过本机私有密钥文件使用 `gpt-6.1-sol`。密钥、轮次目录和凭据不纳入 Git。

## Lite v1.1.3 的精简边界

- 原任务的票据、订单行、损坏证据、政策、角色权限、退款金额计算、幂等交易、结案代码及数据库 Oracle 没有改动。脚本参考路径仍为 A 6 次、B 7 次 GUI 操作；真实 Agent 每角色最多 15 次桌面调用。
- 来源资料与角色表单并排；压缩页头与空白；选中单选项时显示整行高亮；退款完成页将结案表单和交易摘要置于右侧首屏，备注框保持空白且必填。没有预填判断或金额。
- B 若先到达，会读取消息并暂停；只有 A 保存 Review 且发送交接后才恢复。此规则同时应用于独立和共享条件，不重置 B 的桌面调用预算。
- Codex CLI 0.165.0 的协作 MCP 需要显式 `default_tools_approval_mode = "approve"`；模型实际发送/读取消息的探针已验证。Responses relay 仅保留最新桌面截图并随图重复公开角色任务说明，解决原试验的图像历史膨胀与任务丢失；两种桌面拓扑采用相同设置。

## 已完成验证

| 轮次 | 条件 | 结果 | 关键证据 |
| --- | --- | --- | --- |
| `ttr-lite-healthcare-v113-isolated-control-20261031a` | 独立桌面，脚本正/反例 | `CONTROL_PASS` | 正例 A6/B7，$88 与 `RESOLVED`；反例错误金额不退款；容器与 overlay 清理成功。 |
| `ttr-lite-healthcare-v113-isolated-20261031a` | 独立桌面，真实 `gpt-6.1-sol` | `TASK_PASS` | A8/B12；A 消息被 B 读取，B GUI 打开 Review；一笔 $88 退款、`RESOLVED`、审计顺序与受保护状态均通过；229,310 tokens，清理成功。 |
| `ttr-lite-healthcare-v113-shared-20261031a` | 共享桌面，真实模型，诊断轮 | 业务失败，最终标签受重置异常覆盖 | A/B 各 15 次后 Review 0、退款 0、工单 `OPEN`。B 的点击落在 A 窗口的 `Sign out`，A/B 随后困在登录页。评估后的浏览器重置因 A 已登出而抛错，旧运行器将标签覆盖为 `INFRA_FAIL`；原 Oracle 和截图仍在。 |
| `ttr-lite-healthcare-v113-shared-lock-20261031a` | 共享桌面，输入锁，真实模型 | `INFRA_OR_BUDGET_STOP_WITH_ORACLE_SCORE` | A15 后达到 900 秒，B2 后等待交接到期；Review 0、退款 0、`OPEN`。输入请求无重叠，但 A 多次操作落在 B 的浏览器窗口；锁没有保证窗口归属。 |
| `ttr-lite-healthcare-v113-shared-20261031b` | 共享桌面，真实模型，补跑 | `TASK_PASS` | A11/B15；初期同样有窗口互换，但模型恢复焦点，完成一笔 $88 退款与 `RESOLVED`，Oracle 通过，清理成功。 |
| `ttr-lite-healthcare-v113-single-20261031a` | 单 Agent，真实模型，严格 20 次上限 | `TASK_FAIL` | S20；复核和一笔 $88 退款均通过，但结案动作未在预算内提交，工单 `REFUND_PENDING`；161,833 tokens，清理成功。 |
| `ttr-lite-healthcare-v113-single30-20261031a` | 单 Agent，真实模型，诊断性 30 次上限 | `TASK_PASS` | S23；一笔 $88 退款、工单 `RESOLVED`，业务 Oracle 通过；165,793 tokens，清理成功。30 次是显式预算覆盖，不计作默认 S20 成绩。 |

共享轮的交叉窗口误投递由动作日志中的 `window_before`、浏览器登录页截图和服务审计共同支持；单次 GUI 输入并无时间重叠，因此仅序列化输入不足以保证窗口归属。已修复重置异常覆盖业务结果的问题，后续轮次会将重置错误单列。修复前的 16 份已完成轮次 Docker overlay 在核验无运行中容器后清理，合计约 18.46 GB；每轮留有 `overlay_cleanup_audit.json`。

相关的 65 项代码测试通过，`git diff --check` 通过。结果目录、截图、数据库快照和凭据均由 Git 忽略；提交仅包含代码、测试和本 handoff。所有列出的最终轮次均报告容器与 overlay 清理成功。

**结论边界：** 当前同版本真实样本中，隔离 1/1 通过，共享基线 1/2 通过，输入锁 0/1 通过（预算终止）；单 Agent 默认 S20 失败、S30 诊断成功。参考正确脚本为 13 次 GUI 操作，真实模型需要的调用数不同。这不能证明“共享稳定不过”或“输入锁普遍无效”。B 的提前暂停使主要业务阶段近似串行，强模型可以从前期焦点冲突中恢复；若要把 Case 2 作为可靠区分独立/共享桌面的基准，需要在不泄露答案、保留 15 次预算的前提下设计有业务意义的并发前置工作，再冻结新版本做多轮配对试验。

## 待完成

- 下一版若以稳定区分桌面拓扑为目标，需要让 B 在 A 保存 Review 前完成独立、有业务意义的可见资料核验，形成真实并发；冻结后做多轮配对试验。当前样本不能推断总体成功率。
- 默认 S20 预算也应在下一版单独评估：业务参考路径 13 次，但真实模型出现 20 次时只差结案、扩展至 30 次后用 23 次完成。改变预算应提升任务版本，不与本版结果混算。

## 运行命令

在 HealthCare 的上述 worktree 中，使用 OSWorld venv 的 Python：

```bash
python infra/run_ticket_to_resolution_lite_healthcare.py --mode controls --condition collaborative_isolated --run-id RUN_ID
python infra/run_ticket_to_resolution_lite_healthcare.py --mode model --condition collaborative_isolated --run-id RUN_ID
python infra/run_ticket_to_resolution_lite_healthcare.py --mode model --condition collaborative_shared --run-id RUN_ID
python infra/run_ticket_to_resolution_lite_healthcare.py --mode model --condition collaborative_shared --mitigation input-lock --run-id RUN_ID
python infra/run_ticket_to_resolution_lite_healthcare.py --mode model --condition single_agent --step-budget 30 --run-id RUN_ID
```

轮次结果位于忽略的 `runs/ticket_to_resolution/healthcare/<run-id>/result.json`，原始动作、截图、协作读写、模型用量与数据库证据保留在各轮目录。
