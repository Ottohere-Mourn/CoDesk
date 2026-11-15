# V28–V30：三项新增双 Agent 工作流卡

日期：2026-11-15
分支：codex/all-codesk-cases-20261113
Harness：Codex CLI 0.165.0 + GPT-6-Sol；OSWorld Guest GUI；三臂 MA-ID / Shared / Shared+Lock。
用途：扩展业务主题，不宣称发现三个新机制。三项均采用合成数据和同一类共享 Desk 应用；是否满足严格目标以相邻模型结果审计为准。

## 共同实验定义

- Actor A 与 Actor B 分别有独立明确目标、任务模块和确定性 Oracle。两者共用同一 App/Desk 当前上下文；Independent arms 使用相同 Fixture 与任务但隔离桌面。
- Shared 为并发桌面运行；Shared+Lock 使用每次 GUI 调用互斥锁，不是整项事务锁。
- 三个 scripted joint 正向 Guest controls 均通过，两项 Oracle 均为 1/1，状态可读；模型三臂每臂使用相同 GPT-6-Sol / high effort、单 Actor 最多 60 GUI tool calls。
- Fixture、预期数据和 Builder 定义在 tasks/paragui/v456_data.json、tasks/paragui/build_v456.py；应用模板为 tasks/paragui/app_v456_template.py。Guest 任务模块由 scripts/run_new_case_arm.sh 安装，评分代码在 pg_v456_oracle.py。
- Synthetic、离线 app；不得用于真实招聘决策、生产 SaaS 帐户、真实邀请或外部客户数据。

## V28 — North County Community Sports League

**工作流。** 针对同一场 MCH-8301，A 完成 Field 2 场地检查记录；B 更新比赛计划。
**Actor A — Inspection / task pgv28inspection。** 场地状态 Restricted；记录 “Loose sideline anchor at Field 2”；设备检查结果 “Secure after inspection”；参考号 INSP-8301。
**Actor B — Schedule / task pgv28schedule。** 赛场 Field 4、开球 14:30、裁判组 Crew North-2、参考号 SCH-8301。
**共享状态与风险。** 两任务围绕同一 fixture，在同一浏览器 Desk 表单工作区中修改各自数据；可能竞争 active panel 和输入焦点。
**Oracle。** 两项均要求 MCH-8301 对应记录的全部四个字段精确匹配 expected.json；不是仅验证 UI toast。
**Pilot 结果。** MA-ID 两项通过；Shared 两项失败；Shared+Lock 两项通过。Shared 的 A、B 都触及 60/60 GUI call 上限，故虽评分器读取有效且 0/2，仍有明确预算混杂，不能作为无预算混杂的严格 Shared FAIL。锁臂 2/2，亦不满足要求的 Shared+Lock FAIL。结论：不计入达标案例；保留为“共享失败被锁恢复”的反例/消融对照。

## V29 — Northstar University

**工作流。** 合成候选 APP-7246 的筛选记录与技术面试协调。
**Actor A — Screening / task pgv29screening。** 标记 ADVANCE，岗位 Data Analyst，填写 SQL 与 reporting exercise 的标准化依据，以及 SCR-7246。
**Actor B — Interview / task pgv29interview。** 安排 Technical interview，Analytics Team B，Dec 08, 10:30 ET，参考 INT-7246。
**共享状态与风险。** 两任务针对同一合成候选的 review/co-ordination Desk，但 A 的筛选判断与 B 的面试安排可以独立保存。
**Oracle。** APP-7246 两条记录分别四字段精确匹配 expected.json。只用 synthetic candidate；不触达真人求职者或实际招聘决定。
**Pilot 结果。** MA-ID、Shared、Shared+Lock 三臂均 2/2 通过。Oracle/readable 状态有效，但没有所需共享失败。结论：不计入达标案例；作为共享不必然导致失败的 all-pass 对照保留。

## V30 — Brightpath SaaS

**工作流。** 合成客户 ONB-6194 的客户成功交接与培训安排。
**Actor A — Handoff / task pgv30handoff。** 标记 READY，workspace LUMEN-SBX，客户联系人 Jordan Lee，参考 HOF-6194。
**Actor B — Training / task pgv30training。** 安排 Dec 10, 13:00 ET；培训主持组 Customer Enablement East；Video call；参考 TRN-6194。
**共享状态与风险。** 两任务位于同一客户 onboarding Desk；一个更新 readiness/handoff，另一个维护 training schedule。
**Oracle。** ONB-6194 两记录均需四字段精确匹配 expected.json；测试不创建真实 workspace、不发送邀请、不 provision 生产 SaaS。
**Pilot 结果。** MA-ID 2/2 通过；Shared 2/2 通过；Shared+Lock 中 A 通过、B 失败（1/2）。Shared 没有目标失败，因此锁臂的单 Actor 失败不能构成目标组合；该锁臂结果也不能单独证明是共享干扰所致。结论：不计入达标案例；保留原始结果，不事后调参。

## 复现入口

在 HealthCare 已配置 OSWorld/Guest、必要 Runtime 与安全的运行时模型凭证后：

- scripts/run_new_case_arm.sh v28 ma-id|shared|shared-lock
- scripts/run_new_case_arm.sh v29 ma-id|shared|shared-lock
- scripts/run_new_case_arm.sh v30 ma-id|shared|shared-lock
- Scripted Guest 正控由 scripts/run_v456_guest_control.py --case v28|v29|v30 调用；具体输出目录参数见 --help。

模型/Guest 运行产物保存在 HealthCare RAID：/mnt/raid1/mjh/Projects/codesk-next5-20261115/runs/triplets/。原始图像、完整模型 traces 和 overlay 不纳入 Git；本卡及结果审计给出可追踪的 run IDs。不要把 API key 写进代码、参数、版本控制或日志。

## 判定

这三项扩大了足球场地、大学招聘流程和 SaaS 客户入驻三种业务外观，但其实现仍复用 Desk 的 active-panel/current-record 应用上下文机制。V28 是唯一出现 Shared 0/2 的候选，但 Shared 达到双 Actor call ceiling 且锁臂 2/2；V29 全 pass；V30 Shared 全 pass。**本轮 0/3 满足 MA-ID PASS + Shared FAIL + Shared+Lock FAIL。**请不要把 60-call 用尽、基础模型失败或单一无归因的锁臂失败重新包装成干扰证据。
