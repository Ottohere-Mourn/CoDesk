# CoDesk 双智能体工作流卡片：V43–V47

更新：2026-11-17
分支：`codex/all-codesk-cases-20261113`
代码根目录：`/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112`

## 设计口径

这五题是**行业工作流变体**，用于扩展双 Agent 的真实业务表单场景；不是五种不同的底层并发机制。它们复用已有 Synthetic Desk：两名 Agent 分别负责同一条记录的 A/B 两个工作面板，单桌面下共享 `active_panel` 与窗口状态；两个面板字段互不重叠。研究假设仍是：独立桌面可完成，切到共享桌面时可能发生活动面板争用。模型 FAIL 必须来自有效运行和 Oracle，不从 scripted 控制或 timeout 推断。

## 候选卡

| ID | 实务工作流 | Agent A | Agent B | 主要共享状态 / 可观察失败 | 相对已有题的差异与风险 |
|---|---|---|---|---|---|
| **V43 — Bayview Construction RFI & Site Work Package** | 施工图纸澄清及施工包同步 | 处理 `RFI-731`：批准状态、图纸页、详图、回复期限 | 更新受影响区域、专业工种、班次及工作包版本 | 共享当前记录 / 活动面板；一方可能在切面板后把另一表单输入到错误上下文 | 从既有许可/质量题转向设计澄清—施工执行交接；部分表单机制相同 |
| **V44 — Goodline Food Rescue Intake & Distribution** | 食品救援接收筛查与机构配送 | 判定 `DON-244` 接收处置、温度、保质期、供货批号 | 编制受赠食物的接收机构、数量、时窗和路线 | 接收/配送分别独立保存，但共享当前业务面板；错面板会造成配送记录漏填或筛查记录不完整 | 与 V3 社区食品站排班、V16 冷链、V38 召回不同，聚焦“可食捐赠批次→ pantry 配送” |
| **V45 — Metro Heat Response Cooling Center & Shuttle** | 高温天气公共避暑点启动及接驳 | 启用 `HEAT-305`：开放状态、站点、容量、启动引用号 | 配置车辆、线路、接驳时段、派车引用号 | 避暑点与接驳安排依赖同一事件记录；面板切换可能导致 Agent 把调度字段留空 | 聚焦热浪公共服务开点，不是机场乘客协助或一般线路覆盖；热浪人身安全风险只在合成情境中 |
| **V46 — Lakeside Credit Union Card Dispute & Member Support** | 银行卡争议审核与会员补卡 | 审核 `DIS-882`：决定、交易号、争议金额、审核引用号 | 对应冻结/补发动作、补卡尾号、取卡方式、服务引用号 | 争议与补卡状态需在同一案件上下文协调；错误面板可导致一半流程遗漏 | 金融服务事件与旧供应商应付/保险理赔不同；全部账户、金额、卡号均为虚构 |
| **V47 — CivicWeb Accessibility Triage & Release Gate** | 数字无障碍缺陷分级与发布门禁 | 登记 `AX-417`：严重级别、受影响组件、WCAG 条款、修复票号 | 对构建设置 HOLD/VERIFIED/EXCEPTION，记录构建、浏览器和验证引用号 | 缺陷审查与版本门禁共用活动工作区；并发下可能发生发布门禁与缺陷上下文错位 | 与 V26 版权发布、V25 安全事件不同，重点为键盘可达性合规与发布阻断 |

## Fixture、任务类、Oracle

