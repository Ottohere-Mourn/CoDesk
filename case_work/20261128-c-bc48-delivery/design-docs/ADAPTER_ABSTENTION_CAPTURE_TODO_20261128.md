# 待修：合法弃权的回收、评分与调度终态

记录日期：2026-11-28；适用未来新批次/游戏 Case。本次仅记录，不修改生产适配器，不重跑 BC23。

## 事实与定位

BC23 `bc23-shared-night-20261128T075547Z`：A done93步、B declare_infeasible10步，正式进程exit0。11个真实文件已下载，但整个回收receipt缺失，未生成grade。

- `pipeline/runner_hooks/formal_capture.py:321–331`：文件已写入 `guest-files/<内容SHA前16位>`，映射只放在内存列表。
- 同文件 `:346–348`：HTTP receipt失败直接抛 `Guest loopback HTTP receipt could not be recovered`。
- 同文件 `:361`：所有请求结束后才写 `snapshot-capture.json`，某一HTTP失败会丢失之前文件的映射。
- `pipeline/formal_osworld_backend.py`：`teardown_ok` 为false时 aggregate state=failed；但该后端已经把合法弃权映射为 `declared_infeasible`。
- `pipeline/episode_adapter.py:429–430`：aggregate failed 在标准归档/回收/评分之前抛错；后面的终态检查本已接受 `completed` 和 `declared_infeasible`。
- 控制器将此归为脚本错误并自动重试，混淆了合法任务弃权与回收失败。用户已取消自动重试。

因此不得声称“本局仅因 declare_infeasible 被判系统崩溃”。直接技术故障是回收失败；同时应明确保障合法弃权不跳过回收、评分或被自动重跑。

## 后续实现验收要求

1. 把 Actor outcome（done/abstained/timeout/error）、capture completeness、permission audit、Guest cleanup、Oracle evaluation 分开记录。
2. 两个 Actor 均进入合法终态（含弃权）后，照常在 teardown 前尝试 allowlist 回收和评分；不能把弃权当系统崩溃。
3. 每个文件/endpoint 独立回收、独立写入映射/失败记录；单个HTTP失败不得抹掉已下载文件的路径和SHA。
4. 所有可用证据都保留；缺少关键证据就明确未评分/缺证据，不伪造服务回执、权限凭证或成功teardown。
5. 原始产物评分与终态政策分别可审计；若采用“弃权方0分”，必须在 schema/metadata/Prompt契约中明确，而非静默改写Oracle。
6. 调度器按任务语义处理弃权：登记观察结果，不自动重试；只有明确可重试的基础设施错误才按既有政策重试。
7. 测试覆盖：A完成/B弃权；A弃权/B继续完成；弃权且产物齐全；HTTP失败但文件已回收；单文件缺失；权限证据缺失；清理失败；其中任何情形不得伪造凭证。

## 本局补登记

真实回收文件加 A 保存的 QA FINAL 回执（原始动作86/日志/manifest revision5交叉一致）足够执行现有离线Oracle。原始Oracle产物检查A1/B1另存，按用户明确要求加B弃权门槛，正式A1/B0，joint=false。原始归档及Oracle未改，无重跑。
