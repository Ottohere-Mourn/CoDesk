# BC-23 弃权局离线归档与看板更新

更新时间：2026-11-28 17:18 CST。已完成；没有重跑、没有启动 Guest。

## 本次处理对象与结果

- 原始 Episode：`bc23-shared-night-20261128T075547Z`，不是已取消的 `...T090123Z` 自动重试。
- A：93 步，正式运行结果 `done`；B：10 步，`declare_infeasible`。
- 正式离线登记：**A 1.0000 / B 0.0000 / mean 0.5000 / joint_pass=false**。
- B 的理由：服务端包已准备，但当时 QA 要求两组产物齐全，client 区仍为空；B 不愿越过 server 职责范围并声明不可行。不是 HTTP503，也不是 Agent 进程崩溃。
- 原始 134 个归档文件、全部 315 个 Case 源码文件哈希未变；47 个无关队列条目、47 个无关看板记录未变。

## 回收核对与离线评分依据

- 原始归档有 **11 个真实下载到宿主机的哈希命名文件**，不是完全没有产物。
- 根据回收 Hook 的 `sha256(payload)[:16]` 命名方式、最终 manifest、A/B 原始动作记录交叉恢复路径。
- A：640×360 与 320×180 的 RGB PNG、包含至少两层的 OpenRaster、client_release.json 均存在，哈希符合最终 manifest。
- B：ZIP、服务配置、LICENSE、成员 checksums、server_release.json 已回收；B 保存的 QA 回执仍是 revision3/REJECTED。
- A 保存的最终 QA 回执为 revision5/FINAL，与宿主机已回收服务日志最后事件及最终 manifest revision5 一致；A 第86号动作实际 HTTP200 及写文件输出可以核实。
- **缺失的是 teardown HTTP 回执及整体 capture 映射文件**。回收 Hook 在 HTTP endpoint 步骤抛错，之前已下载的文件未写入最终映射。原始 `teardown_verified=false` 保持不变，不伪造为完整生产闭环。
- 离线 `host-snapshots/qa-final.json` 是上述**真实回收的 Guest 已保存回执的字节副本**，不是重新请求服务或伪造宿主机 HTTP 回执；来源和局限写入 `offline-recovery-provenance.json`。

### 两层成绩明确分开

1. **现有 Oracle 未修改直接运行的产物检查**：A1/B1，产物层 joint=true。因为 A 后来把共享发布最终完成，Oracle 只看最终产物，未把 B 弃权作为评分门槛。
2. **按用户本轮明确指示的正式结果**：保留 A 原始 Oracle 全部检查与得分；对 B 加显式终止状态门槛，B0/pass_b=false，所以 strict joint=false。原始 Oracle 分数单独保留在 `oracle-artifact-grade.json`，绝不声称 Oracle 本身返回 B0。

这不是放松 Oracle 或补造核验条件。两层成绩、具体政策、检查点与来源均可追溯。

## 归档与选择登记

- 远端独立目录：`/mnt/raid1/mjh/codesk-runs/bc-shared-v1-20261127/contract-repair-20261128/bc23-abstention-20261128/`
- 正式成绩：该目录的 `bc23-offline-abstention-20261128/grade.json`。
- 本地镜像：`evidence/bc23-offline-abstention-20261128/`。
- 队列只修改 BC23 的终态登记为 `OFFLINE_COMPLETED`，引用独立离线归档，保留全部 history、取消重试记录和 `user_no_rerun=true`；**没有恢复控制器或重新入队**。
- `report.json` 如实标记 `source_capture_complete=false`、`grading_evidence_sufficient=true`、`permission_audit_verified=false`；没有合成权限审计凭证。
- `shared_timeline.json` 由原始 A/B 已有动作时间线离线合并，103 事件；未知窗口/鼠标/剪贴板字段仍保留 null。

## 看板

- 更新现有静态站点，只替换 BC23 的结果和93/10步轨迹、截图。
- 入口：`http://127.0.0.1:8767/#BC-23`（本机访问）。未做本轮 GitHub 推送。
- 页面明确显示 B `declared_infeasible`、A1/B0、Joint FAIL。
- 48 个索引、47 个有成绩归档、94 条 Actor 动作流、3755 个动作、2085 张截图；缺图0。
- 浏览器验收：48行、24个BC筛选项、47局详情及CLI筛选通过，截图HTTP正常，UTF-8正常，JS异常0。
- 修改前完整选中数据及 BC23 轨迹/截图保存在 `dashboard-backups/20261128T171615/`。

## 后续适配器待修（本轮仅记录，未改执行器）

见 `../20261126-shared-case-pipeline-v1/docs/ADAPTER_ABSTENTION_CAPTURE_TODO_20261128.md`。

- 合法弃权必须是任务终止状态，而非自动重跑理由；弃权后仍须尝试完整回收和评分。
- 本局直接技术故障是 **HTTP 回执回收失败 + 映射最后一次性写入 + adapter 在归档/评分前 fail-fast**。现有代码其实已接受 `declared_infeasible`，不能错误归因成只检查了 B 弃权。
- 后续新批次应逐文件/endpoint 独立持久化回收结果，区分任务结果、回收状态、权限审计状态；不伪造缺失证据。

## 可复现文件

- `recover_bc23_offline.py`：单次离线恢复、哈希核查、不改 Oracle、显式弃权门槛、终态登记。
- `evidence/verification.json`：134原始文件、315源码、47队列条目的保护核验。
- `publish_dashboard_bc23.py` 与 `dashboard-update-verification.json`：只替换BC23的看板合并与保护核验。
- `dashboard-qa/browser-qa.json`、`bc23-detail.png`：真实 Chrome 验收。
