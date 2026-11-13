# CoDesk Case 2 下一阶段任务书（交接给新 session）

交接日期：2026-11-01。工作范围仅为 **Case 2 Lite**；Case 3 暂停开发，Case 4 保留独立分支及已完成报告。请先读本文件和 `CASE2_HARDENING_REPORT_20261101.md`，再动代码。不要把旧模型运行当成新版本结果，不要整合其他协作者分支。

## 1. 项目与研究目标

CoDesk 比较两个协作 Agent 在 **独立桌面（Isolated）**、**共享桌面（Shared）**、**共享桌面加逐动作输入锁（Shared+Lock）** 中完成同一真实 Guest GUI 任务的表现。三臂应使用同一业务任务、Fixture、Oracle、模型与推理配置、角色预算、Guest 镜像和协作规则；仅桌面拓扑和第三臂的 Action Lock 不同。保留自然并发，记录窗口焦点、截图、动作顺序、模型/API 状态、业务评分及清理结果。

Case 2 的**研究假设/期望效果**是：Isolated 可稳定 PASS；Shared 因真实共享 GUI 状态干扰而 FAIL；简单逐动作 Action Lock 仍不能完全阻止跨调用焦点误路由，因此 Shared+Lock 也可能 FAIL。**这不是结果筛选标准，也不是必须“做出”失败的验收条件。** 不得设置 Shared 专属障碍、差异预算、不同提示/评分、人工窗口抢占，或丢弃成功运行。若对称改版后 Shared 仍 PASS，应如实保留 Case 2 为简单任务的对照案例。

任务的另一项硬目标是 **独立桌面基础可解性与评分可信度**：同版本真实 Guest GUI 正负控、Oracle、reset/重开或状态复核、可追溯日志必须先通过；模型业务失败、流程失败、预算/API/Guest/后处理故障分别报告。Case 2 不是只追求三臂标签。

## 2. Case 2 业务任务（现行 v1.1.3）

合成工单 T-1042：客户收到损坏的 USB-C dock，订单 O-2048 另有完好的显示器。A 是 Order Verifier，查看客户陈述、订单行、送达证据 `DELIVERY-EV-77` 和政策 `POLICY-RET-4`，保存结构化 Case Review，并给 B 发消息。正确审核应认定受损行为 O-2048-L2，退 dock 的 $80 本金和 $8 税，**不退 $15 运费**，拟退款 $88。B 是 Support Processor，在 GUI 核对来源记录与 A 的 Review，针对该行发起 $88 退款，关联成功交易，以 `PARTIAL_REFUND_DAMAGED_ITEM` 关闭工单并填写客户说明。不得改动无关记录。

当前参考 scripted 正确路径为 A6/B7 次 GUI 动作；每人默认 15 次桌面调用。A 的有效 Review 是 B 退款的后端必要前提，金额、订单行、审计顺序和受保护状态由 Oracle 检查。单 Agent 条件也存在，但本阶段核心是 A/B 三臂。新版本应尽量保留这张工单、订单、退款决定和角色责任，而不是另造题目。

## 3. 已完成基线及真实结果（不要重复消费）

当前开发代码位于 `/home/mjh/Projects/CoDesk-case2-hardening`，分支 `codex/case2-hardening`，交接前 HEAD `01d326a`，工作区干净。旧代码/原始 runs 位于另一 worktree `/home/mjh/Projects/CoDesk-case2-healthcare`，分支 `codex/case2-healthcare`；**模型结果目录仍统一写在后者的 `runs/ticket_to_resolution/healthcare/` 下**。不要在旧 worktree 直接覆盖开发分支，也不要清理 runs/overlays/secrets。完整事实见 `CASE2_HARDENING_REPORT_20261101.md` 和 `CASE2_EXPERIMENT_PLAN_20261031.md`。