- Fixture schema/data：`tasks/paragui/v456_data.json` 中的 `v43`–`v47`。
- Fixture builder / Web app：`tasks/paragui/build_v456.py`、`tasks/paragui/app_v456_template.py`。
- 双角色 OSWorld adapter：`tasks/paragui/pg_v43.py`–`pg_v47.py` 及对应 `task_pgv*.py`。
- Oracle：`tasks/paragui/pg_v456_oracle.py`。默认精确匹配；仅数值字段支持数值等价、V44 use-by 支持常见日期格式，少数明确的自然语言字段允许忽略大小写/多余空白。引用号、状态枚举、交易号、构建号仍严格匹配。
- 自动化 Oracle tests：`tests/test_v456_oracles.py`。截至本批实现，完整文件测试为 **63 passed**，包括新题种子正例、错误值负例、字段隔离、资产重建、五个本地 HTTP 页面/保存路由 roundtrip 及有限的数值/日期/大小写等价检查。该 HTTP roundtrip 仍不是 OSWorld Guest GUI 控制。
- OSWorld Guest scripted joint 正控已完成 **5/5**（五题各自 A/B 均为 1.0）：V43 `cdesk3-v43-scripted-joint-20261117T101342Z-4076241`，V44 `...T101910Z-4078443`，V45 `...T102444Z-4080659`，V46 `...T102745Z-4082142`，V47 `...T103044Z-4083593`。结果、截图和 overlays 留在 RAID 的 `runs/triplets/` 与 `overlays/`；每次仅启动自己的动态分配 Docker Guest，未停止/重置外部 `sharp_bhabha`。

## 复现/实验入口

```bash
cd /home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
export REPRO_ROOT=/mnt/raid1/mjh/Projects/codesk-v43-v47-20261117
export CO_DESK_ASSETS_ROOT="$REPRO_ROOT/assets"
export CO_DESK_RUN_ROOT="$REPRO_ROOT/runs/triplets"
export CO_DESK_OVERLAY_ROOT="$REPRO_ROOT/overlays"
export CO_DESK_OVERLAY_ARCHIVE_ROOT="$REPRO_ROOT/overlays"
export CO_DESK_CODEX_RUNTIME_ROOT=/home/mjh/.cache/codesk-v43-v47-runtime
export CO_DESK_API_BASE_URL=https://docode.cc/v1
for c in v43 v44 v45 v46 v47; do
  python tasks/paragui/build_v456.py "$c" "$CO_DESK_ASSETS_ROOT/$c"
done
# 设置 OPENAI_API_KEY 时只通过 shell secret store/交互注入，不写入仓库或运行报告。
for c in v43 v44 v45 v46 v47; do
  bash scripts/run_new_case_arm.sh "$c" ma-id
  bash scripts/run_new_case_arm.sh "$c" shared
  bash scripts/run_new_case_arm.sh "$c" shared-lock
done
```

单题 scripted joint GUI 正控入口为 `scripts/run_v456_guest_control.py v43` 至 `v47`。GPT-6-Sol 三臂均已完成：V43 在原 task wording 下曾有 A=0/B=1；截图确认 A 录入 `3`，而 source 为 `Detail 3`，因此明确要求精确抄录含 `Detail` 前缀并按新指令重跑 MA-ID，修订后 A/B 均 PASS。其他四题使用原指令和同一 Oracle。5/5 题 MA-ID 均为 A/B 双 PASS；5/5 配对级 Shared 与 Shared+Lock 均失败至少一角色；V43、V45、V47 在同一角色上达到 `PASS → FAIL → FAIL`；V44/V46 虽然配对失败持续，但失败角色在两共享臂间切换。V47 首次 Shared 的 B runner 退出码错误，证据予以保留，并仅作一次 infrastructure retry 后取得有效 arm 结果；未把无效首跑计作 FAIL。完整 run IDs/token/time 见 [模型结果审计](../tasks/paragui/V43_V47_MODEL_RESULTS_20261117_ZH.md)。

## 互补性 / 局限

DockerProvider 使用锁保护的动态端口分配；本批 scripted Guest 正控与三臂实验均已完成，外部 `sharp_bhabha` 与其 QEMU 未被停止/重置。五题覆盖建筑、食品救援、极端高温响应、金融争议和数字无障碍业务表面，但底层竞争仍是 Synthetic Desk 的共享活动面板/当前记录；五题是行业任务变体，不是五种独立机制。已观察到稳定的配对级干扰，但该结果仍基于合成 Web App；若作为主结果，下一步应优先验证到真实生产软件/OS-level contention，而非继续堆叠同一 active-panel 机制的表层案例。
