# V34–V37：四个双 Agent 工作流候选

日期：2026-11-16
分支：`codex/all-codesk-cases-20261113`
代码根目录（HealthCare）：`/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112`
用途：候选卡、Fixture/Oracle 说明与复现指引；模型实验结论见 [V34–V37 模型结果审计](../tasks/paragui/V34_V37_MODEL_RESULTS_20261116_ZH.md)。

## 实验定义

四个场景都在 Synthetic Desk 单页 Web 应用中，让两个 Codex GUI Actor 同时处理**同一业务记录的两个不同面板**。Independent/MA-ID 使用两个隔离 Guest；Shared 共用一个 Guest、一个 Chrome 窗口和同一条记录；Shared+Lock 在每次 GUI 工具调用期间对共享桌面加互斥锁。两项任务初始 Fixture 相同，均从预置 `seed.db` 启动；每个任务通过 SQL 状态快照与预期字段做确定性精确匹配，Oracle 为 0/1 分。

这四项是不同业务外壳，不是四个全新底层机制：它们共同覆盖**同一记录、共享活动面板/表单上下文、表单未保存状态被切走或覆盖**这一类应用层干扰。它们不主张直接证明 OS 层焦点误路由。

每个 case 都有 2/2 的 scripted 联合正控（两项任务均得 1.0）。模型运行统一使用 Codex CLI 0.165.0、GPT-6-Sol/high、60 GUI 调用/Actor、2400s/Actor timeout。MA-ID 对应 `ma-id`，Shared 对应 `shared`，动作级互斥对应 `shared-lock`。不因结果不理想而改提示词或筛除重跑。

## Case 卡

### V34 — River County Water Quality：采样复核与公告结案

- **业务任务 A / `pgv34waterreview`**：复核 WQ-9204，填写分类 ROUTINE、实验室结果 “E. coli not detected; turbidity 0.28 NTU”、处置 RELEASE、实验室参考号 LAB-9204 并保存。
- **业务任务 B / `pgv34advisorycloseout`**：对同一记录登记 NOT REQUIRED、Riverbend South、结案消息 “No restriction; routine sample passed”、NOTICE-9204 并保存。
- **共享状态**：同一记录的 Laboratory sample review / Advisory closeout 面板；选项卡和当前记录均是共享的。
- **Fixture / Oracle**：`tasks/paragui/v456_data.json:v34`；`assets/v34/seed.db` 和 `app_v34.py`；`tasks/paragui/pg_v34.py` 调用 `pg_v456_oracle.py` 对面板字段做精确校验。
- **可观察干扰**：面板切换造成另一任务的未保存输入丢失/落到不匹配的当前上下文。
- **实用性/成本**：日常公用事业质量记录与通知 closeout；实现成本低（复用通用 Desk/Oracle），但应用是假数据，不是实际水务软件。模型结果没有出现 Shared 失败，适合作为边界/负对照，不是达标 case。

### V35 — Linden State University：助学金申诉与注册核验

- **任务 A / `pgv35appealdecision`**：处理 FA-803，记录 GRANT、USD 1200、Spring 2027、AP-803 并保存。
- **任务 B / `pgv35enrollmentverify`**：对同一记录登记 VERIFIED、Enrollment Confirmation、2026-12-08、ENR-803 并保存。
- **共享状态**：Aid appeal 与 Enrollment verification 两个面板争用同一学生服务记录和活动面板。
- **Fixture / Oracle**：`v456_data.json:v35`、`assets/v35`、`pg_v35.py` 和通用精确 Oracle；数据明确为合成信息，不含真实学生个人数据。
- **实用性/成本**：校园学生服务工作流较自然；实现成本低。模型 Independent 中申诉任务 A 已失败，所以 A 缺少有效模型正控，本轮不能据此把 A 的后续失败归因于共享桌面。B 全臂通过，因此不达标。

### V36 — North Ward Election Services：设备封签审计与投票套件放行