- 同版本 SSD/KVM scripted 控制：`ttr-v113-hardening-isolated-control-20261101a` 与 `ttr-v113-hardening-shared-control-20261101a` 均 `CONTROL_PASS`。正控 A6/B7 完成 $88 退款和结案；负控 A6/B4 的错误退款被拒、零退款；两种拓扑的最终数据库 reset 和 Guest 清理通过。这些是脚本正负控，**不是模型实验**。
- 冻结的 v1.1.3 模型三臂（`gpt-6.1-sol`、medium、每人 15 次调用、1800 秒墙钟上限）：`ttr-v113-hardening-isolated-20261031a` 业务 PASS A8/B12；`ttr-v113-hardening-shared-20261031a` 业务 PASS A10/B14；`ttr-v113-hardening-shared-lock-20261031a` 业务 PASS A10/B15。三次 `execution_status=VALID`、Oracle 快照可靠、reset 与清理通过，**三次 `collaboration_process_status=FAIL`**。锁臂记录 22 次 GUI 输入，累计实际锁等待 0 秒；普通 Shared 也没有同时输入碰撞，故本 cohort 不证明 Action Lock 的收益或共享额外失败。
- 严格交接失败有原始时间线：Isolated 中 A 09:09:46.921 UTC 保存 Review，B 09:09:47.125 已打开；A 09:10:23.775 才发消息，B 09:10:37.280 才读。Shared 和锁臂也都是 B 在消息前打开 Review。后端 Review 是必要依赖，**消息目前不是必要的信息来源**。不要把三次业务 PASS 写作严格协作 PASS。
- 较早 900 秒/HDD Shared `ttr-lite-healthcare-v113-shared-20261031a` 存在截图支持的跨窗口登录/退出干扰，A/B 均用满 15 次，原始 Oracle 显示无审核、无退款、工单 OPEN；最终显示的 `INFRA_FAIL` 是随后 reset 异常覆盖了业务 FAIL。另一次旧 Shared 业务 PASS；旧 Shared+Lock A 超时、B 等交接 856.54 秒，只调用两次，是预算无效运行。新代码已将 reset、业务和执行结果分开。旧 900 秒/HDD 与新 1800 秒/SSD 不能合并估计通过率。

**基线结构问题比“单纯太简单”更关键**：`webapp.py` 的 B 首页在 `/lite/review-ready` 上每 3 秒轮询，A 一保存 Review 就自动跳转到审核页，常早于 A 的交接消息；`lite_v1/spec.py` 又允许 B 在审核未保存时很早结束当前轮次等待，因而实际有意义的并发工作少。仅增加随机计算难度或收紧预算，容易让 Isolated 也失败，却未解决研究问题。

## 4. 建议的新版本 v1.2（设计候选，先审计再冻结）

在新的开发分支/worktree 实现；v1.1.3 及原始 runs 保留。对 Isolated/Shared/Shared+Lock **完全对称**地调整：

1. **B 的独立预核验**：B 起始页面保留工单、订单、证据与政策；增加紧凑的 B-only 预核验表单，让 B 在未看 A Review 前独立选择受损订单行、证据/运费处理和拟退款总额并保存。该记录有真实业务意义（双人复核），由 Oracle 检查，不只是为了增加点击。A 同时完成现有 Review，使两人前半段自然并行操作各自浏览器。
2. **真实交接信息**：取消 B 首页的自动 Review 轮询/跳转和提前展示 Review ID。A 保存后在 GUI 得到真实 Review ID，通过协作消息交给 B，不在消息中直接给退款金额。B 读取消息后，在自己的 GUI 用该 ID 打开 Review，比较预核验与审核，再退款、结案。若需 B 可用的查找控件，应是正常业务界面，不能给 Shared 特殊处理。Review ID 由现有审核产生，不引入纯粹的“解锁暗号”。
3. **后端与 Oracle**：B 的退款仍必须引用 A 的有效 Review；检查 B 的预核验、Review ID 与最终退款一致，记录 A 保存→A 发消息→B 实际读取→B 按 ID 在 GUI 打开 Review→B 退款→结案的事件时间线。业务正确、严格协作、模型/预算有效和 reset/后处理各自单列。若 B 提前看到 A 的共享窗口而得知 ID，原始轨迹应保留，严格流程审计可判 FAIL；不能按拓扑修改规则。
4. **可解性余量**：预期正确 scripted 路径约 A6、B9–10 次 GUI 动作。基于真实 Isolated pilot 选择**所有三臂相同**且有恢复余量的模型调用预算与墙钟上限；不要利用刚好卡住 Shared 的阈值制造差异。减少无意义空白和滚动可以，不能预填业务答案。

