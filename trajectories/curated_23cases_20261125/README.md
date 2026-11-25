# Curated 23 High-Quality Cases — Full Dual-Model Trajectories (`92` Episodes / `184` Agent Runs)

本目录完整收录精选 23 道高质量双智能体（`GUI + CLI`）基准在 **`gpt-6.1-sol (high)`** 与 **`gpt-6-astra (high)`** 上的全部 **`92` 局（`184` 个 Non-YOLO 容器角色实例）** 原始轨迹，对应机器可读总表为 [`lists/curated_23cases_and_trajectories_20261125.json`](../../lists/curated_23cases_and_trajectories_20261125.json)，中文总说明见 [`docs/CURATED_23CASES_AND_TRAJECTORIES_20261125_ZH.md`](../../docs/CURATED_23CASES_AND_TRAJECTORIES_20261125_ZH.md)。

## 目录层级与字段说明

每道题目按 `<CASE_ID>/<mode>_<model>/` 组织（每题 4 局：单人/顺序基线 + `shared` 并发 × 双模型）：

- `grade.json` / `report.json`：离线只读判分明细（逐子项布尔结果、错误信息、墙钟耗时）。
- `shared_timeline.json`（并发局）：双角色毫秒级交错时间线（含每次动作前后的 X11 活动窗口 ID/标题、光标坐标、剪贴板、XKB 布局、焦点翻转与误路由按键统计）。
- `tickets/<role>/task.md`：对应角色实际收到的任务工单。
- `actor_<role>/actions.jsonl`：该角色全部 GUI 驱动调用与 `guest_bash` 命令的参数、起止时间戳与耗时。
- `actor_<role>/codex_events.jsonl`：完整 Codex 事件流（含推理摘要、中间 commentary、MCP 工具调用与返回文本、Token 用量；内联 Base64 截图已脱敏替换为 `<BASE64_OMITTED:...chars>` 以保持轻量纯文本可读）。
- `actor_<role>/permission-audit-verified.json`：Non-YOLO 容器沙盒审计凭证。
