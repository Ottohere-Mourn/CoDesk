# C01–C24 + BC01–BC24：GUI + 可读写 CLI 本轮交付

更新日期：2026-11-28。**48 个 Case 索引，47 个有成绩结果，1 个网络失败暂缓（C08）**。本交付与学长的 Curated-23 是不同批次，不替换其结果。

## 先看哪里

- **[静态轨迹看板目录](dashboards/c_bc_48_open_cli_20261128/)**：`index.html`、内嵌数据、逐步工具调用、截图和评分详情。
- **[48 例成绩表 CSV](dashboards/c_bc_48_open_cli_20261128/scores48.csv)**、[完整统计 JSON](dashboards/c_bc_48_open_cli_20261128/final-report.json)。
- **[机器可读总索引](../lists/c_bc_48_open_cli_20261128.json)**：Case → 源码快照 → 选中 Episode → 轨迹 → 分数。
- **[96 条角色轨迹及已有运行证据](../trajectories/c_bc_48_open_cli_20261128/)**。
- **[48 例任务/服务/Oracle 源码快照与 BC 流水线](../case_work/20261128-c-bc48-delivery/)**。

## 学长怎么打开看板

GitHub 文件页只显示 HTML 源码，**不是已经部署的在线网站**。本次没有改仓库的 Pages 设置。下载或拉取本分支后即可本地打开，页面无后端依赖：

```bash
git clone --depth 1 --single-branch --branch codex/c-bc48-gui-cli-dashboard-20261128 https://github.com/Ottohere-Mourn/CoDesk.git CoDesk-48cases
cd CoDesk-48cases
python -m http.server 8767 --directory docs/dashboards/c_bc_48_open_cli_20261128
```

浏览器访问 **http://127.0.0.1:8767/**。也可在 GitHub 选中交付分支，`Code → Download ZIP`，解压后直接双击该目录的 `index.html`（已做真实 Chrome 的 `file://` 验证）。下载包含全部截图，体积约 0.5 GB。

交付分支：`codex/c-bc48-gui-cli-dashboard-20261128`。主聚合分支：`codex/all-codesk-cases-20261113`。实际推送情况以发布记录为准。

## 本轮内容与口径

- Shared 双人模式；本包没有新增 Isolated 对照。
- **96/96** 条角色 `actions.jsonl`，包含 C08 的失败局轨迹。
- **96/96** 条 `codex_events.jsonl`，优先采用原始规范化归档；没有该文件时从已保存的 Codex JSON stdout 提取，来源与非 JSON 行数记录在每局 `archive-availability.json`。
- **2165 张选中轨迹截图**，集中存放在看板的 `assets/`，不重复提交历史尝试截图。47 个有成绩结果的统计包含 2108 张，C08 失败轨迹另有57张。
- 已有 **46 份**权限审计凭证如实归档；C 系列没有的凭证、BC23 未完成生成的凭证不补造。
- 内嵌 Base64 图片已占位符轻量化，工具参数/返回、文本与推理事件保留；推送前扫描私钥、Token、Bearer、带凭据 URL、代理配置。
- C 系列保留原始连续分，不伪造严格 `joint_pass`；BC 系列使用当前选中的严格评分。GUI 时间邻近仅为交叠候选，不宣称都是已证实冲突。
- 源码快照忠实保留实际 staging/部署状态，没有借本次推送修改旧任务或重写其 Prompt；源码/任务素材生成器不等于打包了 OSWorld 镜像、API 凭据和所有外部依赖。

## 两个特别登记

### C08：已结束，不再显示 RUNNING

- 最新 Episode：`CONC-08-codex-shared-20261128T062013Z`。
- **2026-11-28 15:35（北京时间）结束**；A27步、B61步。
- B：`stream disconnected before completion: Upstream service temporarily unavailable`。
- 状态 `DEFERRED_NETWORK`；没有有效最终分数，分数字段为 null，**不当作0分，也不冒充成功**。保留失败动作与截图，本次没有重跑。

### BC23：合法弃权局，已离线登记

- 原始 Episode：`bc23-shared-night-20261128T075547Z`，A93步 done、B10步 declare_infeasible。
- 真实回收的11个文件经哈希、manifest、原始动作与服务日志交叉核对；A保存的最终 QA 回执可核实。原始 HTTP 回收步骤失败仍如实保留，没有伪造完整 teardown/权限证据。
- **正式登记 A1.0000 / B0.0000 / joint_pass=false**：A 使用未修改 Oracle 的真实产物检查；B 按用户明确指示应用弃权零分终态门槛。
- 原始 Oracle 只看最终共享产物，因此给出 A1/B1；该结果另存 `oracle-artifact-grade.json`。不得将正式 B0 误称为原始 Oracle 的直接输出。
- 原始归档、自动重试取消记录、原始 Oracle 分数保留；没有重跑。后续适配器待修项在源码快照 `design-docs/ADAPTER_ABSTENTION_CAPTURE_TODO_20261128.md`。

## 最新 B 类结果

| Case | A/B 步数 | A/B 分数 | strict joint_pass |
|---|---:|---:|---|
| BC11 | 36 / 42 | .5000 / .5000 | false |
| BC12 | 9 / 25 | .5500 / 1.0000 | false |
| BC19 | 4 / 4 | 1.0000 / 1.0000 | true |
| BC20 | 28 / 45 | 1.0000 / 1.0000 | true |
| BC23 | 93 / 10 | 1.0000 / .0000 | false |
| BC24 | 61 / 47 | .0000 / .0000 | false |

BC 当前严格 joint_pass 共 **15/24**。BC03/05/06/17/21 的收紧结果及回归证据保留在源码快照 `audit/`；没有恢复先前被纠正的放宽条件。

## 保护边界

本次只新增独立交付目录及导航链接；不覆盖服务器原始归档、不修改旧 C01–C24 代码、不重启/清理其他会话、不重新派发实验。GitHub 认证凭据由本机 Git Credential Manager 保存，不进入本仓库。