逐动作 Action Lock 只串行单次输入，不能保护“Agent 看截图→思考→下一次点击”之间的前台窗口；A/B 并行预核验会真实增加浏览器窗口切换机会。因此新版有机会检验 Case 4 类似的焦点机制，但不保证预期 PASS/FAIL 组合。若三臂后仍不出现差距，不再继续加 Shared 定向障碍。可将 Focus Revalidation 作为**冻结三臂之后**的单独 Harness 消融，而不是混入第三臂。

## 5. 代码、环境与凭据位置

| 用途 | 位置 |
| --- | --- |
| HealthCare Docker/KVM 入口 | `infra/run_ticket_to_resolution_lite_healthcare.py` |
| 模型生命周期、B 挂起/唤醒、严格交接与分项评分 | `infra/run_ticket_to_resolution_lite_model.py` |
| Guest 启动、真实 GUI scripted 正负控、reset | `infra/run_ticket_to_resolution_lite_native.py` |
| 角色指令和预算 | `oscombo/collab/ticket_to_resolution/lite_v1/spec.py` |
| Case Desk Lite GUI；B 自动轮询/跳转见 `_page_lite` | `oscombo/collab/ticket_to_resolution/webapp.py` |
| 后端业务状态机 / 业务 Oracle | `oscombo/collab/ticket_to_resolution/database.py`、`oracle.py` |
| 相关测试 | `tests/test_ticket_to_resolution_lite.py`、`tests/test_ticket_to_resolution_lite_model_runner.py`、`tests/test_ticket_to_resolution_lite_native_diagnostics.py` |
| v1.1.3 报告 / 已冻结计划 | `CASE2_HARDENING_REPORT_20261101.md`、`CASE2_EXPERIMENT_PLAN_20261031.md` |

SSH 目标是 `HealthCare`，用户 `mjh`。OSWorld 代码与虚拟环境：`/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1`，Python 为其 `.venv/bin/python`。宿主 Docker/KVM runtime 镜像 `swcub/osworld-v2.1-qemu-runtime:local`，Guest 基础镜像 SSD 路径 `/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2`，与 HDD 原镜像 SHA-256 相同：`28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a`。新运行的 overlay 在各 run root 的 `overlays/`，不要手工清理或复用运行目录。

模型为 `gpt-6.1-sol`、medium，首选 `https://api.haogpt.net/v1`，备用 `https://docode.cc/v1`；私有 API key 已在 HealthCare 的 `/home/mjh/.config/codesk/haogpt_case3.key`（0600），**不要复制、输出或提交密钥**。运行器自行读取并探测端点。模型 relay 每角色输出 token 预算 12000。Git remote `origin` 为 `https://github.com/Ottohere-Mourn/CoDesk.git`；本任务无需合并或推送其他分支。

## 6. 复现与新 session 执行顺序

先 `ssh HealthCare`，核对分支、`git status`、磁盘/内存/KVM 与现有 runs。建议从 `codex/case2-hardening` 建独立 `codex/case2-v12` worktree，不在 `case2-healthcare` 旧 worktree 开发。若新 worktree 路径不同，以下命令中的 `cd` 应替换为实际路径。CLI 已核对；`--mode controls` 默认依次运行 positive、negative。现有 runner 接受以 `ttr-lite-` 开头的唯一 run_id；v1.2 新 ID 可用此前缀，运行前确认目录不存在。以下是命令模板，**先完成代码与控制，再预登记正式 ID**：