- **任务 A / `pgv36sealaudit`**：审计 EPK-019，记录 INTACT、24 台扫描器、None、ELEC-019 并保存。
- **任务 B / `pgv36kitrelease`**：为同一设备包登记 READY、North Ward 3、05:30–06:15、MAN-019 并保存。
- **共享状态**：Seal and inventory audit / Polling kit release 面板共用同一准备状态记录。
- **Fixture / Oracle**：`v456_data.json:v36`、`assets/v36`、`pg_v36.py`、通用确定性 Oracle；场景明确是合成选举运营演习，不对应实际投票点。
- **实用性/成本**：审计后放行是合理工作流；政治/选举设备语境属有意构造的测试，不模拟真实选务系统。Shared 下 A 的已完成 Oracle 失败；B 用满 60 次调用（`max_steps`，不是有效模型失败）；Shared+Lock 两项都通过，说明锁恢复了 A 的问题，本轮不达标。
- **运行环境细节**：V36 Shared+Lock 及 V37 的 Guest overlay 临时目录改用 RAID，避免继续挤占 `/dev/shm`；Fixture、提示词、工具权限及评分 Oracle 不变。

### V37 — Cedarline Telecom：故障复核与恢复验证

- **任务 A / `pgv37incidentreview`**：处理 TEL-771，记录 SEV-2、Fiber splice degradation、12 enterprise circuits、INC-771 并保存。
- **任务 B / `pgv37restorationvalidate`**：对同一事件登记 RESTORED、Packet loss below 0.1% for 10 minutes、CHG-771、MONITORING 并保存。
- **共享状态**：Incident review / Restoration validation 面板共用同一事件记录。
- **Fixture / Oracle**：`v456_data.json:v37`、`assets/v37`、`pg_v37.py` 与确定性精确 Oracle；数据是合成网络运营演习，不涉及真实客户网络。
- **实用性/成本**：事件复核与恢复验证是常见运维工作流；实现成本低。Shared 下 B 失败，模型报告填表过程中活动面板反复切换、未保存字段被清空；A 通过。Shared+Lock 下 B 完成并以“记录仍未保存”结束，Oracle 仍为 0；A 在 2400s timeout，被杀前使用 46 次 GUI 调用。
- **解释边界**：B 满足同任务 MA-ID PASS → Shared FAIL → Shared+Lock FAIL，可算一个**任务级**一次性 tuple；不能说整个双 Actor 三臂都失败，因为 Lock 中 A 为 timeout（无效/排除）。B 的锁臂用了 59/60 GUI calls，接近预算顶，需作为预算风险披露。

## 复现

先准备 HealthCare 上的依赖（OSWorld、SWC、Codex Harness 与可用 API 凭据），确认磁盘/Guest 资源；不要覆写历史 artifacts。以下路径均是本批运行采用的 RAID 根目录，按实际部署调整：

```bash
cd /home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
# 每次复现实验先用一个全新的空目录，避免覆盖既有 fixtures/runs/overlays。
export REPRO_ROOT="/mnt/raid1/mjh/Projects/codesk-v34-v37-repro-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$REPRO_ROOT"
export CO_DESK_ASSETS_ROOT="$REPRO_ROOT/assets"
export CO_DESK_RUN_ROOT="$REPRO_ROOT/runs/triplets"
export CO_DESK_OVERLAY_ROOT="$REPRO_ROOT/overlays"
export CO_DESK_OVERLAY_ARCHIVE_ROOT="$REPRO_ROOT/overlays"
export CO_DESK_CODEX_RUNTIME_ROOT="$REPRO_ROOT/codex-runtime"
export CO_DESK_API_BASE_URL=https://docode.cc/v1
python tasks/paragui/build_v456.py v34 "$CO_DESK_ASSETS_ROOT/v34"
python tasks/paragui/build_v456.py v35 "$CO_DESK_ASSETS_ROOT/v35"
python tasks/paragui/build_v456.py v36 "$CO_DESK_ASSETS_ROOT/v36"
python tasks/paragui/build_v456.py v37 "$CO_DESK_ASSETS_ROOT/v37"
# 由运行环境以隐藏输入/安全凭据注入方式提供 OPENAI_API_KEY，不要写入仓库或日志。
bash scripts/run_new_case_arm.sh v34 ma-id
bash scripts/run_new_case_arm.sh v34 shared
bash scripts/run_new_case_arm.sh v34 shared-lock
```

对 `v35`、`v36`、`v37` 替换 case ID；Guest 联合正控可用 `PYTHONPATH=<repo>:<SWC>:<OSWorld> <OSWorld>/.venv/bin/python scripts/run_v456_guest_control.py v34`。脚本会校验 repo 与 OSWorld runtime 中 task modules 一致，并保存 Fixture/source SHA-256、动作日志、截图和 result JSON。原始完整 run artifacts 位于上述 RAID 路径，不提交到 Git。
