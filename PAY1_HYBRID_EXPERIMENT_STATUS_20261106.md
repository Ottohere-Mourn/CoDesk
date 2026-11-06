# PAY-1 Hybrid 实验记录（2026-11-06）

## 结论

**PAY-1 在一次 GPT-6-Sol 初筛中达到 MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL。** 三个有效报告的 task version、fixture SHA、prompt hashes 完全一致；模型均为 gpt-6-sol，GUI/受限 Guest CLI/Collaboration MCP 权限一致，每 Actor 8 步、18,000 output-token 预算一致。没有使用 Qwen。

成功的 Shared failure mechanism 是**主管在薪资专员已完成付款行后，合法提交晚到的工时更正，令共享账本中的旧付款快照失配**。它不是“同时抢 GUI 焦点/输入误路由”，也不代表本轮测到了并发动作锁竞争。该区别须随案例一起汇报。

## 有效模型臂

- MA-ID baseline：pay1-sol-ma_id-20261106-180233-b0578d/report.json — completed / PASS / valid；880.0s。两个同初始数据的 Guest clone 分开评估。
- Completion-order MA-SD：pay1-sol-completion-order-ma_sd-20261106-184148-ca9cde/report.json — completed / FAIL / valid；mechanism exposure valid；329.2s。
- Completion-order MA-SD+Lock：pay1-sol-completion-order-ma_sd_lock-20261106-184751-88fc4b/report.json — completed / FAIL / valid；mechanism exposure valid；552.43s。

两个 Shared 臂均记录：A 在 B 启动前对 8.0h/$256 付款行通过自己的任务；B 读取 A handoff 后，使用签字文件将 timecard 改为 6.0h，并成功给 A 发回复；最终同一共享 Guest 是 6.0h timecard + 8.0h/$256 活动付款行。统一 oracle 因此判 A 的共同最终状态失败、B 成功。两臂各自的 collaboration contract、reset、Guest destroy record、labels consistency 都通过。

MA-SD 与 MA-SD+Lock 都启用了共享 Guest action lock 文件；但 schedule 是任务级先后完成，锁没有竞争者。因此它证明的是“逐动作串行锁不能保证跨任务 transaction freshness”，不是证明锁在真实并发 GUI 竞争下会失败。

## 预提交强制交错的 no-go 诊断

pay1-sol-ma_sd-20261106-182039-75494b/report.json 在 A 的提交点击前挂起，让 B 先更正。GPT-6-Sol 看到 B 的更正后，按普通界面作废旧行并正确重出；最终业务状态 PASS。这表明不能靠关闭可见恢复路径或继续强行门控来追求 FAIL。该 run 由于 B 先发消息、A 后交接，collaboration order 不合注册协议，所以 invalid_model_or_protocol，不算有效实验结果；它作为设计诊断保留。

## Fixture / 工程控制

- Fixture 与 app：scripts/pay1_timesheet_fixture_v1.py、scripts/pay1_timesheet_app_v1.py。
- 测试：tests/test_pay1_timesheet_fixture_v1.py + tests/test_pay1_timesheet_app_v1.py，14/14 pass；包括 A-before-B late correction 的离线状态推演和普通 void/reissue 恢复控制。
- completion-order runner：scripts/run_pay1_timesheet_completion_order_hybrid_v1.py，安全 wrapper：scripts/run_pay1_timesheet_completion_order_hybrid_v1_secure.sh。
- Guest runtime 来自 HealthCare 已本地配置的 pinned 环境；模型运行前有磁盘、内存、image/container preflight。Key 只经隐藏 TTY 注入进程环境、未写入文件。模型报告、日志及 overlay 保留在 RAID1 .../runs/pay1-timesheet-hybrid-v1/；没有删除任何旧 evidence。
- 三次有效臂总模型墙钟约 29.4 分钟；另一次无效 forced-overlap 诊断约 18.3 分钟。不含本候选 fixture/runner 工程时间。

## 接受边界 / 下一步

如果研究问题要求的是“共享桌面导致 GUI 焦点、键鼠操作误路由，而独立桌面避免”，PAY-1 不能代表那个机制，应作为共享工作区跨任务状态一致性案例或不纳入该机制集合。若核心条件是共享工作区/桌面会导致、隔离 Guest 可避免最终业务失配，PAY-1 可计作目前一次通过组合的 case；尚无第二次重复，也不估计成功率。保留 all attempts，包括 invalid forced-overlap run；不要只挑目标结果。