```bash
cd /home/mjh/Projects/CoDesk-case2-hardening
PY=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python
$PY infra/run_ticket_to_resolution_lite_healthcare.py --help
/opt/miniconda3/bin/python -m pytest -q tests/test_ticket_to_resolution_lite.py tests/test_ticket_to_resolution_lite_model_runner.py tests/test_ticket_to_resolution_lite_native_diagnostics.py
```

```bash
# v1.2 改完后，先分别验证两种真实 Guest 拓扑的脚本正负控；ID 换成预登记且未使用的新 ID。
$PY infra/run_ticket_to_resolution_lite_healthcare.py --mode controls --condition collaborative_isolated --run-id ttr-lite-v120-control-isolated-YYYYMMDDa
$PY infra/run_ticket_to_resolution_lite_healthcare.py --mode controls --condition collaborative_shared --run-id ttr-lite-v120-control-shared-YYYYMMDDa
```

```bash
# 独立桌面真实模型 pilot 通过后冻结任务/预算/镜像/ID；正式对照按预登记顺序逐一运行。
$PY infra/run_ticket_to_resolution_lite_healthcare.py --mode model --condition collaborative_isolated --run-id ttr-lite-v120-isolated-r1-YYYYMMDD --wall-seconds 1800
$PY infra/run_ticket_to_resolution_lite_healthcare.py --mode model --condition collaborative_shared --run-id ttr-lite-v120-shared-r1-YYYYMMDD --wall-seconds 1800
$PY infra/run_ticket_to_resolution_lite_healthcare.py --mode model --condition collaborative_shared --mitigation input-lock --run-id ttr-lite-v120-shared-lock-r1-YYYYMMDD --wall-seconds 1800
```

命令中的 `YYYYMMDD` 是**需替换的占位符**；不要直接运行占位符，也不要复用旧 run_id。若经 Isolated pilot 决定改变 15 次默认调用预算或 1800 秒上限，应在三臂前统一冻结，并在三臂命令中用相同 `--step-budget` / `--wall-seconds`；不能在看过 Shared 结果后追改。模型实验串行执行，避免多个 KVM Guest/重型 API 任务互相拖慢。API 或 Guest 异常要标注无效并保留原始目录，不将其算成业务 FAIL；只有新诊断价值时才重试。

每个 run 的 `progress.json` 是实时状态，`result.json` 是最终总账；细查 `oracle`、`business_status`、`collaboration_process_status`、`execution_status`、`handoff_audit`、`desktop_interference`、`failure_attribution`、`actors`、`reset` 和 `cleanup_verified`。`desktop_requests.jsonl` 给出 A/B 输入时间与锁等待；`collaboration/events.jsonl` 与 `collaboration_reads.jsonl` 给出消息/实际读取；`actor_runs/{A,B}/trace.json`、`screenshots/{A,B}/` 给出动作与截图；`evidence/pre-reset-case.sqlite3` 保留评分前业务状态，不能用 reset 后主库替代。上述路径均在单次 run root 下。截图支持的具体错窗口动作才可称“确认误路由”；采样到前台变化或 API 失败本身不是业务干扰证据。

## 7. 验收与停止条件

先提交 v1.2 任务/Fixture/Oracle/Adapter/预算说明与测试；完成同版本真实 GUI scripted 正负控（包括错误或缺失 Review ID、错误预核验/退款、reset）。再跑少量 Isolated 模型 pilot，确认基础可解且严格交接可验证。若独立桌面仍不稳定，先修对三臂对称的可用性问题，保留每次 pilot；不要以 Shared 失败作为“成功”。冻结后做少量重复三臂，报告每次有效/无效状态、步骤、消息及 GUI 时间线、窗口截图、锁等待、模型活动/挂起时间与总耗时。若 Shared 与 Shared+Lock 都 PASS，就把 Case 2 定位为阴性对照，停止为追求失败继续调题；研究主证据仍由 Case 4 承担。
